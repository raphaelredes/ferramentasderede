from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
import json
import asyncio
import logging
import time
import sys
import os
import threading
import base64
import subprocess
from typing import List, Optional

# Adicionar diretório pai ao path para importar módulos do src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.network.tools import NetworkTools
from src.network.monitor import HostMonitor
from src.system.core.winrm_handler import WinRMHandler

net_tools = NetworkTools()
host_monitor = HostMonitor()

# --- WebSocket Manager ---
def _ws_origin_allowed(websocket: WebSocket) -> bool:
    """Reject WebSocket connections whose Origin isn't in the same allow-list
    used for CORS. Browser CORS does NOT cover WebSockets, so without this
    guard any page in the user's default browser could open ws://127.0.0.1
    and receive the live host inventory.

    A missing Origin header (e.g. a non-browser ws client) is also rejected —
    legitimate Electron renderers always send one."""
    try:
        from api.server import ALLOWED_ORIGINS
    except Exception:
        # Fallback if the server module isn't importable here for some reason.
        ALLOWED_ORIGINS = []  # type: ignore[assignment]
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    return origin in ALLOWED_ORIGINS


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> bool:
        if not _ws_origin_allowed(websocket):
            logging.warning(
                f"WS connect rejected: origin={websocket.headers.get('origin')!r} not in allow-list"
            )
            try:
                await websocket.close(code=1008)  # 1008 = Policy Violation
            except Exception:
                pass
            return False
        await websocket.accept()
        self.active_connections.append(websocket)
        return True

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            # Double-disconnect — current code paths don't trigger it, but if
            # a future path adds one we want a breadcrumb instead of silence.
            logging.debug("ConnectionManager.disconnect: websocket already removed")

    async def broadcast(self, message: dict):
        # Snapshot before iterating: a disconnect() during broadcast mutates
        # self.active_connections (list.remove) and can skip an element on the
        # next index advance. Cheap to copy — connection list is small (1-2 in
        # practice).
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                # Client disconnected mid-broadcast — log and move on. Bare
                # except would also catch KeyboardInterrupt which we don't want.
                logging.debug(f"WebSocket broadcast skipped (peer dropped): {e}")

manager = ConnectionManager()

router = APIRouter(tags=["network"])

# --- Models ---
class Host(BaseModel):
    name: Optional[str] = None
    address: str
    mac: Optional[str] = None
    vendor: Optional[str] = None
    type: Optional[str] = "generic"
    hostname: Optional[str] = None
    domain: Optional[str] = None
    ip: Optional[str] = None
    last_status: Optional[bool] = None
    last_checked: Optional[str | float] = None
    group: Optional[str] = None
    monitoring: bool = True
    teamviewer_id: Optional[str | int | float] = None
    ports: Optional[List[int]] = []
    current_user: Optional[str] = None
    # Opportunistic host-probe fields (Sprint 4: data collected for free when
    # the operator authenticates against this host for any reason)
    last_boot: Optional[str] = None
    system_disk_free_gb: Optional[float] = None
    # Inferred from settings.networks at read time — not persisted.
    network_id: Optional[str] = None
    network_name: Optional[str] = None

    # NOTE: this used to live in a `model_validate` classmethod override, but
    # Pydantic v2 routes the constructor through `__pydantic_validator__`,
    # which bypasses subclass overrides. The normalization was running only
    # when callers explicitly invoked `Host.model_validate(...)`, never on the
    # `Host(**dict)` and FastAPI request-body paths. Field validators run on
    # both, which is what we want.

    @field_validator("teamviewer_id", mode="before")
    @classmethod
    def _normalize_teamviewer_id(cls, v):
        # The DB stores `teamviewer_id` as a string, but old rows occasionally
        # come back as float (legacy import). Coerce to string and strip the
        # trailing ".0" that float-formatted IDs pick up.
        if v is None:
            return v
        return str(v).replace(".0", "")

    @field_validator("last_checked", mode="before")
    @classmethod
    def _normalize_last_checked(cls, v):
        # Some legacy rows store last_checked as a float epoch; convert to ISO
        # for the renderer. Bad floats fall back to str() rather than 500.
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, (int, float)):
            try:
                from datetime import datetime
                return datetime.fromtimestamp(v).isoformat()
            except (ValueError, OSError, OverflowError):
                return str(v)
        return v

