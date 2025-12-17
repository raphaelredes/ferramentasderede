from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
import time
import sys
import os
import threading
from typing import List, Optional

# Adicionar diretório pai ao path para importar módulos do src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.network.tools import NetworkTools
from src.network.monitor import HostMonitor
from src.system.core.winrm_handler import WinRMHandler

net_tools = NetworkTools()
host_monitor = HostMonitor()

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

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

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Pre-process to handle non-string fields
        if isinstance(obj, dict):
            if 'teamviewer_id' in obj and obj['teamviewer_id'] is not None:
                obj['teamviewer_id'] = str(obj['teamviewer_id']).replace('.0', '')
            
            if 'last_checked' in obj and obj['last_checked'] is not None:
                val = obj['last_checked']
                if isinstance(val, (float, int)):
                    try:
                        from datetime import datetime
                        obj['last_checked'] = datetime.fromtimestamp(val).isoformat()
                    except:
                        obj['last_checked'] = str(val)
                        
        return super().model_validate(obj, *args, **kwargs)

# ... (omitted lines)

@router.post("/hosts/{address}/refresh")
def refresh_host(address: str):
    try:
        current_hosts = get_hosts_list()
        target_host = next((h for h in current_hosts if h.address == address), None)
        
        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")
            
        fqdn = net_tools.resolve_ip_and_hostname(address)
        ip = address # Assumindo que address é o IP
        
        if fqdn and fqdn not in ["N/A", "Inválido", "Erro"]:
            parts = fqdn.split('.', 1)
            target_host.hostname = parts[0]
            if len(parts) > 1: target_host.domain = parts[1]
        
        if ip and ip != "N/A":
            target_host.ip = ip

        # Try to fetch system info to get current user (if credentials available in vault/cache or if we can)
        # Note: This endpoint is usually called without credentials. 
        # Ideally, current_user is updated via /system/info or a background task.
        # But if we want to update it here, we'd need credentials.
        # For now, we'll rely on the frontend calling /system/info or the background monitor updating it.
        # However, the user asked to search by it, so we need to ensure it's persisted.
        # The Host model update above ensures persistence if save_hosts_list is called.
                
        save_hosts_list(current_hosts)
        return {"status": "success", "message": "Informações atualizadas.", "host": target_host}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao atualizar host: {str(e)}")

class HostUpdate(BaseModel):
    name: Optional[str] = None
    group: Optional[str] = None
    mac: Optional[str] = None
    monitoring: Optional[bool] = None
    reset_stats: Optional[bool] = False
    teamviewer_id: Optional[str] = None
    ports: Optional[List[int]] = None

# ... (omitted lines)

@router.patch("/hosts/{address}")
def update_host(address: str, update: HostUpdate):
    try:
        current_hosts = get_hosts_list()
        target_host = next((h for h in current_hosts if h.address == address), None)
        
        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")
            
        if update.name is not None: target_host.name = update.name
        if update.group is not None: target_host.group = update.group
        if update.mac is not None: target_host.mac = update.mac
        if update.monitoring is not None: target_host.monitoring = update.monitoring
        if update.teamviewer_id is not None: target_host.teamviewer_id = update.teamviewer_id
        if update.ports is not None: target_host.ports = update.ports
        if update.reset_stats: host_monitor.reset_host_stats(target_host.address)
            
        save_hosts_list(current_hosts)
        host_monitor.update_hosts([h.dict() for h in current_hosts])
        return {"status": "success", "message": "Host atualizado com sucesso.", "host": target_host}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao atualizar host: {str(e)}")

class ToolRequest(BaseModel):
    target: str
    task_id: Optional[str] = None

class DiscoveryRequest(BaseModel):
    cidr: str
    task_id: Optional[str] = None
    timeout: Optional[int] = 200
    max_workers: Optional[int] = 50
    online_vendor_lookup: Optional[bool] = False

class StopRequest(BaseModel):
    task_id: str

class WolRequest(BaseModel):
    mac_address: str

# --- Hosts Management ---
from src.core.host_manager import HostManager

# Singleton instance of HostManager
host_manager_instance = HostManager()

def get_hosts_list():
    """Helper to get hosts as Host objects using HostManager."""
    raw_hosts = host_manager_instance.get_all_hosts()
    hosts = []
    for item in raw_hosts:
        # Map HostManager dict to Host model
        hosts.append(Host(
            name=item.get("name", "Unknown"), 
            address=item.get("ip"), # HostManager uses 'ip' for address
            type=item.get("type", "generic"), 
            mac=item.get("mac"),
            vendor=item.get("vendor"),
            hostname=item.get("name"), # HostManager maps hostname to name
            domain=item.get("domain"),
            ip=item.get("ip"),
            last_status=item.get("last_status"),
            last_checked=item.get("last_checked"),
            group=item.get("group"),
            monitoring=item.get("monitoring", True),
            teamviewer_id=item.get("teamviewer_id"),
            ports=item.get("ports", []),
            current_user=item.get("current_user")
        ))
    return hosts

