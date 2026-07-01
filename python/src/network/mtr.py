# app/network/mtr.py
#
# MTR-style path monitor WITHOUT any third-party ICMP library — uses only the
# OS-native `tracert`/`traceroute` and `ping` via subprocess, so the distributed
# portable stays 100% permissively licensed (no LGPL icmplib).
#
# Strategy:
#   1. Run a native traceroute ONCE to discover the ordered list of hop IPs to
#      the target (the path). On Windows: `tracert -d -h <max> <target>`.
#   2. Each cycle, ping every discovered hop IP directly (native `ping`), in
#      parallel, and fold the result into a rolling per-hop table (loss / last /
#      avg / best / worst / jitter) — exactly what mtr shows.
#
# This is the standard "ping each hop" MTR technique. It needs no raw sockets
# and no admin (native ping works as a normal user), and `source_ip` selects
# the egress NIC (multi-VLAN) via ping's -S flag.
#
# Tradeoff vs a raw-socket MTR: hops that reply to the TTL-probe of traceroute
# but drop direct ICMP echo will show as 100% loss here. That's the same caveat
# every "ping-per-hop" MTR has, and is acceptable for a diagnostics tool.

import os
import re
import json
import logging
import subprocess
import concurrent.futures

MAX_HOPS = 30
PROBES_PER_CYCLE = 3          # pings to each hop per cycle
PER_PING_TIMEOUT_MS = 1000    # per-ping wait

_IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
# Latency token in ping output, PT-BR + EN: "tempo=12ms", "time=12ms", "tempo<1ms".
_LAT_RE = re.compile(r"(?:tempo|time)[=<]\s*(\d+)\s*ms", re.IGNORECASE)


def _creationflags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _discover_hops(target, max_hops, source_ip=None, timeout=60):
    """Run native traceroute once; return an ordered list of hop dicts:
    [{"distance": ttl, "address": ip_or_None}]. A non-responding hop yields
    address=None so the table can still show a '*' row for it."""
    if os.name == "nt":
        # -d = no DNS (fast), -h max hops, -w per-hop wait.
        cmd = ["tracert", "-d", "-h", str(max_hops), "-w", "1500"]
        if source_ip:
            cmd += ["-S", source_ip]   # Windows tracert source address
        cmd.append(target)
        encoding = "cp850"
    else:
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", "2"]
        if source_ip:
            cmd += ["-s", source_ip]
        cmd.append(target)
        encoding = "utf-8"

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding=encoding,
            errors="replace", creationflags=_creationflags(), timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return []
    except Exception as e:
        logging.debug(f"MTR traceroute discovery failed for {target}: {e}")
        return []

    hops = []
    distance = 0
    for line in result.stdout.splitlines():
        stripped = line.strip()
        # A hop line starts with the TTL number (Windows: "  1    <1 ms ...";
        # Linux: " 1  10.0.0.1 ..."). Use the leading integer as the TTL.
        m = re.match(r"^\s*(\d+)\s", line)
        if not m:
            continue
        ttl = int(m.group(1))
        # Guard against runaway / header lines that happen to start with a digit.
        if ttl < 1 or ttl > max_hops:
            continue
        distance = ttl
        # Find the first IPv4 on the line that ISN'T the target echoed in a header.
        ips = _IPV4_RE.findall(line)
        # Windows "Request timed out" / PT-BR "Esgotado" rows have no IP → '*'.
        addr = ips[-1] if ips else None
        hops.append({"distance": ttl, "address": addr})
        # Stop once we reach the target itself.
        if addr and addr == target:
            break

    # Deduplicate by distance keeping order (tracert prints one line per TTL).
    seen = set()
    ordered = []
    for h in hops:
        if h["distance"] in seen:
            continue
        seen.add(h["distance"])
        ordered.append(h)
    return ordered


