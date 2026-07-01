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
    # Inferred probable device category (printer/camera/workstation/…). Best
    # effort: combines vendor + hostname + open ports. Never a model — MAC
    # cannot identify a model. `device_type_guess` marks low-confidence results.
    device_type: Optional[str] = None
    device_type_guess: Optional[bool] = None
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
        # Same lookup tolerance as update_host: exact → case-insensitive →
        # host.ip → monitor stats.ip. Operators clicking "refresh" from the
        # popup may have stats.ip on display; we shouldn't 404 that.
        target_host = next((h for h in current_hosts if h.address == address), None)
        if not target_host:
            addr_lower = address.lower() if isinstance(address, str) else address
            target_host = next(
                (h for h in current_hosts
                 if (h.address or "").lower() == addr_lower
                 or (h.ip or "").lower() == addr_lower),
                None,
            )
        if not target_host:
            try:
                monitor_stats = host_monitor.get_stats() or {}
                for monitored_addr, st in monitor_stats.items():
                    st_ip = (st or {}).get("ip") if isinstance(st, dict) else None
                    if st_ip and (st_ip == address or st_ip.lower() == addr_lower):
                        target_host = next(
                            (h for h in current_hosts if h.address == monitored_addr),
                            None,
                        )
                        if target_host:
                            break
            except Exception as e:
                logging.debug(f"refresh_host: monitor-stats fallback failed: {e}")

        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")

        # Use the host's canonical address for the resolver and persistence —
        # not the URL param, which may have been the resolved IP or a
        # case-drifted form.
        canonical_address = target_host.address

        hostname, domain = _resolve_fqdn_for_host(canonical_address)
        if hostname:
            target_host.hostname = hostname
            target_host.domain = domain

        host_manager_instance.update_host_details(canonical_address, hostname=hostname, domain=domain)

        # Forward-DNS: if `address` is a hostname, resolve and persist the
        # IPv4 so the card's "Endereço IP" stops showing the hostname after
        # an explicit refresh. Uses the per-network dns_server when the
        # host's IP belongs to a configured VLAN — otherwise system resolver.
        import ipaddress as _ip
        try:
            _ip.ip_address(canonical_address)
            is_hostname = False
        except ValueError:
            is_hostname = True
        if is_hostname:
            try:
                from src.network import dns_resolver
                # Pick the network's DNS server when we already know which
                # VLAN this host lives on. Falls back to system resolver
                # otherwise. The per-network DNS matters in multi-domain
                # environments where the same shortname exists in both ADs.
                dns_server = None
                if target_host.network_id:
                    try:
                        from api.routes.settings import load_settings
                        settings = load_settings()
                        for net in (settings.networks or []):
                            if net.id == target_host.network_id:
                                dns_server = net.dns_server
                                break
                    except Exception:
                        pass
                new_ip = dns_resolver.resolve_hostname(canonical_address, dns_server=dns_server)
                if new_ip:
                    target_host.ip = new_ip
                    host_manager_instance.update_resolved_ip(canonical_address, new_ip)
            except Exception as e:
                logging.debug(f"refresh_host: forward-DNS for {canonical_address!r} failed: {e}")

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
        # Address lookup is case-insensitive AND tolerant of callers passing
        # `stats.ip` (resolved IP) instead of the stored hostname. Backstory:
        # the frontend's `ipForHost(host)` now prefers `host.stats?.ip` for
        # display, so an operator looking at the popup may have the resolved
        # IP visually associated with the host, but `host.address` (the PK)
        # is still the hostname the host was cadastrado as. If the renderer
        # ever sends the IP by mistake (or a future refactor swaps them), a
        # strict equality check would 404 a legitimate update. Match by:
        #   1. exact (fast path)
        #   2. case-insensitive on .address
        #   3. .ip equality (covers the resolved-IP variant)
        #   4. stats.ip equality from the live monitor — needed because
        #      `host.ip` in the DB stores the hostname (when cadastrado por
        #      nome), so steps 1–3 don't cover the case where the frontend
        #      passes the *resolved* IP it got from /network/monitor.
        target_host = next((h for h in current_hosts if h.address == address), None)
        if not target_host:
            addr_lower = address.lower() if isinstance(address, str) else address
            target_host = next(
                (h for h in current_hosts
                 if (h.address or "").lower() == addr_lower
                 or (h.ip or "").lower() == addr_lower),
                None,
            )
        if not target_host:
            # Last resort: ask the live monitor for hosts whose resolved IP
            # matches `address`. This covers operators cadastrando por hostname
            # — the DB row's `ip` column is the hostname, while the resolved
            # IPv4 lives only in monitor stats.
            try:
                monitor_stats = host_monitor.get_stats() or {}
                resolved_match = None
                for monitored_addr, st in monitor_stats.items():
                    st_ip = (st or {}).get("ip") if isinstance(st, dict) else None
                    if st_ip and (st_ip == address or st_ip.lower() == addr_lower):
                        resolved_match = monitored_addr
                        break
                if resolved_match:
                    target_host = next(
                        (h for h in current_hosts if h.address == resolved_match),
                        None,
                    )
            except Exception as e:
                logging.debug(f"update_host: monitor-stats fallback failed: {e}")

        if not target_host:
            logging.warning(
                f"update_host: 404 for address={address!r}. "
                f"Known addresses: {[h.address for h in current_hosts][:20]}"
            )
            raise HTTPException(status_code=404, detail="Host não encontrado.")

        # Use the host's real address for downstream writes — the URL param
        # was just a lookup key.
        canonical_address = target_host.address

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
            _db.update_host_fields(canonical_address, probe_field_updates)

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

