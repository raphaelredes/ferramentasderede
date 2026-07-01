# app/network/tcp_ping.py
#
# TCP "ping": times the TCP handshake to host:port. The point is liveness +
# latency for hosts that DROP ICMP — which is the default Windows Firewall
# posture in an AD domain. Half the corporate Windows fleet "doesn't ping" but
# has 445/3389/5985 open; this tells you it's alive (and how fast) when ICMP
# lies. Pure stdlib socket.
#
# `source_ip` binds the connect to a specific NIC (multi-VLAN), matching the
# app's source_ip model used by ping/traceroute/iperf.

import socket
import time


def tcp_ping_once(host, port, timeout=2.0, source_ip=None):
    """One TCP-connect probe. Returns (success: bool, rtt_ms: float|None, detail: str)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    if source_ip:
        try:
            # Bind to the source NIC (port 0 = ephemeral). Multi-VLAN egress.
            s.bind((source_ip, 0))
        except OSError as e:
            s.close()
            return False, None, f"bind {source_ip} falhou: {e}"
    try:
        start = time.perf_counter()
        result = s.connect_ex((host, port))
        rtt = (time.perf_counter() - start) * 1000.0
        if result == 0:
            return True, rtt, "aberta"
        # Refused still proves the host is alive (it sent a RST) — but the port
        # is closed. We report it as a reachable host, port closed.
        if result in (10061,):  # WSAECONNREFUSED
            return False, rtt, "recusada (host vivo, porta fechada)"
        if result in (10060,):  # WSAETIMEDOUT
            return False, None, "timeout"
        return False, None, f"sem resposta (cod {result})"
    except socket.timeout:
        return False, None, "timeout"
    except OSError as e:
        return False, None, f"erro: {e}"
    finally:
        s.close()


def tcp_ping_stream(host, port, count=4, timeout=2.0, interval=1.0, source_ip=None):
    """Generator of human-readable lines, mirroring the ping tool's output style.

    Ends with a summary (sent/received, min/avg/max). `count<=0` would be
    unbounded; we treat <=0 as 4 to avoid an accidental infinite loop.
    """
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = 4
    if n <= 0:
        n = 4
    n = min(n, 100)  # hard cap

    yield f"TCP ping para {host}:{port} ({n}x)...\n\n"
    rtts = []
    received = 0
    for i in range(n):
        ok, rtt, detail = tcp_ping_once(host, port, timeout=timeout, source_ip=source_ip)
        if ok and rtt is not None:
            received += 1
            rtts.append(rtt)
            yield f"  resposta de {host}:{port} — tempo={rtt:.1f} ms [{detail}]\n"
        elif rtt is not None:
            # Refused-but-alive: count as a reply for liveness, not for latency.
            yield f"  {host}:{port} — {detail} (tempo={rtt:.1f} ms)\n"
        else:
            yield f"  {host}:{port} — {detail}\n"
        if i < n - 1:
            time.sleep(max(0.0, interval))

    lost = n - received
    loss_pct = (lost / n * 100) if n else 0
    yield f"\nEstatísticas TCP para {host}:{port}:\n"
    yield f"    Tentativas = {n}, Respostas = {received}, Perdidas = {lost} ({loss_pct:.0f}% de perda)\n"
    if rtts:
        yield f"    Mínimo = {min(rtts):.1f} ms, Máximo = {max(rtts):.1f} ms, Média = {sum(rtts)/len(rtts):.1f} ms\n"