def save_hosts_list(hosts_list):
    """Helper to save hosts using HostManager."""
    # Convert Host objects back to dicts expected by HostManager
    updated_list = []
    for h in hosts_list:
        updated_list.append({
            'name': h.name,
            'ip': h.address,
            'mac': h.mac,
            'nickname': h.name, # Use name as nickname/description if not separate
            'group': h.group,
            'tags': [], # Host model doesn't have tags yet, maybe add?
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
        # Use HostManager directly for adding
        new_host_data = {
            'name': host.name,
            'ip': host.address,
            'mac': host.mac,
            'nickname': host.name,
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
        host_monitor.update_hosts([h.dict() for h in current_hosts])
            
        return {"status": "success", "message": f"Host {host.name} adicionado."}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao salvar host: {str(e)}")

@router.post("/hosts/{address}/refresh")
def refresh_host(address: str):
    try:
        current_hosts = get_hosts_list()
        target_host = next((h for h in current_hosts if h.address == address), None)
        
        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")
            
        fqdn = net_tools.resolve_ip_and_hostname(address)
        ip = address
        
        if fqdn and fqdn not in ["N/A", "Inválido", "Erro"]:
            parts = fqdn.split('.', 1)
            target_host.hostname = parts[0]
            if len(parts) > 1: target_host.domain = parts[1]
        
        if ip and ip != "N/A":
            target_host.ip = ip
                
        save_hosts_list(current_hosts)
        return {"status": "success", "message": "Informações atualizadas.", "host": target_host}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao atualizar host: {str(e)}")

@router.delete("/hosts/{address}")
def delete_host(address: str):
    try:
        # Use HostManager directly
        host_manager_instance.remove_hosts([{'ip': address}])
        
        # Update monitor
        current_hosts = get_hosts_list()
        host_monitor.update_hosts([h.dict() for h in current_hosts])
        
        return {"status": "success", "message": "Host removido com sucesso."}
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao remover host: {str(e)}")

@router.patch("/hosts/{address}")
def update_host(address: str, update: HostUpdate):
    try:
        current_hosts = get_hosts_list()
        target_host = next((h for h in current_hosts if h.address == address), None)
        
        if not target_host:
            raise HTTPException(status_code=404, detail="Host não encontrado.")
            
        if update.name is not None: target_host.name = update.name
        if update.group is not None: target_host.group = update.group
        if update.mac is not None: target_host.mac = update.mac
        if update.monitoring is not None: target_host.monitoring = update.monitoring
        if update.teamviewer_id is not None: target_host.teamviewer_id = update.teamviewer_id
        if update.ports is not None: target_host.ports = update.ports
        if update.reset_stats: host_monitor.reset_host_stats(target_host.address)
            
        save_hosts_list(current_hosts)
        host_monitor.update_hosts([h.dict() for h in current_hosts])
        return {"status": "success", "message": "Host atualizado com sucesso.", "host": target_host}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=f"Erro ao atualizar host: {str(e)}")

# --- Network Tools ---
@router.get("/network/monitor")
def get_monitor_stats():
    return host_monitor.get_stats()

@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    await manager.connect(websocket)
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

@router.post("/network/discovery")
def discover_network(request: DiscoveryRequest):
    cidr = request.cidr
    task_id = request.task_id or f"scanner_{time.time()}"
    timeout = request.timeout or 200
    max_workers = request.max_workers or 50
    online_lookup = request.online_vendor_lookup or False
    
    def event_generator():
        try:
            import ipaddress
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                yield json.dumps({"error": "CIDR inválido."}).encode('utf-8') + b"\n"
                return

            iterator = net_tools.discover_hosts(network, task_id, timeout=timeout, max_workers=max_workers, online_vendor_lookup=online_lookup)
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
    
    def event_generator():
        try:
            iterator = net_tools.continuous_ping(target, task_id)
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
    
    def event_generator():
        try:
            iterator = net_tools.traceroute(target, task_id)
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

@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
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
                    def producer():
                        try:
                            for chunk in winrm_session.execute_streaming_command(command):
                                asyncio.run_coroutine_threadsafe(queue.put({"type": "output", "data": chunk}), asyncio.get_event_loop())
                            asyncio.run_coroutine_threadsafe(queue.put(None), asyncio.get_event_loop())
                        except Exception as e:
                            asyncio.run_coroutine_threadsafe(queue.put({"type": "error", "message": str(e)}), asyncio.get_event_loop())

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
        print(f"Erro no WebSocket: {e}")
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
         except: pass

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
                    except: pass
                break
        
        if modified:
            save_hosts_list(current_hosts)
            
    except Exception as e:
        print(f"Erro ao persistir status: {e}")

    return result
