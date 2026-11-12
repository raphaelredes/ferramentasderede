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
            error_detail = result["error"]
            if result.get("details"):
                error_detail += " • " + " • ".join(result["details"])
            raise HTTPException(status_code=500, detail=error_detail)
        # return result removed to allow update logic below
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor: {str(e)}")

    # Persist fields returned by get_system_info.ps1 directly to DB (MAC, Domain, CurrentUser,
    # LastBootUpTime, TeamViewerID, SystemDiskFreeGB) without needing a separate /host-probe call.
    if isinstance(result, dict):
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
            if cu and cu not in ("N/A", "Error"):
                updates['current_user'] = cu
            lb = result.get("LastBootUpTime")
            if lb and lb != "N/A":
                updates['last_boot'] = lb
            tv = result.get("TeamViewerID")
            if tv and tv not in ("N/A", "Unknown"):
                updates['teamviewer_id'] = str(tv)
            htd = result.get("HopToDeskID")
            if htd and htd not in ("N/A", "Unknown"):
                updates['hoptodesk_id'] = str(htd)
            elif htd == "N/A":
                updates['hoptodesk_id'] = None
            disks = result.get("Disks")
            if isinstance(disks, list):
                for d in disks:
                    if isinstance(d, dict) and str(d.get("DeviceID", "")).upper().startswith("C"):
                        free_gb = d.get("Free_GB")
                        if isinstance(free_gb, (int, float)):
                            updates['system_disk_free_gb'] = float(free_gb)
                        break
            if updates:
                _db.update_host_fields(request.target_ip, updates)
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
            error_detail = result["error"]
            if result.get("details"):
                error_detail += " • " + " • ".join(result["details"])
            raise HTTPException(status_code=500, detail=error_detail)
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
        msg = result.get("error", "")
        if result.get("details"):
            msg += " • " + " • ".join(result["details"])
        return {"status": "error", "code": "PROBE_FAILED", "message": msg}

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


class HopToDeskDeployRequest(BaseModel):
    target_ip: str
    username: Optional[str] = None
    password: Optional[str] = None
    credential_id: Optional[str] = None
    target_location: Optional[str] = "public"
    target_user: Optional[str] = None

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


class HopToDeskLaunchRequest(BaseModel):
    target_id: Optional[str] = None


@router.post("/hoptodesk/deploy")
def deploy_hoptodesk(request: HopToDeskDeployRequest, x_temp_auth: str = Header(default=None)):
    """Baixa o HopToDesk localmente (se necessário), implanta no host remoto e obtém o ID."""
    try:
        username, password = _resolve_credentials(request)
    except HTTPException as he:
        def err_gen():
            yield json.dumps({"status": "error", "code": "CREDENTIALS_UNAVAILABLE", "message": he.detail}).encode('utf-8') + b"\n"
        return StreamingResponse(err_gen(), media_type="application/x-ndjson")

    def event_generator():
        from src.system.core.hoptodesk_manager import HopToDeskManager
        from src.system.core.winrm_handler import WinRMHandler
        from src.core.database import db as _db

        handler = None
        try:
            handler = WinRMHandler(request.target_ip, username, password)
            conn_res = handler.connect()
            if "error" in conn_res:
                yield json.dumps({"status": "error", "message": conn_res["error"], "code": conn_res.get("code")}).encode('utf-8') + b"\n"
                return

            for evt in HopToDeskManager.deploy_and_get_id(
                handler,
                request.target_ip,
                username,
                password,
                target_location=request.target_location or "public",
                target_user=request.target_user
            ):
                if evt.get("status") == "success" and evt.get("data"):
                    _db.update_host_fields(request.target_ip, {'hoptodesk_id': str(evt['data'])})
                yield json.dumps(evt).encode('utf-8') + b"\n"

        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}).encode('utf-8') + b"\n"
        finally:
            if handler:
                handler.close()

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/hoptodesk/launch")
def launch_hoptodesk(request: HopToDeskLaunchRequest):
    """Inicia o HopToDesk localmente conectando ao ID especificado."""
    from src.system.core.hoptodesk_manager import HopToDeskManager
    success = HopToDeskManager.launch_local(request.target_id)
    if success:
        return {"status": "success", "message": f"HopToDesk iniciado para {request.target_id}"}
    return {"status": "error", "message": "Não foi possível iniciar o HopToDesk localmente."}

