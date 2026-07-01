# app/network/ptr_sweep.py
#
# Reverse-DNS (PTR) sweep over a CIDR: resolves every host address to a name in
# parallel. Turns the per-host DNS lookup into a VLAN inventory ("name
# everything in this subnet"). Pure Python via dnspython (already a dependency)
# + a ThreadPoolExecutor (the project's established 16-worker pattern).
#
# Respects a per-network `dns_server` (multi-domain correctness) — the same
# reasoning as the rest of the app: don't trust the system resolver when the
# target subnet belongs to a specific AD domain.

import ipaddress
import json
import logging
import concurrent.futures

from src.network import dns_resolver

# Same /16 cap as discovery — a PTR sweep of anything wider is an explicit batch
# job, not an interactive tool.
MAX_ADDRESSES = 65536


def ptr_sweep(cidr, dns_server=None, max_workers=16, stop_event=None):
    """Generator of NDJSON lines. Emits {"progress":...} updates and
    {"result": {ip, hostname}} for each address that resolves to a name, then a
    final {"done": True, "resolved": N, "total": M}.
    """
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        yield json.dumps({"error": "CIDR inválido."}) + "\n"
        return

    if network.num_addresses > MAX_ADDRESSES:
        yield json.dumps({
            "error": f"CIDR muito amplo ({network.num_addresses}). Limite: {MAX_ADDRESSES} (/16)."
        }) + "\n"
        return

    hosts = list(network.hosts())
    total = len(hosts)
    if total == 0:
        yield json.dumps({"done": True, "resolved": 0, "total": 0}) + "\n"
        return

    yield json.dumps({"progress": 0, "total": total, "message": f"Resolvendo {total} endereços..."}) + "\n"

    def _resolve(ip_str):
        try:
            fqdn = dns_resolver.resolve_ip(ip_str, dns_server=dns_server, timeout=2.0)
            return ip_str, fqdn
        except Exception as e:
            logging.debug(f"PTR resolve failed for {ip_str}: {e}")
            return ip_str, None

    resolved = 0
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_resolve, str(ip)): ip for ip in hosts}
        for fut in concurrent.futures.as_completed(futures):
            if stop_event is not None and stop_event.is_set():
                yield json.dumps({"cancelled": True, "resolved": resolved, "total": total}) + "\n"
                return
            done += 1
            ip_str, fqdn = fut.result()
            if fqdn:
                resolved += 1
                yield json.dumps({"result": {"ip": ip_str, "hostname": fqdn}}) + "\n"
            # Progress every 16 addresses (or at the end).
            if done % 16 == 0 or done == total:
                pct = int(done / total * 100)
                yield json.dumps({"progress": pct, "total": total, "done": done}) + "\n"

    yield json.dumps({"done": True, "resolved": resolved, "total": total}) + "\n"