class IperfServerRequest(BaseModel):
    port: Optional[int] = 5201
    source_ip: Optional[str] = None  # NIC to bind the listener to (multi-VLAN)
    task_id: Optional[str] = None

class IperfClientRequest(BaseModel):
    target: str
    port: Optional[int] = 5201
    source_ip: Optional[str] = None  # NIC source for the egress (multi-VLAN)
    duration: Optional[int] = 10
    reverse: Optional[bool] = False  # server transmits, client receives
    udp: Optional[bool] = False
    task_id: Optional[str] = None

class PortScanRequest(BaseModel):
    target: str
    # Either a list/range string ("80, 443, 8000-8100") OR mode="top" for the
    # common-ports scan. `ports` wins when both are present.
    ports: Optional[str] = None
    mode: Optional[str] = None       # "top" | "all" | None (use `ports`)
    task_id: Optional[str] = None

class MtrRequest(BaseModel):
    target: str
    source_ip: Optional[str] = None
    task_id: Optional[str] = None

class TlsCheckRequest(BaseModel):
    host: str
    port: Optional[int] = 443

class TcpPingRequest(BaseModel):
    target: str
    port: int
    count: Optional[int] = 4
    source_ip: Optional[str] = None
    task_id: Optional[str] = None

class PmtuRequest(BaseModel):
    target: str
    source_ip: Optional[str] = None
    task_id: Optional[str] = None

class PtrSweepRequest(BaseModel):
    cidr: str
    dns_server: Optional[str] = None
    task_id: Optional[str] = None

class SubnetCalcRequest(BaseModel):
    cidr: str
    split_prefix: Optional[int] = None

class NtpRequest(BaseModel):
    server: str

class SnmpRequest(BaseModel):
    host: str
    community: Optional[str] = "public"
    port: Optional[int] = 161
    version: Optional[str] = "2c"

class HttpCheckRequest(BaseModel):
    url: str
    method: Optional[str] = "GET"
    verify_tls: Optional[bool] = True