# ... (omitted lines)

def _resolve_fqdn_for_host(ip_address: str):
    """Resolve hostname/domain for an IP, preferring the DNS server of the
    host's configured network when available.

    Order of attempts:
      1. PTR via the network's dns_server (multi-domain correctness)
      2. ping -a (Windows fallback, picks up NetBIOS/local resolver)
      3. socket.gethostbyaddr (system resolver)

    Returns (hostname, domain) or (None, None).
    """
    from src.network import dns_resolver
    configured = _load_configured_networks()
    net_id, _ = _match_network(ip_address, configured)
    dns_server = None
    if net_id:
        try:
            from api.routes.settings import load_settings
            settings = load_settings()
            for net in (settings.networks or []):
                if net.id == net_id:
                    dns_server = net.dns_server
                    break
        except Exception:
            pass

    # 1. Try the network's DNS first
    if dns_server:
        fqdn = dns_resolver.resolve_ip(ip_address, dns_server=dns_server)
        if fqdn:
            return dns_resolver.split_fqdn(fqdn)

    # 2. Windows ping -a fallback
    try:
        fqdn = net_tools.resolve_via_ping_a(ip_address)
        if fqdn and fqdn not in ("N/A", "Inválido", "Erro"):
            return dns_resolver.split_fqdn(fqdn)
    except Exception:
        pass

    # 3. System resolver fallback
    fqdn = dns_resolver.resolve_ip(ip_address)
    if fqdn:
        return dns_resolver.split_fqdn(fqdn)

    # 4. Last resort: legacy resolver in tools.py
    try:
        fqdn = net_tools.resolve_ip_and_hostname(ip_address)
        if fqdn and fqdn not in ("N/A", "Inválido", "Erro"):
            return dns_resolver.split_fqdn(fqdn)
    except Exception:
        pass

    return None, None


@router.post("/hosts/{address}/refresh")
def refresh_host(address: str):
    try:
        current_hosts = get_hosts_list()
        target_host = next((h for h in current_hosts if h.address == address), None)

        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")

        hostname, domain = _resolve_fqdn_for_host(address)
        if hostname:
            target_host.hostname = hostname
            target_host.domain = domain

        if address and address != "N/A":
            target_host.ip = address

        host_manager_instance.update_host_details(address, hostname=hostname, domain=domain)

        return {"status": "success", "message": "Informações atualizadas.", "host": target_host}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar host: {str(e)}")

class HostUpdate(BaseModel):
    name: Optional[str] = None
    group: Optional[str] = None
    mac: Optional[str] = None
    monitoring: Optional[bool] = None
    reset_stats: Optional[bool] = False
    teamviewer_id: Optional[str] = None
    ports: Optional[List[int]] = None
    # Opportunistic probe results (host-probe). All optional; senders should
    # only include keys they actually want to update.
    domain: Optional[str] = None
    current_user: Optional[str] = None
    last_boot: Optional[str] = None
    system_disk_free_gb: Optional[float] = None

# ... (omitted lines)

@router.patch("/hosts/{address}")
def update_host(address: str, update: HostUpdate):
    try:
        current_hosts = get_hosts_list()
        target_host = next((h for h in current_hosts if h.address == address), None)

        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")

        # Fast path: opportunistic probe fields and other simple column updates
        # go through update_host_fields directly. This avoids the full
        # save_hosts_list round-trip (which under the hood was issuing a heavy
        # rewrite). It also doesn't churn the monitor's host list since none of
        # these fields are monitored by it.
        from src.core.database import db as _db
        probe_field_updates = {}
        if update.mac is not None: probe_field_updates['mac'] = update.mac
        if update.domain is not None: probe_field_updates['domain'] = update.domain
        if update.current_user is not None: probe_field_updates['current_user'] = update.current_user
        if update.last_boot is not None: probe_field_updates['last_boot'] = update.last_boot
        if update.system_disk_free_gb is not None: probe_field_updates['system_disk_free_gb'] = update.system_disk_free_gb
        if update.teamviewer_id is not None: probe_field_updates['teamviewer_id'] = update.teamviewer_id
        if probe_field_updates:
            _db.update_host_fields(address, probe_field_updates)

        # Display-only / structural updates still go through the slower path so
        # the nickname-vs-hostname routing in save_hosts_list applies and the
        # monitor picks up changes (e.g. ports list).
        slow_path_needed = (
            update.name is not None
            or update.group is not None
            or update.monitoring is not None
            or update.ports is not None
        )
        if slow_path_needed:
            if update.name is not None: target_host.name = update.name
            if update.group is not None: target_host.group = update.group
            if update.monitoring is not None: target_host.monitoring = update.monitoring
            if update.ports is not None: target_host.ports = update.ports
            save_hosts_list(current_hosts)
            host_monitor.update_hosts([h.model_dump() for h in current_hosts])

        if update.reset_stats:
            host_monitor.reset_host_stats(target_host.address)

        return {"status": "success", "message": "Host atualizado com sucesso.", "host": target_host}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao atualizar host: {str(e)}")

