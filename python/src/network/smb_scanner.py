# python/src/network/smb_scanner.py
"""Módulo de enumeração e auditoria de compartilhamentos de rede SMB/CIFS.

Descobre pastas compartilhadas em hosts remotos (incluindo compartilhamentos
administrativos ocultos C$, ADMIN$) e testa acessibilidade.
"""

import subprocess
import re
import socket
import logging
from typing import Dict, List, Any, Optional

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
    if not _is_port_445_open(target_host):
        return {
            "target": target_host,
            "smb_available": False,
            "error": "Porta SMB (TCP 445) fechada ou inacessível.",
            "shares": []
        }

    shares: List[Dict[str, Any]] = []
    
    # Execução via PowerShell Get-SmbShare ou 'net view' nativo do Windows
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"]
        
        # Script seguro para listar compartilhamentos via WMI/RPC ou net view
        ps_script = f"""
        try {{
            $shares = Get-WmiObject -Class Win32_Share -ComputerName '{target_host}' -ErrorAction Stop
            $shares | ForEach-Object {{
                [PSCustomObject]@{{
                    Name = $_.Name
                    Path = $_.Path
                    Description = $_.Description
                    Type = $_.Type
                }}
            }} | ConvertTo-Json
        }} catch {{
            $netView = net view \\\\{target_host} 2>&1
            $netView | Out-String
        }}
        """
        
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
        startup_info.wShowWindow = 0

        proc = subprocess.run(
            cmd + [ps_script],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=creation_flags,
            startupinfo=startup_info
        )

        
        raw_output = proc.stdout.strip()
        
        # Tentar fazer parse JSON se veio de WMI
        import json
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
                            "path": f"\\\\{target_host}\\{name}",
                            "description": parts[2] if len(parts) > 2 else "",
                            "is_hidden": name.endswith("$"),
                            "type": parts[1]
                        })

    except Exception as exc:
        logging.debug(f"Erro na enumeração de compartilhamentos para {target_host}: {exc}")
        return {
            "target": target_host,
            "smb_available": True,
            "error": str(exc),
            "shares": []
        }

    return {
        "target": target_host,
        "smb_available": True,
        "total_shares": len(shares),
        "shares": shares
    }
