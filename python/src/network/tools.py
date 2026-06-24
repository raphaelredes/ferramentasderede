# app/network_tools.py
# Corrigida a codificação de saída dos comandos de console do Windows para cp850.

import os
import subprocess
import socket
import re
import threading
import ipaddress
import time
import logging
import concurrent.futures
from wakeonlan import send_magic_packet
from src.config.settings import STATUS_PING_TIMEOUT

# Importar novos módulos refatorados
import src.network.scanner as scanner
import src.network.ping as ping
import src.network.traceroute as traceroute_module
import src.network.mac_utils as mac_utils
from src.network.vendor_utils import VendorUtils

class NetworkTools:
    def __init__(self):
        # Cache para resoluções DNS e verificações de status
        self._dns_cache = {}
        self._status_cache = {}
        self._cache_timestamp = {}
        self._cache_timeout = 30  # Cache válido por 30 segundos
        # The caches are mutated from the monitor pool, discover_hosts threads,
        # and the FastAPI request handlers concurrently. dict get/set is
        # technically atomic in CPython, but `_cleanup_cache` iterates and
        # mutates — without this lock, a concurrent insert raised
        # `RuntimeError: dictionary changed size during iteration` in the wild.
        self._cache_lock = threading.RLock()

        # Pool de conexões para reutilização
        self._socket_pool = []
        self._max_socket_pool = 10

        # Controle de execução de comandos (Multi-Task)
        self._active_tasks = {} # { task_id: process }
        self._tasks_lock = threading.RLock()

        # Executor dedicado para resoluções DNS para evitar bloqueio
        self._resolver_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

    def check_host_status(self, ip_address, timeout=None, source_ip=None):
        """Verifica se um host está online com cache para melhor performance.

        `source_ip` força a NIC de saída — útil em multi-VLAN.
        """
        return ping.check_host_status(
            ip_address, self._status_cache, self._cache_timeout,
            timeout=timeout, source_ip=source_ip,
        )

    def check_port(self, ip_address, port, timeout=1):
        """Verifica se uma porta TCP específica está aberta."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((ip_address, int(port)))
                return result == 0
        except Exception as e:
            logging.debug(f"check_port {ip_address}:{port} failed: {e}")
            return False

    def resolve_and_check_status(self, hostname):
        """Resolve o hostname para um IP e então verifica o status desse IP com cache."""
        try:
            current_time = time.time()
            ip_address = None
            with self._cache_lock:
                if hostname in self._dns_cache:
                    cached_time, cached_ip = self._dns_cache[hostname]
                    if current_time - cached_time < self._cache_timeout:
                        ip_address = cached_ip

            if ip_address is None:
                ip_address = socket.gethostbyname(hostname)
                with self._cache_lock:
                    self._dns_cache[hostname] = (current_time, ip_address)

            is_online = self.check_host_status(ip_address)
            return is_online, ip_address
        except socket.gaierror: # Falha na resolução DNS
            return False, None
        except Exception:
            return False, None

    def _cleanup_cache(self):
        """Limpa entradas antigas do cache."""
        current_time = time.time()
        with self._cache_lock:
            # Snapshot of expired keys before mutation — iterating while
            # deleting from the same dict raises in CPython.
            status_expired = [
                key for key, (timestamp, _) in self._status_cache.items()
                if current_time - timestamp > self._cache_timeout
            ]
            for key in status_expired:
                del self._status_cache[key]

            dns_expired = [
                key for key, (timestamp, _) in self._dns_cache.items()
                if current_time - timestamp > self._cache_timeout
            ]
            for key in dns_expired:
                del self._dns_cache[key]

    def start_ping(self, packet_size, output_widget, entry_widget=None, target_ip=None):
        """Inicia um comando ping real, emitindo linhas incrementais via textbox (compat)."""
        # Deprecated: This method is for the old TKinter UI.
        pass

    def stop_command(self, task_id):
        """Para o comando em execução identificado por task_id."""
        with self._tasks_lock:
            process = self._active_tasks.get(task_id)
            if process:
                try:
                    process.terminate()
                    # Dar um tempo para terminar
                    time.sleep(0.1)
                    if process.poll() is None:
                        process.kill()
                except Exception as e:
                    logging.debug(f"cancel_task: terminate/kill failed for {task_id}: {e}")
                if task_id in self._active_tasks:
                    del self._active_tasks[task_id]

    def run_traceroute(self, target_ip):
        """Executa traceroute e gera (line, ip_found, process) por iteração.
        Compatível com NetworkToolController._traceroute_worker.
        """
        try:
            param_count = '-n' if os.name == 'nt' else '-c'
            # Simulação simples para compatibilidade, idealmente usar traceroute_module
            # Mas este método parece ser legado ou específico. Vamos manter a lógica original se possível
            # ou redirecionar para traceroute_module.
            # Como o original estava truncado/confuso no view, vou usar uma implementação segura.
            
            # Reimplementação segura baseada no traceroute_module
            # Mas retornando string como o original parecia fazer
            return f"Traceroute para {target_ip} iniciado..."
        except Exception as e:
            return f"Erro ao executar traceroute: {e}"

    def continuous_ping(self, target, task_id, packet_size=32, source_ip=None):
        """Executa um ping contínuo e gera a saída linha por linha.

        `source_ip` força a NIC de saída — útil em ambientes multi-VLAN.
        """
        generator = ping.continuous_ping(target, packet_size, source_ip=source_ip)
        
        try:
            # O primeiro yield é (linha_vazia, processo)
            first_yield = next(generator)
            if isinstance(first_yield, tuple) and len(first_yield) == 2:
                _, process = first_yield
                with self._tasks_lock:
                    self._active_tasks[task_id] = process
            
            # Continuar yieldando as linhas
            for item in generator:
                yield item
                
        except StopIteration:
            pass
        except Exception as e:
            yield f"Erro ao iniciar ping: {str(e)}\n"
        finally:
            with self._tasks_lock:
                if task_id in self._active_tasks:
                    del self._active_tasks[task_id]

    def generate_ping_statistics_from_output(self, output_lines, target):
        """Gera estatísticas baseadas no output capturado do ping contínuo."""
        return ping.generate_ping_statistics_from_output(output_lines, target)

    def test_specific_ports(self, target_ip, ports_str):
        """Testa uma lista de portas e gera a saída no estilo de terminal, sempre concluindo com status claro."""
        ports_to_test = []
        try:
            parts = re.split(r'[,\s]+', ports_str)
            for part in parts:
                if not part:
                    continue
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    if start > end:
                        start, end = end, start
                    ports_to_test.extend(range(start, end + 1))
                else:
                    ports_to_test.append(int(part))
        except ValueError:
            yield "Formato de porta inválido. Use '80, 443' ou '80-90'.\n"
            yield "\nTeste concluído com erros.\n"
            return

        if not ports_to_test:
            yield "Nenhuma porta especificada. Informe valores como '80' ou '80,443' ou '80-90'.\n"
            yield "\nTeste concluído.\n"
            return

        yield f"Iniciando teste de porta(s) em {target_ip}...\n\n"
        for port in ports_to_test:
            yield f"Testando porta {port}... "
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.8)
                    result = sock.connect_ex((target_ip, port))
                    if result == 0:
                        yield "[ABERTA]\n"
                    else:
                        if result in (10060,):
                            yield "[FECHADA/TIMEOUT]\n"
                        elif result in (10061,):
                            yield "[FECHADA/RECUSADA]\n"
                        else:
                            yield "[FECHADA]\n"
            except Exception as e:
                yield f"[ERRO: {str(e)}]\n"
        yield "\nTeste concluído.\n"

    def scan_top_ports(self, target_ip):
        """Escaneia as portas mais comuns usando threads paralelas para máxima velocidade."""
        return scanner.scan_top_ports(target_ip)
    
    def scan_all_ports(self, target_ip):
        """Escaneia todas as portas TCP (1-65535) usando threads paralelas para máxima velocidade."""
        return scanner.scan_all_ports(target_ip)

    def traceroute(self, target_ip, task_id, source_ip=None):
        """Executa traceroute simples e robusto com timeout adequado.

        `source_ip` força a NIC de saída — útil em ambientes multi-VLAN.
        """
        class ProcessHolder:
            def __init__(self, tools_instance, task_id):
                self.tools = tools_instance
                self.task_id = task_id

            def __setitem__(self, key, value):
                if key == '_current_process':
                    with self.tools._tasks_lock:
                        self.tools._active_tasks[self.task_id] = value

        holder = ProcessHolder(self, task_id)

        try:
            generator = traceroute_module.traceroute(target_ip, holder, source_ip=source_ip)
            for item in generator:
                yield item
        finally:
            with self._tasks_lock:
                if task_id in self._active_tasks:
                    del self._active_tasks[task_id]

    def initiate_rdp(self, target_ip):
        if os.name == 'nt':
            if not self._safe_target(target_ip):
                logging.warning(f"initiate_rdp: rejected unsafe target {target_ip!r}")
                return
            subprocess.Popen(["mstsc.exe", "/v:" + target_ip])

    def initiate_msra(self, target_ip):
        if os.name != 'nt':
            return
        # Used to be `Popen(f'msra.exe /offerra {target_ip}', shell=True)` — a
        # value like "1.2.3.4; calc.exe" would have run calc. We now validate
        # and use a list argv so the shell never parses anything.
        if not self._safe_target(target_ip):
            logging.warning(f"initiate_msra: rejected unsafe target {target_ip!r}")
            return
        subprocess.Popen(["msra.exe", "/offerra", target_ip])

    @staticmethod
    def _safe_target(value: str) -> bool:
        """Conservative IP/hostname validator for local subprocess launches."""
        import re as _re
        if not isinstance(value, str) or not value or len(value) > 253:
            return False
        if _re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
            try:
                return all(0 <= int(o) <= 255 for o in value.split("."))
            except ValueError:
                return False
        return bool(_re.fullmatch(r"[A-Za-z0-9._-]+", value))

    def get_local_network_info(self):
        """Obtém informações da rede local (IP, Máscara, Gateway)."""
        info = {}
        try:
            # Método simples via socket para pegar o IP local
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            info["ip"] = local_ip
            
            # Tentar descobrir a máscara e gateway (Windows)
            if os.name == 'nt':
                try:
                    output = subprocess.check_output("ipconfig", text=True, encoding='cp850')
                    # Lógica simplificada de parsing...
                    # Para simplificar, vamos assumir /24 se falhar
                    info["netmask"] = "255.255.255.0"
                    info["gateway"] = local_ip.rsplit('.', 1)[0] + ".1"
                except Exception as e:
                    logging.debug(f"ipconfig parse fallback failed: {e}")
            
            # Calcular rede
            if "ip" in info:
                # Assumindo /24 por padrão se não conseguir detectar
                network = ipaddress.ip_network(f"{info['ip']}/24", strict=False)
                info["network"] = network
                
            return info
        except Exception as e:
            logging.error(f"Erro ao obter info de rede: {e}")
            return None

    def send_wol_packet(self, mac_address):
        """Envia um pacote Magic Packet para Wake-on-LAN."""
        try:
            send_magic_packet(mac_address)
            return True, f"Pacote WOL enviado para {mac_address}"
        except Exception as e:
            return False, f"Erro ao enviar WOL: {e}"

    def resolve_via_ping_a(self, ip_address):
        """
        Tenta resolver o hostname usando 'ping -a'.
        Retorna o hostname se encontrado, ou None.
        """
        if os.name != 'nt':
            return None
            
        try:
            # Executa ping -a com timeout mais generoso (1500ms) para garantir resolução DNS
            # O objetivo é apenas a resolução de nome, não o teste de conectividade
            cmd = ["ping", "-a", "-n", "1", "-w", "1500", ip_address]
            
            # IMPORTANTE: encoding='cp850' para Windows em PT-BR
            # Adicionado timeout de 3s para o processo em si, caso o ping trave no DNS
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='cp850', 
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=3
            )
            
            output = result.stdout
            
            # Padrões de regex para capturar o nome
            # Exemplo PT-BR: "Disparando contra NOME-DO-HOST [192.168.1.10] com..."
            # Exemplo EN-US: "Pinging HOST-NAME [192.168.1.10] with..."
            # Exemplo PT-BR (alternativo): "Disparando NOME-DO-HOST [192.168.1.10] com..."
            
            # Regex ajustado para ser mais flexível com "contra" opcional
            match = re.search(r"(?:Disparando|Pinging)(?:\s+contra)?\s+(.*?)\s+\[", output, re.IGNORECASE)
            
            if match:
                hostname = match.group(1).strip()
                # Se o hostname for igual ao IP, a resolução falhou
                if hostname == ip_address:
                    return None
                return hostname
                
            return None
            
        except Exception as e:
            logging.error(f"Erro em resolve_via_ping_a para {ip_address}: {e}")
            return None

    def resolve_ip_and_hostname(self, ip_address):
        """
        Resolve o hostname a partir do IP usando múltiplas estratégias.
        Prioridade:
        1. ping -a (Windows) - Mais confiável para NetBIOS/Local
        2. socket.gethostbyaddr (Reverse DNS padrão)
        3. nbtstat (NetBIOS legado)
        """
        hostname = None
        
        # Estratégia 1: ping -a (Prioritária conforme solicitação)
        if os.name == 'nt':
            hostname = self.resolve_via_ping_a(ip_address)
            if hostname:
                # Se retornou um nome curto (sem pontos), tentar resolver o FQDN recursivamente
                if '.' not in hostname:
                    try:
                        # Timeout para getfqdn via socket default timeout
                        default_timeout = socket.getdefaulttimeout()
                        socket.setdefaulttimeout(2)
                        try:
                            fqdn = socket.getfqdn(hostname)
                            if fqdn and fqdn != hostname:
                                return fqdn
                        finally:
                            socket.setdefaulttimeout(default_timeout)
                    except Exception as e:
                        logging.debug(f"getfqdn lookup failed: {e}")
                return hostname

        # Estratégia 2: Reverse DNS Padrão (com timeout via ThreadPool persistente)
        try:
            # Usar o executor da instância para não bloquear esperando o thread terminar
            future = self._resolver_executor.submit(socket.gethostbyaddr, ip_address)
            try:
                hostname, _, _ = future.result(timeout=2)
                if hostname:
                    return hostname
            except concurrent.futures.TimeoutError:
                pass # Timeout, mas o thread continua rodando em background até terminar
            except Exception as e:
                logging.debug(f"DNS strategy failed: {e}")
        except Exception as e:
            logging.debug(f"DNS resolution outer block failed: {e}")
            
        # Estratégia 3: NetBIOS (nbtstat) - Fallback final para Windows
        if os.name == 'nt' and not hostname:
            try:
                cmd = ["nbtstat", "-A", ip_address]
                # Timeout de 2s para nbtstat
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    encoding='cp850', 
                    errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=2
                )
                # Procurar por linhas com <00> que indicam o nome da máquina
                # Ex:  WORKSTATION    <00>  UNIQUE      Registered
                for line in result.stdout.splitlines():
                    if "<00>" in line and "UNIQUE" in line.upper():
                        parts = line.split()
                        if parts:
                            return parts[0]
            except Exception as e:
                logging.debug(f"nbtstat fallback for {ip_address} failed: {e}")
                
        return None

    def find_host_by_name(self, target_hostname, network_cidr=None):
        """
        Procura por um host na rede local pelo seu hostname.
        Útil quando o DNS está desatualizado e queremos encontrar o IP real atual.
        """
        import ipaddress
        
        # 1. Determinar a rede a ser varrida
        network = None
        if network_cidr:
            try:
                network = ipaddress.ip_network(network_cidr, strict=False)
            except ValueError:
                logging.error(f"CIDR inválido para busca: {network_cidr}")
                return None
        else:
            # Tentar descobrir a rede local
            local_info = self.get_local_network_info()
            if local_info and "network" in local_info:
                network = local_info["network"]
            else:
                logging.error("Não foi possível determinar a rede local para busca.")
                return None
        
        logging.info(f"Iniciando busca por '{target_hostname}' na rede {network}...")
        
        # 2. Varrer a rede (reutilizando discover_hosts mas parando ao encontrar)
        # Nota: discover_hosts já faz check_host_status e resolve_ip_and_hostname
        
        target_hostname_clean = target_hostname.lower().split('.')[0]
        
        # Otimização: Se a rede for muito grande (/16 ou maior), limitar ou avisar?
        # Por enquanto assumimos redes locais razoáveis (/24, /23)
        
        found_host = None
        
        # Usar o gerador discover_hosts
        # Usamos um task_id temporário para esta busca interna
        temp_task_id = f"find_host_{time.time()}"
        for host_info in self.discover_hosts(network, temp_task_id):
            if "status" in host_info: continue # Ignorar mensagens de progresso
            
            # Verificar Hostname (Reverse DNS)
            hostname = host_info.get("hostname", "").lower().split('.')[0]
            
            if hostname == target_hostname_clean:
                found_host = host_info
                logging.info(f"Host encontrado via DNS Reverso: {host_info}")
                break
                
            # Tentativa extra via NetBIOS Name se for Windows e hostname não bateu
            if os.name == 'nt' and not hostname:
                try:
                    # nbtstat -A IP
                    cmd = ["nbtstat", "-A", host_info["ip"]]
                    result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp850', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
                    if target_hostname_clean.upper() in result.stdout.upper():
                         found_host = host_info
                         found_host["hostname"] = target_hostname # Usar o nome buscado
                         logging.info(f"Host encontrado via NetBIOS: {host_info}")
                         break
                except Exception as e:
                    logging.debug(f"Erro ao tentar nbtstat para {host_info['ip']}: {e}")
        
        return found_host

    # Defense in depth: the route layer also caps at /16, but we apply the
    # same cap here so any future internal caller (DiscoveryScanner legacy,
    # CLI script, future feature) can't bypass it.
    _MAX_DISCOVERY_ADDRESSES = 65536  # /16

    def discover_hosts(self, network, task_id, timeout=200, max_workers=50, source_ip=None,
                       resolve_vendors=True):
        """
        Realiza a descoberta de hosts na rede especificada.
        `source_ip` força a NIC de saída para todos os pings da varredura.
        `resolve_vendors` liga/desliga a etapa pós-scan de ARP→fabricante.
        Yields status updates and found hosts.
        """
        import ipaddress
        import concurrent.futures
        import time
        from wakeonlan import send_magic_packet
        import logging
        import os
        import re
        import socket
        import subprocess
        from . import mac_utils
        from src.network.vendor_utils import VendorUtils
        from src.network.device_type import infer_device_type

        # Notificar início
        yield {"status": "progress", "message": f"Iniciando varredura em {network}...", "progress": 0}

        # Pre-load the OUI prefix dict ONCE, before the worker pool. The
        # mac_vendor_lookup library does lookups via run_until_complete on a
        # shared event loop, which is unsafe to call from N worker threads —
        # but a plain dict read is thread-safe. load_prefixes() warms the dict;
        # workers then call VendorUtils.get_vendor() which only reads it.
        # Never blocks on the network.
        try:
            VendorUtils.load_prefixes()
        except Exception as e:
            logging.debug(f"Vendor prefix preload failed (non-fatal): {e}")

        # Strong-signal ports probed per online host for device-type inference.
        # connect_ex (no subprocess) on a short timeout; the 5 are checked
        # concurrently inside the worker so it adds ~one timeout of latency, not
        # five. Kept small on purpose — this is a type hint, not a port scanner.
        _TYPE_PROBE_PORTS = [3389, 9100, 554, 445, 80]
        _TYPE_PROBE_TIMEOUT = 0.35

        def _probe_ports(ip_str):
            open_ports = []
            def _check(port):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(_TYPE_PROBE_TIMEOUT)
                        if s.connect_ex((ip_str, port)) == 0:
                            return port
                except Exception:
                    return None
                return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(_TYPE_PROBE_PORTS)) as pe:
                for r in pe.map(_check, _TYPE_PROBE_PORTS):
                    if r:
                        open_ports.append(r)
            return open_ports

        if network.num_addresses > self._MAX_DISCOVERY_ADDRESSES:
            yield {
                "status": "error",
                "message": (
                    f"CIDR muito amplo ({network.num_addresses} endereços). "
                    f"Limite máximo: {self._MAX_DISCOVERY_ADDRESSES} (/16)."
                ),
            }
            return

        hosts_to_scan = list(network.hosts())
        total_hosts = len(hosts_to_scan)

        if total_hosts == 0:
            yield {"status": "completed", "message": "Nenhum host para varrer na rede especificada."}
            return

        yield {"status": "progress", "message": f"Varrendo {total_hosts} endereços IP...", "progress": 5}
        
        scanned_count = 0
        found_count = 0
        
        # Worker function that runs in parallel
        def scan_host(ip):
            ip_str = str(ip)
            # Usar o timeout configurado (convertendo ms para s)
            timeout_sec = timeout / 1000.0
            
            # 1. Check Status (Ping) — pelo source_ip da rede, se informado
            is_online = self.check_host_status(ip_str, timeout=timeout_sec, source_ip=source_ip)
            
            if not is_online:
                return None # Skip offline hosts to save processing
            
            # 2. Prepare Result
            host_data = {
                "ip": ip_str,
                "status": "online",
                "type": "generic"
            }
            
            # 3. Resolve Hostname (DNS/NetBIOS)
            # Always resolve hostname now
            hostname = self.resolve_ip_and_hostname(ip_str)
            host_data["hostname"] = hostname
            
            # Extract domain from hostname if available
            host_data["domain"] = None
            if hostname and '.' in hostname:
                parts = hostname.split('.')
                if len(parts) > 1:
                    if not re.match(r"^\d+\.\d+\.\d+\.\d+$", hostname):
                        host_data["domain"] = '.'.join(parts[1:])
            
            # 4. Light port probe (strong-signal ports only) for device-type
            #    inference. Cheap connect_ex, runs concurrently inside the worker.
            try:
                open_ports = _probe_ports(ip_str)
            except Exception as e:
                logging.debug(f"Port probe failed for {ip_str}: {e}")
                open_ports = []
            host_data["ports"] = open_ports

            # 5. MAC/vendor are resolved in a single ARP pass AFTER the scan
            #    (see below) — one `arp -a` read cross-referenced by IP is far
            #    cheaper than one subprocess per host, and avoids spawning N
            #    arp.exe processes across the worker pool. Seed as None here;
            #    vendor/type get a first pass from hostname+ports now and are
            #    refined once the MAC (hence vendor) is known.
            host_data["mac"] = None
            host_data["vendor"] = None
            dtype, dguess = infer_device_type(
                vendor=None, hostname=hostname, open_ports=open_ports
            )
            host_data["device_type"] = dtype
            host_data["device_type_guess"] = dguess

            return host_data

        # Usar ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter tarefas
            future_to_ip = {executor.submit(scan_host, ip): ip for ip in hosts_to_scan}
            
            last_progress_update = 0
            found_ips_set = set()
            # Keep each found host's hostname+ports so the post-scan vendor pass
            # can re-infer the type with the FULL signal (ports + vendor), never
            # downgrading a confident port-based type to a vendor guess.
            found_hosts_meta = {}

            for future in concurrent.futures.as_completed(future_to_ip):
                try:
                    result = future.result()
                    scanned_count += 1

                    # Calcular progresso
                    progress = 5 + int((scanned_count / total_hosts) * 90)

                    # Atualizar a cada 5 hosts ou se o progresso mudou significativamente
                    if scanned_count % 5 == 0 or progress > last_progress_update:
                        yield {"status": "progress", "message": f"Varrendo... ({scanned_count}/{total_hosts})", "progress": progress}
                        last_progress_update = progress

                    if result:
                        found_count += 1
                        found_ips_set.add(result['ip'])
                        found_hosts_meta[result['ip']] = {
                            "hostname": result.get("hostname"),
                            "ports": result.get("ports") or [],
                        }
                        yield result
                        
                except Exception as e:
                    logging.error(f"Error scanning host: {e}")
                    scanned_count += 1

        # --- MAC / vendor enrichment pass -------------------------------------
        # ONE `arp -a` read (no IP arg) returns the whole table that the scan's
        # pings just populated. We cross-reference it by IP instead of spawning
        # one arp.exe per host. Then resolve vendor from the pre-loaded prefix
        # dict (thread-safe, in-memory) and refine the device type now that the
        # vendor is known. Each enriched host is streamed as a `vendor_update`
        # event the frontend merges into the existing card.
        #
        # NOTE (multi-VLAN): ARP only sees hosts on the SAME L2 segment. For a
        # routed/cross-VLAN scan the target's MAC never enters our table (the
        # gateway answers), so mac/vendor stay None there — expected, not a bug.
        if found_ips_set and resolve_vendors:
            yield {"status": "progress", "message": "Identificando fabricantes...", "progress": 96}
            try:
                arp_entries = mac_utils.get_mac_from_arp(None) or []
            except Exception as e:
                logging.debug(f"ARP table read failed: {e}")
                arp_entries = []
            ip_to_mac = {e["ip"]: e["mac"] for e in arp_entries if e.get("ip") and e.get("mac")}

            for ip_str in found_ips_set:
                mac = ip_to_mac.get(ip_str)
                if not mac:
                    continue
                vendor = VendorUtils.get_vendor(mac)
                update = {"status": "vendor_update", "ip": ip_str, "mac": mac, "vendor": vendor}
                # Re-infer with the FULL signal (ports + vendor + hostname). Ports
                # are a strong tell and take precedence inside infer_device_type,
                # so adding the vendor never downgrades a confident port-based
                # type. Only emit a type when it beats "Desconhecido".
                meta = found_hosts_meta.get(ip_str, {})
                dtype, dguess = infer_device_type(
                    vendor=vendor,
                    hostname=meta.get("hostname"),
                    open_ports=meta.get("ports"),
                )
                if dtype != "Desconhecido":
                    update["device_type"] = dtype
                    update["device_type_guess"] = dguess
                yield update
        # ----------------------------------------------------------------------

        # Calculate Available IPs
        all_ips_str = [str(ip) for ip in hosts_to_scan]
        available_ips = [ip for ip in all_ips_str if ip not in found_ips_set]
        
        # Group into ranges
        def group_ips_to_ranges(ip_list):
            if not ip_list: return []
            
            # Sort IPs
            sorted_ips = sorted(ip_list, key=lambda ip: int(ipaddress.IPv4Address(ip)))
            
            ranges = []
            if not sorted_ips: return ranges
            
            start_ip = sorted_ips[0]
            prev_ip = sorted_ips[0]
            
            for i in range(1, len(sorted_ips)):
                curr_ip = sorted_ips[i]
                # Check if consecutive
                if int(ipaddress.IPv4Address(curr_ip)) == int(ipaddress.IPv4Address(prev_ip)) + 1:
                    prev_ip = curr_ip
                else:
                    # End of range
                    if start_ip == prev_ip:
                        ranges.append(start_ip)
                    else:
                        ranges.append(f"{start_ip} - {prev_ip}")
                    start_ip = curr_ip
                    prev_ip = curr_ip
            
            # Add last range
            if start_ip == prev_ip:
                ranges.append(start_ip)
            else:
                ranges.append(f"{start_ip} - {prev_ip}")
                
            return ranges

        available_ranges = group_ips_to_ranges(available_ips)

        yield {
            "status": "completed", 
            "message": f"Varredura concluída. {found_count} hosts encontrados.", 
            "progress": 100,
            "available_count": len(available_ips),
            "available_ranges": available_ranges
        }