@router.post("/user-profiles")
def get_user_profiles_route(request: SystemInfoRequest, x_temp_auth: str = Header(default=None)):
    r"""Lista todas as pastas de usuários de C:\Users no host remoto (filtrando public/default)."""
    try:
        user, pwd = _resolve_credentials(request)
    except HTTPException as he:
        return {"status": "error", "message": he.detail, "profiles": []}

    from src.system.core.winrm_handler import WinRMHandler
    handler = None
    try:
        handler = WinRMHandler(request.target_ip, user, pwd)
        conn = handler.connect()
        if "error" in conn:
            return {"status": "error", "message": conn["error"], "profiles": []}

        ps_script = r'''
        $baseDir = "$env:SystemDrive\Users"
        if (-not (Test-Path $baseDir)) {
            $regBase = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' -ErrorAction SilentlyContinue).ProfilesDirectory
            if ($regBase) { $baseDir = [System.Environment]::ExpandEnvironmentVariables($regBase) }
        }

        $list = [System.Collections.Generic.List[PSCustomObject]]::new()
        $seen = @{}

        if (Test-Path $baseDir) {
            $dirs = Get-ChildItem -Path $baseDir -Directory -Force -ErrorAction SilentlyContinue
            foreach ($d in $dirs) {
                $n = $d.Name
                $lower = $n.ToLower()
                if ($lower -eq 'public' -or $lower -eq 'público' -or $lower -eq 'publico' -or $lower -eq 'all users') { continue }
                if ($lower -eq 'default' -or $lower.StartsWith('default')) { continue }
                if ($lower -eq 'systemprofile' -or $lower -eq 'localservice' -or $lower -eq 'networkservice') { continue }

                # Garantir rigorosamente que a pasta esteja DENTRO exclusivamente de C:\Users
                $parentPath = (Split-Path -Parent $d.FullName).TrimEnd('\')
                if ($parentPath.ToLower() -ne $baseDir.TrimEnd('\').ToLower()) { continue }

                if (-not $seen.ContainsKey($lower)) {
                    $seen[$lower] = $true
                    $list.Add([PSCustomObject]@{ Username = $n; Path = $d.FullName; DesktopPath = Join-Path $d.FullName "Desktop" })
                }
            }
        }

        @($list | Sort-Object Username) | ConvertTo-Json -Compress
        '''
        res = handler.execute_script(ps_script)
        out = "\n".join(res.get("output", [])).strip()
        profiles = []
        if out:
            try:
                parsed = json.loads(out)
                if isinstance(parsed, dict):
                    profiles = [parsed]
                elif isinstance(parsed, list):
                    profiles = parsed
            except Exception:
                profiles = []
        return {"status": "success", "profiles": profiles}
    except Exception as e:
        return {"status": "error", "message": str(e), "profiles": []}
    finally:
        if handler:
            handler.close()

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


class EnableRemoteWinRMRequest(BaseModel):
    target_ip: str
    username: str = ""
    password: str = ""
    credential_id: Optional[str] = None

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


@router.post("/winrm/enable-remote")
def enable_remote_winrm_route(request: EnableRemoteWinRMRequest):
    """Tenta habilitar o serviço WinRM remotamente no host alvo usando credenciais administrativas."""
    try:
        user = request.username
        pwd = request.password
        if request.credential_id:
            from api.routes.security import vault
            if vault.is_unlocked:
                cred = vault.get_credential(request.credential_id)
                if cred:
                    user = cred.get("username", user)
                    pwd = cred.get("password", pwd)

        if not user or not pwd:
            return {"status": "error", "message": "Credenciais administrativas não fornecidas."}

        from src.system.core.local_commands import LocalCommands
        cmd = LocalCommands(request.target_ip)
        success, message = cmd.enable_remote_winrm(user, pwd)
        if success:
            return {"status": "success", "message": message}
        return {"status": "error", "message": message}
    except Exception as e:
        return {"status": "error", "message": str(e)}



