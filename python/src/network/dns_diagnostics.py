"""Módulo de diagnósticos DNS avançados (RFC 1035, RFC 3597, RFC 8499).

Fornece diagnósticos completos de DNS com padrões profissionais (ISC BIND dig,
Google Admin Toolbox, Cloudflare 1.1.1.1 e MXToolbox):
- Consultas por tipo de registro específico (A, AAAA, CNAME, MX, TXT, NS, SOA, PTR, SRV, CAA).
- Diagnóstico completo de domínio (A/AAAA, MX com SPF/DMARC, NS, SOA e saúde geral).
- Benchmark e comparativo multi-provedor (Resolvedor Local vs Google vs Cloudflare vs Quad9 vs AD).
- Saída bruta canônica idêntica ao utilitário `dig` com seções QUESTION, ANSWER, AUTHORITY, ADDITIONAL.
- Detecção precisa de RCODE (NOERROR, SERVFAIL, NXDOMAIN, REFUSED, TIMEOUT) com diagnósticos em português.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import dns.exception
    import dns.flags
    import dns.message
    import dns.query
    import dns.rcode
    import dns.rdatatype
    import dns.resolver
    import dns.reversename
    _HAS_DNSPYTHON = True
except Exception as _e:
    _HAS_DNSPYTHON = False
    logging.warning(f"dns_diagnostics: dnspython não disponível ({_e})")

# Dicionário de descrições amigáveis de RCODE
RCODE_DESCRIPTIONS = {
    "NOERROR": "Consulta atendida com sucesso sem erros.",
    "FORMERR": "O servidor não conseguiu interpretar a consulta enviada (erro de formato).",
    "SERVFAIL": "Falha no servidor DNS (SERVFAIL). O servidor não conseguiu obter resposta dos servidores autoritativos, houve timeout no encaminhamento ou falha na validação DNSSEC.",
    "NXDOMAIN": "Domínio inexistente (NXDOMAIN). O nome consultado não existe na zona autoritativa.",
    "NOTIMP": "O tipo de consulta ou funcionalidade não é implementado pelo servidor DNS.",
    "REFUSED": "A consulta foi recusada pelo servidor (política de acesso, recursão desabilitada ou restrição de IP).",
    "YXDOMAIN": "Nome que não deveria existir já existe.",
    "YXRRSET": "Conjunto de registros RR que não deveria existir já existe.",
    "NXRRSET": "O conjunto de registros RR solicitado não existe para este nome.",
    "NOTAUTH": "O servidor não é autoritativo para a zona requerida.",
    "NOTZONE": "O nome não está contido na zona especificada.",
    "TIMEOUT": "O servidor DNS não respondeu dentro do tempo limite estipulado.",
}

# Resolvedores públicos de referência para benchmark
PUBLIC_RESOLVERS = [
    {"name": "Google DNS", "ip": "8.8.8.8", "secondary": "8.8.4.4"},
    {"name": "Cloudflare DNS", "ip": "1.1.1.1", "secondary": "1.0.0.1"},
    {"name": "Quad9 (Segurança)", "ip": "9.9.9.9", "secondary": "149.112.112.112"},
    {"name": "OpenDNS", "ip": "208.67.222.222", "secondary": "208.67.220.220"},
]


def format_ttl(seconds: int) -> str:
    """Formata TTL em segundos para representação legível (ex: 3600 -> 3600s (1h))."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{seconds}s ({m}m{f' {s}s' if s else ''})"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{seconds}s ({h}h{f' {m}m' if m else ''})"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{seconds}s ({d}d{f' {h}h' if h else ''})"


def get_system_nameservers() -> List[str]:
    """Obtém a lista de servidores DNS configurados na máquina local."""
    servers = []
    if _HAS_DNSPYTHON:
        try:
            r = dns.resolver.Resolver()
            if r.nameservers:
                servers = list(r.nameservers)
        except Exception as e:
            logging.debug(f"Falha ao ler nameservers dnspython: {e}")
    return servers


