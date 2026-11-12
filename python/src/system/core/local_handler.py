import subprocess
import logging
import json
import os

class LocalHandler:
    def __init__(self, target_ip, username, password):
        self.target_ip = target_ip
        self.username = username
        self.password = password

    def connect(self):
        # Local connection is always "connected"
        return {"success": True}

    def close(self):
        # Best-effort: drop the password reference so a leaked handler object
        # doesn't keep the operator's password alive in memory.
        self.password = None

    def execute_script(self, script: str):
        """Executes a PowerShell script locally via stdin (-Command -) without -EncodedCommand."""
        try:
            wrapped_script = f"""
            $OutputEncoding = [System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
            $ErrorActionPreference = 'Stop'
            try {{
                {script}
            }} catch {{
                Write-Error $_
                exit 1
            }}
            """

            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"]
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == 'nt' else 0
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            try:
                process = subprocess.run(
                    cmd,
                    input=wrapped_script,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    creationflags=creation_flags,
                    startupinfo=startupinfo,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "Local Execution Error: timeout after 300s."}

            output_lines = process.stdout.splitlines()

            if process.returncode != 0:
                error_msg = process.stderr or "Unknown error"
                return {"success": False, "error": f"Local Execution Error: {error_msg}"}

            return {"success": True, "output": output_lines}

        except Exception as e:
            logging.error(f"Local execution failed: {e}")
            return {"success": False, "error": str(e)}
