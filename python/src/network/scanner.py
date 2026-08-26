# python/src/network/scanner.py
"""Módulo de varredura e teste acelerado de portas TCP de alta performance.

Utiliza ThreadPoolExecutor de alta concorrência e timeouts adaptativos (LAN/WAN)
para varrer milhares de portas em poucos segundos (estilo Masscan/RustScan).
"""

import socket
import re as _re
import concurrent.futures
import time
from typing import List, Tuple
from src.config.settings import TOP_60_PORTS, ALL_PORTS, port_number_to_name


def _safe_scan_target(value: str) -> bool:
    """Valida se o alvo é um IPv4 ou hostname seguro."""
    if not isinstance(value, str) or not value or len(value) > 253:
        return False
    if _re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
        try:
            return all(0 <= int(o) <= 255 for o in value.split("."))
        except ValueError:
            return False
    return bool(_re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value))


def _is_lan_or_local(ip: str) -> bool:
    """Verifica se o IP é de rede local ou loopback para aplicar timeout ultra-rápido."""
    if ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168."):
        return True
    if ip.startswith("172."):
        parts = ip.split(".")
        if len(parts) >= 2 and parts[1].isdigit():
            val = int(parts[1])
            if 16 <= val <= 31:
                return True
    return False


def scan_top_ports(target_ip: str, stop_event=None):
    """Escaneia as portas mais comuns usando threads paralelas para máxima velocidade."""
    if not _safe_scan_target(target_ip):
        yield "Endereço de destino inválido.\n"
        return
    open_ports = []
    yield f"Iniciando varredura das portas mais comuns em {target_ip}...\n\n"

    timeout = 0.15 if _is_lan_or_local(target_ip) else 0.35

    def scan_port(port: int):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((target_ip, port))
                return port, result == 0
        except Exception:
            return port, False

    max_workers = min(30, len(TOP_60_PORTS))
    cancelled = False

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_port = {executor.submit(scan_port, port): port for port in TOP_60_PORTS}
        for future in concurrent.futures.as_completed(future_to_port):
            if stop_event is not None and stop_event.is_set():
                cancelled = True
                break
            port, is_open = future.result()
            if is_open:
                service = port_number_to_name.get(port, "Desconhecido")
                open_ports.append((port, service))
                yield f"[+] Porta {port}/TCP ({service}) - [ABERTA]\n"

    if cancelled:
        yield "\nVarredura cancelada.\n"
        return
    yield f"\nVarredura concluída. Total de portas abertas: {len(open_ports)}\n"


def scan_all_ports(target_ip: str, stop_event=None):
    """Escaneia todas as portas TCP (1-65535) usando threads paralelas."""
    if not _safe_scan_target(target_ip):
        yield "Endereço de destino inválido.\n"
        return
    yield from scan_specific_ports(target_ip, "1-65535", stop_event=stop_event)


def scan_specific_ports(target_ip: str, ports_str: str, stop_event=None):
    """Testa portas ou faixas especificadas com concorrência adaptativa ultra-rápida."""
    if not _safe_scan_target(target_ip):
        yield "Endereço de destino inválido.\n"
        return

    ports_to_test: List[int] = []
    try:
        parts = _re.split(r'[,\s]+', ports_str.strip())
        for part in parts:
            if not part:
                continue
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start > end:
                    start, end = end, start
                # Limite de segurança de portas TCP (1-65535)
                start = max(1, min(65535, start))
                end = max(1, min(65535, end))
                ports_to_test.extend(range(start, end + 1))
            else:
                p = int(part)
                if 1 <= p <= 65535:
                    ports_to_test.append(p)
    except ValueError:
        yield "Formato de porta inválido. Use '80, 443' ou '8000-9000'.\n"
        return

    # Remover duplicatas mantendo ordem
    seen = set()
    ports_to_test = [p for p in ports_to_test if not (p in seen or seen.add(p))]

    total_ports = len(ports_to_test)
    if total_ports == 0:
        yield "Nenhuma porta válida especificada.\n"
        return

    is_lan = _is_lan_or_local(target_ip)
    timeout = 0.12 if is_lan else 0.35
    max_workers = min(150, max(10, total_ports))

    yield f"Iniciando teste de {total_ports} porta(s) em {target_ip} ({max_workers} threads simultâneas)...\n\n"

    start_time = time.time()
    open_ports: List[Tuple[int, str]] = []
    scanned_count = 0
    cancelled = False

    def check_single_port(port: int):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                res = s.connect_ex((target_ip, port))
                return port, res == 0
        except Exception:
            return port, False

    # Modo A: Poucas portas (<= 25) -> saída detalhada individual
    if total_ports <= 25:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_port = {executor.submit(check_single_port, p): p for p in ports_to_test}
            for future in concurrent.futures.as_completed(future_to_port):
                if stop_event is not None and stop_event.is_set():
                    cancelled = True
                    break
                port, is_open = future.result()
                service = port_number_to_name.get(port, "Desconhecido")
                if is_open:
                    open_ports.append((port, service))
                    yield f"Porta {port}/TCP ({service})... [ABERTA]\n"
                else:
                    yield f"Porta {port}/TCP ({service})... [FECHADA]\n"
    # Modo B: Muitas portas (> 25) -> streaming em tempo real das abertas + barra de progresso
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_port = {executor.submit(check_single_port, p): p for p in ports_to_test}
            for future in concurrent.futures.as_completed(future_to_port):
                if stop_event is not None and stop_event.is_set():
                    cancelled = True
                    break
                port, is_open = future.result()
                scanned_count += 1
                
                if is_open:
                    service = port_number_to_name.get(port, "Desconhecido")
                    open_ports.append((port, service))
                    yield f"[+] Porta {port}/TCP ({service}) - [ABERTA]\n"

                # Atualizar progresso em lotes para não sobrecarregar a UI
                if scanned_count % 300 == 0 or scanned_count == total_ports:
                    elapsed = max(0.01, time.time() - start_time)
                    rate = scanned_count / elapsed
                    pct = (scanned_count / total_ports) * 100
                    yield f"Progresso: {pct:.1f}% ({scanned_count}/{total_ports}) | Velocidade: {rate:.0f} portas/s\n"

    total_time = time.time() - start_time

    if cancelled:
        yield f"\nVarredura interrompida pelo usuário após {total_time:.1f}s.\n"
    else:
        yield f"\nTeste concluído em {total_time:.2f}s (velocidade média: {total_ports / max(0.01, total_time):.0f} portas/s).\n"

    if open_ports:
        yield f"Total de portas abertas encontradas: {len(open_ports)}\n"
        yield "Resumo das portas abertas:\n"
        for p, svc in sorted(open_ports):
            yield f"  - {p}/TCP: {svc}\n"
    else:
        yield "Nenhuma porta aberta encontrada na faixa testada.\n"