class HopToDeskRemoveRequest(BaseModel):
    target_ip: str
    username: Optional[str] = None
    password: Optional[str] = None
    credential_id: Optional[str] = None

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


@router.post("/hoptodesk/remove")
def remove_hoptodesk_route(request: HopToDeskRemoveRequest):
    """Remove o executavel do HopToDesk e para/desinstala o servico no host remoto."""
    try:
        user, pwd = _resolve_credentials(request)
    except HTTPException as he:
        return {"status": "error", "message": he.detail}

    from src.system.core.winrm_handler import WinRMHandler
    handler = WinRMHandler(request.target_ip, user, pwd)
    conn = handler.connect()
    if "error" in conn:
        return {"status": "error", "message": conn["error"]}

    ps_script = r'''
    Stop-Service -Name "HopToDesk" -Force -ErrorAction SilentlyContinue
    cmd.exe /c "sc.exe delete HopToDesk" 2>$null | Out-Null
    Stop-Process -Name "*hoptodesk*" -Force -ErrorAction SilentlyContinue
    $paths = @(
        "C:\Users\Public\Desktop\HopToDesk.exe",
        "$env:ProgramFiles\HopToDesk\HopToDesk.exe",
        "${env:ProgramFiles(x86)}\HopToDesk\HopToDesk.exe",
        "C:\ProgramData\HopToDesk\HopToDesk.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { Remove-Item -Path $p -Force -ErrorAction SilentlyContinue }
    }
    try {
        $uDirs = Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue
        foreach ($u in $uDirs) {
            $chk = Join-Path $u.FullName "Desktop\HopToDesk.exe"
            if (Test-Path $chk) { Remove-Item -Path $chk -Force -ErrorAction SilentlyContinue }
        }
    } catch {}
    Write-Output "REMOVED"
    '''
    res = handler.execute_script(ps_script)
    _db.update_host_fields(request.target_ip, {"hoptodesk_id": None})
    return {"status": "success", "message": "HopToDesk removido com sucesso do host remoto."}


class RemoteAppActionRequest(BaseModel):
    target_ip: str
    username: Optional[str] = None
    password: Optional[str] = None
    credential_id: Optional[str] = None
    app_name: str

    @field_validator("target_ip")
    @classmethod
    def _target_ip_must_be_safe(cls, v: str) -> str:
        return _validate_target_ip(v)


