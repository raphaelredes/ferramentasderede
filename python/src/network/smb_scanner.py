# python/src/network/smb_scanner.py
"""Módulo de enumeração e auditoria de compartilhamentos de rede SMB/CIFS.

Descobre pastas compartilhadas em hosts remotos (incluindo compartilhamentos
administrativos ocultos C$, ADMIN$) e testa acessibilidade.
"""

import json
import logging
import os
import re
import socket
import subprocess
from typing import Dict, List, Any, Optional

_SAFE_TARGET_RE = re.compile(
    r"^(?:(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9][A-Za-z0-9._\-]{0,252})$"
)

_SMB_ENUM_PS_SCRIPT = (
    "$target = $env:NT_SMB_TARGET; "
    "$user = $env:NT_SMB_USER; "
    "$pass = $env:NT_SMB_PASS; "
    "Remove-Item Env:\\NT_SMB_TARGET, Env:\\NT_SMB_USER, Env:\\NT_SMB_PASS -ErrorAction SilentlyContinue; "
    "try { "
    "    $wmiParams = @{ Class = 'Win32_Share'; ComputerName = $target; ErrorAction = 'Stop' }; "
    "    if ($user -and $pass) { "
    "        $sec = ConvertTo-SecureString $pass -AsPlainText -Force; "
    "        $wmiParams['Credential'] = New-Object System.Management.Automation.PSCredential($user, $sec); "
    "    }; "
    "    Remove-Variable pass -ErrorAction SilentlyContinue; "
    "    $shares = Get-WmiObject @wmiParams; "
    "    $shares | ForEach-Object { "
    "        [PSCustomObject]@{ Name = $_.Name; Path = $_.Path; Description = $_.Description; Type = $_.Type } "
    "    } | ConvertTo-Json "
    "} catch { "
    "    Remove-Variable pass -ErrorAction SilentlyContinue; "
    "    $netView = & net.exe view \"\\\\$target\" 2>&1; "
    "    $netView | Out-String "
    "}"
)


def _is_safe_smb_target(value: str) -> bool:
    if not isinstance(value, str):
        return False
    cleaned = value.strip()
    if not cleaned or not _SAFE_TARGET_RE.match(cleaned):
        return False
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", cleaned):
        return all(0 <= int(o) <= 255 for o in cleaned.split("."))
    return True


def _is_port_445_open(ip: str, timeout: float = 1.0) -> bool:
    """Verifica rapidamente se a porta 445 (SMB) está acessível."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, 445)) == 0
    except Exception:
        return False


def scan_smb_shares(target_host: str, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Enumera compartilhamentos SMB disponíveis no host remoto."""
    clean_target = (target_host or "").strip() if isinstance(target_host, str) else ""
    if not _is_safe_smb_target(clean_target):
        return {
            "target": clean_target,
            "smb_available": False,
            "error": "Endereço ou hostname de destino inválido.",
            "shares": []
        }

    if (username and "\x00" in username) or (password and "\x00" in password):
        return {
            "target": clean_target,
            "smb_available": False,
            "error": "Credenciais contêm caracteres inválidos.",
            "shares": []
        }

    if not _is_port_445_open(clean_target):
        return {
            "target": clean_target,
            "smb_available": False,
            "error": "Porta SMB (TCP 445) fechada ou inacessível.",
            "shares": []
        }

    shares: List[Dict[str, Any]] = []

    # Execução via PowerShell (parâmetros via env vars, nunca interpolados no script)
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _SMB_ENUM_PS_SCRIPT]

        env = os.environ.copy()
        env["NT_SMB_TARGET"] = clean_target
        if username and password:
            env["NT_SMB_USER"] = username
            env["NT_SMB_PASS"] = password
        else:
            env.pop("NT_SMB_USER", None)
            env.pop("NT_SMB_PASS", None)

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
        startup_info.wShowWindow = 0

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            creationflags=creation_flags,
            startupinfo=startup_info
        )

        raw_output = proc.stdout.strip()

        # Tentar fazer parse JSON se veio de WMI
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, dict):
                parsed = [parsed]
            for item in parsed:
                name = item.get("Name", "")
                is_admin = name.endswith("$")
                shares.append({
                    "name": name,
                    "path": item.get("Path", ""),
                    "description": item.get("Description", ""),
                    "is_hidden": is_admin,
                    "type": "Admin" if is_admin else "Shared Disk"
                })
        except Exception:
            # Fallback: Parse output do 'net view'
            for line in raw_output.splitlines():
                line = line.strip()
                if "Disk" in line or "Impressora" in line or "Print" in line:
                    parts = re.split(r'\s{2,}', line)
                    if len(parts) >= 2:
                        name = parts[0]
                        shares.append({
                            "name": name,
                            "path": f"\\\\{clean_target}\\{name}",
                            "description": parts[2] if len(parts) > 2 else "",
                            "is_hidden": name.endswith("$"),
                            "type": parts[1]
                        })

    except Exception as exc:
        logging.debug(f"Erro na enumeração de compartilhamentos para {clean_target}: {exc}")
        return {
            "target": clean_target,
            "smb_available": True,
            "error": str(exc),
            "shares": []
        }

    return {
        "target": clean_target,
        "smb_available": True,
        "total_shares": len(shares),
        "shares": shares
    }
