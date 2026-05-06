import json
import logging
import sys
from pathlib import Path

class UserSessionManager:
    def __init__(self, handler):
        self.handler = handler
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
            self.scripts_dir = base_path / "src" / "system" / "scripts"
        else:
            # Assumes this file is in src/system/core/
            self.scripts_dir = Path(__file__).parent.parent / "scripts"

    def _load_script(self, script_name, replacements=None):
        """Carrega um script PowerShell do arquivo e aplica substituições."""
        script_path = self.scripts_dir / f"{script_name}.ps1"
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                script_content = f.read()
            
            if replacements:
                for key, value in replacements.items():
                    script_content = script_content.replace(key, str(value))
            
            return script_content
        except FileNotFoundError:
            logging.error(f"Script PowerShell não encontrado: {script_path}")
            raise
        except Exception as e:
            logging.error(f"Erro ao carregar script {script_name}: {e}")
            raise

    def list_connected_users(self):
        """Lista usuários conectados usando agregação de query user, quser e WMI."""
        script = self._load_script("list_connected_users")
        try:
            result = self.handler.execute_script(script)
            output_lines = result.get("output", [])
            
            # DEBUG: Write raw output to file (in APP_DATA_DIR, not the user's Desktop).
            try:
                from src.config.settings import APP_DATA_DIR
                import os as _os
                debug_path = _os.path.join(APP_DATA_DIR, "debug_sessions.txt")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write("=== SCRIPT OUTPUT ===\n")
                    for line in output_lines:
                        f.write(line + "\n")
                    f.write("=== END OUTPUT ===\n")
            except Exception as e:
                logging.debug(f"Failed to write debug_sessions.txt: {e}")

            parsed_users = []
            json_start = False
            json_lines = []

            for line in output_lines:
                if "=== RESULTADO_JSON_INICIO ===" in line:
                    json_start = True
                    json_lines = []
                    continue
                elif "=== RESULTADO_JSON_FIM ===" in line:
                    json_start = False
                    try:
                        full_json = "".join(json_lines)
                        users_data = json.loads(full_json)
                        if isinstance(users_data, dict): users_data = [users_data]
                        if isinstance(users_data, list):
                            for user in users_data:
                                parsed_users.append({
                                    'UserName': user.get('UserName', 'Unknown'),
                                    'ID': user.get('SessionId', 'Unknown'),
                                    'State': user.get('State', 'Unknown'),
                                    'SessionName': user.get('SessionName', ''),
                                    'Source': user.get('Source', 'Unknown'),
                                    'LogonTime': user.get('LogonTime', 'N/A'),
                                    'Duration': user.get('Duration', 'N/A'),
                                    'IdleTime': user.get('IdleTime', 'N/A')
                                })
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decode error: {e}")
                    continue
                if json_start:
                    json_lines.append(line)

            logging.info(f"DEBUG: Parsed users list: {parsed_users}")
            yield f"✅ Encontrados {len(parsed_users)} usuários conectados.\n", parsed_users

        except Exception as e:
            logging.error(f"Erro no list_connected_users: {e}")
            yield f"Erro ao listar usuários: {str(e)}\n", []

    def disconnect_user(self, session_id):
        logging.info(f"Executing 'disconnect_user' for session ID {session_id}")
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{ msg {session_id} /TIME:5 "Você será desconectado em 5 segundos pelo administrador." 2>&1 | Out-Null; Write-Output "Aviso enviado." }} catch {{ Write-Output "Aviso falhou." }}
        Start-Sleep -Seconds 5
        try {{ Write-Output "Tentando rwinsta..."; rwinsta {session_id} 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) {{ Write-Output "Sucesso rwinsta."; exit 0 }} }} catch {{}}
        try {{ Write-Output "Tentando logoff..."; logoff {session_id} 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) {{ Write-Output "Sucesso logoff."; exit 0 }} }} catch {{}}
        Write-Output "Falha ao desconectar."
        exit 1
        """
        result = self.handler.execute_script(ps_script)
        output_msg = "\\n".join(result.get("output", []))
        if result.get("success") and ("Sucesso" in output_msg or "desconectada" in output_msg):
             yield f"Sessão {session_id} desconectada com sucesso."
        else:
             yield f"Falha ao desconectar sessão {session_id}. Detalhes:\\n{output_msg}"

    def get_user_activity_events(self, start_time, end_time):
        logging.info(f"Executing 'get_user_activity_events' for period {start_time} to {end_time}")
        script = self._load_script("get_user_activity", {"__START_TIME__": start_time, "__END_TIME__": end_time})
        result = self.handler.execute_script(script)
        full_json_str = "".join(result.get("output", []))
        if not full_json_str:
            yield {"error": "no_output"}
            return
        try:
            event_list = json.loads(full_json_str)
            if isinstance(event_list, dict) and "error" in event_list:
                yield event_list
            else:
                yield [event_list] if isinstance(event_list, dict) else event_list
        except json.JSONDecodeError:
            yield {"error": "json_decode"}
