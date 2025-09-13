# src/ferramentasderede/ui/components/loading_window.py
# Contém a classe para a janela de carregamento.

import customtkinter
import logging
from .base_dialog import BaseDialog

class LoadingWindow(BaseDialog):
    """Cria uma janela de carregamento com auto-destruição garantida."""
    def __init__(self, master, description="Carregando...", on_cancel=None):
        # Flags de controle
        self._destroyed = False
        self._should_close = False
        self._on_cancel = on_cancel
        self._check_timer_id = None
        
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
            
        # SOLUÇÃO RADICAL: Timer de auto-verificação a cada 500ms
        self._start_auto_check()
        
        # SOLUÇÃO RADICAL: Auto-destruição em 30 segundos NO MÁXIMO
        self._max_lifetime_id = self.after(30000, self._force_destroy)
        
    def _start_auto_check(self):
        """Inicia verificação automática para fechar quando necessário"""
        if not self._destroyed:
            self._check_timer_id = self.after(500, self._auto_check)
            
    def _auto_check(self):
        """Verifica se deve fechar automaticamente"""
        try:
            if self._destroyed:
                return
                
            # Se foi sinalizada para fechar, fechar imediatamente
            if self._should_close:
                logging.info("LoadingWindow: Auto-check detectou sinal para fechar")
                self._force_destroy()
                return
                
            # Reagendar próxima verificação
            if not self._destroyed:
                self._check_timer_id = self.after(500, self._auto_check)
                
        except Exception as e:
            logging.error(f"LoadingWindow: Erro no auto-check: {e}")
            self._force_destroy()
            
    def _force_destroy(self):
        """Força destruição imediata da janela"""
        if self._destroyed:
            return
            
        logging.info("LoadingWindow: Iniciando destruição forçada")
        self._destroyed = True
        
        try:
            # Cancelar timers
            if self._check_timer_id:
                self.after_cancel(self._check_timer_id)
                self._check_timer_id = None
        except:
            pass
            
        try:
            if self._max_lifetime_id:
                self.after_cancel(self._max_lifetime_id)
                self._max_lifetime_id = None
        except:
            pass
        
        try:
            # Parar progressbar
            if hasattr(self, 'progressbar') and self.progressbar:
                self.progressbar.stop()
        except:
            pass
            
        try:
            # Destruir janela
            if self.winfo_exists():
                self.destroy()
                logging.info("LoadingWindow: Destruição forçada concluída")
        except:
            pass

    def _on_close_request(self):
        """Chamado ao clicar no X: usar sistema de destruição forçada"""
        logging.info("LoadingWindow: Usuário clicou em fechar")
        
        # Tentar cancelar a operação se um callback foi fornecido
        try:
            if callable(self._on_cancel):
                logging.info("LoadingWindow: Chamando callback de cancelamento")
                self._on_cancel()
        except Exception as e:
            logging.error(f"LoadingWindow: Erro no callback de cancelamento: {e}")
        
        # Forçar destruição imediata
        self._force_destroy()

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
        """Sobrescreve destroy para usar sistema de destruição forçada"""
        logging.info("LoadingWindow: destroy() chamado - redirecionando para _force_destroy()")
        self._force_destroy()

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