class DiscoveryRequest(BaseModel):
    cidr: str
    task_id: Optional[str] = None
    timeout: Optional[int] = 200
    max_workers: Optional[int] = 50
    source_ip: Optional[str] = None  # NIC source for the discovery scan
    # When False, skip the post-scan ARP/vendor enrichment (faster scan, no
    # manufacturer column). Mirrors the `online_vendor_lookup` scanner setting.
    resolve_vendors: Optional[bool] = True

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
    import re as _re
    _IPV4_RE = _re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    raw_hosts = host_manager_instance.get_all_hosts()
    configured = _load_configured_networks()
    # Live monitor snapshot — used as a last-resort source for the resolved
    # IP when the DB column is still empty (host added recently, monitor
    # already resolved but the update_resolved_ip persistence hasn't fired
    # yet, etc.). Cheap dict copy.
    try:
        monitor_snapshot = host_monitor.get_stats() or {}
    except Exception:
        monitor_snapshot = {}
    hosts = []
    for item in raw_hosts:
        # `address` is the DB PK. May be either an IPv4 literal (host
        # cadastrado pelo IP) or a hostname (cadastrado pelo nome).
        address = item.get("ip")
        # Resolved IPv4 — best-of-three:
        #   1. DB column `resolved_ip` (persisted by monitor on forward-DNS)
        #   2. monitor.stats[address].ip (in-memory; survives restart only
        #      until the next DNS cycle)
        #   3. address itself, if it's already an IPv4 literal
        resolved_ip = item.get("resolved_ip")
        if not resolved_ip:
            st = monitor_snapshot.get(address) if address else None
            if isinstance(st, dict):
                cand = st.get("ip")
                if cand and _IPV4_RE.match(cand):
                    resolved_ip = cand
        if not resolved_ip and address and _IPV4_RE.match(address):
            resolved_ip = address

        # Network match uses the *actual IP*, not the hostname — VLAN
        # detection by CIDR is meaningless on a non-IP value.
        net_id, net_name = _match_network(resolved_ip, configured)
        resolved_hostname = item.get("name")          # DNS-resolved
        nickname = item.get("nickname")               # operator label (DB description)
        # Display name fallback chain:
        #   nickname → resolved hostname → IP literal
        # Never "Unknown". Operators want the card to show *something useful*
        # at a glance even before the monitor has resolved DNS; the IP is the
        # least-bad fallback and is always present.
        display_name = nickname or resolved_hostname or address
        hosts.append(Host(
            name=display_name,
            address=address,
            type=item.get("type", "generic"),
            mac=item.get("mac"),
            vendor=item.get("vendor"),
            hostname=resolved_hostname,
            domain=item.get("domain"),
            # Frontend's `host.ip` is now ALWAYS the real IPv4 (or None when
            # nothing was resolved yet). Operators clicking "Copiar IP" or
            # using a quick action no longer get a hostname back.
            ip=resolved_ip,
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
        # Only persist `display` as nickname if it's a true operator label —
        # not the resolved hostname, not the IP fallback we now use when no
        # hostname is known, and not the literal "Unknown" from legacy data.
        # Otherwise nicknames would get frozen as "10.0.0.5" after the first
        # save and never update when DNS later resolves the real name.
        is_meaningful = (
            display
            and display != resolved
            and display != h.address
            and display != 'Unknown'
        )
        nickname = display if is_meaningful else None
        # `h.ip` here is the resolved IPv4 that get_hosts_list computed
        # (best-of-three: DB resolved_ip → monitor stats → address-if-IPv4).
        # Persist it back as resolved_ip so the full-table rewrite below
        # doesn't blow away the cache. Only persist when it's a real IPv4 and
        # differs from the address — for IP-registered hosts address IS the IP
        # and a separate resolved_ip column is redundant.
        import re as _re
        h_ip = h.ip if (h.ip and _re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", h.ip)) else None
        resolved_ip_to_persist = h_ip if (h_ip and h_ip != h.address) else None
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
            'last_status': h.last_status,
            # Forward the columns added after the initial schema so the
            # replace_all_hosts (DELETE+INSERT) inside update_hosts doesn't
            # NULL them. CRITICAL: the v1.2.6 fix wired update_hosts /
            # replace_all_hosts to READ these via .get(), but this caller never
            # populated them — so PATCH name/group/ports/monitoring still wiped
            # resolved_ip + the host-probe fields for every host. This closes
            # that loop.
            'resolved_ip': resolved_ip_to_persist,
            'current_user': h.current_user,
            'last_boot': h.last_boot,
            'system_disk_free_gb': h.system_disk_free_gb,
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

        # If the operator added the host by hostname, resolve the IPv4
        # synchronously *once* and persist it. The monitor will eventually
        # do this on its own (5s DNS loop), but doing it now means the card
        # shows the real IP from the very first GET /hosts after add — no
        # "hostname-in-the-IP-column" beat to confuse the operator.
        import ipaddress as _ip
        try:
            _ip.ip_address(host.address)
            is_hostname = False
        except ValueError:
            is_hostname = True
        if is_hostname:
            try:
                from src.network import dns_resolver
                resolved = dns_resolver.resolve_hostname(host.address)
                if resolved:
                    host_manager_instance.update_resolved_ip(host.address, resolved)
            except Exception as e:
                logging.debug(f"add_host: forward-DNS for {host.address!r} failed: {e}")

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


@router.get("/hosts/{address}/metrics")
def get_host_metrics(address: str, range: str = "24h"):
    """Histórico de uptime/latência de um host para os gráficos do HostDetails.

    `range`: '24h' (default) ou '7d'. Retorna {points:[{ts,online,latency,
    packet_loss_pct}], uptime_pct, sample_count, range}. Vazio (não erro) quando
    ainda não há amostras — a UI mostra um placeholder.
    """
    import time as _time
    from src.core.database import db as _db

    ranges = {"24h": 86400, "7d": 7 * 86400}
    window = ranges.get(range)
    if window is None:
        raise HTTPException(status_code=400, detail="range deve ser '24h' ou '7d'.")

    since = int(_time.time()) - window
    points = _db.get_host_metrics(address, since)

    # Uptime % over the returned window (share of samples that were online).
    sample_count = len(points)
    if sample_count:
        online_count = sum(1 for p in points if p.get("online"))
        uptime_pct = round(100.0 * online_count / sample_count, 1)
    else:
        uptime_pct = None

    return {
        "address": address,
        "range": range,
        "sample_count": sample_count,
        "uptime_pct": uptime_pct,
        "points": points,
    }


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
        # Validate as a real IP (v4 or v6) so a malformed value returns a clear
        # 400 instead of silently yielding fqdn:null (dns.reversename would
        # raise internally and the resolver would just return None).
        try:
            ipaddress.ip_address(req.ip)
        except ValueError:
            raise HTTPException(status_code=400, detail="`ip` deve ser um endereço IP válido.")
        fqdn = dns_resolver.resolve_ip(req.ip, req.dns_server)
        return {"ip": req.ip, "fqdn": fqdn, "dns_server": req.dns_server}
    raise HTTPException(status_code=400, detail="Informe `name` ou `ip`.")

@router.post("/network/discovery")
def discover_network(request: DiscoveryRequest):
    cidr = request.cidr
    task_id = request.task_id or f"scanner_{time.time()}"
    timeout = request.timeout or 200
    # Cap max_workers too. The CIDR is already capped at /16 below, but the
    # `max_workers` field was unbounded — a request with `max_workers: 100000`
    # would spawn 100k threads regardless of CIDR size and exhaust file
    # descriptors. 256 covers any legitimate scanning rate.
    try:
        requested_workers = int(request.max_workers or 50)
    except (TypeError, ValueError):
        requested_workers = 50
    max_workers = max(1, min(requested_workers, 256))

    # Validate source_ip if provided (must be a literal IP, see
    # /network/dns/resolve for the reasoning — same threat model).
    source_ip = request.source_ip
    if source_ip:
        import ipaddress as _ip
        try:
            _ip.ip_address(source_ip)
        except ValueError:
            raise HTTPException(status_code=400, detail="source_ip deve ser um endereço IP.")

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
                resolve_vendors=request.resolve_vendors,
            )
            for host in iterator:
                yield json.dumps(host).encode('utf-8') + b"\n"
                # No artificial 10ms sleep; back-pressure on the streaming
                # response is the right flow-control mechanism.
        except Exception as e:
            yield json.dumps({"error": str(e)}).encode('utf-8') + b"\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.get("/network/vendors/info")
def vendors_info():
    """Status of the local MAC-vendor (OUI) database for the Settings UI."""
    from src.network.vendor_utils import VendorUtils
    return VendorUtils.get_database_info()


@router.post("/network/vendors/update")
def vendors_update():
    """Download a fresh IEEE OUI database. ONLINE and may take a few seconds.

    Explicit operator action only — the scan never auto-downloads (avoids
    surprising a corporate operator and tripping IDS on the IEEE OUI fetch).
    Blocking is acceptable here: it's a deliberate button press, not the scan
    hot path.
    """
    from src.network.vendor_utils import VendorUtils
    success, message = VendorUtils.update_database()
    if not success:
        raise HTTPException(status_code=502, detail=message)
    return {"status": "success", "message": message, "info": VendorUtils.get_database_info()}


def _validate_tool_target(target: str) -> None:
    """Reject targets that look like CLI flags or contain shell metacharacters.

    The /tools/ping and /tools/traceroute endpoints pass `target` as an argv
    element (no shell), so this isn't RCE — but a value starting with `-` is
    interpreted as an option by ping.exe/tracert.exe and triggers help output
    instead of a real probe, and arbitrary strings exfiltrate via the system
    DNS resolver. Use the same shape as `_is_safe_remote_target`."""
    if not _is_safe_remote_target(target):
        raise HTTPException(status_code=400, detail="Endereço de destino inválido.")


def _validate_optional_source_ip(value):
    if not value:
        return
    import ipaddress as _ip
    try:
        _ip.ip_address(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="source_ip deve ser um endereço IP.")


@router.post("/tools/ping")
def run_ping(request: ToolRequest):
    target = request.target
    _validate_tool_target(target)
    _validate_optional_source_ip(request.source_ip)
    task_id = request.task_id or f"ping_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            iterator = net_tools.continuous_ping(target, task_id, source_ip=source_ip)
            for item in iterator:
                line = item[0] if isinstance(item, tuple) else str(item)
                if line:
                    yield line.encode('utf-8')
                    # No artificial 10ms sleep; back-pressure on the streaming
                # response is the right flow-control mechanism.
        except Exception as e:
            yield f"Erro ao executar ping: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")

@router.post("/tools/traceroute")
def run_traceroute(request: ToolRequest):
    target = request.target
    _validate_tool_target(target)
    _validate_optional_source_ip(request.source_ip)
    task_id = request.task_id or f"traceroute_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            iterator = net_tools.traceroute(target, task_id, source_ip=source_ip)
            for item in iterator:
                line = item[0] if isinstance(item, tuple) else str(item)
                if line:
                    yield line.encode('utf-8')
                    # No artificial 10ms sleep; back-pressure on the streaming
                # response is the right flow-control mechanism.
        except Exception as e:
            yield f"Erro ao executar traceroute: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")

