# src/ferramentasderede/ui/components/tool_controllers/base_controller.py
# Contém a lógica central compartilhada por todos os controladores de ferramentas.

import logging
import threading
import queue
import os
import subprocess
import time
import psutil
import gc
from src.network.tools import NetworkTools
from src.system.tools import SystemTools
from ..loading_window import LoadingWindow
from ..credential_dialog import CredentialDialog
from ..custom_dialogs import PasswordInputDialog
from ..credential_service import SALT_FILE
from ..command_status_widget import CommandStatusWidget
from pypsrp.exceptions import WinRMError
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

Q_ITEM_TEXT = "TEXT"
# Q_ITEM_STATUS = "STATUS" # Removido, usaremos Q_ITEM_CALLBACK para status
Q_ITEM_CALLBACK = "CALLBACK"

class BaseToolController:
    # Configurações globais de controle de threads
    MAX_THREADS_WARNING = 200  # Limite de aviso (aumentado significativamente)
    MAX_THREADS_KILL = 500     # Limite de finalização forçada (apenas casos extremos)
    THREAD_CHECK_INTERVAL = 10 # Segundos entre verificações (menos frequente)
    
    # Variável de classe para controlar o monitor global
    _thread_monitor_active = False
    _thread_monitor_lock = threading.Lock()
    
    def __init__(self, app, host, hostname):
        self.app = app
        self.host = host
        self.hostname = hostname
        self.network_tools = NetworkTools()
        self.system_tools = SystemTools(self.app)
        
        self.ui_queue = queue.Queue()
        
        self.current_process = None
        self.is_running = False
        self.running_command = None
        self.on_state_change_callback = None
        self.output_textbox = None
        self.after_id = None
        self._loading_window = None
        self._loading_timeout_id = None
        self.command_status_widget = None
        
        # Iniciar monitor de threads global apenas uma vez
        self._ensure_thread_monitor_active()

    def set_state_change_callback(self, callback):
        self.on_state_change_callback = callback
        
    def setup_command_status_widget(self, parent_frame):
        """Configura o widget de status de comando para uma sub-aba."""
        try:
            if not self.command_status_widget:
                self.command_status_widget = CommandStatusWidget(parent_frame, self.app)
                logging.debug(f"CommandStatusWidget criado para {self.hostname}")
            return self.command_status_widget
        except Exception as e:
            logging.error(f"Erro ao configurar CommandStatusWidget: {e}")
            return None
    
    def _start_command_status(self, command_name):
        """Inicia indicação de status do comando na sub-aba."""
        try:
            if self.command_status_widget:
                self.command_status_widget.start_command(command_name)
                logging.debug(f"Status do comando '{command_name}' iniciado na sub-aba")
        except Exception as e:
            logging.error(f"Erro ao iniciar status do comando na sub-aba: {e}")
    
    def _finish_command_status(self, success=True, message=None):
        """Finaliza indicação de status do comando na sub-aba."""
        try:
            if self.command_status_widget:
                self.command_status_widget.finish_command(success, message)
                logging.debug(f"Status do comando finalizado na sub-aba com sucesso={success}")
        except Exception as e:
            logging.error(f"Erro ao finalizar status do comando na sub-aba: {e}")

    def _notify_state_change(self):
        if self.on_state_change_callback:
            try:
                logging.info(f"_notify_state_change: Chamando callback para comando '{self.running_command}', is_running={self.is_running}")
                status_data = {'running': self.is_running, 'command': self.running_command}
                self.app.after_idle(lambda: self.on_state_change_callback(status_data))
            except Exception as e:
                logging.error(f"Erro em _notify_state_change: {e}")
        else:
            logging.warning(f"_notify_state_change chamado mas sem callback definido para comando '{self.running_command}'")
            
    @classmethod
    def _ensure_thread_monitor_active(cls):
        """Garante que o monitor global de threads esteja ativo"""
        with cls._thread_monitor_lock:
            if not cls._thread_monitor_active:
                cls._thread_monitor_active = True
                monitor_thread = threading.Thread(target=cls._thread_monitor_worker, daemon=True)
                monitor_thread.start()
                logging.debug("Monitor global de threads iniciado")
                
    @classmethod
    def _thread_monitor_worker(cls):
        """Worker que monitora o número de threads e toma ações quando necessário"""
        
        while cls._thread_monitor_active:
            try:
                # Obter informações de threads
                current_process = psutil.Process()
                thread_count = current_process.num_threads()
                
                # Verificar apenas limite crítico - sem avisos repetitivos
                if thread_count >= cls.MAX_THREADS_KILL:
                    logging.error(f"THREAD MONITOR: LIMITE CRÍTICO ATINGIDO - {thread_count} threads! Simulando Ctrl+C - finalizando todos os comandos")
                    
                    # Enviar sinal de finalização para todos os controladores
                    cls._emergency_stop_all_commands()
                    
                    # Aguardar um pouco para as threads finalizarem
                    time.sleep(2)
                    
                    # Verificar se ainda está crítico
                    thread_count_after = psutil.Process().num_threads()
                    if thread_count_after >= cls.MAX_THREADS_KILL:
                        logging.error(f"THREAD MONITOR: Threads ainda altas após finalização de emergência: {thread_count_after}")
                        # Forçar finalização mais agressiva
                        cls._force_cleanup_threads()
                    else:
                        logging.info(f"THREAD MONITOR: Threads reduzidas para {thread_count_after} após finalização de emergência")
                        
            except Exception as e:
                logging.error(f"Erro no monitor de threads: {e}")
                
            # Aguardar próxima verificação
            time.sleep(cls.THREAD_CHECK_INTERVAL)
            
    @classmethod 
    def _emergency_stop_all_commands(cls):
        """Finaliza todos os comandos em execução em todos os controladores"""
        try:
            # Encontrar todas as instâncias ativas de BaseToolController
            controllers = []
            for obj in gc.get_objects():
                if isinstance(obj, BaseToolController) and obj.is_running:
                    controllers.append(obj)
                    
            logging.info(f"EMERGENCY STOP: Finalizando {len(controllers)} controladores ativos")
            
            for controller in controllers:
                try:
                    logging.info(f"EMERGENCY STOP: Finalizando comando '{controller.running_command}' do host '{controller.hostname}'")
                    controller._emergency_stop()
                except Exception as e:
                    logging.error(f"Erro ao finalizar controlador {controller.hostname}: {e}")
                    
        except Exception as e:
            logging.error(f"Erro na finalização de emergência: {e}")
            
    @classmethod
    def get_thread_statistics(cls):
        """Retorna estatísticas atuais de threads"""
        try:
            current_process = psutil.Process()
            thread_count = current_process.num_threads()
            active_threads = threading.active_count()
            
            # Contar controladores ativos
            active_controllers = 0
            running_commands = []
            
            try:
                for obj in gc.get_objects():
                    if isinstance(obj, BaseToolController) and obj.is_running:
                        active_controllers += 1
                        if obj.running_command:
                            running_commands.append(f"{obj.hostname}:{obj.running_command}")
            except:
                pass
                
            return {
                'process_threads': thread_count,
                'python_threads': active_threads,
                'active_controllers': active_controllers,
                'running_commands': running_commands,
                'warning_threshold': cls.MAX_THREADS_WARNING,
                'critical_threshold': cls.MAX_THREADS_KILL,
                'is_warning': thread_count >= cls.MAX_THREADS_WARNING,
                'is_critical': thread_count >= cls.MAX_THREADS_KILL
            }
        except Exception as e:
            logging.error(f"Erro ao obter estatísticas de threads: {e}")
            return None
            
    @classmethod
    def force_emergency_stop(cls):
        """Força finalização de emergência de todos os comandos (para uso manual)"""
        logging.warning("MANUAL EMERGENCY STOP: Iniciando finalização forçada de todos os comandos")
        cls._emergency_stop_all_commands()
        
    @classmethod
    def force_close_all_loading_windows(cls):
        """Força fechamento de todas as LoadingWindows travadas"""
        logging.warning("FORCE CLOSE: Iniciando fechamento forçado de todas as LoadingWindows")
        try:
            controllers = []
            for obj in gc.get_objects():
                if isinstance(obj, BaseToolController) and hasattr(obj, '_loading_window') and obj._loading_window:
                    controllers.append(obj)
                    
            logging.info(f"FORCE CLOSE: Encontradas {len(controllers)} LoadingWindows para fechar")
            
            for controller in controllers:
                try:
                    logging.info(f"FORCE CLOSE: Fechando LoadingWindow do host '{controller.hostname}'")
                    controller._close_loading_window("emergency")
                except Exception as e:
                    logging.error(f"FORCE CLOSE: Erro ao fechar LoadingWindow do host '{controller.hostname}': {e}")
                    
        except Exception as e:
            logging.error(f"FORCE CLOSE: Erro no fechamento forçado: {e}")
            
    @classmethod
    def _force_cleanup_threads(cls):
        """Limpeza forçada de threads quando métodos normais falharam"""
        try:
            # Forçar coleta de lixo
            logging.warning("FORCE CLEANUP: Executando coleta de lixo forçada")
            gc.collect()
            
            # Tentar finalizar threads órfãs
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.daemon:
                    try:
                        if hasattr(thread, '_stop'):
                            thread._stop()
                    except:
                        pass
                        
            logging.warning("FORCE CLEANUP: Limpeza forçada concluída")
            
        except Exception as e:
            logging.error(f"Erro na limpeza forçada: {e}")
            
    def _emergency_stop(self):
        """Finalização de emergência do controlador atual"""
        try:
            logging.warning(f"EMERGENCY STOP: Finalizando comando '{self.running_command}' para host '{self.hostname}'")
            
            # Marcar como não executando
            self.is_running = False
            old_command = self.running_command
            self.running_command = None
            
            # Finalizar processo atual
            if self.current_process:
                try:
                    self.current_process.terminate()
                    time.sleep(0.1)
                    if self.current_process.poll() is None:
                        self.current_process.kill()
                except:
                    pass
                    
            # Enviar mensagem de cancelamento
            try:
                self._put_in_queue(Q_ITEM_TEXT, f"\n--- SISTEMA: Operação '{old_command}' cancelada automaticamente (muitas threads ativas) ---\n")
            except:
                pass
                
            # Notificar mudança de estado
            try:
                self._notify_state_change()
            except:
                pass
                
            # Fechar loading window
            try:
                self._close_loading_window("emergency")
            except:
                pass
                
            logging.info(f"EMERGENCY STOP: Comando '{old_command}' finalizado com sucesso")
            
        except Exception as e:
            logging.error(f"Erro na finalização de emergência: {e}")
            
    def _put_in_queue(self, item_type, data):
        self.ui_queue.put((item_type, data))
        
    def _is_winrm_connection_error(self, exception_obj):
        if exception_obj is None: 
            return False
        
        # Se for string, verificar se contém padrões de erro WinRM
        if isinstance(exception_obj, str):
            error_str = exception_obj.lower()
        else:
            # Verificar se é um erro de conexão WinRM
            error_str = str(exception_obj).lower()
        
        # Erros de conexão WinRM
        winrm_errors = [
            'connection refused',
            'connection timeout',
            'max retries exceeded',
            'failed to establish a new connection',
            'winrm connection failed',
            'httpconnectionpool',
            'urllib3.connection',
            'newconnectionerror',
            'winerror 10061',  # Conexão recusada
            'winerror 10060',  # Timeout
            'winerror 10065',  # Host não encontrado
            'winerror 10051',  # Rede inacessível
            'winerror 10053',  # Conexão abortada
            'winerror 10054',  # Conexão resetada
            'failed to authenticate',  # Erro de autenticação
            'authentication failed',   # Falha de autenticação
        ]
        
        # Verificar se a mensagem de erro contém algum dos padrões
        for error_pattern in winrm_errors:
            if error_pattern in error_str:
                return True
        
        # Verificar tipos específicos de exceção
        from pypsrp.exceptions import WinRMError
        from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout
        
        if isinstance(exception_obj, (WinRMError, ConnectionError, ConnectTimeout, ReadTimeout)):
            return True
        
        return False

    def _get_winrm_error_message(self, exception_obj):
        """Retorna uma mensagem de erro amigável para problemas de conexão WinRM."""
        if not exception_obj:
            return self.app.translate("unknown_error")
        
        error_str = str(exception_obj).lower()
        
        # Verificar se é um erro de localhost (127.0.0.1)
        if '127.0.0.1' in error_str or 'localhost' in error_str:
            return (
                f"{self.app.translate('winrm_error_localhost_title')}.\n\n"
                f"{self.app.translate('winrm_error_localhost_auto_attempt')}\n\n"
                f"{self.app.translate('winrm_error_localhost_causes')}\n"
                f"{self.app.translate('winrm_error_localhost_cause_service')}\n"
                f"{self.app.translate('winrm_error_localhost_cause_firewall')}\n"
                f"{self.app.translate('winrm_error_localhost_cause_self_connect')}\n"
                f"{self.app.translate('winrm_error_localhost_cause_permissions')}\n\n"
                f"{self.app.translate('winrm_error_localhost_solutions')}\n"
                f"{self.app.translate('winrm_error_localhost_solution_quickconfig')}\n"
                f"{self.app.translate('winrm_error_localhost_solution_service')}\n"
                f"{self.app.translate('winrm_error_localhost_solution_firewall')}\n"
                f"{self.app.translate('winrm_error_localhost_solution_hostname')}"
            )
        
        # Verificar se é erro de autenticação
        if 'authentication' in error_str or 'authenticate' in error_str or 'unauthorized' in error_str:
            return (
                f"{self.app.translate('winrm_error_authentication_title')}.\n\n"
                f"{self.app.translate('winrm_error_authentication_desc')}\n\n"
                f"{self.app.translate('winrm_error_authentication_solutions')}\n"
                f"{self.app.translate('winrm_error_authentication_solution_credentials')}\n"
                f"{self.app.translate('winrm_error_authentication_solution_admin')}\n"
                f"{self.app.translate('winrm_error_authentication_solution_permission')}"
            )
        
        # Mapear códigos de erro específicos para mensagens amigáveis
        if 'winerror 10061' in error_str:
            return (
                f"{self.app.translate('winrm_error_connection_refused_title')}.\n\n"
                f"{self.app.translate('winrm_error_connection_refused_desc')}\n\n"
                f"{self.app.translate('winrm_error_connection_refused_causes')}\n"
                f"{self.app.translate('winrm_error_connection_refused_cause_service')}\n"
                f"{self.app.translate('winrm_error_connection_refused_cause_firewall')}\n"
                f"{self.app.translate('winrm_error_connection_refused_cause_config')}\n\n"
                f"{self.app.translate('winrm_error_connection_refused_solutions')}\n"
                f"{self.app.translate('winrm_error_connection_refused_solution_enable')}\n"
                f"{self.app.translate('winrm_error_connection_refused_solution_firewall')}\n"
                f"{self.app.translate('winrm_error_connection_refused_solution_ping')}"
            )
        
        elif 'winerror 10060' in error_str:
            return (
                f"{self.app.translate('winrm_error_timeout_title')}.\n\n"
                f"{self.app.translate('winrm_error_timeout_causes')}\n"
                f"{self.app.translate('winrm_error_timeout_cause_overload')}\n"
                f"{self.app.translate('winrm_error_timeout_cause_network')}\n"
                f"{self.app.translate('winrm_error_timeout_cause_firewall')}\n\n"
                f"{self.app.translate('winrm_error_timeout_solutions')}\n"
                f"{self.app.translate('winrm_error_timeout_solution_wait')}\n"
                f"{self.app.translate('winrm_error_timeout_solution_network')}\n"
                f"{self.app.translate('winrm_error_timeout_solution_ping')}"
            )
        
        elif 'winerror 10065' in error_str:
            return (
                f"{self.app.translate('winrm_error_host_not_found_title')}.\n\n"
                f"{self.app.translate('winrm_error_host_not_found_causes')}\n"
                f"{self.app.translate('winrm_error_host_not_found_cause_ip')}\n"
                f"{self.app.translate('winrm_error_host_not_found_cause_dns')}\n"
                f"{self.app.translate('winrm_error_host_not_found_cause_network')}\n\n"
                f"{self.app.translate('winrm_error_host_not_found_solutions')}\n"
                f"{self.app.translate('winrm_error_host_not_found_solution_ip')}\n"
                f"{self.app.translate('winrm_error_host_not_found_solution_ping')}\n"
                f"{self.app.translate('winrm_error_host_not_found_solution_status')}"
            )
        
        elif 'connection refused' in error_str or 'max retries exceeded' in error_str:
            return (
                f"{self.app.translate('winrm_error_connection_refused_title')}.\n\n"
                f"{self.app.translate('winrm_error_connection_refused_desc')}\n\n"
                f"{self.app.translate('winrm_error_connection_refused_solutions')}\n"
                f"{self.app.translate('winrm_error_connection_refused_solution_enable')}\n"
                f"{self.app.translate('winrm_error_connection_refused_solution_firewall')}\n"
                f"{self.app.translate('winrm_error_connection_refused_solution_ping')}"
            )
        
        else:
            # Mensagem genérica para outros erros
            return (
                f"{self.app.translate('winrm_error_generic_title')}: {str(exception_obj)}\n\n"
                f"{self.app.translate('winrm_error_generic_solutions')}\n"
                f"{self.app.translate('winrm_error_generic_solution_quickconfig')}\n"
                f"{self.app.translate('winrm_error_generic_solution_service')}\n"
                f"{self.app.translate('winrm_error_generic_solution_firewall')}\n"
                f"{self.app.translate('winrm_error_generic_solution_admin')}"
            )

    def _is_localhost(self, host_ip):
        """Verifica se o host é localhost."""
        return host_ip in ['127.0.0.1', 'localhost', '::1']

    def _check_winrm_status(self):
        """Verifica se o WinRM está habilitado e funcionando."""
        try:
            # Verificar se o serviço WinRM está rodando
            result = subprocess.run(['powershell', '-Command', 'Get-Service WinRM'], 
                                  capture_output=True, text=True, timeout=10)
            if 'Running' in result.stdout:
                return True, "WinRM está rodando"
            else:
                return False, "WinRM não está rodando"
        except Exception as e:
            return False, f"Erro ao verificar WinRM: {e}"

    def _fix_winrm_localhost(self):
        """Tenta corrigir automaticamente problemas de WinRM no localhost."""
        logging.info("Tentando corrigir automaticamente problemas de WinRM no localhost...")
        
        try:
            # 1. Habilitar WinRM
            logging.info("Executando winrm quickconfig...")
            result = subprocess.run(['powershell', '-Command', 'winrm quickconfig -force'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logging.warning(f"winrm quickconfig falhou: {result.stderr}")
                return False, "Falha ao habilitar WinRM. Execute como administrador."
            
            # 2. Configurar firewall
            logging.info("Configurando firewall para WinRM...")
            result = subprocess.run(['powershell', '-Command', 
                                   'netsh advfirewall firewall set rule group="Windows Remote Management" new enable=yes'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logging.warning(f"Configuração do firewall falhou: {result.stderr}")
                # Não retorna False aqui, pois o WinRM pode funcionar mesmo sem o firewall
            
            # 3. Verificar se funcionou
            is_running, status = self._check_winrm_status()
            if is_running:
                logging.info("WinRM configurado com sucesso!")
                return True, "WinRM configurado automaticamente com sucesso!"
            else:
                return False, f"WinRM ainda não está funcionando: {status}"
                
        except subprocess.TimeoutExpired:
            return False, "Timeout ao configurar WinRM. Execute manualmente como administrador."
        except Exception as e:
            logging.error(f"Erro ao configurar WinRM: {e}")
            return False, f"Erro ao configurar WinRM: {e}"

    def _should_auto_fix_winrm(self, host_ip):
        """Determina se deve tentar corrigir automaticamente o WinRM."""
        return self._is_localhost(host_ip) and os.name == 'nt'  # Apenas Windows

    def _get_credentials_with_vault(self):
        """
        Método centralizado para obter credenciais. A lógica de criação do cofre foi
        movida para o CredentialDialog para ser mais contextual.
        """
        app = self.app
        cred_service = app.cred_service
        
        # Lógica simplificada: Apenas tenta desbloquear se um cofre já existir.
        if not cred_service.is_unlocked():
            salt_file_path = os.path.join(app.base_dir, SALT_FILE)
            if os.path.exists(salt_file_path):
                title, prompt = app.translate("vault_unlock_title"), app.translate("vault_unlock_prompt")
                pwd_dialog = PasswordInputDialog(app, title, prompt)
                password = pwd_dialog.get_input()
                if password and not cred_service.unlock(password):
                    app.show_error(app.translate("vault_wrong_master_password"))
                # Se o usuário cancelar ou errar a senha, o fluxo continua,
                # mas o cofre permanecerá bloqueado (sem credenciais salvas visíveis).
    
        # Determina o domínio padrão para o diálogo de credenciais
        default_domain = ""
        if self.hostname and '.' in self.hostname:
            parts = self.hostname.split('.', 1)
            if len(parts) > 1 and any(c.isalpha() for c in parts[1]):
                default_domain = parts[1]
        
        # Mostra o diálogo de credenciais. Ele terá acesso ao cofre (se desbloqueado).
        cred_dialog = CredentialDialog(app, self.host.get('ip', self.hostname), default_domain, cred_service)
        username, password = cred_dialog.get_input()
        
        if username is None:
            return None, None
            
        return username, password

    def _start_command(self, command_name, target_func, args_tuple=(), needs_auth=False, loading_text="", timeout=None):
        """Versão simplificada e robusta para iniciar comandos"""
        import time
        
        # Validação básica
        if not command_name or not callable(target_func):
            logging.error(f"START: Parâmetros inválidos - comando='{command_name}', func={target_func}")
            return
        
        # Proteção contra cliques múltiplos - mais restritiva
        current_time = time.time()
        if hasattr(self, '_last_command_time') and current_time - self._last_command_time < 1.0:
            logging.debug(f"START: Comando '{command_name}' bloqueado - clique muito rápido")
            return
            
        # Verificar se já está executando - FORÇA PARADA SE NECESSÁRIO
        if self.is_running:
            logging.warning(f"START: Comando '{command_name}' solicitado mas '{self.running_command}' já executa - FORÇANDO PARADA")
            self.stop_command()  # Força parada do comando anterior
            time.sleep(0.3)  # Aguarda estabilizar
            
        self._last_command_time = current_time
        logging.info(f"START: Iniciando '{command_name}' para host '{self.hostname}'")

        # Obter credenciais se necessário
        username, password = (None, None)
        if needs_auth:
            username, password = self._get_credentials_with_vault()
            if not username:
                self.app.show_info(self.app.translate("user_cancelled_operation"))
                return
            args_tuple = (username, password) + args_tuple
        
        # DEFINIR ESTADO IMEDIATAMENTE
        self.is_running = True
        self.running_command = command_name
        self._command_start_time = current_time
        self.current_process = None  # Reset processo anterior
        
        # NOTIFICAR UI IMEDIATAMENTE
        try:
            if self.on_state_change_callback:
                self.on_state_change_callback({'running': True, 'command': command_name})
                
            if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                try:
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.delete("1.0", "end")
                    self.output_textbox.insert("end", f"--- Iniciando {command_name} ---\n")
                    self.output_textbox.configure(state="disabled")
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"START: Erro na notificação inicial: {e}")
        
        # INICIAR INDICADOR DE STATUS DA ABA
        try:
            self._start_status_indicator(command_name)
            logging.debug(f"START: Indicador de status iniciado para '{command_name}'")
        except Exception as e:
            logging.error(f"START: Erro ao iniciar indicador de status: {e}")
        
        # INICIAR STATUS DA SUB-ABA
        try:
            self._start_command_status(command_name)
        except Exception as e:
            logging.error(f"START: Erro ao iniciar status da sub-aba: {e}")
            
        # CRIAR LOADING WINDOW SE TEXTO FOI FORNECIDO - VERSÃO SIMPLES
        if loading_text and loading_text.strip():
            try:
                logging.info(f"START: Criando LoadingWindow para '{command_name}' com texto: '{loading_text}'")
                self._loading_window = LoadingWindow(
                    self.app, 
                    loading_text, 
                    on_cancel=lambda: self.stop_command()
                )
                logging.debug(f"START: LoadingWindow criada para '{command_name}'")
            except Exception as e:
                logging.error(f"START: Erro ao criar LoadingWindow para '{command_name}': {e}")
                self._loading_window = None

        def thread_wrapper(target, args):
            """Thread wrapper simplificado e robusto"""
            logging.info(f"THREAD: Executando '{command_name}' com args: {args}")
            
            try:
                # Executar o comando
                target(*args)
                logging.info(f"THREAD: '{command_name}' executado com sucesso")
                
            except Exception as e:
                logging.error(f"THREAD: Erro em '{command_name}': {e}")
                
                # Mostrar erro no output se possível
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", f"\nErro: {str(e)}\n")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass
                
                # Finalizar indicador de status com erro
                try:
                    logging.debug(f"THREAD: Finalizando indicador de status com erro para '{command_name}'")
                    self.app.after_idle(lambda: self._finish_status_indicator(False))
                except Exception as status_error:
                    logging.error(f"THREAD: Erro ao finalizar indicador de status com erro: {status_error}")
                
                # Finalizar status da sub-aba com erro
                try:
                    logging.debug(f"THREAD: Finalizando status da sub-aba com erro para '{command_name}'")
                    self.app.after_idle(lambda: self._finish_command_status(False))
                except Exception as substatus_error:
                    logging.error(f"THREAD: Erro ao finalizar status da sub-aba com erro: {substatus_error}")
                    
            finally:
                # FINALIZAR SEMPRE - SEM FILAS COMPLEXAS
                logging.info(f"THREAD: Finalizando '{command_name}'")
                
                try:
                    # Limpar estado diretamente
                    self.is_running = False
                    self.running_command = None
                    self.current_process = None
                    
                    # Notificar UI diretamente
                    if self.on_state_change_callback:
                        try:
                            self.app.after_idle(lambda: self.on_state_change_callback({'running': False, 'command': None}))
                        except:
                            pass
                    
                    # Fechar LoadingWindow - SOLUÇÃO RADICAL
                    try:
                        if hasattr(self, '_loading_window') and self._loading_window:
                            logging.info(f"THREAD: Sinalizando fechamento da LoadingWindow para '{command_name}'")
                            # Marcar para fechamento imediato
                            if hasattr(self._loading_window, '_should_close'):
                                self._loading_window._should_close = True
                            self._loading_window = None
                            logging.info(f"THREAD: LoadingWindow sinalizada para fechamento")
                                
                    except Exception as loading_error:
                        logging.error(f"THREAD: Erro ao sinalizar fechamento da LoadingWindow: {loading_error}")
                        self._loading_window = None
                    
                    # Finalizar indicador de status da aba
                    try:
                        logging.debug(f"THREAD: Finalizando indicador de status para '{command_name}'")
                        self.app.after_idle(lambda: self._finish_status_indicator(True))
                    except Exception as status_error:
                        logging.error(f"THREAD: Erro ao finalizar indicador de status: {status_error}")
                    
                    # Finalizar status da sub-aba com sucesso
                    try:
                        logging.debug(f"THREAD: Finalizando status da sub-aba com sucesso para '{command_name}'")
                        self.app.after_idle(lambda: self._finish_command_status(True))
                    except Exception as substatus_error:
                        logging.error(f"THREAD: Erro ao finalizar status da sub-aba com sucesso: {substatus_error}")
                            
                    # Adicionar mensagem de finalização
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        try:
                            self.output_textbox.configure(state="normal")
                            self.output_textbox.insert("end", f"\n--- Comando '{command_name}' finalizado ---\n")
                            self.output_textbox.see("end")
                            self.output_textbox.configure(state="disabled")
                        except:
                            pass
                            
                except Exception as cleanup_error:
                    logging.error(f"THREAD: Erro na limpeza final: {cleanup_error}")

        # INICIAR THREAD SIMPLIFICADA
        try:
            logging.info(f"START: Criando thread para '{command_name}'")
            thread = threading.Thread(
                target=thread_wrapper, 
                args=(target_func, args_tuple), 
                daemon=True,
                name=f"Tool-{command_name}"
            )
            thread.start()
            logging.info(f"START: Thread '{command_name}' iniciada com sucesso")
            
            # ===== PROTEÇÃO ANTI-IA: CORREÇÃO CRÍTICA DO PROCESS_QUEUE =====
            # AVISO: Esta seção corrige bug crítico onde callbacks da UI não eram processados.
            # MODIFICAÇÃO PROIBIDA sem confirmação explícita do desenvolvedor humano.
            # Esta correção é ESSENCIAL para funcionamento de todas as funcionalidades da UI.
            # =================================================================

            # INICIAR PROCESSAMENTO DA QUEUE SE NÃO ESTIVER RODANDO
            if not hasattr(self, 'after_id') or self.after_id is None:
                try:
                    logging.info(f"START: Iniciando process_queue para '{command_name}'")
                    self.after_id = self.app.after(50, self.process_queue)
                except Exception as queue_error:
                    logging.error(f"START: Erro ao iniciar process_queue: {queue_error}")

        except Exception as e:
            logging.error(f"START: Erro ao iniciar thread '{command_name}': {e}")

            # Reset estado em caso de erro
            self.is_running = False
            self.running_command = None
            self.current_process = None

            # Notificar UI do erro
            if self.on_state_change_callback:
                try:
                    self.on_state_change_callback({'running': False, 'command': None})
                except:
                    pass
    
    def _execute_safe_callback(self, data):
        callback_func = data[0]
        try:
            logging.info(f"Executando callback: {callback_func}")
            if isinstance(data, (list, tuple)) and len(data) >= 3:
                callback_func(*data[1], **data[2])
            else:
                logging.error(f"Estrutura de dados inválida para callback: {type(data)} - {data}")
                return
            logging.info(f"Callback executado com sucesso: {callback_func}")
        except Exception as e:
            logging.error(f"Erro ao executar callback: {e}")
            import traceback
            logging.error(f"Traceback do callback: {traceback.format_exc()}")

    def process_queue(self):
        item_processed = False
        try:
            item_type, data = self.ui_queue.get_nowait()
            item_processed = True
            logging.debug(f"Processando item da fila: {item_type} = {data}")
            if item_type == Q_ITEM_TEXT:
                self.add_output_line(data)
            elif item_type == Q_ITEM_CALLBACK:
                try:
                    logging.info(f"Q_ITEM_CALLBACK recebido - tipo: {type(data)}, conteúdo: {data}")
                    if not isinstance(data, (list, tuple)) or len(data) < 1:
                        logging.error(f"Estrutura de dados inválida para Q_ITEM_CALLBACK: {type(data)} - {data}")
                    else:
                        callback_func = data[0]
                        logging.info(f"Agendando callback: {callback_func}")
                        logging.info(f"Callback data structure: {data}")
                        if hasattr(callback_func, '__self__') and hasattr(callback_func.__self__, 'winfo_exists'):
                            widget = callback_func.__self__
                            if not widget.winfo_exists():
                                logging.warning(f"Widget não existe mais, ignorando callback: {callback_func}")
                            else:
                                logging.info("Widget callback - scheduling with after_idle")
                                self.app.after_idle(lambda: self._execute_safe_callback(data))
                        else:
                            logging.info("Non-widget callback - scheduling with after_idle")
                            self.app.after_idle(lambda: self._execute_safe_callback(data))
                        logging.info("Callback agendado com sucesso")
                except Exception as e:
                    logging.error(f"Erro ao agendar callback: {e}")
                    import traceback
                    logging.error(f"Traceback do agendamento: {traceback.format_exc()}")
        except queue.Empty:
            pass # No items in queue, just continue to finally block
        finally:
            # Continuar processando enquanto houver comandos ativos ou itens pendentes
            try:
                should_continue = (self.is_running or
                                   getattr(self, 'is_shell_connected', False) or
                                   not self.ui_queue.empty()) and not getattr(self.app, '_is_closing', False)
                
                # Adicionar timeout para evitar loop infinito
                if hasattr(self, '_process_queue_count'):
                    self._process_queue_count += 1
                else:
                    self._process_queue_count = 1
                
                # Se processou muitas vezes sem mudança, parar
                if self._process_queue_count > 1000:
                    logging.warning("process_queue executado muitas vezes, parando para evitar loop infinito")
                    self.after_id = None
                    return
                
                if should_continue: # Sempre reschedule if an item was just processed
                    self.after_id = self.app.after(50, self.process_queue)
                else:
                    self.after_id = None
                    self._process_queue_count = 0  # Reset contador quando para
            except Exception as e:
                logging.error(f"Erro ao agendar próximo process_queue: {e}")
                self.after_id = None
        
    def stop_command(self):
        """Versão simplificada e robusta para parar comandos"""
        import time
        
        # Proteção contra múltiplas chamadas - mais restritiva
        current_time = time.time()
        if hasattr(self, '_last_stop_time') and current_time - self._last_stop_time < 0.5:
            logging.debug(f"stop_command: chamada muito recente ignorada")
            return
            
        self._last_stop_time = current_time
        old_command = self.running_command
        
        logging.info(f"STOP: Parando comando '{old_command}' (is_running={self.is_running})")
        
        # 1. FORÇAR LIMPEZA IMEDIATA DE ESTADO
        self.is_running = False
        self.running_command = None
        self._process_queue_count = 0
        
        # 2. TERMINAR PROCESSO COM FORÇA
        if self.current_process:
            try:
                # Tentar terminate primeiro
                self.current_process.terminate()
                time.sleep(0.1)  # Dar tempo para finalizar
                
                # Se ainda está rodando, forçar kill
                if self.current_process.poll() is None:
                    self.current_process.kill()
                    time.sleep(0.1)
                    
                logging.debug(f"STOP: Processo finalizado")
            except Exception as e:
                logging.error(f"STOP: Erro ao finalizar processo: {e}")
            finally:
                self.current_process = None
        
        # 3. LIMPEZA AGRESSIVA DE RECURSOS
        try:
            # Limpar fila
            while not self.ui_queue.empty():
                try:
                    self.ui_queue.get_nowait()
                except:
                    break
                    
            # Cancelar after_id pendente
            if self.after_id:
                try:
                    self.app.after_cancel(self.after_id)
                except:
                    pass
                finally:
                    self.after_id = None
                    
            # Fechar loading window usando sistema de sinalização
            if hasattr(self, '_loading_window') and self._loading_window:
                try:
                    logging.info(f"STOP: Sinalizando fechamento da LoadingWindow")
                    self._loading_window._should_close = True
                    self._loading_window = None
                    logging.info(f"STOP: LoadingWindow sinalizada para fechamento")
                except Exception as e:
                    logging.error(f"STOP: Erro ao sinalizar fechamento: {e}")
                    self._loading_window = None
                    
        except Exception as e:
            logging.error(f"STOP: Erro na limpeza: {e}")
        
        # 4. NOTIFICAR UI DIRETAMENTE - SEM FILAS
        try:
            if self.on_state_change_callback:
                self.on_state_change_callback({'running': False, 'command': None})
                
            # Adicionar mensagem diretamente no output
            if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                try:
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\n--- Comando '{old_command}' cancelado ---\n")
                    self.output_textbox.see("end")
                    self.output_textbox.configure(state="disabled")
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"STOP: Erro na notificação: {e}")
        
        # 5. FINALIZAR INDICADOR DE STATUS COM CANCELAMENTO
        try:
            logging.debug(f"STOP: Finalizando indicador de status com cancelamento para '{old_command}'")
            self._finish_status_indicator(False)  # False porque foi cancelado
        except Exception as e:
            logging.error(f"STOP: Erro ao finalizar indicador de status: {e}")
        
        # 6. FINALIZAR STATUS DA SUB-ABA COM CANCELAMENTO
        try:
            logging.debug(f"STOP: Finalizando status da sub-aba com cancelamento para '{old_command}'")
            self._finish_command_status(False)  # False porque foi cancelado
        except Exception as e:
            logging.error(f"STOP: Erro ao finalizar status da sub-aba: {e}")
        
        logging.info(f"STOP: Comando '{old_command}' parado - Estado limpo")
        
        # 5. AGUARDAR UM POUCO PARA ESTABILIZAR
        time.sleep(0.2)
        
    def _command_finished(self, running_state=False, command_name=None):
        # Esta função agora é a única responsável por atualizar o estado interno e notificar a UI.
        logging.info(f"_command_finished called with running_state={running_state}, running_command='{self.running_command}', is_running={self.is_running}, provided_command_name='{command_name}'")
        
        actual_command_name = command_name if command_name else self.running_command
        
        # Atualizar estado de forma atômica
        self.is_running = running_state
        if not running_state:
            old_command = self.running_command
            # Só limpar running_command se ainda for o mesmo comando ou se o comando for None
            if actual_command_name == old_command or (actual_command_name is None and old_command is not None):
                self.running_command = None
                # Reset contador de process_queue
                self._process_queue_count = 0
                
            # Finalizar indicador de status com sucesso
            if actual_command_name:
                logging.info(f"Comando '{actual_command_name}' finalizado para o host '{self.hostname}'.")
                self._finish_status_indicator(True)
            else:
                logging.debug(f"Tentativa de finalizar comando 'None' para o host '{self.hostname}' - ignorando a finalização do indicador")

            # Garantir fechamento do loading da execução atual, se existir
            try:
                logging.debug(f"Fechando loading window para comando '{actual_command_name}'")
                self._close_loading_window("immediate") # Chamar de forma imediata
            except Exception as e:
                logging.error(f"Erro ao fechar loading window em _command_finished: {e}")
        
        # Notificar a mudança de estado APÓS _command_finished atualizar o estado interno
        if self.on_state_change_callback:
            try:
                logging.debug(f"Chamando on_state_change_callback diretamente do _command_finished para comando '{self.running_command}'")
                self.app.after_idle(lambda: self.on_state_change_callback({'running': self.is_running, 'command': self.running_command}))
            except Exception as e:
                logging.error(f"Erro ao chamar on_state_change_callback diretamente do _command_finished: {e}")
            
    def _handle_command_status_update(self, status_data):
        """Processa atualizações de status de comandos através da fila de callbacks."""
        logging.info(f"_handle_command_status_update recebido: {status_data}")
        running_state = status_data.get("running", False)
        command_name = status_data.get("command", None)
        
        # Atualizar estado interno
        self._command_finished(running_state=running_state, command_name=command_name)
        
        # Também chamar o callback diretamente para notificar a UI imediatamente
        if self.on_state_change_callback and not running_state:
            try:
                logging.info(f"_handle_command_status_update: Chamando callback adicional para comando '{command_name}' finalizado")
                self.on_state_change_callback(status_data)
            except Exception as e:
                logging.error(f"Erro ao chamar callback adicional em _handle_command_status_update: {e}")

    def _close_loading_window(self, reason=None):
        """Fecha a LoadingWindow usando o sistema de sinalização"""
        try:
            if hasattr(self, '_loading_window') and self._loading_window:
                logging.info(f"Sinalizando fechamento da LoadingWindow (reason={reason})")
                # Usar o novo sistema de sinalização
                self._loading_window._should_close = True
                self._loading_window = None
                logging.info("LoadingWindow sinalizada para fechamento")
        except Exception as e:
            logging.error(f"Erro ao sinalizar fechamento da LoadingWindow: {e}")
            self._loading_window = None
            
    def _start_status_indicator(self, command_name):
        """Inicia o indicador de status na aba atual."""
        try:
            # Obter o nome da aba atual
            tab_name = self._get_current_tab_name()
            logging.debug(f"Tab atual: {tab_name}")
            if tab_name and hasattr(self.app, 'host_tab_view'):
                logging.debug(f"Iniciando status para tab '{tab_name}' e comando '{command_name}'")
                self.app.host_tab_view.start_command_status(tab_name, command_name)
            else:
                logging.debug(f"Não foi possível iniciar status: tab_name={tab_name}, has_host_tab_view={hasattr(self.app, 'host_tab_view')}")
        except Exception as e:
            logging.error(f"Erro ao iniciar indicador de status: {e}")
            
    def _finish_status_indicator(self, success=True):
        """Finaliza o indicador de status na aba atual."""
        try:
            # Obter o nome da aba atual
            tab_name = self._get_current_tab_name()
            logging.debug(f"Finalizando status para tab '{tab_name}' com sucesso={success}")
            if tab_name and hasattr(self.app, 'host_tab_view'):
                self.app.host_tab_view.finish_command_status(tab_name, success)
            else:
                logging.debug(f"Não foi possível finalizar status: tab_name={tab_name}, has_host_tab_view={hasattr(self.app, 'host_tab_view')}")
        except Exception as e:
            logging.error(f"Erro ao finalizar indicador de status: {e}")
            import traceback
            logging.error(f"Traceback completo: {traceback.format_exc()}")
            
    def _get_current_tab_name(self):
        """Obtém o nome da aba atual."""
        try:
            if hasattr(self.app, 'host_tab_view') and hasattr(self.app.host_tab_view, 'tab_manager'):
                tab_name = self.app.host_tab_view.tab_manager.get_current_tab_name()
                logging.debug(f"Nome da aba atual obtido: {tab_name}")
                return tab_name
            else:
                logging.debug(f"host_tab_view ou tab_manager não disponível")
        except Exception as e:
            logging.error(f"Erro ao obter nome da aba atual: {e}")
        return None

    def add_output_line(self, line):
        try:
            if self.output_textbox and hasattr(self.output_textbox, 'insert') and self.output_textbox.winfo_exists():
                self.output_textbox.configure(state="normal")
                
                # Suporte a substituição de linha de progresso: linhas que começam com \r
                if isinstance(line, str) and line.startswith("\r"):
                    # Obter última linha atual
                    last_start = self.output_textbox.index("end-1c linestart")
                    last_text = self.output_textbox.get(last_start, "end-1c")
                    
                    # Se a última linha é um progresso, substitui; senão apenas insere
                    if last_text.strip().startswith("Progresso:"):
                        self.output_textbox.delete(last_start, "end-1c")
                        self.output_textbox.insert("end", line[1:])
                    else:
                        self.output_textbox.insert("end", line[1:])
                else:
                    self.output_textbox.insert("end", line)
                
                self.output_textbox.see("end")
                self.output_textbox.configure(state="disabled")
                logging.debug(f"Linha adicionada ao output: {line[:50]}...")
            else:
                logging.debug(f"Output não disponível para adicionar linha: {line[:50]}...")
        except Exception as e:
            logging.error(f"Erro ao adicionar linha na saída: {e}")

    def clear_output(self):
        try:
            if self.output_textbox and hasattr(self.output_textbox, 'delete') and self.output_textbox.winfo_exists():
                self.output_textbox.configure(state="normal")
                self.output_textbox.delete("1.0", "end")
                self.output_textbox.configure(state="disabled")
                logging.debug("Output limpo com sucesso")
            else:
                logging.debug("Output não disponível para limpeza")
        except Exception as e:
            logging.error(f"Erro ao limpar output: {e}")