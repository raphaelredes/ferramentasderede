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
