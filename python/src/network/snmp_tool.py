# python/src/network/snmp_tool.py
"""Módulo avançado de gerenciamento e telemetria SNMP (RFC 1213, RFC 2863 e RFC 3416):

- Leitura do grupo System (sysName, sysDescr, uptime, ifNumber)
- Tabela completa de interfaces em tempo real (ifTable / ifXTable):
    Index, Descrição/Nome da Porta, Tipo, Status Operacional/Administrativo,
    Velocidade negociada e Contadores de Erros/Descartes (ifInErrors/ifOutErrors).
- SNMP Walk livre e exploratório para varredura de subárvores de OIDs.
"""

import logging
import socket
import ipaddress
from typing import Dict, Any, List, Optional

try:
    from pysnmp.hlapi.v3arch.asyncio import (
        get_cmd, set_cmd, next_cmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity,
        UsmUserData,
        usmHMAC192SHA256AuthProtocol, usmHMACSHAAuthProtocol, usmHMACMD5AuthProtocol,
        usmAesCfb128Protocol, usmAesCfb256Protocol, usmDESPrivProtocol,
    )
    from pysnmp.proto.rfc1902 import OctetString
    _HAS_PYSNMP = True
except Exception as e:  # pragma: no cover
    _HAS_PYSNMP = False
    logging.warning(f"pysnmp indisponível: {e}")


# OIDs padrão do grupo System (RFC 1213)
_SYS_OIDS = {
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysObjectID": "1.3.6.1.2.1.1.2.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
}
_IF_NUMBER_OID = "1.3.6.1.2.1.2.1.0"

# OIDs base da ifTable (RFC 2863)
_IF_TABLE_BASE = "1.3.6.1.2.1.2.2.1"
_IF_COLUMNS = {
    "index": "1.3.6.1.2.1.2.2.1.1",
    "descr": "1.3.6.1.2.1.2.2.1.2",
    "type": "1.3.6.1.2.1.2.2.1.3",
    "speed": "1.3.6.1.2.1.2.2.1.5",
    "admin_status": "1.3.6.1.2.1.2.2.1.7",
    "oper_status": "1.3.6.1.2.1.2.2.1.8",
    "in_discards": "1.3.6.1.2.1.2.2.1.13",
    "in_errors": "1.3.6.1.2.1.2.2.1.14",
    "out_discards": "1.3.6.1.2.1.2.2.1.19",
    "out_errors": "1.3.6.1.2.1.2.2.1.20",
}

_STATUS_MAP = {
    1: "UP",
    2: "DOWN",
    3: "TESTING",
    4: "UNKNOWN",
    5: "DORMANT",
    6: "NOT_PRESENT",
    7: "LOWER_LAYER_DOWN",
}

_TYPE_MAP = {
    6: "Ethernet",
    24: "Software Loopback",
    53: "VLAN / SVI",
    135: "L2 VLAN",
    131: "Tunnel",
    161: "LAG / Port-Channel",
}


def _fmt_uptime(ticks):
    """Converte TimeTicks (centésimos de segundo) em Nd HH:MM:SS."""
    try:
        t = int(ticks)
    except (TypeError, ValueError):
        return str(ticks)
    secs = t // 100
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    mins, secs = divmod(secs, 60)
    return f"{days}d {hours:02d}:{mins:02d}:{secs:02d}"


def _fmt_speed(bps):
    """Formata velocidade em bits por segundo para Mbps ou Gbps."""
    try:
        val = int(bps)
        if val >= 10_000_000_000:
            return f"{val // 1_000_000_000} Gbps"
        if val >= 1_000_000_000:
            return f"{val / 1_000_000_000:.1f} Gbps".replace(".0", "")
        if val >= 1_000_000:
            return f"{val // 1_000_000} Mbps"
        if val >= 1_000:
            return f"{val // 1_000} Kbps"
        return f"{val} bps"
    except Exception:
        return str(bps)


WEAK_COMMUNITIES = {
    "public", "private", "cisco", "manager", "switch", "admin", "snmp",
    "router", "default", "system", "read", "write", "secret", "community",
    "test", "monitor", "guest", "netman", "operator", "password", "root"
}


