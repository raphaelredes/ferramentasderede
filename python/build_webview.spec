# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — Ferramentas de Rede portable executable.
#
# Single-file portable build that bundles:
#   - main_webview.py entry point (FastAPI + pywebview)
#   - electron/dist/   → 'gui' folder (frontend build)
#   - src/system/scripts/*.ps1 → PowerShell scripts used by WinRM handler
#   - assets/*         → icons, logos
#   - mac-vendor-lookup OUI database
#   - dnspython (Windows + WMI optional helper handled by graceful fallback in
#     src/network/dns_resolver.py — but we still ship its modules)
#
# Version is now derived from electron/package.json — the single source of
# truth. Bumping `version` there propagates to: this spec (APP_VERSION below),
# Python runtime (src/config/settings.py reads the same file), and the UI
# (src/data/changelog.ts re-exports it from package.json). The changelog
# *entries* still need a manual append, but the version string does not.

block_cipher = None

import json
def _read_version_from_package_json():
    try:
        with open('../electron/package.json', 'r', encoding='utf-8') as f:
            return json.load(f).get('version', '0.0.0-dev')
    except Exception as e:
        print(f"WARN: spec failed to read electron/package.json version: {e}")
        return '0.0.0-dev'
APP_VERSION = _read_version_from_package_json()

frontend_dist = '../electron/dist'

# Ship package.json inside the bundle so settings.APP_VERSION can resolve at
# runtime without needing the source tree alongside the .exe.
added_files = [
    ('assets/*.*', 'assets'),
    ('data', 'data'),
    (frontend_dist, 'gui'),
    ('src/system/scripts/*.ps1', 'src/system/scripts'),
    ('../electron/package.json', '.'),
    # Bundled iperf2 binary (+ its BSD license) for the bandwidth-test tab.
    # Resolved at runtime via sys.frozen/_MEIPASS in src/network/iperf.py.
    ('bin/*', 'bin'),
    # Third-party license attributions (compliance — MIT/BSD/Apache require the
    # notice in binary redistribution; LGPL/MPL items documented here too).
    ('../THIRD-PARTY-LICENSES.txt', '.'),
]

from PyInstaller.utils.hooks import collect_submodules, collect_all, collect_data_files
import sys
import os

sys.path.append(os.path.abspath('.'))

# --- Collect transitively from packages with non-trivial data files ---
src_datas, src_binaries, src_hiddenimports = collect_all('src')

# pywebview ships native .NET DLLs and edge binaries on Windows — collect_all is
# the only reliable way to get them all.
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

# mac-vendor-lookup ships the OUI vendors text file as package data; without
# this the offline vendor lookup degrades to the embedded fallback only.
try:
    mvl_datas = collect_data_files('mac_vendor_lookup', include_py_files=False)
except Exception:
    mvl_datas = []

# dnspython has many submodules and Windows-only helpers (dns.win32util pulls
# in `wmi` which can fail at import — our resolver swallows that — but we
# still include the package so resolve_ip / resolve_hostname have what they
# need at runtime).
dns_hiddenimports = collect_submodules('dns')

# pypsrp + cryptography + cffi: large native deps for WinRM. collect_submodules
# catches lazily-loaded modules that the static analyzer misses.
pypsrp_hiddenimports = collect_submodules('pypsrp')
crypto_hiddenimports = collect_submodules('cryptography')

# pysnmp (SNMP tool) + its pyasn1 dep load MIB/codec modules lazily — the
# static analyzer misses them. collect_submodules pulls the whole tree.
pysnmp_hiddenimports = collect_submodules('pysnmp')
pyasn1_hiddenimports = collect_submodules('pyasn1')

# setuptools >= 80 unbundled jaraco.* / more_itertools / importlib_* —
# pkg_resources now imports them as real top-level packages at runtime via
# the pyi_rth_pkgres hook, and PyInstaller's static analyzer misses them.
# Use collect_all (datas + binaries + hidden imports) so each package is
# fully bundled, not just statically referenced.
pkg_resources_extras_datas = []
pkg_resources_extras_binaries = []
pkg_resources_extras_hiddenimports = []
for _pkg in ('jaraco', 'jaraco.text', 'jaraco.functools', 'jaraco.context',
             'jaraco.collections', 'more_itertools', 'importlib_resources',
             'importlib_metadata', 'zipp', 'platformdirs',
             'pkg_resources'):
    try:
        _d, _b, _h = collect_all(_pkg)
        pkg_resources_extras_datas += _d
        pkg_resources_extras_binaries += _b
        pkg_resources_extras_hiddenimports += _h
    except Exception:
        pass