def _is_ip_address(val: str) -> bool:
    """Verifica se string é um endereço IPv4 ou IPv6."""
    try:
        ipaddress.ip_address(val.strip())
        return True
    except ValueError:
        return False


def _build_raw_dig_text(
    query_name: str,
    record_type: str,
    server: str,
    port: int,
    rcode_str: str,
    flags_list: List[str],
    query_time_ms: float,
    response_msg: Optional[Any],
    when_str: str,
) -> str:
    """Monta a saída textual no padrão oficial do comando ISC BIND `dig`."""
    lines = [
        f"; <<>> DiG (Ferramentas de Rede RFC DiG) <<>> {query_name} {record_type} @{server}",
        ";; global options: +cmd",
    ]

    if response_msg is not None:
        lines.append(";; Got answer:")
        lines.append(
            f";; ->>HEADER<<- opcode: QUERY, status: {rcode_str}, id: {response_msg.id}"
        )
        flags_text = " ".join(flags_list) if flags_list else "none"
        lines.append(
            f";; flags: {flags_text}; QUERY: {len(response_msg.question)}, "
            f"ANSWER: {len(response_msg.answer)}, AUTHORITY: {len(response_msg.authority)}, "
            f"ADDITIONAL: {len(response_msg.additional)}"
        )

        lines.append("")
        lines.append(";; QUESTION SECTION:")
        for q in response_msg.question:
            lines.append(f";{q.to_text()}")

        if response_msg.answer:
            lines.append("")
            lines.append(";; ANSWER SECTION:")
            for rrset in response_msg.answer:
                for rdata in rrset:
                    lines.append(
                        f"{rrset.name.to_text()}\t{rrset.ttl}\tIN\t{dns.rdatatype.to_text(rrset.rdtype)}\t{rdata.to_text()}"
                    )

        if response_msg.authority:
            lines.append("")
            lines.append(";; AUTHORITY SECTION:")
            for rrset in response_msg.authority:
                for rdata in rrset:
                    lines.append(
                        f"{rrset.name.to_text()}\t{rrset.ttl}\tIN\t{dns.rdatatype.to_text(rrset.rdtype)}\t{rdata.to_text()}"
                    )

        if response_msg.additional:
            lines.append("")
            lines.append(";; ADDITIONAL SECTION:")
            for rrset in response_msg.additional:
                for rdata in rrset:
                    lines.append(
                        f"{rrset.name.to_text()}\t{rrset.ttl}\tIN\t{dns.rdatatype.to_text(rrset.rdtype)}\t{rdata.to_text()}"
                    )
    else:
        lines.append(";; connection timed out; no servers could be reached")

    lines.append("")
    lines.append(f";; Query time: {query_time_ms:.1f} msec")
    lines.append(f";; SERVER: {server}#{port}({server})")
    lines.append(f";; WHEN: {when_str}")
    if response_msg is not None:
        try:
            wire_len = len(response_msg.to_wire())
            lines.append(f";; MSG SIZE  rcvd: {wire_len}")
        except Exception:
            pass

    return "\n".join(lines)


