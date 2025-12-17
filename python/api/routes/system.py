from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
import time
import sys
import os
import contextlib
import logging
import io

# Adicionar diretório pai ao path para importar módulos do src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.system.tools import SystemTools
from src.system.core.winrm_handler import WinRMHandler, TemporaryTrustedHosts

# Mock para a classe App (Tkinter) que o SystemTools espera
class AppMock:
    def translate(self, key, **kwargs):
        return key

sys_tools = SystemTools(AppMock())

router = APIRouter(prefix="/system", tags=["system"])

class SystemInfoRequest(BaseModel):
    target_ip: str
    username: str
    password: str

class ServicesRequest(BaseModel):
    target_ip: str
    username: str
    password: str

class ServiceManageRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    service_name: str
    action: str # "start", "stop", "restart", "pause", "set_startup"
    startup_type: str | None = None

class LogsRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    log_name: str = "System"
    level: str = "Error" # "Error", "Warning", "Information"
    count: int = 20

class DisconnectRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    session_id: str

class PowerRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    action: str # "shutdown", "restart", "logoff"
    message: str = "Manutenção Programada"
    timeout: int = 30
    force: bool = False

class TestConnectionRequest(BaseModel):
    target_ip: str
    username: str
    password: str

def get_trusted_hosts_context(ip: str, auth_header: str):
    """Retorna o context manager apropriado baseado no header."""
    if auth_header == "true":
        return TemporaryTrustedHosts(ip)
    return contextlib.nullcontext()

