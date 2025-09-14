# ui_components/host_manager_frame.py
# Painel esquerdo para gerenciar a lista de hosts e configurações.

import customtkinter
import logging

class HostManagerFrame(customtkinter.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, width=250)
        self.app = app
        logging.info("Initializing HostManagerFrame")
        self.grid_propagate(False)
        self.grid_rowconfigure(2, weight=1)

        # --- Título ---
        self.title_label = customtkinter.CTkLabel(self, text="", font=customtkinter.CTkFont(size=16, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=10, pady=(20, 10), sticky="ew")
        
        # --- Linha Separadora ---
        separator = customtkinter.CTkFrame(self, height=2, fg_color="gray20")
        separator.grid(row=1, column=0, padx=10, sticky="ew")

        # --- Lista de Hosts ---
        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.grid(row=2, column=0, sticky="nsew", padx=5)
        self.host_widgets = []

        # --- Frame de Configurações ---
        settings_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        settings_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        settings_frame.grid_columnconfigure(0, weight=1)

        self.sound_on_icon_text = "🔊"
        self.sound_off_icon_text = "🔇"
        self.sound_button = customtkinter.CTkButton(settings_frame, text="", font=customtkinter.CTkFont(size=24), width=30, height=30, command=self.app.toggle_sound, fg_color="transparent")
        self.sound_button.grid(row=0, column=1, sticky="e")

        self.appearance_mode_label = customtkinter.CTkLabel(settings_frame, text="", anchor="w")
        self.appearance_mode_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(settings_frame, values=[], command=self.app.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")

        self.scaling_label = customtkinter.CTkLabel(settings_frame, text="", anchor="w")
        self.scaling_label.grid(row=3, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        self.scaling_optionemenu = customtkinter.CTkOptionMenu(settings_frame, values=["80%", "90%", "100%", "110%", "120%"], command=self.app.change_scaling_event)
        self.scaling_optionemenu.grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        self.language_label = customtkinter.CTkLabel(settings_frame, text="", anchor="w")
        self.language_label.grid(row=5, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        self.language_optionemenu = customtkinter.CTkOptionMenu(settings_frame, values=["Português", "English", "Español"], command=self.app.change_language_event)
        self.language_optionemenu.grid(row=6, column=0, columnspan=2, padx=10, pady=(0, 20), sticky="ew")


    def update_host_list(self):
        """Limpa e recria a lista de widgets de host."""
        logging.debug("Updating host list display")
        for widget in self.host_widgets:
            widget.destroy()
        self.host_widgets = []

        for host in self.app.favorites:
            host_frame = customtkinter.CTkFrame(self.scrollable_frame, fg_color="transparent")
            host_frame.pack(fill="x", expand=True, pady=4)
            host_frame.grid_columnconfigure(1, weight=1)

            # Indicador de Status
            status = self.app.host_statuses.get(host['ip'], 'unknown')
            status_color = {"online": "#2ECC71", "offline": "#E74C3C"}.get(status, "grey")
            status_indicator = customtkinter.CTkLabel(host_frame, text="●", text_color=status_color, font=("Arial", 20))
            status_indicator.grid(row=0, column=0, rowspan=2, padx=(0, 5))

            # Nome e IP
            name_label = customtkinter.CTkLabel(host_frame, text=host['name'], anchor="w", font=customtkinter.CTkFont(weight="bold"))
            name_label.grid(row=0, column=1, sticky="w")
            ip_label = customtkinter.CTkLabel(host_frame, text=host['ip'], anchor="w", font=customtkinter.CTkFont(size=11), text_color="white")
            ip_label.grid(row=1, column=1, sticky="w")
            
            # Botões de Ação
            connect_button = customtkinter.CTkButton(host_frame, text=self.app.translate("ui_connect"), width=60, height=24,
                                                     command=lambda h=host: (logging.info(f"Connect button clicked for host: {h.get('name', h.get('ip'))}"), self.app.controller.connect_to_host(h)))
            connect_button.grid(row=0, column=2, padx=5)

            remove_button = customtkinter.CTkButton(host_frame, text="✕", width=24, height=24, fg_color="#E74C3C", hover_color="#C0392B",
                                                    command=lambda h=host: (logging.info(f"Remove button clicked for host: {h.get('name', h.get('ip'))}"), self.app.controller.remove_host(h)))
            remove_button.grid(row=1, column=2, padx=5)

            self.host_widgets.extend([host_frame, status_indicator, name_label, ip_label, connect_button, remove_button])

    def update_language(self):
        """Atualiza os textos de todos os widgets no frame."""
        self.title_label.configure(text=self.app.translate("ui_host_manager_title"))
        logging.debug("Updating UI for language change")
        self.appearance_mode_label.configure(text=self.app.translate("ui_appearance"))
        self.scaling_label.configure(text=self.app.translate("ui_scaling"))
        self.language_label.configure(text=self.app.translate("ui_language"))
        
        self.appearance_mode_optionemenu.configure(values=[self.app.translate("label_system"), self.app.translate("label_light"), self.app.translate("label_dark")])
        self.appearance_mode_optionemenu.set(self.app.get_appearance_mode_display_name(customtkinter.get_appearance_mode()))
        self.scaling_optionemenu.set(self.app.current_scaling)
        self.language_optionemenu.set(self.app.get_language_display_name(self.app.current_language))
        
        self.update_host_list()
        self.update_sound_icon()

    def update_sound_icon(self):
        if self.app.play_sound_on_finish.get():
            logging.debug("Updating sound icon to ON")
            self.sound_button.configure(text=self.sound_on_icon_text)
        else:
            logging.debug("Updating sound icon to OFF")
            self.sound_button.configure(text=self.sound_off_icon_text)