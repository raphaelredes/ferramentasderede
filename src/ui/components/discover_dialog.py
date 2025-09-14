# app/ui_components/discover_dialog.py
# Janela para escanear a rede, com sub-abas para agrupar resultados por domínio.

import customtkinter
import ipaddress
import os
import json
try:
    from ...config.settings import DISCOVERY_CACHE_FILE
except ImportError:
    from src.config.settings import DISCOVERY_CACHE_FILE
from src.network.discovery import DiscoveryScanner
from .tool_controllers.home_scanner_controller import HomeScannerController
from .base_dialog import BaseDialog

class DiscoverDialog(BaseDialog):
    def __init__(self, master, app, available_hosts):
        super().__init__(app=app, title=app.translate("scanner_title"))
        self.available_hosts = available_hosts
        self.host_map = { (h.get('nickname') or h.get('name')): h for h in self.available_hosts }
        
        self.all_found_hosts = []
        self.checkbox_widgets = {}
        self.domain_groups = {}
        self.selected_hosts = []

        self.scanner = DiscoveryScanner(app, callbacks={
            'on_status_update': self.update_status,
            'on_host_found': self.add_host_to_results,
            'on_scan_finished': self.on_scan_finished
        })

        self._setup_ui()
        self.load_from_cache()

    def _setup_ui(self):
        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(550, 650)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(3, weight=1)
        
        title_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("scanner_title"), font=customtkinter.CTkFont(size=14, weight="bold"))
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        top_frame = customtkinter.CTkFrame(main_frame)
        top_frame.grid(row=1, column=0, sticky="ew")
        top_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = customtkinter.CTkLabel(top_frame, text=self.app.translate("scanner_ready"), anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=(5, 5))
        
        self.progressbar = customtkinter.CTkProgressBar(main_frame, mode="indeterminate")
        self.progressbar.grid(row=2, column=0, sticky="ew", pady=(5, 10))
        self.progressbar.set(0)

        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.grid(row=3, column=0, sticky="nsew", pady=(10,0))
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(2, weight=1)

        self._create_scan_tabs(content_frame)

        self.search_entry = customtkinter.CTkEntry(content_frame, placeholder_text=self.app.translate("filter_placeholder"))
        self.search_entry.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        self.search_entry.bind("<KeyRelease>", self.filter_results)

        self.results_container_frame = customtkinter.CTkFrame(content_frame, fg_color="transparent")
        self.results_container_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        self.results_container_frame.grid_columnconfigure(0, weight=1)
        self.results_container_frame.grid_rowconfigure(0, weight=1)
        self._create_results_area()

        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=4, column=0, pady=(15, 0))

        self.add_button = customtkinter.CTkButton(button_frame, text=self.app.translate("scanner_add_selected"), command=self.confirm_selection, state="disabled")
        self.add_button.pack(side="left", padx=5)

        self.close_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_close"), command=self.on_close, fg_color="gray50")
        self.close_button.pack(side="left", padx=5)
        self.bind("<Escape>", lambda e: self.on_close())

    def _create_scan_tabs(self, parent):
        tab_view = customtkinter.CTkTabview(parent, anchor="w")
        tab_view.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        local_tab = tab_view.add(self.app.translate("scanner_tab_local"))
        remote_tab = tab_view.add(self.app.translate("scanner_tab_remote"))
        custom_tab = tab_view.add(self.app.translate("scanner_tab_custom"))
        
        local_tab.grid_columnconfigure(0, weight=1)
        self.local_scan_button = customtkinter.CTkButton(local_tab, text=self.app.translate("scanner_local_scan"), command=self.start_local_scan)
        self.local_scan_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        remote_tab.grid_columnconfigure(0, weight=1)
        host_names = list(self.host_map.keys())
        self.remote_host_combo = customtkinter.CTkComboBox(remote_tab, values=host_names, state="readonly" if host_names else "disabled")
        self.remote_host_combo.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        if host_names: self.remote_host_combo.set(host_names[0])
        self.remote_scan_button = customtkinter.CTkButton(remote_tab, text=self.app.translate("scanner_remote_scan"), command=self.start_remote_scan, state="normal" if host_names else "disabled")
        self.remote_scan_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        custom_tab.grid_columnconfigure(1, weight=1)
        self.network_entry = customtkinter.CTkEntry(custom_tab, placeholder_text="192.168.0.0")
        self.network_entry.grid(row=0, column=1, padx=(0, 10), pady=(10, 5), sticky="ew")
        self.mask_entry = customtkinter.CTkEntry(custom_tab, placeholder_text="255.255.255.0")
        self.mask_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")
        self.custom_scan_button = customtkinter.CTkButton(custom_tab, text=self.app.translate("scanner_custom_scan"), command=self.start_custom_scan)
        self.custom_scan_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    def _create_results_area(self):
        if hasattr(self, 'domain_tab_view'):
            self.domain_tab_view.destroy()
            
        self.domain_tab_view = customtkinter.CTkTabview(self.results_container_frame, anchor="w")
        self.domain_tab_view.grid(row=0, column=0, sticky="nsew")
        
        self.show_placeholder_tab(self.app.translate("scan_placeholder_tab"))

    def show_placeholder_tab(self, text):
        placeholder_text = self.app.translate("scan_placeholder_tab")
        if placeholder_text not in self.domain_tab_view._name_list:
            placeholder_tab = self.domain_tab_view.add(placeholder_text)
            label = customtkinter.CTkLabel(placeholder_tab, text=text)
            label.pack(expand=True)
            self.domain_tab_view.set(placeholder_text)

    def _prepare_for_scan(self):
        self.clear_results()
        self._set_buttons_for_scan_state(is_scanning=True)
        self.add_button.configure(state="disabled")
        self.progressbar.start()

    def start_local_scan(self):
        self._prepare_for_scan()
        self.scanner.start_scan("local")

    def start_remote_scan(self):
        host_name = self.remote_host_combo.get()
        if not host_name:
            self.app.show_error(self.app.translate("remote_scan_no_host_selected"))
            return
        
        target_host = self.host_map.get(host_name)
        scanner_controller = HomeScannerController(self.app)
        username, password = scanner_controller.get_credentials_for_remote_scan(target_host)
        self.lift(); self.focus_set()
        if not username: return

        self._prepare_for_scan()
        remote_info = {**target_host, "username": username, "password": password}
        self.scanner.start_scan("remote", remote_host_info=remote_info)

    def start_custom_scan(self):
        try:
            network = ipaddress.IPv4Network(f"{self.network_entry.get()}/{self.mask_entry.get()}", strict=False)
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            self.app.show_error(self.app.translate("error_net_address_invalid"))
            return
        
        self._prepare_for_scan()
        self.scanner.start_scan("custom", scan_target=network)

    def on_scan_finished(self):
        if not self.winfo_exists():
            return
        self.progressbar.stop()
        self.progressbar.set(1)
        self._set_buttons_for_scan_state(is_scanning=False)

    def _set_buttons_for_scan_state(self, is_scanning):
        if is_scanning:
            stop_text = self.app.translate("scanner_stop_scan")
            self.local_scan_button.configure(text=stop_text, command=self.scanner.stop_scan)
            self.remote_scan_button.configure(text=stop_text, command=self.scanner.stop_scan)
            self.custom_scan_button.configure(text=stop_text, command=self.scanner.stop_scan)
        else:
            self.local_scan_button.configure(text=self.app.translate("scanner_local_scan"), command=self.start_local_scan)
            self.remote_scan_button.configure(text=self.app.translate("scanner_remote_scan"), command=self.start_remote_scan)
            self.custom_scan_button.configure(text=self.app.translate("scanner_custom_scan"), command=self.start_custom_scan)

    def update_status(self, text):
        if not self.winfo_exists():
            return
        self.status_label.configure(text=text)

    def add_host_to_results(self, host_data):
        if not self.winfo_exists(): return
        ip = host_data['ip']
        if ip in self.checkbox_widgets: return

        if not self.domain_groups:
            self.domain_tab_view.delete(self.app.translate("scan_placeholder_tab"))

        self.all_found_hosts.append(host_data)
        self.all_found_hosts.sort(key=lambda x: ipaddress.IPv4Address(x['ip']))
        
        hostname = host_data.get('hostname', ip)
        domain = self._extract_domain(hostname)

        if domain not in self.domain_groups:
            new_tab = self.domain_tab_view.add(domain)
            scroll_frame = customtkinter.CTkScrollableFrame(new_tab)
            scroll_frame.pack(fill="both", expand=True)
            self.domain_groups[domain] = scroll_frame
        
        container = self.domain_groups[domain]
        display_name = hostname.split('.')[0]
        checkbox_text = f"{display_name} ({ip})" if hostname != ip else ip
        checkbox = customtkinter.CTkCheckBox(container, text=checkbox_text)
        checkbox.pack(padx=10, pady=5, anchor="w", fill="x")
        
        self.checkbox_widgets[ip] = checkbox
        self.add_button.configure(state="normal")

    def _extract_domain(self, hostname):
        default = self.app.translate("default_domain_name")
        try:
            ipaddress.ip_address(hostname)
            return default
        except ValueError:
            pass
        if '.' in hostname:
            parts = hostname.split('.', 1)
            if len(parts) > 1 and any(c.isalpha() for c in parts[1]):
                return parts[1].upper()
        return default

    def filter_results(self, event=None):
        term = self.search_entry.get().lower()
        for ip, cb in self.checkbox_widgets.items():
            if cb.winfo_exists():
                cb.pack_forget()
                if term in cb.cget("text").lower():
                    cb.pack(padx=10, pady=5, anchor="w", fill="x")

    def clear_results(self):
        self._create_results_area()
        self.domain_groups.clear()
        self.checkbox_widgets.clear()
        if not self.scanner.is_running():
            self.all_found_hosts.clear()

    def load_from_cache(self):
        cache_file_path = os.path.join(self.app.base_dir, DISCOVERY_CACHE_FILE)
        if not os.path.exists(cache_file_path): return
        try:
            with open(cache_file_path, "r") as f:
                cached_hosts = json.load(f)
            if cached_hosts:
                self.clear_results()
                for host in cached_hosts:
                    self.add_host_to_results(host)
                self.update_status(self.app.translate("scanner_cached_results_message"))
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    def save_to_cache(self):
        cache_file_path = os.path.join(self.app.base_dir, DISCOVERY_CACHE_FILE)
        try:
            with open(cache_file_path, "w") as f:
                json.dump(self.all_found_hosts, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar cache de descoberta: {e}")

    def confirm_selection(self):
        for ip, cb in self.checkbox_widgets.items():
            if cb.winfo_ismapped() and cb.get() == 1:
                text = cb.cget("text")
                hostname_part, ip_from_text = (text.replace(")", "").split(" (") if " (" in text else (text, text))
                original = next((h for h in self.all_found_hosts if h['ip'] == ip_from_text), None)
                full_hostname = original.get('hostname', hostname_part) if original else hostname_part
                self.selected_hosts.append({"name": full_hostname, "ip": ip_from_text})
        self.on_close()

    def get_selection(self):
        return self.selected_hosts

    def on_close(self):
        self.scanner.stop_scan()
        self.destroy()