class ToolRequest(BaseModel):
    target: str
    task_id: Optional[str] = None
    source_ip: Optional[str] = None  # NIC source for ping/traceroute (multi-VLAN)

class DiscoveryRequest(BaseModel):
    cidr: str
    task_id: Optional[str] = None
    timeout: Optional[int] = 200
    max_workers: Optional[int] = 50
    source_ip: Optional[str] = None  # NIC source for the discovery scan

class StopRequest(BaseModel):
    task_id: str

class WolRequest(BaseModel):
    mac_address: str

# --- Hosts Management ---
from src.core.host_manager import HostManager

# Singleton instance of HostManager
host_manager_instance = HostManager()


def _load_configured_networks():
    """Load `networks` from settings, parsed and ready for IP→network matching.

    Returns a list of (id, name, ip_network) tuples. Bad CIDRs are skipped.
    Loaded fresh on each call so changes in Settings take effect immediately
    without restarting the API.
    """
    import ipaddress
    try:
        from api.routes.settings import load_settings
        settings = load_settings()
    except Exception:
        return []

    parsed = []
    for net in (settings.networks or []):
        if not net.enabled:
            continue
        try:
            parsed.append((net.id, net.name, ipaddress.ip_network(net.cidr, strict=False)))
        except (ValueError, TypeError):
            continue
    return parsed


def _match_network(ip_str: str, configured):
    """Return (network_id, network_name) for an IP, or (None, None)."""
    if not ip_str or not configured:
        return None, None
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except (ValueError, TypeError):
        return None, None
    for net_id, net_name, net in configured:
        try:
            if ip_obj in net:
                return net_id, net_name
        except (TypeError, ValueError):
            continue
    return None, None


def get_hosts_list():
    """Helper to get hosts as Host objects using HostManager.

    Naming model:
      * `nickname` (DB column `description`)  – operator-chosen label, sticky.
      * `name`/`hostname`                     – DNS-resolved hostname, updated
                                                automatically by the monitor.
    UI's `host.name` is what shows up big on the card; we prefer the nickname
    when set, otherwise fall back to the resolved hostname. `host.hostname`
    keeps the raw DNS hostname so views that want to show "real name" (e.g.,
    HostDetails / RDP launcher) still have it.

    Each host also gets `network_id` / `network_name` inferred from its IP
    against the user-configured networks (Settings → Redes / VLANs).
    """
    raw_hosts = host_manager_instance.get_all_hosts()
    configured = _load_configured_networks()
    hosts = []
    for item in raw_hosts:
        ip = item.get("ip")
        net_id, net_name = _match_network(ip, configured)
        resolved_hostname = item.get("name")          # DNS-resolved
        nickname = item.get("nickname")               # operator label (DB description)
        display_name = nickname or resolved_hostname  # what UI shows as title
        hosts.append(Host(
            name=display_name or "Unknown",
            address=ip,
            type=item.get("type", "generic"),
            mac=item.get("mac"),
            vendor=item.get("vendor"),
            hostname=resolved_hostname,
            domain=item.get("domain"),
            ip=ip,
            last_status=item.get("last_status"),
            last_checked=item.get("last_checked"),
            group=item.get("group"),
            monitoring=item.get("monitoring", True),
            teamviewer_id=item.get("teamviewer_id"),
            ports=item.get("ports", []),
            current_user=item.get("current_user"),
            last_boot=item.get("last_boot"),
            system_disk_free_gb=item.get("system_disk_free_gb"),
            network_id=net_id,
            network_name=net_name,
        ))
    return hosts