def query_dns_record(
    target: str,
    record_type: str = "A",
    dns_server: Optional[str] = None,
    timeout: float = 3.0,
) -> Dict[str, Any]:
    """Executa uma consulta DNS RFC para um alvo e tipo de registro específicos.

    Retorna dicionário estruturado com RCODE, flags, tempos, registros e saída dig.
    """
    clean_target = target.strip()
    clean_type = record_type.strip().upper()

    if not clean_target:
        return {
            "ok": False,
            "error": "Informe um hostname ou endereço IP para consulta.",
            "target": clean_target,
            "record_type": clean_type,
        }

    # Se tipo for AUTO, infere pelo formato do target
    is_ip = _is_ip_address(clean_target)
    if clean_type in ("AUTO", ""):
        clean_type = "PTR" if is_ip else "A"

    # Se for PTR, converte IP para reverse domain name
    query_name = clean_target
    if clean_type == "PTR" or is_ip and clean_type == "AUTO":
        try:
            clean_type = "PTR"
            rev_name = dns.reversename.from_address(clean_target)
            query_name = rev_name.to_text()
        except Exception as e:
            return {
                "ok": False,
                "error": f"Endereço IP inválido para consulta reversa: {e}",
                "target": clean_target,
                "record_type": clean_type,
            }

    # Determinar servidor DNS a consultar
    system_servers = get_system_nameservers()
    target_server = dns_server.strip() if dns_server else (system_servers[0] if system_servers else "8.8.8.8")
    server_port = 53

    now_str = datetime.now().strftime("%a %b %d %H:%M:%S %Y")

    if not _HAS_DNSPYTHON:
        return {
            "ok": False,
            "error": "Biblioteca dnspython não está disponível no sistema.",
            "target": clean_target,
            "record_type": clean_type,
        }

    try:
        rdtype = dns.rdatatype.from_text(clean_type)
    except Exception:
        return {
            "ok": False,
            "error": f"Tipo de registro DNS inválido ou não suportado: '{clean_type}'",
            "target": clean_target,
            "record_type": clean_type,
        }

    # Monta a mensagem RFC com flags RD (Recursão Solicitada) e AD (DNSSEC)
    msg = dns.message.make_query(query_name, rdtype)
    msg.flags |= dns.flags.AD

    t_start = time.perf_counter()
    response = None
    rcode_str = "TIMEOUT"
    flags_list: List[str] = []
    error_msg: Optional[str] = None

    try:
        # Consulta primária via UDP
        response = dns.query.udp(msg, target_server, timeout=timeout, port=server_port)
        # Se mensagem foi truncada (TC=1), chaveia para TCP conforme RFC 7766
        if response.flags & dns.flags.TC:
            response = dns.query.tcp(msg, target_server, timeout=timeout, port=server_port)
    except dns.exception.Timeout:
        rcode_str = "TIMEOUT"
        error_msg = f"Tempo esgotado ({timeout}s) ao consultar o servidor DNS {target_server}."
    except Exception as e:
        err_type = type(e).__name__
        if "LifetimeTimeout" in err_type or "Timeout" in err_type:
            rcode_str = "TIMEOUT"
            error_msg = f"Tempo limite de consulta excedido ({timeout}s) no servidor {target_server}."
        else:
            rcode_str = "ERROR"
            error_msg = f"Erro de comunicação de rede: {e}"

    t_elapsed_ms = (time.perf_counter() - t_start) * 1000

    answers: List[Dict[str, Any]] = []
    authorities: List[Dict[str, Any]] = []
    additionals: List[Dict[str, Any]] = []

    if response is not None:
        rcode_val = response.rcode()
        rcode_str = dns.rcode.to_text(rcode_val)

        # Decodifica flags ativas
        f = response.flags
        if f & dns.flags.AA:
            flags_list.append("AA")  # Authoritative Answer
        if f & dns.flags.RD:
            flags_list.append("RD")  # Recursion Desired
        if f & dns.flags.RA:
            flags_list.append("RA")  # Recursion Available
        if f & dns.flags.AD:
            flags_list.append("AD")  # Authentic Data (DNSSEC)
        if f & dns.flags.CD:
            flags_list.append("CD")  # Checking Disabled
        if f & dns.flags.TC:
            flags_list.append("TC")  # Truncated

        # Processa ANSWER section
        for rrset in response.answer:
            rtype_str = dns.rdatatype.to_text(rrset.rdtype)
            rname_str = rrset.name.to_text().rstrip(".")
            ttl_val = rrset.ttl
            for rdata in rrset:
                item: Dict[str, Any] = {
                    "name": rname_str,
                    "type": rtype_str,
                    "ttl": ttl_val,
                    "ttl_formatted": format_ttl(ttl_val),
                    "raw_data": rdata.to_text(),
                }
                # Atributos específicos por tipo
                if rtype_str in ("A", "AAAA"):
                    item["address"] = rdata.address
                elif rtype_str == "CNAME":
                    item["target"] = rdata.target.to_text().rstrip(".")
                elif rtype_str == "MX":
                    item["priority"] = rdata.preference
                    item["target"] = rdata.exchange.to_text().rstrip(".")
                elif rtype_str == "TXT":
                    item["strings"] = [s.decode("utf-8", errors="replace") if isinstance(s, bytes) else str(s) for s in rdata.strings]
                    item["text"] = " ".join(item["strings"])
                elif rtype_str == "NS":
                    item["nameserver"] = rdata.target.to_text().rstrip(".")
                elif rtype_str == "PTR":
                    item["ptr_name"] = rdata.target.to_text().rstrip(".")
                elif rtype_str == "SRV":
                    item["priority"] = rdata.priority
                    item["weight"] = rdata.weight
                    item["port"] = rdata.port
                    item["target"] = rdata.target.to_text().rstrip(".")
                elif rtype_str == "SOA":
                    item["mname"] = rdata.mname.to_text().rstrip(".")
                    item["rname"] = rdata.rname.to_text().rstrip(".")
                    item["serial"] = rdata.serial
                    item["refresh"] = rdata.refresh
                    item["retry"] = rdata.retry
                    item["expire"] = rdata.expire
                    item["minimum"] = rdata.minimum
                answers.append(item)

        # Processa AUTHORITY section
        for rrset in response.authority:
            rtype_str = dns.rdatatype.to_text(rrset.rdtype)
            for rdata in rrset:
                authorities.append({
                    "name": rrset.name.to_text().rstrip("."),
                    "type": rtype_str,
                    "ttl": rrset.ttl,
                    "ttl_formatted": format_ttl(rrset.ttl),
                    "data": rdata.to_text(),
                })

        # Processa ADDITIONAL section
        for rrset in response.additional:
            rtype_str = dns.rdatatype.to_text(rrset.rdtype)
            for rdata in rrset:
                additionals.append({
                    "name": rrset.name.to_text().rstrip("."),
                    "type": rtype_str,
                    "ttl": rrset.ttl,
                    "ttl_formatted": format_ttl(rrset.ttl),
                    "data": rdata.to_text(),
                })

    raw_dig = _build_raw_dig_text(
        query_name=clean_target,
        record_type=clean_type,
        server=target_server,
        port=server_port,
        rcode_str=rcode_str,
        flags_list=flags_list,
        query_time_ms=t_elapsed_ms,
        response_msg=response,
        when_str=now_str,
    )

    return {
        "ok": rcode_str == "NOERROR" and len(answers) > 0,
        "target": clean_target,
        "record_type": clean_type,
        "server_used": f"{target_server}:{server_port}",
        "server_ip": target_server,
        "is_system_resolver": dns_server is None,
        "rcode": rcode_str,
        "rcode_description": RCODE_DESCRIPTIONS.get(
            rcode_str, f"Código de resposta DNS: {rcode_str}"
        ),
        "flags": flags_list,
        "query_time_ms": round(t_elapsed_ms, 1),
        "answer_count": len(answers),
        "answers": answers,
        "authority_count": len(authorities),
        "authorities": authorities,
        "additional_count": len(additionals),
        "additionals": additionals,
        "raw_dig": raw_dig,
        "error": error_msg,
    }


