from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from typing import Optional
import json
import asyncio
import re
import time
import sys
import os
import contextlib
import logging
import io


# Strict allowlist for target_ip. Accepts IPv4 literal OR a clean DNS
# label/FQDN (letters, digits, dot, hyphen, leading alphanumeric, max 253).
# Used by every /system/* Pydantic request — `target_ip` flows verbatim into
# PowerShell templates (e.g. get_system_info.ps1: `__TARGET_IP__`) via
# str.replace, so a value containing `$(...)` or `"` would interpolate into
# the script. Validating the *shape* here closes that path without trusting
# the PS author to remember to escape.
_TARGET_IP_RE = re.compile(r"^(?:(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9][A-Za-z0-9._\-]{0,252})$")


def _validate_target_ip(value: str) -> str:
    if not isinstance(value, str) or not _TARGET_IP_RE.match(value):
        raise ValueError(f"target_ip inválido: {value!r}")
    # Extra octet check for IPv4 form
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
        if not all(0 <= int(o) <= 255 for o in value.split(".")):
            raise ValueError(f"target_ip inválido (octeto fora de [0,255]): {value!r}")
    return value

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
    username: str = ""
    password: str = ""
    # When set, resolve username/password from the unlocked vault. Lets the UI
    # silently fetch info (e.g. TeamViewer ID) using the configured default
    # credential without ever exposing the password in the renderer.
    credential_id: Optional[str] = None

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


def _resolve_credentials(request: SystemInfoRequest):
    """Resolve effective (username, password) for a request, honoring credential_id.

    If `credential_id` is provided and the vault is unlocked, use those creds.
    Otherwise fall back to whatever was passed in plaintext.
    Raises HTTPException 401 when credential_id is set but the vault isn't ready.
    """
    if request.credential_id:
        from api.routes.security import vault
        if not vault.is_unlocked:
            raise HTTPException(status_code=401, detail="Vault locked. Unlock it or provide credentials directly.")
        cred = vault.get_credential(request.credential_id)
        if not cred:
            raise HTTPException(status_code=404, detail="Credential not found in vault.")
        return cred.get("username", ""), cred.get("password", "")
    return request.username, request.password

class ServicesRequest(BaseModel):
    target_ip: str
    username: str
    password: str

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

class ServiceManageRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    service_name: str
    action: str # "start", "stop", "restart", "pause", "set_startup"
    startup_type: str | None = None

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

class LogsRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    log_name: str = "System"
    level: str = "Error" # "Error", "Warning", "Information"
    count: int = 20

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

class DisconnectRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    session_id: str

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

class PowerRequest(BaseModel):
    target_ip: str
    username: str
    password: str
    action: str # "shutdown", "restart", "logoff"
    message: str = "Manutenção Programada"
    timeout: int = 30
    force: bool = False

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

class TestConnectionRequest(BaseModel):
    target_ip: str
    username: str
    password: str

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

def get_trusted_hosts_context(ip: str, auth_header: str):
    """Retorna o context manager apropriado baseado no header."""
    if auth_header == "true":
        return TemporaryTrustedHosts(ip)
    return contextlib.nullcontext()


def _is_trusted_hosts_error(result):
    """True if a WinRM connect/exec result represents the TrustedHosts gate.

    The handler used to set ``error`` to the literal string
    "TRUSTED_HOSTS_REQUIRED", but it now puts a friendly message in ``error``
    and the machine-readable identifier in ``code``. This helper accepts both
    shapes so we keep working with mixed callers.
    """
    if not isinstance(result, dict):
        return False
    if result.get("code") == "TRUSTED_HOSTS_REQUIRED":
        return True
    err = result.get("error")
    if isinstance(err, str) and "TRUSTED_HOSTS_REQUIRED" in err:
        return True
    return False


class DiagnoseRequest(BaseModel):
    target_ip: str

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