def save_hosts_list(hosts_list):
    """Helper to save hosts using HostManager.

    Maps Pydantic `Host` (UI shape) back to the HostManager dict shape:
      * `h.hostname` (DNS-resolved) → manager['name']      → DB `hostname`.
      * `h.name`     (display)      → manager['nickname']  → DB `description`,
        BUT only if it actually differs from the resolved hostname — otherwise
        we'd persist the resolver's output as a "user nickname" and freeze it
        in place after the first save.
    """
    updated_list = []
    for h in hosts_list:
        resolved = h.hostname
        display = h.name
        nickname = display if (display and display != resolved and display != 'Unknown') else None
        updated_list.append({
            'name': resolved,
            'ip': h.address,
            'mac': h.mac,
            'nickname': nickname,
            'group': h.group,
            'domain': h.domain,
            'tags': [],
            'ports': h.ports,
            'monitoring': h.monitoring,
            'vendor': h.vendor,
            'type': h.type,
            'teamviewer_id': h.teamviewer_id,
            'last_checked': h.last_checked,
            'last_status': h.last_status
        })
    host_manager_instance.update_hosts(updated_list)

@router.get("/hosts", response_model=List[Host])
def get_hosts():
    return get_hosts_list()

@router.post("/hosts")
def add_host(host: Host):
    try:
        # `host.name` here is the user-typed nickname (label in UI is "Apelido").
        # Store it in `nickname` (DB column `description`). Leave `name` (which
        # maps to DB `hostname`) empty so the reverse-DNS resolver can fill it
        # in later without overwriting the nickname the operator chose.
        new_host_data = {
            'name': None,
            'ip': host.address,
            'mac': host.mac,
            'nickname': host.name or None,
            'group': host.group,
            'ports': host.ports,
            'monitoring': host.monitoring,
            'vendor': host.vendor,
            'type': host.type,
            'teamviewer_id': host.teamviewer_id
        }
        success, message = host_manager_instance.add_host(new_host_data)
        
        if not success:
             raise HTTPException(status_code=400, detail=message)
        
        # Update monitor
        current_hosts = get_hosts_list()
        host_monitor.update_hosts([h.model_dump() for h in current_hosts])
            
        return {"status": "success", "message": f"Host {host.name} adicionado."}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao salvar host: {str(e)}")

@router.delete("/hosts/{address}")
def delete_host(address: str):
    try:
        # Use HostManager directly
        host_manager_instance.remove_hosts([{'ip': address}])

        # Update monitor
        current_hosts = get_hosts_list()
        host_monitor.update_hosts([h.model_dump() for h in current_hosts])

        return {"status": "success", "message": "Host removido com sucesso."}
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao remover host: {str(e)}")

# --- Network Tools ---
@router.get("/network/monitor")
def get_monitor_stats():
    return host_monitor.get_stats()

@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    if not await manager.connect(websocket):
        return  # Origin rejected; close was already sent.
    try:
        while True:
            # Keep connection alive and handle incoming messages if needed
            # For now, we just push updates, but we need to await receive to keep socket open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@router.get("/network/local")
def get_local_network():
    return net_tools.get_local_network_info()

@router.get("/network/interfaces")
def get_network_interfaces():
    """List local IPv4 interfaces (NICs). Used to auto-populate the
    `networks` list in Settings when the analyst is on a multi-VLAN /
    multi-domain machine."""
    from src.network.interfaces import list_local_interfaces
    return list_local_interfaces()


class DnsResolveRequest(BaseModel):
    name: Optional[str] = None       # hostname or FQDN to forward-resolve
    ip: Optional[str] = None         # IP for reverse PTR
    dns_server: Optional[str] = None
    domain: Optional[str] = None


