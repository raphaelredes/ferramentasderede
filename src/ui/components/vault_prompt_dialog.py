# src/ferramentasderede/ui/components/vault_prompt_dialog.py
# Diálogo específico para perguntar ao usuário se deseja criar um cofre de sessão.

import customtkinter
import logging
from .base_dialog import BaseDialog

class VaultPromptDialog(BaseDialog):
    def __init__(self, app):
        logging.info("Showing vault creation prompt dialog.")
        super().__init__(app=app, title=app.translate("vault_ask_to_create_title"))
        self._result = False

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        
        icon_label = customtkinter.CTkLabel(main_frame, text="❓", font=customtkinter.CTkFont(size=48))
        icon_label.grid(row=0, column=0, pady=(0, 10))

        message_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("vault_create_prompt_session_only"), wraplength=400, justify="center")
        message_label.grid(row=1, column=0, pady=(0, 20))
        
        info_button = customtkinter.CTkButton(
            main_frame,
            text=self.app.translate("vault_more_info_button"),
            command=self.app.show_security_info_dialog,
            fg_color="transparent",
            border_width=1
        )
        info_button.grid(row=2, column=0, pady=(0, 20), padx=40, sticky="ew")

        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0)
        
        yes_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_yes"), command=self._on_yes)
        yes_button.grid(row=0, column=0, padx=5)

        no_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_no"), command=self._on_no, fg_color="gray50")
        no_button.grid(row=0, column=1, padx=5)
        
        self.bind("<Escape>", self._on_no)

    def _on_yes(self, event=None):
        logging.info("User chose to create a vault.")
        self._result = True
        self.destroy()

    def _on_no(self, event=None):
        logging.info("User chose NOT to create a vault.")
        self._result = False
        self.destroy()

    def get_result(self):
        """Apenas retorna o valor. A espera é gerenciada por quem chama o diálogo."""
        return self._result