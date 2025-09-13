# app/ui_components/tool_controllers/services_controller.py

import time
from .base_controller import BaseToolController, Q_ITEM_CALLBACK

class ServicesController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)

    def get_services(self, callback_populate_list):
        self._start_command("get_services", self._get_services_worker, 
            args_tuple=(callback_populate_list,), needs_auth=True)

    def _get_services_worker(self, username, password, callback_populate_list):
        services_data = self.system_tools.get_remote_services(self.host['ip'], username, password)
        if "error" in services_data and self._is_winrm_connection_error(services_data.get("exception_obj")):
            self._put_in_queue(Q_ITEM_CALLBACK, (self.app.show_winrm_error_dialog, (), {}))
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_populate_list, ([],), {}))
        else:
            self._put_in_queue(Q_ITEM_CALLBACK, (callback_populate_list, (services_data,), {}))
            
    def manage_service(self, service_name, action, callback_after_action):
        self._start_command(f"{action}_service", self._manage_service_worker,
            args_tuple=(service_name, action, callback_after_action), 
            needs_auth=True)

    def _manage_service_worker(self, username, password, service_name, action, callback_after_action):
        expected_status = 4 if action in ["start", "restart"] else 1
        for _ in self.system_tools.manage_remote_service(self.host['ip'], username, password, service_name, action):
            pass
        
        time.sleep(2)
        new_service_data = self.system_tools.get_single_remote_service(self.host['ip'], username, password, service_name)
        status_changed = False
        if "error" not in new_service_data and isinstance(new_service_data, dict):
            current_status = new_service_data.get("Status")
            if current_status == expected_status:
                status_changed = True
        self._put_in_queue(Q_ITEM_CALLBACK, (callback_after_action, (service_name, new_service_data, status_changed), {}))