@router.post("/network/dns/resolve")
def resolve_via_specific_dns(req: DnsResolveRequest):
    """Forward or reverse DNS lookup against a chosen DNS server.

    Useful when the same hostname exists in multiple AD domains and the
    system resolver picks the wrong one.

    `dns_server` must be a plain IP address. Accepting hostnames here is
    pointless (we'd need DNS to look up DNS) and lets a malicious local
    process steer the resolver at an attacker-controlled server to exfiltrate
    which internal hostnames the operator is investigating.
    """
    import ipaddress
    if req.dns_server:
        try:
            ipaddress.ip_address(req.dns_server)
        except ValueError:
            raise HTTPException(status_code=400, detail="dns_server deve ser um endereço IP.")

    from src.network import dns_resolver
    if req.name:
        ip = dns_resolver.resolve_hostname(req.name, req.dns_server, req.domain)
        return {"name": req.name, "ip": ip, "dns_server": req.dns_server, "domain": req.domain}
    if req.ip:
        fqdn = dns_resolver.resolve_ip(req.ip, req.dns_server)
        return {"ip": req.ip, "fqdn": fqdn, "dns_server": req.dns_server}
    raise HTTPException(status_code=400, detail="Informe `name` ou `ip`.")

@router.post("/network/discovery")
def discover_network(request: DiscoveryRequest):
    cidr = request.cidr
    task_id = request.task_id or f"scanner_{time.time()}"
    timeout = request.timeout or 200
    max_workers = request.max_workers or 50
    source_ip = request.source_ip

    # Cap CIDR size BEFORE spinning up worker threads. A misclick on
    # 10.0.0.0/8 used to spawn 16M scan tasks, fill the threadpool for
    # hours, and pollute the DB with junk hosts. /16 = 64K addresses is
    # already a long scan; anything wider should be an explicit batch.
    _MAX_DISCOVERY_ADDRESSES = 65536  # /16

    def event_generator():
        try:
            import ipaddress
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                yield json.dumps({"error": "CIDR inválido."}).encode('utf-8') + b"\n"
                return

            if network.num_addresses > _MAX_DISCOVERY_ADDRESSES:
                yield json.dumps({
                    "error": (
                        f"CIDR muito amplo ({network.num_addresses} endereços). "
                        f"Limite máximo: {_MAX_DISCOVERY_ADDRESSES} (/16). "
                        "Divida em sub-redes menores."
                    )
                }).encode('utf-8') + b"\n"
                return

            iterator = net_tools.discover_hosts(
                network, task_id,
                timeout=timeout, max_workers=max_workers,
                source_ip=source_ip,
            )
            for host in iterator:
                yield json.dumps(host).encode('utf-8') + b"\n"
                time.sleep(0.01)
        except Exception as e:
            yield json.dumps({"error": str(e)}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/tools/ping")
def run_ping(request: ToolRequest):
    target = request.target
    task_id = request.task_id or f"ping_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            iterator = net_tools.continuous_ping(target, task_id, source_ip=source_ip)
            for item in iterator:
                line = item[0] if isinstance(item, tuple) else str(item)
                if line:
                    yield line.encode('utf-8')
                    time.sleep(0.01)
        except Exception as e:
            yield f"Erro ao executar ping: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")

@router.post("/tools/traceroute")
def run_traceroute(request: ToolRequest):
    target = request.target
    task_id = request.task_id or f"traceroute_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            iterator = net_tools.traceroute(target, task_id, source_ip=source_ip)
            for item in iterator:
                line = item[0] if isinstance(item, tuple) else str(item)
                if line:
                    yield line.encode('utf-8')
                    time.sleep(0.01)
        except Exception as e:
            yield f"Erro ao executar traceroute: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")

@router.post("/tools/stop")
def stop_tool(request: StopRequest):
    net_tools.stop_command(request.task_id)
    return {"status": "success", "message": "Ferramenta parada."}

@router.post("/network/wol")
def wake_on_lan(request: WolRequest):
    success, message = net_tools.send_wol_packet(request.mac_address)
    if success: return {"status": "success", "message": message}
    else: raise HTTPException(status_code=400, detail=message)

class ExternalTerminalRequest(BaseModel):
    ip: str
    username: str
    password: str