def classify_network_target(host: str) -> Dict[str, Any]:
    """Classifica se o alvo pertence a uma rede privada RFC 1918 / RFC 4193, Loopback, Link-Local ou WAN Pública."""
    clean_host = (host or "").strip()
    if not clean_host:
        return {
            "type": "UNKNOWN",
            "network_type": "UNKNOWN",
            "is_private": True,
            "ip": "",
            "label": "Host não informado",
            "description": "Host não informado",
            "risk": "LOW"
        }

    try:
        # 1. Tentar interpretar diretamente como endereço IP (IPv4 ou IPv6)
        try:
            ip_obj = ipaddress.ip_address(clean_host)
            ip = str(ip_obj)
        except ValueError:
            # 2. Se for nome de domínio, resolver via socket.getaddrinfo (suporta registros A e AAAA)
            addr_info = socket.getaddrinfo(clean_host, None)
            ip = addr_info[0][4][0]
            ip_obj = ipaddress.ip_address(ip)

        if ip_obj.is_loopback:
            return {
                "type": "LOOPBACK",
                "network_type": "LOOPBACK",
                "is_private": True,
                "ip": ip,
                "label": f"Loopback Local ({ip})",
                "description": f"Loopback Local ({ip})",
                "risk": "LOW"
            }
        if ip_obj.is_private:
            return {
                "type": "RFC1918",
                "network_type": "RFC1918",
                "is_private": True,
                "ip": ip,
                "label": f"Rede Privada LAN / Corporativa ({ip})",
                "description": f"Rede Privada LAN / Corporativa ({ip})",
                "risk": "LOW"
            }
        if ip_obj.is_link_local:
            return {
                "type": "LINK_LOCAL",
                "network_type": "LINK_LOCAL",
                "is_private": True,
                "ip": ip,
                "label": f"Link-Local ({ip})",
                "description": f"Link-Local ({ip})",
                "risk": "LOW"
            }
        return {
            "type": "PUBLIC_WAN",
            "network_type": "PUBLIC_WAN",
            "is_private": False,
            "ip": ip,
            "label": f"IP Público / Internet ({ip})",
            "description": f"IP Público / Internet ({ip})",
            "risk": "HIGH",
            "warning": "ALERTA CRÍTICO DE RISCO (WAN / Internet): O tráfego SNMPv1/v2c trafegará por redes públicas desprotegidas sem cifragem, expondo a credencial em texto claro para provedores e nós intermediários."
        }
    except Exception:
        return {
            "type": "UNKNOWN",
            "network_type": "UNKNOWN",
            "is_private": True,
            "ip": clean_host,
            "label": clean_host,
            "description": clean_host,
            "risk": "LOW"
        }


def evaluate_community_strength(community: str, version: str) -> Dict[str, Any]:
    """Avalia o risco da credencial (community) utilizada."""
    c = (community or "").strip()
    c_lower = c.lower()
    is_weak = c_lower in WEAK_COMMUNITIES
    is_v1_v2 = str(version).lower() in ("1", "v1", "2c", "v2c", "2")

    if not is_v1_v2:
        return {"is_weak": False, "severity": "SECURE", "warning": None}

    if is_weak:
        is_priv = c_lower == "private"
        return {
            "is_weak": True,
            "severity": "CRITICAL" if is_priv else "HIGH",
            "warning": f"A community '{c}' é uma credencial padrão de fábrica conhecida mundialmente. Atacantes e ferramentas de varredura automatizada testam essa credencial rotineiramente."
        }
    if len(c) < 8:
        return {
            "is_weak": True,
            "severity": "MEDIUM",
            "warning": f"A community '{c}' tem menos de 8 caracteres e possui baixa entropia, sendo vulnerável a força bruta local."
        }
    return {"is_weak": False, "severity": "LOW", "warning": None}


