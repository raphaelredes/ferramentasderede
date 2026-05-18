import os
import subprocess
import time
import re
import logging

import socket

def check_host_status(ip_address, cache=None, cache_timeout=30, timeout=None, source_ip=None):
    """Verifica se um host está online com cache para melhor performance.

    `source_ip` força a NIC de saída — necessário em ambientes multi-VLAN.
    """
    try:
        # Verificar cache primeiro. A chave inclui source_ip pois um mesmo IP
        # pode estar online por uma NIC e offline por outra.
        current_time = time.time()
        cache_key = (ip_address, source_ip) if source_ip else ip_address
        if cache and cache_key in cache:
            cached_time, cached_status = cache[cache_key]
            if current_time - cached_time < cache_timeout:
                return cached_status

        param_count = '-n' if os.name == 'nt' else '-c'
        param_timeout = '-w' if os.name == 'nt' else '-W'

        if timeout:
            timeout_val = str(int(timeout * 1000)) if os.name == 'nt' else str(timeout)
        else:
            timeout_val = str(300) if os.name == 'nt' else str(0.3)

        command = ["ping", "-4", param_count, "1", param_timeout, timeout_val]
        if source_ip:
            command += (["-S", source_ip] if os.name == 'nt' else ["-I", source_ip])
        command.append(ip_address)
        # Adicionar timeout ao subprocess.run para evitar travamentos
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, timeout=float(timeout_val) + 1)
        except subprocess.TimeoutExpired:
            return False
        
        status = result.returncode == 0
        
        # Fallback: Se ping falhar, tentar porta 135 (RPC) ou 445 (SMB) para hosts Windows
        if not status:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5) # Timeout curto para fallback
                    if sock.connect_ex((ip_address, 135)) == 0:
                        status = True
                    elif sock.connect_ex((ip_address, 445)) == 0:
                        status = True
            except Exception as e:
                logging.debug(f"TCP fallback for {ip_address} failed: {e}")

        # Armazenar no cache
        if cache is not None:
            cache[cache_key] = (current_time, status)

        return status
    except Exception:
        return False

try:
    from icmplib import ping as icmp_ping
    ICMPLIB_AVAILABLE = True
except ImportError:
    ICMPLIB_AVAILABLE = False

def parse_ping_output(output):
    """Extrai a latência (ms) da saída do comando ping."""
    # Tentar pegar a média primeiro (Average = XXms, Média = XXms)
    avg_match = re.search(r'(?:Average|Média|Media)\s*=\s*(\d+)ms', output, re.IGNORECASE)
    if avg_match:
        return int(avg_match.group(1))
    
    # Fallback para pegar o primeiro tempo encontrado (time=XXms)
    time_match = re.search(r'(?:tempo|time)[=<](\d+)ms', output, re.IGNORECASE)
    if time_match:
        return int(time_match.group(1))
        
    return None

