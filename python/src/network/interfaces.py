"""Local NIC enumeration for multi-domain / multi-VLAN environments.

Returns the IPv4 interfaces with their CIDR so the user (or auto-detection)
can populate the configured `networks` list.
"""
import ipaddress
import logging
from typing import List, Dict, Any

import psutil


def _netmask_to_prefix(netmask: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask}", strict=False).prefixlen
    except (ipaddress.NetmaskValueError, ValueError):
        return 24


def list_local_interfaces() -> List[Dict[str, Any]]:
    """Enumerate IPv4 interfaces that are up and have an address.

    Each entry has: name, ip, netmask, prefix, cidr, network, is_up, mac.
    Loopback and link-local (169.254.x.x) interfaces are skipped.
    """
    results: List[Dict[str, Any]] = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
    except Exception as e:
        logging.exception(f"Falha ao enumerar interfaces: {e}")
        return results

    for nic_name, nic_addrs in addrs.items():
        is_up = stats.get(nic_name).isup if nic_name in stats else False
        if not is_up:
            continue

        ipv4 = next((a for a in nic_addrs if a.family.name == "AF_INET"), None)
        if not ipv4:
            continue
        if ipv4.address.startswith("127.") or ipv4.address.startswith("169.254."):
            continue

        mac = next((a.address for a in nic_addrs if a.family.name in ("AF_LINK", "AF_PACKET")), None)

        prefix = _netmask_to_prefix(ipv4.netmask) if ipv4.netmask else 24
        try:
            network = ipaddress.ip_network(f"{ipv4.address}/{prefix}", strict=False)
            cidr = str(network)
        except ValueError:
            continue

        results.append({
            "name": nic_name,
            "ip": ipv4.address,
            "netmask": ipv4.netmask,
            "prefix": prefix,
            "cidr": cidr,
            "network": str(network.network_address),
            "broadcast": str(network.broadcast_address) if network.broadcast_address else None,
            "is_up": is_up,
            "mac": mac,
        })

    return results
