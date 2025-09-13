# src/ferramentasderede/ui/components/custom_dialogs.py
# Módulo para criar caixas de diálogo personalizadas que respeitam o tema da aplicação.

import customtkinter
from .base_dialog import BaseDialog

class CustomMessageBox(BaseDialog):
    def __init__(self, app, title, message, buttons, text_color=None):
        # Inicializar atributos ANTES de chamar super().__init__
        self.result = None
        self.buttons_list = buttons if buttons else []
        self.app = app
        
        super().__init__(app=app, title=title) 
        
        self.bind("<Escape>", self._on_escape)

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        
        if any(b.lower() in ["sim", "não", "yes", "no", "sí"] for b in buttons):
            icon_label = customtkinter.CTkLabel(main_frame, text="❓", font=customtkinter.CTkFont(size=48))
            icon_label.grid(row=0, column=0, pady=(0, 10))
            message_row = 1
            button_row = 2
        else:
            message_row = 0
            button_row = 1

        message_label = customtkinter.CTkLabel(main_frame, text=message, wraplength=350, justify="center", text_color=text_color)
        message_label.grid(row=message_row, column=0, pady=(0, 20))

        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=button_row, column=0)

        for i, button_text in enumerate(buttons):
            is_cancel = button_text.lower() in ["não", "cancelar", "no", "cancel"]
            
            button = customtkinter.CTkButton(
                button_frame,
                text=button_text,
                command=lambda b=button_text: self._on_button_press(b)
            )
            if i == 0 and not is_cancel:
                button.focus_set()
                self.bind("<Return>", lambda e, b=button_text: self._on_button_press(b))

            button.grid(row=0, column=i, padx=5)

    def _on_button_press(self, button_text):
        self.result = button_text
        self.destroy()

    def _on_escape(self, event=None):
        cancel_buttons = [b for b in self.buttons_list if b.lower() in ["não", "cancelar", "no", "cancel"]]
        if cancel_buttons:
            self._on_button_press(cancel_buttons[0])
        else:
            self.destroy()

    def destroy(self, event=None):
        try:
            # Verificação de segurança para evitar AttributeError
            if hasattr(self, 'result') and self.result is None:
                if hasattr(self, 'buttons_list') and hasattr(self, 'app'):
                    if self.app.translate("label_no") in self.buttons_list:
                        self.result = self.app.translate("label_no")
        except:
            # Se houver qualquer erro, ignorar e continuar com destroy
            pass
        
        super().destroy()

    def get_result(self):
        return getattr(self, 'result', None)

class PasswordInputDialog(BaseDialog):
    def __init__(self, app, title, message):
        super().__init__(app=app, title=title)
        self._user_input = None

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        message_label = customtkinter.CTkLabel(main_frame, text=message, wraplength=350, justify="left")
        message_label.grid(row=0, column=0, pady=(0, 10), sticky="w")

        self.entry = customtkinter.CTkEntry(main_frame, show="*", width=300)
        self.entry.grid(row=1, column=0, pady=(0, 20), sticky="ew")
        self.entry.bind("<Return>", self._ok_event)
        self.entry.focus_set() # Define o foco diretamente

        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="e")
        
        ok_button = customtkinter.CTkButton(
            button_frame,
            text=self.app.translate("label_ok"),
            command=self._ok_event
        )
        ok_button.pack(side="left", padx=5)

        cancel_button = customtkinter.CTkButton(
            button_frame,
            text=self.app.translate("label_cancel"),
            command=self._cancel_event,
            fg_color="gray50"
        )
        cancel_button.pack(side="left", padx=5)

        self.bind("<Escape>", self._cancel_event)

    def _ok_event(self, event=None):
        self._user_input = self.entry.get()
        self.destroy()

    def _cancel_event(self, event=None):
        self._user_input = None
        self.destroy()

    def get_input(self):
        self.wait()
        return self._user_input