# app/ui_components/tool_controllers/system_info_controller.py

import customtkinter
from datetime import datetime, timedelta
from .base_controller import BaseToolController, Q_ITEM_CALLBACK, Q_ITEM_TEXT
from ..loading_window import LoadingWindow
from ..credential_dialog import CredentialDialog
from ..custom_dialogs import PasswordInputDialog
from ..custom_input_dialog import CustomInputDialog
from ..credential_service import SALT_FILE

class SystemInfoController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)
        self.countdown_end_time = None
        self.countdown_job_id = None
        self.countdown_label = None
        self.system_info_panel = None
        self.info_display_widget = None

    def get_sysinfo(self, store_only=False):
        """Busca informações do sistema. Se store_only=True, apenas armazena os dados."""
        self._start_command("get_sysinfo", self._get_system_info_worker,
            args_tuple=(store_only,),
            needs_auth=True,
            loading_text=self.app.translate("loading_getting_sysinfo"))

    def _get_system_info_worker(self, username, password, store_only):
        sys_info_data = self.system_tools.get_remote_system_info_raw(self.host['ip'], username, password)

        if "error" in sys_info_data:
            exception_obj = sys_info_data.get("exception_obj")
            if self._is_winrm_connection_error(exception_obj):
                self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
            
            if not store_only:
                self._put_in_queue(Q_ITEM_CALLBACK, (self.update_ui_with_data, (sys_info_data,), {}))
            return

        # Armazena os dados no dicionário do host para acesso futuro
        self.host['system_info'] = sys_info_data
        
        if not store_only:
            self._put_in_queue(Q_ITEM_CALLBACK, (self.update_ui_with_data, (sys_info_data,), {}))

    def update_ui_with_data(self, data_to_display):
        """Atualiza os widgets da UI com os dados fornecidos."""
        if self.system_info_panel and self.system_info_panel.winfo_exists():
            self.system_info_panel.display_info(data_to_display)
        
        if "error" not in data_to_display:
            subnet = data_to_display.get("SubnetMask", "...")
            if self.info_display_widget and self.info_display_widget.winfo_exists():
                self.info_display_widget.update_info(subnet_mask=subnet)
        
    def _shutdown_restart_worker(self, username, password, action_flag, message, delay_seconds):
        if delay_seconds > 0:
            self.countdown_end_time = datetime.now() + timedelta(seconds=delay_seconds)
            self._put_in_queue(Q_ITEM_CALLBACK, (self.update_countdown, (), {}))
        
        generator = self.system_tools.execute_shutdown_command(self.host['ip'], username, password, action_flag, message, delay_seconds)
        for line in generator:
            if isinstance(line, dict) and line.get("status") == "error":
                self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
                return
            self._put_in_queue(Q_ITEM_TEXT, str(line))

    def _get_full_display_name(self):
        nickname = self.host.get('nickname', '').strip()
        original_name = self.host.get('name')
        if nickname and nickname != original_name:
            return f"'{original_name}' (aba: {nickname})"
        return f"'{original_name}'"

    def _shutdown_restart_handler(self, action_flag, output_widget, countdown_label):
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

    def restart_host(self, output_widget, countdown_label):
        self._shutdown_restart_handler("/r", output_widget, countdown_label)

    def shutdown_host(self, output_widget, countdown_label):
        self._shutdown_restart_handler("/s", output_widget, countdown_label)
        
    def _cancel_shutdown_worker(self, username, password):
        for line in self.system_tools.execute_shutdown_command(self.host['ip'], username, password, "/a", "", 0):
            if isinstance(line, dict) and line.get("status") == "error":
                self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
                return
            self._put_in_queue(Q_ITEM_TEXT, str(line))
            
        if self.countdown_job_id:
            self.app.after_cancel(self.countdown_job_id)
            self.countdown_job_id = None
        
        update_label_args = ({"text": self.app.translate("schedule_no_active")},)
        self._put_in_queue(Q_ITEM_CALLBACK, (self.countdown_label.configure, update_label_args, {}))

    def cancel_shutdown(self, output_widget, countdown_label):
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

    def update_countdown(self):
        if self.countdown_end_time and self.countdown_label and self.countdown_label.winfo_exists():
            remaining = self.countdown_end_time - datetime.now()
            if remaining.total_seconds() > 0:
                mins, secs = divmod(int(remaining.total_seconds()), 60)
                self.countdown_label.configure(text=f"{self.app.translate('schedule_remaining_time')} {mins:02d}:{secs:02d}")
                self.countdown_job_id = self.app.after(1000, self.update_countdown)
            else:
                self.countdown_label.configure(text=self.app.translate("schedule_no_active"))