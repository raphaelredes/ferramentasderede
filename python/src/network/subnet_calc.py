# app/network/subnet_calc.py
#
# Subnet / CIDR calculator. Pure stdlib `ipaddress`. Given a CIDR (or IP/mask),
# returns network, broadcast, usable range, mask, wildcard, host count, etc.
# Optionally splits into N equal subnets. A daily convenience for a multi-VLAN
# analyst who lives in CIDRs.

import ipaddress


def calc(cidr, split_prefix=None):
    """Return a dict describing the network in `cidr`.

    `cidr` accepts '10.0.0.0/24', '10.0.0.5/24', or '10.0.0.0 255.255.255.0'.
    `split_prefix` (optional int): if given and larger than the network prefix,
    also returns the list of equal subnets at that prefix.
    """
    raw = (cidr or "").strip().replace("  ", " ")
    # Support "ip mask" form by converting to ip/prefix.
    if " " in raw:
        parts = raw.split()
        if len(parts) == 2:
            try:
                ip = ipaddress.ip_address(parts[0])
                mask = ipaddress.ip_address(parts[1])
                prefix = ipaddress.IPv4Network(f"0.0.0.0/{parts[1]}").prefixlen
                raw = f"{ip}/{prefix}"
            except ValueError:
                return {"ok": False, "error": "Formato inválido. Use CIDR ou 'IP máscara'."}

    try:
        net = ipaddress.ip_network(raw, strict=False)
    except ValueError as e:
        return {"ok": False, "error": f"CIDR inválido: {e}"}

    is_v4 = net.version == 4
    hosts_iter = list(net.hosts())
    first_host = str(hosts_iter[0]) if hosts_iter else None
    last_host = str(hosts_iter[-1]) if hosts_iter else None

    out = {
        "ok": True,
        "input": raw,
        "version": net.version,
        "network": str(net.network_address),
        "prefix": net.prefixlen,
        "netmask": str(net.netmask),
        "broadcast": str(net.broadcast_address) if is_v4 else None,
        "hostmask": str(net.hostmask),  # wildcard
        "num_addresses": net.num_addresses,
        "num_usable": max(0, len(hosts_iter)),
        "first_host": first_host,
        "last_host": last_host,
        "is_private": net.is_private,
        "cidr": str(net),
    }

    # Optional split into smaller equal subnets.
    if split_prefix is not None:
        try:
            sp = int(split_prefix)
            if sp > net.prefixlen and sp <= net.max_prefixlen:
                subnets = list(net.subnets(new_prefix=sp))
                # Cap the returned list so a /8 → /30 doesn't return millions.
                MAX_RETURN = 1024
                out["split_prefix"] = sp
                out["split_count"] = len(subnets)
                out["subnets"] = [str(s) for s in subnets[:MAX_RETURN]]
                out["split_truncated"] = len(subnets) > MAX_RETURN
            else:
                out["split_error"] = "O prefixo de divisão deve ser maior que o da rede."
        except (TypeError, ValueError):
            out["split_error"] = "Prefixo de divisão inválido."

    return out


def ip_in_network(ip, cidr):
    """Return whether `ip` belongs to `cidr` (helper for 'qual VLAN?')."""
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False