@router.post("/remote-app/start")
def start_remote_app(request: RemoteAppActionRequest, x_temp_auth: str = Header(default=None)):
    """Inicia o aplicativo especificado (hoptodesk ou teamviewer) no host remoto."""
    try:
        username, password = _resolve_credentials(request)
    except HTTPException as he:
        return {"status": "error", "message": he.detail}

    from src.system.core.winrm_handler import WinRMHandler
    handler = None
    try:
        handler = WinRMHandler(request.target_ip, username, password)
        conn = handler.connect()
        if "error" in conn:
            return {"status": "error", "message": conn["error"]}

        app = request.app_name.lower().strip()
        if app == "hoptodesk":
            ps_script = r'''
            # 1. Verificar se o processo ja esta em execucao
            $proc = Get-Process -Name "*hoptodesk*" -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Output "ALREADY_RUNNING"
                exit
            }

            # 2. Localizar o executavel portátil copiado
            $candidate = $null
            if (Test-Path 'C:\Users\Public\Desktop\HopToDesk.exe') {
                $candidate = 'C:\Users\Public\Desktop\HopToDesk.exe'
            }
            if (-not $candidate) {
                try {
                    $uDirs = Get-ChildItem "C:\Users" -Directory -Force -ErrorAction SilentlyContinue
                    foreach ($u in $uDirs) {
                        foreach ($sub in @("Desktop\HopToDesk.exe", "Downloads\HopToDesk.exe", "AppData\Local\HopToDesk\HopToDesk.exe")) {
                            $chk = Join-Path $u.FullName $sub
                            if (Test-Path $chk) { $candidate = $chk; break }
                        }
                        if ($candidate) { break }
                    }
                } catch {}
            }
            if (-not $candidate) {
                foreach ($sp in @("$env:ProgramFiles\HopToDesk\HopToDesk.exe", "${env:ProgramFiles(x86)}\HopToDesk\HopToDesk.exe", "C:\ProgramData\HopToDesk\HopToDesk.exe")) {
                    if ($sp -and (Test-Path $sp)) { $candidate = $sp; break }
                }
            }
            if (-not $candidate) {
                Write-Output "NOT_INSTALLED"
                exit
            }

            # 3. Detectar usuarios interativos ativos (console / sessoes graficas abertas)
            $usersToLaunch = [System.Collections.Generic.List[string]]::new()
            try {
                $cs = (Get-CimInstance Win32_ComputerSystem).UserName
                if ($cs -and (-not $usersToLaunch.Contains($cs))) { $usersToLaunch.Add($cs) }
            } catch {}

            try {
                $explorers = Get-CimInstance Win32_Process -Filter "Name = 'explorer.exe'" -ErrorAction SilentlyContinue
                foreach ($exp in $explorers) {
                    $o = Invoke-CimMethod -InputObject $exp -MethodName GetOwner -ErrorAction SilentlyContinue
                    if ($o -and $o.Domain -and $o.User) {
                        $fullU = "$($o.Domain)\$($o.User)"
                        if (-not $usersToLaunch.Contains($fullU)) { $usersToLaunch.Add($fullU) }
                    }
                }
            } catch {}

            # 4. Iniciar diretamente no desktop interativo do usuario via schtasks.exe (imune a restrições DCOM do WinRM)
            $taskName = "HopToDesk_Start_" + (Get-Random)
            $taskCreated = $false

            foreach ($uName in $usersToLaunch) {
                if (-not $uName) { continue }
                $createCmd = "schtasks /create /tn `"$taskName`" /tr `"\`"$candidate\`"`" /sc ONCE /st 23:59 /it /ru `"$uName`" /rl HIGHEST /f"
                $null = cmd.exe /c $createCmd 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $taskCreated = $true
                    break
                }
            }

            if (-not $taskCreated) {
                $createCmd = "schtasks /create /tn `"$taskName`" /tr `"\`"$candidate\`"`" /sc ONCE /st 23:59 /it /rl HIGHEST /f"
                $null = cmd.exe /c $createCmd 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $taskCreated = $true
                }
            }

            if ($taskCreated) {
                $null = cmd.exe /c "schtasks /run /tn `"$taskName`"" 2>&1
                Start-Sleep -Seconds 2
                $null = cmd.exe /c "schtasks /delete /tn `"$taskName`" /f" 2>&1
            } else {
                Start-Process -FilePath $candidate -WindowStyle Normal -ErrorAction SilentlyContinue
            }

            # 5. Confirmar se o processo esta ativo (aguarda ate 5 segundos)
            $isRunning = $false
            for ($chk = 0; $chk -lt 5; $chk++) {
                $p = Get-Process -Name "*hoptodesk*" -ErrorAction SilentlyContinue
                if ($p) { $isRunning = $true; break }
                Start-Sleep -Seconds 1
            }

            if ($isRunning) { Write-Output "STARTED" } else { Write-Output "FAILED" }
            '''
        elif app == "teamviewer":
            ps_script = r'''
            $svc = Get-Service -Name "TeamViewer" -ErrorAction SilentlyContinue
            if ($svc) {
                if ($svc.Status -ne "Running") {
                    Start-Service -Name "TeamViewer" -ErrorAction SilentlyContinue
                    Start-Sleep -Seconds 1
                }
                $svc = Get-Service -Name "TeamViewer" -ErrorAction SilentlyContinue
                if ($svc.Status -eq "Running") {
                    Write-Output "STARTED"
                    exit
                }
            }
            $proc = Get-Process -Name "*teamviewer*" -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Output "ALREADY_RUNNING"
                exit
            }
            $candidate = $null
            foreach ($p in @("$env:ProgramFiles\TeamViewer\TeamViewer.exe", "${env:ProgramFiles(x86)}\TeamViewer\TeamViewer.exe")) {
                if (Test-Path $p) { $candidate = $p; break }
            }
            if ($candidate) {
                Start-Process -FilePath $candidate -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 1
                if (Get-Process -Name "*teamviewer*" -ErrorAction SilentlyContinue) {
                    Write-Output "STARTED"
                } else {
                    Write-Output "FAILED"
                }
            } else {
                Write-Output "NOT_INSTALLED"
            }
            '''
        else:
            return {"status": "error", "message": f"Aplicativo desconhecido: {app}"}

        res = handler.execute_script(ps_script)
        out = "".join(res.get("output", [])).strip()
        if "STARTED" in out or "ALREADY_RUNNING" in out:
            return {"status": "success", "running": True, "message": f"{app.capitalize()} em execução no host!"}
        elif "NOT_INSTALLED" in out:
            return {"status": "not_installed", "running": False, "message": f"{app.capitalize()} não está instalado no host remoto."}
        else:
            return {"status": "error", "running": False, "message": f"Não foi possível iniciar {app.capitalize()} no host."}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if handler:
            handler.close()


