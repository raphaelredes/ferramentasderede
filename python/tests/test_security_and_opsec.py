"""Regression tests for OPSEC guardrails, security hardening, and repaired code paths."""

from __future__ import annotations

import hashlib
import os
import pathlib
import sys
import types
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PYTHON_DIR = TESTS_DIR.parent
REPO_ROOT = PYTHON_DIR.parent

for p in (str(PYTHON_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from api.server import app
from api.routes import ad_tools as ad_routes
from api.routes import batch_ops as batch_routes
from api.routes import l2_discovery as l2_routes
from api.routes import network as network_routes
from api.routes import settings as settings_routes
from scripts import check_opsec
from src.config.settings import UI_PREFS_FILE
from src.network import ad_tools as ad_lib
from src.network import dns_diagnostics, http_check, mtr, smb_scanner
from src.network.tools import NetworkTools
from src.network.vendor_utils import VendorUtils
from src.system.core import batch_runner, local_commands
from src.system.core.hoptodesk_manager import HopToDeskManager
from src.utils.report_generator import (
    PRINT_SCRIPT_CSP_HASH,
    generate_inventory_report_html,
    generate_sla_report_html,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. OPSEC Guardrails
# ---------------------------------------------------------------------------

def test_repo_has_zero_opsec_leaks():
    assert check_opsec.main([]) == 0


def test_check_opsec_detects_synthetic_leaks_and_allows_neutral_inputs(monkeypatch):
    win_leak = "C:\\Use" + "rs\\alice\\Desktop\\note.txt"
    posix_leak = "/c/Use" + "rs/bob/repo"
    host_leak = "ADM" + "-99999"
    net1_leak = "10." + "212.1.5"
    net2_leak = "10.10." + "38.10"
    net3_leak = "10.10." + "90.7"
    net4_leak = "10.200." + "5.1"

    assert check_opsec.scan_text("sample.txt", win_leak)
    assert check_opsec.scan_text("sample.txt", posix_leak)
    assert check_opsec.scan_text("sample.txt", host_leak)
    for net in (net1_leak, net2_leak, net3_leak, net4_leak):
        assert check_opsec.scan_text("sample.txt", net), f"failed to flag {net}"

    # Public/documentation examples must pass
    neutral = "\n".join([
        r"C:\Users\Public\Desktop\HopToDesk.exe",
        "192.0.2.10",
        "198.51.100.7",
        "corp.example.com",
        "1.1.1.1",
    ])
    assert check_opsec.scan_text("neutral.txt", neutral) == []

    # Hash matcher splits dotted/hyphenated tokens without plaintext in script
    digest = hashlib.sha256(b"syntheticorgtoken").hexdigest()
    monkeypatch.setitem(check_opsec.BLOCKED_TOKEN_HASHES, digest, "TEST_ORG")
    hits = check_opsec.scan_text("domain.txt", "host.syntheticorgtoken.invalid")
    assert any("HASH:TEST_ORG" in rule for _, _, rule in hits)


# ---------------------------------------------------------------------------
# 2. Report XSS Escaping & CSP Headers
# ---------------------------------------------------------------------------

def test_report_html_escapes_dynamic_fields():
    inv_html = generate_inventory_report_html([
        {
            "name": "<script>alert(1)</script>",
            "address": '1.1.1.1" onclick="evil()',
            "group_name": "<b>Grupo</b>",
            "vendor": "<svg onload=alert(2)>",
            "status": "online",
            "latency": 12.5,
        }
    ])
    assert "<script>alert(1)</script>" not in inv_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in inv_html
    assert 'onclick="evil()"' not in inv_html
    assert "&lt;svg onload=alert(2)&gt;" in inv_html

    sla_html = generate_sla_report_html(
        'dc01<img src=x onerror=alert(3)>',
        '<em>192.0.2.5</em>',
        {
            "summary": {"uptime_percent": "<script>x</script>", "avg_latency": 5, "avg_jitter": 1, "mos_score": 4.4},
            "points": [{"time_label": "<i>10:00</i>", "is_online": True, "latency_ms": 5, "jitter_ms": 1, "packet_loss": 0}],
        },
    )
    assert "<img src=x onerror=alert(3)>" not in sla_html
    assert "&lt;img src=x onerror=alert(3)&gt;" in sla_html
    assert "<em>192.0.2.5</em>" not in sla_html
    assert "<script>x</script>" not in sla_html


def test_reports_endpoint_sets_security_headers():
    resp = client.post("/reports/generate", json={"report_type": "inventory"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert f"script-src '{PRINT_SCRIPT_CSP_HASH}'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]


# ---------------------------------------------------------------------------
# 3. HopToDesk Binary Verification & LPE Defenses
# ---------------------------------------------------------------------------

def test_hoptodesk_verify_pe_rejects_non_mz_and_checks_templates(tmp_path):
    bad_file = tmp_path / "HopToDesk.exe"
    bad_file.write_bytes(b"NOT_A_PE_BINARY")
    assert HopToDeskManager._verify_pe_authenticode(bad_file) is False

    fake_pe = tmp_path / "FakeSigned.exe"
    fake_pe.write_bytes(b"MZ" + b"\x00" * 1024)
    if sys.platform == "win32":
        # Unsigned binary must be rejected by Get-AuthenticodeSignature on Windows
        assert HopToDeskManager._verify_pe_authenticode(fake_pe) is False

    ps1 = (PYTHON_DIR / "src" / "system" / "scripts" / "get_system_info.ps1").read_text(encoding="utf-8")
    htd_py = (PYTHON_DIR / "src" / "system" / "core" / "hoptodesk_manager.py").read_text(encoding="utf-8")
    sys_py = (PYTHON_DIR / "api" / "routes" / "system.py").read_text(encoding="utf-8")

    assert "HKEY_CLASSES_ROOT\\hoptodesk" not in ps1
    assert "HKEY_CLASSES_ROOT\\hoptodesk" not in htd_py
    assert "/rl HIGHEST" not in htd_py
    assert "/rl HIGHEST" not in sys_py


# ---------------------------------------------------------------------------
# 4. Input Validation & Injection Defenses
# ---------------------------------------------------------------------------

def test_injection_and_target_validation_rejected():
    assert client.post("/l2/smb-shares", json={"target": "127.0.0.1'; whoami; #"}).status_code == 422
    assert client.post("/l2/lldp-listen", json={"interface_ip": "127.0.0.1 && dir"}).status_code == 422
    assert client.get("/l2/arp-conflicts", params={"interface_ip": "not-an-ip"}).status_code == 400

    res_smb = smb_scanner.scan_smb_shares("127.0.0.1'; calc.exe; #")
    assert res_smb["smb_available"] is False
    assert "inválido" in res_smb["error"].lower()

    assert client.post("/ad/test-ports", json={"target": "-flag.example.com"}).status_code == 422
    assert client.post("/ad/test-srv", json={"domain": "example.com;id", "dns_server": "bad-ip"}).status_code == 422
    assert client.post("/ad/check-skew", json={"target": "bad target"}).status_code == 422
    assert client.post("/ad/fsmo", json={"domain": "-domain"}).status_code == 422
    assert client.post("/ad/replication", json={"dc_target": "dc01 & whoami"}).status_code == 422

    assert ad_lib.get_ad_fsmo_roles("example.com & whoami")["ok"] is False
    assert ad_lib.check_ad_replication("-badflag")["ok"] is False

    assert NetworkTools._safe_target("-evil") is False
    assert NetworkTools._safe_target("host01.example.com") is True
    assert network_routes._is_safe_remote_target("-evil") is False
    assert network_routes._is_safe_remote_target("192.0.2.10") is True

    ok_winrm, _ = local_commands.LocalCommands("bad target; calc").enable_remote_winrm("admin", "pass")
    assert ok_winrm is False

    assert client.post(
        "/tools/terminal/external",
        json={"ip": "-host", "username": "u", "password": "p"},
    ).status_code == 400


def test_dns_benchmark_filters_non_ip_custom_servers(monkeypatch):
    seen_servers = []

    def fake_query(target, record_type="A", dns_server=None, timeout=3.0):
        seen_servers.append(dns_server)
        return {"answers": [], "rcode": "NXDOMAIN", "query_time_ms": 1.0}

    monkeypatch.setattr(dns_diagnostics, "get_system_nameservers", lambda: [])
    monkeypatch.setattr(dns_diagnostics, "query_dns_record", fake_query)

    dns_diagnostics.benchmark_dns_resolvers(
        "example.com",
        extra_servers=[
            {"ip": "evil.example.com;id", "name": "Invalid"},
            {"ip": "192.0.2.53", "name": "ValidDocDNS"},
        ],
    )
    assert "evil.example.com;id" not in seen_servers
    assert "192.0.2.53" in seen_servers


def test_vendor_utils_masks_oui_and_defaults_offline(monkeypatch):
    requested_urls = []

    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"company": "ExampleVendor"}'

    def fake_urlopen(req, timeout=2.0):
        requested_urls.append(req.full_url)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    vendor = VendorUtils.lookup_vendor_online("AA:BB:CC:11:22:33")
    assert vendor == "ExampleVendor"
    assert requested_urls and requested_urls[0].endswith("/AA:BB:CC:00:00:00")

    called_online = {"flag": False}
    monkeypatch.setattr(
        VendorUtils,
        "lookup_vendor_online",
        classmethod(lambda cls, mac, timeout=2.0: called_online.__setitem__("flag", True) or "X"),
    )
    monkeypatch.setattr(VendorUtils, "load_prefixes", classmethod(lambda cls, force=False: {}))
    monkeypatch.setattr(VendorUtils, "_load_dynamic_cache", classmethod(lambda cls: None))
    VendorUtils._dynamic_cache = {}
    VendorUtils.get_vendor("02:11:22:33:44:55")
    assert called_online["flag"] is False


def test_electron_and_webview_url_and_id_validators():
    webview_src = (PYTHON_DIR / "main_webview.py").read_text(encoding="utf-8")
    main_ts_src = (REPO_ROOT / "electron" / "electron" / "main.ts").read_text(encoding="utf-8")

    assert "def _is_safe_external_url" in webview_src
    assert 'r"[A-Za-z0-9][A-Za-z0-9._-]*"' in webview_src
    assert 're.fullmatch(r"\\d{1,32}", clean_id)' in webview_src
    assert "id.replace(/\\D+/g, '').slice(0, 32)" in main_ts_src


# ---------------------------------------------------------------------------
# 5. Functional Bug Regressions
# ---------------------------------------------------------------------------

def test_settings_uses_app_data_dir_file():
    assert settings_routes.SETTINGS_FILE == UI_PREFS_FILE


def test_batch_execute_and_runner_flow(monkeypatch):
    monkeypatch.setattr(batch_routes.vault, "is_unlocked", False)
    resp = client.post(
        "/batch/execute",
        json={"command": "hostname", "targets": [{"ip": "192.0.2.10", "name": "Host1"}]},
    )
    assert resp.status_code == 401

    calls = {"init": [], "closed": 0}

    class FakeWinRM:
        def __init__(self, target_ip, username, password, target_hostname=None, target_domain=None):
            calls["init"].append((target_ip, username, password))

        def connect(self):
            return {"success": True}

        def execute_script(self, script):
            return {"success": True, "output": ["HOST01"]}

        def close(self):
            calls["closed"] += 1

    monkeypatch.setattr(batch_runner, "WinRMHandler", FakeWinRM)
    res = batch_runner.execute_batch_command(
        targets=[{"ip": "192.0.2.10", "name": "Host1", "username": "op", "password": "pw"}],
        command="hostname",
        max_workers=2,
    )
    assert len(res) == 1
    assert res[0]["success"] is True
    assert res[0]["stdout"] == "HOST01"
    assert calls["init"] == [("192.0.2.10", "op", "pw")]
    assert calls["closed"] == 1


def test_mtr_windows_drops_ipv4_source_flag_for_tracert(monkeypatch):
    recorded_cmds = []

    def fake_run(cmd, **kwargs):
        recorded_cmds.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="  1   1 ms   1 ms   1 ms  192.0.2.1\n", stderr="")

    monkeypatch.setattr(mtr.os, "name", "nt")
    monkeypatch.setattr(mtr.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(mtr.subprocess, "STARTUPINFO", MagicMock(), raising=False)
    monkeypatch.setattr(mtr.subprocess, "STARTF_USESHOWWINDOW", 0x00000001, raising=False)
    monkeypatch.setattr(mtr.subprocess, "run", fake_run)

    hops = mtr._discover_hops("192.0.2.1", max_hops=5, source_ip="192.0.2.99")
    assert recorded_cmds
    assert "-S" not in recorded_cmds[0]
    assert hops == [{"distance": 1, "address": "192.0.2.1"}]


def test_http_check_caps_oversized_response_body(monkeypatch):
    class FakeHttpResp:
        status_code = 200
        url = "https://example.com/"
        headers = {"Content-Type": "text/plain"}
        history = []

        def iter_content(self, chunk_size=65536):
            # Yield 4 MB across chunks; http_check must stop at 2 MB
            for _ in range(64):
                yield b"A" * 65536

        def close(self):
            pass

    monkeypatch.setattr(http_check, "_measure_socket_phases", lambda *a, **kw: (1.0, 2.0, 3.0, "93.184.216.34"))
    monkeypatch.setattr("requests.Session.request", lambda *a, **kw: FakeHttpResp())

    res = http_check.check("https://example.com")
    assert res["ok"] is True
    assert res["content_length"] == 2 * 1024 * 1024