def check_host_status_detailed(ip_address, count=1, is_wan=False, resolve_names=False, fast_mode=False):
    """Verifica status e latência de um host usando icmplib (rápido) ou subprocess (lento)."""
    
    # Definir timeout baseado no modo (Burst vs Normal) e Tipo de Rede (LAN vs WAN)
    # Burst Mode (count > 1):
    #   - LAN: 200ms (Rápido)
    #   - WAN: 500ms (Confiável)
    # Normal Mode (count == 1):
    #   - 1000ms (Padrão)
    if count > 1:
        timeout_val = 0.5 if is_wan else 0.2
    else:
        # Se fast_mode, usar timeout agressivo de 500ms
        timeout_val = 0.5 if fast_mode else 1.0

    # Tentar icmplib primeiro (muito mais rápido) - APENAS SE NÃO PRECISAR RESOLVER NOMES
    # icmplib não suporta resolução de nomes reversa (ping -a) nativamente da mesma forma que o ping do Windows
    if ICMPLIB_AVAILABLE and not resolve_names:
        try:
            # privileged=False tenta usar datagram sockets (não requer admin no Linux, mas pode falhar no Windows sem admin)
            # Se falhar, tentamos o método antigo.
            # Intervalo menor para burst
            interval = 0.2 if count > 1 else 0.2
            host = icmp_ping(ip_address, count=count, interval=interval, timeout=timeout_val, privileged=False)
            
            if host.is_alive:
                return {
                    'online': True,
                    'latency': host.avg_rtt,
                    'packet_loss': int(host.packet_loss * host.packets_sent), # icmplib retorna float 0.0-1.0
                    'packet_loss_pct': host.packet_loss * 100,
                    'total_packets': host.packets_sent,
                    'resolved_hostname': None,
                    'domain': None
                }
        except Exception as e:
            # Se der erro (ex: permissão), cai para o fallback
            # logging.debug(f"icmplib falhou para {ip_address}, usando fallback: {e}")
            pass

    # Fallback para o método antigo (subprocess)
    try:
        # Converter timeout para formato do comando ping
        # OTIMIZAÇÃO: Timeout máximo de 1000ms para garantir updates rápidos
        timeout_val = min(timeout_val, 1.0)
        timeout_ms = str(int(timeout_val * 1000))
        timeout_s = str(timeout_val)

        # Otimização para Windows (e Linux sem root):
        # O comando ping padrão espera 1s entre envios. Para 'Burst Mode' (count > 1),
        # isso causa demora de ~5s para 5 pings.
        # Solução: Executar 'ping -n 1' várias vezes em loop se count > 1.
        # Isso é muito mais rápido para hosts online (retorno imediato).
        
        if count > 1 and not resolve_names:
            total_sent = 0
            total_lost = 0
            rtt_sum = 0
            rtt_count = 0
            
            for _ in range(count):
                # Executar 1 ping
                if os.name == 'nt':
                    cmd = ["ping", "-n", "1", "-w", timeout_ms, ip_address]
                else:
                    cmd = ["ping", "-c", "1", "-W", timeout_s, ip_address]
                
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                
                try:
                    res = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        encoding='cp850', 
                        errors='replace',
                        creationflags=creation_flags,
                        timeout=float(timeout_val) + 1 # Timeout de segurança do Python
                    )
                except subprocess.TimeoutExpired:
                    total_lost += 1
                    continue
                
                total_sent += 1
                if res.returncode == 0:
                    # Extrair latência deste ping
                    lat = parse_ping_output(res.stdout)
                    if lat is not None:
                        rtt_sum += lat
                        rtt_count += 1
                else:
                    total_lost += 1
            
            # Calcular médias
            avg_latency = (rtt_sum / rtt_count) if rtt_count > 0 else None
            packet_loss_pct = (total_lost / total_sent) * 100 if total_sent > 0 else 100
            
            return {
                'online': rtt_count > 0, # Considera online se pelo menos 1 respondeu? Ou se a maioria? Vamos ser otimistas: se 1 respondeu, está online.
                'latency': avg_latency,
                'packet_loss': total_lost,
                'packet_loss_pct': packet_loss_pct,
                'total_packets': total_sent,
                'resolved_hostname': None,
                'domain': None
            }

        # Comportamento padrão para count=1 (ou se decidirmos não usar o loop)
        # Se resolve_names=True, adicionar flag -a no Windows
        if os.name == 'nt':
            command = ["ping", "-n", str(count), "-w", timeout_ms]
            if resolve_names:
                command.append("-a")
            command.append(ip_address)
        else:
            command = ["ping", "-c", str(count), "-W", timeout_s, ip_address]
        
        # Windows needs CREATE_NO_WINDOW
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        
        # Se estiver resolvendo nomes, aumentar o timeout total pois o DNS pode demorar
        proc_timeout = (float(timeout_val) * count) + 2
        if resolve_names:
            proc_timeout += 2 # +2s para DNS
        
        try:
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                encoding='cp850', 
                errors='replace',
                creationflags=creation_flags,
                timeout=proc_timeout
            )
        except subprocess.TimeoutExpired:
            return {
                'online': False,
                'latency': None,
                'packet_loss': count,
                'packet_loss_pct': 100,
                'total_packets': count,
                'resolved_hostname': None,
                'domain': None
            }
        
        online = result.returncode == 0
        latency = None
        packet_loss = 0
        packet_loss_pct = 0
        total_packets = count
        resolved_hostname = None
        domain = None
        
        if online:
            latency = parse_ping_output(result.stdout)
            
            # Tentar extrair estatísticas se disponíveis
            lost_match = re.search(r'(?:Lost|Perdidos)\s*=\s*(\d+)', result.stdout, re.IGNORECASE)
            sent_match = re.search(r'(?:Sent|Enviados)\s*=\s*(\d+)', result.stdout, re.IGNORECASE)
            
            if lost_match and sent_match:
                packet_loss = int(lost_match.group(1))
                total_packets = int(sent_match.group(1))
                if total_packets > 0:
                    packet_loss_pct = (packet_loss / total_packets) * 100
            
            # Extrair Hostname se solicitado
            if resolve_names and os.name == 'nt':
                    match = re.search(r"(?:Disparando|Pinging)(?:\s+contra)?\s+(.*?)\s+\[", result.stdout, re.IGNORECASE)
                    if match:
                        hostname_cand = match.group(1).strip()
                        if hostname_cand != ip_address:
                            resolved_hostname = hostname_cand
                            # Extract domain if present (e.g., host.domain.com -> domain.com)
                            if '.' in resolved_hostname:
                                parts = resolved_hostname.split('.')
                                if len(parts) > 1:
                                    domain = '.'.join(parts[1:])
            
            # Fallback: Use socket.getfqdn() if ping -a failed to resolve a name or returned the IP
            if resolve_names and (not resolved_hostname or resolved_hostname == ip_address):
                try:
                    fqdn = socket.getfqdn(ip_address)
                    if fqdn and fqdn != ip_address:
                        resolved_hostname = fqdn
                        if '.' in resolved_hostname:
                            parts = resolved_hostname.split('.')
                            if len(parts) > 1:
                                domain = '.'.join(parts[1:])
                except Exception as e:
                    logging.debug(f"getfqdn fallback for {ip_address} failed: {e}")

        else:
            packet_loss = count
            packet_loss_pct = 100
            
            # Fallback: Tentar TCP connect se ping falhar (apenas se count for 1, para não demorar muito)
            # OTIMIZAÇÃO: Se fast_mode, pular TCP connect para garantir ciclo de 1s
            if count == 1 and not fast_mode:
                try:
                    start_time = time.time()
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.settimeout(1.0)
                        # Tentar porta 135 (RPC - comum em Windows)
                        if sock.connect_ex((ip_address, 135)) == 0:
                            online = True
                            latency = int((time.time() - start_time) * 1000)
                        # Se falhar, tentar porta 445 (SMB)
                        elif sock.connect_ex((ip_address, 445)) == 0:
                            online = True
                            latency = int((time.time() - start_time) * 1000)
                except Exception as e:
                    logging.debug(f"TCP probe fallback for {ip_address} failed: {e}")
        
        # Fallback 2: Verificar tabela ARP (para hosts na mesma sub-rede que bloqueiam tudo)
        # OTIMIZAÇÃO: Se fast_mode, pular ARP check pois arp -a é lento
        if not online and count == 1 and not fast_mode:
            if check_arp_table(ip_address):
                online = True
                latency = 0 # Latência desprezível na rede local

    # Fallback 3: Tentar via PowerShell (Test-Connection) se tudo falhar
        # REMOVIDO: PowerShell é muito lento (3-5s) e causa atraso no monitoramento em tempo real.
        # Se o ping ICMP e TCP falharem, consideramos offline para manter o ciclo de 1s.
        # if not online and os.name == 'nt' and count == 1:
        #     ps_online, ps_latency = check_powershell_ping(ip_address)
        #     if ps_online:
        #         online = True
        #         latency = ps_latency
        
        return {
            'online': online,
            'latency': latency,
            'packet_loss': packet_loss,
            'packet_loss_pct': packet_loss_pct,
            'total_packets': total_packets,
            'resolved_hostname': resolved_hostname,
            'domain': domain
        }
        
    except Exception as e:
        logging.error(f"Erro ao verificar status detalhado de {ip_address}: {e}")
        return {
            'online': False, 
            'latency': None,
            'packet_loss': count,
            'packet_loss_pct': 100,
            'total_packets': count,
            'resolved_hostname': None,
            'domain': None
        }

