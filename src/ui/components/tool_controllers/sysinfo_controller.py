# app/ui_components/tool_controllers/sysinfo_controller.py
# Contém a lógica de negócios para a aba "Sistema".

from .base_controller import BaseToolController, Q_ITEM_CALLBACK, Q_ITEM_TEXT
from datetime import datetime, timedelta
import logging
from ..custom_input_dialog import CustomInputDialog

class SysInfoController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)
        logging.info(f"SysInfoController initialized for host: {hostname or host.get('ip')}")

    def get_system_info(self, callback_update_general, callback_update_disks):
        """
        Orquestra a busca de informações do sistema.
        """
        logging.info(f"Starting system info fetching for host: {self.hostname or self.host.get('ip')}")
        # Limpa e prepara a UI antes de iniciar o comando
        if callback_update_general and hasattr(self.app, 'after'):
             self.app.after(0, lambda: callback_update_general(None, show_loading=True))

        self._start_command("get_sysinfo", self._get_sysinfo_worker,
                            args_tuple=(callback_update_general, callback_update_disks),
                            needs_auth=True,
                            loading_text=self.app.translate("loading_getting_sysinfo"))

    def get_sysinfo(self, store_only=False):
        """Busca informações do sistema. Se store_only=True, apenas armazena os dados."""
        # Cria callbacks para atualizar a UI
        def callback_update_general(data, show_loading=False):
            if self.system_info_panel and self.system_info_panel.winfo_exists():
                self.system_info_panel.display_info(data)
        
        def callback_update_disks(disks_data):
            logging.debug(f"SYSINFO: Recebidos dados de disco: {disks_data}")
            if hasattr(self, 'system_info_panel') and self.system_info_panel and hasattr(self.system_info_panel, 'winfo_exists') and self.system_info_panel.winfo_exists():
                try:
                    self.system_info_panel._display_disk_info(disks_data if disks_data else [])
                    logging.debug("SYSINFO: Dados de disco atualizados na UI")
                except Exception as e:
                    logging.error(f"SYSINFO: Erro ao atualizar dados de disco na UI: {e}")
            else:
                logging.warning("SYSINFO: system_info_panel não disponível para atualização de disco")
        
        self.get_system_info(callback_update_general, callback_update_disks)

    def _get_sysinfo_worker(self, username, password, callback_update_general, callback_update_disks):
        """Worker simplificado e robusto para buscar informações do sistema"""
        logging.info(f"SYSINFO: Buscando informações do sistema para {self.host['ip']}")
        
        try:
            # Buscar dados do sistema
            raw_data = self.system_tools.get_remote_system_info_raw(self.host['ip'], username, password)
            logging.debug(f"SYSINFO: Dados brutos recebidos: {raw_data}")

            if "error" in raw_data:
                error_message = raw_data["error"]
                exception_obj = raw_data.get("exception_obj")
                
                logging.error(f"SYSINFO: Erro para {self.host['ip']}: {error_message}")
                
                # Determinar mensagem de erro apropriada
                if self._is_winrm_connection_error(exception_obj):
                    friendly_error = self._get_winrm_error_message(exception_obj)
                    final_error = friendly_error
                else:
                    final_error = error_message

                # Mostrar erro diretamente
                try:
                    self.app.show_error(final_error)
                except:
                    pass
                    
                # Atualizar painel de informações com erro
                try:
                    if callback_update_general and callable(callback_update_general):
                        self.app.after_idle(lambda: callback_update_general({"error": final_error}))
                except:
                    pass
                return

            # Processar dados brutos
            processed_data = self._process_raw_sysinfo(raw_data)
            logging.info(f"SYSINFO: Dados processados com sucesso para {self.host['ip']}")

            # Atualizar UI diretamente
            try:
                if callback_update_general and callable(callback_update_general):
                    self.app.after_idle(lambda: callback_update_general(processed_data))
                    
                if callback_update_disks and callable(callback_update_disks):
                    disks_data = raw_data.get("Disks", [])
                    self.app.after_idle(lambda: callback_update_disks(disks_data))
            except Exception as ui_error:
                logging.error(f"SYSINFO: Erro na atualização da UI: {ui_error}")

        except Exception as e:
            logging.error(f"SYSINFO: Exceção inesperada para {self.host['ip']}: {e}")
            
            # Atualizar UI com erro
            try:
                if callback_update_general and callable(callback_update_general):
                    self.app.after_idle(lambda: callback_update_general({"error": f"Erro inesperado: {str(e)}"}))
            except:
                pass
                
        finally:
            logging.info(f"SYSINFO: Worker finalizado para {self.host['ip']}")


    def _process_raw_sysinfo(self, raw_data):
        """
        Converte os dados brutos do PowerShell em um formato mais legível.
        """
        logging.debug("Starting raw system info processing.")
        processed = raw_data.copy()

        # Processar Uptime
        try:
            boot_time_str = raw_data.get("LastBootUpTime")
            if boot_time_str:
                # Tentar diferentes formatos de data
                boot_time = None
                
                # Formato 1: ISO com timezone (2025-08-23T09:53:13.5000000-03:00)
                try:
                    # Remover timezone para compatibilidade
                    if '-' in boot_time_str and ':' in boot_time_str.split('-')[-1]:
                        # Formato com timezone, remover parte do timezone
                        base_time = boot_time_str.split('-')[:-1]
                        timezone_part = boot_time_str.split('-')[-1]
                        if ':' in timezone_part:
                            # Remover timezone (ex: -03:00)
                            timezone_removed = '-'.join(base_time)
                            boot_time = datetime.fromisoformat(timezone_removed)
                        else:
                            boot_time = datetime.fromisoformat(boot_time_str)
                    else:
                        boot_time = datetime.fromisoformat(boot_time_str.rstrip("Z"))
                except ValueError:
                    # Formato 2: Tentar parse manual se necessário
                    try:
                        from dateutil import parser
                        boot_time = parser.parse(boot_time_str)
                    except ImportError:
                        # Fallback: usar apenas a data se disponível
                        if 'T' in boot_time_str:
                            date_part = boot_time_str.split('T')[0]
                            boot_time = datetime.fromisoformat(date_part)
                
                if boot_time:
                    uptime = datetime.now() - boot_time
                    days = uptime.days
                    hours, remainder = divmod(uptime.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    uptime_str = f"{days} {self.app.translate('time_days')}, {hours} {self.app.translate('time_hours')}, {minutes} {self.app.translate('time_minutes')}"
                    processed["Uptime"] = uptime_str
                else:
                    processed["Uptime"] = self.app.translate("not_available")
            else:
                processed["Uptime"] = self.app.translate("not_available")
                logging.warning("LastBootUpTime not found in raw data.")
        except Exception as e:
            processed["Uptime"] = self.app.translate("sysinfo_invalid_date")
            logging.error(f"Error processing Uptime date string '{boot_time_str}': {e}")

        # Processar Data de Instalação
        try:
            install_date_str = raw_data.get("OS_InstallDate")
            if install_date_str:
                # Tentar diferentes formatos de data
                install_date = None
                
                # Formato 1: ISO padrão
                try:
                    install_date = datetime.fromisoformat(install_date_str.rstrip("Z"))
                except ValueError:
                    # Formato 2: .NET Date format (/Date(1736211838000)/)
                    if install_date_str.startswith('/Date(') and install_date_str.endswith(')/'):
                        try:
                            timestamp_str = install_date_str[6:-2]  # Remove /Date( and )/
                            timestamp_ms = int(timestamp_str)
                            install_date = datetime.fromtimestamp(timestamp_ms / 1000)
                        except (ValueError, OSError):
                            pass
                    else:
                        # Formato 3: Tentar parse manual
                        try:
                            from dateutil import parser
                            install_date = parser.parse(install_date_str)
                        except ImportError:
                            pass
                
                if install_date:
                    processed["InstallDate"] = install_date.strftime("%d/%m/%Y %H:%M:%S")
                else:
                    processed["InstallDate"] = self.app.translate("not_available")
            else:
                processed["InstallDate"] = self.app.translate("not_available")
                logging.warning("OS_InstallDate not found in raw data.")
        except Exception as e:
            processed["InstallDate"] = self.app.translate("sysinfo_invalid_date")
            logging.error(f"Error processing OS_InstallDate string '{install_date_str}': {e}")

        logging.debug("Raw system info processing finished.")
        return processed

    def shutdown_host(self, output_widget, countdown_label):
        """Desliga o host remoto."""
        self._shutdown_restart_handler("/s", output_widget, countdown_label)

    def restart_host(self, output_widget, countdown_label):
        """Reinicia o host remoto."""
        self._shutdown_restart_handler("/r", output_widget, countdown_label)

    def cancel_shutdown(self, output_widget, countdown_label):
        """Cancela o agendamento de shutdown/restart."""
        self.output_textbox = output_widget
        self.countdown_label = countdown_label
        full_display_name = self._get_full_display_name()
        if not self.app.ask_yes_no(
            self.app.translate("schedule_cancel"),
            self.app.translate("Tem certeza que deseja cancelar o agendamento no host {full_display_name}?", full_display_name=full_display_name)
        ):
            return
        self._start_command("cancel_shutdown", self._cancel_shutdown_worker, needs_auth=True,
            loading_text=self.app.translate("loading_cancelling_schedule"))

    def _shutdown_restart_handler(self, action_flag, output_widget, countdown_label):
        """Handler para shutdown e restart."""
        self.output_textbox = output_widget
        self.countdown_label = countdown_label
        dialog = CustomInputDialog(self.app, title=self.app.translate("schedule_action_title"), text=self.app.translate("schedule_action_prompt"))
        input_raw = dialog.get_input()

        if input_raw:
            parts = [p.strip() for p in input_raw.split(',', 1)]
            try:
                minutes = int(parts[0])
                if minutes < 0:
                    self.app.show_error(self.app.translate("error_invalid_minutes_positive"))
                    return
                
                message = parts[1] if len(parts) > 1 else self.app.translate("system_scheduled_action")
                delay_seconds = minutes * 60
                
                action_text = self.app.translate("schedule_restart").upper() if action_flag == "/r" else self.app.translate("schedule_shutdown").upper()
                title_text = self.app.translate("confirm_restart_title") if action_flag == "/r" else self.app.translate("confirm_shutdown_title")
                full_display_name = self._get_full_display_name()
                
                if not self.app.ask_yes_no(
                    title_text,
                    self.app.translate("confirm_action_on_host", action=action_text, full_display_name=full_display_name)
                ):
                    return

                command_name = "restart" if action_flag == "/r" else "shutdown"
                self._start_command(command_name, self._shutdown_restart_worker,
                    args_tuple=(action_flag, message, delay_seconds), needs_auth=True,
                    loading_text=self.app.translate("loading_scheduling_action"))
            except (ValueError, IndexError):
                self.app.show_error(self.app.translate("Formato inválido. Use: minutos, mensagem"))

    def _shutdown_restart_worker(self, username, password, action_flag, message, delay_seconds):
        """Worker simplificado e robusto para shutdown/restart."""
        logging.info(f"SHUTDOWN: Executando {action_flag} para {self.host['ip']}, delay: {delay_seconds}s")
        
        try:
            if delay_seconds > 0:
                self.countdown_end_time = datetime.now() + timedelta(seconds=delay_seconds)
                # Iniciar countdown diretamente
                try:
                    self.app.after_idle(self.update_countdown)
                except:
                    pass
            
            # Executar comando de shutdown/restart
            for line in self.system_tools.execute_shutdown_command(self.host['ip'], username, password, action_flag, message, delay_seconds):
                if not self.is_running:
                    logging.info(f"SHUTDOWN: Cancelado pelo usuário - IP: {self.host['ip']}")
                    break
                    
                if isinstance(line, dict) and line.get("status") == "error":
                    logging.error(f"SHUTDOWN: Erro WinRM para {self.host['ip']}")
                    try:
                        self.app.after_idle(self.app.show_winrm_error_dialog)
                    except:
                        pass
                    return
                
                # Atualizar output diretamente
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", str(line))
                        self.output_textbox.see("end") 
                        self.output_textbox.configure(state="disabled")
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"SHUTDOWN: Erro inesperado para {self.host['ip']}: {e}")
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\nErro no comando: {e}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            logging.info(f"SHUTDOWN: Worker finalizado para {self.host['ip']}")

    def _cancel_shutdown_worker(self, username, password):
        """Worker simplificado e robusto para cancelar shutdown/restart."""
        logging.info(f"CANCEL_SHUTDOWN: Cancelando agendamento para {self.host['ip']}")
        
        try:
            # Executar comando de cancelamento
            for line in self.system_tools.execute_shutdown_command(self.host['ip'], username, password, "/a", "", 0):
                if not self.is_running:
                    logging.info(f"CANCEL_SHUTDOWN: Cancelado pelo usuário - IP: {self.host['ip']}")
                    break
                    
                if isinstance(line, dict) and line.get("status") == "error":
                    logging.error(f"CANCEL_SHUTDOWN: Erro WinRM para {self.host['ip']}")
                    try:
                        self.app.after_idle(self.app.show_winrm_error_dialog)
                    except:
                        pass
                    return
                
                # Atualizar output diretamente
                try:
                    if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                        self.output_textbox.configure(state="normal")
                        self.output_textbox.insert("end", str(line))
                        self.output_textbox.see("end")
                        self.output_textbox.configure(state="disabled")
                except:
                    pass
            
            # Cancelar countdown job se existir        
            if self.countdown_job_id:
                try:
                    self.app.after_cancel(self.countdown_job_id)
                    self.countdown_job_id = None
                except:
                    pass
            
            # Atualizar label do countdown diretamente
            try:
                if self.countdown_label and hasattr(self.countdown_label, 'winfo_exists') and self.countdown_label.winfo_exists():
                    self.countdown_label.configure(text=self.app.translate("schedule_no_active"))
            except:
                pass
                
        except Exception as e:
            logging.error(f"CANCEL_SHUTDOWN: Erro inesperado para {self.host['ip']}: {e}")
            try:
                if self.output_textbox and hasattr(self.output_textbox, 'winfo_exists') and self.output_textbox.winfo_exists():
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", f"\nErro no cancelamento: {e}\n")
                    self.output_textbox.configure(state="disabled")
            except:
                pass
                
        finally:
            logging.info(f"CANCEL_SHUTDOWN: Worker finalizado para {self.host['ip']}")

    def _get_full_display_name(self):
        """Obtém o nome completo para exibição."""
        nickname = self.host.get('nickname', '').strip()
        original_name = self.host.get('name')
        if nickname and nickname != original_name:
            return f"'{original_name}' (aba: {nickname})"
        return f"'{original_name}'"

    def update_countdown(self):
        """Atualiza o contador regressivo."""
        if self.countdown_end_time and self.countdown_label and self.countdown_label.winfo_exists():
            remaining = self.countdown_end_time - datetime.now()
            if remaining.total_seconds() > 0:
                mins, secs = divmod(int(remaining.total_seconds()), 60)
                self.countdown_label.configure(text=f"{self.app.translate('schedule_remaining_time')} {mins:02d}:{secs:02d}")
                self.countdown_job_id = self.app.after(1000, self.update_countdown)
            else:
                self.countdown_label.configure(text=self.app.translate("schedule_no_active"))