class ConnectivityDiagRequest(BaseModel):
    targets: list[str] | str
    username: Optional[str] = ""
    password: Optional[str] = ""
    credential_id: Optional[str] = None


@router.post("/connectivity-diag")
def connectivity_diag_route(request: ConnectivityDiagRequest):
    """Stream em tempo real (NDJSON) de Auditoria Multi-Host de Wi-Fi, Enlaces LAN e 802.1x."""
    from src.system.core.wifi_diag_manager import parse_targets, stream_connectivity_diagnostic

    parsed_targets = parse_targets(request.targets)
    if not parsed_targets:
        raise HTTPException(
            status_code=400,
            detail="Informe ao menos um Hostname ou Endereço IPv4 válido (ex: 1.1.1.1, host.example.com).",
        )

    eff_user = (request.username or "").strip()
    eff_pass = request.password or ""

    if not eff_user or not eff_pass:
        from api.routes.security import vault
        if request.credential_id and request.credential_id != "auto":
            if not vault.is_unlocked:
                raise HTTPException(
                    status_code=401,
                    detail="Cofre de Credenciais bloqueado. Desbloqueie o cofre na aba Segurança ou informe usuário e senha manualmente.",
                )
            cred = vault.get_credential(request.credential_id)
            if not cred:
                raise HTTPException(status_code=404, detail="Credencial selecionada não encontrada no Cofre.")
            eff_user = cred.get("username", "")
            eff_pass = cred.get("password", "")
        elif vault.is_unlocked:
            all_creds = vault.get_all_credentials()
            if all_creds:
                eff_user = all_creds[0].get("username", "")
                eff_pass = all_creds[0].get("password", "")

        if not eff_user or not eff_pass:
            raise HTTPException(
                status_code=400,
                detail="Credenciais administrativas são obrigatórias para auditar interfaces e Wi-Fi via WinRM. Desbloqueie o Cofre de Credenciais ou informe usuário/senha manualmente.",
            )

    return StreamingResponse(
        stream_connectivity_diagnostic(
            targets=parsed_targets,
            username=eff_user,
            password=eff_pass,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )

