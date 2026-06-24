import threading
import time
import logging
import socket
import ipaddress
import os
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from .ping import check_host_status_detailed
from . import mac_utils
from .tools import NetworkTools

from src.core.host_manager import HostManager


# Tunable via env var for ops without a redeploy. Cap default at 64: balances
# parallelism vs. Windows handle / ping.exe spawn limits. Anything above ~128
# starts triggering "no more handles" in tight loops.
_DEFAULT_POOL_SIZE = int(os.environ.get("NT_MONITOR_POOL_SIZE", "64"))
_TICK_INTERVAL_S = 1.0
# How often the history sampler snapshots stats into host_metrics. 60s keeps the
# table small (~43k rows/host/month) while giving enough resolution for 24h/7d
# charts. Tunable for ops without a redeploy.
_METRICS_SAMPLE_INTERVAL_S = int(os.environ.get("NT_METRICS_SAMPLE_INTERVAL_S", "60"))


class HostMonitor:
    """Pings every monitored host roughly once per second using a shared pool.

    Previous design used one OS thread per host with its own 1s loop. That
    didn't scale: 100 hosts = 100 ping.exe spawns/s + 100 idle threads + GIL
    contention. Now a single scheduler thread enqueues N tasks per tick into
    a fixed-size ThreadPoolExecutor — thread count is bounded regardless of
    how many hosts the user adds. If a tick can't drain in 1s (overload) we
    skip and log instead of piling up backlog.
    """

    def __init__(self):
        self._hosts: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._pool: Optional[ThreadPoolExecutor] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Per-host in-flight guard: if last tick's ping didn't finish before the
        # next tick fires, skip this round for that host rather than queueing
        # duplicates that pile up under network pressure.
        self._inflight: set = set()

        self._last_resolution_times = {}
        self._tools = NetworkTools()
        self._host_manager = HostManager()

    def start_monitoring(self, hosts: List[Dict[str, Any]], on_update_callback=None):
        """Inicia o monitoramento para uma lista de hosts."""
        if self._running:
            self.update_hosts(hosts)
            return

        self._running = True
        self._on_update_callback = on_update_callback
        self._stop_event.clear()
        self._pool = ThreadPoolExecutor(
            max_workers=_DEFAULT_POOL_SIZE,
            thread_name_prefix="monitor-ping",
        )
        self.update_hosts(hosts)

        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="monitor-scheduler"
        )
        self._scheduler_thread.start()

        self._dns_thread = threading.Thread(target=self._dns_loop, daemon=True, name="monitor-dns")
        self._dns_thread.start()

        # History sampler: snapshots get_stats() periodically and batch-writes to
        # host_metrics. Separate thread so DB I/O never sits on the ping hot path.
        self._metrics_thread = threading.Thread(
            target=self._metrics_loop, daemon=True, name="monitor-metrics"
        )
        self._metrics_thread.start()

        logging.info(f"HostMonitor started with pool_size={_DEFAULT_POOL_SIZE}")

    def stop_monitoring(self):
        """Para todo o monitoramento."""
        self._running = False
        self._on_update_callback = None
        self._stop_event.set()

        with self._lock:
            self._hosts.clear()
            self._last_resolution_times.clear()
            self._inflight.clear()

        if self._pool:
            # Don't wait — tasks are short-lived; daemon threads die with the
            # process anyway. `wait=False` avoids blocking shutdown on a stuck
            # subprocess.run() inside ping.
            try:
                self._pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                logging.exception("HostMonitor: pool shutdown failed")
            self._pool = None

    def update_hosts(self, hosts: List[Dict[str, Any]]):
        """Sincroniza o conjunto de hosts monitorados.

        Não cria mais 1 thread por host — apenas atualiza o dicionário. O scheduler
        descobre IPs novos no próximo tick.
        """
        if not self._running:
            return

        current_ips = set()

        with self._lock:
            for host in hosts:
                ip = host.get('address')
                if not ip:
                    continue

                current_ips.add(ip)

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
                        'ip': ip,
                        'consecutive_successes': 0,
                        'consecutive_failures': 0,
                        'is_smart_offline': False,
                        'has_ever_been_online': False,
                        # ISO timestamp of the most recent online->offline transition.
                        # `None` until the host first goes down (or for hosts that
                        # never came up). Cleared on the offline->online transition.
                        'offline_since': None,
                        'history': [],
                        'ports': host.get('ports', []),
                        'ports_status': {},
                        'monitoring_start_time': time.time(),
                    }
                else:
                    self._hosts[ip]['monitoring'] = host.get('monitoring', True)
                    self._hosts[ip]['hostname'] = host.get('hostname')
                    self._hosts[ip]['ports'] = host.get('ports', [])

            # Remover hosts que não estão mais na lista
            ips_to_remove = [ip for ip in self._hosts if ip not in current_ips]
            for ip in ips_to_remove:
                del self._hosts[ip]
                if ip in self._last_resolution_times:
                    del self._last_resolution_times[ip]
                self._inflight.discard(ip)

    def _scheduler_loop(self):
        """Enfileira um ping por host a cada tick. Tick fixo de 1s.

        Se a fila do pool já tem trabalho para esse IP, pula esse tick para esse
        host — evita backlog quando um destino lento bloqueia o worker.
        """
        while self._running and not self._stop_event.is_set():
            tick_start = time.time()
            try:
                with self._lock:
                    targets = [
                        (ip, data.get('hostname'))
                        for ip, data in self._hosts.items()
                        if data.get('monitoring', True) and ip not in self._inflight
                    ]
                    for ip, _ in targets:
                        self._inflight.add(ip)

                if targets and self._pool:
                    for ip, hostname in targets:
                        self._pool.submit(self._ping_task, ip, hostname)
            except Exception:
                logging.exception("HostMonitor: scheduler tick failed")

            elapsed = time.time() - tick_start
            sleep_for = max(0.05, _TICK_INTERVAL_S - elapsed)
            self._stop_event.wait(sleep_for)

    def _ping_task(self, ip: str, hostname: Optional[str]):
        """Wrapper para a task no pool — chama _process_host e limpa o inflight."""
        try:
            self._process_host(ip, hostname)
        except Exception:
            logging.exception(f"HostMonitor: _process_host failed for {ip}")
        finally:
            with self._lock:
                self._inflight.discard(ip)

    def reset_host_stats(self, ip: str):
        """Reseta as estatísticas de ping para um host específico.

        Matches the host key case-insensitively. DB column `address` can drift
        in case (DNS reverse occasionally returns the hostname lowercase, and
        a save round-trip would persist that). When that happens, the route
        layer's case-insensitive lookup finds the host but the canonical
        address comes back in whichever case the DB has — which may differ
        from the case the monitor was originally seeded with. Without the
        normalization here, `if ip in self._hosts` would miss and reset
        would silently no-op.
        """
        with self._lock:
            actual_key = None
            if ip in self._hosts:
                actual_key = ip
            else:
                ip_lower = ip.lower() if isinstance(ip, str) else ip
                for k in self._hosts:
                    if isinstance(k, str) and k.lower() == ip_lower:
                        actual_key = k
                        break
            if actual_key is not None:
                stats = self._hosts[actual_key]
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
                stats['has_ever_been_online'] = False
                logging.info(f"Estatísticas resetadas para o host {ip}")

    @staticmethod
    def _resolve_hostname_multi_domain(hostname):
        """Forward-resolve a hostname trying each configured network's
        dns_server/domain before falling back to the system resolver.

        In a two-AD environment the same short hostname can exist in both
        domains; the system resolver picks whichever the machine's primary
        DNS knows. By trying every configured (dns_server, domain) pair we
        give the operator a deterministic answer per VLAN. First valid A
        record wins. Returns the IPv4 string or None.

        Best-effort: any failure to load settings just degrades to the plain
        system resolver, which is what the monitor did before.
        """
        from src.network import dns_resolver
        try:
            from api.routes.settings import load_settings
            settings = load_settings()
            networks = [n for n in (settings.networks or []) if n.enabled and n.dns_server]
        except Exception:
            networks = []

        for net in networks:
            try:
                ip = dns_resolver.resolve_hostname(
                    hostname, dns_server=net.dns_server, domain=net.domain
                )
                if ip:
                    return ip
            except Exception as e:
                logging.debug(f"multi-domain resolve via {net.dns_server} failed for {hostname}: {e}")

        # Fallback: system resolver (also handles the no-networks-configured case).
        try:
            return dns_resolver.resolve_hostname(hostname)
        except Exception as e:
            logging.debug(f"system resolve failed for {hostname}: {e}")
            return None

    def _resolve_one_host(self, ip):
        """Resolve reverse DNS, forward DNS (if input was a hostname) and MAC
        for a single host. Persists updates and fires the on_update callback.

        Designed to run from a thread pool — locks are scoped tightly so N
        resolutions overlap rather than serializing 2s/host of DNS lookup.
        """
        try:
            # --- Reverse DNS (IP -> hostname/domain) ---
            with self._lock:
                if ip not in self._hosts:
                    return
                current_hostname = self._hosts[ip].get('hostname')
                current_domain = self._hosts[ip].get('domain')

            needs_resolution = (
                (not current_hostname or current_hostname == ip or current_hostname == "Não detectado")
                or (not current_domain or current_domain == "Não detectado")
            )

            if needs_resolution:
                try:
                    fqdn = self._tools.resolve_ip_and_hostname(ip)
                    if fqdn:
                        parts = fqdn.split('.', 1)
                        new_hostname = parts[0]
                        new_domain = parts[1] if len(parts) > 1 else None

                        with self._lock:
                            if ip in self._hosts:
                                self._hosts[ip]['hostname'] = new_hostname
                                self._hosts[ip]['domain'] = new_domain
                                logging.info(f"Reverse DNS Update: {ip} -> {new_hostname} ({new_domain})")
                                callback = self._on_update_callback
                            else:
                                callback = None

                        if callback:
                            try:
                                callback(ip, {'hostname': new_hostname, 'domain': new_domain})
                            except Exception:
                                logging.exception(f"on_update_callback raised for {ip}")

                        self._host_manager.update_host_details(ip, hostname=new_hostname, domain=new_domain)
                except Exception:
                    logging.exception(f"reverse DNS failed for {ip}")

            # --- Forward DNS (hostname input -> IP), if applicable ---
            try:
                ipaddress.ip_address(ip)
                is_hostname_input = False
            except ValueError:
                is_hostname_input = True

            if is_hostname_input:
                try:
                    # Route through dns_resolver, not the system resolver. In a
                    # multi-domain setup the system resolver may pick the wrong
                    # domain when the same shortname exists in both ADs.
                    #
                    # For a hostname we don't yet know which VLAN it belongs to
                    # (no IP to _match_network against), so we try each
                    # configured network's dns_server/domain in turn, falling
                    # back to the system resolver. First answer wins. This is
                    # the multi-domain-aware path; before, the monitor always
                    # used the blind system resolver here.
                    from src.network import dns_resolver
                    resolved_ip = self._resolve_hostname_multi_domain(ip)
                    if not resolved_ip:
                        raise socket.gaierror(f"resolve_hostname returned None for {ip}")
                    with self._lock:
                        if ip in self._hosts:
                            current_resolved = self._hosts[ip].get('ip')
                            if resolved_ip != current_resolved:
                                self._hosts[ip]['ip'] = resolved_ip
                                logging.info(f"DNS Update: {ip} -> {resolved_ip}")
                                callback = self._on_update_callback
                            else:
                                callback = None
                        else:
                            callback = None
                    if callback:
                        try:
                            callback(ip, {'ip': resolved_ip})
                        except Exception:
                            logging.exception(f"on_update_callback raised for {ip}")
                    # Persistir o IPv4 resolvido na coluna `resolved_ip` do DB.
                    # Diferente do in-memory `_hosts[ip]['ip']` (que some quando
                    # o app reinicia), isto sobrevive restarts — então um host
                    # cadastrado pelo hostname já mostra o IP correto no card
                    # no boot seguinte, antes do monitor terminar o primeiro
                    # round de DNS.
                    try:
                        self._host_manager.update_resolved_ip(ip, resolved_ip)
                    except Exception:
                        logging.debug(f"update_resolved_ip failed for {ip}", exc_info=True)
                except Exception as _e:
                    # Forward-DNS failure is expected (host offline, DNS down,
                    # invalid hostname). Drop to debug so we have a breadcrumb
                    # without spamming the operator's errors.log every 5s/host.
                    logging.debug(f"forward DNS failed for {ip}: {_e}")

            # --- MAC Address Resolution (every ~5 min while online) ---
            needs_mac = False
            with self._lock:
                if ip in self._hosts:
                    current_mac = self._hosts[ip].get('mac')
                    is_online = self._hosts[ip].get('online', False)
                    last_mac_attempt = self._hosts[ip].get('last_mac_attempt', 0)
                    if not current_mac and is_online and (time.time() - last_mac_attempt > 300):
                        needs_mac = True
                        self._hosts[ip]['last_mac_attempt'] = time.time()

            if needs_mac:
                try:
                    mac_address = mac_utils.resolve_mac_address(ip)
                    if mac_address:
                        with self._lock:
                            if ip in self._hosts:
                                self._hosts[ip]['mac'] = mac_address
                        self._host_manager.update_host_details(ip, mac=mac_address)
                except Exception:
                    logging.exception(f"MAC resolution failed for {ip}")
        except Exception:
            logging.exception(f"_resolve_one_host failed for {ip}")

    def _dns_loop(self):
        """Loop dedicado para resolução de DNS / MAC em background.

        Anteriormente serial (~2s/host × N hosts era impraticável em rede
        ampla). Agora despacha as resoluções em paralelo via um
        ThreadPoolExecutor persistente — limitado a 16 workers para não
        exaurir file descriptors nem detonar o DNS server.

        Pool é criado uma vez e reutilizado a cada ciclo. Antes o pool era
        recriado a cada 5s dentro de um `with`, alocando/destruindo 16 OS
        threads continuamente — sob 100+ hosts isso era ~16 thread spawn/s
        gratuito.
        """
        from concurrent.futures import ThreadPoolExecutor
        dns_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="dns-resolve")
        try:
            while self._running:
                try:
                    with self._lock:
                        hosts_to_resolve = list(self._hosts.keys())

                    if hosts_to_resolve:
                        futures = [dns_pool.submit(self._resolve_one_host, ip) for ip in hosts_to_resolve]
                        for f in futures:
                            if not self._running:
                                break
                            try:
                                f.result(timeout=15)
                            except Exception as _e:
                                logging.debug(f"DNS resolution task raised: {_e}")

                    # Sleep antes da próxima rodada completa.
                    time.sleep(5)
                except Exception as e:
                    logging.error(f"Error in DNS loop: {e}")
                    time.sleep(5)
        finally:
            # Não esperar tasks pendentes — o app pode estar fechando.
            dns_pool.shutdown(wait=False, cancel_futures=True)

    def _process_host(self, ip: str, hostname: str):
        """Processa um único host: ping (DNS já resolvido em background)."""
        if not self._running:
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
                # OTIMIZAÇÃO: Não resolver nomes no loop principal para permitir uso do icmplib (rápido)
                # A resolução de nomes é feita pela thread _dns_loop em background
                # fast_mode=True pula TCP/ARP checks para garantir ciclo de 1s
                result = check_host_status_detailed(ping_ip, count=ping_count, is_wan=is_wan, resolve_names=False, fast_mode=True)
                
                # Se resolveu hostname, atualizar
                if result.get('resolved_hostname'):
                    fqdn = result['resolved_hostname']
                    parts = fqdn.split('.', 1)
                    new_hostname = parts[0]
                    new_domain = parts[1] if len(parts) > 1 else None
                    
                    with self._lock:
                        if ip in self._hosts:
                            self._hosts[ip]['hostname'] = new_hostname
                            if new_domain:
                                self._hosts[ip]['domain'] = new_domain
                    
                    # Persistir no banco de dados
                    self._host_manager.update_host_details(ip, hostname=new_hostname, domain=new_domain)
            else:
                # Se não conseguiu resolver, considera offline imediatamente
                result = {
                    'online': False, 
                    'latency': None,
                    'packet_loss': ping_count,
                    'packet_loss_pct': 100,
                    'total_packets': ping_count,
                    'resolved_hostname': None
                }

            # --- Atualizar MAC Address ---
            # REMOVIDO: Movido para _dns_loop para não bloquear o ping
            mac_address = None

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
                # Requer 2 sucessos consecutivos para evitar reset por falso positivo
                # isolado (icmplib em SOCK_DGRAM, ARP cache, ping a IP reciclado por outra
                # máquina, etc.). Antes era 1 — causava o card piscar entre "OFFLINE 96%"
                # e "ONLINE 0% 1pkt" sempre que um pacote sneak passava.
                was_offline_state = stats.get('is_smart_offline', False) or stats.get('packet_loss_pct', 0) > 60
                if result['online'] and was_offline_state and stats.get('consecutive_successes', 0) >= 2:
                    logging.info(f"Smart Recovery: Host {ip} recovered after 2+ consecutive pings. Resetting stats.")
                    # Resetar stats mas manter IP e hostname
                    stats['latency'] = result['latency'] # Manter o atual
                    stats['average_latency'] = result['latency']
                    stats['packet_loss'] = 0
                    stats['packet_loss_pct'] = 0
                    stats['total_packets'] = ping_count # Começar com este ping
                    stats['packets_sent_history'] = ping_count
                    stats['packets_lost_history'] = 0 # Reset lost history
                    stats['consecutive_failures'] = 0 # Reset failures
                    stats['online'] = True # Force online
                    stats['has_ever_been_online'] = True # Force ever online
                    stats['is_smart_offline'] = False # Reset smart offline flag
                    # Came back online — clear the "offline since" marker so the
                    # UI doesn't keep displaying a stale timestamp.
                    stats['offline_since'] = None

                    if 'history' not in stats: stats['history'] = []
                    stats['history'].append({
                        'timestamp': time.time(),
                        'latency': result['latency'] if result['latency'] else 0,
                        'packet_loss': 0
                    })
                    if len(stats['history']) > 60: stats['history'].pop(0)
                    return

                # Atualização Normal de Stats
                # `online` agora reflete o estado *consolidado*, não o último ping isolado.
                # Um único pacote que passa em um host com 96% de perda não deve pintar
                # o card de verde — manter coerência com o corpo "HOST OFFLINE".
                # Regra: online = último ping respondeu E não está em smart-offline E
                # (ou já é online estável, ou tem ≥2 sucessos consecutivos).
                if result['online']:
                    stats['has_ever_been_online'] = True

                last_ping_ok = bool(result['online'])
                in_smart_offline = stats.get('is_smart_offline', False)
                cons_ok = stats.get('consecutive_successes', 0)
                was_online = stats.get('online', False)
                # Estável: já estava online e respondeu agora -> mantém online
                # Recuperando: estava offline e tem ≥2 ok consecutivos -> online
                stats['online'] = last_ping_ok and not in_smart_offline and (was_online or cons_ok >= 2)

                # Track the online -> offline transition so the UI can show
                # "offline desde". We only stamp the moment the host *flips*
                # online -> offline; subsequent offline ticks leave the marker
                # alone so it points at the original drop. The marker is
                # cleared on the reverse transition below (and in Smart
                # Recovery above). `has_ever_been_online` gates the first
                # stamp — for a host that has never come up since we started
                # monitoring, "offline desde X" would be misleading.
                from datetime import datetime as _dt
                if was_online and not stats['online'] and stats.get('has_ever_been_online'):
                    stats['offline_since'] = _dt.now().isoformat()
                elif stats['online']:
                    if stats.get('offline_since'):
                        stats['offline_since'] = None
                
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

                # Snapshot stats + callback BEFORE releasing the lock, then
                # invoke the callback OUTSIDE the lock. The callback does DB
                # writes and a WebSocket broadcast; holding `_lock` through that
                # serialized every host's tick behind whichever one happened to
                # be flushing — under load this drifted ticks well past 1s.
                stats_snapshot = stats.copy()
                callback = self._on_update_callback

            # Outside the lock now.
            if callback:
                try:
                    callback(ip, stats_snapshot)
                except Exception as e:
                    logging.error(f"Error in update callback: {e}")

        except Exception as e:
            logging.error(f"Erro ao processar host {ip}: {e}")

    def _check_port(self, ip, port, timeout=0.2):
        """Verifica se uma porta TCP específica está aberta."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, int(port)))
                return result == 0
        except Exception as e:
            logging.debug(f"_check_port {ip}:{port} failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Retorna as estatísticas atuais de todos os hosts."""
        with self._lock:
            return {ip: data.copy() for ip, data in self._hosts.items()}

    def _metrics_loop(self):
        """Snapshot periódico das stats → host_metrics (histórico persistente).

        Roda num thread próprio para que a escrita no SQLite nunca fique no
        caminho crítico do ping. Amostra a cada _METRICS_SAMPLE_INTERVAL_S e
        faz pruning da retenção uma vez por hora. Best-effort: qualquer falha é
        logada e o loop continua — histórico é secundário ao monitoramento.
        """
        from src.core.database import db

        last_prune = 0.0
        # Skip the very first interval so calibration (first ping round) settles
        # before we record — avoids a misleading "offline" sample at t=0.
        self._stop_event.wait(_METRICS_SAMPLE_INTERVAL_S)

        while self._running and not self._stop_event.is_set():
            try:
                now = int(time.time())
                snapshot = self.get_stats()
                rows = []
                for ip, data in snapshot.items():
                    if not data.get('monitoring', True):
                        continue
                    # Don't record hosts still calibrating — their status isn't
                    # meaningful yet.
                    if not data.get('calibration_done'):
                        continue
                    online = bool(data.get('online'))
                    rows.append({
                        'address': ip,
                        'ts': now,
                        'online': online,
                        # Latency only meaningful when up.
                        'latency': data.get('latency') if online else None,
                        'packet_loss_pct': data.get('packet_loss_pct', 0),
                    })
                if rows:
                    db.insert_metrics_batch(rows)

                # Prune at most once an hour.
                if time.time() - last_prune > 3600:
                    db.prune_metrics()
                    last_prune = time.time()
            except Exception:
                logging.exception("HostMonitor: metrics sampler tick failed")

            self._stop_event.wait(_METRICS_SAMPLE_INTERVAL_S)
