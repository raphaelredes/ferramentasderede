# app/ui_components/services_frame.py
# Frame orquestrador para gerenciar e exibir serviços remotos.

import customtkinter
import os
from datetime import datetime
from .service_manager.data_manager import ServiceDataManager
from .service_manager.service_widget import ServiceWidget

class ServicesFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.host = host
        self.tool_controller = tool_controller
        
        self.current_page = 1
        self.items_per_page = 20
        
        # Cache de widgets para reutilização
        self.widget_pool = []
        self.active_widgets = []
        self.widget_data_cache = {}
        
        # Cache de tema para evitar múltiplas chamadas
        self.cached_theme_colors = None
        self.last_theme_mode = None
        
        # Debounce para filtro
        self.filter_timer = None
        
        cache_path = os.path.join(self.app.base_dir, "cache", "services", f"{self.host['ip'].replace('.', '_')}.json")
        self.data_manager = ServiceDataManager(cache_path)

        self._create_layout()
        self.after(100, self.initial_load)
        self.update_language()

    def _create_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(2, weight=1)

        self.refresh_button = customtkinter.CTkButton(controls_frame, text="", command=self.refresh_services_from_remote)
        self.refresh_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.last_updated_label = customtkinter.CTkLabel(controls_frame, text="", text_color="white", font=customtkinter.CTkFont(size=11))
        self.last_updated_label.grid(row=0, column=1, padx=(5, 10), pady=5, sticky="w")
        
        self.filter_entry = customtkinter.CTkEntry(controls_frame, placeholder_text="")
        self.filter_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        self.filter_entry.bind("<KeyRelease>", self.filter_services_debounced)

        self.list_frame = customtkinter.CTkScrollableFrame(self, fg_color=("gray85", "gray17"))
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 5))

        pagination_frame = customtkinter.CTkFrame(self)
        pagination_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        pagination_frame.grid_columnconfigure(2, weight=1)

        # Botão primeira página
        self.first_button = customtkinter.CTkButton(pagination_frame, text="", command=self.first_page, width=80)
        self.first_button.grid(row=0, column=0, padx=5, pady=5)
        
        # Botão página anterior
        self.prev_button = customtkinter.CTkButton(pagination_frame, text="", command=self.prev_page, width=80)
        self.prev_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Label da página atual
        self.page_label = customtkinter.CTkLabel(pagination_frame, text="")
        self.page_label.grid(row=0, column=2, padx=5, pady=5)
        
        # Botão próxima página
        self.next_button = customtkinter.CTkButton(pagination_frame, text="", command=self.next_page, width=80)
        self.next_button.grid(row=0, column=3, padx=5, pady=5)
        
        # Botão última página
        self.last_button = customtkinter.CTkButton(pagination_frame, text="", command=self.last_page, width=80)
        self.last_button.grid(row=0, column=4, padx=5, pady=5)

    def initial_load(self):
        if not self.data_manager.load_from_cache():
            self._clear_list_frame()
            msg = customtkinter.CTkLabel(self.list_frame, text=self.app.translate("service_click_refresh"))
            msg.pack(pady=20)
            self._update_pagination_controls(0, 0)
            self._update_last_updated_label()
        else:
            self.render_page(1)
            self._update_last_updated_label(self.data_manager.get_last_update_time())


    def refresh_services_from_remote(self):
        self._clear_list_frame()
        loading_label = customtkinter.CTkLabel(self.list_frame, text=self.app.translate("service_loading_remote"))
        loading_label.pack(pady=20)
        self._update_pagination_controls(0, 0, is_loading=True)
        self.tool_controller.get_services(self.process_remote_data)

    def process_remote_data(self, services_data):
        self.data_manager.set_data(services_data)
        if "error" not in services_data:
            self.data_manager.save_to_cache()
            self._update_last_updated_label(self.data_manager.get_last_update_time())
        else:
            self._update_last_updated_label(self.data_manager.get_last_update_time())

        self.filter_entry.delete(0, "end")
        self.render_page(1)

    def _update_last_updated_label(self, timestamp_dt=None):
        if timestamp_dt and isinstance(timestamp_dt, datetime):
            formatted_time = timestamp_dt.strftime("%d/%m/%Y %H:%M:%S")
            self.last_updated_label.configure(text=self.app.translate("last_updated_label", datetime=formatted_time))
        else:
            self.last_updated_label.configure(text="")

    def _get_theme_colors(self):
        """Cache de cores do tema para evitar múltiplas chamadas."""
        current_mode = customtkinter.get_appearance_mode().lower()
        
        if self.cached_theme_colors is None or self.last_theme_mode != current_mode:
            self.last_theme_mode = current_mode
            if current_mode == "light":
                self.cached_theme_colors = {
                    "running": "#107C10",
                    "stopped": "#D13438",
                    "start_fg": "#107C10",
                    "start_hover": "#0F6E0F",
                    "stop_fg": "#D13438",
                    "stop_hover": "#B52D30"
                }
            else:
                self.cached_theme_colors = {
                    "running": "#2ECC71",
                    "stopped": "#E74C3C",
                    "start_fg": "#2ECC71",
                    "start_hover": "#27AE60",
                    "stop_fg": "#E74C3C",
                    "stop_hover": "#C0392B"
                }
        
        return self.cached_theme_colors

    def filter_services_debounced(self, event=None):
        """Filtro com debounce para melhor performance."""
        if self.filter_timer:
            self.after_cancel(self.filter_timer)
        
        self.filter_timer = self.after(300, self.filter_services)  # 300ms debounce

    def filter_services(self, event=None):
        self.data_manager.filter(self.filter_entry.get())
        self.render_page_optimized(1)

    def render_page_optimized(self, page_number):
        """Versão otimizada com reutilização de widgets."""
        page_items, self.current_page, total_pages = self.data_manager.get_page(page_number, self.items_per_page)

        # Esconder widgets ativos desnecessários
        for widget in self.active_widgets[len(page_items):]:
            widget.pack_forget()

        if not page_items:
            # Esconder todos os widgets e mostrar mensagem
            for widget in self.active_widgets:
                widget.pack_forget()
                
            message_data = self.data_manager.current_view
            if isinstance(message_data, dict) and "error" in message_data:
                msg_text = message_data["error"]
            elif not self.data_manager.all_services:
                 msg_text = self.app.translate("service_click_refresh_short")
            else:
                msg_text = self.app.translate("service_no_services_found")
            
            if not hasattr(self, 'msg_label') or not self.msg_label.winfo_exists():
                self.msg_label = customtkinter.CTkLabel(self.list_frame, text="", wraplength=400)
            
            self.msg_label.configure(text=msg_text)
            self.msg_label.pack(pady=20)
        else:
            # Esconder mensagem se existir
            if hasattr(self, 'msg_label') and self.msg_label.winfo_exists():
                self.msg_label.pack_forget()
            
            # Reutilizar widgets existentes ou criar novos
            theme_colors = self._get_theme_colors()
            
            for i, item_data in enumerate(page_items):
                if i < len(self.active_widgets):
                    # Reutilizar widget existente
                    self._update_service_widget(self.active_widgets[i], item_data, theme_colors)
                    self.active_widgets[i].pack(fill="x", pady=2, padx=2)
                else:
                    # Criar novo widget otimizado
                    widget = self._create_optimized_service_widget(item_data, theme_colors)
                    self.active_widgets.append(widget)

        self._update_pagination_controls(self.current_page, total_pages)

    def render_page(self, page_number):
        """Método original mantido para compatibilidade."""
        return self.render_page_optimized(page_number)
        
    def _update_pagination_controls(self, current, total, is_loading=False):
        if is_loading or total == 0:
            self.page_label.configure(text="")
            self.first_button.configure(state="disabled")
            self.prev_button.configure(state="disabled")
            self.next_button.configure(state="disabled")
            self.last_button.configure(state="disabled")
        else:
            self.page_label.configure(text=f"{self.app.translate('label_page')} {current} {self.app.translate('label_of')} {total}")
            
            # Primeira página - sempre habilitado se não estiver na primeira
            self.first_button.configure(state="normal" if current > 1 else "disabled")
            
            # Página anterior - sempre habilitado se não estiver na primeira
            self.prev_button.configure(state="normal" if current > 1 else "disabled")
            
            # Próxima página - sempre habilitado se não estiver na última
            self.next_button.configure(state="normal" if current < total else "disabled")
            
            # Última página - sempre habilitado se não estiver na última
            self.last_button.configure(state="normal" if current < total else "disabled")

    def _clear_list_frame(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

    def _create_optimized_service_widget(self, service_data, theme_colors):
        """Cria um widget de serviço otimizado."""
        widget = customtkinter.CTkFrame(self.list_frame)
        widget.grid_columnconfigure(0, weight=1)
        
        name = service_data.get("Name")
        display_name = service_data.get("DisplayName")
        
        status_obj = service_data.get("Status")
        is_running = (isinstance(status_obj, str) and status_obj == "Running") or \
                     (isinstance(status_obj, int) and status_obj == 4)
        status_str = "Running" if is_running else "Stopped"
        status_color = theme_colors["running"] if is_running else theme_colors["stopped"]
        
        # Widgets internos
        info_label = customtkinter.CTkLabel(widget, text=f"{display_name}\n({name})", justify="left", anchor="w")
        info_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        status_label = customtkinter.CTkLabel(widget, text=status_str, text_color=status_color, font=("", 12, "bold"))
        status_label.grid(row=0, column=1, padx=10, pady=5)

        button_frame = customtkinter.CTkFrame(widget, fg_color="transparent")
        button_frame.grid(row=0, column=2, padx=10, pady=5)
            
        start_btn = customtkinter.CTkButton(button_frame, text="Iniciar", width=60,
                                          command=lambda: self.handle_service_action(name, "start"),
                                          fg_color=theme_colors["start_fg"],
                                          hover_color=theme_colors["start_hover"],
                                          text_color="white")
        start_btn.pack(side="left", padx=2)
        
        stop_btn = customtkinter.CTkButton(button_frame, text="Parar", width=60,
                                         command=lambda: self.handle_service_action(name, "stop"),
                                         fg_color=theme_colors["stop_fg"],
                                         hover_color=theme_colors["stop_hover"],
                                         text_color="white")
        stop_btn.pack(side="left", padx=2)
        
        restart_btn = customtkinter.CTkButton(button_frame, text="Reiniciar", width=70,
                                            command=lambda: self.handle_service_action(name, "restart"),
                                            text_color="white")
        restart_btn.pack(side="left", padx=2)
        
        # Estados dos botões
        if is_running:
            start_btn.configure(state="disabled", text_color="white")
        else:
            stop_btn.configure(state="disabled", text_color="white")
            restart_btn.configure(state="disabled", text_color="white")
            restart_btn.configure(state="disabled")
        
        # Armazenar referências para atualização
        widget._info_label = info_label
        widget._status_label = status_label
        widget._start_btn = start_btn
        widget._stop_btn = stop_btn
        widget._restart_btn = restart_btn
        widget._service_name = name
        
        widget.pack(fill="x", pady=2, padx=2)
        return widget

    def _update_service_widget(self, widget, service_data, theme_colors):
        """Atualiza um widget existente com novos dados."""
        name = service_data.get("Name")
        display_name = service_data.get("DisplayName")
        
        status_obj = service_data.get("Status")
        is_running = (isinstance(status_obj, str) and status_obj == "Running") or \
                     (isinstance(status_obj, int) and status_obj == 4)
        status_str = "Running" if is_running else "Stopped"
        status_color = theme_colors["running"] if is_running else theme_colors["stopped"]
        
        # Atualizar textos
        widget._info_label.configure(text=f"{display_name}\n({name})")
        widget._status_label.configure(text=status_str, text_color=status_color)
        
        # Atualizar comandos dos botões
        widget._start_btn.configure(command=lambda: self.handle_service_action(name, "start"))
        widget._stop_btn.configure(command=lambda: self.handle_service_action(name, "stop"))
        widget._restart_btn.configure(command=lambda: self.handle_service_action(name, "restart"))
        
        # Atualizar cores dos botões
        widget._start_btn.configure(fg_color=theme_colors["start_fg"], hover_color=theme_colors["start_hover"])
        widget._stop_btn.configure(fg_color=theme_colors["stop_fg"], hover_color=theme_colors["stop_hover"])
        
        # Estados dos botões
        if is_running:
            widget._start_btn.configure(state="disabled")
            widget._stop_btn.configure(state="normal")
            widget._restart_btn.configure(state="normal")
        else: 
            widget._start_btn.configure(state="normal")
            widget._stop_btn.configure(state="disabled")
            widget._restart_btn.configure(state="disabled")
        
        widget._service_name = name

    def first_page(self):
        """Vai para a primeira página."""
        self.render_page_optimized(1)

    def last_page(self):
        """Vai para a última página."""
        page_items, _, total_pages = self.data_manager.get_page(1, self.items_per_page)
        if total_pages > 0:
            self.render_page_optimized(total_pages)

    def next_page(self):
        self.render_page_optimized(self.current_page + 1)

    def prev_page(self):
        self.render_page_optimized(self.current_page - 1)

    def handle_service_action(self, service_name, action):
        self.tool_controller.manage_service(service_name, action, self.update_service_status_after_action)

    def update_service_status_after_action(self, service_name, service_data, status_changed):
        self.data_manager.update_service_in_cache(service_name, service_data)
        if not status_changed:
            self.app.show_info(self.app.translate("service_status_unchanged_message"))
        self.data_manager.filter(self.filter_entry.get())
        self.render_page_optimized(self.current_page)
        self._update_last_updated_label(self.data_manager.get_last_update_time())
        
    def update_language(self):
        self.refresh_button.configure(text=self.app.translate("service_refresh"))
        self.filter_entry.configure(placeholder_text=self.app.translate("service_filter_placeholder"))
        
        # Botões de paginação com texto
        self.first_button.configure(text=self.app.translate("pagination_first") if hasattr(self.app, 'translate') and self.app.translate("pagination_first") != "pagination_first" else "Primeira")
        self.prev_button.configure(text=self.app.translate("pagination_prev") if hasattr(self.app, 'translate') and self.app.translate("pagination_prev") != "pagination_prev" else "Anterior")
        self.next_button.configure(text=self.app.translate("pagination_next") if hasattr(self.app, 'translate') and self.app.translate("pagination_next") != "pagination_next" else "Próxima")
        self.last_button.configure(text=self.app.translate("pagination_last") if hasattr(self.app, 'translate') and self.app.translate("pagination_last") != "pagination_last" else "Última")
        
        self._update_last_updated_label(self.data_manager.get_last_update_time())
        # Invalidar cache de cores para re-render com idioma correto
        self.cached_theme_colors = None
        if self.data_manager.all_services:
            self.render_page_optimized(self.current_page)