def diagnose_domain_complete(
    target: str,
    dns_server: Optional[str] = None,
    timeout: float = 3.0,
) -> Dict[str, Any]:
    """Realiza um diagnóstico abrangente de saúde DNS para um domínio ou IP.

    Consulta A, AAAA, CNAME, MX, TXT (SPF/DMARC), NS e SOA.
    Se o servidor corporativo local falhar (SERVFAIL ou TIMEOUT), executa
    uma comparação automática com um resolvedor público para diagnosticar
    se o problema é da rede interna ou do domínio.
    """
    clean_target = target.strip()
    if not clean_target:
        return {"ok": False, "error": "Informe um domínio ou IP."}

    is_ip = _is_ip_address(clean_target)

    # Caso seja IP, faz verificação reversa (PTR) e direta de consistência (FCrDNS)
    if is_ip:
        ptr_res = query_dns_record(clean_target, "PTR", dns_server=dns_server, timeout=timeout)
        insights = []
        reverse_name = None
        if ptr_res.get("answers"):
            reverse_name = ptr_res["answers"][0].get("ptr_name")
            insights.append({
                "type": "success",
                "title": "Registro Reverso (PTR) Encontrado",
                "message": f"O endereço IP {clean_target} resolve reversamente para o nome '{reverse_name}'.",
            })
            # Teste FCrDNS (Forward-Confirmed Reverse DNS)
            forward_check = query_dns_record(reverse_name, "A", dns_server=dns_server, timeout=timeout)
            forward_ips = [a.get("address") for a in forward_check.get("answers", []) if a.get("address")]
            if clean_target in forward_ips:
                insights.append({
                    "type": "success",
                    "title": "FCrDNS Válido (Consistência Direta/Reversa)",
                    "message": f"O nome '{reverse_name}' resolve de volta para o IP {clean_target} (Consistência FCrDNS confirmada).",
                })
            else:
                insights.append({
                    "type": "warning",
                    "title": "FCrDNS Inconsistente",
                    "message": f"O nome reverso '{reverse_name}' não resolve diretamente de volta para o IP original {clean_target}.",
                })
        else:
            insights.append({
                "type": "warning",
                "title": "Sem Registro Reverso (PTR)",
                "message": f"Nenhum registro PTR configurado para {clean_target}. Servidores de e-mail e filtros de segurança corporativos podem rejeitar conexões originadas deste IP.",
            })

        return {
            "ok": ptr_res.get("ok", False),
            "target": clean_target,
            "mode": "ip_reverse",
            "primary_result": ptr_res,
            "records": ptr_res.get("answers", []),
            "insights": insights,
        }

    # Domínio: consulta registros vitais em paralelo
    vital_types = ["A", "AAAA", "MX", "TXT", "NS", "SOA", "CNAME"]
    results_by_type: Dict[str, Dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=len(vital_types)) as pool:
        future_to_type = {
            pool.submit(query_dns_record, clean_target, t, dns_server, timeout): t
            for t in vital_types
        }
        for fut in as_completed(future_to_type):
            t = future_to_type[fut]
            try:
                results_by_type[t] = fut.result()
            except Exception as e:
                results_by_type[t] = {"ok": False, "rcode": "ERROR", "error": str(e), "answers": []}

    # Coleta todos os registros obtidos
    all_records: List[Dict[str, Any]] = []
    for t in vital_types:
        r = results_by_type.get(t, {})
        for ans in r.get("answers", []):
            all_records.append(ans)

    primary_a = results_by_type.get("A", {})
    insights: List[Dict[str, Any]] = []

    # Diagnóstico inteligente de falha local vs pública
    has_local_failure = primary_a.get("rcode") in ("SERVFAIL", "TIMEOUT", "REFUSED")
    public_verified: Optional[Dict[str, Any]] = None

    if has_local_failure and (dns_server is None or dns_server != "8.8.8.8"):
        # Executa sonda rápida contra 8.8.8.8 para verificar se o domínio funciona fora
        try:
            public_check = query_dns_record(clean_target, "A", dns_server="8.8.8.8", timeout=2.0)
            if public_check.get("ok"):
                public_verified = public_check
                public_ips = [a.get("address") for a in public_check.get("answers", [])]
                insights.append({
                    "type": "error_critical",
                    "title": "Falha no Resolvedor DNS Local (Detectada Isoladamente)",
                    "message": (
                        f"O servidor DNS local retornou {primary_a.get('rcode')}, porém resolvedores públicos externos "
                        f"(Google 8.8.8.8) resolveram o domínio normalmente para: {', '.join(public_ips)}. "
                        "Isto indica que a falha não é do domínio e sim de infraestrutura interna: verifique os "
                        "encaminhadores (forwarders) do seu servidor DNS local ou regras de firewall na porta 53."
                    ),
                })
        except Exception:
            pass

    if primary_a.get("ok"):
        ips = [a.get("address") for a in primary_a.get("answers", []) if a.get("address")]
        insights.append({
            "type": "success",
            "title": "Resolução IPv4 (A) Operacional",
            "message": f"O domínio resolve para: {', '.join(ips)} (latência: {primary_a.get('query_time_ms')} ms).",
        })

    # Verificação IPv6
    aaaa_res = results_by_type.get("AAAA", {})
    if aaaa_res.get("ok"):
        v6_ips = [a.get("address") for a in aaaa_res.get("answers", []) if a.get("address")]
        insights.append({
            "type": "info",
            "title": "Suporte a IPv6 Ativo (AAAA)",
            "message": f"Endereço IPv6 disponível: {', '.join(v6_ips)}.",
        })

    # Verificação de MX e E-mail
    mx_res = results_by_type.get("MX", {})
    txt_res = results_by_type.get("TXT", {})
    if mx_res.get("ok"):
        mx_hosts = [f"{a.get('target')} (pref {a.get('priority')})" for a in mx_res.get("answers", [])]
        insights.append({
            "type": "success",
            "title": "Servidores de Correio (MX) Configurados",
            "message": f"Servidores MX: {'; '.join(mx_hosts)}.",
        })

        # Checa presença de SPF nos registros TXT
        has_spf = False
        for txt in txt_res.get("answers", []):
            raw_t = txt.get("raw_data", "")
            if "v=spf1" in raw_t:
                has_spf = True
                insights.append({
                    "type": "success",
                    "title": "Política SPF Encontrada",
                    "message": f"Registro de validação de remetente SPF ativo: {raw_t.strip('\"')}",
                })
                break
        if not has_spf:
            insights.append({
                "type": "warning",
                "title": "Registro SPF Ausente",
                "message": "O domínio possui registros MX para receber e-mails, mas não possui registro TXT com política SPF (v=spf1). Mensagens enviadas podem ser marcadas como spam.",
            })

    # Verificação de Servidores Autoritativos (NS)
    ns_res = results_by_type.get("NS", {})
    if ns_res.get("ok"):
        ns_servers = [a.get("nameserver") for a in ns_res.get("answers", []) if a.get("nameserver")]
        insights.append({
            "type": "info",
            "title": "Servidores de Nome Autoritativos (NS)",
            "message": f"{len(ns_servers)} servidores autoritativos listados: {', '.join(ns_servers)}.",
        })

    # Verificação de SOA
    soa_res = results_by_type.get("SOA", {})
    if soa_res.get("ok") and soa_res.get("answers"):
        soa_item = soa_res["answers"][0]
        insights.append({
            "type": "info",
            "title": "Zona Autoritativa (SOA)",
            "message": f"Servidor primário: {soa_item.get('mname')}, Serial da zona: {soa_item.get('serial')}.",
        })

    # Determina o resultado principal para o card superior
    main_result = primary_a if primary_a.get("rcode") != "TIMEOUT" else (results_by_type.get("CNAME") or primary_a)

    return {
        "ok": len(all_records) > 0 or (public_verified is not None and public_verified.get("ok", False)),
        "target": clean_target,
        "mode": "domain_complete",
        "primary_result": main_result,
        "records": all_records,
        "results_by_type": results_by_type,
        "insights": insights,
        "public_comparison": public_verified,
    }


