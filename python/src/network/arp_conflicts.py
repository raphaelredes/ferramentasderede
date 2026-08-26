# python/src/network/arp_conflicts.py
"""Módulo de detecção de conflitos de IP e anomalias na tabela ARP.

Inspeciona a tabela ARP do sistema para detectar se múltiplos endereços MAC
estão respondendo pelo mesmo IP ou se há gateways conflitantes.
"""

import subprocess
import re
import logging
from typing import Dict, List, Any, Optional

def inspect_arp_table(interface_ip: Optional[str] = None) -> Dict[str, Any]:
    """Lê a tabela ARP atual e verifica duplicações de IP ou múltiplos MACs."""
    arp_entries: List[Dict[str, str]] = []
    ip_to_macs: Dict[str, List[str]] = {}
    mac_to_ips: Dict[str, List[str]] = {}

    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
        startup_info.wShowWindow = 0

        proc = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=creation_flags,
            startupinfo=startup_info
        )

        
        current_interface = None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("Interface:"):
                match = re.search(r'Interface:\s*([0-9\.]+)', line)
                if match:
                    current_interface = match.group(1)
                continue

            # Match IP, MAC, Type
            match = re.search(r'([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\s+([0-9a-fA-F\-]{17})\s+(\w+)', line)
            if match:
                ip, mac, entry_type = match.groups()
                mac = mac.lower().replace("-", ":")
                
                # Ignorar broadcast/multicast (ex: 224.x, 255.255.255.255)
                if ip.endswith(".255") or ip.startswith("224.") or mac == "ff:ff:ff:ff:ff:ff":
                    continue

                if interface_ip and current_interface and current_interface != interface_ip:
                    continue

                arp_entries.append({
                    "interface": current_interface or "Default",
                    "ip": ip,
                    "mac": mac,
                    "type": entry_type
                })
                
                ip_to_macs.setdefault(ip, []).append(mac)
                mac_to_ips.setdefault(mac, []).append(ip)

    except Exception as exc:
        logging.error(f"Erro ao ler tabela ARP: {exc}")
        return {"error": str(exc), "entries": [], "conflicts": []}

    # Detectar conflitos: 1 IP associado a múltiplos MACs diferentes
    conflicts = []
    for ip, macs in ip_to_macs.items():
        unique_macs = list(set(macs))
        if len(unique_macs) > 1:
            conflicts.append({
                "type": "IP_CONFLICT",
                "ip": ip,
                "macs": unique_macs,
                "severity": "CRITICAL",
                "description": f"O endereço IP {ip} está associado a múltiplos endereços MAC ({', '.join(unique_macs)}). Possível conflito de IP estático ou ataque ARP spoofing."
            })

    return {
        "total_entries": len(arp_entries),
        "conflicts_detected": len(conflicts),
        "conflicts": conflicts,
        "entries": arp_entries
    }
