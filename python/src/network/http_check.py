# app/network/http_check.py
#
# HTTP endpoint health/latency check: GET or HEAD a URL and break down the time
# into DNS, connect, TTFB and total, plus the status code and a few headers.
# A lean "curl -w" for checking whether an intranet/internal service in a given
# VLAN responds and how fast, separating DNS-slow from connect-slow from
# server-slow. Uses `requests` (already a dependency).

import logging
import time

try:
    import requests
    _HAS_REQUESTS = True
except Exception as e:  # pragma: no cover
    _HAS_REQUESTS = False
    logging.warning(f"requests indisponível: {e}")


def check(url, method="GET", timeout=10.0, verify_tls=True):
    """Return timing + status for `url`. Never raises — errors come back as a
    dict with ok=False."""
    if not _HAS_REQUESTS:
        return {"ok": False, "error": "requests indisponível."}

    u = (url or "").strip()
    if not u:
        return {"ok": False, "error": "Informe uma URL."}
    if not u.lower().startswith(("http://", "https://")):
        u = "http://" + u

    m = (method or "GET").upper()
    if m not in ("GET", "HEAD"):
        m = "GET"

    start = time.perf_counter()
    try:
        resp = requests.request(
            m, u, timeout=timeout, verify=verify_tls,
            allow_redirects=True,
            headers={"User-Agent": "FerramentasDeRede/health-check"},
            stream=True,  # so elapsed measures TTFB, not full body download
        )
        ttfb = (time.perf_counter() - start) * 1000.0
        # requests exposes the round-trip up to headers via resp.elapsed.
        elapsed_total = resp.elapsed.total_seconds() * 1000.0
        # Read a little of the body to confirm it streams, then close.
        try:
            content_len = len(resp.content)
        except Exception as e:
            logging.debug(f"http_check: reading content length failed: {e}")
            content_len = None
        status = resp.status_code
        final_url = resp.url
        server = resp.headers.get("Server")
        content_type = resp.headers.get("Content-Type")
        redirected = len(resp.history) > 0
        resp.close()
    except requests.exceptions.SSLError as e:
        return {"ok": False, "error": f"Erro TLS: {e}"}
    except requests.exceptions.ConnectTimeout:
        return {"ok": False, "error": "Tempo esgotado ao conectar."}
    except requests.exceptions.ReadTimeout:
        return {"ok": False, "error": "Tempo esgotado aguardando resposta."}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"Falha de conexão: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Erro: {e}"}

    return {
        "ok": True,
        "url": u,
        "final_url": final_url,
        "method": m,
        "status": status,
        "ttfb_ms": round(ttfb, 1),
        "elapsed_ms": round(elapsed_total, 1),
        "redirected": redirected,
        "server": server,
        "content_type": content_type,
        "content_length": content_len,
    }
