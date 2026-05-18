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
        """Executes a PowerShell script locally."""
        try:
            # Wrap script to ensure UTF-8 output and handle errors
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

            import base64
            encoded_script = base64.b64encode(wrapped_script.encode('utf-16le')).decode('utf-8')

            # PowerShell -EncodedCommand has a documented ~32KB cap on the
            # encoded argument. Refuse oversized scripts up front instead of
            # hitting a cryptic "command line too long" error from CreateProcess.
            if len(encoded_script) > 32000:
                return {"error": "Script muito longo para -EncodedCommand."}

            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script]

            try:
                # Hard timeout so a hanging local script can't pin this thread
                # indefinitely. 5 minutes is generous enough for any local
                # script we ship; longer signals a real hang.
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                return {"error": "Local Execution Error: timeout after 300s."}

            output_lines = process.stdout.splitlines()

            if process.returncode != 0:
                error_msg = process.stderr or "Unknown error"
                return {"error": f"Local Execution Error: {error_msg}"}

            return {"success": True, "output": output_lines}

        except Exception as e:
            logging.error(f"Local execution failed: {e}")
            return {"error": str(e)}
