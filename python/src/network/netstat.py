# app/network/netstat.py
#
# Local connection table (netstat -ano + process name) via psutil. Shows TCP/UDP
# endpoints with owning PID and process name. Pure Python (psutil, already a
# dependency).
#
# NOTE on privilege: psutil.net_connections() returns connections for OTHER
# users' processes only when elevated; un-elevated it still returns the current
# process/user's connections and raises AccessDenied for the rest (we degrade
# gracefully and just skip what we can't see).

import logging
import psutil


# Friendly names for the numeric TCP states psutil reports.
_STATE_PT = {
    "ESTABLISHED": "ESTABELECIDA",
    "LISTEN": "OUVINDO",
    "TIME_WAIT": "TIME_WAIT",
    "CLOSE_WAIT": "CLOSE_WAIT",
    "SYN_SENT": "SYN_SENT",
    "SYN_RECV": "SYN_RECV",
    "FIN_WAIT1": "FIN_WAIT1",
    "FIN_WAIT2": "FIN_WAIT2",
    "LAST_ACK": "LAST_ACK",
    "CLOSING": "CLOSING",
    "NONE": "—",
}


def get_connections(kind="inet"):
    """Return a list of active connections.

    `kind`: 'inet' (TCP+UDP, v4+v6), 'tcp', 'udp'. Each row:
      {proto, local, remote, status, pid, process}
    """
    kind_map = {"inet": "inet", "tcp": "tcp", "udp": "udp"}
    psutil_kind = kind_map.get(kind, "inet")

    try:
        conns = psutil.net_connections(kind=psutil_kind)
    except psutil.AccessDenied:
        # Without elevation we can't enumerate all; fall back to inet which
        # still yields the current user's sockets.
        try:
            conns = psutil.net_connections(kind="inet")
        except Exception as e:
            logging.warning(f"net_connections negado: {e}")
            return []
    except Exception as e:
        logging.exception(f"net_connections falhou: {e}")
        return []

    # Cache pid→name so we don't query the same process repeatedly.
    name_cache = {}

    def _proc_name(pid):
        if pid is None:
            return None
        if pid in name_cache:
            return name_cache[pid]
        try:
            nm = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            # Process gone, or we lack rights to read its name (other user's
            # process when un-elevated). Either way, no name available.
            logging.debug(f"netstat: process name for pid {pid} unavailable: {e}")
            nm = None
        name_cache[pid] = nm
        return nm

    rows = []
    for c in conns:
        # Map socket type to a protocol label.
        import socket as _socket
        if c.type == _socket.SOCK_STREAM:
            proto = "TCP"
        elif c.type == _socket.SOCK_DGRAM:
            proto = "UDP"
        else:
            proto = str(c.type)

        laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "—"
        raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "—"
        status = _STATE_PT.get(c.status, c.status or "—")

        rows.append({
            "proto": proto,
            "local": laddr,
            "remote": raddr,
            "status": status,
            "pid": c.pid,
            "process": _proc_name(c.pid),
        })

    # Listening + established first (the interesting ones), then by proto.
    def _sort_key(r):
        prio = 0 if r["status"] in ("OUVINDO", "ESTABELECIDA") else 1
        return (prio, r["proto"], r["local"])
    rows.sort(key=_sort_key)
    return rows