def _ping_host(ip, count, source_ip=None):
    """Native ping `ip` `count` times. Returns (sent, received, [rtts_ms])."""
    if os.name == "nt":
        cmd = ["ping", "-4", "-n", str(count), "-w", str(PER_PING_TIMEOUT_MS)]
        if source_ip:
            cmd += ["-S", source_ip]
        cmd.append(ip)
        encoding = "cp850"
    else:
        cmd = ["ping", "-4", "-c", str(count), "-W", str(max(1, PER_PING_TIMEOUT_MS // 1000))]
        if source_ip:
            cmd += ["-I", source_ip]
        cmd.append(ip)
        encoding = "utf-8"

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding=encoding,
            errors="replace", creationflags=_creationflags(),
            timeout=(PER_PING_TIMEOUT_MS / 1000.0) * count + 3,
        )
    except subprocess.TimeoutExpired:
        return count, 0, []
    except Exception as e:
        logging.debug(f"MTR ping {ip} failed: {e}")
        return count, 0, []

    rtts = [int(x) for x in _LAT_RE.findall(result.stdout)]
    received = len(rtts)
    return count, received, rtts


class _HopAccumulator:
    """Rolling per-hop stats keyed by distance (TTL). Jitter is computed per
    cycle (intra-cycle mean |Δ|) and averaged — never across cycle boundaries."""

    def __init__(self):
        self._hops = {}

    def ensure(self, distance, address):
        h = self._hops.get(distance)
        if h is None:
            h = {"distance": distance, "address": address, "sent": 0,
                 "received": 0, "rtts": [], "jitter_sum": 0.0, "jitter_n": 0}
            self._hops[distance] = h
        elif address:
            h["address"] = address
        return h

    def update(self, distance, address, sent, received, rtts):
        h = self.ensure(distance, address)
        h["sent"] += sent
        h["received"] += received
        if rtts:
            if len(rtts) > 1:
                diffs = [abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))]
                h["jitter_sum"] += sum(diffs) / len(diffs)
                h["jitter_n"] += 1
            h["rtts"].extend(rtts)
            if len(h["rtts"]) > 100:
                h["rtts"] = h["rtts"][-100:]

    def snapshot(self):
        rows = []
        for distance in sorted(self._hops.keys()):
            h = self._hops[distance]
            rtts = h["rtts"]
            sent = h["sent"]
            received = h["received"]
            loss_pct = (100.0 * (sent - received) / sent) if sent else 0.0
            if rtts:
                last, best, worst = rtts[-1], min(rtts), max(rtts)
                avg = sum(rtts) / len(rtts)
                jitter = (h["jitter_sum"] / h["jitter_n"]) if h["jitter_n"] else 0.0
            else:
                last = best = worst = avg = jitter = None
            rows.append({
                "hop": distance,
                "address": h["address"] or "*",
                "loss_pct": round(loss_pct, 1),
                "sent": sent,
                "last": round(last, 2) if last is not None else None,
                "avg": round(avg, 2) if avg is not None else None,
                "best": round(best, 2) if best is not None else None,
                "worst": round(worst, 2) if worst is not None else None,
                "jitter": round(jitter, 2) if jitter is not None else None,
            })
        return rows


def run_mtr(target, source_ip=None, max_hops=MAX_HOPS, stop_event=None):
    """Generator yielding NDJSON lines: one {"hops":[...]} object per cycle.
    Native traceroute+ping only (no icmplib). Runs until stop_event is set or
    the consumer closes the generator."""
    try:
        hops_cap = max(1, min(int(max_hops), MAX_HOPS))
    except (TypeError, ValueError):
        hops_cap = MAX_HOPS

    yield json.dumps({"status": "started", "target": target}) + "\n"

    # 1. Discover the path once.
    discovered = _discover_hops(target, hops_cap, source_ip=source_ip)
    if not discovered:
        yield json.dumps({
            "error": ("Não foi possível traçar a rota (alvo inacessível, sem "
                      "permissão, ou bloqueando ICMP).")
        }) + "\n"
        return

    acc = _HopAccumulator()
    # Seed the table so every hop shows immediately (even before its first ping).
    for h in discovered:
        acc.ensure(h["distance"], h["address"])
    # Only hops with a known IP can be pinged directly; '*' hops stay in the
    # table but accrue no stats.
    pingable = [(h["distance"], h["address"]) for h in discovered if h["address"]]

    yield json.dumps({"hops": acc.snapshot()}) + "\n"

    # 2. Each cycle: ping every pingable hop in parallel, fold into the table.
    while stop_event is None or not stop_event.is_set():
        try:
            if not pingable:
                # Nothing to measure (all hops anonymous) — emit and stop.
                yield json.dumps({"hops": acc.snapshot()}) + "\n"
                return

            max_workers = min(16, len(pingable))
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                future_map = {
                    ex.submit(_ping_host, addr, PROBES_PER_CYCLE, source_ip): (dist, addr)
                    for dist, addr in pingable
                }
                for fut in concurrent.futures.as_completed(future_map):
                    dist, addr = future_map[fut]
                    if stop_event is not None and stop_event.is_set():
                        break
                    try:
                        sent, received, rtts = fut.result()
                    except Exception as e:
                        logging.debug(f"MTR hop ping future failed: {e}")
                        sent, received, rtts = PROBES_PER_CYCLE, 0, []
                    results[dist] = (addr, sent, received, rtts)

            for dist, (addr, sent, received, rtts) in results.items():
                acc.update(dist, addr, sent, received, rtts)

            yield json.dumps({"hops": acc.snapshot()}) + "\n"
        except GeneratorExit:
            return
        except Exception as e:
            logging.debug(f"MTR cycle error for {target}: {e}")
            yield json.dumps({"error": f"Erro no MTR: {e}"}) + "\n"
            return
