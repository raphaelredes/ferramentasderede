# app/app_ui_manager.py
# Gerencia a criação e atualização dos widgets da janela principal.

import os
import customtkinter
from PIL import Image
from .host_tab_view import HostTabView
from .info_widgets import show_about_popup

class AppUIManager:
    def __init__(self, app, translator):
        self.app = app
        self.translator = translator
        self.controller = app.controller
        self.settings = app.settings_manager

    def create_widgets(self):
        """Cria todos os widgets da janela principal."""
        self.app.grid_columnconfigure(0, weight=1)
        self.app.grid_rowconfigure(0, weight=1)

        # Frame principal sem bordas brancas
        # Obter cor de fundo baseada no tema atual
        import customtkinter
        current_appearance = customtkinter.get_appearance_mode()
        
        if current_appearance.lower() == "dark":
            main_bg_color = "#212121"  # Cinza escuro
        else:
            main_bg_color = "#f0f0f0"  # Cinza claro
            
        main_content_frame = customtkinter.CTkFrame(
            self.app, 
            fg_color=main_bg_color,  # Usar cor apropriada para o tema
            corner_radius=0,
            border_width=0
        )
        main_content_frame.grid(row=0, column=0, sticky="nsew")
        main_content_frame.grid_columnconfigure(0, weight=1)
        main_content_frame.grid_rowconfigure(1, weight=1) 

        # Frame superior sem bordas
        top_frame = customtkinter.CTkFrame(
            main_content_frame, 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=0)  # Coluna dos botões com peso 0
        top_frame.grid_columnconfigure(2, weight=0)  # Coluna do menu com peso 0

        self._create_top_buttons(top_frame)
        self._create_settings_widgets(top_frame)
        
        # Restaurar o HostTabView original com todas as funcionalidades
        from .host_tab_view import HostTabView
        self.app.host_tab_view = HostTabView(main_content_frame, self.app, self.controller)
        self.app.host_tab_view.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Frame inferior sem bordas
        bottom_frame = customtkinter.CTkFrame(
            main_content_frame, 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        self._create_bottom_widgets(bottom_frame)

    def _create_top_buttons(self, parent):
        """Cria os botões de ação principais."""
        # Container de botões sem bordas
        button_container = customtkinter.CTkFrame(
            parent,
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        button_container.grid(row=0, column=0, sticky="w", padx=(0, 20))

        # Botão para adicionar novo host
        self.app.add_host_button = customtkinter.CTkButton(
            button_container, text="+ Host", width=80, height=32,
            font=customtkinter.CTkFont(size=12, weight="bold"),
            text_color="white",
            command=self.controller.add_new_host
        )
        self.app.add_host_button.pack(side="left", padx=(0, 10))

        # Botão de configurações das abas
        self.app.tab_settings_button = customtkinter.CTkButton(
            button_container, text="⚙️", width=40, height=32,
            font=customtkinter.CTkFont(size=14),
            text_color="white",
            command=self.controller.open_tab_settings_dialog
        )
        self.app.tab_settings_button.pack(side="left", padx=(0, 20))

        self.app.actions_menu_keys = [
            "title_remove_hosts",
            "actions_import",
            "actions_export",
            "actions_manage_creds"
        ]
        # Inicializar com valores traduzidos imediatamente
        initial_values = [self.translator.translate(key) for key in self.app.actions_menu_keys]
        self.app.actions_menu = customtkinter.CTkOptionMenu(
            button_container,
            values=initial_values,
            width=180,  # Largura ajustada
            height=32,  # Altura TOTALMENTE fixa
            font=customtkinter.CTkFont(size=12),  # Fonte fixa
            dropdown_font=customtkinter.CTkFont(size=11)  # Fonte dropdown fixa
        )
        # Definir valor inicial imediatamente
        self.app.actions_menu.set(self.translator.translate("actions_menu_title"))
        
        # Criar mapeamento de comandos imediatamente
        self._action_text_to_key_map = {self.translator.translate(key): key for key in self.app.actions_menu_keys}
        
        def command_wrapper(translated_choice):
            """
            Wrapper melhorado para comando do menu que evita chamadas desnecessárias.
            """
            # Verificar se é uma escolha válida
            if not translated_choice:
                return
                
            # Verificar se é o título do menu (evitar flicker)
            if translated_choice == self.translator.translate("actions_menu_title"):
                return
                
            # Buscar a chave correspondente
            key = self._action_text_to_key_map.get(translated_choice)
            if key:
                import logging
                logging.debug(f"Comando do menu executado: {translated_choice} -> {key}")
                self.app.handle_action_menu(key)
            else:
                import logging
                logging.debug(f"Opção de menu desconhecida: {translated_choice}")
        
        self.app.actions_menu.configure(command=command_wrapper)
        self.app.actions_menu.pack(side="left", padx=(0, 10))

    def _create_settings_widgets(self, parent):
        """Cria os widgets de configurações (aparência, idioma)."""
        # Container de configurações sem bordas
        settings_container = customtkinter.CTkFrame(
            parent, 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        settings_container.grid(row=0, column=2, sticky="e")
        
        self.app.appearance_mode_label = customtkinter.CTkLabel(
            settings_container, 
            text="", 
            anchor="w", 
            text_color="white",
            width=80,  # Largura TOTALMENTE fixa
            height=32,  # Altura TOTALMENTE fixa
            font=customtkinter.CTkFont(size=12)  # Fonte fixa
        )
        self.app.appearance_mode_label.pack(side="left", padx=(10, 5))
        
        # Inicializar com valores traduzidos imediatamente
        appearance_values = [
            self.translator.translate("label_system"), 
            self.translator.translate("label_light"), 
            self.translator.translate("label_dark")
        ]
        self.app.appearance_mode_menu = customtkinter.CTkOptionMenu(
            settings_container, 
            values=appearance_values,
            command=self.settings.change_appearance_mode_event,
            width=120,  # Largura TOTALMENTE fixa
            height=32,  # Altura TOTALMENTE fixa
            font=customtkinter.CTkFont(size=12),  # Fonte fixa
            dropdown_font=customtkinter.CTkFont(size=11)  # Fonte dropdown fixa
        )
        # Definir valor inicial imediatamente
        self.app.appearance_mode_menu.set(self.settings.get_appearance_mode_display_name(self.app.current_appearance_mode))
        self.app.appearance_mode_menu.pack(side="left", padx=(0, 10))

    def _create_bottom_widgets(self, parent):
        """Cria os widgets do rodapé (Sobre, Idioma)."""
        parent.grid_columnconfigure(1, weight=1)

        # Container esquerdo sem bordas
        left_container = customtkinter.CTkFrame(
            parent, 
            fg_color="transparent",
            corner_radius=0,
            border_width=0
        )
        left_container.grid(row=0, column=0, sticky="w", padx=(5, 0))

        from .info_widgets import show_about_popup
        self.app.about_button = customtkinter.CTkButton(
            left_container, 
            text="", 
            width=80,  # Largura TOTALMENTE fixa
            height=28,  # Altura TOTALMENTE fixa
            fg_color="transparent", 
            text_color="white", 
            hover=False, 
            command=lambda: show_about_popup(self.app),
            corner_radius=6,
            font=customtkinter.CTkFont(size=11)  # Fonte fixa
        )
        self.app.about_button.pack(side="left", padx=(0, 15))
        
        self.app.language_menu = customtkinter.CTkOptionMenu(
            left_container, 
            values=["Português", "English", "Español"], 
            command=self.settings.change_language_event,
            width=120,  # Largura TOTALMENTE fixa
            height=28,  # Altura TOTALMENTE fixa
            font=customtkinter.CTkFont(size=11),  # Fonte fixa
            dropdown_font=customtkinter.CTkFont(size=10)  # Fonte dropdown fixa
        )
        # Definir valor inicial imediatamente
        self.app.language_menu.set(self.settings.get_language_display_name(self.app.current_language))
        self.app.language_menu.pack(side="left")

    def update_ui_texts(self):
        """Atualiza todos os textos da UI para o idioma atual."""
        translated_title = self.translator.translate("title_app")
        self.app.title(translated_title)

        self.app.about_button.configure(text=self.translator.translate("title_about"))

        # Atualizar textos dos novos botões
        if hasattr(self.app, 'add_host_button'):
            self.app.add_host_button.configure(text="+ Host")

        self.app.language_menu.set(self.settings.get_language_display_name(self.app.current_language))
        self.app.appearance_mode_label.configure(text=self.translator.translate("ui_appearance"))

        translated_appearance_modes = [
            self.translator.translate("label_system"),
            self.translator.translate("label_light"),
            self.translator.translate("label_dark")
        ]
        self.app.appearance_mode_menu.configure(values=translated_appearance_modes)
        self.app.appearance_mode_menu.set(self.settings.get_appearance_mode_display_name(self.app.current_appearance_mode))

        self._update_actions_menu()

        if hasattr(self.app, 'host_tab_view') and self.app.host_tab_view:
            self.app.host_tab_view.update_language()

    def _update_actions_menu(self):
        """Atualiza os itens e o comando do menu de ações."""
        translated_values = [self.translator.translate(key) for key in self.app.actions_menu_keys]
        self.app.actions_menu.configure(values=translated_values)
        self.app.actions_menu.set(self.translator.translate("actions_menu_title"))

        # Atualizar mapeamento de comandos
        self._action_text_to_key_map = {self.translator.translate(key): key for key in self.app.actions_menu_keys}
        
        def new_command(translated_choice):
            """Comando atualizado que evita flicker."""
            # Verificar se é uma escolha válida
            if not translated_choice:
                return

            # Verificar se é o título do menu (evitar flicker)
            if translated_choice == self.translator.translate("actions_menu_title"):
                return

            key = self._action_text_to_key_map.get(translated_choice)
            if key:
                self.app.handle_action_menu(key)