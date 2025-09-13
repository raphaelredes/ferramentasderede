# app/ui_components/host_tab_manager/home_tab_manager.py
# Gerencia a criação e a lógica da interface da aba "Home" e suas sub-abas.

import customtkinter
import ipaddress
from ..context_menu import TerminalContextMenu
from ..tool_controllers.network_tool_controller import NetworkToolController
from ..tool_controllers.home_scanner_controller import HomeScannerController # Nova importação
from src.network.discovery import DiscoveryScanner

class HomeTabManager:
    def __init__(self, parent_tab, app, host_tab_view):
        self.parent_tab = parent_tab
        self.app = app
        self.host_tab_view = host_tab_view

        self.home_tool_controller = NetworkToolController(self.app, host={'ip': ''}, hostname='')
        self.home_scanner_controller = HomeScannerController(self.app) # Novo controlador
        
        self.scanner_checkbox_widgets = {}
        self.scanner_domain_groups = {}
        self.scanner_all_found_hosts = []
        self.scanner = DiscoveryScanner(app, callbacks={
            'on_status_update': self._update_scanner_status,
            'on_host_found': self._add_host_to_scanner_results,
            'on_scan_finished': self._on_scan_finished
        })

        self._create_widgets()

    # ... (O resto do arquivo, exceto _start_remote_scan, permanece o mesmo)
    def _create_widgets(self):
        self.parent_tab.grid_columnconfigure(0, weight=1)
        self.parent_tab.grid_rowconfigure(0, weight=1)
        home_tab_view = customtkinter.CTkTabview(self.parent_tab, anchor="center")
        home_tab_view.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ping_tab = home_tab_view.add(self.app.translate("home_tab_ping"))
        traceroute_tab = home_tab_view.add(self.app.translate("home_tab_traceroute"))
        scanner_tab = home_tab_view.add(self.app.translate("home_tab_scanner"))
        self._create_home_ping_tab(ping_tab)
        self._create_home_traceroute_tab(traceroute_tab)
        self._create_home_scanner_tab(scanner_tab)
        self.home_tool_controller.set_state_change_callback(self.update_home_buttons_state)
        self.update_home_buttons_state()

    def _create_home_ping_tab(self, parent_tab):
        parent_tab.grid_columnconfigure(0, weight=1)
        parent_tab.grid_rowconfigure(2, weight=1)  # Ajustar para acomodar widget de status
        
        # Configurar widget de status de comando
        status_widget = self.home_tool_controller.setup_command_status_widget(parent_tab)
        if status_widget:
            status_widget.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        
        controls_frame = customtkinter.CTkFrame(parent_tab)
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))
        controls_frame.grid_columnconfigure(0, weight=1)
        self.home_ping_target_entry = customtkinter.CTkEntry(controls_frame, placeholder_text=self.app.translate("home_ping_placeholder"))
        self.home_ping_target_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.home_ping_target_entry.bind("<Return>", lambda event: self.toggle_home_ping())
        packet_size_frame = customtkinter.CTkFrame(controls_frame, fg_color="transparent")
        packet_size_frame.grid(row=0, column=1, padx=5, pady=10)
        packet_size_label = customtkinter.CTkLabel(packet_size_frame, text=self.app.translate("ping_size"))
        packet_size_label.pack(side="left", padx=(0, 5))
        self.home_packet_size_entry = customtkinter.CTkEntry(packet_size_frame, width=60, placeholder_text="32")
        self.home_packet_size_entry.pack(side="left")
        self.home_packet_size_entry.bind("<Return>", lambda event: self.toggle_home_ping())
        self.home_ping_button = customtkinter.CTkButton(controls_frame, text="", command=self.toggle_home_ping)
        self.home_ping_button.grid(row=0, column=2, padx=(5, 10), pady=10)
        self.home_ping_output_textbox = customtkinter.CTkTextbox(parent_tab, font=("Consolas", 12))
        self.home_ping_output_textbox.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.home_ping_output_textbox.configure(state="disabled")
        TerminalContextMenu(self.app, self.home_ping_output_textbox)

    def _create_home_traceroute_tab(self, parent_tab):
        parent_tab.grid_columnconfigure(0, weight=1)
        parent_tab.grid_rowconfigure(2, weight=1)  # Ajustar para acomodar widget de status
        
        # Configurar widget de status de comando
        status_widget = self.home_tool_controller.setup_command_status_widget(parent_tab)
        if status_widget:
            status_widget.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        
        controls_frame = customtkinter.CTkFrame(parent_tab)
        controls_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))
        controls_frame.grid_columnconfigure(0, weight=1)
        self.home_traceroute_target_entry = customtkinter.CTkEntry(controls_frame, placeholder_text=self.app.translate("home_traceroute_placeholder"))
        self.home_traceroute_target_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.home_traceroute_target_entry.bind("<Return>", lambda event: self.toggle_home_traceroute())
        self.home_traceroute_button = customtkinter.CTkButton(controls_frame, text="", command=self.toggle_home_traceroute)
        self.home_traceroute_button.grid(row=0, column=1, padx=(5, 10), pady=10)
        self.home_traceroute_output_textbox = customtkinter.CTkTextbox(parent_tab, font=("Consolas", 12))
        self.home_traceroute_output_textbox.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.home_traceroute_output_textbox.configure(state="disabled")
        TerminalContextMenu(self.app, self.home_traceroute_output_textbox)

    def toggle_home_ping(self):
        target = self.home_ping_target_entry.get()
        running_cmd = getattr(self.home_tool_controller, 'running_command', None)
        
        import logging
        logging.info(f"toggle_home_ping chamado - target: {target}, running_cmd: {running_cmd}")
        
        if running_cmd == f"ping_{target}" or (running_cmd and running_cmd.startswith("ping_")):
            self.home_tool_controller.stop_command()
            logging.info("Parando comando ping")
        else:
            packet_size = self.home_packet_size_entry.get()
            logging.info(f"Iniciando ping para {target} com packet_size {packet_size}")
            self.home_tool_controller.start_standalone_ping(target, packet_size, self.home_ping_output_textbox)
        
        # Forçar atualização imediata dos botões para feedback visual
        self.update_home_buttons_state()
    
    def toggle_home_traceroute(self):
        target = self.home_traceroute_target_entry.get()
        running_cmd = getattr(self.home_tool_controller, 'running_command', None)
        
        import logging
        logging.info(f"toggle_home_traceroute chamado - target: {target}, running_cmd: {running_cmd}")
        
        if running_cmd == f"traceroute_{target}" or (running_cmd and running_cmd.startswith("traceroute_")):
            self.home_tool_controller.stop_command()
            logging.info("Parando comando traceroute")
        else:
            logging.info(f"Iniciando traceroute para {target}")
            self.home_tool_controller.start_standalone_traceroute(target, self.home_traceroute_output_textbox)
        
        # Forçar atualização imediata dos botões para feedback visual
        self.update_home_buttons_state()

    def update_home_buttons_state(self, status_data=None):
        """Atualiza estado dos botões baseado no comando atual
        Args:
            status_data: Dados de status do callback (opcional) - {'running': bool, 'command': str}
        """
        import logging
        
        cmd = self.home_tool_controller.running_command
        is_running = self.home_tool_controller.is_running
        ping_running = cmd and cmd.startswith("ping_")
        traceroute_running = cmd and cmd.startswith("traceroute_")
        
        # Log detalhado para debug
        logging.info(f"HomeTabManager.update_home_buttons_state chamado:")
        logging.info(f"  - status_data: {status_data}")
        logging.info(f"  - controller.running_command: {cmd}")
        logging.info(f"  - controller.is_running: {is_running}")
        logging.info(f"  - ping_running: {ping_running}")
        logging.info(f"  - traceroute_running: {traceroute_running}")
        
        # Configurar botão ping
        if ping_running:
            self.home_ping_button.configure(
                text=self.app.translate("ping_scan_stop"), 
                state="normal",
                fg_color="#E74C3C"  # Vermelho para indicar "parar"
            )
        else:
            # Resetar para cor padrão - usar método diferente
            self.home_ping_button.configure(
                text=self.app.translate("ping_scan_start"), 
                state="disabled" if traceroute_running else "normal"
            )
            # Resetar cor padrão
            try:
                self.home_ping_button.configure(fg_color=("gray75", "gray25"))  # Cor padrão do CTkButton
            except:
                pass  # Se falhar, manter cor atual
            
        # Configurar botão traceroute
        if traceroute_running:
            self.home_traceroute_button.configure(
                text=self.app.translate("ping_scan_stop"), 
                state="normal",
                fg_color="#E74C3C"  # Vermelho para indicar "parar"
            )
        else:
            self.home_traceroute_button.configure(
                text=self.app.translate("traceroute_start"), 
                state="disabled" if ping_running else "normal"
            )
            # Resetar cor padrão
            try:
                self.home_traceroute_button.configure(fg_color=("gray75", "gray25"))  # Cor padrão do CTkButton
            except:
                pass  # Se falhar, manter cor atual

    def _create_home_scanner_tab(self, parent_tab):
        parent_tab.grid_columnconfigure(0, weight=1)
        parent_tab.grid_rowconfigure(1, weight=1)
        top_frame = customtkinter.CTkFrame(parent_tab)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_frame.grid_columnconfigure(0, weight=1)
        self.scanner_status_label = customtkinter.CTkLabel(top_frame, text=self.app.translate("scanner_ready"), anchor="w")
        self.scanner_status_label.pack(fill="x", padx=10, pady=(5, 5))
        self.scanner_progressbar = customtkinter.CTkProgressBar(top_frame, mode="indeterminate")
        self.scanner_progressbar.pack(fill="x", expand=True, padx=10, pady=(0, 5))
        self.scanner_progressbar.set(0)
        main_container = customtkinter.CTkFrame(parent_tab, fg_color="transparent")
        main_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_container.grid_columnconfigure(0, weight=1, minsize=350)
        main_container.grid_columnconfigure(1, weight=3)
        main_container.grid_rowconfigure(0, weight=1)
        controls_frame = customtkinter.CTkFrame(main_container)
        controls_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        scan_type_tabs = customtkinter.CTkTabview(controls_frame, anchor="center")
        scan_type_tabs.pack(fill="x", expand=False, padx=10, pady=10)
        self._populate_scanner_control_tabs(scan_type_tabs)
        results_frame = customtkinter.CTkFrame(main_container)
        results_frame.grid(row=0, column=1, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(2, weight=1)
        self.scanner_filter_entry = customtkinter.CTkEntry(results_frame, placeholder_text=self.app.translate("scanner_filter_placeholder"))
        self.scanner_filter_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.scanner_filter_entry.bind("<KeyRelease>", self._filter_scanner_results)
        self.scanner_add_button = customtkinter.CTkButton(results_frame, text=self.app.translate("scanner_add_selected"), command=self._confirm_scanner_selection, state="disabled")
        self.scanner_add_button.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.scanner_results_tabs = customtkinter.CTkTabview(results_frame, anchor="w")
        self.scanner_results_tabs.grid(row=2, column=0, sticky="nsew", pady=5, padx=5)
        self._show_scanner_placeholder_tab(self.app.translate("scan_placeholder_tab"))

    def _populate_scanner_control_tabs(self, tab_view):
        local_tab, remote_tab, custom_tab = tab_view.add(self.app.translate("scanner_tab_local")), tab_view.add(self.app.translate("scanner_tab_remote")), tab_view.add(self.app.translate("scanner_tab_custom"))
        local_tab.grid_columnconfigure(0, weight=1)
        self.local_scan_button = customtkinter.CTkButton(local_tab, text=self.app.translate("scanner_local_scan"), command=self._start_local_scan)
        self.local_scan_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        remote_tab.grid_columnconfigure(0, weight=1)
        host_names = [self.host_tab_view._get_display_name(h) for h in self.app.favorites]
        remote_label = customtkinter.CTkLabel(remote_tab, text=self.app.translate("scanner_remote_select_host"))
        remote_label.grid(row=0, column=0, padx=10, pady=(10,0), sticky="w")
        self.remote_host_combo = customtkinter.CTkComboBox(remote_tab, values=host_names, state="readonly" if host_names else "disabled")
        self.remote_host_combo.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        if host_names: self.remote_host_combo.set(host_names[0])
        self.remote_scan_button = customtkinter.CTkButton(remote_tab, text=self.app.translate("scanner_remote_scan"), command=self._start_remote_scan, state="normal" if host_names else "disabled")
        self.remote_scan_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        custom_tab.grid_columnconfigure(1, weight=1)
        net_label, self.network_entry = customtkinter.CTkLabel(custom_tab, text=self.app.translate("scanner_custom_net_address")), customtkinter.CTkEntry(custom_tab, placeholder_text="192.168.0.0")
        net_label.grid(row=0, column=0, padx=(10,5), pady=(10,0)); self.network_entry.grid(row=0, column=1, padx=(0, 10), pady=(10, 5), sticky="ew")
        mask_label, self.mask_entry = customtkinter.CTkLabel(custom_tab, text=self.app.translate("scanner_custom_subnet_mask")), customtkinter.CTkEntry(custom_tab, placeholder_text="255.255.255.0")
        mask_label.grid(row=1, column=0, padx=(10,5), pady=5); self.mask_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")
        self.custom_scan_button = customtkinter.CTkButton(custom_tab, text=self.app.translate("scanner_custom_scan"), command=self._start_custom_scan)
        self.custom_scan_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    def _prepare_for_scan(self):
        self._clear_scanner_results(); self._set_scanner_buttons_state(is_scanning=True)
        self.scanner_add_button.configure(state="disabled"); self.scanner_progressbar.start()

    def _start_local_scan(self):
        self._prepare_for_scan(); self.scanner.start_scan("local")

    def _start_remote_scan(self):
        host_name = self.remote_host_combo.get()
        if not host_name: return
        target_host = next((h for h in self.app.favorites if self.host_tab_view._get_display_name(h) == host_name), None)
        if not target_host: return
        
        # USA O NOVO CONTROLADOR PARA OBTER CREDENCIAIS
        username, password = self.home_scanner_controller.get_credentials_for_remote_scan(target_host)
        if not username: return
        
        self._prepare_for_scan()
        remote_info = {**target_host, "username": username, "password": password}
        self.scanner.start_scan("remote", remote_host_info=remote_info)

    def _start_custom_scan(self):
        try:
            network = ipaddress.IPv4Network(f"{self.network_entry.get()}/{self.mask_entry.get()}", strict=False)
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            self.app.show_error(self.app.translate("error_net_address_invalid"))
            return
        self._prepare_for_scan(); self.scanner.start_scan("custom", scan_target=network)

    def _on_scan_finished(self):
        if not self.parent_tab.winfo_exists(): return
        self.scanner_progressbar.stop(); self.scanner_progressbar.set(1)
        self._set_scanner_buttons_state(is_scanning=False)

    def _set_scanner_buttons_state(self, is_scanning):
        stop_text = self.app.translate("scanner_stop_scan")
        if is_scanning:
            self.local_scan_button.configure(text=stop_text, command=self.scanner.stop_scan)
            self.remote_scan_button.configure(text=stop_text, command=self.scanner.stop_scan)
            self.custom_scan_button.configure(text=stop_text, command=self.scanner.stop_scan)
        else:
            self.local_scan_button.configure(text=self.app.translate("scanner_local_scan"), command=self._start_local_scan)
            self.remote_scan_button.configure(text=self.app.translate("scanner_remote_scan"), command=self._start_remote_scan)
            self.custom_scan_button.configure(text=self.app.translate("scanner_custom_scan"), command=self._start_custom_scan)

    def _update_scanner_status(self, text):
        if not self.parent_tab.winfo_exists(): return
        self.scanner_status_label.configure(text=text)

    def _add_host_to_scanner_results(self, host_data):
        if not self.parent_tab.winfo_exists(): return
        ip = host_data['ip']
        if ip in self.scanner_checkbox_widgets: return
        if not self.scanner_domain_groups:
            try: self.scanner_results_tabs.delete(self.app.translate("scan_placeholder_tab"))
            except: pass
        self.scanner_all_found_hosts.append(host_data)
        self.scanner_all_found_hosts.sort(key=lambda x: ipaddress.IPv4Address(x['ip']))
        hostname = host_data.get('hostname', ip)
        domain = self._extract_scanner_domain(hostname)
        if domain not in self.scanner_domain_groups:
            new_tab = self.scanner_results_tabs.add(domain)
            scroll_frame = customtkinter.CTkScrollableFrame(new_tab); scroll_frame.pack(fill="both", expand=True)
            self.scanner_domain_groups[domain] = scroll_frame
        container, display_name = self.scanner_domain_groups[domain], hostname.split('.')[0]
        checkbox_text = f"{display_name} ({ip})" if hostname != ip else ip
        checkbox = customtkinter.CTkCheckBox(container, text=checkbox_text); checkbox.pack(padx=10, pady=5, anchor="w", fill="x")
        self.scanner_checkbox_widgets[ip] = checkbox; self.scanner_add_button.configure(state="normal")

    def _extract_scanner_domain(self, hostname):
        default = self.app.translate("default_domain_name")
        try:
            ipaddress.ip_address(hostname); return default
        except ValueError: pass
        if '.' in hostname:
            parts = hostname.split('.', 1)
            if len(parts) > 1 and any(c.isalpha() for c in parts[1]): return parts[1].upper()
        return default
        
    def _filter_scanner_results(self, event=None):
        term = self.scanner_filter_entry.get().lower()
        for ip, cb in self.scanner_checkbox_widgets.items():
            if cb.winfo_exists():
                cb.pack_forget();
                if term in cb.cget("text").lower(): cb.pack(padx=10, pady=5, anchor="w", fill="x")

    def _clear_scanner_results(self):
        for widget in self.scanner_checkbox_widgets.values():
            if widget.winfo_exists(): widget.destroy()
        for name in list(self.scanner_domain_groups.keys()):
            if self.scanner_results_tabs.winfo_exists():
                try: self.scanner_results_tabs.delete(name)
                except: pass
        self.scanner_domain_groups.clear(); self.scanner_checkbox_widgets.clear(); self.scanner_all_found_hosts.clear()
        self._show_scanner_placeholder_tab(self.app.translate("scan_placeholder_tab"))

    def _show_scanner_placeholder_tab(self, text):
        placeholder_text = self.app.translate("scan_placeholder_tab")
        if placeholder_text not in self.scanner_results_tabs._name_list:
            placeholder_tab = self.scanner_results_tabs.add(placeholder_text)
            label = customtkinter.CTkLabel(placeholder_tab, text=text, text_color="gray50"); label.pack(expand=True)
            self.scanner_results_tabs.set(placeholder_text)

    def _confirm_scanner_selection(self):
        selected_hosts = []
        for ip, cb in self.scanner_checkbox_widgets.items():
            if cb.winfo_ismapped() and cb.get() == 1:
                text = cb.cget("text")
                hostname_part, ip_from_text = (text.replace(")", "").split(" (") if " (" in text else (text, text))
                original = next((h for h in self.scanner_all_found_hosts if h['ip'] == ip_from_text), None)
                full_hostname = original.get('hostname', hostname_part) if original else hostname_part
                selected_hosts.append({"name": full_hostname, "ip": ip_from_text}); cb.deselect()
        self.app.controller.add_discovered_hosts(selected_hosts)

    def update_language(self):
        if hasattr(self, 'home_ping_target_entry'):
            self.home_ping_target_entry.configure(placeholder_text=self.app.translate("home_ping_placeholder"))
            packet_size_frame = self.home_ping_target_entry.master.winfo_children()[1]
            packet_size_label = packet_size_frame.winfo_children()[0]
            packet_size_label.configure(text=self.app.translate("ping_size"))
        if hasattr(self, 'home_traceroute_target_entry'):
            self.home_traceroute_target_entry.configure(placeholder_text=self.app.translate("home_traceroute_placeholder"))
        self.update_home_buttons_state()