def check_powershell_ping(ip_address):
    """Tenta verificar status usando PowerShell Test-Connection (ICMP) e Test-NetConnection (TCP)."""
    try:
        # Tentar Test-Connection (ICMP) - Count 2 para confiabilidade
        cmd = f"Test-Connection -ComputerName {ip_address} -Count 2 -Quiet"
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0 and "True" in result.stdout:
            return True, 0 # Latência desconhecida, assume 0 ou baixo
            
        # Tentar Test-NetConnection porta 135 (TCP)
        cmd_tcp = f"Test-NetConnection -ComputerName {ip_address} -Port 135 -InformationLevel Quiet"
        result_tcp = subprocess.run(["powershell", "-Command", cmd_tcp], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result_tcp.returncode == 0 and "True" in result_tcp.stdout:
            return True, 0
            
        return False, None
    except Exception as e:
        logging.debug(f"Test-Connection fallback failed for {ip_address}: {e}")
        return False, None

def check_arp_table(ip_address):
    """Verifica se o IP está presente na tabela ARP (indica que está online na rede local)."""
    try:
        # Executar arp -a
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True, encoding='cp850', errors='replace', creationflags=creation_flags)
        
        if result.returncode == 0:
            # Procurar pelo IP na saída (com espaço antes ou depois para evitar falsos positivos de substrings)
            # Ex: " 192.168.1.1 "
            return f" {ip_address} " in result.stdout
        return False
    except Exception as e:
        logging.debug(f"ARP table check failed for {ip_address}: {e}")
        return False

