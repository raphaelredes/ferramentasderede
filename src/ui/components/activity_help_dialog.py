# app/ui_components/activity_help_dialog.py

import customtkinter
from .base_dialog import BaseDialog

class ActivityHelpDialog(BaseDialog):
    def __init__(self, app):
        # CORREÇÃO: Chama o super() corretamente com 'app' e um título.
        super().__init__(app=app, title=app.translate("activity_help_title"))
        self._result = False
        
        # CORREÇÃO: Usa 'self' como o pai dos frames, não o 'border_frame' que não existe mais.
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        title_label = customtkinter.CTkLabel(
            main_frame,
            text=self.app.translate("activity_help_title"),
            font=customtkinter.CTkFont(size=16, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=(0, 10), sticky="w")

        info_text = self.app.translate("activity_help_message")
        info_label = customtkinter.CTkLabel(
            main_frame,
            text=info_text,
            wraplength=500,
            justify="left",
            anchor="w"
        )
        info_label.grid(row=1, column=0, pady=(0, 15), sticky="ew")

        # CORREÇÃO: Usa 'self' como o pai dos frames.
        bottom_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(0, 20), anchor="s")
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.dont_show_again_var = customtkinter.BooleanVar()
        self.checkbox = customtkinter.CTkCheckBox(
            bottom_frame,
            text=self.app.translate("activity_help_dont_show_again"),
            variable=self.dont_show_again_var
        )
        self.checkbox.grid(row=0, column=0, padx=5, pady=(5,10), sticky="w")

        self.ok_button = customtkinter.CTkButton(
            bottom_frame,
            text=self.app.translate("label_ok"),
            command=self._on_ok
        )
        self.ok_button.grid(row=1, column=0, padx=5, sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self._on_ok)
        self.bind("<Return>", self._on_ok)
        self.bind("<Escape>", self._on_ok)
    
    def _on_ok(self, event=None):
        self._result = self.dont_show_again_var.get()
        self.destroy()

    def get_result(self):
        # A espera agora é gerenciada por quem chama o diálogo, se necessário.
        return self._result