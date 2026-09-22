# python/src/network/ad_tools.py
"""Módulo de diagnóstico especializado para Active Directory em ambientes Multi-Domínio.

Testa matriz de portas críticas de DC, consulta e valida registros DNS SRV
e verifica desvio de relógio (Time Skew) com o PDC Emulator para Kerberos.
"""

import socket
import time
import logging
from typing import Dict, List, Any, Optional
import dns.resolver

# Lista de portas essenciais para funcionamento do Active Directory
AD_CORE_PORTS = [
    {"port": 53, "proto": "TCP", "service": "DNS", "desc": "Resolução de Nomes AD"},
    {"port": 88, "proto": "TCP", "service": "Kerberos", "desc": "Autenticação Kerberos v5"},
    {"port": 135, "proto": "TCP", "service": "RPC Mapper", "desc": "Mapeador de Endpoints RPC"},
    {"port": 389, "proto": "TCP", "service": "LDAP", "desc": "Consultas de Diretório LDAP"},
    {"port": 445, "proto": "TCP", "service": "SMB", "desc": "Compartilhamento & GPO (SYSVOL)"},
    {"port": 464, "proto": "TCP", "service": "Kpasswd", "desc": "Troca de Senha Kerberos"},
    {"port": 636, "proto": "TCP", "service": "LDAPS", "desc": "LDAP Seguro (SSL/TLS)"},
    {"port": 3268, "proto": "TCP", "service": "Global Catalog", "desc": "Catálogo Global LDAP"},
    {"port": 3269, "proto": "TCP", "service": "GC SSL", "desc": "Catálogo Global Seguro"},
]


def test_ad_port(target_ip: str, port: int, source_ip: Optional[str] = None, timeout: float = 2.0) -> Dict[str, Any]:
    """Testa uma única porta TCP com medição de latência e suporte a source_ip."""
    sock = None
    start_time = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        if source_ip:
            sock.bind((source_ip, 0))
        result = sock.connect_ex((target_ip, port))
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        is_open = (result == 0)
        return {
            "port": port,
            "open": is_open,
            "latency_ms": latency if is_open else None,
            "error_code": result if not is_open else None
        }
    except Exception as exc:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "port": port,
            "open": False,
            "latency_ms": None,
            "error": str(exc)
        }
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def test_ad_port_matrix(target_host: str, source_ip: Optional[str] = None, timeout: float = 1.5) -> List[Dict[str, Any]]:
    """Testa a matriz de portas do Active Directory para um DC específico."""
    results = []
    try:
        target_ip = socket.gethostbyname(target_host)
    except Exception:
        target_ip = target_host

    for item in AD_CORE_PORTS:
        port = item["port"]
        check = test_ad_port(target_ip, port, source_ip=source_ip, timeout=timeout)
        results.append({
            "port": port,
            "proto": item["proto"],
            "service": item["service"],
            "desc": item["desc"],
            "open": check.get("open", False),
            "latency_ms": check.get("latency_ms"),
            "error": check.get("error")
        })
    return results


def test_ad_srv_records(domain: str, dns_server: Optional[str] = None, site: Optional[str] = None) -> List[Dict[str, Any]]:
    """Consulta os registros DNS SRV críticos para localização de DCs no domínio."""
    resolver = dns.resolver.Resolver()
    if dns_server:
        resolver.nameservers = [dns_server]
    resolver.timeout = 3.0
    resolver.lifetime = 3.0

    srv_queries = [
        {"name": f"_ldap._tcp.dc._msdcs.{domain}", "desc": "Controladores de Domínio (DCs)"},
        {"name": f"_kerberos._tcp.{domain}", "desc": "Servidores KDC Kerberos"},
        {"name": f"_kpasswd._tcp.{domain}", "desc": "Serviço de Senha Kerberos"},
        {"name": f"_gc._tcp.{domain}", "desc": "Servidores Catálogo Global (GC)"},
    ]

    if site:
        srv_queries.append({
            "name": f"_ldap._tcp.{site}._sites.dc._msdcs.{domain}",
            "desc": f"DCs no Site '{site}'"
        })

    results = []
    for query in srv_queries:
        record_name = query["name"]
        entry = {
            "record": record_name,
            "desc": query["desc"],
            "found": False,
            "targets": [],
            "error": None
        }
        try:
            answers = resolver.resolve(record_name, 'SRV')
            targets = []
            for rdata in answers:
                target_str = str(rdata.target).rstrip('.')
                target_ips = []
                try:
                    ip_answers = resolver.resolve(target_str, 'A')
                    target_ips = [str(ip) for ip in ip_answers]
                except Exception:
                    pass

                targets.append({
                    "target": target_str,
                    "port": rdata.port,
                    "priority": rdata.priority,
                    "weight": rdata.weight,
                    "ips": target_ips
                })
            entry["found"] = len(targets) > 0
            entry["targets"] = targets
        except Exception as err:
            entry["error"] = str(err)
        results.append(entry)

    return results


def check_kerberos_time_skew(target_host: str, source_ip: Optional[str] = None) -> Dict[str, Any]:
    """Verifica a diferença de tempo (skew) entre a máquina local e o DC (limite Kerberos: 300s)."""
    import ntplib
    client = ntplib.NTPClient()
    try:
        response = client.request(target_host, version=3, timeout=2.5)
        offset_seconds = response.offset
        offset_ms = round(offset_seconds * 1000, 2)
        skew_warning = abs(offset_seconds) > 300.0
        skew_caution = abs(offset_seconds) > 2.0

        return {
            "target": target_host,
            "offset_seconds": round(offset_seconds, 4),
            "offset_ms": offset_ms,
            "delay_ms": round(response.delay * 1000, 2),
            "stratum": response.stratum,
            "server_time": time.ctime(response.tx_time),
            "skew_warning": skew_warning,
            "skew_caution": skew_caution,
            "status": "CRITICAL" if skew_warning else ("WARNING" if skew_caution else "HEALTHY")
        }
    except Exception as exc:
        return {
            "target": target_host,
            "error": str(exc),
            "status": "ERROR"
        }