def continuous_ping(target, packet_size=32, source_ip=None):
    """Executa um ping contínuo e gera a saída linha por linha.

    `source_ip` força a interface de saída — essencial em máquinas com NICs em
    múltiplas VLANs/domínios onde a rota default pode mandar o pacote pela
    interface errada.
    """
    if os.name == 'nt':
        command = ["ping", "-4", "-t", "-l", str(packet_size)]
        if source_ip:
            command += ["-S", source_ip]
        command.append(target)
    else:
        command = ["ping", "-4"]
        if source_ip:
            command += ["-I", source_ip]
        command += [target, "-s", str(packet_size)]

    encoding = 'cp850' if os.name == 'nt' else 'utf-8'
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding=encoding, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    
    yield "", process
    try: # Adicionado bloco try para garantir a limpeza
        for line in iter(process.stdout.readline, ''):
            yield line, process
    finally: # Garante que estas linhas sempre serão executadas
        process.stdout.close()
        process.wait()

def get_ping_statistics(target):
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

def generate_ping_statistics_from_output(output_lines, target):
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
                time_match = re.search(r'tempo[=<](\d+)ms', line) or re.search(r'time[=<](\d+)ms', line)
                if time_match:
                    response_times.append(int(time_match.group(1)))
                    
            # Contar timeouts/perdas. Antes a expressão era
            # `"timeout" in line or "time=" in line and "ms" not in line ...`
            # — sem parênteses, `and` precede `or`, então o agrupamento real
            # era `(timeout) OR (time= AND NOT ms) OR ...`, perdendo casos de
            # "tempo esgotado" + "Esgotado..." em algumas combinações.
            elif (
                "tempo esgotado" in line
                or "timeout" in line
                or ("time=" in line and "ms" not in line)
                or "Esgotado o tempo limite" in line
                or "Request timed out" in line
            ):
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
