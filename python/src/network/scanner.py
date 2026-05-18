import socket
import re as _re
import concurrent.futures
import time
from src.config.settings import TOP_60_PORTS, ALL_PORTS, port_number_to_name


def _safe_scan_target(value: str) -> bool:
    """IPv4 / hostname allowlist for port-scan targets. Same shape as
    `_is_safe_remote_target` in the route layer — defense in depth here so a
    future caller that bypasses the route gate still can't ask the scanner to
    open 65k sockets against an attacker-controlled hostname."""
    if not isinstance(value, str) or not value or len(value) > 253:
        return False
    if _re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
        try:
            return all(0 <= int(o) <= 255 for o in value.split("."))
        except ValueError:
            return False
    return bool(_re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value))


def scan_top_ports(target_ip):
    """Escaneia as portas mais comuns usando threads paralelas para máxima velocidade."""
    if not _safe_scan_target(target_ip):
        yield "Endereço de destino inválido.\n"
        return
    open_ports = []
    yield f"Iniciando varredura das portas mais comuns em {target_ip}...\n"
    
    def scan_port(port):
        """Função para escanear uma porta individual."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.3)
                result = sock.connect_ex((target_ip, port))
                return port, result == 0
        except Exception:
            # Connect failures in port scan are expected for closed/filtered ports;
            # silencing here keeps the hot loop fast (logging 65535 misses would flood).
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

def scan_all_ports(target_ip):
    """Escaneia todas as portas TCP (1-65535) usando threads paralelas para máxima velocidade."""
    if not _safe_scan_target(target_ip):
        yield "Endereço de destino inválido.\n"
        return

    open_ports = []
    scanned_count = 0
    total_ports = len(ALL_PORTS)
    start_time = time.time()
    
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
        except Exception:
            # Connect failures in port scan are expected for closed/filtered ports;
            # silencing here keeps the hot loop fast (logging 65535 misses would flood).
            return port, False
    
    # Usar ThreadPoolExecutor para escaneamento paralelo. 100 sockets em vôo
    # é o teto seguro no Windows (FD limit padrão é 512, mas o conn-track do
    # firewall corporativo derruba a velocidade real bem antes disso).
    max_workers = min(100, total_ports)
    
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
