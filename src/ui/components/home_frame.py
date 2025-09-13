# app/ui_components/home_frame.py
# Contém a interface gráfica (widgets) da aba "Início".

import customtkinter
from tkinter import ttk
import logging

class HomeFrame(customtkinter.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        logging.info("Initializing HomeFrame")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Frame de Controles Superior ---
        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_frame.grid_columnconfigure(0, weight=1)

        self.scan_button = customtkinter.CTkButton(controls_frame, text="", command=None)
        self.scan_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.scan_progress_bar = customtkinter.CTkProgressBar(controls_frame, orientation="horizontal")
        self.scan_progress_bar.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="ew")
        self.scan_progress_bar.set(0)
        self.scan_progress_bar.configure(mode="indeterminate")

        self.scan_status_label = customtkinter.CTkLabel(controls_frame, text="", anchor="w")
        self.scan_status_label.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")

        # --- Frame de Resultados (Treeview) ---
        results_frame = customtkinter.CTkFrame(self)
        results_frame.grid(row=1, column=0, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)

        self.tree = self._create_treeview(results_frame)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = customtkinter.CTkScrollbar(results_frame, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # --- Frame de Ações Inferior ---
        actions_frame = customtkinter.CTkFrame(self)
        actions_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        actions_frame.grid_columnconfigure(1, weight=1)
        
        self.add_selected_button = customtkinter.CTkButton(actions_frame, text="", command=self._on_add_selected, state="disabled")
        self.add_selected_button.grid(row=0, column=0, padx=10, pady=10)

        self.filter_entry = customtkinter.CTkEntry(actions_frame, placeholder_text="")
        self.filter_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.filter_entry.bind("<KeyRelease>", self._filter_treeview)

        # Inicialização de estado
        self._is_scanning = False
        self._start_scan_command = None
        self._stop_scan_command = None
        self._add_hosts_command = None
        self.update_language()
        self.update_scan_status(self.app.translate("home_scan_ready"))

    def _apply_appearance_mode(self, color_value):
        """
        Aplica a cor correta baseada no modo de aparência atual.
        Usa cores melhoradas para o tema claro.
        """
        # Se for uma tupla, extrair a cor correta baseada no modo
        if isinstance(color_value, tuple) and len(color_value) == 2:
            current_mode = customtkinter.get_appearance_mode()
            if current_mode.lower() == "light":
                base_color = color_value[0]
            else:
                base_color = color_value[1]
        elif isinstance(color_value, str):
            base_color = color_value
        else:
            # Se não conseguir determinar, usar valor padrão
            return "#FFFFFF"
        
        # Aplicar melhorias se for tema claro
        current_mode = customtkinter.get_appearance_mode()
        if current_mode.lower() == "light":
            # Mapear cores específicas para versões melhoradas
            enhanced_colors = {
                "#EAEAEA": "#FBFBFB",  # Cor de linha alternada mais sutil
                "#F0F0F0": "#F8F9FA",  # Fundo de cabeçalho mais suave
                "gray90": "#FAFAFA",   # Fundo geral mais suave
                "gray80": "#F3F3F3",   # Hover mais sutil
                "gray86": "#F8F9FA",   # Fundo do frame mais suave
                "gray17": "#2B2B2B",   # Para modo escuro
            }
            return enhanced_colors.get(base_color, base_color)
        else:
            return base_color

    def _create_treeview(self, parent):
        try:
            style = ttk.Style()
            style.theme_use("clam")  # Usar tema 'clam'
            bg_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"])
            text_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkLabel"]["text_color"])
            selected_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkButton"]["fg_color"])

            logging.debug(f"HomeFrame _create_treeview colors - bg: {bg_color}, text: {text_color}, selected: {selected_color}")

            style.configure("Treeview", 
                            background=bg_color, 
                            foreground=text_color, 
                            fieldbackground=bg_color, 
                            borderwidth=0,
                            relief="flat")  # Remover borda
            style.map('Treeview', background=[('selected', selected_color)])
            style.configure("Treeview.Heading", 
                            background=bg_color, 
                            foreground=text_color, 
                            relief="flat") # Remover borda do cabeçalho
            style.map("Treeview.Heading", background=[('active', bg_color)])

            tree = ttk.Treeview(parent, columns=("hostname", "ip"), show="headings", style="Treeview")
            tree.heading("hostname", text=self.app.translate("home_col_hostname"))
            tree.heading("ip", text=self.app.translate("home_col_ip"))
            tree.column("hostname", anchor="w", stretch=True)
            tree.column("ip", anchor="w", width=150)
            return tree
            
        except Exception as e:
            logging.error(f"Error creating HomeFrame treeview: {e}")
            # Fallback para treeview básico
            tree = ttk.Treeview(parent, columns=("hostname", "ip"), show="headings")
            tree.heading("hostname", text="Hostname")
            tree.heading("ip", text="IP")
            tree.column("hostname", anchor="w", stretch=True)
            tree.column("ip", anchor="w", width=150)
            return tree

    def update_theme(self):
        """
        Atualiza o tema do componente. Chamado quando o tema da aplicação muda.
        """
        try:
            # Reconfigura estilos do Treeview
            style = ttk.Style()
            style.theme_use("clam")  # Garantir o uso do tema 'clam'
            bg_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"])
            text_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkLabel"]["text_color"])
            selected_color = self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkButton"]["fg_color"])

            logging.debug(f"HomeFrame colors - bg: {bg_color}, text: {text_color}, selected: {selected_color}")

            style.configure("Treeview", 
                            background=bg_color, 
                            foreground=text_color, 
                            fieldbackground=bg_color, 
                            borderwidth=0,
                            relief="flat")  # Remover borda
            style.map('Treeview', background=[('selected', selected_color)])
            style.configure("Treeview.Heading", 
                            background=bg_color, 
                            foreground=text_color, 
                            relief="flat") # Remover borda do cabeçalho
            style.map("Treeview.Heading", background=[('active', bg_color)])
            
            # Atualiza cor do botão scan se necessário
            self.update_scan_button_state()
            
        except Exception as e:
            logging.error(f"Error updating HomeFrame theme: {e}")
            # Fallback silencioso - mantém tema atual

    def set_scan_commands(self, start_command, stop_command):
        self._start_scan_command = start_command
        self._stop_scan_command = stop_command
        logging.debug("Scan commands set in HomeFrame")
        self.scan_button.configure(command=self._toggle_scan)

    def set_add_hosts_command(self, command):
        self._add_hosts_command = command
        logging.debug("Add hosts command set in HomeFrame")

    def _toggle_scan(self):
        if self._is_scanning:
            logging.info("Stopping scan from HomeFrame")
            if self._stop_scan_command:
                self._stop_scan_command()
        else:
            logging.info("Starting scan from HomeFrame")
            if self._start_scan_command:
                self._start_scan_command()

    def _on_add_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return
        
        hosts_to_add = []
        for item_id in selected_items:
            item = self.tree.item(item_id)
            hosts_to_add.append({'name': item['values'][0], 'ip': item['values'][1]})
        logging.info(f"Adding {len(hosts_to_add)} selected hosts from HomeFrame")
            
        if self._add_hosts_command:
            self._add_hosts_command(hosts_to_add)

    def on_scan_finished(self):
        logging.info("Scan finished in HomeFrame")
        self._is_scanning = False
        self.scan_progress_bar.stop()
        self.scan_progress_bar.set(0)
        self.update_scan_button_state()
        self.add_selected_button.configure(state="normal" if self.tree.get_children() else "disabled")

    def update_scan_status(self, text):
        logging.debug(f"Updating scan status: {text}")
        self.scan_status_label.configure(text=text)
        if "Varrendo" in text or "Scanning" in text or "Escaneando" in text:
            if not self._is_scanning:
                self._is_scanning = True
                self.scan_progress_bar.start()
                self.update_scan_button_state()
                self.add_selected_button.configure(state="disabled")

    def update_scan_button_state(self):
        if self._is_scanning:
            logging.debug("Setting scan button state to 'Stop'")
            self.scan_button.configure(text=self.app.translate("scanner_stop_scan"), fg_color="red")
        else:
            logging.debug("Setting scan button state to 'Start'")
            # Usa a cor padrão do CustomTkinter para o botão
            self.scan_button.configure(text=self.app.translate("scanner_local_scan"), fg_color=self._apply_appearance_mode(customtkinter.ThemeManager.theme["CTkButton"]["fg_color"]))
    
    def add_host_to_treeview(self, host_info):
        logging.debug(f"Adding host to treeview: Hostname={host_info.get('hostname')}, IP={host_info.get('ip')}")
        self.tree.insert("", "end", values=(host_info['hostname'], host_info['ip']))

    def clear_scan_results(self):
        logging.debug("Clearing scan results in HomeFrame treeview")
        for item in self.tree.get_children():
            self.tree.delete(item)
    def _filter_treeview(self, event=None):
        filter_text = self.filter_entry.get().lower()
        for item_id in self.tree.get_children():
            item_values = self.tree.item(item_id, "values")
            hostname = item_values[0].lower()
            ip = item_values[1].lower()
            if filter_text in hostname or filter_text in ip:
                logging.debug(f"Applying filter '{filter_text}', showing item: {item_values}")
                # Re-insere o item para torná-lo visível se estava oculto
                self.tree.reattach(item_id, '', 'end')
            else:
                # Oculta o item
                self.tree.detach(item_id)

    def update_language(self):
        logging.debug("Updating language in HomeFrame")
        self.tree.heading("hostname", text=self.app.translate("home_col_hostname"))
        self.tree.heading("ip", text=self.app.translate("home_col_ip"))
        self.update_scan_button_state()
        self.add_selected_button.configure(text=self.app.translate("scanner_add_selected"))
        self.filter_entry.configure(placeholder_text=self.app.translate("scanner_filter_placeholder"))