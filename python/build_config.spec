# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Coletar todos os arquivos de dados necessários
added_files = [
    ('languages/*.json', 'languages'),
    ('assets/*.*', 'assets'),
    ('data', 'data'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
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
    ],
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
    name='FerramentasDeRede_v1.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Sem console (modo GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.ico',  # Ícone da aplicação
    version_file=None,
)
