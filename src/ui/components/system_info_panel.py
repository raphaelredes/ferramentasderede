# app/ui_components/system_info_panel.py
# Painel para exibir informações detalhadas do sistema de um host remoto.

import customtkinter
from datetime import datetime
import re
import logging

class SystemInfoPanel(customtkinter.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("gray85", "gray17"), corner_radius=10)
        logging.info("Initializing SystemInfoPanel")
        self.app = app
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.tab_view = customtkinter.CTkTabview(self, anchor="w")
        self.tab_view.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.general_tab = self.tab_view.add(self.app.translate("sysinfo_general_tab"))
        self.disks_tab = self.tab_view.add(self.app.translate("sysinfo_disks_tab"))
        
        self._create_general_tab_widgets()
        self._create_disks_tab_widgets()
        
    def _create_info_row(self, parent, text_key, row):
        title_label = customtkinter.CTkLabel(parent, text=self.app.translate(text_key), anchor="w", font=customtkinter.CTkFont(weight="bold"))
        title_label.grid(row=row, column=0, sticky="w", padx=10, pady=(6,0))
        
        value_label = customtkinter.CTkLabel(parent, text="...", anchor="w", wraplength=200)
        value_label.grid(row=row, column=1, sticky="ew", padx=10, pady=(6,0))
        
        return title_label, value_label

    def _create_general_tab_widgets(self):
        logging.debug("Creating general tab widgets")
        self.general_tab.grid_columnconfigure(1, weight=1)
        self.os_title, self.os_value = self._create_info_row(self.general_tab, "sysinfo_os", 0)
        self.version_title, self.version_value = self._create_info_row(self.general_tab, "sysinfo_os_version", 1)
        self.cpu_title, self.cpu_value = self._create_info_row(self.general_tab, "sysinfo_cpu", 2)
        self.ram_title, self.ram_value = self._create_info_row(self.general_tab, "sysinfo_ram", 3)
        self.uptime_title, self.uptime_value = self._create_info_row(self.general_tab, "sysinfo_uptime", 4)
        self.install_date_title, self.install_date_value = self._create_info_row(self.general_tab, "sysinfo_install_date", 5)

    def _create_disks_tab_widgets(self):
        logging.debug("Creating disks tab widgets")
        self.disks_tab.grid_columnconfigure(0, weight=1)
        self.disks_tab.grid_rowconfigure(0, weight=1)
        self.disks_frame = customtkinter.CTkScrollableFrame(self.disks_tab, fg_color="transparent")
        self.disks_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.disks_frame.grid_columnconfigure(0, weight=1)
        
    def display_info(self, info_data):
        logging.info(f"Received info data for display. Data is None: {info_data is None}, is empty: {not info_data}, has error: {'error' in info_data if isinstance(info_data, dict) else False}")
        if info_data is None:
            self._set_all_labels_to("...")
            self._clear_disks_frame()
            return
        
        if not info_data:
            initial_prompt = self.app.translate("sysinfo_initial_prompt")
            self._set_all_labels_to(initial_prompt)
            self._clear_disks_frame()
            no_disk_label = customtkinter.CTkLabel(self.disks_frame, text=initial_prompt)
            no_disk_label.pack(pady=10)
            return
            
        if "error" in info_data:
            error_text = info_data.get("error", self.app.translate("sysinfo_loading_failed"))
            
            # Verificar se é um erro de autenticação WinRM
            if "authentication" in error_text.lower() or "autenticação" in error_text.lower():
                # Para erros de autenticação, mostrar apenas "Erro de Autenticação" em todos os campos
                self._set_all_labels_to(self.app.translate("winrm_error_authentication_title"))
            else:
                # Para outros tipos de erro, mostrar a mensagem completa
                self._set_all_labels_to(error_text)
            
            self._clear_disks_frame()
            return

        self.os_value.configure(text=info_data.get("OS", "N/A"))
        self.version_value.configure(text=info_data.get("OS_Version", "N/A"))
        self.cpu_value.configure(text=info_data.get("CPU", "N/A"))
        ram_gb = info_data.get("RAM_GB")
        self.ram_value.configure(text=f"{ram_gb} GB" if ram_gb else "N/A")

        self._parse_and_display_dates(info_data)
        self._display_disk_info(info_data.get("Disks", []))

    def _parse_and_display_dates(self, info_data):
        try:
            last_boot_str = info_data.get("LastBootUpTime")
            if last_boot_str:
                last_boot_aware = datetime.fromisoformat(last_boot_str)
                now_aware = datetime.now(last_boot_aware.tzinfo)
                uptime = now_aware - last_boot_aware
                days, rem = divmod(uptime.total_seconds(), 86400)
                hours, rem = divmod(rem, 3600)
                minutes, _ = divmod(rem, 60)
                self.uptime_value.configure(text=f"{int(days)}d {int(hours)}h {int(minutes)}m")
            else:
                self.uptime_value.configure(text="N/A")
        except (ValueError, TypeError):
            self.uptime_value.configure(text=self.app.translate("sysinfo_invalid_date"))

        try:
            install_date_str = info_data.get("OS_InstallDate")
            if install_date_str:
                # Extrai o timestamp do formato /Date(timestamp)/ e converte para segundos
                match = re.search(r'/Date\((\d+)\)/', install_date_str)
                if match:
                    timestamp_ms = int(match.group(1))
                    install_date = datetime.fromtimestamp(timestamp_ms / 1000) # Convert ms to s
                    self.install_date_value.configure(text=install_date.strftime("%d/%m/%Y %H:%M"))
                else:
                    self.install_date_value.configure(text="N/A")
            else:
                self.install_date_value.configure(text="N/A")
        except (ValueError, TypeError, AttributeError) as e:
            self.install_date_value.configure(text=self.app.translate("sysinfo_invalid_date"))
            # Adicionar log para depuração
            import logging
            logging.error(f"Erro ao parsear InstallDate \'{install_date_str}\': {e}")

    def _display_disk_info(self, disks):
        self._clear_disks_frame()
        if not disks:
            no_disk_label = customtkinter.CTkLabel(self.disks_frame, text="N/A")
            no_disk_label.pack(pady=10)
            return
            
        for i, disk in enumerate(disks):
            total_gb = disk.get("Total_GB", 0)
            free_gb = disk.get("Free_GB", 0)
            used_gb = total_gb - free_gb
            percentage = used_gb / total_gb if total_gb > 0 else 0
            
            logging.debug(f"Disk {i}: DeviceID={disk.get("DeviceID")}, Total_GB={total_gb}, Free_GB={free_gb}, Used_GB={used_gb}, Percentage={percentage}")

            label_text = self.app.translate("disk_space_info", 
                                            volume_name=disk.get("VolumeName", "-"), 
                                            drive_letter=disk.get("DeviceID", "?"), 
                                            free_gb=free_gb, total_gb=total_gb)
            logging.debug(f"Disk Label Text: {label_text}")
            logging.debug(f"Disk Percentage: {percentage}")

            disk_frame = customtkinter.CTkFrame(self.disks_frame, fg_color="transparent")
            disk_frame.pack(fill="x", padx=5, pady=(5 if i > 0 else 0, 5))
            
            label = customtkinter.CTkLabel(disk_frame, text=label_text, anchor="w")
            label.pack(fill="x", pady=(0, 2))
            
            progress_bar = customtkinter.CTkProgressBar(disk_frame)
            progress_bar.pack(fill="x", pady=(0,5))
            progress_bar.set(percentage)
        self.disks_frame.update_idletasks()
        self.disks_frame.update()
            
    def _set_all_labels_to(self, text):
        self.os_value.configure(text=text)
        self.version_value.configure(text=text)
        self.cpu_value.configure(text=text)
        self.ram_value.configure(text=text)
        self.uptime_value.configure(text=text)
        self.install_date_value.configure(text=text)

    def _clear_disks_frame(self):
        logging.debug("Clearing disks frame")
        for widget in self.disks_frame.winfo_children():
            widget.destroy()

    def update_language(self):
        self.os_title.configure(text=self.app.translate("sysinfo_os"))
        self.version_title.configure(text=self.app.translate("sysinfo_os_version"))
        self.cpu_title.configure(text=self.app.translate("sysinfo_cpu"))
        self.ram_title.configure(text=self.app.translate("sysinfo_ram"))
        self.uptime_title.configure(text=self.app.translate("sysinfo_uptime"))
        self.install_date_title.configure(text=self.app.translate("sysinfo_install_date"))
        logging.debug("Updating UI language for SystemInfoPanel")
        
        new_tab_names = [self.app.translate("sysinfo_general_tab"), self.app.translate("sysinfo_disks_tab")]
        if hasattr(self.tab_view, "_segmented_button"):
            current_tab_name = self.tab_view.get()
            self.tab_view._segmented_button.configure(values=new_tab_names)
            if current_tab_name in self.tab_view._name_list:
                 self.tab_view.set(current_tab_name)