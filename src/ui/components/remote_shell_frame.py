# app/ui_components/remote_shell_frame.py
# Frame para executar comandos remotos em um shell interativo.

import customtkinter
try:
    from ...config.settings import MONOSPACE_FONT
except ImportError:
    from src.config.settings import MONOSPACE_FONT
import logging
from .context_menu import TerminalContextMenu

class RemoteShellFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller):
        super().__init__(master, fg_color="transparent")
        self.app = app
        logging.info(f"Initializing RemoteShellFrame for host: {host.get('name', host.get('ip', 'unknown'))}")
        self.host = host
        self.tool_controller = tool_controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(0, weight=1)
        
        self.launch_button = customtkinter.CTkButton(
            controls_frame, 
            text="", 
            command=self.launch_shell
        )
        self.launch_button.pack(fill="x", expand=True, padx=10, pady=10)
        
        self.info_label = customtkinter.CTkLabel(
            controls_frame, 
            text="", 
            wraplength=450,
            justify="center",
            text_color="white"
        )
        self.info_label.pack(fill="x", expand=True, padx=10, pady=(0, 10))

        self.output_textbox = customtkinter.CTkTextbox(self, font=MONOSPACE_FONT, height=300)
        self.output_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.output_textbox.configure(state="disabled")
        
        TerminalContextMenu(self.app, self.output_textbox)
        
        self.update_language()

    def launch_shell(self):
        logging.info(f"Launch shell button clicked for host: {self.host.get('name', self.host.get('ip', 'unknown'))}")
        if self.tool_controller.is_running:
            logging.warning(f"Shell launch prevented: another command is running for host: {self.host.get('name', self.host.get('ip', 'unknown'))}")
            self.app.show_info("Aguarde a ação anterior ser concluída.")
            return
        logging.info(f"Launching remote shell for host: {self.host.get('name', self.host.get('ip', 'unknown'))}")
        self.tool_controller.launch_shell(self.output_textbox)

    def update_language(self):
        self.launch_button.configure(text=self.app.translate("remote_shell_start"))
        self.info_label.configure(text=self.app.translate("interactive_shell_info"))