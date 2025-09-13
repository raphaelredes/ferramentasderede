# app/ui_components/tool_controllers/remote_actions_controller.py

import os
import subprocess
from .base_controller import BaseToolController, Q_ITEM_CALLBACK, Q_ITEM_TEXT

class RemoteActionsController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)

    def _initiate_rdp_worker(self, username, password):
        """Worker simplificado e robusto para iniciar RDP"""
        logging.info(f"RDP: Verificando sessões ativas para {self.host['ip']}")
        
        try:
            # Verificar usuários conectados
            users_iterator = self.system_tools.list_connected_users(self.host['ip'], username, password)
            log, users_data = next(users_iterator, (None, []))
            if users_data is None: 
                users_data = []

            _, final_users_data = next(users_iterator, (None, []))
            if final_users_data: 
                users_data = final_users_data

            active_sessions = [user for user in users_data if user.get('State', '').lower() == 'ativo']

            def launch_rdp():
                logging.info(f"RDP: Iniciando conexão para {self.host['ip']}")
                self.network_tools.initiate_rdp(self.host['ip'])

            # Verificar se há sessões ativas
            if active_sessions:
                user_list = ", ".join([s['UserName'] for s in active_sessions])
                
                # Perguntar confirmação usando after_idle para não travar
                def ask_confirmation():
                    try:
                        if self.app.ask_yes_no(
                            self.app.translate("rdp_warning_title"),
                            self.app.translate("rdp_warning_message", users=user_list, host_name=self.host['name'])
                        ):
                            launch_rdp()
                    except Exception as e:
                        logging.error(f"RDP: Erro no dialog de confirmação: {e}")
                        
                # Executar dialog na thread principal
                self.app.after_idle(ask_confirmation)
            else:
                # Não há sessões ativas, iniciar RDP diretamente
                self.app.after_idle(launch_rdp)
                
        except Exception as e:
            logging.error(f"RDP: Erro para {self.host['ip']}: {e}")
            
            # Mostrar erro diretamente
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"Erro ao verificar sessões RDP: {str(e)}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            logging.info(f"RDP: Worker finalizado para {self.host['ip']}")

    def initiate_rdp(self):
        # Configurar timeout específico para RDP (20 segundos)
        self._start_command("check_rdp", self._initiate_rdp_worker, 
                           loading_text=self.app.translate("loading_checking_sessions"), 
                           needs_auth=True, timeout=20.0)

    def run_rdp(self):
        """Alias para initiate_rdp para padronizar nomenclatura"""
        self.initiate_rdp()

    def initiate_msra(self):
        self.network_tools.initiate_msra(self.host['ip'])

    def run_msra(self):
        """Inicia conexão MSRA"""
        self.initiate_msra()

    def run_wol(self):
        """Envia Wake-on-LAN packet"""
        logging.info(f"WOL: Enviando pacote Wake-on-LAN para {self.host.get('name', self.host.get('ip'))}")
        
        mac = self.host.get("mac")
        if not mac:
            error_msg = "Endereço MAC não encontrado para este host."
            logging.warning(f"WOL: {error_msg}")
            
            # Mostrar erro na UI se disponível
            try:
                if hasattr(self, 'output_textbox') and self.output_textbox and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"--- Wake-on-LAN ---\nERRO: {error_msg}\n\n")
                    self.output_textbox.see("end")
                    self.output_textbox.configure(state="disabled")
                else:
                    # Se não há textbox, mostrar mensagem direta
                    self.app.show_error(error_msg)
            except:
                self.app.show_error(error_msg)
            return
            
        try:
            # Enviar pacote WOL
            success, message = self.network_tools.send_wol_packet(mac)
            
            result_text = f"--- Wake-on-LAN ---\nMAC: {mac}\n{message}\n\n"
            
            # Mostrar resultado na UI
            try:
                if hasattr(self, 'output_textbox') and self.output_textbox and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", result_text)
                    self.output_textbox.see("end")
                    self.output_textbox.configure(state="disabled")
                else:
                    # Se não há textbox, mostrar notificação
                    if success:
                        self.app.show_toast_notification(f"WOL enviado para {self.host.get('name', self.host.get('ip'))}")
                    else:
                        self.app.show_error(f"Falha no WOL: {message}")
            except:
                # Fallback para notificação direta
                if success:
                    self.app.show_toast_notification(f"WOL enviado com sucesso")
                else:
                    self.app.show_error(f"Falha no WOL: {message}")
                    
            logging.info(f"WOL: {'Sucesso' if success else 'Falha'} - {message}")
            
        except Exception as e:
            error_msg = f"Erro ao enviar Wake-on-LAN: {str(e)}"
            logging.error(f"WOL: {error_msg}")
            
            # Mostrar erro
            try:
                if hasattr(self, 'output_textbox') and self.output_textbox and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"--- Wake-on-LAN ---\nERRO: {error_msg}\n\n")
                    self.output_textbox.configure(state="disabled")
                else:
                    self.app.show_error(error_msg)
            except:
                self.app.show_error(error_msg)

    def get_tv_id(self):
        """Alias para get_teamviewer_id para padronizar nomenclatura"""
        if hasattr(self, 'output_textbox') and hasattr(self, 'info_display'):
            self.get_teamviewer_id(self.output_textbox, self.info_display, None)

    def configure_winrm(self):
        """Alias para check_and_configure_winrm para padronizar nomenclatura"""
        if hasattr(self, 'output_textbox') and hasattr(self, 'configure_winrm_button'):
            self.check_and_configure_winrm(self.output_textbox, self.configure_winrm_button)

    def send_wol(self, output_widget):
        self.output_textbox = output_widget
        self.clear_output()
        mac = self.host.get("mac")
        if not mac:
            self.add_output_line(self.app.translate("wol_mac_missing") + "\n")
            return
        
        success, message = self.network_tools.send_wol_packet(mac)
        self.add_output_line(f"--- Wake-on-LAN ---\n{message}\n")

    def _get_tv_id_worker(self, username, password, info_display_widget, button_callback):
        """Worker simplificado e robusto para obter TeamViewer ID"""
        final_tv_id = None
        connection_failed = False
        
        logging.info(f"TEAMVIEWER: Obtendo ID do TeamViewer para {self.host['ip']}")
        
        try:
            # Usar o método direto do sistema
            for result in self.system_tools.get_remote_teamviewer_id(self.host['ip'], username, password):
                if isinstance(result, dict) and result.get("status") == "error":
                    connection_failed = True
                    error_msg = result.get("message", "Erro desconhecido")
                    # Mostrar erro diretamente
                    try:
                        if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                            self.output_textbox.configure(state="normal")
                            self.output_textbox.insert("end", error_msg + "\n")
                            self.output_textbox.configure(state="disabled")
                    except:
                        pass
                    break

                # Resultado normal (line, tv_id)
                line, tv_id = result
                
                if "FALHA NA CONEXÃO" in line:
                    connection_failed = True
                    
                # Mostrar output diretamente
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", line)
                        self.output_textbox.see("end")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass
                    
                if tv_id and tv_id != "N/A":
                    final_tv_id = tv_id
            
            # Mostrar dialog de erro WinRM se necessário
            if connection_failed:
                try:
                    self.app.show_winrm_error_dialog()
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"TEAMVIEWER: Erro para {self.host['ip']}: {e}")
            
            # Mostrar erro diretamente
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"Erro: {str(e)}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            # Atualização da UI diretamente
            logging.info(f"TEAMVIEWER: Finalizando - ID encontrado: {final_tv_id}, connection_failed: {connection_failed}")
            
            try:
                # Atualizar display do TeamViewer ID
                if info_display_widget and hasattr(info_display_widget, 'update_info'):
                    if final_tv_id:
                        info_display_widget.update_info(tv_id=str(final_tv_id))
                    elif not connection_failed:
                        info_display_widget.update_info(tv_id=self.app.translate("tv_id_not_found"))
                        
                # Chamar callback se disponível
                if button_callback and callable(button_callback):
                    button_callback()
                    
            except Exception as ui_error:
                logging.error(f"TEAMVIEWER: Erro na atualização da UI: {ui_error}")
                
            logging.info(f"TEAMVIEWER: Worker finalizado para {self.host['ip']}")

    def get_teamviewer_id(self, output_widget, info_display_widget, button_callback):
        self.output_textbox = output_widget
        info_display_widget.update_info(tv_id="...")
        self._start_command("get_tv_id", self._get_tv_id_worker, 
            args_tuple=(info_display_widget, button_callback), needs_auth=True, 
            loading_text=self.app.translate("loading_getting_tv_id"))
            
    def open_tv_and_copy_id(self, tv_id):
        self.app.clipboard_clear()
        self.app.clipboard_append(tv_id)
        self.app.show_toast_notification(self.app.translate("tv_id_copied_toast", tv_id=tv_id))

        if os.name == 'nt':
            try:
                tv_paths = [
                    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "TeamViewer", "TeamViewer.exe"),
                    os.path.join(os.environ.get("ProgramFiles", ""), "TeamViewer", "TeamViewer.exe")
                ]
                tv_exe_path = next((path for path in tv_paths if os.path.exists(path)), None)
                
                if tv_exe_path:
                    subprocess.Popen([tv_exe_path])
                else:
                    self.app.show_info(self.app.translate("tv_exe_not_found"))
            except Exception as e:
                self.app.show_error(self.app.translate("tv_open_failed").format(error=str(e)))

    def _list_users_worker(self, username, password, callback_update_combobox):
        users_data = []
        try:
            for result in self.system_tools.list_connected_users(self.host['ip'], username, password):
                if isinstance(result, dict) and "status" in result:
                    if result["status"] == "error":
                        error_msg = result.get("message", "Erro de conexão WinRM")
                        self._put_in_queue(Q_ITEM_TEXT, f"ERRO: {error_msg}\n")
                        
                        # Verificar se é erro de credenciais ou conectividade
                        if "authentication" in error_msg.lower() or "credential" in error_msg.lower():
                            self._put_in_queue(Q_ITEM_CALLBACK, (self._handle_auth_error, (), {}))
                        else:
                            self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
                        return
                    continue
                line, users = result
                if line:
                    self._put_in_queue(Q_ITEM_TEXT, line)
                if users is not None: 
                    users_data = users
            
            import logging
            logging.info(f"Enviando callback update_users_combobox com {len(users_data)} usuários")
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_combobox, (users_data,), {}))
        except Exception as e:
            logging.error(f"Erro no _list_users_worker: {e}")
            error_msg = f"Erro inesperado ao listar usuários: {str(e)}"
            self._put_in_queue(Q_ITEM_TEXT, f"{error_msg}\n")
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_combobox, ([],), {}))

    def _handle_auth_error(self):
        """Trata erros de autenticação de forma específica"""
        self.app.show_error(
            "Credenciais inválidas ou usuário sem permissões adequadas.\n"
            "Verifique se:\n"
            "• As credenciais estão corretas\n"
            "• O usuário tem privilégios administrativos\n"
            "• O serviço WinRM está configurado corretamente"
        )

    def list_users(self, output_widget, callback_update_combobox):
        self.output_textbox = output_widget
        self._start_command("list_users", self._list_users_worker,
            args_tuple=(callback_update_combobox,), needs_auth=True,
            loading_text=self.app.translate("loading_listing_users"))
    
    def _disconnect_user_worker(self, username, password, session_id, callback_update_combobox):
        users_data = []
        try:
            for result in self.system_tools.disconnect_user(self.host['ip'], username, password, session_id):
                if isinstance(result, dict) and result.get("status") == "error": # Corrigido de 'line' para 'result'
                     self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
                     return
                line, users = result
                self._put_in_queue(Q_ITEM_TEXT, line)
                if users is not None: users_data = users
            # Mover a chamada de atualização da combobox para aqui
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_combobox, (users_data,), {}))
        except Exception as e:
            logging.error(f"Erro no _disconnect_user_worker: {e}")
            # Colocar tratamento de erro aqui se necessário, mas a finalização é pelo thread_wrapper

    def disconnect_user(self, session_id, username_to_disconnect, output_widget, callback_update_combobox):
        if not self.app.ask_yes_no(
            self.app.translate("confirm_disconnect_title"), 
            self.app.translate("confirm_disconnect_message", username=username_to_disconnect, session_id=session_id, target_ip=self.host['name'])
        ):
            self.add_output_line(self.app.translate("user_disconnect_cancelled") + "\n")
            return

        self.output_textbox = output_widget
        self._start_command("disconnect_user", self._disconnect_user_worker,
            args_tuple=(session_id, callback_update_combobox), needs_auth=True,
            loading_text=self.app.translate("loading_disconnecting_user"))
            
    def _update_winrm_button_state(self, is_ok, button_widget):
        """Callback para atualizar o botão de acordo com o status do WinRM."""
        if not button_widget or not button_widget.winfo_exists():
            return
            
        if is_ok:
            button_widget.configure(
                text=self.app.translate("remote_actions_winrm_ok"),
                state="disabled",
                fg_color="#27AE60",
                # CORREÇÃO: Força o texto para preto em ambos os temas.
                text_color="black"
            )
        else:
            # Se a verificação falhar, o botão se transforma no botão de configurar.
            button_widget.configure(
                text=self.app.translate("remote_actions_configure_winrm"),
                state="normal",
                fg_color="#E67E22", # Laranja aviso
                hover_color="#D35400",
                command=lambda: self._execute_winrm_configuration(self.output_textbox)
            )

    def _check_winrm_worker(self, username, password, button_widget):
        """Worker que executa a verificação do WinRM em uma thread."""
        try:
            self.add_output_line("--- Verificando status do WinRM... ---\n")
            result = self.system_tools.check_remote_winrm_status(self.host['ip'], username, password)

            if isinstance(result, dict) and "error" in result:
                self.add_output_line(f"Erro de conexão: {result['error']}\n")
                self._put_in_queue(Q_ITEM_CALLBACK, (self._update_winrm_button_state, (False, button_widget), {}))
            elif result:
                self.add_output_line("Sucesso: O serviço WinRM está respondendo.\n")
                self._put_in_queue(Q_ITEM_CALLBACK, (self._update_winrm_button_state, (True, button_widget), {}))
            else:
                self.add_output_line("Falha: O serviço WinRM não está respondendo ou não está configurado corretamente.\n")
                self._put_in_queue(Q_ITEM_CALLBACK, (self._update_winrm_button_state, (False, button_widget), {}))
        finally:
            # Garantir finalização do loading (agora tratado pelo thread_wrapper)
            pass # Adicionado para evitar IndentationError

    def check_and_configure_winrm(self, output_widget, button_widget):
        """Orquestrador chamado pelo clique inicial do botão 'Verificar WinRM'."""
        self.output_textbox = output_widget
        self._start_command("check_winrm", self._check_winrm_worker,
            args_tuple=(button_widget,),
            needs_auth=True,
            loading_text=self.app.translate("loading_checking_winrm"))

    def _execute_winrm_configuration(self, output_widget):
        """Função que executa a configuração (ação original do botão)."""
        self.output_textbox = output_widget
        local_net_info = self.network_tools.get_local_network_info()
        if "error" in local_net_info:
            self.app.show_error(f"Não foi possível obter o IP local: {local_net_info['error']}")
            return
        local_ip = local_net_info['ip']
        self._start_command("configure_winrm", self._configure_winrm_worker, 
            args_tuple=(local_ip,), needs_auth=True, 
            loading_text=self.app.translate("loading_configuring_winrm"))
    
    def _configure_winrm_worker(self, username, password, local_ip):
        try:
            # 1) Habilitar WinRM (serviço e firewall) via PsExec
            ok, msg = self.system_tools.enable_remote_winrm(self.host['ip'], username, password)
            self._put_in_queue(Q_ITEM_TEXT, f"{msg}\n")
            # 2) Configurar TrustedHosts para confiar no IP local (para PSRemoting)
            for line, _ in self.system_tools.configure_remote_winrm_trusted_hosts(self.host['ip'], username, password, local_ip):
                self._put_in_queue(Q_ITEM_TEXT, line)
            # 3) Feedback final e finalizar comando
            if ok:
                self._put_in_queue(Q_ITEM_TEXT, "WinRM habilitado e configurado. Tente novamente a ação desejada.\n")
            else:
                self._put_in_queue(Q_ITEM_TEXT, "Não foi possível garantir a habilitação do WinRM. Verifique manualmente.\n")
        finally:
            # Garantir finalização do loading (agora tratado pelo thread_wrapper)
            pass # Adicionado para evitar IndentationError