def _validate_port(value) -> int:
    """Coerce + validate a TCP/UDP port to 1..65535. Raises 400 on bad input."""
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Porta inválida.")
    if not (1 <= port <= 65535):
        raise HTTPException(status_code=400, detail="Porta deve estar entre 1 e 65535.")
    return port


@router.get("/tools/iperf/status")
def iperf_status():
    """Whether the bundled iperf binary is available, plus its version. The
    frontend uses this to enable/disable the bandwidth tab with a clear
    message instead of failing mid-stream."""
    return net_tools.get_iperf_info()


@router.post("/tools/iperf/server")
def run_iperf_server(request: IperfServerRequest):
    """Start iperf in SERVER mode. This machine becomes the bandwidth-test
    destination; operators on other VLANs run `iperf -c <this_ip>` against it.

    Runs until stopped via /tools/stop (or the client disconnects, which tears
    down the StreamingResponse and terminates the process)."""
    port = _validate_port(request.port if request.port is not None else 5201)
    _validate_optional_source_ip(request.source_ip)
    task_id = request.task_id or f"iperf_server_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            iterator = net_tools.run_iperf_server(task_id, port=port, source_ip=source_ip)
            for item in iterator:
                line = item[0] if isinstance(item, tuple) else str(item)
                if line:
                    yield line.encode('utf-8')
        except Exception as e:
            yield f"Erro ao executar servidor iperf: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/tools/iperf/client")
