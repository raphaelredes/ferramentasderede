# app/system_tools.py
# Atua como uma fachada (Facade) para as classes de ferramentas de sistema mais complexas.

import os
import subprocess
import tempfile
from .core.local_commands import LocalCommands
from .core.remote_commands import RemoteCommands
from .core.winrm_handler import WinRMError, ConnectionError, ConnectTimeout, WinRMHandler

class SystemTools:
    def __init__(self, app):
        self.app = app # Armazena a referência da aplicação para acessar o tradutor

    def list_connected_users(self, target_ip, username, password):
        """Lista usuários conectados usando WinRM."""
        return self._stream_winrm_command(
            target_ip, username, password,
            lambda cmd: cmd.list_connected_users_winrm()
        )

    def disconnect_user(self, target_ip, username, password, session_id):
        """Desconecta um usuário usando WinRM."""
        return self._stream_winrm_command(
            target_ip, username, password,
            lambda cmd: cmd.disconnect_user_winrm(session_id)
        )

    def configure_remote_winrm_trusted_hosts(self, target_ip, username, password, local_ip_to_trust):
        cmd = LocalCommands(target_ip)
        return cmd.configure_remote_winrm_with_psexec(username, password, local_ip_to_trust)

    def enable_remote_winrm(self, target_ip, username, password):
        """Habilita WinRM no host remoto via PsExec (serviço e firewall)."""
        cmd = LocalCommands(target_ip)
        return cmd.enable_remote_winrm_with_psexec(username, password)

    def check_remote_winrm_status(self, target_ip, username, password):
        """Verifica o status do WinRM no host remoto."""
        return self._execute_winrm_command(
            target_ip, username, password,
            lambda cmd: cmd.check_winrm_status()
        )

    def launch_interactive_remote_shell(self, target_ip, full_username, password):
        """Inicia uma nova janela do PowerShell já conectada à máquina remota."""
        if os.name != 'nt':
            return False, self.app.translate("error_windows_only")

        # Traduzindo as strings que serão usadas no script
        t = self.app.translate
        remote_session_title = t("shell_remote_session_title", target=target_ip)
        warning_trustedhosts = t("shell_warning_trustedhosts", ip=target_ip)
        prompt_add_trustedhosts = t("shell_prompt_add_trustedhosts")
        info_adding_trustedhosts = t("shell_info_adding_trustedhosts", ip=target_ip)
        info_uac_prompt = t("shell_info_uac_prompt")
        info_uac_close = t("shell_info_uac_close")
        error_privileges = t("shell_error_privileges")
        info_run_as_admin = t("shell_info_run_as_admin")
        info_op_cancelled = t("shell_info_op_cancelled")
        error_conn_proceed = t("shell_error_conn_proceed")
        info_window_close = t("shell_info_window_close")
        info_connecting = t("shell_info_connecting", target=target_ip, user=full_username)
        info_wait = t("shell_info_wait")
        error_connection_failed = t("shell_error_connection_failed")
        error_check_credentials = t("shell_error_check_credentials")

        ps_script = f"""
        # Define a codificação da console para UTF-8 para suportar acentos
        chcp 65001 | Out-Null

        $host.UI.RawUI.WindowTitle = "{remote_session_title}"
        $targetIp = '{target_ip}'
        $username = '{full_username}'
        $password = '{password}'

        function Check-And-Set-TrustedHosts {{
            param($ip)
            $trustedHosts = Get-Item -Path WSMan:\\localhost\\Client\\TrustedHosts -ErrorAction SilentlyContinue
            
            if (-not $trustedHosts -or $trustedHosts.Value -notlike "*$ip*") {{
                Write-Host "{warning_trustedhosts}" -ForegroundColor Yellow
                $choice = Read-Host "{prompt_add_trustedhosts}"
                if ($choice -eq 'S' -or $choice -eq 's' -or $choice -eq 'Y' -or $choice -eq 'y') {{
                    Write-Host "{info_adding_trustedhosts}" -ForegroundColor Cyan
                    
                    $currentValue = if ($trustedHosts) {{ $trustedHosts.Value }} else {{ '' }}
                    $newValue = if ($currentValue -and $currentValue -ne '*') {{ "$currentValue,$ip" }} else {{ $ip }}
                    
                    $command = "Set-Item -Path WSMan:\\localhost\\Client\\TrustedHosts -Value '$newValue' -Force"
                    try {{
                        Start-Process powershell -Verb RunAs -ArgumentList "-NoExit", "-Command", $command
                        Write-Host "{info_uac_prompt}" -ForegroundColor Green
                        Write-Host "{info_uac_close}"
                        Start-Sleep -Seconds 30
                        return $false
                    }} catch {{
                        Write-Host "{error_privileges}" -ForegroundColor Red
                        Write-Host "{info_run_as_admin}"
                        Write-Host "Set-Item -Path WSMan:\\localhost\\Client\\TrustedHosts -Value '<seu-ip-local>,{target_ip}' -Force"
                        return $false
                    }}
                }} else {{
                    Write-Host "{info_op_cancelled}" -ForegroundColor Yellow
                    return $false
                }}
            }}
            return $true
        }}

        if (-not (Check-And-Set-TrustedHosts -ip $targetIp)) {{
            Write-Host "{error_conn_proceed}" -ForegroundColor Red
            Write-Host "{info_window_close}"
            Start-Sleep -Seconds 20
            Exit
        }}

        try {{
            $securePassword = ConvertTo-SecureString -String $password -AsPlainText -Force
            $credential = New-Object System.Management.Automation.PSCredential($username, $securePassword)
            Write-Host "{info_connecting}" -ForegroundColor Green
            Write-Host "{info_wait}"
            Enter-PSSession -ComputerName $targetIp -Credential $credential
        }} catch {{
            Write-Host "--- {error_connection_failed} ---" -ForegroundColor Red
            Write-Host $_.Exception.Message
            Write-Host "{error_check_credentials}"
            Write-Host "{info_window_close}"
            Start-Sleep -Seconds 20
        }}
        """

        try:
            # Salva o arquivo temporário com encoding 'utf-8-sig' para suportar acentos
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ps1', encoding='utf-8-sig') as temp_script:
                temp_script.write(ps_script)
                temp_script_path = temp_script.name
            
            full_command = [
                'powershell.exe',
                '-NoExit',
                '-ExecutionPolicy', 'Bypass',
                '-File', temp_script_path
            ]
            
            subprocess.Popen(full_command, creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            return True, f"Janela do PowerShell para {target_ip} iniciada."

        except Exception as e:
            return False, f"Falha ao iniciar o shell interativo: {e}"

    def _execute_winrm_command(self, target_ip, username, password, command_func):
        """Executa um comando WinRM de forma mais direta para evitar o erro unhashable type."""
        cmd = None
        try:
            cmd = RemoteCommands(target_ip, username, password)
            cmd.handler = WinRMHandler(cmd.target_ip, cmd.username, cmd.password)
            connection_result = cmd.handler.connect()
            
            if "error" in connection_result:
                raise connection_result.get("exception_obj", ConnectionError(connection_result['error']))

            result = command_func(cmd)
            return result

        except (WinRMError, ConnectionError, ConnectTimeout) as e:
            return {"error": str(e), "exception_obj": e}
        except Exception as e:
            import logging
            logging.error(f"Exceção inesperada em _execute_winrm_command: {type(e).__name__} - {e}")
            return {"error": f"Erro inesperado: {e}", "exception_obj": e}
        finally:
            if cmd and cmd.handler:
                cmd.handler.close()

    def _stream_winrm_command(self, target_ip, username, password, command_func):
        try:
            with RemoteCommands(target_ip, username, password) as cmd:
                yield from command_func(cmd)
        except (WinRMError, ConnectionError, ConnectTimeout) as e:
            yield {"status": "error", "message": f"Exceção na conexão WinRM: {e}"}
        except Exception as e:
            yield {"status": "error", "message": f"Erro inesperado: {e}"}

    def execute_remote_network_scan(self, target_ip, username, password):
        return self._stream_winrm_command(
            target_ip, username, password,
            lambda cmd: cmd.scan_network()
        )

    def get_remote_teamviewer_id(self, target_ip, username, password):
        return self._stream_winrm_command(
            target_ip, username, password,
            lambda cmd: cmd.get_teamviewer_id()
        )

    def get_remote_system_info_raw(self, target_ip, username, password):
        return self._execute_winrm_command(target_ip, username, password, 
            lambda cmd: cmd.get_system_info_raw())

    def get_remote_services(self, target_ip, username, password):
        return self._execute_winrm_command(target_ip, username, password, 
            lambda cmd: cmd.get_remote_services())
            
    def get_single_remote_service(self, target_ip, username, password, service_name):
        return self._execute_winrm_command(target_ip, username, password, 
            lambda cmd: cmd.get_single_service(service_name))

    def manage_remote_service(self, target_ip, username, password, service_name, action):
        return self._stream_winrm_command(target_ip, username, password, 
            lambda cmd: cmd.manage_remote_service(service_name, action))

    def execute_shutdown_command(self, target_ip, username, password, action_flag, message, delay_seconds):
        return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.execute_shutdown_command(action_flag, message, delay_seconds))

    def get_remote_event_logs(self, target_ip, username, password, log_name, level, count):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.get_remote_event_logs(log_name, level, count))

    def get_remote_shell_session(self, target_ip, username, password):
        return RemoteCommands(target_ip, username, password)
    
    def get_remote_activity_events(self, target_ip, username, password, start_time, end_time):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.get_user_activity_events(start_time, end_time))