# Static PowerShell launcher script.
# IP / username / password come in via env vars so they are never interpolated
# into the script text — eliminates shell-injection and keeps the password out
# of the process command line and PowerShell history.
_EXTERNAL_TERMINAL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$ip   = $env:NT_REMOTE_IP
$user = $env:NT_REMOTE_USER
$pass = $env:NT_REMOTE_PASS
# Wipe env vars from this child process so they do not leak via Get-ChildItem env:
Remove-Item Env:\NT_REMOTE_IP, Env:\NT_REMOTE_USER, Env:\NT_REMOTE_PASS -ErrorAction SilentlyContinue

if (-not $ip -or -not $user -or -not $pass) {
    Write-Error 'Credenciais ausentes.'
    exit 1
}

$sec  = ConvertTo-SecureString $pass -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential($user, $sec)
Remove-Variable pass

try {
    $trusted = (Get-Item WSMan:\localhost\Client\TrustedHosts).Value
    if ($trusted -ne '*' -and $trusted -notlike "*$ip*") {
        Write-Host "Configurando TrustedHosts para $ip..." -ForegroundColor Yellow
        try {
            $newTrusted = if ($trusted) { "$trusted, $ip" } else { $ip }
            Set-Item WSMan:\localhost\Client\TrustedHosts -Value $newTrusted -Force -ErrorAction Stop
            Write-Host 'IP adicionado aos TrustedHosts com sucesso.' -ForegroundColor Green
        } catch {
            Write-Warning 'Nao foi possivel adicionar aos TrustedHosts (Requer Admin). A conexao pode falhar.'
            Write-Warning "Erro: $_"
        }
    }
} catch {
    Write-Warning "Erro ao consultar TrustedHosts: $_"
}