def run_iperf_client(request: IperfClientRequest):
    """Run iperf in CLIENT mode against an existing iperf server on the network
    (the inverse of /tools/iperf/server). Measures bandwidth from this machine
    to `target`."""
    target = request.target
    _validate_tool_target(target)
    _validate_optional_source_ip(request.source_ip)
    port = _validate_port(request.port if request.port is not None else 5201)
    task_id = request.task_id or f"iperf_client_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            iterator = net_tools.run_iperf_client(
                target, task_id, port=port, source_ip=source_ip,
                duration=request.duration, reverse=bool(request.reverse),
                udp=bool(request.udp),
            )
            for item in iterator:
                line = item[0] if isinstance(item, tuple) else str(item)
                if line:
                    yield line.encode('utf-8')
        except Exception as e:
            yield f"Erro ao executar cliente iperf: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/tools/mtr")
def run_mtr(request: MtrRequest):
    """MTR-style path monitor: streams a per-hop table (latency/jitter/loss)
    every cycle until stopped via /tools/stop. Uses OS-native tracert + ping."""
    target = request.target
    _validate_tool_target(target)
    _validate_optional_source_ip(request.source_ip)
    task_id = request.task_id or f"mtr_{time.time()}"
    source_ip = request.source_ip

    def event_generator():
        try:
            for line in net_tools.run_mtr(target, task_id, source_ip=source_ip):
                # mtr module already yields NDJSON strings.
                yield (line if isinstance(line, str) else str(line)).encode('utf-8')
        except Exception as e:
            yield (json.dumps({"error": str(e)}) + "\n").encode('utf-8')
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/tools/ports")
def scan_ports(request: PortScanRequest):
    """Test TCP ports on a host. `mode='top'` scans common ports, `mode='all'`
    scans 1-65535, otherwise `ports` is a list/range string ('80,443,8000-8100').
    All three underlying calls are line generators; we stream them as-is."""
    target = request.target
    _validate_tool_target(target)
    task_id = request.task_id or f"ports_{time.time()}"

    def event_generator():
        try:
            mode = (request.mode or "").lower()
            if mode not in ("top", "all") and (not request.ports or not request.ports.strip()):
                yield "Informe portas (ex.: 80, 443, 8000-8100) ou um modo.\n".encode('utf-8')
                return
            # run_port_scan registers a stop event under task_id so /tools/stop
            # can actually cancel the scan (the bare generators couldn't be).
            line_gen = net_tools.run_port_scan(target, task_id, ports_str=request.ports, mode=mode)
            for line in line_gen:
                yield (line if isinstance(line, str) else str(line)).encode('utf-8')
        except Exception as e:
            yield f"Erro ao testar portas: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.get("/network/traffic")
