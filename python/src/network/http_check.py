# python/src/network/http_check.py
"""Diagnóstico HTTP de alta precisão com decomposição de tempos estilo 'curl -w',

Auditoria de Cabeçalhos de Segurança OWASP e Rastreamento de Cadeia de Redirecionamentos.
"""

import socket
import ssl
import time
import logging
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional

try:
    import requests
    _HAS_REQUESTS = True
except Exception as e:  # pragma: no cover
    _HAS_REQUESTS = False
    logging.warning(f"requests indisponível: {e}")


def _measure_socket_phases(scheme: str, host: str, port: int, timeout: float = 5.0, verify_tls: bool = True):
    """Mede com precisão os tempos de DNS, TCP Handshake e TLS Handshake."""
    dns_ms = None
    tcp_ms = None
    tls_ms = None
    resolved_ip = None

    # Fase 1: Resolução DNS
    t_dns_start = time.perf_counter()
    try:
        addrinfo = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        dns_ms = round((time.perf_counter() - t_dns_start) * 1000.0, 2)
        if addrinfo:
            resolved_ip = addrinfo[0][4][0]
    except Exception as e:
        dns_ms = round((time.perf_counter() - t_dns_start) * 1000.0, 2)
        return dns_ms, tcp_ms, tls_ms, resolved_ip

    if not resolved_ip:
        return dns_ms, tcp_ms, tls_ms, None

    # Fase 2: TCP Handshake (SYN -> SYN/ACK)
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        t_tcp_start = time.perf_counter()
        sock.connect((resolved_ip, port))
        tcp_ms = round((time.perf_counter() - t_tcp_start) * 1000.0, 2)

        # Fase 3: TLS Handshake (Client Hello -> Key Exchange)
        if scheme == "https":
            t_tls_start = time.perf_counter()
            ctx = ssl.create_default_context()
            if not verify_tls:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            try:
                ssock = ctx.wrap_socket(sock, server_hostname=host)
                tls_ms = round((time.perf_counter() - t_tls_start) * 1000.0, 2)
                ssock.close()
                sock = None
            except Exception:
                tls_ms = round((time.perf_counter() - t_tls_start) * 1000.0, 2)
    except Exception:
        pass
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass

    return dns_ms, tcp_ms, tls_ms, resolved_ip


def audit_security_headers(headers: Dict[str, str]) -> Dict[str, Any]:
    """Audita os principais cabeçalhos de segurança recomendados pela OWASP e Mozilla."""
    # Converter chaves para case-insensitive
    h_lower = {k.lower(): v for k, v in headers.items()}

    hsts = h_lower.get("strict-transport-security")
    csp = h_lower.get("content-security-policy")
    xfo = h_lower.get("x-frame-options")
    xcto = h_lower.get("x-content-type-options")
    rp = h_lower.get("referrer-policy")
    pp = h_lower.get("permissions-policy")

    audit = [
        {
            "id": "hsts",
            "name": "Strict-Transport-Security (HSTS)",
            "present": bool(hsts),
            "value": hsts or "Ausente",
            "status": "pass" if bool(hsts) else "warning",
            "desc": "Força navegadores a utilizarem apenas HTTPS, protegendo contra SSL Stripping.",
        },
        {
            "id": "csp",
            "name": "Content-Security-Policy (CSP)",
            "present": bool(csp),
            "value": (csp[:120] + "...") if csp and len(csp) > 120 else (csp or "Ausente"),
            "status": "pass" if bool(csp) else "warning",
            "desc": "Restringe as origens de scripts, imagens e conexões, prevenindo ataques XSS.",
        },
        {
            "id": "xfo",
            "name": "X-Frame-Options",
            "present": bool(xfo),
            "value": xfo or "Ausente",
            "status": "pass" if bool(xfo) and xfo.upper() in ("DENY", "SAMEORIGIN") else "warning",
            "desc": "Impede que o site seja inserido em iframes maliciosos (proteção contra Clickjacking).",
        },
        {
            "id": "xcto",
            "name": "X-Content-Type-Options",
            "present": bool(xcto),
            "value": xcto or "Ausente",
            "status": "pass" if bool(xcto) and "nosniff" in xcto.lower() else "warning",
            "desc": "Impede que navegadores adivinhem o MIME-type de arquivos, prevenindo execução indevida.",
        },
        {
            "id": "rp",
            "name": "Referrer-Policy",
            "present": bool(rp),
            "value": rp or "Ausente",
            "status": "pass" if bool(rp) else "info",
            "desc": "Controla quanta informação de URL é enviada no cabeçalho Referer em requisições externas.",
        },
        {
            "id": "pp",
            "name": "Permissions-Policy",
            "present": bool(pp),
            "value": (pp[:120] + "...") if pp and len(pp) > 120 else (pp or "Ausente"),
            "status": "pass" if bool(pp) else "info",
            "desc": "Controla o acesso da página a recursos do dispositivo (câmera, microfone, geolocalização).",
        }
    ]

    passed_count = sum(1 for item in audit if item["status"] == "pass")
    total_count = len(audit)

    grade = "A" if passed_count >= 5 else "B" if passed_count >= 3 else "C" if passed_count >= 2 else "D"

    return {
        "headers": audit,
        "passed": passed_count,
        "total": total_count,
        "grade": grade
    }


