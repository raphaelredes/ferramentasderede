# app/ui_components/remote_actions_frame.py
# Frame que contém os botões para ações remotas rápidas e sessões de usuário.

import customtkinter
from .remote_sessions_frame import RemoteSessionsFrame
import logging

class RemoteActionsFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host_info, controllers, info_display): # Adicionado info_display
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.host_info = host_info
        self.controllers = controllers
        self.tool_controller = controllers['remote_actions']
        self.info_display = info_display # Armazenar a referência

        logging.info(f"Initializing RemoteActionsFrame for host: {self.host_info.get('name', self.host_info.get('ip', 'N/A'))}")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Removendo duplicação - funcionalidades movidas para RemoteSessionsFrame
        
        # --- Frame de Sessões de Usuário ---
        # CORREÇÃO: Passando o info_display que estava faltando
        sessions_frame = RemoteSessionsFrame(self, self.app, self.host_info, self.controllers['remote_sessions'], self.info_display)
        sessions_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)