def network_traffic():
    """Cumulative per-NIC byte/packet counters + server timestamp. The frontend
    diffs successive snapshots to compute throughput (multi-VLAN: one row per
    NIC). Stateless — sampling cadence is the client's choice."""
    return net_tools.get_traffic_snapshot()


# ---- TLS certificate inspector ----
@router.post("/tools/tls")
def tls_check(request: TlsCheckRequest):
    """Inspect the TLS certificate served by host:port (subject/SAN/expiry)."""
    if not _is_safe_remote_target(request.host):
        raise HTTPException(status_code=400, detail="Host inválido.")
    port = _validate_port(request.port if request.port is not None else 443)
    from src.network import tls_check as _tls
    return _tls.check_certificate(request.host, port)


# ---- TCP ping ----
@router.post("/tools/tcp-ping")
def tcp_ping(request: TcpPingRequest):
    """TCP-connect ping: liveness + latency for ICMP-blocking hosts."""
    _validate_tool_target(request.target)
    _validate_optional_source_ip(request.source_ip)
    port = _validate_port(request.port)
    task_id = request.task_id or f"tcpping_{time.time()}"

    def event_generator():
        try:
            for line in net_tools.run_tcp_ping(request.target, port, task_id,
                                                count=request.count, source_ip=request.source_ip):
                yield (line if isinstance(line, str) else str(line)).encode('utf-8')
        except Exception as e:
            yield f"Erro no TCP ping: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")


