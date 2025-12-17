# app/system_tools.py
# Atua como uma fachada (Facade) para as classes de ferramentas de sistema mais complexas.

import os
import subprocess
import tempfile
import logging
import json
from .core.local_commands import LocalCommands
from .core.remote_commands import RemoteCommands
from .core.winrm_handler import WinRMError, ConnectionError, ConnectTimeout, WinRMHandler
from .core.local_handler import LocalHandler

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

    def get_remote_event_logs(self, target_ip, username, password, log_name, level, count):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.get_remote_event_logs(log_name, level, count))

    def get_remote_shell_session(self, target_ip, username, password):
        return RemoteCommands(target_ip, username, password)
    
    def get_remote_activity_events(self, target_ip, username, password, start_time, end_time):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.get_user_activity_events(start_time, end_time))

    def send_message(self, target_ip, username, password, message):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.send_message(message))

    def cancel_shutdown_command(self, target_ip, username, password):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.cancel_shutdown_command())

    def manage_remote_service(self, target_ip, username, password, service_name, action, startup_type=None):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.manage_remote_service(service_name, action, startup_type))

    def manage_spooler(self, target_ip, username, password, action):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.manage_spooler(action))

    def execute_shutdown_command(self, target_ip, username, password, action_flag, message, delay_seconds):
         return self._stream_winrm_command(target_ip, username, password,
            lambda cmd: cmd.execute_shutdown_command(action_flag, message, delay_seconds))

    def _execute_winrm_command(self, target_ip, username, password, command_func):
        """Executa um comando WinRM de forma síncrona e segura."""
        cmd = None
        try:
            cmd = RemoteCommands(target_ip, username, password)
            
            # Check for localhost and use LocalHandler if applicable
            if target_ip in ["127.0.0.1", "localhost"]:
                logging.info(f"Using LocalHandler for target {target_ip}")
                cmd.handler = LocalHandler(cmd.target_ip, cmd.username, cmd.password)
            else:
                # Injeção manual do handler para controle explícito
                cmd.handler = WinRMHandler(cmd.target_ip, cmd.username, cmd.password)
            
            connection_result = cmd.handler.connect()
            if "error" in connection_result:
                return connection_result
                
            return command_func(cmd)
            
        except (WinRMError, ConnectionError, ConnectTimeout) as e:
            return {"error": f"Erro de conexão WinRM: {str(e)}"}
        except Exception as e:
            return {"error": f"Erro inesperado: {str(e)}"}
        finally:
            if cmd and cmd.handler:
                cmd.handler.close()

    def _stream_winrm_command(self, target_ip, username, password, command_func):
        """Executa um comando WinRM e faz streaming dos resultados (generator)."""
        cmd = None
        try:
            cmd = RemoteCommands(target_ip, username, password)
            
            if target_ip in ["127.0.0.1", "localhost"]:
                logging.info(f"Using LocalHandler for streaming target {target_ip}")
                cmd.handler = LocalHandler(cmd.target_ip, cmd.username, cmd.password)
            else:
                cmd.handler = WinRMHandler(cmd.target_ip, cmd.username, cmd.password)
            
            connection_result = cmd.handler.connect()
            if "error" in connection_result:
                yield {"status": "error", "message": connection_result["error"]}
                return

            # Executa a função que retorna um generator
            iterator = command_func(cmd)
            
            # Itera sobre o resultado e repassa
            for item in iterator:
                yield item
                
        except (WinRMError, ConnectionError, ConnectTimeout) as e:
            yield {"status": "error", "message": f"Erro de conexão WinRM: {str(e)}"}
        except Exception as e:
            yield {"status": "error", "message": f"Erro inesperado: {str(e)}"}
        finally:
            if cmd and cmd.handler:
                cmd.handler.close()