def _build_auth_data(
    version: str = "2c",
    community: str = "public",
    v3_user: Optional[str] = None,
    v3_auth_key: Optional[str] = None,
    v3_priv_key: Optional[str] = None,
    v3_auth_proto: Optional[str] = "SHA256",
    v3_priv_proto: Optional[str] = "AES128",
    v3_sec_level: Optional[str] = "authPriv",
):
    """Cria dinamicamente o objeto de autenticação SNMP (CommunityData para v1/v2c ou UsmUserData para v3)."""
    ver_clean = str(version or "2c").lower().strip()
    if ver_clean in ("3", "v3"):
        user = (v3_user or "snmpuser").strip()
        sec_level = (v3_sec_level or "authPriv").strip()

        # Validação RFC 3414 (chaves USM precisam de no mínimo 8 octetos)
        if sec_level in ("authNoPriv", "authPriv") and v3_auth_key and len(v3_auth_key) < 8:
            raise ValueError("A senha de autenticação SNMPv3 (authKey) deve ter no mínimo 8 caracteres (RFC 3414).")
        if sec_level == "authPriv" and v3_priv_key and len(v3_priv_key) < 8:
            raise ValueError("A chave de privacidade SNMPv3 (privKey) deve ter no mínimo 8 caracteres (RFC 3414).")

        auth_proto_map = {
            "SHA256": usmHMAC192SHA256AuthProtocol,
            "SHA-256": usmHMAC192SHA256AuthProtocol,
            "SHA": usmHMACSHAAuthProtocol,
            "SHA1": usmHMACSHAAuthProtocol,
            "SHA-1": usmHMACSHAAuthProtocol,
            "MD5": usmHMACMD5AuthProtocol,
        }
        priv_proto_map = {
            "AES128": usmAesCfb128Protocol,
            "AES-128": usmAesCfb128Protocol,
            "AES": usmAesCfb128Protocol,
            "AES256": usmAesCfb256Protocol,
            "AES-256": usmAesCfb256Protocol,
            "DES": usmDESPrivProtocol,
        }

        auth_p = auth_proto_map.get(str(v3_auth_proto or "").upper(), usmHMAC192SHA256AuthProtocol)
        priv_p = priv_proto_map.get(str(v3_priv_proto or "").upper(), usmAesCfb128Protocol)

        if sec_level == "noAuthNoPriv" or not v3_auth_key:
            return UsmUserData(user)
        elif sec_level == "authNoPriv" or not v3_priv_key:
            return UsmUserData(user, authKey=v3_auth_key, authProtocol=auth_p)
        else:
            return UsmUserData(user, authKey=v3_auth_key, authProtocol=auth_p, privKey=v3_priv_key, privProtocol=priv_p)

    mp_model = 0 if ver_clean in ("1", "v1") else 1
    return CommunityData(community or "public", mpModel=mp_model)


async def query_system(
    host: str,
    community: str = "public",
    port: int = 161,
    version: str = "2c",
    timeout: float = 4.0,
    retries: int = 1,
    v3_user: Optional[str] = None,
    v3_auth_key: Optional[str] = None,
    v3_priv_key: Optional[str] = None,
    v3_auth_proto: Optional[str] = "SHA256",
    v3_priv_proto: Optional[str] = "AES128",
    v3_sec_level: Optional[str] = "authPriv",
) -> Dict[str, Any]:
    """Lê o grupo system básico e contagem de interfaces de um ativo SNMP."""
    if not _HAS_PYSNMP:
        return {"ok": False, "error": "pysnmp indisponível no ambiente."}
    if not host or not host.strip():
        return {"ok": False, "error": "Informe o host SNMP."}

    auth = _build_auth_data(
        version=version, community=community, v3_user=v3_user,
        v3_auth_key=v3_auth_key, v3_priv_key=v3_priv_key,
        v3_auth_proto=v3_auth_proto, v3_priv_proto=v3_priv_proto,
        v3_sec_level=v3_sec_level
    )

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
            auth,
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

    # Obter contagem de interfaces
    try:
        ei, es, _, ifb = await get_cmd(
            engine, auth, transport,
            ContextData(), ObjectType(ObjectIdentity(_IF_NUMBER_OID)),
        )
        if not ei and not es and ifb:
            result["ifNumber"] = int(ifb[0][1])
    except Exception as e:
        logging.debug(f"SNMP ifNumber failed: {e}")

    return result


