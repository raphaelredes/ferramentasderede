# app/network/traffic.py
#
# Per-NIC throughput snapshot via psutil. Pure Python, no external binary.
# The frontend polls /network/traffic on an interval and computes rates from
# the delta between two cumulative-counter snapshots — the same way every OS
# bandwidth meter works (counters are monotonic byte totals, not rates).
#
# We intentionally return the raw cumulative counters + a server timestamp and
# let the client diff successive samples. That keeps the endpoint stateless
# (no per-client server state) and lets the client control the sampling
# interval / backoff exactly like MonitoringContext does for /network/monitor.

import logging
import time
from typing import Dict, Any

import psutil


def get_traffic_snapshot() -> Dict[str, Any]:
    """Return cumulative byte/packet counters per NIC plus a server timestamp.

    Shape:
      {
        "ts": <float epoch seconds>,
        "nics": {
          "<name>": {"bytes_sent", "bytes_recv", "packets_sent",
                     "packets_recv", "is_up", "speed_mbps"},
          ...
        }
      }

    The client diffs two snapshots: rate = (bytes2 - bytes1) / (ts2 - ts1).
    """
    out: Dict[str, Any] = {"ts": time.time(), "nics": {}}
    try:
        counters = psutil.net_io_counters(pernic=True)
    except Exception as e:
        logging.exception(f"net_io_counters falhou: {e}")
        return out

    try:
        stats = psutil.net_if_stats()
    except Exception as e:
        logging.debug(f"net_if_stats falhou: {e}")
        stats = {}

    for name, c in counters.items():
        st = stats.get(name)
        # Skip interfaces that are down — keeps the UI focused on live NICs.
        is_up = bool(st.isup) if st else True
        out["nics"][name] = {
            "bytes_sent": c.bytes_sent,
            "bytes_recv": c.bytes_recv,
            "packets_sent": c.packets_sent,
            "packets_recv": c.packets_recv,
            "is_up": is_up,
            # Link speed in Mbps when the OS reports it (0 = unknown).
            "speed_mbps": (st.speed if st and st.speed else 0),
        }
    return out
