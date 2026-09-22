# python/test_all_new_features.py
"""Bateria de testes automatizados de ponta a ponta para todas as novas funcionalidades."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from api.server import app

def run_tests():
    print("=" * 65)
    print(" INICIANDO BATERIA DE TESTES DE TODAS AS NOVAS FUNCIONALIDADES")
    print("=" * 65)

    client = TestClient(app)
    results = {}

    # Test 1: Descoberta de Camada 2 & Switch (LLDP / CDP / L2 Telemetry)
    print("\n[1/6] Testando Descoberta de Camada 2 & Switch (LLDP/CDP/L2)...")
    try:
        from src.network.lldp_cdp import capture_l2_discovery
        direct_l2 = capture_l2_discovery(timeout_seconds=2)
        print(f"  -> Chamada direta Python: success={direct_l2.get('success')}, switch={direct_l2.get('data', {}).get('switch_name')}")
        
        resp = client.post("/l2/lldp-listen", json={"timeout_seconds": 2})
        assert resp.status_code == 200, f"Status code: {resp.status_code}"
        l2_json = resp.json()
        assert l2_json.get("success") is True
        print(f"  -> Rota /l2/lldp-listen: HTTP 200 OK | Protocolo: {l2_json['data']['protocol']} | Gateway: {l2_json['data']['mgmt_ip']}")
        results["Switch / L2"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["Switch / L2"] = f"FAIL: {e}"

    # Test 2: Diagnóstico de Active Directory
    print("\n[2/6] Testando Diagnóstico de Active Directory...")
    try:
        from src.network.ad_tools import test_ad_port_matrix, test_ad_srv_records, check_kerberos_time_skew
        ports_res = test_ad_port_matrix("127.0.0.1", timeout=0.3)
        print(f"  -> Matriz de 9 portas AD (127.0.0.1): {len(ports_res)} portas testadas")
        assert len(ports_res) == 9
        
        resp = client.post("/ad/test-ports", json={"target": "127.0.0.1", "timeout": 0.3})
        assert resp.status_code == 200
        print(f"  -> Rota /ad/test-ports: HTTP 200 OK | Total: {resp.json().get('total_ports')}")
        results["Active Directory"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["Active Directory"] = f"FAIL: {e}"

    # Test 3: Pastas SMB Scanner
    print("\n[3/6] Testando Scanner de Compartilhamentos SMB...")
    try:
        from src.network.smb_scanner import scan_smb_shares
        smb_res = scan_smb_shares(target_host="127.0.0.1")
        print(f"  -> SMB Scanner local (127.0.0.1): executado com sucesso")
        
        resp = client.post("/l2/smb-shares", json={"target": "127.0.0.1"})
        assert resp.status_code == 200
        print(f"  -> Rota /l2/smb-shares: HTTP 200 OK")
        results["Pastas SMB"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["Pastas SMB"] = f"FAIL: {e}"

    # Test 4: Conflitos ARP
    print("\n[4/6] Testando Detecção de Conflitos ARP...")
    try:
        from src.network.arp_conflicts import inspect_arp_table
        arp_res = inspect_arp_table()
        print(f"  -> Tabela ARP: {arp_res.get('total_entries')} entradas, {arp_res.get('conflicts_detected')} conflitos")
        
        resp = client.get("/l2/arp-conflicts")
        assert resp.status_code == 200
        print(f"  -> Rota /l2/arp-conflicts: HTTP 200 OK | Entradas: {resp.json().get('total_entries')}")
        results["Conflitos ARP"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["Conflitos ARP"] = f"FAIL: {e}"

    # Test 5: Multi-Host Batch Runner & Snippets
    print("\n[5/6] Testando Multi-Host Batch Runner & Snippets...")
    try:
        from src.system.core.snippets_manager import list_snippets, save_snippet
        snippets = list_snippets()
        print(f"  -> Snippets carregados do SQLite: {len(snippets)} snippets")
        assert len(snippets) > 0
        
        resp = client.get("/batch/snippets")
        assert resp.status_code == 200
        snippets_list = resp.json()
        assert isinstance(snippets_list, list) and len(snippets_list) > 0
        print(f"  -> Rota /batch/snippets: HTTP 200 OK | Count: {len(snippets_list)}")
        results["Batch Runner & Snippets"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["Batch Runner & Snippets"] = f"FAIL: {e}"

    # Test 6: Emissão de Relatórios Técnicos (HTML / PDF)
    print("\n[6/6] Testando Emissão de Relatórios Técnicos...")
    try:
        from src.utils.report_generator import generate_inventory_report_html
        sample_hosts = [{"name": "Gateway Core", "address": "10.10.38.1", "status": "online", "latency": 1.2, "vendor": "Cisco", "type": "router"}]
        html_report = generate_inventory_report_html(sample_hosts)
        print(f"  -> Relatório HTML gerado ({len(html_report)} bytes)")
        assert len(html_report) > 500
        
        resp = client.post("/reports/generate", json={"report_type": "inventory", "format": "html"})
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
        print(f"  -> Rota /reports/generate: HTTP 200 OK (HTML renderizado: {len(resp.text)} chars)")
        results["Relatórios Técnicos"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["Relatórios Técnicos"] = f"FAIL: {e}"

    # Test 7: Mapeamento BGP ASN & Operadoras (Team Cymru DNS)
    print("\n[7/12] Testando Mapeamento BGP ASN (Team Cymru DNS)...")
    try:
        from src.network.asn_lookup import lookup_ip_asn
        # Test RFC1918
        res_lan = lookup_ip_asn("192.168.1.1")
        assert res_lan["asn"] == "RFC1918", f"Esperado RFC1918, obtido {res_lan}"
        print(f"  -> IP Privado 192.168.1.1: {res_lan['asn']} - {res_lan['as_name']}")

        # Test Loopback
        res_loop = lookup_ip_asn("127.0.0.1")
        assert res_loop["asn"] == "LOOPBACK"

        # Test Public IP
        res_pub = lookup_ip_asn("8.8.8.8")
        print(f"  -> IP Público 8.8.8.8: ASN={res_pub['asn']} | Provedor={res_pub['as_name']} | País={res_pub['country']}")
        assert res_pub["asn"] == "AS15169" or "GOOGLE" in res_pub["as_name"].upper()
        results["BGP ASN (Team Cymru)"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["BGP ASN (Team Cymru)"] = f"FAIL: {e}"

    # Test 8: MTR com Jitter RFC 1889 e Traceroute Estruturado NDJSON
    print("\n[8/12] Testando MTR Jitter RFC 1889 & Traceroute Streaming...")
    try:
        from src.network.mtr import _HopAccumulator
        acc = _HopAccumulator()
        acc.update(1, "8.8.8.8", 3, 3, [10, 12, 11])
        snap = acc.snapshot()
        assert len(snap) == 1
        assert snap[0]["jitter"] is not None
        assert snap[0]["history"] == [10, 12, 11]
        print(f"  -> MTR Snapshot: Hop #{snap[0]['hop']} | ASN={snap[0]['asn']} | Jitter={snap[0]['jitter']}ms | History={snap[0]['history']}")

        # Rota de streaming do traceroute
        resp = client.post("/tools/traceroute/stream", json={"target": "127.0.0.1"})
        assert resp.status_code == 200
        ndjson_lines = [l for l in resp.text.split("\n") if l.strip()]
        assert len(ndjson_lines) >= 2
        print(f"  -> Rota /tools/traceroute/stream: HTTP 200 OK | {len(ndjson_lines)} eventos NDJSON gerados")
        results["MTR Jitter & Trace Stream"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["MTR Jitter & Trace Stream"] = f"FAIL: {e}"

    # Test 9: HTTP Web Health (Waterfall, OWASP Security Headers, Redirects)
    print("\n[9/12] Testando HTTP Web Health (Waterfall, OWASP, Redirects)...")
    try:
        from src.network.http_check import check as check_http_endpoint
        http_res = check_http_endpoint("https://www.cloudflare.com", timeout=6.0)
        assert http_res.get("ok") is True, f"HTTP check failed: {http_res}"
        wf = http_res.get("timing", {})
        print(f"  -> HTTP Waterfall: DNS={wf.get('dns_ms')}ms | TCP={wf.get('tcp_ms')}ms | TLS={wf.get('tls_ms')}ms | TTFB={wf.get('ttfb_ms')}ms | Download={wf.get('download_ms')}ms")
        assert wf.get("total_ms") is not None
        sec_audit = http_res.get("security", {})
        print(f"  -> OWASP Security Headers: Score={sec_audit.get('score')} | Presentes={sec_audit.get('passed_count')}/{sec_audit.get('total_count')}")
        assert "headers" in sec_audit

        resp = client.post("/tools/http", json={"url": "https://www.cloudflare.com", "method": "GET", "timeout": 6.0})
        assert resp.status_code == 200
        http_api_data = resp.json()
        assert http_api_data.get("ok") is True
        print(f"  -> Rota /tools/http: HTTP 200 OK | Status={http_api_data.get('status')} | Score OWASP={http_api_data.get('security', {}).get('score')}")
        results["HTTP Waterfall & OWASP"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["HTTP Waterfall & OWASP"] = f"FAIL: {e}"

    # Test 10: TLS / SSL Inspector (Chain of Trust, Protocols, ALPN, Ciphers)
    print("\n[10/12] Testando TLS / SSL Inspector (Cadeia, Protocolos, ALPN, Cifras)...")
    try:
        from src.network.tls_check import check_certificate as check_tls_endpoint
        tls_res = check_tls_endpoint("cloudflare.com", port=443, timeout=5.0)
        assert tls_res.get("ok") is True, f"TLS check failed: {tls_res}"
        chain = tls_res.get("chain", [])
        print(f"  -> Cadeia de Certificados: {len(chain)} certificados identificados")
        assert len(chain) >= 1
        proto_matrix = tls_res.get("protocols", {})
        print(f"  -> Matriz de Protocolos: {proto_matrix}")
        assert "TLSv1.2" in proto_matrix and "TLSv1.3" in proto_matrix
        cipher_eval = tls_res.get("cipher_eval", {})
        print(f"  -> Cifra negociada: {cipher_eval.get('name')} | PFS={cipher_eval.get('pfs')} | AEAD={cipher_eval.get('aead')}")
        print(f"  -> ALPN negociado: {tls_res.get('alpn')}")

        resp = client.post("/tools/tls", json={"host": "cloudflare.com", "port": 443})
        assert resp.status_code == 200
        tls_api_data = resp.json()
        assert tls_api_data.get("ok") is True
        print(f"  -> Rota /tools/tls: HTTP 200 OK | Protocol={tls_api_data.get('tls_version')} | Chain={len(tls_api_data.get('chain', []))}")
        results["TLS / SSL Inspector"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["TLS / SSL Inspector"] = f"FAIL: {e}"

    # Test 11: SNMP Manager (query_interfaces, walk_custom)
    print("\n[11/12] Testando SNMP Manager (query_interfaces & walk)...")
    try:
        import asyncio
        from src.network.snmp_tool import query_interfaces, walk_custom
        # Loopback sem SNMP configurado retornará ok=False gracefully com mensagem clara sem exceção não tratada
        if_res = asyncio.run(query_interfaces("127.0.0.1", port=161, community="public", timeout=0.5, retries=0))
        assert "ok" in if_res
        print(f"  -> SNMP query_interfaces (127.0.0.1): ok={if_res.get('ok')} | msg={if_res.get('error', 'interfaces: ' + str(len(if_res.get('interfaces', []))))}")

        resp = client.post("/tools/snmp/interfaces", json={"host": "127.0.0.1", "port": 161, "community": "public", "timeout": 0.5, "retries": 0})
        assert resp.status_code == 200
        print(f"  -> Rota /tools/snmp/interfaces: HTTP 200 OK | Response ok: {resp.json().get('ok')}")

        resp_walk = client.post("/tools/snmp/walk", json={"host": "127.0.0.1", "port": 161, "community": "public", "root_oid": "1.3.6.1.2.1.1", "timeout": 0.5, "retries": 0})
        assert resp_walk.status_code == 200
        print(f"  -> Rota /tools/snmp/walk: HTTP 200 OK | Entries count: {len(resp_walk.json().get('entries', []))}")
        results["SNMP Manager (ifTable & Walk)"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["SNMP Manager (ifTable & Walk)"] = f"FAIL: {e}"

    # Test 12: Active Directory (FSMO & Replicação)
    print("\n[12/12] Testando Active Directory (FSMO & Replicação)...")
    try:
        from src.network.ad_tools import get_ad_fsmo_roles, check_ad_replication
        fsmo_res = get_ad_fsmo_roles()
        print(f"  -> get_ad_fsmo_roles: ok={fsmo_res.get('ok')}, domain={fsmo_res.get('domain')}, roles={len(fsmo_res.get('role_list', []))}")
        assert "roles" in fsmo_res

        repl_res = check_ad_replication()
        print(f"  -> check_ad_replication: ok={repl_res.get('ok')}, status={repl_res.get('status')}")
        assert "status" in repl_res

        resp_fsmo = client.post("/ad/fsmo", json={})
        assert resp_fsmo.status_code == 200
        print(f"  -> Rota /ad/fsmo: HTTP 200 OK | Domain={resp_fsmo.json().get('domain')}")

        resp_repl = client.post("/ad/replication", json={})
        assert resp_repl.status_code == 200
        print(f"  -> Rota /ad/replication: HTTP 200 OK | Status={resp_repl.json().get('status')}")
        results["AD FSMO & Replicação"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["AD FSMO & Replicação"] = f"FAIL: {e}"

    # Test 13: SNMP Security & Risk Posture Audit (NIST SP 800-123 & CISA)
    print("\n[13/13] Testando SNMP Security & Risk Posture Audit (NIST/CISA)...")
    try:
        import asyncio
        from src.network.snmp_tool import analyze_snmp_security_posture, classify_network_target, evaluate_community_strength

        # Validação de classificação de enlace (Privada vs WAN)
        priv_net = classify_network_target("192.168.1.1")
        assert priv_net["is_private"] is True
        assert priv_net["network_type"] == "RFC1918"

        wan_net = classify_network_target("8.8.8.8")
        assert wan_net["is_private"] is False
        assert wan_net["network_type"] == "PUBLIC_WAN"

        # Validação de robustez de community
        weak_comm = evaluate_community_strength("public", "2c")
        assert weak_comm["is_weak"] is True
        assert weak_comm["severity"] in ("HIGH", "CRITICAL")

        strong_comm = evaluate_community_strength("K9#mX7$vL2!pQ5@z", "2c")
        assert strong_comm["is_weak"] is False

        # Chamada direta assíncrona
        posture_res = asyncio.run(analyze_snmp_security_posture(
            host="127.0.0.1", port=161, community="public", version="2c", timeout=0.5
        ))
        assert posture_res.get("ok") is True
        assert "risk_score" in posture_res
        assert "findings" in posture_res
        assert "recommendations" in posture_res
        print(f"  -> analyze_snmp_security_posture: score={posture_res.get('risk_score')}, level={posture_res.get('risk_level')}")

        # Chamada HTTP via rota FastAPI
        resp_sec = client.post("/tools/snmp/security-audit", json={
            "host": "127.0.0.1", "port": 161, "community": "public", "version": "2c", "timeout": 0.5
        })
        assert resp_sec.status_code == 200
        sec_json = resp_sec.json()
        assert sec_json.get("ok") is True
        assert "risk_score" in sec_json
        print(f"  -> Rota /tools/snmp/security-audit: HTTP 200 OK | Risk={sec_json.get('risk_label')} (Score: {sec_json.get('risk_score')})")
        results["SNMP Security Audit (NIST/CISA)"] = "PASS"
    except Exception as e:
        print(f"  -> FALHA: {e}")
        results["SNMP Security Audit (NIST/CISA)"] = f"FAIL: {e}"

    print("\n" + "=" * 65)
    print(" RESUMO FINAL DOS TESTES DE FUNCIONALIDADES:")
    print("=" * 65)
    all_passed = True
    for feat, status in results.items():
        print(f"  * {feat.ljust(32)} : [{status}]")
        if status != "PASS":
            all_passed = False

    if all_passed:
        print("\n [SUCESSO TOTAL] 100% das novas funcionalidades validadas com retorno!")
        return 0
    else:
        print("\n [ERRO] Algumas funcionalidades falharam.")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