async def query_interfaces(
    host: str,
    community: str = "public",
    port: int = 161,
    version: str = "2c",
    timeout: float = 3.0,
    retries: int = 1,
    max_interfaces: int = 128,
    v3_user: Optional[str] = None,
    v3_auth_key: Optional[str] = None,
    v3_priv_key: Optional[str] = None,
    v3_auth_proto: Optional[str] = "SHA256",
    v3_priv_proto: Optional[str] = "AES128",
    v3_sec_level: Optional[str] = "authPriv",
) -> Dict[str, Any]:
    """Varre e monta a tabela de interfaces (RFC 1213 / RFC 2863) de switches e roteadores."""
    if not _HAS_PYSNMP:
        return {"ok": False, "error": "pysnmp indisponível no ambiente."}
    clean_host = (host or "").strip()
    if not clean_host:
        return {"ok": False, "error": "Informe o host SNMP."}

    auth = _build_auth_data(
        version=version, community=community, v3_user=v3_user,
        v3_auth_key=v3_auth_key, v3_priv_key=v3_priv_key,
        v3_auth_proto=v3_auth_proto, v3_priv_proto=v3_priv_proto,
        v3_sec_level=v3_sec_level
    )

    try:
        transport = await UdpTransportTarget.create((clean_host, port), timeout=timeout, retries=retries)
    except Exception as e:
        return {"ok": False, "error": f"Erro no transporte UDP: {e}"}

    engine = SnmpEngine()

    interfaces_map: Dict[int, Dict[str, Any]] = {}

    # Varredura das colunas principais da ifTable
    for col_name, base_oid in _IF_COLUMNS.items():
        current_oid = ObjectIdentity(base_oid)
        count = 0
        while count < max_interfaces:
            try:
                ei, es, eidx, varBinds = await next_cmd(
                    engine, auth, transport, ContextData(), ObjectType(current_oid), lexicographicMode=False
                )
                if ei:
                    # Se na primeira coluna 'descr' o host não responder, ele está offline ou sem SNMP
                    if not interfaces_map and col_name == "descr":
                        return {"ok": False, "error": f"Sem resposta SNMP de {clean_host}:{port} ({ei})"}
                    break
                if es or not varBinds:
                    break

                oid_obj, val = varBinds[0]
                oid_str = str(oid_obj)
                if not oid_str.startswith(base_oid + "."):
                    break

                # O último sub-identificador do OID é o ifIndex
                try:
                    if_index = int(oid_str.split(".")[-1])
                except ValueError:
                    break

                if if_index not in interfaces_map:
                    interfaces_map[if_index] = {
                        "index": if_index,
                        "descr": f"Interface #{if_index}",
                        "type": "Desconhecido",
                        "type_raw": 0,
                        "speed": "—",
                        "speed_raw": 0,
                        "admin_status": "UNKNOWN",
                        "oper_status": "UNKNOWN",
                        "in_discards": 0,
                        "in_errors": 0,
                        "out_discards": 0,
                        "out_errors": 0,
                        "has_errors": False,
                    }

                h = interfaces_map[if_index]
                sval = val.prettyPrint()

                if col_name == "descr":
                    h["descr"] = sval
                elif col_name == "type":
                    try:
                        raw_t = int(val)
                        h["type_raw"] = raw_t
                        h["type"] = _TYPE_MAP.get(raw_t, f"Tipo #{raw_t}")
                    except Exception:
                        h["type"] = sval
                elif col_name == "speed":
                    try:
                        raw_spd = int(val)
                        h["speed_raw"] = raw_spd
                        h["speed"] = _fmt_speed(raw_spd)
                    except Exception:
                        h["speed"] = sval
                elif col_name == "admin_status":
                    try:
                        h["admin_status"] = _STATUS_MAP.get(int(val), sval)
                    except Exception:
                        h["admin_status"] = sval
                elif col_name == "oper_status":
                    try:
                        h["oper_status"] = _STATUS_MAP.get(int(val), sval)
                    except Exception:
                        h["oper_status"] = sval
                elif col_name == "in_errors":
                    try:
                        h["in_errors"] = int(val)
                    except Exception:
                        pass
                elif col_name == "out_errors":
                    try:
                        h["out_errors"] = int(val)
                    except Exception:
                        pass
                elif col_name == "in_discards":
                    try:
                        h["in_discards"] = int(val)
                    except Exception:
                        pass
                elif col_name == "out_discards":
                    try:
                        h["out_discards"] = int(val)
                    except Exception:
                        pass

                current_oid = ObjectIdentity(oid_str)
                count += 1
            except Exception as e:
                logging.debug(f"Erro no walk SNMP da coluna {col_name}: {e}")
                break

    # Ordenar por índice e calcular resumo
    if_list = sorted(interfaces_map.values(), key=lambda x: x["index"])
    for iface in if_list:
        iface["has_errors"] = (iface["in_errors"] > 0) or (iface["out_errors"] > 0)

    up_count = sum(1 for i in if_list if i["oper_status"] == "UP")
    down_count = sum(1 for i in if_list if i["oper_status"] == "DOWN")
    error_count = sum(1 for i in if_list if i["has_errors"])

    return {
        "ok": True,
        "host": clean_host,
        "total_interfaces": len(if_list),
        "up_count": up_count,
        "down_count": down_count,
        "error_count": error_count,
        "interfaces": if_list,
    }


