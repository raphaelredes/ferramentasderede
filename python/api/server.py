from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import sys
import os
from contextlib import asynccontextmanager

# Configure the root logger eagerly. Without this, `logging.info(...)` calls
# in the route layer are silently dropped (root level defaults to WARNING).
# Idempotent: if a downstream tool already configured the root, basicConfig
# is a no-op.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Uvicorn configures its own handlers for these loggers; with `propagate=True`
# (default) each log line would also fire the root handler installed by
# basicConfig, double-printing every uvicorn message. Cut the propagation so
# uvicorn's output stays single-emit.
for _uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_uvicorn_logger_name).propagate = False

# Adicionar diretório pai ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes.network import get_hosts_list, save_hosts_list, host_monitor, manager
from api.routes import system, network, security, settings, ad_tools, metrics, l2_discovery, batch_ops, reports
from src.system.backup import BackupManager
from src.core.database import db as _db
from src.network.metrics_history import record_metric
from src.network.toast_notifier import notify_host_status_change
import asyncio

# Global event loop reference
main_loop = None

# Mapping from monitor-emitted keys to the DB column names accepted by
# DatabaseManager.update_host_fields. Anything else falls through to the slow
# read-modify-save path (rare; e.g. ports list changes).
_MONITOR_TO_DB_FIELD = {
    'hostname': 'hostname',
    'name': 'hostname',       # monitor sometimes emits 'name' (UI form) for hostname
    'domain': 'domain',
    'mac': 'mac',
    'last_status': 'last_status',
    'last_checked': 'last_checked',
    'vendor': 'vendor',
    'monitoring': 'monitoring',
}

# --- Callbacks ---
def handle_host_update(address: str, updates: dict):
    """Persistência granular das mudanças emitidas pelo monitor."""
    try:
        db_fields = {}
        fallback_needed = False
        for key, value in updates.items():
            if key in _MONITOR_TO_DB_FIELD:
                db_fields[_MONITOR_TO_DB_FIELD[key]] = value
            elif key == 'ip':
                continue
            else:
                fallback_needed = True

        if db_fields:
            _db.update_host_fields(address, db_fields)

        if fallback_needed:
            row = next((r for r in _db.get_all_hosts() if r.get('address') == address), None)
            if row:
                for key, value in updates.items():
                    if key in _MONITOR_TO_DB_FIELD or key == 'ip':
                        continue
                    if key in ('tags', 'ports'):
                        row[key] = value
                _db.save_host(row)

        # Gravar métricas históricas de forma não-bloqueante
        if 'latency' in updates or 'last_status' in updates or 'packet_loss' in updates:
            is_up = (updates.get('last_status') == 'online')
            lat = updates.get('latency')
            loss = updates.get('packet_loss', 0.0)
            jit = updates.get('jitter', 0.0)
            record_metric(
                host_id=None,
                ip_address=address,
                latency_ms=lat if is_up else None,
                packet_loss=loss,
                is_online=is_up,
                jitter_ms=jit
            )

        # Broadcast update via WebSocket
        if main_loop and main_loop.is_running():
            message = {"type": "update", "data": {address: updates}}
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)

    except Exception as e:
        logging.exception(f"Erro ao persistir atualização de host {address}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    # Initialize Backup Manager and run daily check
    try:
        backup_manager = BackupManager()
        await asyncio.to_thread(backup_manager.run_daily_backup_check)
    except Exception as e:
        logging.warning(f"Backup check failed: {e}")

    # Carregar hosts e iniciar monitoramento
    hosts = get_hosts_list()
    hosts_dicts = [h.model_dump() for h in hosts]
    host_monitor.start_monitoring(hosts_dicts, on_update_callback=handle_host_update)
    logging.info("Monitoramento de hosts iniciado.")
    yield
    host_monitor.stop_monitoring()
    logging.info("Monitoramento de hosts parado.")

app = FastAPI(title="Network Tools API", lifespan=lifespan)

# CORS — locked to local origins by default.
_webview_port = os.environ.get("NT_WEBVIEW_PORT", "5174").strip() or "5174"
_default_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    f"http://127.0.0.1:{_webview_port}",
    f"http://localhost:{_webview_port}",
]
_cors_env = os.environ.get("NT_CORS_ORIGINS", "").strip()
ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Temp-Auth", "Authorization"],
)

# Incluir Routers do Sistema e Rede
app.include_router(system.router)
app.include_router(network.router)
app.include_router(security.router)
app.include_router(settings.router)
app.include_router(ad_tools.router)
app.include_router(metrics.router)
app.include_router(l2_discovery.router)
app.include_router(batch_ops.router)
app.include_router(reports.router)

# --- Root Endpoint ---
@app.get("/")
async def root():
    from src.config.settings import APP_VERSION
    return {"status": "online", "version": APP_VERSION}

# --- Security Endpoints moved to api.routes.security ---

# --- Logging Config ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/network/status") == -1 and record.getMessage().find("/network/monitor") == -1

if __name__ == "__main__":
    # logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    # Bind locally by default so the API is not exposed to the LAN.
    # Override with NT_API_HOST=0.0.0.0 (and matching NT_CORS_ORIGINS) when needed.
    host = os.environ.get("NT_API_HOST", "127.0.0.1")
    port = int(os.environ.get("NT_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