def check(url: str, method: str = "GET", timeout: float = 10.0, verify_tls: bool = True) -> Dict[str, Any]:
    """Retorna diagnóstico completo do endpoint HTTP:

    - Waterfall de 5 fases (DNS, TCP, TLS, TTFB, Transferência)
    - Auditoria de Headers de Segurança OWASP
    - Cadeia de Redirecionamentos
    - Metadados do Servidor
    """
    if not _HAS_REQUESTS:
        return {"ok": False, "error": "requests indisponível no ambiente."}

    u = (url or "").strip()
    if not u:
        return {"ok": False, "error": "Informe uma URL para teste."}

    if not u.lower().startswith(("http://", "https://")):
        u = "http://" + u

    m = (method or "GET").upper()
    if m not in ("GET", "HEAD"):
        m = "GET"

    parsed = urlparse(u)
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)

    if not host:
        return {"ok": False, "error": f"URL inválida: não foi possível extrair o host de '{u}'."}

    # 1. Medir DNS, TCP e TLS
    dns_ms, tcp_ms, tls_ms, resolved_ip = _measure_socket_phases(
        scheme, host, port, timeout=min(timeout, 5.0), verify_tls=verify_tls
    )

    # 2. Executar requisição HTTP completa para coletar TTFB, resposta e headers
    t_req_start = time.perf_counter()
    try:
        session = requests.Session()
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 FerramentasDeRede/HealthCheck"
        }

        ssl_warning = None
        try:
            resp = session.request(
                m, u, timeout=timeout, verify=verify_tls,
                allow_redirects=True,
                headers=req_headers,
                stream=True
            )
        except requests.exceptions.SSLError as ssl_err:
            # Fallback tolerante para redes corporativas com proxy/inspeção SSL ou certificados auto-assinados
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            try:
                resp = session.request(
                    m, u, timeout=timeout, verify=False,
                    allow_redirects=True,
                    headers=req_headers,
                    stream=True
                )
                ssl_warning = f"Aviso de Certificado: Cadeia não verificada (Proxy corporativo ou certificado auto-assinado: {ssl_err})"
            except Exception as inner_err:
                return {"ok": False, "error": f"Erro de Certificado SSL/TLS: {inner_err}"}

        t_headers_received = time.perf_counter()
        ttfb_ms = round((t_headers_received - t_req_start) * 1000.0, 2)

        # Download do corpo
        body_bytes = b""
        try:
            body_bytes = resp.content
            content_len = len(body_bytes)
        except Exception:
            content_len = None

        t_body_done = time.perf_counter()
        download_ms = round((t_body_done - t_headers_received) * 1000.0, 2)
        total_ms = round((t_body_done - t_req_start) * 1000.0, 2)

        # Ajuste de tempos relativos para o Waterfall
        # Se dns_ms + tcp_ms + tls_ms somados formam o handshake inicial,
        # o tempo de processamento puro do servidor no TTFB é (ttfb_ms - connect_time)
        connect_time = (tcp_ms or 0) + (tls_ms or 0)
        server_processing_ms = max(0.5, round(ttfb_ms - connect_time, 2)) if connect_time > 0 else ttfb_ms

        status = resp.status_code
        final_url = resp.url
        server_header = resp.headers.get("Server")
        content_type = resp.headers.get("Content-Type")

        # Rastrear cadeia de redirecionamentos
        redirects: List[Dict[str, Any]] = []
        if resp.history:
            for hist in resp.history:
                redirects.append({
                    "status": hist.status_code,
                    "url": hist.url,
                    "location": hist.headers.get("Location")
                })
            # Incluir o nó final
            redirects.append({
                "status": resp.status_code,
                "url": resp.url,
                "location": None
            })

        # Auditoria OWASP dos cabeçalhos
        sec_audit = audit_security_headers(dict(resp.headers))

        resp.close()

        return {
            "ok": True,
            "url": u,
            "final_url": final_url,
            "resolved_ip": resolved_ip,
            "method": m,
            "status": status,
            "server": server_header,
            "content_type": content_type,
            "content_length": content_len,
            "redirected": len(resp.history) > 0,
            "redirects": redirects,
            "timing": {
                "dns_ms": dns_ms,
                "tcp_ms": tcp_ms,
                "tls_ms": tls_ms,
                "server_processing_ms": server_processing_ms,
                "ttfb_ms": ttfb_ms,
                "download_ms": download_ms,
                "total_ms": total_ms,
            },
            "security": sec_audit,
            "ssl_warning": ssl_warning,
            # Campos retrocompatíveis para o frontend anterior
            "ttfb_ms": ttfb_ms,
            "elapsed_ms": total_ms,
        }

    except requests.exceptions.SSLError as e:
        return {"ok": False, "error": f"Erro de Certificado SSL/TLS: {e}"}
    except requests.exceptions.ConnectTimeout:
        return {"ok": False, "error": "Tempo limite esgotado ao tentar estabelecer conexão TCP."}
    except requests.exceptions.ReadTimeout:
        return {"ok": False, "error": "Tempo limite esgotado aguardando resposta do servidor (Read Timeout)."}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"Falha de conexão com o host: {e}"}
    except Exception as e:
        logging.error(f"Erro em check_http: {e}")
        return {"ok": False, "error": f"Erro: {str(e)}"}