async def walk_custom(
    host: str,
    root_oid: str = "1.3.6.1.2.1.1",
    community: str = "public",
    port: int = 161,
    version: str = "2c",
    max_rows: int = 100,
    timeout: float = 3.0,
    retries: int = 1,
    v3_user: Optional[str] = None,
    v3_auth_key: Optional[str] = None,
    v3_priv_key: Optional[str] = None,
    v3_auth_proto: Optional[str] = "SHA256",
    v3_priv_proto: Optional[str] = "AES128",
    v3_sec_level: Optional[str] = "authPriv",
) -> Dict[str, Any]:
    """Executa um SNMP Walk livre em qualquer subárvore OID especificada."""
    if not _HAS_PYSNMP:
        return {"ok": False, "error": "pysnmp indisponível no ambiente."}
    clean_host = (host or "").strip()
    clean_oid = (root_oid or "").strip()
    if not clean_host:
        return {"ok": False, "error": "Informe o host SNMP."}
    if not clean_oid:
        return {"ok": False, "error": "Informe o OID inicial para o Walk."}

    auth = _build_auth_data(
        version=version, community=community, v3_user=v3_user,
        v3_auth_key=v3_auth_key, v3_priv_key=v3_priv_key,
        v3_auth_proto=v3_auth_proto, v3_priv_proto=v3_priv_proto,
        v3_sec_level=v3_sec_level
    )

    try:
        transport = await UdpTransportTarget.create((clean_host, port), timeout=timeout, retries=retries)
    except Exception as e:
        return {"ok": False, "error": f"Erro no transporte UDP: {e}"}

    engine = SnmpEngine()

    results: List[Dict[str, Any]] = []
    current_oid = ObjectIdentity(clean_oid)

    while len(results) < max_rows:
        try:
            ei, es, eidx, varBinds = await next_cmd(
                engine, auth, transport, ContextData(), ObjectType(current_oid), lexicographicMode=False
            )
            if ei:
                if not results:
                    return {"ok": False, "error": f"Sem resposta SNMP: {ei}"}
                break
            if es:
                if not results:
                    return {"ok": False, "error": f"Erro SNMP: {es.prettyPrint()}"}
                break
            if not varBinds:
                break

            oid_obj, val = varBinds[0]
            oid_str = str(oid_obj)

            # Verificar se ainda pertence à subárvore
            if not oid_str.startswith(clean_oid):
                break

            results.append({
                "oid": oid_str,
                "value": val.prettyPrint(),
                "type": val.__class__.__name__
            })

            current_oid = ObjectIdentity(oid_str)
        except Exception as e:
            logging.debug(f"Erro no walk customizado: {e}")
            break

    return {
        "ok": True,
        "host": clean_host,
        "root_oid": clean_oid,
        "total_nodes": len(results),
        "nodes": results,
    }


