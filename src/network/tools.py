# app/network_tools.py
# Corrigida a codificação de saída dos comandos de console do Windows para cp850.

import os
import subprocess
import socket
import re
import threading
import ipaddress
import concurrent.futures
from wakeonlan import send_magic_packet
from src.config.settings import STATUS_PING_TIMEOUT, TOP_60_PORTS, ALL_PORTS, port_number_to_name
import time
import logging

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
        
        # Controle de execução de comandos
        self.is_running = False
        self.running_command = None
        self._current_process = None

    def check_host_status(self, ip_address):
        """Verifica se um host está online com cache para melhor performance."""
        try:
            # Verificar cache primeiro
            current_time = time.time()
            if ip_address in self._status_cache:
                cached_time, cached_status = self._status_cache[ip_address]
                if current_time - cached_time < self._cache_timeout:
                    return cached_status
            
            param_count = '-n' if os.name == 'nt' else '-c'
            param_timeout = '-w' if os.name == 'nt' else '-W'
            # Timeout otimizado: 300ms no Windows, 0.3s no Linux
            timeout_val = str(300) if os.name == 'nt' else str(0.3)
            command = ["ping", "-4", param_count, "1", param_timeout, timeout_val, ip_address]
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            status = result.returncode == 0
            
            # Armazenar no cache
            self._status_cache[ip_address] = (current_time, status)
            
            # Limpar cache antigo se necessário
            if len(self._status_cache) > 100:
                self._cleanup_cache()
            
            return status
        except Exception:
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
        if self.is_running:
            return
        self.is_running = True
        self.running_command = "ping"

        def run_ping():
            process = None
            try:
                output_widget.configure(state="normal")
                output_widget.insert("end", f"Iniciando ping com tamanho de pacote: {packet_size}\n")
                output_widget.configure(state="disabled")

                # Este método compatível só é usado quando chamado diretamente.
                # Mantemos 127.0.0.1 como fallback; o fluxo principal usa o IP de destino pelo controller.
                ip = target_ip or "127.0.0.1"
                command = ["ping", "-4", "-t", "-l", str(packet_size), "-w", "3000", ip]
                # Usar localhost como fallback compatível
                encoding = 'cp850' if os.name == 'nt' else 'utf-8'
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding=encoding, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

                for line in iter(process.stdout.readline, ''):
                    if not self.is_running:
                        break
                    if line:
                        output_widget.configure(state="normal")
                        output_widget.insert("end", line)
                        output_widget.see("end")
                        output_widget.configure(state="disabled")
                
            except Exception as e:
                logging.error(f"Erro no ping: {e}")
            finally:
                try:
                    if process:
                        process.terminate()
                except:
                    pass
                self.is_running = False
                self.running_command = None

        threading.Thread(target=run_ping, daemon=True).start()

    def stop_command(self):
        """Para o comando em execução."""
        self.is_running = False
        self.running_command = None
        if self._current_process:
            try:
                self._current_process.terminate()
            except:
                pass
            self._current_process = None

    def run_traceroute(self, target_ip):
        """Executa traceroute e gera (line, ip_found, process) por iteração.
        Compatível com NetworkToolController._traceroute_worker.
        """
        import re
        ip = target_ip or "127.0.0.1"
        command = ["tracert", "-d", ip] if os.name == 'nt' else ["traceroute", ip]
        encoding = 'cp850' if os.name == 'nt' else 'utf-8'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding=encoding, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        # Primeira iteração entrega apenas o processo
        yield "Iniciando traceroute...\n", None, process
        try:
            for raw_line in iter(process.stdout.readline, ''):
                line = raw_line
                # Detectar IP simples na linha
                m = re.search(r"(?:(?:\d{1,3}\.){3}\d{1,3})", line)
                ip_found = m.group(0) if m else None
                yield line, ip_found, process
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass
            try:
                process.terminate()
            except Exception:
                pass

    def test_ports(self, ports, output_widget, entry_widget=None):
        """Testa portas específicas."""
        if self.is_running:
            return
        
        self.is_running = True
        self.running_command = "port_test"
        
        def run_port_test():
            try:
                output_widget.configure(state="normal")
                output_widget.insert("end", f"Testando portas: {ports}\n")
                output_widget.configure(state="disabled")
                
                # Aqui você implementaria o teste de portas real
                time.sleep(1)
                
                output_widget.configure(state="normal")
                output_widget.insert("end", "Teste de portas concluído.\n")
                output_widget.configure(state="disabled")
                
            except Exception as e:
                logging.error(f"Erro no teste de portas: {e}")
            finally:
                self.is_running = False
                self.running_command = None
        
        threading.Thread(target=run_port_test, daemon=True).start()

    def start_all_ports_scan(self, output_widget):
        """Inicia escaneamento de todas as portas."""
        if self.is_running:
            return
        
        self.is_running = True
        self.running_command = "scan"
        
        def run_scan():
            try:
                output_widget.configure(state="normal")
                output_widget.insert("end", "Iniciando escaneamento de portas...\n")
                output_widget.configure(state="disabled")
                
                # Aqui você implementaria o escaneamento real
                time.sleep(3)
                
                output_widget.configure(state="normal")
                output_widget.insert("end", "Escaneamento concluído.\n")
                output_widget.configure(state="disabled")
                
            except Exception as e:
                logging.error(f"Erro no escaneamento: {e}")
            finally:
                self.is_running = False
                self.running_command = None
        
        threading.Thread(target=run_scan, daemon=True).start()

    def resolve_ip_and_hostname(self, target):
        """Resolve o IP e o hostname para um alvo, otimizado para Windows."""
        try:
            ip_address = socket.gethostbyname(target)
            hostname = "N/A"
            
            if os.name == 'nt':
                try:
                    output = subprocess.check_output(
                        ["ping", "-4", "-a", "-n", "1", "-w", "1000", ip_address],
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='cp850',
                        errors='replace',
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    match = re.search(r"Pinging ([\w\.-]+) \[", output) or re.search(r"Disparando ([\w\.-]+) \[", output)
                    if match:
                        hostname = match.group(1)
                except (subprocess.CalledProcessError, Exception):
                    pass

            if hostname == "N/A":
                try:
                    hostname, _, _ = socket.gethostbyaddr(ip_address)
                except (socket.herror, socket.gaierror):
                    pass

            return ip_address, hostname

        except socket.gaierror:
            return "Inválido", "Inválido"
        except Exception:
            return "Erro", "Erro"

    def get_local_network_info(self):
        """Obtém o IP, sub-rede e objeto de rede da máquina local."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            if os.name == 'nt':
                proc = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='cp850', errors='replace')
                output = proc.stdout
                
                adapter_section = ""
                for section in output.split('\n\n'):
                    if local_ip in section:
                        adapter_section = section
                        break

                if not adapter_section:
                    return {"error": f"Não foi possível encontrar o adaptador para o IP {local_ip}."}

                mask_match = re.search(r"M[áa]scara de Sub-rede.*: ([\d\.]+)", adapter_section) or re.search(r"Subnet Mask.*: ([\d\.]+)", adapter_section)
                
                if mask_match:
                    subnet_mask = mask_match.group(1).strip()
                else:
                    return {"error": "Máscara de sub-rede não encontrada na seção do adaptador."}
            else: 
                subnet_mask = "255.255.255.0"

            interface = ipaddress.IPv4Interface(f"{local_ip}/{subnet_mask}")
            return {
                "ip": local_ip,
                "subnet": subnet_mask,
                "network": interface.network
            }

        except Exception as e:
            return {"error": str(e)}

    def discover_hosts(self, network, max_threads=50):
        hosts_to_scan = list(network.hosts())
        results_queue = []
        threads = []
        
        def ping_and_resolve(ip_obj):
            ip_str = str(ip_obj)
            if self.check_host_status(ip_str):
                _, hostname = self.resolve_ip_and_hostname(ip_str)
                results_queue.append({"ip": ip_str, "hostname": hostname if hostname != "N/A" else ip_str})

        for ip_addr in hosts_to_scan:
            thread = threading.Thread(target=ping_and_resolve, args=(ip_addr,), daemon=True)
            threads.append(thread)
            thread.start()

            if len(threads) >= max_threads:
                for t in threads:
                    t.join()
                threads = []
                for result in sorted(results_queue, key=lambda x: ipaddress.IPv4Address(x['ip'])):
                    yield result
                results_queue.clear()

        for t in threads:
            t.join()

        for result in sorted(results_queue, key=lambda x: ipaddress.IPv4Address(x['ip'])):
            yield result

    def send_wol_packet(self, mac_address):
        """Envia um pacote Wake-on-LAN."""
        try:
            if not re.match(r"([0-9a-fA-F]{2}[:\-]){5}([0-9a-fA-F]{2})", mac_address):
                return False, "Formato de endereço MAC inválido."
            
            send_magic_packet(mac_address)
            return True, f"Pacote Wake-on-LAN enviado para {mac_address}."
        except Exception as e:
            return False, f"Falha ao enviar pacote WOL: {e}"

    def ping_with_stats(self, target, count=4):
        """Executa ping para um host e retorna a saída com estatísticas completas como no prompt de comando."""
        try:
            param_count = '-n' if os.name == 'nt' else '-c'
            command = ["ping", "-4", param_count, str(count), target]
            result = subprocess.run(command, capture_output=True, text=True, encoding='cp850', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            output = result.stdout
            
            # Se o ping falhou, tentar com timeout menor
            if result.returncode != 0:
                timeout_param = '-w' if os.name == 'nt' else '-W'
                timeout_val = '1000' if os.name == 'nt' else '1'
                command_retry = ["ping", "-4", param_count, str(count), timeout_param, timeout_val, target]
                result_retry = subprocess.run(command_retry, capture_output=True, text=True, encoding='cp850', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                output = result_retry.stdout
            
            # Garantir que sempre temos estatísticas
            if "Estatísticas" not in output and "Statistics" not in output:
                # Adicionar estatísticas básicas se não estiverem presentes
                lines = output.split('\n')
                stats_line = f"\nEstatísticas do Ping para {target}:\n"
                stats_line += "    Pacotes: Enviados = 4, Recebidos = 0, Perdidos = 4 (100% de perda)\n"
                output += stats_line
            
            return output
        except Exception as e:
            return f"Erro ao executar ping: {e}\n\nEstatísticas do Ping para {target}:\n    Pacotes: Enviados = 0, Recebidos = 0, Perdidos = 0 (erro na execução)"

    def continuous_ping(self, target, packet_size=32):
        """Executa um ping contínuo e gera a saída linha por linha."""
        # ALTERAÇÃO: Forçar IPv4 para evitar uso automático de IPv6
        if os.name == 'nt':
            command = ["ping", "-4", "-t", "-l", str(packet_size), target]  # -4 força IPv4
        else:
            command = ["ping", "-4", target, "-s", str(packet_size)]  # -4 força IPv4
        
        encoding = 'cp850' if os.name == 'nt' else 'utf-8'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding=encoding, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        yield "", process
        try: # Adicionado bloco try para garantir a limpeza
            for line in iter(process.stdout.readline, ''):
                yield line, process
        finally: # Garante que estas linhas sempre serão executadas
            process.stdout.close()
            process.wait()
            
    def get_ping_statistics(self, target):
        """Executa um ping rápido para obter estatísticas."""
        try:
            param_count = '-n' if os.name == 'nt' else '-c'
            count = '4'  # Apenas 4 pings para estatísticas rápidas
            command = ["ping", "-4", param_count, count, target]
            result = subprocess.run(command, capture_output=True, text=True, encoding='cp850', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            output = result.stdout
            
            # Se o ping falhou, tentar com timeout menor
            if result.returncode != 0:
                timeout_param = '-w' if os.name == 'nt' else '-W'
                timeout_val = '1000' if os.name == 'nt' else '1'
                command_retry = ["ping", "-4", param_count, count, timeout_param, timeout_val, target]
                result_retry = subprocess.run(command_retry, capture_output=True, text=True, encoding='cp850', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                output = result_retry.stdout
            
            # Extrair apenas as estatísticas
            lines = output.split('\n')
            stats_lines = []
            in_stats = False
            
            for line in lines:
                if "Estatísticas" in line or "Statistics" in line or "Pacotes:" in line or "Packets:" in line:
                    in_stats = True
                if in_stats:
                    stats_lines.append(line)
                    
            if stats_lines:
                return '\n'.join(stats_lines)
            else:
                return f"\nEstatísticas do Ping para {target}:\n    Pacotes: Enviados = 0, Recebidos = 0, Perdidos = 0 (sem dados)\n"
                
        except Exception as e:
            return f"\nEstatísticas do Ping para {target}:\n    Pacotes: Enviados = 0, Recebidos = 0, Perdidos = 0 (erro: {e})\n"
            
    def generate_ping_statistics_from_output(self, output_lines, target):
        """Gera estatísticas baseadas no output capturado do ping contínuo."""
        try:
            sent_count = 0
            received_count = 0
            lost_count = 0
            response_times = []
            
            for line in output_lines:
                line = line.strip()
                
                # Contar pings enviados (linhas que começam com "Disparando" ou "Pinging")
                if line.startswith("Disparando") or line.startswith("Pinging"):
                    sent_count += 1
                    
                # Contar respostas recebidas
                elif "Resposta de" in line or "Reply from" in line:
                    received_count += 1
                    
                    # Extrair tempo de resposta
                    import re
                    time_match = re.search(r'tempo[=<](\d+)ms', line) or re.search(r'time[=<](\d+)ms', line)
                    if time_match:
                        response_times.append(int(time_match.group(1)))
                        
                # Contar timeouts/perdas
                elif "tempo esgotado" in line or "timeout" in line or "time=" in line and "ms" not in line:
                    lost_count += 1
                    
            # Calcular estatísticas
            total_sent = sent_count + received_count + lost_count
            if total_sent == 0:
                total_sent = len(output_lines)  # Fallback
                
            loss_percentage = (lost_count / total_sent * 100) if total_sent > 0 else 0
            
            # Calcular estatísticas de tempo
            if response_times:
                min_time = min(response_times)
                max_time = max(response_times)
                avg_time = sum(response_times) / len(response_times)
            else:
                min_time = max_time = avg_time = 0
                
            # Gerar estatísticas no formato do Windows
            stats = f"\nEstatísticas do Ping para {target}:\n"
            stats += f"    Pacotes: Enviados = {total_sent}, Recebidos = {received_count}, Perdidos = {lost_count} ({loss_percentage:.0f}% de perda)\n"
            
            if response_times:
                stats += "Tempo aproximado de ida e volta em milissegundos:\n"
                stats += f"    Mínimo = {min_time}ms, Máximo = {max_time}ms, Média = {avg_time:.0f}ms\n"
                
            return stats
            
        except Exception as e:
            return f"\nEstatísticas do Ping para {target}:\n    Pacotes: Enviados = 0, Recebidos = 0, Perdidos = 0 (erro ao gerar estatísticas: {e})\n"

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
                        # Mapeia alguns códigos comuns para uma mensagem mais clara
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
        open_ports = []
        yield f"Iniciando varredura das portas mais comuns em {target_ip}...\n"
        
        def scan_port(port):
            """Função para escanear uma porta individual."""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.3)
                    result = sock.connect_ex((target_ip, port))
                    return port, result == 0
            except:
                return port, False
        
        # Usar ThreadPoolExecutor para escaneamento paralelo
        max_workers = min(20, len(TOP_60_PORTS))  # Máximo 20 threads para portas comuns
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter todas as portas para escaneamento
            future_to_port = {executor.submit(scan_port, port): port for port in TOP_60_PORTS}
            
            # Processar resultados conforme ficam prontos
            for future in concurrent.futures.as_completed(future_to_port):
                port, is_open = future.result()
                if is_open:
                    service = port_number_to_name.get(port, "Desconhecido")
                    open_ports.append((port, service))
                    # NÃO exibir portas abertas durante o escaneamento - apenas coletar
        
        yield "\nVarredura concluída.\n"
        if open_ports:
            yield f"Total de portas abertas encontradas: {len(open_ports)}\n"
            yield "Portas abertas:\n"
            for port, service in sorted(open_ports):
                yield f"  - {port}: {service}\n"
        else:
            yield "Nenhuma porta aberta encontrada nas portas comuns.\n"
            
    def scan_all_ports(self, target_ip):
        """Escaneia todas as portas TCP (1-65535) usando threads paralelas para máxima velocidade."""
        import time
        
        open_ports = []
        scanned_count = 0
        total_ports = len(ALL_PORTS)
        start_time = time.time()
        last_progress_time = start_time
        
        yield f"Iniciando varredura completa de todas as portas em {target_ip}...\n"
        yield "Usando escaneamento paralelo otimizado para máxima velocidade.\n"
        yield "Pressione 'Parar de Escanear' para interromper.\n\n"
        
        def scan_port(port):
            """Função para escanear uma porta individual."""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.1)  # Timeout ainda menor para máxima velocidade
                    result = sock.connect_ex((target_ip, port))
                    return port, result == 0
            except:
                return port, False
        
        # Usar ThreadPoolExecutor para escaneamento paralelo
        max_workers = min(200, total_ports)  # Aumentado para 200 threads simultâneas
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter todas as portas para escaneamento
            future_to_port = {executor.submit(scan_port, port): port for port in ALL_PORTS}
            
            # Processar resultados conforme ficam prontos
            for future in concurrent.futures.as_completed(future_to_port):
                port, is_open = future.result()
                scanned_count += 1
                current_time = time.time()
                
                # Mostrar progresso a cada 500 portas com estimativa de tempo (substituindo a mesma linha)
                if scanned_count % 500 == 0:
                    progress = (scanned_count / total_ports) * 100
                    elapsed_time = current_time - start_time
                    
                    if scanned_count > 0:
                        # Calcular velocidade (portas por segundo)
                        ports_per_second = scanned_count / elapsed_time
                        remaining_ports = total_ports - scanned_count
                        estimated_remaining_time = remaining_ports / ports_per_second if ports_per_second > 0 else 0
                        
                        # Formatar tempo restante
                        if estimated_remaining_time < 60:
                            time_str = f"{estimated_remaining_time:.0f}s"
                        elif estimated_remaining_time < 3600:
                            minutes = estimated_remaining_time / 60
                            time_str = f"{minutes:.1f}min"
                        else:
                            hours = estimated_remaining_time / 3600
                            time_str = f"{hours:.1f}h"
                        
                        yield f"\rProgresso: {progress:.1f}% ({scanned_count}/{total_ports}) | Velocidade: {ports_per_second:.0f} portas/s | Tempo restante: ~{time_str}"
                    else:
                        yield f"\rProgresso: {progress:.1f}% ({scanned_count}/{total_ports} portas verificadas)"
                
                if is_open:
                    service = port_number_to_name.get(port, "Desconhecido")
                    open_ports.append((port, service))
                    # NÃO exibir portas abertas durante o escaneamento - apenas coletar
        
        total_time = time.time() - start_time
        yield f"\nVarredura completa concluída em {total_time:.1f} segundos.\n"
        if open_ports:
            yield f"Total de portas abertas encontradas: {len(open_ports)}\n"
            yield "Portas abertas:\n"
            for port, service in sorted(open_ports):
                yield f"  - {port}: {service}\n"
        else:
            yield "Nenhuma porta aberta encontrada.\n"

    def traceroute(self, target_ip):
        """Executa traceroute simples e robusto com timeout adequado."""
        logging.info(f"TRACEROUTE: Iniciando para {target_ip}")
        
        try:
            # Comando traceroute para Windows e Linux
            if os.name == 'nt':
                # No Windows: tracert com máximo de saltos limitado para hosts locais
                command = ["tracert", "-h", "15", "-w", "3000", target_ip]
                encoding = 'cp850'
            else:
                command = ["traceroute", "-m", "15", "-w", "3", target_ip]
                encoding = 'utf-8'
            
            # Executar comando com timeout
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                encoding=encoding, 
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Armazenar referência do processo
            self._current_process = process
            
            yield f"Rastreando rota para {target_ip}...\n\n"
            
            # Ler output linha por linha com timeout por linha
            import time
            import select
            import sys
            
            line_count = 0
            max_lines = 50  # Limite para evitar travamentos
            start_time = time.time()
            max_duration = 60  # Timeout total de 60 segundos
            
            while True:
                # Verificar timeout total
                if time.time() - start_time > max_duration:
                    yield f"\nTimeout: Traceroute interrompido após {max_duration} segundos.\n"
                    break
                
                # Verificar se processo ainda está rodando
                if process.poll() is not None:
                    # Processo terminou, ler linhas restantes
                    remaining_lines = process.stdout.read()
                    if remaining_lines:
                        yield remaining_lines
                    break
                    
                try:
                    # Tentar ler linha com timeout pequeno
                    if os.name == 'nt':
                        # No Windows, usar readline normal
                        line = process.stdout.readline()
                    else:
                        # No Linux, usar select para timeout
                        ready, _, _ = select.select([process.stdout], [], [], 1.0)
                        if ready:
                            line = process.stdout.readline()
                        else:
                            line = None
                            
                    if line:
                        yield line
                        line_count += 1
                        
                        # Limite de linhas para evitar spam infinito
                        if line_count > max_lines:
                            yield f"\nLimite de linhas atingido ({max_lines}). Finalizando traceroute.\n"
                            break
                    else:
                        # Aguardar um pouco antes de tentar novamente
                        time.sleep(0.1)
                        
                except Exception as read_error:
                    logging.error(f"TRACEROUTE: Erro na leitura: {read_error}")
                    break
            
            # Finalização
            try:
                return_code = process.poll()
                if return_code is not None:
                    if return_code == 0:
                        yield f"\nTraceroute concluído.\n"
                    else:
                        yield f"\nTraceroute finalizado (código: {return_code}).\n"
                else:
                    yield f"\nTraceroute interrompido.\n"
            except:
                pass
                
        except FileNotFoundError:
            yield f"Erro: Comando traceroute não encontrado no sistema.\n"
            yield f"No Windows: use 'tracert'. No Linux: instale 'traceroute'.\n"
        except Exception as e:
            logging.error(f"TRACEROUTE: Erro para {target_ip}: {e}")
            yield f"Erro no traceroute: {str(e)}\n"
        finally:
            # Limpeza forçada
            if hasattr(self, '_current_process') and self._current_process:
                try:
                    self._current_process.terminate()
                    time.sleep(0.1)
                    if self._current_process.poll() is None:
                        self._current_process.kill()
                except:
                    pass
                finally:
                    self._current_process = None
            logging.info(f"TRACEROUTE: Finalizado para {target_ip}")

    def initiate_rdp(self, target_ip):
        if os.name == 'nt':
            subprocess.Popen(["mstsc.exe", "/v:" + target_ip])
    
    def initiate_msra(self, target_ip):
        if os.name == 'nt':
            subprocess.Popen(f'msra.exe /offerra {target_ip}', shell=True)