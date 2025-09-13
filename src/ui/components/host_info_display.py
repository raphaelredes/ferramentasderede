# app/ui_components/host_info_display.py
# Painel que exibe informações estáticas sobre um host remoto.

import customtkinter

class HostInfoDisplay(customtkinter.CTkFrame):
    def __init__(self, master, app, host_data):
        super().__init__(master)
        self.app = app
        self.host_data = host_data

        self.grid_columnconfigure(1, weight=1)

        # --- Labels de Identificação ---
        hostname_label = customtkinter.CTkLabel(self, text=f"{self.app.translate('label_host')}:", font=customtkinter.CTkFont(weight="bold"))
        hostname_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.hostname_label_value = customtkinter.CTkLabel(self, text=self.host_data.get('name', self.app.translate("not_available")), anchor="w")
        self.hostname_label_value.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="ew")

        ip_label = customtkinter.CTkLabel(self, text=f"{self.app.translate('label_ip')}:", font=customtkinter.CTkFont(weight="bold"))
        ip_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.ip_label_value = customtkinter.CTkLabel(self, text=self.host_data.get('ip', self.app.translate("not_available")), anchor="w")
        self.ip_label_value.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # --- Labels de Informações Remotas ---
        os_label = customtkinter.CTkLabel(self, text=f"{self.app.translate('sysinfo_os')}", font=customtkinter.CTkFont(weight="bold"))
        os_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.os_label_value = customtkinter.CTkLabel(self, text=self.app.translate("not_available"), anchor="w")
        self.os_label_value.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        ram_label = customtkinter.CTkLabel(self, text=f"{self.app.translate('sysinfo_ram')}", font=customtkinter.CTkFont(weight="bold"))
        ram_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.ram_label_value = customtkinter.CTkLabel(self, text=self.app.translate("not_available"), anchor="w")
        self.ram_label_value.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        tv_id_label = customtkinter.CTkLabel(self, text=f"{self.app.translate('label_tv_id')}:", font=customtkinter.CTkFont(weight="bold"))
        tv_id_label.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="w")
        self.tv_id_label_value = customtkinter.CTkLabel(self, text=self.app.translate("not_available"), anchor="w")
        self.tv_id_label_value.grid(row=4, column=1, padx=10, pady=(5, 10), sticky="ew")

    def update_info(self, os=None, ram=None, tv_id=None):
        """Atualiza as labels com novas informações."""
        if os is not None:
            self.os_label_value.configure(text=os)
        if ram is not None:
            self.ram_label_value.configure(text=ram)
        if tv_id is not None:
            self.tv_id_label_value.configure(text=tv_id)