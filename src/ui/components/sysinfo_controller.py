# app/ui_components/tool_controllers/sysinfo_controller.py
# Contém a lógica de negócios para a aba "Sistema".

from .base_controller import BaseToolController, Q_ITEM_CALLBACK
from datetime import datetime, timedelta

class SysInfoController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)

    def get_system_info(self, callback_update_general, callback_update_disks):
        """
        Orquestra a busca de informações do sistema.
        """
        # Limpa e prepara a UI antes de iniciar o comando
        if callback_update_general and hasattr(self.app, 'after'):
             self.app.after(0, lambda: callback_update_general(None, show_loading=True))

        self._start_command("get_sysinfo", self._get_sysinfo_worker,
                            args_tuple=(callback_update_general, callback_update_disks),
                            needs_auth=True,
                            loading_text=self.app.translate("loading_getting_sysinfo"))

    def _get_sysinfo_worker(self, username, password, callback_update_general, callback_update_disks):
        """
        Worker executado em uma thread para buscar e processar as informações do sistema.
        """
        raw_data = self.system_tools.get_remote_system_info_raw(self.host['ip'], username, password)

        if "error" in raw_data:
            if self._is_winrm_connection_error(raw_data.get("exception_obj")):
                self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
            
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_general, ({"error": raw_data["error"]},), {}))
            return

        # Processa os dados brutos para torná-los mais amigáveis
        processed_data = self._process_raw_sysinfo(raw_data)

        # Envia os dados processados de volta para a UI através de callbacks na fila
        self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_general, (processed_data,), {}))
        self._put_in_queue(Q_ITEM_CALLBACK, (callback_update_disks, (raw_data.get("Disks", []),), {}))

    def _process_raw_sysinfo(self, raw_data):
        """
        Converte os dados brutos do PowerShell em um formato mais legível.
        """
        processed = raw_data.copy()

        # Processar Uptime
        try:
            boot_time_str = raw_data.get("LastBootUpTime")
            if boot_time_str:
                boot_time = datetime.fromisoformat(boot_time_str)
                uptime = datetime.now() - boot_time
                
                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                uptime_str = f"{days} {self.app.translate('time_days')}, {hours} {self.app.translate('time_hours')}, {minutes} {self.app.translate('time_minutes')}"
                processed["Uptime"] = uptime_str
        except (ValueError, TypeError):
            processed["Uptime"] = self.app.translate("sysinfo_invalid_date")

        # Processar Data de Instalação
        try:
            install_date_str = raw_data.get("OS_InstallDate")
            if install_date_str:
                install_date = datetime.fromisoformat(install_date_str)
                processed["InstallDate"] = install_date.strftime("%d/%m/%Y %H:%M:%S")
        except (ValueError, TypeError):
            processed["InstallDate"] = self.app.translate("sysinfo_invalid_date")
            
        return processed