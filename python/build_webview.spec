# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Frontend assets path (relative to python/ directory)
frontend_dist = '../electron/dist'

added_files = [
    ('assets/*.*', 'assets'),
    ('data', 'data'),
    (frontend_dist, 'gui'), # Bundle frontend build into 'gui' folder
    ('src/system/scripts/*.ps1', 'src/system/scripts'), # Bundle PowerShell scripts
]

from PyInstaller.utils.hooks import collect_submodules, collect_all
import sys
import os

# Ensure we can find 'src'
sys.path.append(os.path.abspath('.'))

# Collect everything from src
src_datas, src_binaries, src_hiddenimports = collect_all('src')

hidden_imports = collect_submodules('src') + src_hiddenimports

a = Analysis(
    ['main_webview.py'],
    pathex=['.', 'src'],
    binaries=src_binaries,
    datas=added_files + src_datas,
    hiddenimports=[
        'uvicorn',
        'fastapi',
        'webview',
        'clr_loader',
        'pythonnet',
        'PIL._tkinter_finder',
        'tkinter',
        'tkinter.ttk',
        'customtkinter',
        'pypsrp',
        'pypsrp.host',
        'pypsrp.powershell',
        'winrm',
        'cryptography',
        'spnego',
        'requests',
        'requests_ntlm',
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
        'src.system.core.winrm_handler',
        'src.system.core.remote_commands',
        'src.system.core.local_commands',
        'src.system.core.local_handler',
    ] + hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pytest',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Ferramentas de Rede v1.2.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # GUI mode (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\logo_fixed.ico',
    uac_admin=True,
)