@router.post("/info")
def system_info(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    """Obtém informações detalhadas do sistema (OS, Hardware) via WMI."""
    try:
        with get_trusted_hosts_context(request.target_ip, x_temp_auth):
            result = sys_tools.get_remote_system_info_raw(
                request.target_ip,
                request.username,
                request.password
            )
            
        if "error" in result:
            # Se for erro de TrustedHosts, retorna 403 com código específico
            if result.get("error") == "TRUSTED_HOSTS_REQUIRED":
                raise HTTPException(status_code=403, detail="TRUSTED_HOSTS_REQUIRED")
            raise HTTPException(status_code=500, detail=result["error"])
        # return result removed to allow update logic below
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor: {str(e)}")

    # Update host with current user if available
    if isinstance(result, dict) and "CurrentUser" in result and result["CurrentUser"] != "N/A":
        try:
            from api.routes.network import get_hosts_list, save_hosts_list, host_monitor
            current_hosts = get_hosts_list()
            target_host = next((h for h in current_hosts if h.address == request.target_ip), None)
            if target_host:
                target_host.current_user = result["CurrentUser"]
                save_hosts_list(current_hosts)
                # Optional: update monitor if needed, but maybe not strictly necessary for just this field
                # host_monitor.update_hosts([h.dict() for h in current_hosts]) 
        except Exception as e:
            print(f"Erro ao atualizar CurrentUser no host: {e}")

    return result

@router.post("/services")
def list_services(request: ServicesRequest, x_temp_auth: str = Header(default=None)):
    """Lista todos os serviços do host remoto."""
    try:
        with get_trusted_hosts_context(request.target_ip, x_temp_auth):
            result = sys_tools.get_remote_services(
                request.target_ip,
                request.username,
                request.password
            )

        if isinstance(result, dict) and "error" in result:
            if result.get("error") == "TRUSTED_HOSTS_REQUIRED":
                raise HTTPException(status_code=403, detail="TRUSTED_HOSTS_REQUIRED")
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor: {str(e)}")

@router.post("/services/manage")
def manage_service(request: ServiceManageRequest, x_temp_auth: str = Header(default=None)):
    """Inicia, para ou reinicia um serviço remoto."""
    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.manage_remote_service(
                    request.target_ip,
                    request.username,
                    request.password,
                    request.service_name,
                    request.action,
                    request.startup_type
                )
                for item in iterator:
                    if isinstance(item, dict) and item.get("status") == "error":
                            yield json.dumps(item).encode('utf-8') + b"\n"
                    else:
                            yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                    time.sleep(0.01)

        except Exception as e:
            # Para streaming, não podemos levantar HTTPException, temos que enviar JSON de erro
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg: # O erro pode vir encapsulado
                 yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

class SpoolerManageRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    action: str # "restart", "clear_and_restart"

@router.post("/spooler/manage")
def manage_spooler(request: SpoolerManageRequest, x_temp_auth: str = Header(default=None)):
    """Gerencia o Spooler de Impressão (Reiniciar, Limpar)."""
    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.manage_spooler(
                    request.target_ip,
                    request.username,
                    request.password,
                    request.action
                )
                for item in iterator:
                    if isinstance(item, dict) and item.get("status") == "error":
                            yield json.dumps(item).encode('utf-8') + b"\n"
                    else:
                            yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                    time.sleep(0.01)

        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/logs")
def get_logs(request: LogsRequest, x_temp_auth: str = Header(default=None)):
    """Obtém logs de eventos do Windows."""
    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.get_remote_event_logs(
                    request.target_ip,
                    request.username,
                    request.password,
                    request.log_name,
                    request.level,
                    request.count
                )
                for item in iterator:
                    yield json.dumps(item).encode('utf-8') + b"\n"
                    time.sleep(0.01)
                
        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"error": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"error": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/teamviewer")
def get_teamviewer_id(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    """Obtém o TeamViewer ID do host remoto."""
    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.get_remote_teamviewer_id(
                    request.target_ip,
                    request.username,
                    request.password
                )
                for item in iterator:
                    if isinstance(item, tuple) and len(item) == 2:
                        msg, data = item
                        yield json.dumps({"status": "success", "message": msg, "data": data}).encode('utf-8') + b"\n"
                    elif isinstance(item, dict) and "error" in item:
                            yield json.dumps(item).encode('utf-8') + b"\n"
                    else:
                        yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                    time.sleep(0.01)

        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/sessions")
def list_sessions(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    """Lista sessões de usuários conectados."""
    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.list_connected_users(
                    request.target_ip,
                    request.username,
                    request.password
                )
                for item in iterator:
                    if isinstance(item, tuple) and len(item) == 2:
                        msg, data = item
                        yield json.dumps({"status": "success", "message": msg, "data": data}).encode('utf-8') + b"\n"
                    elif isinstance(item, dict) and "error" in item:
                            yield json.dumps(item).encode('utf-8') + b"\n"
                    else:
                        yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                    time.sleep(0.01)

        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/disconnect")
def disconnect_session(request: DisconnectRequest, x_temp_auth: str = Header(default=None)):
    """Desconecta uma sessão de usuário."""
    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.disconnect_user(
                    request.target_ip,
                    request.username,
                    request.password,
                    request.session_id
                )
                for item in iterator:
                    yield json.dumps(item).encode('utf-8') + b"\n"
                    time.sleep(0.01)

        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/power")
def power_action(request: PowerRequest, x_temp_auth: str = Header(default=None)):
    """Executa ações de energia (shutdown, restart, logoff) ou envia mensagens via WinRM."""
    
    if request.action == "message":
        def event_generator():
            try:
                with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                    iterator = sys_tools.send_message(
                        request.target_ip,
                        request.username,
                        request.password,
                        request.message
                    )
                    for item in iterator:
                        if isinstance(item, dict) and item.get("status") == "error":
                                yield json.dumps(item).encode('utf-8') + b"\n"
                        else:
                                yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                        time.sleep(0.01)
            except Exception as e:
                error_msg = str(e)
                if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                        yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
                else:
                        yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"
        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    flag = ""
    if request.action == "shutdown":
        flag = "-s"
    elif request.action == "restart":
        flag = "-r"
    elif request.action == "logoff":
        flag = "-l"
    elif request.action == "cancel":
        def event_generator():
            try:
                with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                    iterator = sys_tools.cancel_shutdown_command(
                        request.target_ip,
                        request.username,
                        request.password
                    )
                    for item in iterator:
                        if isinstance(item, dict) and item.get("status") == "error":
                                yield json.dumps(item).encode('utf-8') + b"\n"
                        else:
                                yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                        time.sleep(0.01)
            except Exception as e:
                error_msg = str(e)
                if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                        yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
                else:
                        yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"
        return StreamingResponse(event_generator(), media_type="application/x-ndjson")
    else:
        raise HTTPException(status_code=400, detail="Ação inválida. Use 'shutdown', 'restart', 'logoff', 'cancel' ou 'message'.")

    if request.force and flag != "-l":
        flag += " -f"

    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.execute_shutdown_command(
                    request.target_ip, 
                    request.username, 
                    request.password, 
                    flag, 
                    request.message, 
                    request.timeout
                )
                for item in iterator:
                    if isinstance(item, dict) and item.get("status") == "error":
                            yield json.dumps(item).encode('utf-8') + b"\n"
                    else:
                            yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                    time.sleep(0.01)
                
        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"status": "error", "message": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.get("/trusted-hosts")
def get_trusted_hosts_status():
    """Verifica o status do TrustedHosts."""
    # Retorna o valor atual
    current = WinRMHandler.get_trusted_hosts()
    return {"configured": current == "*", "value": current}

@router.post("/trusted-hosts")
def configure_trusted_hosts():
    """Configura o TrustedHosts para '*' (permitir tudo)."""
    # Define como '*'
    success = WinRMHandler.set_trusted_hosts("*")
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao configurar TrustedHosts.")
    return {"success": True}
    return {"success": True}

@router.post("/test-connection")
def test_connection(request: TestConnectionRequest, x_temp_auth: str = Header(default=None)):
    """Testa a conexão WinRM e retorna logs detalhados."""
    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)
    
    # Capturar logs do root logger
    logger = logging.getLogger()
    logger.addHandler(ch)
    
    result = {"success": False, "error": "Unknown"}
    
    try:
        with get_trusted_hosts_context(request.target_ip, x_temp_auth):
            handler = WinRMHandler(request.target_ip, request.username, request.password)
            result = handler.connect()
            handler.close()
    except Exception as e:
        result = {"success": False, "error": str(e)}
    finally:
        logger.removeHandler(ch)
        logs = log_capture_string.getvalue()
        
    return {"result": result, "logs": logs}
