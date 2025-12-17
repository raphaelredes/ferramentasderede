from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import sys
import os
from contextlib import asynccontextmanager

# Adicionar diretório pai ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes.network import get_hosts_list, save_hosts_list, host_monitor, manager
from api.routes import system, network, security
from src.system.backup import BackupManager
import asyncio

# Global event loop reference
main_loop = None
# --- Callbacks ---
def handle_host_update(address: str, updates: dict):
    """Callback para persistir atualizações do monitoramento."""
    try:
        current_hosts = get_hosts_list()
        modified = False
        
        for h in current_hosts:
            if h.address == address:
                for key, value in updates.items():
                    if hasattr(h, key):
                        current_val = getattr(h, key)
                        if current_val != value:
                            setattr(h, key, value)
                            modified = True
                break
        
        if modified:
            print(f"Persistindo atualização para {address}: {updates}")
            save_hosts_list(current_hosts)
            
        # Broadcast update via WebSocket
        if main_loop and main_loop.is_running():
            # Send structured update: {ip: {key: value}}
            message = {"type": "update", "data": {address: updates}}
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)
            
    except Exception as e:
        print(f"Erro ao persistir atualização de host: {e}")

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
        print(f"Warning: Backup check failed: {e}")

    # Carregar hosts e iniciar monitoramento
    hosts = get_hosts_list()
    hosts_dicts = [h.model_dump() for h in hosts]
    host_monitor.start_monitoring(hosts_dicts, on_update_callback=handle_host_update)
    print("Monitoramento de hosts iniciado.")
    yield
    host_monitor.stop_monitoring()
    print("Monitoramento de hosts parado.")

app = FastAPI(title="Network Tools API", lifespan=lifespan)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir Routers
app.include_router(system.router)
app.include_router(network.router)
app.include_router(security.router)

# --- Root Endpoint ---
@app.get("/")
async def root():
    return {"status": "online", "version": "2.0.0"}

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
    uvicorn.run(app, host="0.0.0.0", port=8000)