@router.post("/diagnose-target")
def diagnose_target(request: DiagnoseRequest):
    """Return diagnostic info about a remote target so the frontend can render
    a useful TrustedHosts modal — specifically, whether the target sits in a
    different AD domain than the local machine, which is the most common
    reason WinRM falls back to NTLM and trips the TrustedHosts gate.

    All fields are best-effort. None of them are required to render the modal,
    they just make the modal smarter when present.
    """
    target_domain = None
    network_name = None
    try:
        from api.routes.settings import load_settings
        import ipaddress
        settings = load_settings()
        ip_obj = ipaddress.ip_address(request.target_ip)
        for net in (settings.networks or []):
            if not net.enabled:
                continue
            try:
                if ip_obj in ipaddress.ip_network(net.cidr, strict=False):
                    network_name = net.name
                    if net.domain:
                        target_domain = net.domain
                    break
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logging.debug(f"diagnose_target: settings lookup failed: {e}")

    local_domain = None
    try:
        # USERDNSDOMAIN is set on domain-joined Windows machines.
        local_domain = os.environ.get("USERDNSDOMAIN") or None
    except Exception:
        pass

    cross_domain = None
    if target_domain and local_domain:
        cross_domain = target_domain.lower() != local_domain.lower()

    return {
        "target_ip": request.target_ip,
        "target_domain": target_domain,
        "local_domain": local_domain,
        "network_name": network_name,
        "cross_domain": cross_domain,
    }

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
            if _is_trusted_hosts_error(result):
                raise HTTPException(status_code=403, detail="TRUSTED_HOSTS_REQUIRED")
            raise HTTPException(status_code=500, detail=result["error"])
        # return result removed to allow update logic below
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor: {str(e)}")

    # Update host with current user and TeamViewer ID if available
    if isinstance(result, dict):
        updates_needed = False
        try:
            from api.routes.network import get_hosts_list, save_hosts_list, host_manager_instance
            
            # We need to fetch fresh list or use manager directly
            # Using manager directly is better for atomic updates but we need the object first
            current_hosts = get_hosts_list()
            target_host = next((h for h in current_hosts if h.address == request.target_ip), None)
            
            if target_host:
                if "CurrentUser" in result and result["CurrentUser"] != "N/A":
                    target_host.current_user = result["CurrentUser"]
                    updates_needed = True
                
                if "TeamViewerID" in result and result["TeamViewerID"] != "N/A" and result["TeamViewerID"] != "Unknown":
                    target_host.teamviewer_id = result["TeamViewerID"]
                    updates_needed = True
                
                if updates_needed:
                    # Persist using HostManager
                    # Re-construct dict for update
                    host_data = {
                        'ip': target_host.address,
                        'current_user': target_host.current_user,
                        'teamviewer_id': target_host.teamviewer_id
                    }
                    # We can use update_host_details or update_hosts. update_hosts expects full list or list of dicts.
                    # Let's use save_hosts_list helper which handles the conversion
                    save_hosts_list(current_hosts)
                    
        except Exception as e:
            logging.exception(f"Erro ao atualizar informações do host: {e}")

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
            if _is_trusted_hosts_error(result):
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
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.

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

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)

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
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.

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
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.
                
        except Exception as e:
            error_msg = str(e)
            if "TRUSTED_HOSTS_REQUIRED" in error_msg:
                 yield json.dumps({"error": "TRUSTED_HOSTS_REQUIRED"}).encode('utf-8') + b"\n"
            else:
                 yield json.dumps({"error": error_msg}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/host-probe")
def host_probe(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    """Lightweight opportunistic probe — runs a single PowerShell script over WinRM
    that collects MAC, Domain, CurrentUser, LastBootUpTime, SystemDiskFreeGB and
    immediately persists them on the host record. Intended to be fired in the
    background after the user authenticates against this host for any reason
    (Terminal Remoto opening, TestConnection succeeding, etc.).

    Failures are absorbed and returned in the JSON body so callers can be
    fire-and-forget. The endpoint itself never errors out for routine WinRM
    issues — only for malformed requests or missing vault credentials.
    """
    try:
        username, password = _resolve_credentials(request)
    except HTTPException as he:
        return {"status": "error", "code": "CREDENTIALS_UNAVAILABLE", "message": he.detail}

    try:
        with get_trusted_hosts_context(request.target_ip, x_temp_auth):
            result = sys_tools.get_host_probe(request.target_ip, username, password)
    except Exception as e:
        logging.exception(f"host_probe failed for {request.target_ip}: {e}")
        return {"status": "error", "code": "PROBE_FAILED", "message": str(e)}

    if not isinstance(result, dict):
        return {"status": "error", "code": "PROBE_FAILED", "message": "Resposta inválida."}
    if "error" in result:
        if _is_trusted_hosts_error(result):
            return {"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": result.get("error", "")}
        return {"status": "error", "code": "PROBE_FAILED", "message": result.get("error", "")}

    # Persist whatever fields actually came back. The probe script returns "N/A"
    # strings for fields it couldn't resolve — we treat those as "no signal" and
    # don't overwrite existing values with them.
    try:
        from src.core.database import db as _db
        updates = {}
        mac = result.get("MACAddress")
        if mac and mac != "N/A":
            updates['mac'] = mac
        dom = result.get("Domain")
        if dom and dom != "N/A":
            updates['domain'] = dom
        cu = result.get("CurrentUser")
        if cu and cu != "N/A":
            updates['current_user'] = cu
        lb = result.get("LastBootUpTime")
        if lb and lb != "N/A":
            updates['last_boot'] = lb
        df = result.get("SystemDiskFreeGB")
        if isinstance(df, (int, float)):
            updates['system_disk_free_gb'] = float(df)
        if updates:
            _db.update_host_fields(request.target_ip, updates)
    except Exception as e:
        # Persistence is best-effort. Caller still gets the data in the response.
        logging.exception(f"host_probe persistence failed for {request.target_ip}: {e}")

    return {"status": "success", "data": result}


@router.post("/pre-power-check")
def pre_power_check(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    """Pre-shutdown/restart safety check — see get_pre_power_check.ps1.

    Used by the UI to warn the operator about: recent uptime, pending reboots,
    and active interactive sessions before triggering a destructive action.
    Designed to be fast (<3s typical); failures don't block the underlying
    action since the caller treats this purely as advisory.
    """
    try:
        username, password = _resolve_credentials(request)
    except HTTPException as he:
        return {"status": "error", "code": "CREDENTIALS_UNAVAILABLE", "message": he.detail}

    try:
        with get_trusted_hosts_context(request.target_ip, x_temp_auth):
            result = sys_tools.get_pre_power_check(request.target_ip, username, password)
    except Exception as e:
        logging.exception(f"pre_power_check failed for {request.target_ip}: {e}")
        return {"status": "error", "code": "CHECK_FAILED", "message": str(e)}

    if not isinstance(result, dict):
        return {"status": "error", "code": "CHECK_FAILED", "message": "Resposta inválida."}
    if "error" in result and not any(k in result for k in ("uptime_minutes", "sessions", "pending_reboot")):
        # Full failure — script crashed before populating anything useful.
        if _is_trusted_hosts_error(result):
            return {"status": "error", "code": "TRUSTED_HOSTS_REQUIRED", "message": result.get("error", "")}
        return {"status": "error", "code": "CHECK_FAILED", "message": result.get("error", "")}

    return {"status": "success", "data": result}


@router.post("/teamviewer")
def get_teamviewer_id(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    """Obtém o TeamViewer ID do host remoto.

    Accepts either explicit credentials or `credential_id` referencing the
    unlocked vault. The RemoteAccessModal uses credential_id to silently
    auto-fetch missing IDs without ever handling the password in the renderer.
    """
    try:
        username, password = _resolve_credentials(request)
    except HTTPException as he:
        # Propagate as a single-line NDJSON so the frontend can show the right
        # message without parsing a 401/404 specially.
        def err_gen():
            yield json.dumps({"status": "error", "code": "CREDENTIALS_UNAVAILABLE", "message": he.detail}).encode('utf-8') + b"\n"
        return StreamingResponse(err_gen(), media_type="application/x-ndjson")

    def event_generator():
        try:
            with get_trusted_hosts_context(request.target_ip, x_temp_auth):
                iterator = sys_tools.get_remote_teamviewer_id(
                    request.target_ip,
                    username,
                    password
                )
                for item in iterator:
                    if isinstance(item, tuple) and len(item) == 2:
                        msg, data = item
                        yield json.dumps({"status": "success", "message": msg, "data": data}).encode('utf-8') + b"\n"
                    elif isinstance(item, dict) and "error" in item:
                            yield json.dumps(item).encode('utf-8') + b"\n"
                    else:
                        yield json.dumps({"status": "info", "message": str(item)}).encode('utf-8') + b"\n"
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.

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
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.

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
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.

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
                        # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.
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
                        # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.
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
                    # No artificial sleep — back-pressure on the WS socket
                    # is the right flow-control mechanism; the 10ms sleep was
                    # adding 2s/200 events of pure latency.
                
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
