# src/ferramentasderede/system/core/remote_commands.py
# Gerencia a sessão WinRM e executa comandos de alto nível.

import json
import re
import time
import logging
import os
from pathlib import Path
from .winrm_handler import WinRMHandler, WinRMError, ConnectionError, ConnectTimeout

class RemoteCommands:
    def __init__(self, target_ip, username, password):
        self.target_ip = target_ip
        self.username = username
        self.password = password
        self.handler = None
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

    def __enter__(self):
        """Permite o uso em um 'with' statement, estabelecendo a conexão."""
        try:
            self.handler = WinRMHandler(self.target_ip, self.username, self.password)
            connection_result = self.handler.connect()
            if "error" in connection_result:
                logging.error(f"WinRM connection failed for {self.target_ip}: {connection_result['error']}")
                raise ConnectionError(connection_result['error'])
            return self
        except Exception as e:
            logging.error(f"Erro em __enter__ do RemoteCommands: {type(e).__name__} - {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Garante que a conexão seja fechada ao sair do 'with'."""
        if self.handler:
            self.handler.close()
            
    def check_winrm_status(self):
        """
        Executa um comando leve para verificar se o serviço WinRM está respondendo.
        Retorna True em caso de sucesso, False em caso de falha.
        """
        try:
            script = "Write-Host 'WinRM Test OK'"
            result = self.handler.execute_script(script)
            success = result.get("success", False)
            return success
        except Exception as e:
            logging.error(f"Erro no check_winrm_status: {e}")
            return False

    def list_connected_users_winrm(self):
        """
        Lista usuários conectados usando agregação de query user, quser e WMI.
        """
        script = self._load_script("list_connected_users")
        try:
            result = self.handler.execute_script(script)
            output_lines = result.get("output", [])
            
            # DEBUG: Write raw output to file
            try:
                with open(r"C:\Users\raphael.rego\Desktop\ferramentasderede\debug_sessions.txt", "w", encoding="utf-8") as f:
                    f.write("=== SCRIPT OUTPUT ===\n")
                    for line in output_lines:
                        f.write(line + "\n")
                    f.write("=== END OUTPUT ===\n")
            except Exception as e:
                logging.error(f"Failed to write debug file: {e}")

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
                        
                        # Normalize to list if it's a single object (dict)
                        if isinstance(users_data, dict):
                            users_data = [users_data]
                            
                        if isinstance(users_data, list):
                            for user in users_data:
                                parsed_users.append({
                                    'UserName': user.get('UserName', 'Unknown'),
                                    'ID': user.get('SessionId', 'Unknown'),
                                    'State': user.get('State', 'Unknown'),
                                    'SessionName': user.get('SessionName', ''),
                                    'LogonTime': user.get('LogonTime', 'N/A'),
                                    'Duration': user.get('Duration', 'N/A'),
                                    'IdleTime': user.get('IdleTime', 'N/A')
                                })
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decode error in list_connected_users_winrm: {e}")
                    continue
                
                if json_start:
                    json_lines.append(line)

            logging.info(f"DEBUG: Parsed users list: {parsed_users}")
            yield f"✅ Encontrados {len(parsed_users)} usuários conectados.\n", parsed_users

        except Exception as e:
            logging.error(f"Erro no list_connected_users_winrm: {e}")
            yield f"Erro ao listar usuários: {str(e)}\n", []

    def disconnect_user_winrm(self, session_id):
        logging.info(f"Executing 'disconnect_user_winrm' for session ID {session_id} on {self.target_ip}")
        
        # Script PowerShell robusto para tentar desconectar
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        
        # Enviar aviso ao usuário
        try {{
            msg {session_id} /TIME:5 "Você será desconectado em 5 segundos pelo administrador." 2>&1 | Out-Null
            Write-Output "Aviso enviado para sessão {session_id}."
        }} catch {{
            Write-Output "Aviso: Não foi possível enviar mensagem (msg.exe falhou ou não suportado)."
        }}

        # Aguardar 5 segundos
        Start-Sleep -Seconds 5

        try {{
            # Tentativa 1: rwinsta (Reset Session)
            Write-Output "Tentando rwinsta para sessão {session_id}..."
            rwinsta {session_id} 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {{
                Write-Output "Sessão {session_id} desconectada com sucesso via rwinsta."
                exit 0
            }}
        }} catch {{
            Write-Output "Erro ao executar rwinsta: $_"
        }}

        try {{
            # Tentativa 2: logoff (Logoff Session)
            Write-Output "Tentando logoff para sessão {session_id}..."
            logoff {session_id} 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {{
                Write-Output "Sessão {session_id} desconectada com sucesso via logoff."
                exit 0
            }}
        }} catch {{
            Write-Output "Erro ao executar logoff: $_"
        }}

        # Se chegou aqui, falhou
        Write-Output "Falha ao desconectar sessão {session_id} usando ambos rwinsta e logoff."
        exit 1
        """

        result = self.handler.execute_script(ps_script)
        
        output_msg = "\\n".join(result.get("output", []))
        
        if result.get("success") and "desconectada com sucesso" in output_msg:
             yield f"Sessão {session_id} desconectada com sucesso."
        else:
             yield f"Falha ao desconectar sessão {session_id}. Detalhes:\\n{output_msg}"

    def get_user_activity_events(self, start_time, end_time):
        logging.info(f"Executing 'get_user_activity_events' on {self.target_ip} for period {start_time} to {end_time}")
        """Busca eventos de atividade usando múltiplas fontes de dados com fallbacks robustos."""
        script = self._load_script("get_user_activity", {
            "__START_TIME__": start_time,
            "__END_TIME__": end_time
        })
        
        result = self.handler.execute_script(script)
        logging.debug(f"Raw output for get_user_activity_events: {result.get('output')}")
        full_json_str = "".join(result.get("output", []))
        if not full_json_str:
            logging.warning(f"No output received for get_user_activity_events on {self.target_ip}")
            yield {"error": "no_output"}
            return
        
        try:
            event_list = json.loads(full_json_str)
            if isinstance(event_list, dict) and "error" in event_list:
                logging.warning(f"Remote error reported for get_user_activity_events on {self.target_ip}: {event_list.get('error')}")
                yield event_list
            else:
                logging.info(f"Successfully retrieved {len(event_list) if isinstance(event_list, list) else 1} activity events from {self.target_ip}")
                yield [event_list] if isinstance(event_list, dict) else event_list
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for get_user_activity_events on {self.target_ip}: {e}. Raw output: {full_json_str}")
            yield {"error": "json_decode"}

    def get_remote_services(self):
        """Obtém lista de serviços do host remoto."""
        logging.info(f"Executing 'get_remote_services' on {self.target_ip}")
        script = self._load_script("get_services")
        result = self.handler.execute_script(script)
        
        output = result.get("output", [])
        if output:
            try:
                full_json = "".join(output)
                return json.loads(full_json)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error in get_remote_services: {e}")
                return []
        return []

    def manage_service(self, service_name, action, startup_type=None):
        """Gerencia um serviço (start, stop, restart, set-startup)."""
        logging.info(f"Executing 'manage_service' for '{service_name}' (Action: {action}) on {self.target_ip}")
        
        replacements = {
            "__SERVICE_NAME__": service_name,
            "__ACTION__": action
        }
        
        if startup_type:
             replacements["__STARTUP_TYPE__"] = startup_type
             script = self._load_script("manage_service_startup", replacements)
        else:
             script = self._load_script("manage_service", replacements)
             
        result = self.handler.execute_script(script)
        
        # Check for specific error output even if exit code was 0 (PowerShell sometimes swallows errors)
        output_str = "".join(result.get("output", [])).lower()
        if "acesso negado" in output_str or "access is denied" in output_str:
             yield {"status": "error", "message": "Acesso negado. Verifique se o usuário tem permissões administrativas."}
             return

        if result.get("success"):
             yield {"status": "success", "message": f"Ação '{action}' executada com sucesso em '{service_name}'."}
        else:
             yield {"status": "error", "message": f"Falha ao executar ação: {output_str}"}

    def get_single_service(self, service_name):
        """Obtém detalhes de um único serviço."""
        logging.info(f"Executing 'get_single_service' for '{service_name}' on {self.target_ip}")
        script = self._load_script("get_single_service", {
            "__SERVICE_NAME__": service_name
        })
        result = self.handler.execute_script(script)
        output = result.get("output", [])
        
        if output:
            try:
                full_json = "".join(output)
                return json.loads(full_json)
            except json.JSONDecodeError:
                pass
        return {"error": f"Serviço '{service_name}' não encontrado."}

    def execute_shutdown_command(self, action_flag, message, delay_seconds):
        """Executa comando de shutdown/restart remoto com múltiplos fallbacks."""
        action_type = "restart" if "-r" in action_flag else "shutdown"
        logging.info(f"Executing {action_type} command on {self.target_ip}")
        
        # 1. Tentar shutdown.exe (Nativo, suporta mensagens)
        cmd_native = f"shutdown {action_flag}"
        if "-l" not in action_flag:
            cmd_native += f" -t {delay_seconds}"
        if message and "-l" not in action_flag:
            safe_message = message.replace('"', "'")
            cmd_native += f' -c "{safe_message}"'
            
        logging.debug(f"Attempt 1: Native shutdown command: {cmd_native}")
        result = self.handler.execute_script(cmd_native)
        
        if result.get("success") and not any(err in "".join(result.get("output", [])).lower() for err in ["acesso negado", "access is denied", "falha", "failed"]):
            yield f"Comando enviado com sucesso (Nativo): {cmd_native}"
            return

        logging.warning(f"Native shutdown failed, trying PowerShell fallback. Output: {result.get('output')}")
        yield "Método nativo falhou, tentando PowerShell (Stop/Restart-Computer)..."

        # 2. Tentar PowerShell Stop-Computer / Restart-Computer (Mais robusto via WinRM, sem mensagem)
        ps_cmd = "Restart-Computer -Force" if action_type == "restart" else "Stop-Computer -Force"
        logging.debug(f"Attempt 2: PowerShell command: {ps_cmd}")
        
        result_ps = self.handler.execute_script(ps_cmd)
        if result_ps.get("success"):
            yield f"Comando enviado com sucesso (PowerShell): {ps_cmd}"
            return

        logging.warning(f"PowerShell fallback failed, trying WMI. Output: {result_ps.get('output')}")
        yield "Método PowerShell falhou, tentando WMI..."

        # 3. Tentar WMI (Win32_OperatingSystem)
        # Flags: 1 (Shutdown), 2 (Reboot), 6 (Force Reboot), 5 (Force Shutdown)
        wmi_flags = "6" if action_type == "restart" else "5"
        wmi_cmd = f"Get-WmiObject Win32_OperatingSystem | Invoke-WmiMethod -Name Win32Shutdown -ArgumentList {wmi_flags}"
        
        logging.debug(f"Attempt 3: WMI command: {wmi_cmd}")
        result_wmi = self.handler.execute_script(wmi_cmd)
        
        if result_wmi.get("success"):
            yield f"Comando enviado com sucesso (WMI): {wmi_cmd}"
            return

        yield {"status": "error", "message": "Falha em todos os métodos de desligamento (Nativo, PowerShell, WMI)."}

    def cancel_shutdown_command(self):
        """Cancela um agendamento de shutdown/restart."""
        logging.info(f"Executing 'cancel_shutdown_command' on {self.target_ip}")
        
        cmd = "shutdown -a"
        result = self.handler.execute_script(cmd)
        
        if result.get("success") and not any(err in "".join(result.get("output", [])).lower() for err in ["falha", "failed", "não há desligamento", "unable to abort"]):
            yield "Agendamento cancelado com sucesso."
            return

        # Fallback check: if output says "Unable to abort the system shutdown because no shutdown was in progress", it's technically a success (nothing to cancel)
        output_str = "".join(result.get("output", [])).lower()
        if "no shutdown was in progress" in output_str or "não há desligamento" in output_str:
             yield "Nenhum agendamento encontrado para cancelar."
             return

        yield {"status": "error", "message": f"Falha ao cancelar agendamento: {output_str}"}

    def send_message(self, message):
        """Envia uma mensagem para o usuário logado usando msg.exe."""
        logging.info(f"Executing 'send_message' on {self.target_ip}")
        
        check_cmd = "Get-Command msg.exe -ErrorAction SilentlyContinue"
        check_result = self.handler.execute_script(check_cmd)
        
        if not check_result.get("output"):
            logging.warning(f"msg.exe not found on {self.target_ip}")
            yield {"status": "error", "message": "O comando 'msg' não está disponível neste host (comum em versões Home)."}
            return

        safe_message = message.replace('"', "'")
        cmd = f'msg * "{safe_message}"'
        
        logging.debug(f"Message command: {cmd}")
        
        result = self.handler.execute_script(cmd)
        output = result.get("output", [])
        
        if result.get("success") and not any("erro" in line.lower() or "error" in line.lower() for line in output):
            yield f"Mensagem enviada com sucesso."
        else:
            error_msg = "".join(output)
            yield {"status": "error", "message": f"Falha ao enviar mensagem: {error_msg}"}

    def get_system_info_raw(self):
        """Obtém informações básicas do sistema."""
        logging.info(f"Executing 'get_system_info_raw' on {self.target_ip}")
        script = self._load_script("get_system_info", {
            "__TARGET_IP__": self.target_ip
        })
        result = self.handler.execute_script(script)
        
        output = result.get("output", [])
        if output:
            try:
                full_json = "".join(output)
                return json.loads(full_json)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error in get_system_info_raw: {e}")
                return {"error": "Falha ao decodificar JSON de resposta."}
        return {"error": "Sem resposta do host remoto."}

    def get_remote_event_logs(self, log_name, level, count):
        """Obtém logs de eventos do Windows."""
        logging.info(f"Executing 'get_remote_event_logs' on {self.target_ip}")
        
        # Map level string to ID for Get-WinEvent
        # Critical=1, Error=2, Warning=3, Information=4, Verbose=5
        level_map = {
            "Critical": 1,
            "Error": 2,
            "Warning": 3,
            "Information": 4,
            "Verbose": 5
        }
        
        level_id = level_map.get(level, 2) # Default to Error (2)
        
        script = self._load_script("get_event_logs", {
            "__LOG_NAME__": log_name,
            "__LEVEL_ID__": level_id,
            "__COUNT__": count
        })
        
        result = self.handler.execute_script(script)
        output = result.get("output", [])
        
        if output:
            full_json = "".join(output)
            
            if "LOG_NOT_FOUND" in full_json:
                 yield {"error": f"Log '{log_name}' não encontrado."}
                 return
            if "NO_LEVEL_MATCH" in full_json:
                 return 

            try:
                logs = json.loads(full_json)
                if isinstance(logs, list):
                    for log in logs:
                        yield log
                elif isinstance(logs, dict):
                    yield logs
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error in get_remote_event_logs: {e}")
                yield {"error": "Falha ao decodificar logs."}