# src/ferramentasderede/ui/components/custom_input_dialog.py
# Versão personalizada do CTkInputDialog que herda de BaseDialog para centralização.

import customtkinter
from .base_dialog import BaseDialog

class CustomInputDialog(BaseDialog):
    def __init__(self, app, title: str, text: str):
        super().__init__(app, title=title, min_width=350, min_height=180, max_width=500, max_height=300)
        self._input_value = None

        # CORREÇÃO: Usa 'self' como pai, não o 'border_frame' que não existe mais.
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)  # Message cresce
        main_frame.grid_rowconfigure(1, weight=0)  # Entry não cresce
        main_frame.grid_rowconfigure(2, weight=0)  # Buttons não crescem

        message_label = customtkinter.CTkLabel(main_frame, text=text, wraplength=400, justify="left")
        message_label.grid(row=0, column=0, pady=(0, 15), padx=5, sticky="ew")

        self.entry = customtkinter.CTkEntry(main_frame, height=35)
        self.entry.grid(row=1, column=0, pady=(0, 20), padx=5, sticky="ew")
        self.entry.bind("<Return>", self._ok_event)
        self.entry.focus()
        
        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="e", padx=5)

        ok_button = customtkinter.CTkButton(
            button_frame, text=self.app.translate("label_confirm"), command=self._ok_event, height=32
        )
        ok_button.pack(side="right", padx=(5, 0))

        cancel_button = customtkinter.CTkButton(
            button_frame, text=self.app.translate("label_cancel"), command=self._cancel_event, 
            fg_color="gray50", height=32
        )
        cancel_button.pack(side="right", padx=(0, 5))
        
        self.bind("<Escape>", self._cancel_event)

    def _ok_event(self, event=None):
        self._input_value = self.entry.get()
        self.destroy()

    def _cancel_event(self, event=None):
        self._input_value = None
        self.destroy()

    def get_input(self):
        """Espera a janela ser fechada e retorna o valor inserido."""
        self.wait()
        return self._input_value