Write-Host "Conectando a $ip..." -ForegroundColor Cyan
Enter-PSSession -ComputerName $ip -Credential $cred
""".strip()


def _is_safe_remote_target(value: str) -> bool:
    """Conservative validator for an IP or hostname before launching PowerShell."""
    import re
    if not value or len(value) > 253:
        return False
    # IPv4
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
        try:
            return all(0 <= int(o) <= 255 for o in value.split("."))
        except ValueError:
            return False
    # Hostname: letters, digits, hyphen, dot. No spaces, no quotes, no PS metachars.
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))


@router.post("/tools/terminal/external")
def open_external_terminal(request: ExternalTerminalRequest):
    if not _is_safe_remote_target(request.ip):
        raise HTTPException(status_code=400, detail="Endereço de destino inválido.")
    if not request.username or "\x00" in request.username or "\x00" in request.password:
        raise HTTPException(status_code=400, detail="Credenciais inválidas.")

    try:
        encoded_cmd = base64.b64encode(_EXTERNAL_TERMINAL_SCRIPT.encode("utf-16le")).decode("utf-8")

        # Pass IP/user/pass via env vars instead of command line so they don't
        # appear in `Get-Process` / wmic / Process Explorer.
        env = os.environ.copy()
        env["NT_REMOTE_IP"] = request.ip
        env["NT_REMOTE_USER"] = request.username
        env["NT_REMOTE_PASS"] = request.password

        subprocess.Popen(
            ["powershell", "-NoProfile", "-NoExit", "-EncodedCommand", encoded_cmd],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=env,
        )

        return {"status": "success", "message": "Terminal externo iniciado."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar terminal: {str(e)}")

@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    if not _ws_origin_allowed(websocket):
        logging.warning(
            f"WS /ws/terminal connect rejected: origin={websocket.headers.get('origin')!r}"
        )
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
        return
    await websocket.accept()
    winrm_session = None
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "connect":
                ip = data.get("ip")
                username = data.get("username")
                password = data.get("password")
                credential_id = data.get("credential_id")
                
                if credential_id:
                    try:
                        from api.routes.security import vault
                        if not vault.is_unlocked:
                            await websocket.send_json({"type": "error", "message": "Cofre bloqueado. Desbloqueie nas configurações."})
                            continue
                            
                        target_cred = vault.get_credential(credential_id)
                        if target_cred:
                            username = target_cred['username']
                            password = target_cred['password']
                        else:
                            await websocket.send_json({"type": "error", "message": "Credencial não encontrada."})
                            continue
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": f"Erro ao recuperar credencial: {str(e)}"})
                        continue

                await websocket.send_json({"type": "status", "message": f"Conectando a {ip}..."})
                
                def connect_winrm():
                    handler = WinRMHandler(ip, username, password)
                    result = handler.connect()
                    return handler, result

                winrm_session, result = await asyncio.to_thread(connect_winrm)

                # Whatever the outcome, drop the local plaintext copy. The
                # handler kept its own copy of `password` until we changed it
                # to zero on success; in the failure path it lived in this
                # closure until the next "connect" message arrived. WinRMHandler
                # itself now nulls self.password on success.
                password = None
                data["password"] = None

                if result.get("success"):
                    await websocket.send_json({"type": "status", "message": "Conectado com sucesso!"})
                    await websocket.send_json({"type": "ready"})
                else:
                    await websocket.send_json({"type": "error", "message": f"Falha na conexão: {result.get('error')}"})
                    winrm_session = None

            elif msg_type == "command":
                if not winrm_session:
                    await websocket.send_json({"type": "error", "message": "Não conectado."})
                    continue
                
                command = data.get("command")
                try:
                    queue = asyncio.Queue()
                    loop = asyncio.get_running_loop()
                    def producer():
                        try:
                            for chunk in winrm_session.execute_streaming_command(command):
                                asyncio.run_coroutine_threadsafe(queue.put({"type": "output", "data": chunk}), loop)
                            asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                        except Exception as e:
                            asyncio.run_coroutine_threadsafe(queue.put({"type": "error", "message": str(e)}), loop)

                    t = threading.Thread(target=producer, daemon=True)
                    t.start()
                    
                    while True:
                        msg = await queue.get()
                        if msg is None: break
                        await websocket.send_json(msg)
                        
                    await websocket.send_json({"type": "prompt"})
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif msg_type == "disconnect":
                if winrm_session:
                    winrm_session.close()
                    winrm_session = None
                await websocket.send_json({"type": "status", "message": "Desconectado."})

    except WebSocketDisconnect:
        if winrm_session: winrm_session.close()
    except Exception as e:
        # logging.exception, not print: the Electron temp log used to capture
        # stdout/stderr from this child process, which could leak exception
        # context (URLs, partial credentials) to disk.
        logging.exception(f"Erro no WebSocket terminal: {e}")
        if winrm_session: winrm_session.close()

# --- Status Check (Legacy/Compat) ---
@router.get("/network/status")
def check_status(ip: str):
    """Verifica o status (online/offline) de um IP e atualiza o registro."""
    result = net_tools.check_host_status_detailed(ip)
    is_online = result['online']
    resolved_ip_found = None

    if not is_online and not ip.replace('.', '').isdigit():
         try:
             import socket
             resolved_ip = socket.gethostbyname(ip)
             if resolved_ip != ip:
                 res_resolved = net_tools.check_host_status_detailed(resolved_ip)
                 if res_resolved['online']:
                     result = res_resolved
                     is_online = True
                     resolved_ip_found = resolved_ip
                     result['resolved_ip'] = resolved_ip
         except Exception as e:
             logging.debug(f"check_status: hostname fallback resolve failed for {ip}: {e}")

    try:
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Update via HostManager
        current_hosts = get_hosts_list()
        modified = False
        
        for h in current_hosts:
            if h.address == ip:
                h.last_checked = current_time
                if h.last_status != is_online:
                    h.last_status = is_online
                    modified = True
                if is_online and resolved_ip_found:
                    h.ip = resolved_ip_found
                    modified = True
                elif is_online and (not h.ip or h.ip == "N/A"):
                    try:
                        resolved_ip, _ = net_tools.resolve_ip_and_hostname(ip)
                        if resolved_ip and resolved_ip != "N/A":
                            h.ip = resolved_ip
                            modified = True
                    except Exception as e:
                        logging.debug(f"check_status: post-online IP resolution failed for {ip}: {e}")
                break
        
        if modified:
            save_hosts_list(current_hosts)
            
    except Exception as e:
        logging.exception(f"Erro ao persistir status: {e}")

    return result
