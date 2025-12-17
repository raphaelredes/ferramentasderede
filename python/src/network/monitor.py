import threading
import time
import logging
import socket
import ipaddress
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from .ping import check_host_status_detailed
from . import mac_utils
from .tools import NetworkTools

class HostMonitor:
    def __init__(self):
        self._hosts: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=50)
        self._monitor_thread = None
        self._last_resolution_times = {}
        self._processing_hosts = set()

    def start_monitoring(self, hosts: List[Dict[str, Any]], on_update_callback=None):
        """Inicia o monitoramento para uma lista de hosts."""
        if self._running:
            self.update_hosts(hosts)
            return

        self._running = True
        self._on_update_callback = on_update_callback
        self.update_hosts(hosts)
        
        self._monitor_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._monitor_thread.start()
        
        self._dns_thread = threading.Thread(target=self._dns_loop, daemon=True)
        self._dns_thread.start()

    def stop_monitoring(self):
        """Para todo o monitoramento."""
        self._running = False
        self._on_update_callback = None
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = ThreadPoolExecutor(max_workers=50) # Recreate for next start
        
        with self._lock:
            self._hosts.clear()
            self._last_resolution_times.clear()
            self._processing_hosts.clear()

    def update_hosts(self, hosts: List[Dict[str, Any]]):
        """Atualiza a lista de hosts monitorados."""
        if not self._running:
            return

        current_ips = set()
        
        with self._lock:
            # Identificar hosts novos e removidos
            for host in hosts:
                ip = host.get('address')
                if not ip:
                    continue
                
                current_ips.add(ip)
                
                # Se é um novo host, inicializar stats
                if ip not in self._hosts:
                    self._hosts[ip] = {
                        'online': False,
                        'latency': None,
                        'average_latency': None,
                        'packet_loss': 0,
                        'packet_loss_pct': 0,
                        'total_packets': 0,
                        'packets_sent_history': 0,
                        'packets_lost_history': 0,
                        'latency_sum': 0.0,
                        'latency_count': 0,
                        'last_checked': None,
                        'hostname': host.get('hostname'),
                        'domain': host.get('domain'),
                        'calibration_done': False,
                        'monitoring': host.get('monitoring', True),
                        'ip': ip, # Store resolved/current IP
                        'consecutive_successes': 0,
                        'consecutive_failures': 0,
                        'is_smart_offline': False,
                        'is_smart_offline': False,
                        'history': [], # List of {timestamp, latency, packet_loss} - managed manually to avoid deque serialization issues
                        'ports': host.get('ports', []),
                        'ports_status': {},
                        'monitoring_start_time': time.time()
                    }
                else:
                    # Atualizar flag de monitoramento, hostname e portas se host já existe
                    self._hosts[ip]['monitoring'] = host.get('monitoring', True)
                    self._hosts[ip]['hostname'] = host.get('hostname')
                    self._hosts[ip]['ports'] = host.get('ports', [])

            # Remover hosts que não estão mais na lista
            ips_to_remove = [ip for ip in self._hosts if ip not in current_ips]
            for ip in ips_to_remove:
                del self._hosts[ip]
                if ip in self._last_resolution_times:
                    del self._last_resolution_times[ip]
                if ip in self._processing_hosts:
                    self._processing_hosts.discard(ip)

    def reset_host_stats(self, ip: str):
        """Reseta as estatísticas de ping para um host específico."""
        with self._lock:
            if ip in self._hosts:
                stats = self._hosts[ip]
                stats['latency'] = None
                stats['average_latency'] = None
                stats['packet_loss'] = 0
                stats['packet_loss_pct'] = 0
                stats['total_packets'] = 0
                stats['packets_sent_history'] = 0
                stats['packets_lost_history'] = 0
                stats['latency_sum'] = 0.0
                stats['latency_count'] = 0
                stats['calibration_done'] = False
                stats['consecutive_successes'] = 0
                stats['consecutive_failures'] = 0
                stats['is_smart_offline'] = False
                # Keep history for context, or clear it? Better keep it to show the "drop"
                logging.info(f"Estatísticas resetadas para o host {ip}")

    def _main_loop(self):
        """Loop principal que agenda as tarefas de ping."""
        while self._running:
            start_time = time.time()
            
            # Snapshot dos hosts para iterar sem bloquear por muito tempo
            with self._lock:
                hosts_to_process = [(ip, data['hostname'], data.get('monitoring', True)) 
                                  for ip, data in self._hosts.items()]

            for ip, hostname, monitoring in hosts_to_process:
                if monitoring:
                    # Check if already processing to avoid queue flooding
                    should_process = False
                    with self._lock:
                        if ip not in self._processing_hosts:
                            self._processing_hosts.add(ip)
                            should_process = True
                    
                    if should_process:
                        self._executor.submit(self._process_host, ip, hostname)
                else:
                    pass

            # Aguardar 1 segundo entre ciclos (mais rápido com icmplib)
            elapsed = time.time() - start_time
            sleep_time = max(0.1, 1.0 - elapsed)
            time.sleep(sleep_time)

    def _dns_loop(self):
        """Loop dedicado para resolução de DNS em background."""
        while self._running:
            try:
                # Snapshot para não bloquear
                with self._lock:
                    hosts_to_resolve = list(self._hosts.keys())
                
                for ip in hosts_to_resolve:
                    if not self._running: break
                    
                    try:
                        # Verificar se precisamos resolver hostname (IP -> Hostname)
                        # Se não tiver hostname ou se for igual ao IP, tentar resolver
                        current_hostname = None
                        current_domain = None
                        with self._lock:
                            if ip in self._hosts:
                                current_hostname = self._hosts[ip].get('hostname')
                                current_domain = self._hosts[ip].get('domain')
                        
                        needs_resolution = (not current_hostname or current_hostname == ip or current_hostname == "Não detectado") or \
                                           (not current_domain or current_domain == "Não detectado")
                        
                        if needs_resolution:
                            try:
                                # Usar NetworkTools para resolver (ping -a, DNS, NetBIOS)
                                fqdn = self._tools.resolve_ip_and_hostname(ip)
                                
                                if fqdn:
                                    # Separar Hostname e Domínio
                                    parts = fqdn.split('.', 1)
                                    new_hostname = parts[0]
                                    new_domain = parts[1] if len(parts) > 1 else None
                                    
                                    with self._lock:
                                        if ip in self._hosts:
                                            self._hosts[ip]['hostname'] = new_hostname
                                            self._hosts[ip]['domain'] = new_domain
                                            logging.info(f"Reverse DNS Update: {ip} -> {new_hostname} ({new_domain})")
                                            
                                            if self._on_update_callback:
                                                try:
                                                    # Enviar update parcial
                                                    self._on_update_callback(ip, {
                                                        'hostname': new_hostname,
                                                        'domain': new_domain
                                                    })
                                                except:
                                                    pass
                            except Exception as e:
                                # logging.error(f"Error resolving {ip}: {e}")
                                pass

                        # Verificar se é hostname (Hostname -> IP) - Lógica original mantida mas otimizada
                        is_hostname_input = False
                        try:
                            ipaddress.ip_address(ip)
                        except ValueError:
                            is_hostname_input = True
                        
                        if is_hostname_input:
                            try:
                                resolved_ip = socket.gethostbyname(ip)
                                with self._lock:
                                    if ip in self._hosts:
                                        current_resolved = self._hosts[ip].get('ip')
                                        if resolved_ip != current_resolved:
                                            self._hosts[ip]['ip'] = resolved_ip
                                            logging.info(f"DNS Update: {ip} -> {resolved_ip}")
                                            
                                            if self._on_update_callback:
                                                try:
                                                    self._on_update_callback(ip, {'ip': resolved_ip})
                                                except:
                                                    pass
                            except:
                                pass
                    except:
                        pass
                    
                    # Pequena pausa entre resoluções para não saturar CPU/Rede
                    time.sleep(0.5) # Aumentado para 500ms para dar tempo ao sistema
                
                # Aguardar 10 segundos antes da próxima rodada completa de DNS
                time.sleep(10)
            except Exception as e:
                logging.error(f"Error in DNS loop: {e}")
                time.sleep(5)

    def _process_host(self, ip: str, hostname: str):
        """Processa um único host: ping (DNS já resolvido em background)."""
        if not self._running:
            with self._lock:
                self._processing_hosts.discard(ip)
            return

        try:
            current_ip = ip
            
            # Verificar estado atual (protegido)
            is_calibrating = False
            is_smart_offline = False
            
            with self._lock:
                if ip in self._hosts:
                    stats = self._hosts[ip]
                    is_calibrating = not stats.get('calibration_done', False)
                    is_smart_offline = stats.get('is_smart_offline', False)
                    
                    # Usar IP resolvido pelo background thread, se houver
                    if 'ip' in stats and stats['ip']:
                        current_ip = stats['ip']

            # Garantir que temos um IP válido para pingar
            ping_ip = current_ip
            resolution_failed = False
            
            # Validação rápida de IP (sem DNS) e detecção de WAN/LAN
            is_wan = False
            try:
                ip_obj = ipaddress.ip_address(ping_ip)
                # Considerar WAN se não for privado e não for loopback
                is_wan = not ip_obj.is_private and not ip_obj.is_loopback
            except ValueError:
                # Se ainda não é IP, é porque o DNS thread ainda não resolveu ou falhou
                # Tentamos usar o hostname direto no ping, mas marcamos que pode falhar
                pass

            # --- Executar Ping ---
            # Se estiver calibrando, usar Burst Mode (5 pings rápidos)
            ping_count = 5 if is_calibrating else 1
            
            if not resolution_failed:
                result = check_host_status_detailed(ping_ip, count=ping_count, is_wan=is_wan)
            else:
                # Se não conseguiu resolver, considera offline imediatamente
                result = {
                    'online': False, 
                    'latency': None,
                    'packet_loss': ping_count,
                    'packet_loss_pct': 100,
                    'total_packets': ping_count
                }

            # --- Atualizar MAC Address ---
            mac_address = None
            if result['online']:
                needs_mac = False
                with self._lock:
                    if ip in self._hosts:
                        current_mac = self._hosts[ip].get('mac')
                        if not current_mac:
                            needs_mac = True
                
                if needs_mac:
                    mac_address = mac_utils.resolve_mac_address(ping_ip)

            # --- Atualizar Estatísticas e Lógica Smart ---
            with self._lock:
                if ip not in self._hosts:
                    return
                
                stats = self._hosts[ip]
                
                # Atualizar contadores de sucesso/falha consecutivos
                if result['online']:
                    stats['consecutive_successes'] = stats.get('consecutive_successes', 0) + 1
                    stats['consecutive_failures'] = 0
                else:
                    stats['consecutive_failures'] = stats.get('consecutive_failures', 0) + 1
                    stats['consecutive_successes'] = 0

                # Verificar critérios de Smart Offline
                # > 50 pacotes E > 60% perda
                total_pkts = stats.get('packets_sent_history', 0)
                loss_pkts = stats.get('packets_lost_history', 0)
                loss_pct = 0
                if total_pkts > 0:
                    loss_pct = (loss_pkts / total_pkts) * 100
                
                if total_pkts > 50 and loss_pct > 60:
                    stats['is_smart_offline'] = True
                
                # Lógica de Recuperação (Smart Recovery)
                # Se estava offline e teve 10 sucessos consecutivos -> RESET
                if stats.get('is_smart_offline', False) and stats.get('consecutive_successes', 0) >= 10:
                    logging.info(f"Smart Recovery: Host {ip} recovered. Resetting stats.")
                    # Resetar stats mas manter IP e hostname
                    stats['latency'] = result['latency'] # Manter o atual
                    stats['average_latency'] = result['latency']
                    stats['packet_loss'] = 0
                    stats['packet_loss_pct'] = 0
                    stats['total_packets'] = ping_count # Começar com este ping
                    stats['packets_sent_history'] = ping_count
                    stats['packets_lost_history'] = 0
                    stats['latency_sum'] = (result['latency'] * ping_count) if result['latency'] else 0
                    stats['latency_count'] = ping_count
                    stats['calibration_done'] = False # Recalibrar se necessário
                    stats['consecutive_successes'] = 1
                    stats['consecutive_failures'] = 0
                    stats['is_smart_offline'] = False
                    stats['is_smart_offline'] = False
                    stats['online'] = True
                    # stats['last_checked'] = time.time()
                    from datetime import datetime
                    stats['last_checked'] = datetime.now().isoformat()
                    if mac_address: stats['mac'] = mac_address
                    # Add history point for recovery
                    if 'history' not in stats: stats['history'] = []
                    stats['history'].append({
                        'timestamp': time.time(),
                        'latency': result['latency'] if result['latency'] else 0,
                        'packet_loss': 0
                    })
                    if len(stats['history']) > 60: stats['history'].pop(0)
                    return 

                # Atualização Normal de Stats
                stats['online'] = result['online']
                if mac_address:
                    stats['mac'] = mac_address
                stats['latency'] = result['latency']
                # stats['last_checked'] = time.time()
                from datetime import datetime
                stats['last_checked'] = datetime.now().isoformat()
                
                stats['packets_sent_history'] += result['total_packets']
                
                # Lógica de Calibração
                if not stats.get('calibration_done', False):
                    # Se não tiver start_time (hosts antigos em memória), usa 0 para forçar calibração imediata
                    start_time = stats.get('monitoring_start_time', 0)
                    elapsed_monitoring = time.time() - start_time
                    
                    # Se usou burst (ping_count > 1) ou já tem pacotes suficientes, marca como calibrado
                    if ping_count > 1 or stats['packets_sent_history'] >= 5 or elapsed_monitoring > 5:
                        stats['calibration_done'] = True
                        
                        # Se foi burst, já temos dados suficientes para inicializar
                        stats['packets_lost_history'] += result['packet_loss']
                        if result['latency'] is not None:
                            # Assumindo que result['latency'] é a média do burst
                            stats['latency_sum'] += result['latency'] * result['total_packets']
                            stats['latency_count'] += result['total_packets']
                    else:
                        stats['packets_lost_history'] += result['packet_loss']
                        if result['latency'] is not None:
                            stats['latency_sum'] += result['latency']
                            stats['latency_count'] += 1
                else:
                    stats['packets_lost_history'] += result['packet_loss']
                    if result['latency'] is not None:
                        # Se result['total_packets'] > 1 (ex: mudou lógica futura), usar multiplicação
                        # Mas no fluxo normal ping_count é 1
                        stats['latency_sum'] += result['latency'] * result['total_packets']
                        stats['latency_count'] += result['total_packets']
                    
                    if stats['latency_count'] > 0:
                        stats['average_latency'] = stats['latency_sum'] / stats['latency_count']
                    else:
                        stats['average_latency'] = None
                
                stats['packet_loss'] = stats['packets_lost_history']
                stats['total_packets'] = stats['packets_sent_history']
                
                if stats['packets_sent_history'] > 0:
                    stats['packet_loss_pct'] = (stats['packets_lost_history'] / stats['packets_sent_history']) * 100
                else:
                    stats['packet_loss_pct'] = 0.0

                # Update History
                if 'history' not in stats: stats['history'] = []
                stats['history'].append({
                    'timestamp': time.time(),
                    'latency': result['latency'] if result['latency'] else 0,
                    'packet_loss': result['packet_loss']
                })
                # Keep last 60 points
                if len(stats['history']) > 60:
                    stats['history'].pop(0)

                # --- Check Ports ---
                ports = stats.get('ports', [])
                if ports:
                    ports_status = {}
                    for port in ports:
                        is_open = self._check_port(ping_ip, port)
                        ports_status[port] = is_open
                    stats['ports_status'] = ports_status

                # Notify callback about update
                if self._on_update_callback:
                    try:
                        self._on_update_callback(ip, stats.copy())
                    except Exception as e:
                        logging.error(f"Error in update callback: {e}")

        except Exception as e:
            logging.error(f"Erro ao processar host {ip}: {e}")
        finally:
            with self._lock:
                self._processing_hosts.discard(ip)

    def _check_port(self, ip, port, timeout=1):
        """Verifica se uma porta TCP específica está aberta."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, int(port)))
                return result == 0
        except:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Retorna as estatísticas atuais de todos os hosts."""
        with self._lock:
            return {ip: data.copy() for ip, data in self._hosts.items()}
