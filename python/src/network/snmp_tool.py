# app/network/snmp_tool.py
#
# SNMP query tool: reads standard system OIDs (sysDescr/sysName/sysUpTime/...)
# from a switch / router / printer, and optionally the interface count. pysnmp
# 7.x (BSD-2, pure Python). v1/v2c with a read-only community string.
#
# WHY this is the most "corporate" tool here: a multi-VLAN analyst constantly
# needs to ask network gear "what are you, how long up, what's your name" and
# (with the ifTable) "which ports are up/down". A read-only community is safe.
#
# pysnmp 7.x is fully ASYNCIO — get_cmd and UdpTransportTarget.create are
# coroutines — so these functions are async and the FastAPI route awaits them.

import logging

try:
    from pysnmp.hlapi.v3arch.asyncio import (
        get_cmd, next_cmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity,
    )
    _HAS_PYSNMP = True
except Exception as e:  # pragma: no cover
    _HAS_PYSNMP = False
    logging.warning(f"pysnmp indisponível: {e}")


# Standard SNMPv2-MIB system OIDs (numeric, so we don't depend on MIB compiling).
_SYS_OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysObjectID": "1.3.6.1.2.1.1.2.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
}
# ifNumber.0 — number of interfaces (cheap one-shot beyond the system group).
_IF_NUMBER_OID = "1.3.6.1.2.1.2.1.0"


def _fmt_uptime(ticks):
    """TimeTicks are hundredths of a second. Render as Nd HH:MM:SS."""
    try:
        t = int(ticks)
    except (TypeError, ValueError):
        return str(ticks)
    secs = t // 100
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    return f"{days}d {hours:02d}:{mins:02d}:{secs:02d}"


async def query_system(host, community="public", port=161, version="2c", timeout=4.0, retries=1):
    """Read the system group from `host`. Returns a dict (ok/error)."""
    if not _HAS_PYSNMP:
        return {"ok": False, "error": "pysnmp indisponível."}
    if not host or not host.strip():
        return {"ok": False, "error": "Informe o host SNMP."}

    # v1 -> mpModel 0 ; v2c -> mpModel 1
    mp_model = 0 if str(version) in ("1", "v1") else 1

    try:
        transport = await UdpTransportTarget.create((host.strip(), port), timeout=timeout, retries=retries)
    except Exception as e:
        return {"ok": False, "error": f"Não foi possível criar o transporte UDP: {e}"}

    engine = SnmpEngine()
    result = {"ok": True, "host": host.strip(), "community": community, "version": str(version)}

    object_types = [ObjectType(ObjectIdentity(oid)) for oid in _SYS_OIDS.values()]
    keys = list(_SYS_OIDS.keys())

    try:
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            engine,
            CommunityData(community, mpModel=mp_model),
            transport,
            ContextData(),
            *object_types,
        )
    except Exception as e:
        return {"ok": False, "error": f"Erro na consulta SNMP: {e}"}

    if errorIndication:
        return {"ok": False, "error": f"Sem resposta SNMP: {errorIndication}"}
    if errorStatus:
        return {"ok": False, "error": f"Erro SNMP: {errorStatus.prettyPrint()}"}

    for key, vb in zip(keys, varBinds):
        try:
            _oid, val = vb
            sval = val.prettyPrint()
            if key == "sysUpTime":
                result["sysUpTime"] = _fmt_uptime(int(val))
                result["sysUpTimeRaw"] = int(val)
            else:
                result[key] = sval
        except Exception as e:
            logging.debug(f"SNMP varbind parse for {key}: {e}")
            result[key] = None

    # Best-effort interface count (separate GET; failure is non-fatal).
    try:
        ei, es, _, ifb = await get_cmd(
            engine, CommunityData(community, mpModel=mp_model), transport,
            ContextData(), ObjectType(ObjectIdentity(_IF_NUMBER_OID)),
        )
        if not ei and not es and ifb:
            result["ifNumber"] = int(ifb[0][1])
    except Exception as e:
        logging.debug(f"SNMP ifNumber failed: {e}")

    return result