hidden_imports = list(set(
    collect_submodules('src')
    + src_hiddenimports
    + webview_hiddenimports
    + dns_hiddenimports
    + pypsrp_hiddenimports
    + crypto_hiddenimports
    + pysnmp_hiddenimports
    + pyasn1_hiddenimports
    + pkg_resources_extras_hiddenimports
))

a = Analysis(
    ['main_webview.py'],
    pathex=['.', 'src'],
    binaries=src_binaries + webview_binaries + pkg_resources_extras_binaries,
    datas=added_files + src_datas + webview_datas + mvl_datas + pkg_resources_extras_datas,
    hiddenimports=[
        # FastAPI / uvicorn stack
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.responses',
        'starlette',
        'starlette.responses',
        'pydantic',
        # GUI
        'webview',
        'clr_loader',
        'pythonnet',
        # Multi-VLAN / multi-domain networking deps (1.2.2)
        'dns',
        'dns.resolver',
        'dns.reversename',
        'dns.exception',
        'mac_vendor_lookup',
        'psutil',
        # SNMP + NTP tools (Sprint: more network tools)
        'ntplib',
        'pysnmp',
        'pysnmp.hlapi',
        'pysnmp.hlapi.v3arch',
        'pysnmp.hlapi.v3arch.asyncio',
        'pyasn1',
        'pyasn1.codec.ber',
        # WinRM / remote
        'pypsrp',
        'pypsrp.host',
        'pypsrp.powershell',
        'pypsrp.wsman',
        'pypsrp.exceptions',
        'winrm',
        'cryptography',
        'cryptography.hazmat',
        'cryptography.hazmat.bindings',
        'spnego',
        'requests',
        'requests_ntlm',
        # Networking utilities
        'wakeonlan',
        'socket',
        'socketserver',
        'http.server',
        'webbrowser',
        # pkg_resources runtime dependencies (setuptools >= 80 unbundled these)
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
        'jaraco.collections',
        'more_itertools',
        'importlib_resources',
        'importlib_metadata',
        'zipp',
        'platformdirs',
        # stdlib that PyInstaller sometimes misses when imported lazily
        'concurrent.futures',
        'queue',
        'threading',
        'json',
        'sqlite3',
        'base64',
        'hashlib',
        'secrets',
        'logging',
        'logging.handlers',
        'ipaddress',
        'subprocess',
        # Internal modules — explicit so static analysis doesn't drop them
        'src.system.core.winrm_handler',
        'src.system.core.remote_commands',
        'src.system.core.local_commands',
        'src.system.core.local_handler',
        'src.network.interfaces',
        'src.network.dns_resolver',
        'src.network.ping',
        'src.network.iperf',
        'src.network.mtr',
        'src.network.traffic',
        'src.network.tls_check',
        'src.network.tcp_ping',
        'src.network.pmtu',
        'src.network.netstat',
        'src.network.snmp_tool',
        'src.network.ntp_tool',
        'src.network.http_check',
        'src.network.traceroute',
        'src.network.scanner',
        'src.network.monitor',
        'src.network.tools',
        'src.network.mac_utils',
        'src.network.vendor_utils',
        'api.routes.network',
        'api.routes.security',
        'api.routes.settings',
        'api.routes.system',
    ] + hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy scientific / data libs — not used, slim the bundle
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        # Test / build tooling
        'pytest',
        'setuptools',
        'customtkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

from PyInstaller.building.splash import Splash

splash = Splash(
    'assets/splash.png',
    binaries=a.binaries,
    datas=a.datas,
)


exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Ferramentas.de.Rede.v' + APP_VERSION,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\logo_fixed.ico',
    uac_admin=False,
)


