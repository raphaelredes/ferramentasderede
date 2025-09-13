# src/ferramentasderede/ui/components/loading_window.py
# Contém a classe para a janela de carregamento.

import customtkinter
import logging
from .base_dialog import BaseDialog

class LoadingWindow(BaseDialog):
    """Cria uma janela de carregamento para operações demoradas com opção de cancelar."""
    def __init__(self, master, description="Carregando...", on_cancel=None):
        # Inicializar flag antes de chamar super().__init__
        self._destroyed = False
        self._on_cancel = on_cancel
        
        super().__init__(master, title="Carregando...")
        
        # Configurar como janela simples sem redimensionamento
        self.resizable(False, False)

        # Frame principal
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.label = customtkinter.CTkLabel(
            main_frame, 
            text=description, 
            font=customtkinter.CTkFont(size=14), 
            wraplength=350
        )
        self.label.pack(pady=20, padx=20)
        
        self.progressbar = customtkinter.CTkProgressBar(main_frame, mode="indeterminate")
        self.progressbar.pack(pady=10, padx=20, fill="x")
        self.progressbar.start()

        # Substituir protocolo de fechamento para permitir cancelamento
        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        except Exception:
            pass

    def _on_close_request(self):
        """Chamado ao clicar no X: tenta cancelar a operação em andamento com segurança."""
        try:
            if callable(self._on_cancel):
                try:
                    self._on_cancel()
                except Exception:
                    pass
        finally:
            try:
                self.destroy()
            except Exception:
                self._destroyed = True

    def wm_state(self, newstate=None):
        """Sobrescreve wm_state para evitar erros quando a janela foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return "withdrawn"
        try:
            return super().wm_state(newstate)
        except Exception as e:
            logging.debug(f"Error in wm_state: {e}")
            self._destroyed = True
            return "withdrawn"

    def state(self, newstate=None):
        """Sobrescreve state para evitar erros quando a janela foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return "withdrawn"
        try:
            return super().state(newstate)
        except Exception as e:
            logging.debug(f"Error in state: {e}")
            self._destroyed = True
            return "withdrawn"

    def withdraw(self):
        """Sobrescreve withdraw para marcar como destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().withdraw()
        except Exception as e:
            logging.debug(f"Error in withdraw: {e}")
            self._destroyed = True

    def deiconify(self):
        """Sobrescreve deiconify para verificar se foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().deiconify()
        except Exception as e:
            logging.debug(f"Error in deiconify: {e}")
            self._destroyed = True

    def iconify(self):
        """Sobrescreve iconify para verificar se foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().iconify()
        except Exception as e:
            logging.debug(f"Error in iconify: {e}")
            self._destroyed = True

    def focus_set(self):
        """Sobrescreve focus_set para evitar erros quando a janela foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().focus_set()
        except Exception as e:
            logging.debug(f"Error in focus_set: {e}")
            self._destroyed = True

    def focus_force(self):
        """Sobrescreve focus_force para evitar erros quando a janela foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().focus_force()
        except Exception as e:
            logging.debug(f"Error in focus_force: {e}")
            self._destroyed = True

    def grab_set(self):
        """Sobrescreve grab_set para evitar erros quando a janela foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().grab_set()
        except Exception as e:
            logging.debug(f"Error in grab_set: {e}")
            self._destroyed = True

    def grab_release(self):
        """Sobrescreve grab_release para evitar erros quando a janela foi destruída."""
        if self._destroyed or not self.winfo_exists():
            return
        try:
            super().grab_release()
        except Exception as e:
            logging.debug(f"Error in grab_release: {e}")
            self._destroyed = True

    def destroy(self):
        """Sobrescreve destroy para parar a progressbar antes de destruir."""
        if self._destroyed:
            return
            
        self._destroyed = True
        
        try:
            if hasattr(self, 'progressbar') and self.progressbar.winfo_exists():
                self.progressbar.stop()
                try:
                    # Destruir explicitamente a progressbar para cancelar qualquer loop interno
                    self.progressbar.destroy()
                except Exception as e:
                    logging.debug(f"Error destroying progressbar: {e}")
        except Exception as e:
            logging.debug(f"Error stopping progressbar: {e}")
        
        try:
            # Verificar se a janela ainda existe antes de destruir
            if self.winfo_exists():
                super().destroy()
        except Exception as e:
            logging.debug(f"Error destroying LoadingWindow: {e}")
            # Se não conseguir destruir, pelo menos marcar como destruída
            self._destroyed = True

    def update_status(self, text):
        """Atualiza o texto da label de status de forma thread-safe."""
        if self._destroyed or not self.winfo_exists():
            return
            
        def do_update():
            try:
                if not self._destroyed and self.winfo_exists() and hasattr(self, 'label') and self.label.winfo_exists():
                    self.label.configure(text=text)
                    self.update_idletasks()
            except Exception as e:
                logging.debug(f"Error updating loading window status: {e}")
                # Marcar como destruída se houver erro
                self._destroyed = True
        
        try:
            if not self._destroyed and self.winfo_exists():
                self.after(0, do_update)
        except Exception as e:
            logging.debug(f"Error scheduling status update: {e}")
            self._destroyed = True