# app/network/pmtu.py
#
# Path MTU discovery: finds the largest packet that traverses the path to a
# target WITHOUT fragmentation, via a binary search on the ICMP payload size
# with the Don't-Fragment bit set.
#
# WHY native `ping -f` instead of icmplib: the DF bit is the whole point of
# PMTU, and icmplib's high-level ping() does NOT expose a don't-fragment option.
# Windows `ping -f -l <n>` sets DF and reports "Packet needs to be fragmented
# but DF set" when the size exceeds the path MTU — exactly the signal we binary-
# search on. Runs as a normal user; no raw socket / admin needed.
#
# `source_ip` selects the egress NIC (multi-VLAN) via ping's -S flag.
#
# Reported MTU = payload_found + 28 (20 IPv4 header + 8 ICMP header).

import os
import subprocess
import re
import logging

ICMP_IP_OVERHEAD = 28  # 20 (IPv4) + 8 (ICMP echo)

# Search bounds on the ICMP *payload* size. 1472 payload = 1500 MTU (standard
# Ethernet). We search [0, 1472] by default; jumbo frames are out of scope for
# a path-MTU-to-target tool (and most paths cap at 1500 anyway).
MIN_PAYLOAD = 0
MAX_PAYLOAD = 1472


def _ping_df(target, payload_size, source_ip=None, timeout_ms=1500):
    """Send ONE DF-set ping with the given payload size.

    Returns one of: 'ok' (got a reply — fits), 'too_big' (DF/fragmentation
    needed — too large), 'no_reply' (timeout/unreachable — inconclusive).
    """
    if os.name != "nt":
        # Linux: ping -M do -s <size> -c 1
        cmd = ["ping", "-4", "-M", "do", "-s", str(payload_size), "-c", "1",
               "-W", str(max(1, timeout_ms // 1000)), target]
    else:
        cmd = ["ping", "-4", "-f", "-l", str(payload_size), "-n", "1",
               "-w", str(timeout_ms)]
        if source_ip:
            cmd += ["-S", source_ip]
        cmd.append(target)

    if os.name != "nt" and source_ip:
        cmd[1:1] = ["-I", source_ip]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="cp850" if os.name == "nt" else "utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=(timeout_ms / 1000.0) + 2,
        )
    except subprocess.TimeoutExpired:
        return "no_reply"
    except Exception as e:
        logging.debug(f"pmtu ping failed ({payload_size}B): {e}")
        return "no_reply"

    out = (result.stdout or "") + (result.stderr or "")
    low = out.lower()

    # "Too big" signals (PT-BR + EN + Linux).
    if ("fragmented" in low or "fragmentar" in low or "fragmentado" in low
            or "message too long" in low or "frag needed" in low
            or "precisa ser fragmentado" in low):
        return "too_big"

    # Success signals: a real echo reply with a time.
    if (("tempo=" in low or "time=" in low or "tempo<" in low or "time<" in low)
            or "bytes=" in low or "bytes from" in low):
        return "ok"

    # Windows returns rc 0 only on a real reply; a non-zero rc with no frag
    # message is usually a timeout/unreachable.
    if result.returncode == 0 and ("reply" in low or "resposta" in low):
        return "ok"
    return "no_reply"


def discover_pmtu(target, source_ip=None):
    """Generator of human-readable progress lines, ending with the discovered
    path MTU. Binary search over the DF payload size."""
    yield f"Descobrindo o Path MTU até {target}...\n\n"

    # Sanity: make sure the host answers a tiny DF ping at all.
    probe = _ping_df(target, 0, source_ip=source_ip)
    if probe == "no_reply":
        yield ("O alvo não respondeu nem ao menor pacote. Pode estar offline ou "
               "bloqueando ICMP — o Path MTU discovery por ICMP não é possível "
               "neste caso.\n")
        return

    lo, hi = MIN_PAYLOAD, MAX_PAYLOAD

    # Confirm the upper bound's status to frame the search.
    top = _ping_df(target, hi, source_ip=source_ip)
    if top == "ok":
        mtu = hi + ICMP_IP_OVERHEAD
        yield f"Pacote máximo padrão (1472B payload) passou sem fragmentar.\n"
        yield f"\nPath MTU = {mtu} bytes (payload {hi} + {ICMP_IP_OVERHEAD} de cabeçalho).\n"
        return

    # Binary search for the largest payload that returns 'ok'.
    best = lo
    steps = 0
    while lo <= hi and steps < 16:  # 16 steps covers the whole 0..1472 range
        steps += 1
        mid = (lo + hi) // 2
        status = _ping_df(target, mid, source_ip=source_ip)
        if status == "ok":
            best = mid
            lo = mid + 1
            yield f"  {mid + ICMP_IP_OVERHEAD}B passou — subindo...\n"
        elif status == "too_big":
            hi = mid - 1
            yield f"  {mid + ICMP_IP_OVERHEAD}B fragmentaria — descendo...\n"
        else:
            # Inconclusive at this size; nudge down to keep the search moving.
            hi = mid - 1
            yield f"  {mid + ICMP_IP_OVERHEAD}B inconclusivo — descendo...\n"

    mtu = best + ICMP_IP_OVERHEAD
    yield f"\nPath MTU até {target} = {mtu} bytes.\n"
    if mtu < 1500:
        yield (f"Atenção: menor que o padrão Ethernet (1500). Indica um enlace "
               f"com MTU reduzido no caminho (VPN/túnel/VLAN) — possível causa "
               f"de 'conecta mas trava em transferências grandes'.\n")
