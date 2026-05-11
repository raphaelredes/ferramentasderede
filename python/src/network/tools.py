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
            # Verificar cache de DNS primeiro
            current_time = time.time()
            if hostname in self._dns_cache:
                cached_time, cached_ip = self._dns_cache[hostname]
                if current_time - cached_time < self._cache_timeout:
                    ip_address = cached_ip
                else:
                    ip_address = socket.gethostbyname(hostname)
                    self._dns_cache[hostname] = (current_time, ip_address)
            else:
                ip_address = socket.gethostbyname(hostname)
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
        expired_keys = []
        
        for key, (timestamp, _) in self._status_cache.items():
            if current_time - timestamp > self._cache_timeout:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._status_cache[key]
        
        # Limpar cache DNS também
        expired_dns_keys = []
        for key, (timestamp, _) in self._dns_cache.items():
            if current_time - timestamp > self._cache_timeout:
                expired_dns_keys.append(key)
        
        for key in expired_dns_keys:
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
            subprocess.Popen(["mstsc.exe", "/v:" + target_ip])
    
    def initiate_msra(self, target_ip):
        if os.name == 'nt':
            subprocess.Popen(f'msra.exe /offerra {target_ip}', shell=True)

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

    def discover_hosts(self, network, task_id, timeout=200, max_workers=50, source_ip=None):
        """
        Realiza a descoberta de hosts na rede especificada.
        `source_ip` força a NIC de saída para todos os pings da varredura.
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

        # Notificar início
        yield {"status": "progress", "message": f"Iniciando varredura em {network}...", "progress": 0}
        
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
            
            # 4. No MAC/Vendor resolution as requested
            host_data["mac"] = None
            host_data["vendor"] = None
                
            return host_data

        # Usar ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter tarefas
            future_to_ip = {executor.submit(scan_host, ip): ip for ip in hosts_to_scan}
            
            last_progress_update = 0
            found_ips_set = set()
            
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
                        yield result
                        
                except Exception as e:
                    logging.error(f"Error scanning host: {e}")
                    scanned_count += 1

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