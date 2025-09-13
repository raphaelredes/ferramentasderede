# app/ui_components/traceroute_frame.py

import customtkinter
try:
    from ...config.settings import MONOSPACE_FONT
except ImportError:
    from src.config.settings import MONOSPACE_FONT
import logging
from .context_menu import TerminalContextMenu

class TracerouteFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller):
        super().__init__(master, fg_color="transparent")
        self.app = app
        logging.info(f"Initializing TracerouteFrame for host: {host.get('name', host.get('ip', 'N/A'))}")
        self.host = host
        self.tool_controller = tool_controller

        # Configurar grid para melhor distribuição do espaço
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # A área de texto deve expandir

        # Botão de controle - mais compacto
        self.start_button = customtkinter.CTkButton(self, text="", command=self.toggle_traceroute, height=32)
        self.start_button.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        # Área de texto - maior e mais responsiva
        self.output_textbox = customtkinter.CTkTextbox(self, wrap="word", font=MONOSPACE_FONT, height=300)
        self.output_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.output_textbox.configure(state="disabled")

        TerminalContextMenu(self.app, self.output_textbox)
        
        self.update_language()

    def toggle_traceroute(self):
        if self.tool_controller.is_running:
            logging.info(f"Stopping traceroute for host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
            self.tool_controller.stop_command()
            # Refletir imediatamente
            self.start_button.configure(text=self.app.translate("traceroute_start"))
        else:
            logging.info(f"Starting traceroute for host: {self.host.get('name', self.host.get('ip', 'N/A'))}")
            # Usar o fluxo do controller, que usa o IP do host de destino
            self.tool_controller.run_traceroute(self.output_textbox)
            # Refletir imediatamente
            self.start_button.configure(text=self.app.translate("label_cancel"))
        self.update_button_state()

    def update_button_state(self):
        is_running = self.tool_controller.is_running
        button_text = self.app.translate("label_cancel") if is_running else self.app.translate("traceroute_start")
        logging.debug(f"Updating traceroute button state: {'Running' if is_running else 'Stopped'}, text: {button_text}")
        self.start_button.configure(text=button_text)

    def update_language(self):
        self.update_button_state()