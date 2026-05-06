"""DNS resolution helpers for multi-domain environments.

In a network with two AD domains (e.g. dominio-a.local and dominio-b.local),
the same hostname may exist on both, so we cannot trust the system resolver
to pick the right one. This module lets us query a specific DNS server when
we know which domain a host belongs to.

Uses dnspython if available, falls back to socket so the app keeps working
even if `pip install -r requirements.txt` was not re-run after this change.
"""
from __future__ import annotations

import logging
import socket
from typing import Optional, Tuple

try:
    import dns.resolver
    import dns.reversename
    import dns.exception
    _HAS_DNSPYTHON = True
except ImportError:
    _HAS_DNSPYTHON = False
    logging.info("dnspython não instalado — usando socket como fallback. Rode `pip install -r requirements.txt`.")
except Exception as _dns_init_err:
    # dnspython on Windows + Python 3.13 may fail at import time when its
    # optional `wmi` helper crashes ("Sintaxe inválida" via pywintypes).
    # We don't need WMI for our use case, so degrade gracefully.
    _HAS_DNSPYTHON = False
    logging.warning(
        f"dnspython não pôde ser importado ({_dns_init_err.__class__.__name__}: {_dns_init_err}). "
        "Caindo para resolver do sistema."
    )


def _make_resolver(dns_server: Optional[str], timeout: float):
    """Build a dns.resolver.Resolver pointing at `dns_server` (or system default)."""
    resolver = dns.resolver.Resolver(configure=dns_server is None)
    if dns_server:
        resolver.nameservers = [dns_server]
    resolver.timeout = timeout
    resolver.lifetime = timeout
    return resolver


def resolve_hostname(
    hostname: str,
    dns_server: Optional[str] = None,
    domain: Optional[str] = None,
    timeout: float = 2.0,
) -> Optional[str]:
    """Resolve hostname → IPv4. Tries `hostname.domain` if `domain` is given.

    Returns the IP string, or None on failure.
    """
    if not hostname:
        return None

    candidates = [hostname]
    if domain and "." not in hostname:
        candidates.append(f"{hostname}.{domain}")

    if _HAS_DNSPYTHON:
        try:
            resolver = _make_resolver(dns_server, timeout)
            for name in candidates:
                try:
                    answers = resolver.resolve(name, "A")
                    for rdata in answers:
                        return rdata.address
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    continue
                except dns.exception.DNSException as e:
                    logging.debug(f"DNS error for {name} via {dns_server or 'system'}: {e}")
                    continue
        except Exception as e:
            logging.warning(f"resolve_hostname dnspython failed: {e}")

    # Fallback — system resolver. Cannot honor `dns_server`.
    if dns_server:
        logging.warning(f"dnspython indisponível; ignorando dns_server={dns_server} para {hostname}")
    for name in candidates:
        try:
            return socket.gethostbyname(name)
        except socket.gaierror:
            continue
    return None


def resolve_ip(
    ip: str,
    dns_server: Optional[str] = None,
    timeout: float = 2.0,
) -> Optional[str]:
    """Reverse-resolve IP → FQDN, optionally via a specific DNS server."""
    if not ip:
        return None

    if _HAS_DNSPYTHON:
        try:
            resolver = _make_resolver(dns_server, timeout)
            rev = dns.reversename.from_address(ip)
            answers = resolver.resolve(rev, "PTR")
            for rdata in answers:
                fqdn = str(rdata.target).rstrip(".")
                if fqdn:
                    return fqdn
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return None
        except dns.exception.DNSException as e:
            logging.debug(f"PTR error for {ip} via {dns_server or 'system'}: {e}")
        except Exception as e:
            logging.warning(f"resolve_ip dnspython failed: {e}")

    if dns_server:
        logging.warning(f"dnspython indisponível; ignorando dns_server={dns_server} para PTR {ip}")
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except (socket.herror, socket.gaierror):
        return None


def split_fqdn(fqdn: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """('host.dom.tld', ...) -> ('host', 'dom.tld'). Returns (None, None) if empty."""
    if not fqdn:
        return None, None
    parts = fqdn.split(".", 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]