def get_ad_fsmo_roles(domain: Optional[str] = None) -> Dict[str, Any]:
    """Descobre e mapeia os 5 detentores de funções FSMO no Active Directory."""
    import subprocess
    import os
    import re

    cmd = ["netdom", "query", "fsmo"]
    if domain and domain.strip():
        cmd.extend(["/domain:" + domain.strip()])

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="cp850" if os.name == "nt" else "utf-8",
            errors="replace",
            creationflags=flags,
            startupinfo=startupinfo,
            timeout=10,
        )
    except Exception as e:
        return {"ok": False, "error": f"Falha ao executar netdom: {e}"}

    if p.returncode != 0:
        err_msg = p.stderr.strip() or p.stdout.strip() or f"Código de saída: {p.returncode}"
        return {"ok": False, "error": f"Erro ao consultar FSMO: {err_msg}"}

    lines = p.stdout.splitlines()
    roles = {
        "schema_master": None,
        "domain_naming_master": None,
        "pdc_emulator": None,
        "rid_master": None,
        "infrastructure_master": None,
    }

    for line in lines:
        l = line.strip()
        if not l or "Comando conclu" in l:
            continue
        parts = re.split(r"\s{2,}", l)
        if len(parts) >= 2:
            role_label = parts[0].lower()
            holder = parts[1].strip()
        else:
            tokens = l.split()
            if len(tokens) >= 2:
                role_label = " ".join(tokens[:-1]).lower()
                holder = tokens[-1].strip()
            else:
                continue

        if "esquema" in role_label or "schema" in role_label:
            roles["schema_master"] = holder
        elif "nomea" in role_label or "naming" in role_label:
            roles["domain_naming_master"] = holder
        elif "pdc" in role_label:
            roles["pdc_emulator"] = holder
        elif "rid" in role_label:
            roles["rid_master"] = holder
        elif "infraestrutura" in role_label or "infrastructure" in role_label:
            roles["infrastructure_master"] = holder

    role_list = [
        {"role": "Schema Master", "desc": "Mestre de Esquema da Floresta (Modificações de Classes e Atributos)", "holder": roles["schema_master"]},
        {"role": "Domain Naming Master", "desc": "Mestre de Nomeação de Domínio (Adição e Remoção de Domínios na Floresta)", "holder": roles["domain_naming_master"]},
        {"role": "PDC Emulator", "desc": "Emulador PDC (Sincronismo de Tempo, Bloqueio de Senhas e GPO)", "holder": roles["pdc_emulator"]},
        {"role": "RID Master", "desc": "Mestre de Pools RID (Alocação de Identificadores de Segurança)", "holder": roles["rid_master"]},
        {"role": "Infrastructure Master", "desc": "Mestre de Infraestrutura (Referências de Objetos Inter-domínio)", "holder": roles["infrastructure_master"]},
    ]

    return {
        "ok": True,
        "domain": domain or "Local / Atual",
        "roles": roles,
        "role_list": role_list,
        "raw_output": p.stdout.strip(),
    }


def check_ad_replication(dc_target: Optional[str] = None) -> Dict[str, Any]:
    """Audita a replicação do Active Directory com repadmin /replsummary."""
    import subprocess
    import os
    import re

    cmd = ["repadmin", "/replsummary"]
    if dc_target and dc_target.strip():
        cmd.append(dc_target.strip())

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="cp850" if os.name == "nt" else "utf-8",
            errors="replace",
            creationflags=flags,
            startupinfo=startupinfo,
            timeout=15,
        )
    except Exception as e:
        return {"ok": False, "error": f"Falha ao executar repadmin: {e}"}

    if p.returncode != 0 and not p.stdout:
        err_msg = p.stderr.strip() or f"Código de saída: {p.returncode}"
        return {"ok": False, "error": f"Erro na replicação: {err_msg}"}

    lines = p.stdout.splitlines()
    sources = []
    destinations = []
    current_section = None

    for line in lines:
        l = line.strip()
        if not l:
            continue
        if "DSA Origem" in l or "Source DSA" in l:
            current_section = "source"
            continue
        elif "DSA Destino" in l or "Destination DSA" in l:
            current_section = "dest"
            continue

        m = re.match(r"^([a-zA-Z0-9.-]+)\s+([0-9a-zA-Z.:]+)\s+(\d+)\s*/\s*(\d+)\s*(\d*)", l)
        if m:
            entry = {
                "dsa": m.group(1),
                "largest_delta": m.group(2),
                "fails": int(m.group(3)),
                "total": int(m.group(4)),
                "percent_fails": int(m.group(5)) if m.group(5) else 0,
                "status": "HEALTHY" if int(m.group(3)) == 0 else "FAILING",
            }
            if current_section == "source":
                sources.append(entry)
            elif current_section == "dest":
                destinations.append(entry)

    total_fails = sum(s["fails"] for s in sources) + sum(d["fails"] for d in destinations)

    return {
        "ok": True,
        "dc_target": dc_target or "Todos os Controladores",
        "total_fails": total_fails,
        "status": "HEALTHY" if total_fails == 0 else "WARNING",
        "sources": sources,
        "destinations": destinations,
        "raw_output": p.stdout.strip(),
    }

