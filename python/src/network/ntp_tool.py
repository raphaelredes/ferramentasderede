# app/network/ntp_tool.py
#
# NTP query: asks a time server for its time and reports the local clock offset,
# stratum, delay, and root dispersion. ntplib (MIT, pure Python).
#
# WHY this is in an AD-focused tool: Kerberos breaks when the client clock skews
# more than ~5 minutes from the KDC. "Why does Kerberos auth fail?" is very
# often a clock-offset problem — this lets the analyst check a domain time
# source's offset directly.

import logging

try:
    import ntplib
    _HAS_NTPLIB = True
except Exception as e:  # pragma: no cover
    _HAS_NTPLIB = False
    logging.warning(f"ntplib indisponível: {e}")


def query(server, timeout=5.0, version=3):
    """Query an NTP `server`. Returns a dict with offset/stratum/delay or error."""
    if not _HAS_NTPLIB:
        return {"ok": False, "error": "ntplib indisponível."}
    if not server or not server.strip():
        return {"ok": False, "error": "Informe um servidor NTP."}

    client = ntplib.NTPClient()
    try:
        resp = client.request(server.strip(), version=version, timeout=timeout)
    except ntplib.NTPException as e:
        return {"ok": False, "error": f"Erro NTP: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Falha ao consultar {server}: {e}"}

    # offset > 0 means the local clock is BEHIND the server by that many seconds.
    offset = resp.offset
    return {
        "ok": True,
        "server": server.strip(),
        "offset_seconds": round(offset, 4),
        "offset_ms": round(offset * 1000.0, 1),
        "delay_ms": round(resp.delay * 1000.0, 1),
        "stratum": resp.stratum,
        "ref_id": ntplib.ref_id_to_text(resp.ref_id, resp.stratum),
        "root_delay_ms": round(resp.root_delay * 1000.0, 1),
        "root_dispersion_ms": round(resp.root_dispersion * 1000.0, 1),
        "precision": resp.precision,
        # Kerberos tolerance is typically 300s. Flag when the offset would break it.
        "kerberos_risk": abs(offset) > 300,
    }
