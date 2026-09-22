"""Módulo de resolução de Sistema Autônomo (ASN), Operadora e País para IPs.

Utiliza o serviço de mapeamento global de BGP via DNS da Team Cymru
(RFC 1035 UDP), sem dependência de APIs externas pagas ou chaves:
- origin.asn.cymru.com (IP -> ASN, Prefixo BGP, País)
- asn.cymru.com (ASN -> Nome do AS / Operadora de Telecom)

Inclui cache em memória com expiração e reconhecimento nativo de
espaços de endereçamento especiais (RFC 1918, CGNAT, Loopback, Link-Local).
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from typing import Dict, List, Optional, Any

try:
    import dns.resolver
    _HAS_DNSPYTHON = True
except Exception:
    _HAS_DNSPYTHON = False

# Cache em memória: { ip: (timestamp, data_dict) }
_ASN_CACHE: Dict[str, tuple[float, Dict[str, str]]] = {}
_CACHE_TTL = 3600.0  # 1 hora
_CACHE_LOCK = threading.RLock()

# Servidores DNS públicos rápidos e confiáveis para consultas Cymru
_CYMRU_SERVERS = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]


def _get_special_range_info(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Optional[Dict[str, str]]:
    """Identifica se o IP pertence a faixas privadas, reservadas ou CGNAT."""
    if ip_obj.is_loopback:
        return {"asn": "LOOPBACK", "as_name": "Interface Loopback Local", "country": "LOCAL"}
    if ip_obj.is_private:
        return {"asn": "RFC1918", "as_name": "Rede Privada (LAN / Corporativa)", "country": "LAN"}
    if ip_obj.is_link_local:
        return {"asn": "APIPA", "as_name": "Link-Local / APIPA (169.254.x.x)", "country": "LOCAL"}
    # CGNAT (RFC 6598 - 100.64.0.0/10)
    cgnat_net = ipaddress.ip_network("100.64.0.0/10")
    if ip_obj in cgnat_net:
        return {"asn": "CGNAT", "as_name": "Operadora CGNAT (RFC 6598)", "country": "WAN"}
    return None


def lookup_ip_asn(ip_str: str, timeout: float = 2.0) -> Dict[str, str]:
    """Consulta ASN, Nome da Operadora e País para um endereço IP.

    Retorna dicionário: {"asn": "AS15169", "as_name": "GOOGLE - Google LLC, US", "country": "US"}
    """
    clean_ip = ip_str.strip()
    if not clean_ip or clean_ip == "*":
        return {"asn": "—", "as_name": "—", "country": "—"}

    # Checa cache em memória
    now = time.time()
    with _CACHE_LOCK:
        if clean_ip in _ASN_CACHE:
            ts, val = _ASN_CACHE[clean_ip]
            if now - ts < _CACHE_TTL:
                return val

    # Validação de IP
    try:
        ip_obj = ipaddress.ip_address(clean_ip)
    except ValueError:
        return {"asn": "INVÁLIDO", "as_name": "Endereço IP inválido", "country": "—"}

    # Faixas reservadas / privadas
    special = _get_special_range_info(ip_obj)
    if special is not None:
        with _CACHE_LOCK:
            _ASN_CACHE[clean_ip] = (now, special)
        return special

    if not _HAS_DNSPYTHON:
        return {"asn": "DNS-N/A", "as_name": "Resolução de ASN indisponível", "country": "—"}

    # Monta consulta Team Cymru
    try:
        if ip_obj.version == 4:
            rev_octets = clean_ip.split(".")[::-1]
            cymru_query = ".".join(rev_octets) + ".origin.asn.cymru.com"
        else:
            # IPv6 reverso no formato nibbles
            nibbles = ip_obj.exploded.replace(":", "")[::-1]
            cymru_query = ".".join(nibbles) + ".origin6.asn.cymru.com"

        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = _CYMRU_SERVERS
        resolver.timeout = timeout
        resolver.lifetime = timeout

        asn = ""
        country = ""
        as_name = ""

        # 1. Obter ASN e País
        answers = resolver.resolve(cymru_query, "TXT")
        for rdata in answers:
            # Formato: "15169 | 8.8.8.0/24 | US | arin | 1992-12-01"
            txt_content = rdata.to_text().strip('"')
            parts = [p.strip() for p in txt_content.split("|")]
            if parts:
                asn = parts[0].split()[0]  # se houver múltiplos ASNs anunciados, pega o primeiro
            if len(parts) > 2:
                country = parts[2]
            break

        # 2. Obter Nome do AS / Operadora se ASN encontrado
        if asn and asn.isdigit():
            try:
                name_query = f"AS{asn}.asn.cymru.com"
                name_ans = resolver.resolve(name_query, "TXT")
                for nrdata in name_ans:
                    # Formato: "15169 | US | arin | 2000-03-30 | GOOGLE - Google LLC, US"
                    ntxt = nrdata.to_text().strip('"')
                    nparts = [np.strip() for np in ntxt.split("|")]
                    if len(nparts) >= 5:
                        as_name = nparts[4]
                    elif len(nparts) >= 1:
                        as_name = f"AS{asn}"
                    break
            except Exception:
                as_name = f"AS{asn}"

        result = {
            "asn": f"AS{asn}" if asn and asn.isdigit() else "Desconhecido",
            "as_name": as_name or (f"AS{asn}" if asn else "Operadora não identificada"),
            "country": country or "—",
        }

        with _CACHE_LOCK:
            _ASN_CACHE[clean_ip] = (now, result)
        return result

    except Exception as e:
        logging.debug(f"Falha na resolução ASN para {clean_ip}: {e}")
        fallback = {"asn": "N/D", "as_name": "Não divulgado em BGP", "country": "—"}
        # Cache curto para falhas (30s)
        with _CACHE_LOCK:
            _ASN_CACHE[clean_ip] = (now - _CACHE_TTL + 30.0, fallback)
        return fallback


def lookup_asns_batch(ips: List[str]) -> Dict[str, Dict[str, str]]:
    """Resolve múltiplos IPs em paralelo e retorna mapa { ip: {asn, as_name, country} }."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    clean_ips = list({ip.strip() for ip in ips if ip and ip.strip() and ip.strip() != "*"})

    with ThreadPoolExecutor(max_workers=min(len(clean_ips) or 1, 10)) as pool:
        future_map = {pool.submit(lookup_ip_asn, ip): ip for ip in clean_ips}
        for fut in as_completed(future_map):
            ip = future_map[fut]
            try:
                results[ip] = fut.result()
            except Exception:
                results[ip] = {"asn": "Erro", "as_name": "Falha na consulta", "country": "—"}
    return results
