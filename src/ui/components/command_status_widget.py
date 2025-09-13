# src/ferramentasderede/ui/components/command_status_widget.py
# Widget de status de execução de comandos para ser usado dentro das sub-abas

import customtkinter
import threading
import time
import logging

class CommandStatusWidget(customtkinter.CTkFrame):
    """Widget compacto para mostrar status de execução de comandos dentro das sub-abas."""
    
    def __init__(self, master, app, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app = app
        self.status = "idle"  # idle, running, success, error
        self.current_command = None
        self.blink_thread = None
        self.blink_active = False
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configura a interface do widget."""
        # Container principal - layout horizontal compacto
        self.grid_columnconfigure(1, weight=1)
        
        # Indicador visual (círculo pequeno)
        self.status_indicator = customtkinter.CTkLabel(
            self,
            text="●",
            font=customtkinter.CTkFont(size=16),
            width=20,
            text_color="gray60"
        )
        self.status_indicator.grid(row=0, column=0, padx=(0, 5), sticky="w")
        
        # Label de status
        self.status_label = customtkinter.CTkLabel(
            self,
            text=self.app.translate("status_ready"),
            font=customtkinter.CTkFont(size=12),
            anchor="w"
        )
        self.status_label.grid(row=0, column=1, sticky="ew")
        
        # Inicialmente oculto
        self.grid_remove()
        
    def start_command(self, command_name):
        """Inicia indicação de comando em execução."""
        try:
            logging.debug(f"COMMAND_STATUS: Iniciando para comando '{command_name}'")
            self.current_command = command_name
            self.status = "running"
            
            # Mostrar widget
            self.grid()
            
            # Atualizar textos
            status_text = self.app.translate("status_running_command", command=command_name)
            self.status_label.configure(text=status_text)
            
            # Iniciar piscar laranja
            self._start_blink("orange")
            
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro ao iniciar comando '{command_name}': {e}")
    
    def finish_command(self, success=True, message=None):
        """Finaliza indicação de comando."""
        try:
            logging.debug(f"COMMAND_STATUS: Finalizando comando '{self.current_command}' sucesso={success}")
            
            # Parar piscar
            self._stop_blink()
            
            # Definir cor e mensagem baseado no resultado
            if success:
                self.status = "success"
                color = "green"
                if not message:
                    message = self.app.translate("status_command_completed", command=self.current_command or "comando")
            else:
                self.status = "error"
                color = "red"
                if not message:
                    message = self.app.translate("status_command_failed", command=self.current_command or "comando")
            
            # Atualizar visual
            self.status_indicator.configure(text_color=color)
            self.status_label.configure(text=message)
            
            # Auto-ocultar após 3 segundos
            self.after(3000, self._auto_hide)
            
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro ao finalizar comando: {e}")
    
    def hide_status(self):
        """Oculta o widget de status."""
        try:
            self._stop_blink()
            self.status = "idle"
            self.current_command = None
            self.grid_remove()
            logging.debug("COMMAND_STATUS: Widget ocultado")
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro ao ocultar: {e}")
    
    def _start_blink(self, color):
        """Inicia efeito de piscar."""
        try:
            self._stop_blink()  # Parar qualquer piscar anterior
            self.blink_active = True
            self.blink_thread = threading.Thread(
                target=self._blink_worker,
                args=(color,),
                daemon=True
            )
            self.blink_thread.start()
            logging.debug(f"COMMAND_STATUS: Piscar iniciado com cor '{color}'")
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro ao iniciar piscar: {e}")
    
    def _stop_blink(self):
        """Para o efeito de piscar."""
        try:
            self.blink_active = False
            if self.blink_thread and self.blink_thread.is_alive():
                # Aguardar thread parar
                self.blink_thread.join(timeout=1.0)
                logging.debug("COMMAND_STATUS: Piscar parado")
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro ao parar piscar: {e}")
    
    def _blink_worker(self, color):
        """Worker thread para fazer o indicador piscar."""
        bright_color = color
        dim_color = f"{color}40"  # Versão mais escura
        
        while self.blink_active:
            try:
                if self.winfo_exists():
                    # Alternar entre cores
                    current_color = bright_color if int(time.time() * 2) % 2 == 0 else dim_color
                    self.after_idle(lambda c=current_color: self._update_indicator_color(c))
                    time.sleep(0.5)
                else:
                    break
            except Exception as e:
                logging.debug(f"COMMAND_STATUS: Erro no piscar: {e}")
                break
    
    def _update_indicator_color(self, color):
        """Atualiza cor do indicador de forma thread-safe."""
        try:
            if self.blink_active and self.winfo_exists():
                self.status_indicator.configure(text_color=color)
        except Exception as e:
            logging.debug(f"COMMAND_STATUS: Erro ao atualizar cor: {e}")
    
    def _auto_hide(self):
        """Auto-oculta o widget após completar comando."""
        try:
            if self.status in ["success", "error"]:
                self.hide_status()
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro no auto-hide: {e}")
    
    def update_language(self):
        """Atualiza textos quando idioma muda."""
        try:
            if self.status == "idle":
                self.status_label.configure(text=self.app.translate("status_ready"))
            elif self.status == "running" and self.current_command:
                status_text = self.app.translate("status_running_command", command=self.current_command)
                self.status_label.configure(text=status_text)
        except Exception as e:
            logging.error(f"COMMAND_STATUS: Erro ao atualizar idioma: {e}")