async def probe_snmpv3_support(host: str, port: int = 161, timeout: float = 2.0) -> Dict[str, Any]:
    """Testa se o dispositivo remoto possui agente SNMPv3 ativo e responde à descoberta de EngineID (RFC 3414)."""
    if not _HAS_PYSNMP:
        return {"supported": False, "details": "pysnmp indisponível"}
    clean_host = (host or "").strip()
    if not clean_host:
        return {"supported": False, "details": "Host inválido"}

    try:
        transport = await UdpTransportTarget.create((clean_host, port), timeout=timeout, retries=0)
        engine = SnmpEngine()
        auth = UsmUserData("probe_discovery_user")
        ei, es, eidx, vb = await get_cmd(
            engine, auth, transport, ContextData(), ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0"))
        )
        if ei:
            ei_str = str(ei).lower()
            if any(k in ei_str for k in ("unknownusername", "wrongdigest", "notinwindow", "engineid", "authorizationerror")):
                return {
                    "supported": True,
                    "details": f"Agente SNMPv3 ativo detectado (Respondeu à descoberta USM da RFC 3414: {ei})"
                }
            if "timeout" in ei_str:
                return {
                    "supported": False,
                    "details": "Sem resposta à sonda SNMPv3 (Timeout / Não habilitado)"
                }
            return {"supported": False, "details": str(ei)}
        return {"supported": True, "details": "Agente SNMPv3 ativo e respondeu com sucesso"}
    except Exception as e:
        return {"supported": False, "details": f"Erro na sonda SNMPv3: {e}"}