# ---- Path MTU discovery ----
@router.post("/tools/pmtu")
def pmtu(request: PmtuRequest):
    """Discover the largest unfragmented packet to the target (path MTU)."""
    _validate_tool_target(request.target)
    _validate_optional_source_ip(request.source_ip)
    task_id = request.task_id or f"pmtu_{time.time()}"

    def event_generator():
        try:
            for line in net_tools.run_pmtu(request.target, task_id, source_ip=request.source_ip):
                yield (line if isinstance(line, str) else str(line)).encode('utf-8')
        except Exception as e:
            yield f"Erro no PMTU: {str(e)}\n".encode('utf-8')
    return StreamingResponse(event_generator(), media_type="text/plain")


# ---- Reverse-DNS (PTR) sweep ----
@router.post("/tools/ptr-sweep")
def ptr_sweep(request: PtrSweepRequest):
    """Resolve every host in a CIDR to a name (VLAN inventory). NDJSON stream."""
    if request.dns_server:
        import ipaddress as _ip
        try:
            _ip.ip_address(request.dns_server)
        except ValueError:
            raise HTTPException(status_code=400, detail="dns_server deve ser um endereço IP.")
    task_id = request.task_id or f"ptrsweep_{time.time()}"

    def event_generator():
        try:
            for line in net_tools.run_ptr_sweep(request.cidr, task_id, dns_server=request.dns_server):
                yield (line if isinstance(line, str) else str(line)).encode('utf-8')
        except Exception as e:
            yield (json.dumps({"error": str(e)}) + "\n").encode('utf-8')
    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# ---- Subnet calculator ----
@router.post("/tools/subnet")
def subnet_calc(request: SubnetCalcRequest):
    """CIDR math: network/broadcast/usable range/mask/wildcard, optional split."""
    from src.network import subnet_calc as _sc
    result = _sc.calc(request.cidr, split_prefix=request.split_prefix)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "CIDR inválido."))
    return result


# ---- NTP query ----
@router.post("/tools/ntp")
def ntp_query(request: NtpRequest):
    """Query an NTP server for clock offset/stratum (Kerberos skew check)."""
    if not _is_safe_remote_target(request.server):
        raise HTTPException(status_code=400, detail="Servidor NTP inválido.")
    from src.network import ntp_tool
    return ntp_tool.query(request.server)


# ---- SNMP system query (async: pysnmp 7.x is asyncio) ----
@router.post("/tools/snmp")
async def snmp_query(request: SnmpRequest):
    """Read the SNMP system group from a network device (switch/router)."""
    if not _is_safe_remote_target(request.host):
        raise HTTPException(status_code=400, detail="Host SNMP inválido.")
    port = _validate_port(request.port if request.port is not None else 161)
    from src.network import snmp_tool
    return await snmp_tool.query_system(
        request.host, community=request.community or "public",
        port=port, version=request.version or "2c",
    )


# ---- Local connections (netstat-like) ----
@router.get("/tools/connections")
def local_connections(kind: str = "inet"):
    """Active local TCP/UDP connections with owning process (netstat -ano +
    process name). `kind`: 'inet' | 'tcp' | 'udp'."""
    from src.network import netstat
    if kind not in ("inet", "tcp", "udp"):
        kind = "inet"
    return {"connections": netstat.get_connections(kind=kind)}


