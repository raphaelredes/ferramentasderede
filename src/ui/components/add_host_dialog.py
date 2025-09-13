# src/ferramentasderede/ui/components/add_host_dialog.py

import customtkinter
import logging
from .base_dialog import BaseDialog

class AddHostDialog(BaseDialog):
    def __init__(self, app):
        self.app = app
        super().__init__(app, title=self.app.translate("title_add_host"))
        self._input_value = None

        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        # Mensagem melhorada explicando a funcionalidade
        message_text = self.app.translate("dialog_add_host_text_mac")
        message_text += "\n\n💡 Dica: Apenas o nome/IP é suficiente. O sistema resolverá automaticamente o hostname e IP."
        
        message_label = customtkinter.CTkLabel(main_frame, text=message_text, wraplength=350, justify="left")
        message_label.grid(row=0, column=0, pady=(0, 10), padx=20, sticky="w")

        self.entry = customtkinter.CTkEntry(main_frame, width=300, placeholder_text="Ex: google.com ou 8.8.8.8")
        self.entry.grid(row=1, column=0, pady=(0, 10), padx=20, sticky="ew")
        self.entry.bind("<Return>", self._ok_event)
        
        # Label de status para feedback
        self.status_label = customtkinter.CTkLabel(main_frame, text="", text_color=("gray50", "gray70"))
        self.status_label.grid(row=2, column=0, pady=(0, 20), padx=20, sticky="w")
        
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="e", padx=20, pady=(10, 20))

        self.ok_button = customtkinter.CTkButton(
            button_frame,
            text=self.app.translate("label_confirm"),
            command=self._ok_event
        )
        self.ok_button.pack(side="left", padx=5)

        cancel_button = customtkinter.CTkButton(
            button_frame,
            text=self.app.translate("label_cancel"),
            command=self._cancel_event,
            fg_color="gray50"
        )
        cancel_button.pack(side="left")
        
        self.bind("<Escape>", self._cancel_event)
        
        # Focar no campo de entrada
        self.entry.focus_set()

    def _ok_event(self, event=None):
        input_value = self.entry.get().strip()
        
        if not input_value:
            self.update_status("❌ Por favor, insira um nome ou IP válido.", error=True)
            return
        
        # Validar formato básico
        if self._validate_input(input_value):
            self._input_value = input_value
            self.update_status("✅ Entrada válida. Processando...", success=True)
            self._safe_destroy()
        else:
            self.update_status("❌ Formato inválido. Use: nome,ip,mac ou apenas nome/IP", error=True)
    
    def _cancel_event(self, event=None):
        self._input_value = None
        self._safe_destroy()
    
    def _validate_input(self, input_value):
        """Valida o formato da entrada."""
        if not input_value:
            return False
        
        # Aceitar qualquer entrada não vazia (a validação completa será feita no controlador)
        return True
    
    def update_status(self, message, error=False, success=False):
        """Atualiza a mensagem de status."""
        try:
            if error:
                self.status_label.configure(text=message, text_color=("red", "#ff6b6b"))
            elif success:
                self.status_label.configure(text=message, text_color=("green", "#51cf66"))
            else:
                self.status_label.configure(text=message, text_color=("gray50", "gray70"))
            
            self.status_label.update()
        except Exception as e:
            logging.error(f"Erro ao atualizar status: {e}")

    def _safe_destroy(self):
        """Destrói o diálogo de forma segura."""
        try:
            # Remover bindings para evitar callbacks após destruição
            self.unbind("<Escape>")
            self.entry.unbind("<Return>")
            
            # Destruir a janela
            self.destroy()
        except Exception as e:
            logging.error(f"Error destroying AddHostDialog: {e}")

    def get_input(self):
        try:
            self.wait()
            return self._input_value
        except Exception as e:
            logging.error(f"Error in get_input: {e}")
            return None