async def audit_write_access(
    host: str,
    port: int = 161,
    community: str = "public",
    version: str = "2c",
    timeout: float = 2.5,
    v3_user: Optional[str] = None,
    v3_auth_key: Optional[str] = None,
    v3_priv_key: Optional[str] = None,
    v3_auth_proto: Optional[str] = "SHA256",
    v3_priv_proto: Optional[str] = "AES128",
    v3_sec_level: Optional[str] = "authPriv",
) -> Dict[str, Any]:
    """Audita de forma NÃO-DESTRUTIVA se a credencial SNMP possui privilégio de escrita (Read-Write / SET).
    
    1. Lê o valor atual de sysLocation (1.3.6.1.2.1.1.6.0).
    2. Tenta reaplicar o EXATO MESMO valor via set_cmd.
    - Se o agente retornar noError (0): a credencial possui privilégio de ESCRITA (Risco Crítico).
    - Se o agente retornar notWritable (17) ou noAccess (6): a credencial é estritamente READ-ONLY (Segura).
    - Se falhar por timeout ou erro de leitura: informa o status com precisão.
    """
    if not _HAS_PYSNMP:
        return {"ok": False, "write_enabled": False, "status": "UNAVAILABLE", "message": "pysnmp indisponível."}
    clean_host = (host or "").strip()
    if not clean_host:
        return {"ok": False, "write_enabled": False, "status": "ERROR", "message": "Host inválido."}

    auth = _build_auth_data(
        version=version, community=community, v3_user=v3_user,
        v3_auth_key=v3_auth_key, v3_priv_key=v3_priv_key,
        v3_auth_proto=v3_auth_proto, v3_priv_proto=v3_priv_proto,
        v3_sec_level=v3_sec_level
    )

    try:
        transport = await UdpTransportTarget.create((clean_host, port), timeout=timeout, retries=0)
    except Exception as e:
        return {"ok": False, "write_enabled": False, "status": "TRANSPORT_ERROR", "message": str(e)}

    engine = SnmpEngine()
    target_oid = "1.3.6.1.2.1.1.6.0"  # sysLocation

    # Passo 1: Leitura inicial segura do valor atual
    current_val = ""
    try:
        ei, es, eidx, varBinds = await get_cmd(
            engine, auth, transport, ContextData(), ObjectType(ObjectIdentity(target_oid))
        )
        if ei:
            return {"ok": False, "write_enabled": False, "status": "TIMEOUT", "message": f"Sem resposta na leitura: {ei}"}
        if not varBinds:
            return {"ok": False, "write_enabled": False, "status": "EMPTY", "message": "Nenhuma variável retornada na leitura inicial."}

        val_ret = varBinds[0][1]
        val_str = str(val_ret).lower()
        if "no such" in val_str or val_ret.__class__.__name__ in ("NoSuchObject", "NoSuchInstance"):
            return {
                "ok": True,
                "write_enabled": False,
                "status": "NOT_SUPPORTED",
                "message": "O ativo não implementa o OID sysLocation (MIB-II). Escrita não pôde ser testada de forma não-destrutiva.",
                "severity": "INFO"
            }
        current_val = val_ret.prettyPrint()
    except Exception as e:
        return {"ok": False, "write_enabled": False, "status": "EXCEPTION", "message": str(e)}

    # Passo 2: Tentativa de reescrita idêntica e inofensiva
    try:
        ei, es, eidx, varBinds = await set_cmd(
            engine, auth, transport, ContextData(),
            ObjectType(ObjectIdentity(target_oid), OctetString(current_val))
        )
        if ei:
            ei_str = str(ei).lower()
            if any(k in ei_str for k in ("notwritable", "noaccess", "readonly")):
                return {
                    "ok": True,
                    "write_enabled": False,
                    "status": "READ_ONLY",
                    "message": "Operação SET rejeitada. Credencial é estritamente Read-Only.",
                    "severity": "SECURE"
                }
            return {
                "ok": False,
                "write_enabled": False,
                "status": "SET_FAILED",
                "message": f"Falha na tentativa SET: {ei}",
                "severity": "LOW"
            }

        es_code = int(es) if es is not None else 0
        es_name = es.prettyPrint() if es is not None else ""

        if es_code == 0:
            return {
                "ok": True,
                "write_enabled": True,
                "status": "WRITE_ENABLED",
                "message": "ALERTA CRÍTICO: O dispositivo aceitou o comando SNMP SET! A community possui privilégio de ESCRITA (Read-Write).",
                "severity": "CRITICAL"
            }
        elif es_code in (6, 17) or any(k in es_name.lower() for k in ("notwritable", "noaccess", "readonly")):
            return {
                "ok": True,
                "write_enabled": False,
                "status": "READ_ONLY",
                "message": f"Protegido: Agente recusou escrita com '{es_name}'. Credencial é Read-Only.",
                "severity": "SECURE"
            }
        else:
            return {
                "ok": True,
                "write_enabled": False,
                "status": "REJECTED",
                "message": f"Agente retornou status '{es_name}'. Escrita não autorizada.",
                "severity": "SECURE"
            }
    except Exception as e:
        return {"ok": False, "write_enabled": False, "status": "EXCEPTION", "message": str(e)}