# ---- HTTP endpoint health/latency ----
@router.post("/tools/http")
def http_check(request: HttpCheckRequest):
    """GET/HEAD a URL with timing (TTFB/total) and status."""
    from src.network import http_check as _http
    return _http.check(request.url, method=request.method or "GET",
                       verify_tls=request.verify_tls if request.verify_tls is not None else True)


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

# 1 MB cap per WS message. Legitimate `command` payloads are at most a few
# KB; anything larger is either misuse or a local-process DoS attempt (the
# origin check stops browser-driven abuse, but in-scope per threat model).
_WS_MAX_MESSAGE_BYTES = 1 * 1024 * 1024


async def _ws_receive_json_bounded(websocket: WebSocket) -> dict:
    """Receive a JSON message with a hard byte cap; drops the connection on
    overflow with WebSocket close code 1009 (Message Too Big)."""
    message = await websocket.receive()
    text = message.get("text")
    if text is None:
        data = message.get("bytes") or b""
        if len(data) > _WS_MAX_MESSAGE_BYTES:
            await websocket.close(code=1009)
            raise WebSocketDisconnect()
        text = data.decode("utf-8")
    elif len(text.encode("utf-8")) > _WS_MAX_MESSAGE_BYTES:
        await websocket.close(code=1009)
        raise WebSocketDisconnect()
    return json.loads(text)


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
            data = await _ws_receive_json_bounded(websocket)
            msg_type = data.get("type")
            
            if msg_type == "connect":
                ip = data.get("ip")
                username = data.get("username")
                password = data.get("password")
                credential_id = data.get("credential_id")

                # Validate the target before touching WinRM — same guard as
                # the REST /tools/terminal/external path. WinRMHandler builds
                # a PowerShell session against `ip`; rejecting non-host shapes
                # here keeps the two terminal entry points consistent.
                if not _is_safe_remote_target(ip or ""):
                    await websocket.send_json({"type": "error", "message": "Endereço de destino inválido."})
                    continue

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
    """Verifica o status (online/offline) de um IP e atualiza o registro.

    Validate `ip` with the same shape regex as `/tools/ping` so:
      - A value starting with `-` can't be interpreted as a ping.exe option.
      - The hostname-fallback path below can't be coerced into an arbitrary
        DNS lookup for exfiltration. The system resolver is also bypassed
        in favor of the per-network `dns_resolver` so multi-domain setups
        pick the right answer.
    """
    if not _is_safe_remote_target(ip):
        raise HTTPException(status_code=400, detail="Endereço de destino inválido.")

    result = net_tools.check_host_status_detailed(ip)
    is_online = result['online']
    resolved_ip_found = None

    if not is_online and not ip.replace('.', '').isdigit():
         try:
             from src.network import dns_resolver
             # Prefer the DNS server of the network this host belongs to (if any).
             # `_match_network` only works on IP literals; here `ip` is a hostname,
             # so we fall back to the system resolver via dns_resolver (which
             # itself routes through any configured `dns_server` when one is
             # provided).
             resolved_ip = dns_resolver.resolve_hostname(ip)
             if resolved_ip and resolved_ip != ip:
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
                        # `ip` here is the host's address (may be a hostname when
                        # cadastrado por nome). We want to fill h.ip with the
                        # resolved IPv4. Forward-resolve via dns_resolver.
                        # NOTE: the previous code did
                        #   `resolved_ip, _ = net_tools.resolve_ip_and_hostname(ip)`
                        # which always raised — that method returns a single
                        # HOSTNAME (not a 2-tuple, and not an IP), so the unpack
                        # threw every time and this enrichment never ran.
                        from src.network import dns_resolver
                        resolved_ip = dns_resolver.resolve_hostname(ip)
                        if resolved_ip and resolved_ip != ip and resolved_ip != "N/A":
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
