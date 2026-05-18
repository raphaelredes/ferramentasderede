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
from api.routes import system, network, security
from src.system.backup import BackupManager
from src.core.database import db as _db
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
    """Persistência granular das mudanças emitidas pelo monitor.

    Antes: cada update (1×/s por host) chamava replace_all_hosts → DELETE+INSERT
    da tabela inteira. Em 100 hosts isso era ~100 reescritas/s. Agora mapeamos
    cada chave volátil para uma coluna e fazemos UPDATE granular protegido pelo
    write lock + retry do DatabaseManager. Chaves não-mapeadas caem no fallback
    antigo (raro — só quando mudam ports, group etc., que não vêm do monitor).
    """
    try:
        db_fields = {}
        fallback_needed = False
        for key, value in updates.items():
            if key in _MONITOR_TO_DB_FIELD:
                db_fields[_MONITOR_TO_DB_FIELD[key]] = value
            elif key == 'ip':
                # 'ip' do monitor é o address resolvido — só relevante quando o
                # host foi cadastrado por hostname. Não persistimos a cada tick.
                continue
            else:
                fallback_needed = True

        if db_fields:
            _db.update_host_fields(address, db_fields)

        if fallback_needed:
            # Caminho raro: chave não mapeada — ler o row do DB, aplicar updates
            # whitelisted e UPSERT individual via save_host (NÃO save_hosts_list,
            # que chama replace_all_hosts e apagaria os outros hosts).
            row = next((r for r in _db.get_all_hosts() if r.get('address') == address), None)
            if row:
                # tags/ports são colunas JSON: deixar passar se vierem como list.
                for key, value in updates.items():
                    if key in _MONITOR_TO_DB_FIELD or key == 'ip':
                        continue
                    if key in ('tags', 'ports'):
                        row[key] = value
                _db.save_host(row)

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
        # Run in thread to not block startup
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

# CORS — locked to local origins by default. There are two renderers:
#  * Electron dev: Vite serves the UI on http://127.0.0.1:5173.
#  * Pywebview portable build (main_webview.py): a small static HTTP
#    server hosts the UI on a fixed loopback port (default 5174 — see
#    NT_WEBVIEW_PORT). Both ends agree on that port so we keep CORS
#    pinned to a closed set of origins.
# Override by setting NT_CORS_ORIGINS to a comma-separated list.
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
    # Tightened from "*" to the actual verbs and headers we use. Wildcards
    # combined with allow_credentials=True are a defense-in-depth smell: any
    # future compromise of one of the allowed origins (the static webview port
    # has no auth and could be replaced by a malicious local process) gets to
    # speak any verb with any header. Keep the surface narrow.
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Temp-Auth", "Authorization"],
)

# Incluir Routers
app.include_router(system.router)
app.include_router(network.router)
app.include_router(security.router)

# --- Root Endpoint ---
@app.get("/")
async def root():
    # Mirror the single-source version from settings (which reads package.json).
    # The hard-coded "2.0.0" that used to live here was stale and confused
    # smoke tests against TESTES.html.
    from src.config.settings import APP_VERSION
    return {"status": "online", "version": APP_VERSION}

# --- Settings & Security Endpoints ---
# Settings moved to api.routes.settings
# Security moved to api.routes.security

from api.routes import settings

app.include_router(settings.router)

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