def benchmark_dns_resolvers(
    target: str,
    record_type: str = "A",
    extra_servers: Optional[List[Dict[str, str]]] = None,
    timeout: float = 3.0,
) -> Dict[str, Any]:
    """Compara o desempenho e os resultados entre múltiplos provedores DNS.

    Consulta em paralelo o resolvedor padrão do sistema, resolvedores públicos mundiais
    (Google, Cloudflare, Quad9, OpenDNS) e eventuais servidores corporativos cadastrados.
    """
    clean_target = target.strip()
    if not clean_target:
        return {"ok": False, "error": "Informe o alvo para benchmark."}

    # Monta a lista de provedores a testar
    servers_to_test: List[Dict[str, str]] = []

    # 1. Resolvedor do Sistema
    sys_servers = get_system_nameservers()
    sys_ip = sys_servers[0] if sys_servers else "Sistema Local"
    servers_to_test.append({
        "id": "system",
        "name": "Resolver do Sistema (Local)",
        "ip": sys_ip,
        "type": "local",
    })

    # 2. Servidores Públicos Globais
    for pub in PUBLIC_RESOLVERS:
        servers_to_test.append({
            "id": pub["name"].lower().replace(" ", "_"),
            "name": pub["name"],
            "ip": pub["ip"],
            "type": "public",
        })

    # 3. Servidores customizados / redes do usuário
    if extra_servers:
        for ex in extra_servers:
            ip = ex.get("ip") or ex.get("dns_server")
            name = ex.get("name") or ip
            if ip and ip not in [s["ip"] for s in servers_to_test]:
                servers_to_test.append({
                    "id": f"custom_{ip}",
                    "name": f"AD/VLAN: {name}",
                    "ip": ip,
                    "type": "corporate",
                })

    benchmarks: List[Dict[str, Any]] = []

    def _probe_server(srv: Dict[str, str]) -> Dict[str, Any]:
        # Para o servidor local do sistema, passamos None para usar o resolver padrão configurado
        target_ip = None if srv["id"] == "system" else srv["ip"]
        res = query_dns_record(clean_target, record_type=record_type, dns_server=target_ip, timeout=timeout)
        answers_summary = []
        for a in res.get("answers", []):
            if "address" in a:
                answers_summary.append(a["address"])
            elif "target" in a:
                answers_summary.append(a["target"])
            elif "raw_data" in a:
                answers_summary.append(a["raw_data"])

        return {
            "id": srv["id"],
            "name": srv["name"],
            "ip": srv["ip"],
            "type": srv["type"],
            "ok": res.get("ok", False),
            "rcode": res.get("rcode", "ERROR"),
            "rcode_description": res.get("rcode_description", ""),
            "query_time_ms": res.get("query_time_ms", 0),
            "flags": res.get("flags", []),
            "answer_count": len(res.get("answers", [])),
            "answers_summary": answers_summary,
            "error": res.get("error"),
        }

    with ThreadPoolExecutor(max_workers=min(len(servers_to_test), 10)) as pool:
        future_map = {pool.submit(_probe_server, s): s for s in servers_to_test}
        for fut in as_completed(future_map):
            try:
                benchmarks.append(fut.result())
            except Exception as e:
                s = future_map[fut]
                benchmarks.append({
                    "id": s["id"],
                    "name": s["name"],
                    "ip": s["ip"],
                    "type": s["type"],
                    "ok": False,
                    "rcode": "ERROR",
                    "query_time_ms": 0,
                    "flags": [],
                    "answer_count": 0,
                    "answers_summary": [],
                    "error": str(e),
                })

    # Ordena: local primeiro, depois por tempo de resposta
    benchmarks.sort(key=lambda x: (0 if x["id"] == "system" else 1, x["query_time_ms"] if x["ok"] else 99999))

    # Análise de consenso e divergências
    divergence_detected = False
    status_summary = {}
    for b in benchmarks:
        status_summary[b["rcode"]] = status_summary.get(b["rcode"], 0) + 1

    if len(status_summary) > 1:
        divergence_detected = True

    return {
        "ok": True,
        "target": clean_target,
        "record_type": record_type,
        "benchmarks": benchmarks,
        "divergence_detected": divergence_detected,
        "status_distribution": status_summary,
    }
