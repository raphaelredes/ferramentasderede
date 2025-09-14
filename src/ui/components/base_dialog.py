# app/ui_components/base_dialog.py
# Classe base para todas as janelas de diálogo personalizadas da aplicação.

import customtkinter
import logging
import tkinter as tk
import platform

# Importar APIs do Windows se disponível
if platform.system() == "Windows":
    try:
        import ctypes
        from ctypes import wintypes
        _has_windows_api = True
    except ImportError:
        _has_windows_api = False
else:
    _has_windows_api = False

class BaseDialog(customtkinter.CTkToplevel):
    """
    Uma classe base para diálogos que usa a barra de título padrão do sistema
    operacional para garantir estabilidade máxima de foco e eventos.
    O diálogo é modal e sempre centralizado no monitor da janela principal.
    Inclui proteção anti-travamento com timeout automático e layout responsivo.
    """
    def __init__(self, app, title="", timeout_seconds=60, min_width=300, min_height=200, max_width=800, max_height=600):
        super().__init__(app)
        self.app = app
        self._timeout_seconds = timeout_seconds
        self._timeout_timer = None
        self._dialog_result = None
        self._is_modal_active = False
        
        # Parâmetros de responsividade
        self._min_width = min_width
        self._min_height = min_height
        self._max_width = max_width
        self._max_height = max_height
        self._auto_resize = False
        
        self.title(title)
        self.transient(app)
        
        # Impedir redimensionamento por padrão para melhor UX
        self.resizable(False, False)
        self.minsize(min_width, min_height)
        self.maxsize(max_width, max_height)

        # Manter a janela oculta inicialmente para evitar ghosting
        self.withdraw()

        # Configurar grid responsivo
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Configurar eventos
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._on_configure)
        
        # Aguardar que a janela seja construída e então centralizar
        self.after(1, self._schedule_smart_centering)

    def _on_close(self, event=None):
        """Manipula o fechamento do diálogo."""
        self._cancel_timeout()
        self._dialog_result = None
        self.destroy()
    
    def _on_configure(self, event=None):
        """Manipula eventos de redimensionamento para manter responsividade."""
        if event and event.widget == self and self._auto_resize:
            try:
                # Verificar se a janela está dentro dos limites
                current_width = self.winfo_width()
                current_height = self.winfo_height()
                
                # Ajustar se necessário
                new_width = max(self._min_width, min(current_width, self._max_width))
                new_height = max(self._min_height, min(current_height, self._max_height))
                
                if new_width != current_width or new_height != current_height:
                    self.geometry(f"{new_width}x{new_height}")
                    
            except Exception as e:
                logging.debug(f"Erro em _on_configure: {e}")
    
    def set_responsive_size(self, preferred_width=None, preferred_height=None):
        """Define um tamanho preferido responsivo baseado no conteúdo."""
        try:
            self.update_idletasks()
            
            # Obter tamanho necessário do conteúdo
            req_width = self.winfo_reqwidth()
            req_height = self.winfo_reqheight()
            
            # Usar valores preferidos ou calculados
            width = preferred_width or max(req_width, self._min_width)
            height = preferred_height or max(req_height, self._min_height)
            
            # Garantir que está dentro dos limites
            width = max(self._min_width, min(width, self._max_width))
            height = max(self._min_height, min(height, self._max_height))
            
            # Aplicar tamanho
            self.geometry(f"{width}x{height}")
            
        except Exception as e:
            logging.debug(f"Erro em set_responsive_size: {e}")
    
    def disable_auto_resize(self):
        """Desabilita o redimensionamento automático."""
        self._auto_resize = False
        self.resizable(False, False)
    
    def enable_auto_resize(self):
        """Habilita o redimensionamento automático."""
        self._auto_resize = True
        self.resizable(True, True)
        
    def _cancel_timeout(self):
        """Cancela o timer de timeout se estiver ativo."""
        if self._timeout_timer:
            try:
                self.after_cancel(self._timeout_timer)
            except:
                pass
            self._timeout_timer = None
    
    def _on_timeout(self):
        """Chamado quando o diálogo expira por timeout."""
        logging.warning(f"Diálogo '{self.title()}' encerrado por timeout após {self._timeout_seconds}s")
        self._dialog_result = None
        self._timeout_timer = None
        
        # Mostrar aviso para o usuário se possível
        if hasattr(self.app, 'show_info'):
            try:
                self.app.show_info(f"Diálogo fechado automaticamente após {self._timeout_seconds} segundos de inatividade.")
            except:
                pass
        
        self.destroy()
    
    def _start_timeout(self):
        """Inicia o timer de timeout."""
        if self._timeout_seconds > 0:
            self._timeout_timer = self.after(self._timeout_seconds * 1000, self._on_timeout)
            logging.debug(f"Timer de timeout iniciado para diálogo '{self.title()}' ({self._timeout_seconds}s)")
    
    def wait_with_timeout(self):
        """
        Versão do wait() com timeout automático.
        Retorna None se timeout, ou o resultado do diálogo.
        """
        try:
            # Iniciar timeout
            self._start_timeout()
            self._is_modal_active = True
            
            # Aguardar até que o diálogo seja fechado
            self.wait_window()
            
            return self._dialog_result
        
        except Exception as e:
            logging.error(f"Erro em wait_with_timeout: {e}")
            return None
        finally:
            self._cancel_timeout()
            self._is_modal_active = False

    def destroy(self, event=None):
        """
        Sobrescreve o método destroy para garantir que o grab seja liberado.
        """
        self._cancel_timeout()
        try:
            self.grab_release()
        except:
            pass
        super().destroy()

    def _schedule_smart_centering(self):
        """
        Agenda a centralização inteligente da janela no monitor correto.
        Usa o método da aplicação principal se disponível para detectar o monitor atual.
        """
        # Atualizar layout sem mostrar a janela
        self.update_idletasks()
        
        # Usar método inteligente da aplicação principal se disponível
        if hasattr(self.app, 'center_popup_on_main_window'):
            # Deixar a aplicação principal centralizar no monitor correto
            self.after(50, lambda: self._center_with_app_method())
        else:
            # Fallback para método tradicional
            self.after(50, self._center_on_screen)
    
    def _center_with_app_method(self):
        """
        Centraliza usando um método responsivo e confiável.
        """
        try:
            # Ajustar tamanho responsivo primeiro
            self.set_responsive_size()
            
            # Mostrar temporariamente para calcular o tamanho real
            self.deiconify()
            self.update_idletasks()
            
            # Obter dimensões reais da janela
            width = self.winfo_width()
            height = self.winfo_height()
            
            # Se as dimensões são muito pequenas, usar valores mínimos
            if width < self._min_width:
                width = self._min_width
            if height < self._min_height:
                height = self._min_height
            
            # Obter info do monitor da aplicação principal (VERSÃO MELHORADA)
            try:
                monitor_x, monitor_y, monitor_width, monitor_height = self.app.get_window_monitor_info()
                logging.debug(f"BaseDialog usando monitor: {monitor_x}, {monitor_y}, {monitor_width}x{monitor_height}")
            except Exception as e:
                logging.debug(f"Erro ao obter monitor info: {e}")
                # Fallback simples
                monitor_x, monitor_y = 0, 0
                monitor_width = self.winfo_screenwidth()
                monitor_height = self.winfo_screenheight()
            
            # Verificar se a janela cabe na tela
            if width > monitor_width * 0.9:
                width = int(monitor_width * 0.9)
            if height > monitor_height * 0.9:
                height = int(monitor_height * 0.9)
            
            # Calcular posição central
            x = monitor_x + (monitor_width - width) // 2
            y = monitor_y + (monitor_height - height) // 2
            
            # Garantir que não sai da tela
            x = max(monitor_x, min(x, monitor_x + monitor_width - width))
            y = max(monitor_y, min(y, monitor_y + monitor_height - height))
            
            # Aplicar posição e tamanho
            self.geometry(f"{width}x{height}+{x}+{y}")
            
            # Configurar como modal
            self.lift()
            self.focus_set()
            self.grab_set()
            
            logging.debug(f"Dialog responsivo centralizado em ({x}, {y}) com tamanho {width}x{height}")
            
        except Exception as e:
            logging.error(f"Erro na centralização responsiva: {e}")
            # Fallback final - centralizar na tela principal
            try:
                self.deiconify()
                self.update_idletasks()
                width = max(self.winfo_width(), self._min_width)
                height = max(self.winfo_height(), self._min_height)
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
                self.geometry(f"{width}x{height}+{x}+{y}")
                self.lift()
                self.focus_set()
                self.grab_set()
            except:
                pass

    def _schedule_centering(self):
        """
        Agenda a centralização mantendo a janela oculta para evitar ghosting.
        """
        # Atualizar layout sem mostrar a janela
        self.update_idletasks()
        
        # Agendar centralização mantendo a janela oculta
        self.after(50, self._center_on_screen)

    def _get_windows_screen_info(self):
        """
        Obtém informações de tela usando APIs do Windows para melhor precisão.
        """
        if not _has_windows_api:
            return None
            
        try:
            # Configurar DPI awareness se ainda não estiver configurado
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except:
                    pass
            
            # Obter o monitor principal
            hMonitor = ctypes.windll.user32.MonitorFromPoint(
                wintypes.POINT(0, 0), 
                1  # MONITOR_DEFAULTTOPRIMARY
            )
            
            # Estrutura para informações do monitor
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)
                ]
            
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
            
            if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(monitor_info)):
                rect = monitor_info.rcMonitor
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
                
        except Exception as e:
            logging.error(f"Error getting Windows screen info: {e}")
            
        return None

    def _get_screen_geometry(self):
        """
        Obtém a geometria real da tela considerando DPI scaling.
        """
        try:
            # Tentar usar APIs do Windows primeiro (mais precisas)
            windows_info = self._get_windows_screen_info()
            if windows_info:
                return windows_info
            
            # Método 1: Tentar obter geometria da janela pai
            if self.app and hasattr(self.app, 'winfo_x'):
                parent_x = self.app.winfo_x()
                parent_y = self.app.winfo_y()
                parent_width = self.app.winfo_width()
                parent_height = self.app.winfo_height()
                
                # Se a janela pai está visível, usar seu monitor
                if parent_width > 1 and parent_height > 1:
                    # Usar geometria da tela baseada na posição da janela pai
                    screen_width = self.winfo_screenwidth()
                    screen_height = self.winfo_screenheight()
                    
                    return 0, 0, screen_width, screen_height
            
            # Método 2: Usar geometria padrão da tela
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            
            return 0, 0, screen_width, screen_height
            
        except Exception as e:
            logging.error(f"Error getting screen geometry: {e}")
            # Fallback para valores padrão
            return 0, 0, 1920, 1080

    def _center_on_screen(self):
        """
        Centraliza a janela na tela considerando DPI scaling e múltiplos monitores.
        Mantém a janela oculta durante o processo para evitar ghosting.
        """
        try:
            # Atualizar para garantir que todas as dimensões estão corretas (janela ainda oculta)
            self.update_idletasks()
            
            # Obter dimensões da janela
            # Tentar diferentes métodos para obter o tamanho correto
            window_width = max(
                self.winfo_reqwidth(),
                self.winfo_width() if self.winfo_width() > 1 else 0
            )
            window_height = max(
                self.winfo_reqheight(),
                self.winfo_height() if self.winfo_height() > 1 else 0
            )
            
            # Valores mínimos para evitar janelas muito pequenas
            if window_width < 200:
                window_width = 400
            if window_height < 150:
                window_height = 300
            
            # Obter geometria da tela
            screen_x, screen_y, screen_width, screen_height = self._get_screen_geometry()
            
            # Calcular posição central
            pos_x = screen_x + (screen_width - window_width) // 2
            pos_y = screen_y + (screen_height - window_height) // 2
            
            # Garantir que a janela não saia da tela (margem de 50px)
            margin = 50
            pos_x = max(screen_x + margin, min(pos_x, screen_x + screen_width - window_width - margin))
            pos_y = max(screen_y + margin, min(pos_y, screen_y + screen_height - window_height - margin))
            
            # Definir posição enquanto a janela ainda está oculta
            geometry_string = f"+{int(pos_x)}+{int(pos_y)}"
            self.wm_geometry(geometry_string)
            
            # Agora mostrar a janela na posição correta
            self.deiconify()
            
            # Configurar como modal
            self.lift()
            self.focus_force()
            self.grab_set()
            
            logging.debug(f"Window positioned at ({pos_x}, {pos_y}) with size ({window_width}x{window_height}) on screen ({screen_x}, {screen_y}, {screen_width}x{screen_height})")
            
        except Exception as e:
            logging.error(f"Error centering window: {e}")
            # Fallback simples
            self._simple_center_fallback()

    def _simple_center_fallback(self):
        """
        Método de fallback simples para centralização sem ghosting.
        """
        try:
            # Verificar se a janela ainda existe antes de qualquer operação
            if not self.winfo_exists():
                return
                
            # A janela já deve estar oculta, mas garantir
            if self.winfo_viewable():
                self.withdraw()
            
            self.update_idletasks()
            
            # Verificar novamente se a janela existe após update_idletasks
            if not self.winfo_exists():
                return
            
            # Calcular centro usando método tkinter padrão
            width = self.winfo_reqwidth()
            height = self.winfo_reqheight()
            
            x = (self.winfo_screenwidth() // 2) - (width // 2)
            y = (self.winfo_screenheight() // 2) - (height // 2)
            
            # Aplicar posição enquanto oculta
            self.geometry(f"+{x}+{y}")
            
            # Verificar se a janela ainda existe antes de mostrar
            if not self.winfo_exists():
                return
                
            # Mostrar na posição correta
            self.deiconify()
            self.lift()
            self.focus_force()
            self.grab_set()
            
            logging.debug(f"Fallback centering applied: ({x}, {y})")
            
        except Exception as e:
            logging.error(f"Error in fallback centering: {e}")
            # Último recurso: mostrar a janela mesmo que não esteja perfeitamente centralizada
            try:
                if self.winfo_exists():
                    self.deiconify()
                    self.lift()
                    self.focus_force()
                    self.grab_set()
            except Exception as final_error:
                logging.error(f"Final fallback also failed: {final_error}")

    def wait(self):
        """
        Método conveniente para pausar a execução até que o diálogo seja fechado.
        """
        try:
            # Verificar se a janela ainda existe antes de aguardar
            if not self.winfo_exists():
                return
                
            # Usar a janela principal da aplicação como master
            self.app.wait_window(self)
        except Exception as e:
            logging.error(f"Error in dialog wait: {e}")
            # Último recurso: aguardar manualmente
            try:
                while self.winfo_exists():
                    self.update()
                    self.after(100)
            except:
                pass