# src/ferramentasderede/ui/components/tab_settings_dialog.py
# Janela para configurar o intervalo e renomear as abas, com suporte a drag-and-drop.

import customtkinter
from .base_dialog import BaseDialog
import logging

class TabSettingsDialog(BaseDialog):
    def __init__(self, master, app, current_interval, all_hosts, ask_initial_info):
        super().__init__(app=app, title=app.translate("tab_settings_title"))
        logging.info(f"Initializing TabSettingsDialog with interval: {current_interval}, ask_initial_info: {ask_initial_info}")
        self.hosts_local_list = list(all_hosts) 
        self.result_data = None

        self.host_frames = []
        self.drag_widget = None
        self.drag_start_y = 0
        self.drop_indicator = None

        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(600, 700)
        self.bind("<Escape>", self.on_close)

        # Container principal com scroll
        main_scroll = customtkinter.CTkScrollableFrame(self)
        main_scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_scroll.grid_columnconfigure(0, weight=1)

        # === SEÇÃO 1: CONFIGURAÇÕES GERAIS ===
        general_section = customtkinter.CTkFrame(main_scroll, corner_radius=12)
        general_section.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        general_section.grid_columnconfigure(0, weight=1)

        # Título da seção com ícone
        general_title_frame = customtkinter.CTkFrame(general_section, fg_color="transparent")
        general_title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        general_title_frame.grid_columnconfigure(1, weight=1)

        general_icon = customtkinter.CTkLabel(general_title_frame, text="⚙️", font=customtkinter.CTkFont(size=20))
        general_icon.grid(row=0, column=0, padx=(0, 10))

        general_title = customtkinter.CTkLabel(
            general_title_frame,
            text="Configurações Gerais",
            font=customtkinter.CTkFont(size=16, weight="bold")
        )
        general_title.grid(row=0, column=1, sticky="w")

        # Separador
        separator1 = customtkinter.CTkFrame(general_section, height=1, fg_color=("gray80", "gray30"))
        separator1.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 15))

        # Configuração de intervalo
        interval_frame = customtkinter.CTkFrame(general_section, fg_color="transparent")
        interval_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))
        interval_frame.grid_columnconfigure(1, weight=1)

        interval_icon = customtkinter.CTkLabel(interval_frame, text="⏱️", font=customtkinter.CTkFont(size=16))
        interval_icon.grid(row=0, column=0, padx=(0, 10), pady=10)

        interval_content = customtkinter.CTkFrame(interval_frame, fg_color="transparent")
        interval_content.grid(row=0, column=1, sticky="ew")
        interval_content.grid_columnconfigure(0, weight=1)

        self.interval_label = customtkinter.CTkLabel(
            interval_content,
            text=self.app.translate("tab_settings_interval_label"),
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        self.interval_label.grid(row=0, column=0, sticky="w", pady=(10, 5))

        self.interval_entry = customtkinter.CTkEntry(
            interval_content,
            placeholder_text="Ex: 30",
            height=35
        )
        self.interval_entry.insert(0, str(current_interval))
        self.interval_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Configuração de informações iniciais
        info_frame = customtkinter.CTkFrame(general_section, fg_color="transparent")
        info_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        info_frame.grid_columnconfigure(1, weight=1)

        info_icon = customtkinter.CTkLabel(info_frame, text="ℹ️", font=customtkinter.CTkFont(size=16))
        info_icon.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="n")

        info_content = customtkinter.CTkFrame(info_frame, fg_color="transparent")
        info_content.grid(row=0, column=1, sticky="ew")
        info_content.grid_columnconfigure(0, weight=1)

        info_title = customtkinter.CTkLabel(
            info_content,
            text="Informações Iniciais",
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        info_title.grid(row=0, column=0, sticky="w", pady=(10, 5))

        checkbox_frame = customtkinter.CTkFrame(info_content, fg_color="transparent")
        checkbox_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        checkbox_frame.grid_columnconfigure(1, weight=1)

        self.ask_info_checkbox = customtkinter.CTkCheckBox(checkbox_frame, text="")
        self.ask_info_checkbox.grid(row=0, column=0, sticky="n")

        ask_info_label = customtkinter.CTkLabel(
            checkbox_frame,
            text=self.app.translate("tab_settings_ask_initial_info_label"),
            wraplength=450,
            justify="left",
            anchor="w"
        )
        ask_info_label.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ask_info_label.bind("<Button-1>", lambda e: self.ask_info_checkbox.toggle())

        if ask_initial_info:
            self.ask_info_checkbox.select()

        # === SEÇÃO 2: GERENCIAMENTO DE HOSTS ===
        hosts_section = customtkinter.CTkFrame(main_scroll, corner_radius=12)
        hosts_section.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        hosts_section.grid_columnconfigure(0, weight=1)

        # Título da seção com ícone
        hosts_title_frame = customtkinter.CTkFrame(hosts_section, fg_color="transparent")
        hosts_title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        hosts_title_frame.grid_columnconfigure(1, weight=1)

        hosts_icon = customtkinter.CTkLabel(hosts_title_frame, text="🖥️", font=customtkinter.CTkFont(size=20))
        hosts_icon.grid(row=0, column=0, padx=(0, 10))

        hosts_title = customtkinter.CTkLabel(
            hosts_title_frame,
            text="Gerenciamento de Hosts",
            font=customtkinter.CTkFont(size=16, weight="bold")
        )
        hosts_title.grid(row=0, column=1, sticky="w")

        # Separador
        separator2 = customtkinter.CTkFrame(hosts_section, height=1, fg_color=("gray80", "gray30"))
        separator2.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        # Instruções
        instructions = customtkinter.CTkLabel(
            hosts_section,
            text="📋 Arraste e solte os hosts para reordenar • Edite IPs e apelidos conforme necessário",
            font=customtkinter.CTkFont(size=11),
            text_color=("gray60", "gray40")
        )
        instructions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 15))

        # Frame para a lista de hosts
        hosts_content = customtkinter.CTkFrame(hosts_section, fg_color="transparent")
        hosts_content.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        hosts_content.grid_columnconfigure(0, weight=1)

        # Container compacto para a lista (sem cabeçalho)
        self.scrollable_frame = customtkinter.CTkScrollableFrame(hosts_content, height=220)
        self.scrollable_frame.grid(row=0, column=0, sticky="ew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.drop_indicator = customtkinter.CTkFrame(self.scrollable_frame, height=2, fg_color="cyan")

        self.populate_host_list()

        # === RESET DE FÁBRICA ===
        reset_section = customtkinter.CTkFrame(main_scroll, corner_radius=12)
        reset_section.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        reset_section.grid_columnconfigure(0, weight=1)

        # Botão reset com descrição
        reset_container = customtkinter.CTkFrame(reset_section, fg_color="transparent")
        reset_container.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        reset_container.grid_columnconfigure(1, weight=1)

        reset_icon = customtkinter.CTkLabel(reset_container, text="⚠️", font=customtkinter.CTkFont(size=16))
        reset_icon.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="n")

        reset_content = customtkinter.CTkFrame(reset_container, fg_color="transparent")
        reset_content.grid(row=0, column=1, sticky="ew")
        reset_content.grid_columnconfigure(0, weight=1)

        reset_title = customtkinter.CTkLabel(
            reset_content,
            text="Reset de Fábrica",
            font=customtkinter.CTkFont(size=13, weight="bold")
        )
        reset_title.grid(row=0, column=0, sticky="w", pady=(10, 2))

        reset_desc = customtkinter.CTkLabel(
            reset_content,
            text="Restaura todas as configurações para os valores padrão. Esta ação não pode ser desfeita.",
            font=customtkinter.CTkFont(size=11),
            text_color=("gray60", "gray40"),
            wraplength=400,
            justify="left"
        )
        reset_desc.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.reset_button = customtkinter.CTkButton(
            reset_content,
            text="🔄 " + self.app.translate("factory_reset_button"),
            command=self.app.controller.factory_reset,
            fg_color="#E74C3C",
            hover_color="#C0392B",
            height=35,
            font=customtkinter.CTkFont(size=12, weight="bold")
        )
        self.reset_button.grid(row=2, column=0, sticky="w", pady=(0, 10))

        # === BOTÕES DE AÇÃO PRINCIPAL ===
        bottom_buttons_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        bottom_buttons_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 20))
        bottom_buttons_frame.grid_columnconfigure(0, weight=1)

        # Container para botões centralizados
        buttons_container = customtkinter.CTkFrame(bottom_buttons_frame, fg_color="transparent")
        buttons_container.grid(row=0, column=0)

        self.save_button = customtkinter.CTkButton(
            buttons_container,
            text="💾 " + self.app.translate("label_save"),
            command=self.confirm,
            height=40,
            width=120,
            font=customtkinter.CTkFont(size=13, weight="bold"),
            fg_color="#27AE60",
            hover_color="#229954"
        )
        self.save_button.grid(row=0, column=0, padx=(0, 10))

        self.cancel_button = customtkinter.CTkButton(
            buttons_container,
            text="❌ " + self.app.translate("label_cancel"),
            command=self.on_close,
            height=40,
            width=120,
            font=customtkinter.CTkFont(size=13, weight="bold"),
            fg_color="#6C757D",
            hover_color="#5A6268"
        )
        self.cancel_button.grid(row=0, column=1)

    def populate_host_list(self):
        logging.debug("Populating host list for editing in TabSettingsDialog")
        for widget in self.host_frames:
            widget.destroy()
        self.host_frames = []
        
        for i, host in enumerate(self.hosts_local_list):
            # Card compacto de host
            container_frame = customtkinter.CTkFrame(
                self.scrollable_frame,
                fg_color=("gray92", "gray18"),
                corner_radius=6,
                height=40
            )
            container_frame.grid(row=i, column=0, sticky="ew", padx=4, pady=2)
            container_frame.grid_columnconfigure(1, weight=1)  # Coluna de conteúdo expansível
            container_frame.grid_propagate(False)

            # Handle de arrastar + ícone na mesma coluna
            left_frame = customtkinter.CTkFrame(container_frame, fg_color="transparent", width=60)
            left_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ns")
            left_frame.grid_propagate(False)

            drag_handle = customtkinter.CTkLabel(
                left_frame,
                text="⋮⋮",
                cursor="hand2",
                font=customtkinter.CTkFont(size=12, weight="bold"),
                text_color=("gray50", "gray60")
            )
            drag_handle.pack(side="left", padx=(5, 2))

            host_icon = customtkinter.CTkLabel(
                left_frame,
                text="🖥️",
                font=customtkinter.CTkFont(size=12)
            )
            host_icon.pack(side="left", padx=(0, 5))

            # Área principal com campos de entrada alinhados aos cabeçalhos
            content_frame = customtkinter.CTkFrame(container_frame, fg_color="transparent")
            content_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
            content_frame.grid_columnconfigure(1, weight=1)

            # Campos de entrada alinhados com os cabeçalhos
            ip_entry = customtkinter.CTkEntry(
                content_frame,
                placeholder_text=host.get('ip', 'Ex: 192.168.1.100'),
                height=28,
                width=140,
                font=customtkinter.CTkFont(family="Consolas", size=11)
            )
            ip_entry.insert(0, host.get('ip', ''))
            ip_entry.grid(row=0, column=0, sticky="w", padx=(0, 5))

            nickname_entry = customtkinter.CTkEntry(
                content_frame,
                placeholder_text=f"Nome para {host.get('name', 'Host')}",
                height=28,
                font=customtkinter.CTkFont(size=11)
            )
            nickname = host.get('nickname', '')
            if nickname:
                nickname_entry.insert(0, nickname)
            nickname_entry.grid(row=0, column=1, sticky="ew", padx=(20, 5))

            # Status indicator no canto direito
            status_frame = customtkinter.CTkFrame(container_frame, fg_color="transparent", width=50)
            status_frame.grid(row=0, column=2, padx=5, pady=5, sticky="ns")
            status_frame.grid_propagate(False)

            status_indicator = customtkinter.CTkLabel(
                status_frame,
                text="●",
                font=customtkinter.CTkFont(size=12),
                text_color=("#27AE60" if i % 2 == 0 else "#E74C3C")
            )
            status_indicator.pack(expand=True)

            container_frame.host_data = host
            container_frame.nickname_entry = nickname_entry
            container_frame.ip_entry = ip_entry
            self.host_frames.append(container_frame)

            # Binds para drag and drop
            drag_handle.bind("<ButtonPress-1>", lambda event, widget=container_frame: self.start_drag(event, widget))
            drag_handle.bind("<B1-Motion>", self.do_drag)
            drag_handle.bind("<ButtonRelease-1>", self.end_drag)

    def start_drag(self, event, widget):
        logging.debug(f"Starting drag for widget: {widget}")
        self.drag_widget = widget
        self.drag_start_y = event.y_root

    def do_drag(self, event):
        if not self.drag_widget:
            logging.debug("do_drag called but no widget is being dragged.")
            return

        self.drag_widget.lift()
        y = self.drag_widget.winfo_y() + (event.y_root - self.drag_start_y)
        
        self.drag_widget.place(y=y, x=0, relwidth=1)
        
        self.drag_start_y = event.y_root

        target_index = -1
        for i, frame in enumerate(self.host_frames):
            if frame is self.drag_widget:
                continue
            
            if self.drag_widget.winfo_y() < frame.winfo_y() + frame.winfo_height() / 2:
                target_index = i
                self.drop_indicator.grid(row=target_index, column=0, sticky="ew", padx=5)
                logging.debug(f"Dragging widget. Potential target index: {target_index}")
                self.drop_indicator.lift()
                break
        else:
            target_index = len(self.host_frames)
            self.drop_indicator.grid(row=target_index, column=0, sticky="ew", padx=5)
            self.drop_indicator.lift()

    def end_drag(self, event):
        logging.debug("Ending drag operation")
        if not self.drag_widget:
            return
        
        self.drop_indicator.grid_forget()
        
        target_index = -1
        for i, frame in enumerate(self.host_frames):
            if frame is self.drag_widget:
                continue
            if self.drag_widget.winfo_y() < frame.winfo_y() + frame.winfo_height() / 2:
                target_index = i
                logging.debug(f"Drag ended. Determined target index: {target_index}")
                break
        
        self.drag_widget.place_forget()
        original_index = self.host_frames.index(self.drag_widget)
        
        dragged_frame = self.host_frames.pop(original_index)
        dragged_data = self.hosts_local_list.pop(original_index)
        
        if target_index != -1:
            if target_index > original_index:
                target_index -= 1
            self.host_frames.insert(target_index, dragged_frame)
            self.hosts_local_list.insert(target_index, dragged_data)
        else:
            self.host_frames.append(dragged_frame)
            self.hosts_local_list.append(dragged_data)

        for i, frame in enumerate(self.host_frames):
            frame.grid(row=i, column=0, sticky="ew", padx=5, pady=4)

        self.drag_widget = None
        logging.debug("Drag operation finished and UI re-gridded.")

    def confirm(self):
        try:
            interval_value = int(self.interval_entry.get())
            logging.debug(f"Confirming settings. Entered interval: {interval_value}, Ask initial info: {bool(self.ask_info_checkbox.get())}")
            if interval_value < 5:
                self.app.show_error(self.app.translate("error_invalid_interval"))
                return
            
            final_hosts_list = []
            for frame in self.host_frames:
                host_data = frame.host_data
                host_data['nickname'] = frame.nickname_entry.get().strip()
                # Atualizar IP se alterado
                new_ip = frame.ip_entry.get().strip()
                if new_ip:
                    host_data['ip'] = new_ip
                final_hosts_list.append(host_data)

            self.result_data = {
                "interval": interval_value,
                "updated_hosts": final_hosts_list,
                "ask_initial_info": bool(self.ask_info_checkbox.get())
            }
            logging.info(f"Tab settings confirmed. Result data: {self.result_data}")
            self.destroy()

        except (ValueError, TypeError):
            self.app.show_error(self.app.translate("error_invalid_interval"))
            logging.warning(f"Invalid interval value entered: {self.interval_entry.get()}")

    def on_close(self, event=None):
        self.result_data = None
        logging.info("Tab settings dialog closed without saving.")
        self.destroy()

    def get_selection(self):
        self.wait()
        return self.result_data