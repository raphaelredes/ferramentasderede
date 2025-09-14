# src/ferramentasderede/ui/components/remove_host_dialog.py
# Diálogo para selecionar e remover um ou mais hosts, agora mostrando apelidos.

import customtkinter
import logging
from .base_dialog import BaseDialog

class RemoveHostDialog(BaseDialog):
    def __init__(self, master, app, hosts):
        super().__init__(app=app, title=app.translate("title_remove_hosts"))
        logging.info("Initializing RemoveHostDialog")
        self.hosts = hosts
        self.selected_hosts = []
        self.checkboxes = []

        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(400, 350)
        self.bind("<Escape>", lambda e: self.destroy())

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        title_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("title_remove_hosts"), font=customtkinter.CTkFont(size=14, weight="bold"))
        title_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        scrollable_frame = customtkinter.CTkScrollableFrame(main_frame)
        scrollable_frame.grid(row=1, column=0, sticky="nsew")
        scrollable_frame.grid_columnconfigure(0, weight=1)

        for i, host in enumerate(self.hosts):
            nickname = host.get("nickname", "").strip()
            original_name = host.get("name", "N/A")
            ip = host.get("ip", "N/A")

            if nickname and nickname != original_name:
                display_text = f"{nickname} ({original_name} - {ip})"
            else:
                display_text = f"{original_name} ({ip})"
            
            checkbox = customtkinter.CTkCheckBox(scrollable_frame, text=display_text)
            checkbox.grid(row=i, column=0, sticky="w", padx=10, pady=5)
            self.checkboxes.append((checkbox, host))

        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(10, 0))

        self.confirm_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_confirm"), command=self.confirm)
        self.confirm_button.pack(side="left", padx=5)

        self.cancel_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_cancel"), command=self.destroy, fg_color="gray50")
        self.cancel_button.pack(side="left", padx=5)

    def confirm(self):
        for checkbox, host in self.checkboxes:
            if checkbox.get() == 1:
                self.selected_hosts.append(host)
        logging.debug(f"Selected hosts for removal: {self.selected_hosts}")
        logging.info(f"Confirmed removal of {len(self.selected_hosts)} hosts.")
        self.destroy()

    def get_selection(self):
        self.wait()
        return self.selected_hosts