async def analyze_snmp_security_posture(
    host: str,
    port: int = 161,
    community: str = "public",
    version: str = "2c",
    timeout: float = 3.0,
    v3_user: Optional[str] = None,
    v3_auth_key: Optional[str] = None,
    v3_priv_key: Optional[str] = None,
    v3_auth_proto: Optional[str] = "SHA256",
    v3_priv_proto: Optional[str] = "AES128",
    v3_sec_level: Optional[str] = "authPriv",
) -> Dict[str, Any]:
    """Audita a postura completa de segurança de uma operação SNMP em redes monitoradas e não-monitoradas."""
    clean_host = (host or "").strip()
    ver_clean = str(version or "2c").lower().strip()
    is_v3 = ver_clean in ("3", "v3")

    # 1. Enlace de Rede
    net_info = classify_network_target(clean_host)

    # 2. Avaliação da Community / Credencial
    cred_info = evaluate_community_strength(community, ver_clean)

    # 3. Protocolo
    proto_info = {
        "version": "SNMPv3" if is_v3 else f"SNMPv{version}",
        "is_encrypted": is_v3 and (v3_sec_level == "authPriv"),
        "is_authenticated": is_v3 and (v3_sec_level in ("authPriv", "authNoPriv")),
        "cleartext_warning": not is_v3,
    }

    # 4. Sonda SNMPv3 (se não estiver usando v3)
    v3_probe = {"supported": is_v3, "details": "Já operando com SNMPv3" if is_v3 else "Não consultado"}
    if not is_v3:
        v3_probe = await probe_snmpv3_support(clean_host, port=port, timeout=min(timeout, 2.0))

    # 5. Auditoria de Escrita RW
    write_res = await audit_write_access(
        host=clean_host, port=port, community=community, version=version,
        timeout=min(timeout, 2.5),
        v3_user=v3_user, v3_auth_key=v3_auth_key, v3_priv_key=v3_priv_key,
        v3_auth_proto=v3_auth_proto, v3_priv_proto=v3_priv_proto,
        v3_sec_level=v3_sec_level,
    )

    # 6. Cálculo do Score de Risco e Nível
    risk_score = 0
    findings: List[Dict[str, str]] = []
    recommendations: List[str] = []

    # Fator 1: Enlace WAN Pública
    if not net_info.get("is_private", True):
        risk_score += 40
        findings.append({
            "severity": "CRITICAL" if not is_v3 else "MEDIUM",
            "title": "Alvo em Rede Pública / Internet",
            "desc": "O dispositivo está acessível na Internet. Pacotes SNMPv1/v2c expõem a community a interceptação por provedores e nós de trânsito."
        })
        recommendations.append("Bloquear a porta UDP 161 na borda e acessar o ativo exclusivamente via VPN IPsec ou rede de gerência dedicada (OOBM).")

    # Fator 2: Community Fraca
    if cred_info.get("is_weak"):
        sev = cred_info.get("severity", "HIGH")
        risk_score += (35 if sev == "CRITICAL" else 25)
        findings.append({
            "severity": sev,
            "title": f"Community Fraca / Padrão ('{community}')",
            "desc": cred_info.get("warning") or "Community padrão de fábrica vulnerável a varredura automatizada."
        })
        recommendations.append("Substituir a community por uma string complexa e randômica com mais de 16 caracteres, ou migrar para SNMPv3.")

    # Fator 3: Permissão de Escrita Ativa (RW)
    if write_res.get("write_enabled"):
        risk_score += 45
        findings.append({
            "severity": "CRITICAL",
            "title": "Permissão de Escrita Ativa (SNMP SET / Read-Write)",
            "desc": "A credencial informada permite alteração de parâmetros do dispositivo de rede. Um atacante pode reconfigurar interfaces ou baixar arquivos de configuração."
        })
        recommendations.append("Desabilitar imediatamente a community de escrita (RW) no switch/roteador caso a operação seja apenas de monitoramento e telemetria.")

    # Fator 4: Protocolo Descriptografado em texto claro
    if not is_v3:
        risk_score += 20
        findings.append({
            "severity": "HIGH",
            "title": "Protocolo Legado em Texto Claro (SNMPv1 / SNMPv2c)",
            "desc": "O protocolo transmite credenciais e métricas sem cifragem de payload (RFC 1157/1901)."
        })
        if v3_probe.get("supported"):
            recommendations.append("O dispositivo alvo já suporta SNMPv3. Habilite o modo USM authPriv (SHA-256 + AES) para criptografar todo o tráfego.")
        else:
            recommendations.append("Restringir o acesso a estações de monitoramento autorizadas utilizando ACLs no switch/roteador.")

    risk_score = min(100, risk_score)
    if is_v3 and (v3_sec_level == "authPriv") and not write_res.get("write_enabled") and net_info.get("is_private"):
        risk_score = 0

    if risk_score >= 70:
        risk_level = "CRITICAL"
        risk_label = "Risco Crítico"
    elif risk_score >= 40:
        risk_level = "HIGH"
        risk_label = "Alto Risco"
    elif risk_score >= 15:
        risk_level = "MEDIUM"
        risk_label = "Atenção Moderada"
    else:
        risk_level = "LOW"
        risk_label = "Postura Fortalecida (Seguro)"

    return {
        "ok": True,
        "host": clean_host,
        "port": port,
        "version": version,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "network": net_info,
        "credentials": cred_info,
        "protocol": proto_info,
        "write_audit": write_res,
        "snmpv3_probe": v3_probe,
        "findings": findings,
        "recommendations": recommendations,
    }
