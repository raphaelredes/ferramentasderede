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
        pass

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
            
            # Use -EncodedCommand to avoid escaping issues? Or just passed as string?
            # Passing as string with -Command is usually fine if we are careful.
            # But for complex scripts, saving to temp file or using encoded command is safer.
            # Let's try passing as -Command first, but we need to be careful with quotes.
            # Actually, RemoteCommands loads scripts that might have quotes.
            # Better to use EncodedCommand.
            
            import base64
            encoded_script = base64.b64encode(wrapped_script.encode('utf-16le')).decode('utf-8')
            
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            output_lines = process.stdout.splitlines()
            
            if process.returncode != 0:
                error_msg = process.stderr or "Unknown error"
                return {"error": f"Local Execution Error: {error_msg}"}
                
            return {"success": True, "output": output_lines}
            
        except Exception as e:
            logging.error(f"Local execution failed: {e}")
            return {"error": str(e)}
