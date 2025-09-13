# app/ui_components/tool_controllers/remote_shell_controller.py

from .base_controller import BaseToolController, Q_ITEM_TEXT, Q_ITEM_CALLBACK

class RemoteShellController(BaseToolController):
    def __init__(self, app, host, hostname):
        super().__init__(app, host, hostname)

    def launch_shell(self, output_widget):
        self.output_textbox = output_widget
        self.clear_output()
        self.add_output_line(self.app.translate("interactive_shell_log_start"))
        self.add_output_line(self.app.translate("interactive_shell_log_credentials"))
        self.add_output_line(self.app.translate("interactive_shell_log_window"))

        self._start_command(
            "launch_shell",
            self._launch_shell_worker,
            needs_auth=True,
            loading_text=""
        )

    def _launch_shell_worker(self, username, password):
        success, message = self.system_tools.launch_interactive_remote_shell(
            self.host['ip'], username, password
        )
        if success:
            self._put_in_queue(Q_ITEM_TEXT, f"\nSUCESSO: {message}\n")
            # Fecha explicitamente o loading em caso de sucesso
            self._put_in_queue(Q_ITEM_CALLBACK, (self._close_loading_window, tuple(), {}))
        else:
            self._put_in_queue(Q_ITEM_TEXT, f"\nFALHA: {message}\n")
            # Fecha explicitamente o loading também em falha
            self._put_in_queue(Q_ITEM_CALLBACK, (self._close_loading_window, tuple(), {}))