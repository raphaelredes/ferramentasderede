# app/gui.py
# Classe principal da aplicação. Responsável por inicializar a janela,
# os gerenciadores e lidar com eventos de alto nível.

import os
import customtkinter
import threading
from tkinter import Menu
import logging
from PIL import Image, ImageTk
import platform
import time

# Importar bibliotecas da API do Windows, se disponíveis
PYWIN32_AVAILABLE = False
if os.name == 'nt':
    try:
        import win32gui
        import win32con
        import win32api
        PYWIN32_AVAILABLE = True
    except ImportError:
        logging.warning("Aviso: A biblioteca 'pywin32' não foi encontrada. As funções nativas de janela (maximizar) não funcionarão corretamente.")
        PYWIN32_AVAILABLE = False

# Importar APIs do Windows para DPI awareness se disponível
if platform.system() == "Windows":
    try:
        import ctypes
        from ctypes import wintypes
        _has_windows_api = True
    except ImportError:
        _has_windows_api = False
else:
    _has_windows_api = False

from .controller import AppController
from src.utils.translation import TranslationManager
from .settings_manager import AppSettingsManager
from src.ui.components.app_ui_manager import AppUIManager
from src.system.optimizer import PerformanceOptimizer
from src.system.advanced_optimizer import initialize_advanced_optimizer, get_advanced_optimizer
from src.ui.components.custom_dialogs import CustomMessageBox, PasswordInputDialog
from src.ui.components.credential_service import CredentialService, SALT_FILE, CRED_FILE
from src.ui.components.credential_manager_dialog import CredentialManagerDialog
from src.ui.components.security_info_dialog import SecurityInfoDialog
from src.ui.components.vault_prompt_dialog import VaultPromptDialog
from src.utils.performance_monitor import PerformanceMonitor

class App(customtkinter.CTk):
    def __init__(self, base_dir, loading_window=None):
        super().__init__()

        # Ocultar janela até que seja centralizada
        self.withdraw()

        self._is_closing = False
        self._callback_protection_active = False
        self.base_dir = base_dir
        self.loading_window = loading_window
        self._initialization_complete = False

        try:
            salt_path = os.path.join(self.base_dir, SALT_FILE)
            cred_path = os.path.join(self.base_dir, CRED_FILE)
            if os.path.exists(salt_path):
                os.remove(salt_path)
            if os.path.exists(cred_path):
                os.remove(cred_path)
        except OSError as e:
            logging.warning(f"Aviso: Não foi possível apagar os arquivos de credenciais da sessão anterior. Erro: {e}")
        
        # Inicializar otimizadores de performance
        self.performance_optimizer = PerformanceOptimizer(self)
        self.performance_optimizer.optimize_startup()
        
        # Inicializar monitor de performance e travamentos
        self.performance_monitor = PerformanceMonitor(self)
        self.performance_monitor.on_command_timeout = self._handle_command_timeout
        self.performance_monitor.on_high_resource_usage = self._handle_high_resource_usage
        self.performance_monitor.on_mainloop_freeze = self._handle_mainloop_freeze
        
        # Inicializar otimizador avançado se habilitado
        from src.config.settings import ADVANCED_PERFORMANCE_ENABLED
        if ADVANCED_PERFORMANCE_ENABLED:
            self.advanced_optimizer = initialize_advanced_optimizer(self)
            logging.debug("Advanced performance optimizer initialized")
        
        self.translator = TranslationManager(languages_dir=os.path.join(self.base_dir, "languages"))
        self.settings_manager = AppSettingsManager(self)
        self.cred_service = CredentialService(self.base_dir) # A chamada aqui está correta
        self.controller = AppController(self)
        self.ui_manager = AppUIManager(self, self.translator)

        self.favorites = []
        self.credential_cache = {}
        self.last_used_creds_by_domain = {}
        self.current_language = "pt-BR"
        self.current_appearance_mode = "System"
        self.ask_for_initial_info_on_select = True
        self.show_activity_help_dialog = True 
        self.vault_prompt_decision_made = False
        self.is_fully_loaded = False
        self.pending_tv_id_check_host = None
        self.host_statuses = {}
        
        # Sistema anti-flicker para menu de ações
        self._menu_action_timer = None
        self._last_menu_action = None
        self.ip_mismatches = {}
        self.stop_monitoring_event = threading.Event()
        self.status_update_interval = 60

        # Sistema de otimização de redimensionamento
        self._resize_timer = None
        self._resize_in_progress = False
        self._last_geometry = None
        self._resize_debounce_ms = 50   # 50ms de debounce - mais responsivo

        self.settings_manager.load_ui_preferences()
        
        self.app_ctk_icon = None
        self.app_photo_icon = None

        # Carregar ícones de forma síncrona
        self._load_icons_lazy()

        # Configurar tamanho responsivo baseado na resolução da tela
        self._setup_responsive_size()
        
        # Criar widgets rapidamente
        self.ui_manager.create_widgets()
        
        # Atualizar textos de forma síncrona
        self.ui_manager.update_ui_texts()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.toast_label = None
        
        # Sistema DEFINITIVO anti-travamento - valores estáticos
        self._setup_windows_explorer_dpi_system()
        self._init_static_monitor_system()
        self._setup_fluid_ui_system()
        self._fix_window_borders()
        
        # Marcar inicialização como completa
        self._initialization_complete = True

        # Se há uma janela de carregamento, notificar que a inicialização terminou
        if self.loading_window:
            self.after(100, lambda: self.loading_window.update_step("Interface criada", "Carregando dados em segundo plano..."))

    def _get_windows_screen_info(self):
        """Obtém informações básicas da tela."""
        try:
            if not _has_windows_api:
                return None
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            return 0, 0, screen_width, screen_height, screen_width, screen_height - 60
        except:
            return None
            
    def _setup_windows_explorer_dpi_system(self):
        """
        Configura DPI awareness EXATAMENTE como Windows Explorer.
        Usa DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2.
        """
        try:
            if platform.system() != "Windows":
                return
                
            import ctypes
            from ctypes import wintypes
            
            # Definir constantes do Windows (como Explorer usa)
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            
            try:
                # Método moderno (Windows 10 1703+) - como Windows Explorer
                ctypes.windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
                logging.debug("DPI Per-Monitor V2 configurado (como Windows Explorer)")
                
            except Exception:
                try:
                    # Fallback para Windows 8.1+ 
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
                    logging.debug("DPI Per-Monitor V1 configurado (fallback)")
                    
                except Exception:
                    try:
                        # Fallback para Windows Vista+
                        ctypes.windll.user32.SetProcessDPIAware()
                        logging.debug("DPI System Aware configurado (fallback básico)")
                        
                    except Exception as e:
                        logging.debug(f"Nenhum DPI awareness configurado: {e}")
            
            # Aguardar janela estar disponível antes de configurar estilos
            self.after(100, self._apply_window_styles)
                
        except Exception as e:
            logging.error(f"Erro ao configurar DPI como Windows Explorer: {e}")
    
    def _apply_window_styles(self):
        """
        Aplica estilos avançados da janela após ela estar completamente inicializada.
        Foca na eliminação de artefatos visuais e bordas brancas.
        """
        try:
            import ctypes
            
            hwnd = self.winfo_id()
            
            # Obter estilo atual
            current_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            
            # Remover flags que podem causar redesenhos/flicker em alguns hardwares
            WS_EX_COMPOSITED = 0x02000000
            WS_EX_NOREDIRECTIONBITMAP = 0x00200000
            safe_style = current_style & ~WS_EX_COMPOSITED & ~WS_EX_NOREDIRECTIONBITMAP
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, safe_style)
            
            # Configurar modo de desenho para eliminar flicker
            try:
                # Reverter políticas DWM que possam introduzir flicker
                DWM_WNDRATTR_NCRENDERING_POLICY = 2
                DWMNCRP_ENABLED = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWM_WNDRATTR_NCRENDERING_POLICY,
                    ctypes.byref(ctypes.c_int(DWMNCRP_ENABLED)),
                    ctypes.sizeof(ctypes.c_int)
                )
                
                logging.debug("DWM rendering policy aplicada")
                
            except Exception as e:
                logging.debug(f"Erro ao configurar DWM: {e}")
            
            # Atualização leve da janela para aplicar novos estilos sem forçar redraw total
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0004  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER
            )
            
            # Evitar redesenho completo aqui para não gerar flicker
            
            logging.debug("Estilos anti-border aplicados com sucesso")
            
        except Exception as e:
            logging.debug(f"Erro ao aplicar estilos de janela: {e}")

    def _init_static_monitor_system(self):
        """
        Sistema DEFINITIVO - valores completamente estáticos, ZERO APIs.
        """
        try:
            # Detectar resolução UMA VEZ na inicialização (quando é seguro)
            try:
                initial_width = self.winfo_screenwidth()
                initial_height = self.winfo_screenheight()
                logging.debug(f"Resolução inicial detectada: {initial_width}x{initial_height}")
            except:
                # Se falhar mesmo na inicialização, usar padrão
                initial_width, initial_height = 1920, 1080
                logging.debug("Usando resolução padrão: 1920x1080")
            
            # Cache ESTÁTICO - nunca mais será alterado
            self._static_screen_width = initial_width
            self._static_screen_height = initial_height
            
            # Configurações comuns de monitores (baseado na resolução detectada)
            self._static_monitor_configs = [
                # Monitor principal (sempre primeiro)
                {'x': 0, 'y': 0, 'width': self._static_screen_width, 'height': self._static_screen_height, 'primary': True},
                # Monitor à direita
                {'x': self._static_screen_width, 'y': 0, 'width': 1920, 'height': 1080},
                # Monitor à esquerda
                {'x': -1920, 'y': 0, 'width': 1920, 'height': 1080},
                # Monitor 4K à direita
                {'x': self._static_screen_width, 'y': 0, 'width': 3840, 'height': 2160},
                # Monitor acima
                {'x': 0, 'y': -1080, 'width': 1920, 'height': 1080},
                # Monitor abaixo
                {'x': 0, 'y': self._static_screen_height, 'width': 1920, 'height': 1080},
            ]
            
            # Sistema de detecção de movimento
            self._last_window_position = None
            self._movement_detected = False
            self._movement_timer = None
            
            # Sistema otimizado de redimensionamento com debouncing
            self.bind('<Configure>', self._on_configure_optimized)
            
            logging.debug(f"Sistema estático inicializado com {len(self._static_monitor_configs)} configurações")
            
        except Exception as e:
            logging.error(f"Erro na inicialização do sistema estático: {e}")
            # Fallback absoluto
            self._static_screen_width = 1920
            self._static_screen_height = 1080
            self._static_monitor_configs = [
                {'x': 0, 'y': 0, 'width': 1920, 'height': 1080, 'primary': True}
            ]
    
    def _setup_fluid_ui_system(self):
        """
        Sistema de UI FLUIDA - configuração simplificada sem interferência com cliques.
        """
        try:
            # Desabilitar escalonamento automático do CustomTkinter
            import customtkinter
            
            # Forçar escala fixa (1.0) para evitar reescalonamento durante mudança de monitor
            customtkinter.set_widget_scaling(1.0)
            customtkinter.set_window_scaling(1.0)
            
            # Configurar sistema de dimensões fixas
            self._ui_frozen = False
            self._base_widget_sizes = {}
            
            # Configurar fonte base fixa
            self._base_font_size = 13
            
            logging.debug("Sistema de UI fluida configurado (sem interferência de eventos)")
            
        except Exception as e:
            logging.error(f"Erro ao configurar UI fluida: {e}")

    def _fix_window_borders(self):
        """
        Corrige bordas brancas e problemas visuais da janela.
        Remove completamente qualquer borda visível.
        """
        try:
            # Configurar cor de fundo da janela principal
            import customtkinter
            
            # Obter cor de fundo baseada no tema atual
            current_appearance = customtkinter.get_appearance_mode()
            
            if current_appearance.lower() == "dark":
                # Cores para tema escuro
                bg_color = "#212121"  # Cinza escuro
                fg_color = "#2b2b2b"  # Cinza um pouco mais claro
            else:
                # Cores para tema claro
                bg_color = "#f0f0f0"  # Cinza claro
                fg_color = "#ffffff"  # Branco
            
            # Configurar cor de fundo da janela principal
            self.configure(fg_color=bg_color)
            
            # Configurações adicionais para eliminar bordas
            try:
                # Remover bordas da janela se possível
                import tkinter as tk
                
                # Configurar highlightthickness como 0 para remover bordas
                self.configure(highlightthickness=0)
                
                # Configurar bd (border) como 0
                self.configure(bd=0)
                
                # Agendar aplicação de estilos mais avançados
                self.after(50, lambda: self._apply_advanced_border_fix(bg_color))
                
            except Exception as e:
                logging.debug(f"Erro nas configurações de borda: {e}")
            
            # Definir cor padrão para frames transparentes
            self._default_bg_color = bg_color
            
            logging.debug(f"Bordas da janela configuradas para tema {current_appearance}")
                
        except Exception as e:
            logging.error(f"Erro ao configurar bordas da janela: {e}")
    
    def _apply_advanced_border_fix(self, bg_color):
        """
        Aplica correções avançadas de borda após a janela estar totalmente carregada.
        """
        try:
            # Forçar cor de fundo em TODOS os níveis possíveis
            self.configure(background=bg_color)
            
            # Tentar configurar cores adicionais do Tkinter
            try:
                self.configure(bg=bg_color)
                self.tk.call('wm', 'attributes', self._w, '-alpha', 1.0)  # 100% opaco por padrão
            except:
                pass
            
            # Forçar refresh em todos os widgets filhos
            try:
                for widget in self.winfo_children():
                    widget.update_idletasks()
            except:
                pass
            
            # Atualizar e forçar redesenho MÚLTIPLAS vezes
            for i in range(3):
                self.update_idletasks()
                self.update()
            
            logging.debug("Correções avançadas de borda aplicadas com múltiplos refreshes")
            
        except Exception as e:
            logging.debug(f"Erro ao aplicar correções avançadas: {e}")

    def _load_icons_lazy(self):
        """Carrega ícones de forma lazy para acelerar inicialização."""
        try:
            # Cache de ícones para evitar recarregamento
            if hasattr(self, '_icon_cache') and self._icon_cache:
                self.app_ctk_icon = self._icon_cache.get('ctk_icon')
                self.app_photo_icon = self._icon_cache.get('photo_icon')
                if self.app_ctk_icon and self.app_photo_icon:
                    return
            
            icon_light_path = os.path.join(self.base_dir, "assets", "icon_light.png")
            icon_dark_path = os.path.join(self.base_dir, "assets", "icon_dark.png")
            icon_ico_path = os.path.join(self.base_dir, "assets", "icon.ico")

            if os.path.exists(icon_light_path) and os.path.exists(icon_dark_path):
                # Carregar ícones apenas uma vez
                pil_light_image = Image.open(icon_light_path)
                pil_dark_image = Image.open(icon_dark_path)
                self.app_ctk_icon = customtkinter.CTkImage(light_image=pil_light_image, dark_image=pil_dark_image, size=(24, 24))
                self.app_photo_icon = ImageTk.PhotoImage(pil_dark_image)
                
                # Armazenar no cache
                if not hasattr(self, '_icon_cache'):
                    self._icon_cache = {}
                self._icon_cache['ctk_icon'] = self.app_ctk_icon
                self._icon_cache['photo_icon'] = self.app_photo_icon
            
            icon_set = False
            if os.name == 'nt' and os.path.exists(icon_ico_path):
                self.iconbitmap(default=icon_ico_path)
                icon_set = True
            
            if not icon_set and self.app_photo_icon:
                try:
                    self.iconphoto(True, self.app_photo_icon)
                except Exception as e:
                    logging.debug(f"Erro ao definir iconphoto: {e}")
                    self.app_photo_icon = None

            if not self.app_ctk_icon and not icon_set:
                 logging.debug("Ícones não encontrados na pasta 'assets/'")

        except Exception as e:
            logging.debug(f"Erro ao carregar ícones: {e}")

    def _setup_responsive_size(self):
        """
        Configura o tamanho da janela de forma responsiva baseada na resolução da tela.
        """
        try:
            # Obter informações da tela
            windows_info = self._get_windows_screen_info()
            if windows_info:
                screen_width, screen_height = windows_info[2], windows_info[3]
                work_width, work_height = windows_info[4], windows_info[5]
            else:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                work_width, work_height = screen_width, screen_height - 60  # Estimar barra de tarefas
            
            # Usar 80% do tamanho da área de trabalho (sem barra de tarefas)
            width = int(work_width * 0.8)
            height = int(work_height * 0.8)
            
            # Garantir tamanho mínimo para usabilidade
            width = max(width, 1200)
            height = max(height, 700)
            
            # Garantir tamanho máximo para telas muito grandes
            width = min(width, 2400)  # Máximo para telas muito grandes
            height = min(height, 1400)
            
            # Aplicar configurações usando wm_geometry (mais confiável)
            self.wm_geometry(f"{width}x{height}")
            self.minsize(800, 600)  # Tamanho mínimo atualizado
            
            # Salvar dimensões para centralização
            self._window_width = width
            self._window_height = height
            
            logging.debug(f"Responsive size configured: {width}x{height} for screen {screen_width}x{screen_height}")
            
        except Exception as e:
            logging.error(f"Error setting responsive size: {e}")
            # Fallback para tamanho padrão (aproximadamente 80% de Full HD)
            self.wm_geometry("1536x864")  # 80% de 1920x1080
            self.minsize(800, 600)
            self._window_width = 1536
            self._window_height = 864

    def _center_and_show_main_window(self):
        """
        VERSÃO ULTRA-VISÍVEL: Garante que a janela sempre apareça.
        """
        try:
            # Obter dimensões da tela
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            # Tamanho: 50% da tela
            target_w = max(800, min(int(screen_w * 0.5), 1600))
            target_h = max(600, min(int(screen_h * 0.5), 1200))

            # Posição central
            pos_x = (screen_w - target_w) // 2
            pos_y = (screen_h - target_h) // 2

            # SEQUÊNCIA ULTRA-VISÍVEL
            self.withdraw()  # Ocultar primeiro

            # Definir geometria
            final_geometry = f"{target_w}x{target_h}+{pos_x}+{pos_y}"
            self.geometry(final_geometry)

            # FORÇAR VISIBILIDADE MÁXIMA
            self.deiconify()  # Mostrar
            self.lift()       # Para frente
            self.attributes('-topmost', True)  # Por cima de tudo
            self.focus_force()  # Foco
            self.update()       # Atualizar

            # Remover topmost após garantir visibilidade
            self.after(100, lambda: self.attributes('-topmost', False))

            logging.info(f"JANELA ULTRA-VISÍVEL: {final_geometry} em tela {screen_w}x{screen_h}")

            # Log de verificação
            self.after(200, self._log_final_position)

        except Exception as e:
            logging.error(f"Erro centralização: {e}")
            # Fallback de emergência
            try:
                self.geometry("800x600+100+100")
                self.deiconify()
                self.lift()
                self.attributes('-topmost', True)
                self.after(100, lambda: self.attributes('-topmost', False))
            except:
                pass

    def _log_final_position(self):
        """Log da posição final para debug."""
        try:
            real_geo = self.geometry()
            real_state = self.state()
            real_x, real_y = self.winfo_x(), self.winfo_y()
            real_w, real_h = self.winfo_width(), self.winfo_height()

            logging.info(f"POSIÇÃO FINAL CONFIRMADA:")
            logging.info(f"  Geometria: {real_geo}")
            logging.info(f"  Estado: {real_state}")
            logging.info(f"  Posição: ({real_x}, {real_y})")
            logging.info(f"  Tamanho: {real_w}x{real_h}")

        except Exception as e:
            logging.error(f"Erro verificando posição final: {e}")

    def _verify_position(self):
        """Verifica a posição real da janela."""
        try:
            real_geometry = self.geometry()
            real_x = self.winfo_x()
            real_y = self.winfo_y()
            real_w = self.winfo_width()
            real_h = self.winfo_height()

            logging.info(f"POSIÇÃO REAL: geometry='{real_geometry}', x={real_x}, y={real_y}, size={real_w}x{real_h}")

        except Exception as e:
            logging.error(f"Erro verificação posição: {e}")

    def show_main_window(self):
        """
        Método público para mostrar a janela principal centralizada.
        Deve ser chamado após o carregamento completo.
        """
        self._center_and_show_main_window()
    
    def get_window_monitor_info(self):
        """
        Retorna informações do monitor onde a janela principal está localizada.
        VERSÃO OTIMIZADA com cache para reduzir chamadas de API.
        """
        try:
            # Cache de informações do monitor para reduzir overhead
            if not hasattr(self, '_monitor_info_cache'):
                self._monitor_info_cache = {}
                self._monitor_cache_timestamp = 0
            
            current_time = time.time()
            # Cache válido por 1 segundo para evitar muitas chamadas de API
            if current_time - self._monitor_cache_timestamp < 1.0 and self._monitor_info_cache:
                return self._monitor_info_cache.get('cached_info', (0, 0, 1920, 1080))
            
            # Obter posição REAL da janela principal
            main_x = self.winfo_x()
            main_y = self.winfo_y()
            main_width = self.winfo_width()
            main_height = self.winfo_height()
            
            # Se a janela ainda não tem geometria válida, usar valores padrão
            if main_width <= 1 or main_height <= 1:
                return 0, 0, getattr(self, '_static_screen_width', 1920), getattr(self, '_static_screen_height', 1080)
            
            # Calcular centro da janela principal
            center_x = main_x + main_width // 2
            center_y = main_y + main_height // 2
            
            # Detectar monitor baseado no centro da janela
            try:
                import ctypes
                
                # Usar API do Windows para detectar monitor correto
                point = ctypes.wintypes.POINT(center_x, center_y)
                monitor = ctypes.windll.user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
                
                if monitor:
                    class MONITORINFO(ctypes.Structure):
                        _fields_ = [
                            ("cbSize", ctypes.wintypes.DWORD),
                            ("rcMonitor", ctypes.wintypes.RECT),
                            ("rcWork", ctypes.wintypes.RECT),
                            ("dwFlags", ctypes.wintypes.DWORD)
                        ]
                    
                    monitor_info = MONITORINFO()
                    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                    
                    if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
                        rect = monitor_info.rcMonitor
                        monitor_x = rect.left
                        monitor_y = rect.top
                        monitor_width = rect.right - rect.left
                        monitor_height = rect.bottom - rect.top
                        
                        # Armazenar no cache
                        result = (monitor_x, monitor_y, monitor_width, monitor_height)
                        self._monitor_info_cache['cached_info'] = result
                        self._monitor_cache_timestamp = current_time
                        
                        logging.debug(f"Monitor detectado: {monitor_x}, {monitor_y}, {monitor_width}x{monitor_height}")
                        return result
                        
            except Exception as e:
                logging.debug(f"Erro na detecção do monitor: {e}")
            
            # Fallback: usar toda a área da tela
            try:
                import ctypes
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                result = (0, 0, screen_width, screen_height)
                
                # Armazenar no cache
                self._monitor_info_cache['cached_info'] = result
                self._monitor_cache_timestamp = current_time
                
                return result
            except:
                # Fallback final: valores estáticos
                result = (0, 0, getattr(self, '_static_screen_width', 1920), getattr(self, '_static_screen_height', 1080))
                self._monitor_info_cache['cached_info'] = result
                self._monitor_cache_timestamp = current_time
                return result
                
        except Exception as e:
            logging.error(f"Erro em get_window_monitor_info: {e}")
            # Fallback final: valores estáticos
            return 0, 0, getattr(self, '_static_screen_width', 1920), getattr(self, '_static_screen_height', 1080)
    

    
    def center_popup_on_main_window(self, popup_window, width=None, height=None):
        """
        Centraliza uma janela popup no mesmo monitor da janela principal.
        VERSÃO MELHORADA que força o popup no monitor correto.
        
        Args:
            popup_window: A janela popup a ser centralizada
            width: Largura desejada (opcional, usa o tamanho atual se não especificado)
            height: Altura desejada (opcional, usa o tamanho atual se não especificado)
        """
        try:
            # Múltiplas atualizações para garantir dimensões corretas
            for i in range(3):
                self.update_idletasks()
                popup_window.update_idletasks()
            
            # Obter posição REAL da janela principal
            main_x = self.winfo_x()
            main_y = self.winfo_y()
            main_width = self.winfo_width()
            main_height = self.winfo_height()
            
            # Se ainda não temos geometria válida, aguardar
            if main_width <= 1 or main_height <= 1:
                self.after(20, lambda: self.center_popup_on_main_window(popup_window, width, height))
                return
            
            # Obter dimensões da popup
            if width is None:
                width = max(popup_window.winfo_reqwidth(), 300)
            if height is None:
                height = max(popup_window.winfo_reqheight(), 200)
                
            # Se as dimensões ainda são muito pequenas, usar padrões
            if width < 100:
                width = 400
            if height < 100:
                height = 300
            
            # MÉTODO MELHORADO: Usar detecção correta do monitor
            try:
                monitor_x, monitor_y, monitor_width, monitor_height = self.get_window_monitor_info()
                
                # Centralizar no monitor detectado
                pos_x = monitor_x + (monitor_width - width) // 2
                pos_y = monitor_y + (monitor_height - height) // 2
                
                logging.debug(f"Usando monitor detectado: {monitor_x}, {monitor_y}, {monitor_width}x{monitor_height}")
                
            except:
                # Fallback: posição baseada na janela principal
                pos_x = main_x + (main_width - width) // 2
                pos_y = main_y + (main_height - height) // 2
                
                logging.debug(f"Fallback: usando posição da janela principal")
            
            # Garantir que não sai completamente da tela
            try:
                import ctypes
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                
                # Ajustar se necessário para ficar na tela
                if pos_x < 0:
                    pos_x = 50
                if pos_y < 0:
                    pos_y = 50
                if pos_x + width > screen_width:
                    pos_x = screen_width - width - 50
                if pos_y + height > screen_height:
                    pos_y = screen_height - height - 50
                    
            except:
                # Se APIs Windows falharem, apenas garantir que não seja negativo
                pos_x = max(pos_x, 50)
                pos_y = max(pos_y, 50)
            
            # PRIMEIRO: Ocultar popup durante posicionamento para evitar flicker
            popup_window.withdraw()
            
            # SEGUNDO: Aplicar geometria completa
            popup_window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
            
            # TERCEIRO: Atualizar e mostrar
            popup_window.update_idletasks()
            popup_window.deiconify()
            
            # QUARTO: Forçar foco e trazer para frente
            popup_window.lift()
            popup_window.focus_set()
            popup_window.grab_set()  # Tornar modal
            
            logging.debug(f"Popup FORÇADO em ({pos_x}, {pos_y}) baseado na janela principal ({main_x}, {main_y})")
            
        except Exception as e:
            logging.error(f"Erro ao centralizar popup: {e}")
            # Fallback: posição simples relativa à janela principal
            try:
                main_x = self.winfo_x()
                main_y = self.winfo_y()
                fallback_x = main_x + 100
                fallback_y = main_y + 100
                popup_window.geometry(f"{width or 400}x{height or 300}+{fallback_x}+{fallback_y}")
                popup_window.lift()
                popup_window.focus_set()
            except:
                popup_window.geometry(f"{width or 400}x{height or 300}")

    def translate(self, text_key, **kwargs):
        """Traduz uma chave de texto com cache otimizado."""
        try:
            # Criar chave de cache única
            cache_key = f"{text_key}_{self.current_language}"
            
            # Verificar cache primeiro
            if hasattr(self, '_translation_cache') and cache_key in self._translation_cache:
                cached_result = self._translation_cache[cache_key]
                if kwargs:
                    return cached_result.format(**kwargs)
                return cached_result
            
            # Traduzir usando o tradutor
            translated_text = self.translator.translate(text_key, **kwargs)
            
            # Armazenar no cache (sem formatação para permitir reutilização)
            if hasattr(self, '_translation_cache'):
                if len(self._translation_cache) > 1000:  # Limite do cache
                    self._translation_cache.clear()
                self._translation_cache[cache_key] = translated_text
            
            return translated_text
            
        except Exception as e:
            logging.warning(f"Erro na tradução de '{text_key}': {e}")
            return text_key

    def clear_translation_cache(self):
        """Limpa o cache de traduções quando o idioma muda."""
        if hasattr(self, '_translation_cache'):
            self._translation_cache.clear()
            logging.debug("Cache de traduções limpo")

    def force_update_translations(self):
        """Força atualização de todas as traduções na aplicação."""
        try:
            logging.debug("Iniciando atualização forçada de traduções")
            
            # Limpar cache de traduções
            self.clear_translation_cache()
            
            # Atualizar textos da UI principal
            if hasattr(self, 'ui_manager'):
                self.ui_manager.update_ui_texts()
            
            # Atualizar abas de host
            if hasattr(self, 'host_tab_view'):
                self.host_tab_view.update_language()
            
            # Forçar atualização de todos os widgets visíveis
            self._force_update_visible_widgets()
            
            logging.debug("Traduções forçadamente atualizadas em toda a aplicação")
            
        except Exception as e:
            logging.error(f"Erro ao forçar atualização de traduções: {e}")

    def _force_update_visible_widgets(self):
        """Força atualização de todos os widgets visíveis."""
        try:
            # Atualizar todos os widgets filhos da janela principal
            for widget in self.winfo_children():
                if hasattr(widget, 'update_language') and callable(widget.update_language):
                    try:
                        widget.update_language()
                    except Exception as e:
                        logging.warning(f"Erro ao atualizar widget: {e}")
                
                # Recursivamente atualizar widgets filhos
                self._update_widget_children(widget)
                        
        except Exception as e:
            logging.error(f"Erro ao atualizar widgets visíveis: {e}")

    def _update_widget_children(self, parent_widget):
        """Atualiza recursivamente todos os widgets filhos."""
        try:
            for child in parent_widget.winfo_children():
                if hasattr(child, 'update_language') and callable(child.update_language):
                    try:
                        child.update_language()
                    except Exception as e:
                        logging.warning(f"Erro ao atualizar widget filho: {e}")
                
                # Continuar recursivamente
                self._update_widget_children(child)
                
        except Exception as e:
            logging.warning(f"Erro ao atualizar widgets filhos: {e}")

    def handle_action_menu(self, choice_key: str):
        """
        Manipula as ações do menu Gestão.
        Sistema melhorado com debounce para evitar flicker e múltiplas execuções.
        """
        import logging
        import time
        
        # Verificar se é uma ação válida (não o título do menu)
        if choice_key == self.translate("actions_menu_title"):
            # Usuário clicou no menu mas não selecionou uma opção
            logging.debug("Menu título selecionado - ignorando para evitar flicker")
            return
            
        # Sistema de debounce para evitar múltiplas execuções
        current_time = time.time()
        if (self._last_menu_action and 
            self._last_menu_action.get('choice') == choice_key and 
            current_time - self._last_menu_action.get('time', 0) < 1.0):
            logging.debug(f"Ação de menu ignorada (debounce): {choice_key}")
            return
        
        # Cancelar timer anterior se existir
        if self._menu_action_timer:
            try:
                self.after_cancel(self._menu_action_timer)
            except:
                pass
            self._menu_action_timer = None
        
        # Atualizar último comando
        self._last_menu_action = {'choice': choice_key, 'time': current_time}
        
        logging.debug(f"Executando ação do menu: {choice_key}")
        
        # Executar a ação apenas se for uma opção válida
        action_executed = False
        
        try:
            if choice_key == "title_remove_hosts":
                self.controller.open_remove_host_dialog()
                action_executed = True
            elif choice_key == "actions_import":
                self.controller.import_hosts()
                action_executed = True
            elif choice_key == "actions_export":
                self.controller.export_hosts()
                action_executed = True
            elif choice_key == "actions_manage_creds":
                self.open_credential_manager()
                action_executed = True
            else:
                logging.warning(f"Ação de menu desconhecida: {choice_key}")
                
        except Exception as e:
            logging.error(f"Erro ao executar ação do menu {choice_key}: {e}")
            action_executed = False
        
        # Só resetar o menu se uma ação foi executada com sucesso
        if action_executed:
            # Delay ligeiramente maior para garantir que a ação seja completada
            self._menu_action_timer = self.after(100, lambda: self._reset_action_menu())
    
    def _reset_action_menu(self):
        """
        Reseta o menu de ações para o título padrão de forma segura.
        """
        try:
            if hasattr(self, 'actions_menu') and self.actions_menu:
                current_value = self.actions_menu.get()
                target_value = self.translate("actions_menu_title")
                
                # Só resetar se necessário para evitar flicker desnecessário
                if current_value != target_value:
                    self.actions_menu.set(target_value)
                    
        except Exception as e:
            import logging
            logging.debug(f"Erro ao resetar menu de ações: {e}")

    def open_credential_manager(self):
        if not os.path.exists(os.path.join(self.base_dir, SALT_FILE)):
            dialog = VaultPromptDialog(self)
            self.center_popup_on_main_window(dialog, 400, 300)
            dialog.wait()
            if not dialog.get_result():
                self.show_info(self.translate("user_cancelled_operation"))
                return
            title, prompt = self.translate("vault_create_title"), self.translate("vault_create_prompt")
        else:
            title, prompt = self.translate("vault_unlock_title"), self.translate("vault_unlock_prompt")

        password_dialog = PasswordInputDialog(self, title, prompt)
        self.center_popup_on_main_window(password_dialog, 400, 200)
        password = password_dialog.get_input()
        
        if password is None:
            self.show_info(self.translate("user_cancelled_operation"))
            return
        
        if not password: # Senha em branco
            # Não faz nada, simplesmente não desbloqueia
            return

        if not self.cred_service.unlock(password):
            self.show_error(self.translate("vault_wrong_master_password"))
            return
        
        manager_dialog = CredentialManagerDialog(self, self.cred_service)
        self.center_popup_on_main_window(manager_dialog, 600, 500)
        manager_dialog.wait()
        
        self.cred_service.lock()
        self.show_toast_notification(self.translate("vault_locked_after_management"))

    def _on_configure_optimized(self, event):
        """Sistema otimizado de redimensionamento com debouncing."""
        # Ignorar eventos que não são da janela principal
        if event.widget != self:
            return

        try:
            # Verificar se a geometria realmente mudou
            current_geometry = f"{event.width}x{event.height}"
            if current_geometry == self._last_geometry:
                return

            self._last_geometry = current_geometry

            # Cancelar timer anterior se existir
            if self._resize_timer:
                self.after_cancel(self._resize_timer)

            # Marcar que resize está em progresso
            self._resize_in_progress = True

            # Agendar processamento com debounce
            self._resize_timer = self.after(self._resize_debounce_ms, self._process_resize)

        except Exception as e:
            logging.error(f"Erro no redimensionamento otimizado: {e}")

    def _process_resize(self):
        """Processa o redimensionamento após o debounce."""
        try:
            if not self._resize_in_progress:
                return

            # Operações mínimas durante resize
            # Apenas salvar geometria se necessário
            if hasattr(self, 'settings_manager') and self.settings_manager:
                try:
                    # Salvar geometria de forma assíncrona se método existir
                    def save_geometry():
                        try:
                            if hasattr(self.settings_manager, 'save_window_geometry'):
                                self.settings_manager.save_window_geometry()
                            else:
                                # Salvar configurações UI que podem incluir geometria
                                self.settings_manager.save_ui_preferences()
                        except Exception as e:
                            logging.debug(f"Erro ao salvar geometria: {e}")

                    # Executar salvamento em thread daemon para não bloquear UI
                    save_thread = threading.Thread(target=save_geometry, daemon=True)
                    save_thread.start()

                except Exception as e:
                    logging.debug(f"Erro no salvamento de geometria: {e}")

            # Resetar flag
            self._resize_in_progress = False
            self._resize_timer = None

        except Exception as e:
            logging.error(f"Erro no processamento de resize: {e}")
            self._resize_in_progress = False
            self._resize_timer = None

    def on_closing(self):
        # Sempre perguntar confirmação, mesmo com comandos em andamento
        if self.ask_yes_no(self.translate("confirm_exit_title"), self.translate("confirm_exit_message")):
            self._is_closing = True

            # Iniciar processo de finalização robusta incluindo simulação de Ctrl+C
            self._execute_complete_shutdown()

    def _execute_complete_shutdown(self):
        """Executa finalização completa com simulação de Ctrl+C."""
        import threading
        import time
        import signal

        def shutdown_thread():
            try:
                logging.info("Iniciando finalização completa da aplicação...")

                # Parar sistemas de monitoramento primeiro
                self._loop_active = False
                self._watchdog_active = False

                # Parar threads de monitoramento
                try:
                    self.stop_monitoring_event.set()
                except Exception as e:
                    logging.debug(f"Erro ao parar threads: {e}")

                # Aguardar threads pararem
                time.sleep(0.2)

                # Limpar callbacks pendentes ANTES de outras operações
                self._cancel_all_pending_callbacks()

                # Limpar otimizadores de performance
                if hasattr(self, 'performance_optimizer'):
                    try:
                        self.performance_optimizer.cleanup()
                    except Exception as e:
                        logging.debug(f"Erro ao limpar performance_optimizer: {e}")

                if hasattr(self, 'advanced_optimizer'):
                    try:
                        self.advanced_optimizer.cleanup()
                    except Exception as e:
                        logging.debug(f"Erro ao limpar advanced_optimizer: {e}")

                # Parar monitor de performance
                if hasattr(self, 'performance_monitor'):
                    try:
                        self.performance_monitor.stop_monitoring()
                    except Exception as e:
                        logging.debug(f"Erro ao parar performance_monitor: {e}")

                # Operações de limpeza
                try:
                    self.cred_service.lock()
                except Exception as e:
                    logging.debug(f"Erro ao bloquear credenciais: {e}")

                # Remover arquivos temporários
                try:
                    if os.path.exists(os.path.join(self.base_dir, CRED_FILE)):
                        os.remove(os.path.join(self.base_dir, CRED_FILE))
                    if os.path.exists(os.path.join(self.base_dir, SALT_FILE)):
                        os.remove(os.path.join(self.base_dir, SALT_FILE))
                except OSError as e:
                    logging.debug(f"Erro ao apagar arquivos do cofre: {e}")

                # Salvar configurações
                try:
                    self.settings_manager.save_ui_preferences()
                except Exception as e:
                    logging.debug(f"Erro ao salvar configurações: {e}")

                # Fechar diálogos filhos
                self._close_child_windows()

                # Chamar limpeza de callbacks final
                self._cleanup_callbacks()

                # Aguardar para garantir que threads parem completamente
                time.sleep(0.3)

                # Força parada de todos os handlers de eventos
                try:
                    self.quit()
                except Exception as e:
                    logging.debug(f"Erro no quit: {e}")

                # Aguardar callbacks finalizarem
                time.sleep(0.1)

                # Destruir janela
                try:
                    self.destroy()
                except Exception as e:
                    logging.debug(f"Erro no destroy: {e}")

                # Aguardar destruição completar
                time.sleep(0.1)

                # Força saída do mainloop do tkinter
                try:
                    import tkinter
                    if hasattr(tkinter, '_default_root') and tkinter._default_root:
                        tkinter._default_root.quit()
                        tkinter._default_root.destroy()
                except Exception as e:
                    logging.debug(f"Erro ao limpar tkinter root: {e}")

                # Verificar threads ativas e forçar finalização
                active_threads = [t for t in threading.enumerate() if t != threading.current_thread() and not t.daemon]
                if active_threads:
                    logging.debug(f"Threads ainda ativas: {[t.name for t in active_threads]}")

                # SEMPRE simular Ctrl+C para garantir finalização completa
                logging.info("Simulando Ctrl+C para finalização completa...")
                time.sleep(0.1)
                os.kill(os.getpid(), signal.SIGINT)

            except Exception as e:
                logging.error(f"Erro durante shutdown completo: {e}")
                # Força saída mesmo se houver erro
                import sys
                sys.exit(0)

        # Executar shutdown em thread separada para não bloquear
        shutdown_t = threading.Thread(target=shutdown_thread, daemon=True)
        shutdown_t.start()

    def _close_child_windows(self):
        """Fecha todas as janelas filhas de forma segura."""
        try:
            for child in list(self.winfo_children()):
                if hasattr(child, 'destroy'):
                    try:
                        child.destroy()
                    except Exception as e:
                        logging.debug(f"Erro ao fechar janela filha: {e}")
        except Exception as e:
            logging.debug(f"Erro ao enumerar janelas filhas: {e}")
    
    def show_security_info_dialog(self):
        dialog = SecurityInfoDialog(self)
        self.center_popup_on_main_window(dialog, 500, 400)
        dialog.wait()

    def show_winrm_error_dialog(self):
        dialog = CustomMessageBox(self,
            title=self.translate("winrm_error_title"),
            message=self.translate("winrm_error_message"),
            buttons=[self.translate("label_ok")]
        )
        self.center_popup_on_main_window(dialog, 400, 200)
        dialog.wait()

    def show_error(self, message, widget_to_focus=None):
        dialog = CustomMessageBox(self, title=self.translate("label_error"), message=message, buttons=[self.translate("label_ok")], text_color="#f29d9d")
        dialog.wait()
        if widget_to_focus:
            self.after(10, widget_to_focus.focus_set)
    
    # Métodos de callback para o monitor de performance
    
    def _handle_command_timeout(self, command_name: str, duration: float):
        """Trata timeouts de comandos"""
        logging.warning(f"Comando '{command_name}' com timeout detectado após {duration:.1f}s")
        
        # Mostrar notificação não bloqueante
        self.show_toast_notification(
            f"Atenção: Comando '{command_name}' pode ter travado ({duration:.0f}s). "
            "Considere cancelar ou reiniciar a operação."
        )
    
    def _handle_high_resource_usage(self, metrics):
        """Trata uso excessivo de recursos - DESABILITADO"""
        # Avisos de recursos desabilitados - 21-25 threads é uso normal para esta aplicação
        # com recursos de sobra no sistema
        
        # Só avisar em casos realmente extremos
        extreme_usage = False
        message_parts = []
        
        if metrics.cpu_percent > 95:  # 95% CPU (era 80%)
            message_parts.append(f"• CPU: {metrics.cpu_percent:.1f}%")
            extreme_usage = True
            
        if metrics.memory_mb > 2000:  # 2GB memória (era 500MB)
            message_parts.append(f"• Memória: {metrics.memory_mb:.0f}MB")
            extreme_usage = True
            
        # Remover completamente aviso de threads
        # if metrics.thread_count > 20:
        #     message_parts.append(f"• Threads: {metrics.thread_count}")
        #     extreme_usage = True
            
        if extreme_usage:
            message = f"Uso extremo de recursos detectado:\n" + "\n".join(message_parts)
            message += "\nConsidere fechar algumas operações em andamento."
            logging.warning(message.replace('\n', ' '))
            
            # Mostrar warning não bloqueante apenas uma vez por minuto
            if not hasattr(self, '_last_resource_warning'):
                self._last_resource_warning = 0
                
            import time
            current_time = time.time()
            if current_time - self._last_resource_warning > 60:  # 1 minuto
                self._last_resource_warning = current_time
                self.show_toast_notification("⚠️ Uso extremo de recursos detectado. Verifique operações em andamento.")
    
    def _handle_mainloop_freeze(self):
        """Trata travamento do mainloop"""
        logging.error("Travamento do mainloop detectado! Tentando recuperação...")
        
        # Tentar forçar processamento de eventos pendentes
        try:
            self.update_idletasks()
            self.update()
        except Exception as e:
            logging.error(f"Erro na recuperação do mainloop: {e}")
        
        # Limpar comandos travados
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.force_cleanup_hanging_commands()
        
        # Mostrar alerta crítico
        self.show_toast_notification("🚨 Travamento detectado! Sistema tentando recuperação automática...")

    def show_info(self, message):
        dialog = CustomMessageBox(self, title=self.translate("label_information"), message=message, buttons=[self.translate("label_ok")])
        dialog.wait()

    def ask_yes_no(self, title, message):
        dialog = CustomMessageBox(self, title=title, message=message, buttons=[self.translate("label_yes"), self.translate("label_no")])
        dialog.wait()
        return dialog.get_result() == self.translate("label_yes")

    def prompt_for_initial_info_preference(self):
        if self.ask_yes_no(
            self.translate("initial_prompt_ask_for_info_title"),
            self.translate("initial_prompt_ask_for_info_message")
        ):
            self.ask_for_initial_info_on_select = True
        else:
            self.ask_for_initial_info_on_select = False
        self.settings_manager.save_ui_preferences()
        
    def show_toast_notification(self, message):
        if self._is_closing or not self.winfo_exists():
            return
        if self.toast_label and self.toast_label.winfo_exists():
            self.toast_label.destroy()
        self.toast_label = customtkinter.CTkLabel(self, text=message, fg_color=("gray80", "#333333"), text_color="white", corner_radius=10, font=("Arial", 12))
        self.toast_label.place(relx=0.5, rely=0.95, anchor="center")
        self.toast_label.after(3000, self.toast_label.destroy)

    def show_loading_indicator(self, message):
        """Mostra um indicador de carregamento sobre a área das abas."""
        try:
            # Verificar se o host_tab_view existe
            if hasattr(self, 'host_tab_view') and hasattr(self.host_tab_view, 'tab_view'):
                self.loading_label = customtkinter.CTkLabel(self.host_tab_view.tab_view, text=message, font=customtkinter.CTkFont(size=14, weight="bold"))
                self.loading_label.place(relx=0.5, rely=0.5, anchor="center")
                self.host_tab_view.tab_view.update_idletasks()
            else:
                logging.warning("host_tab_view não está disponível para mostrar indicador de carregamento")
        except Exception as e:
            logging.error(f"Erro ao mostrar indicador de carregamento: {e}")

    def update_loading_indicator(self, message):
        """Atualiza o texto do indicador de carregamento."""
        if hasattr(self, 'loading_label') and self.loading_label.winfo_exists():
            self.loading_label.configure(text=message)
            self.loading_label.update_idletasks()

    def hide_loading_indicator(self):
        """Remove o indicador de carregamento e mostra a área das abas."""
        if hasattr(self, 'loading_label') and self.loading_label.winfo_exists():
            self.loading_label.destroy()
    
    def run(self):
        """Inicia a aplicação com carregamento otimizado e proteção contra loops."""
        try:
            logging.info("=== INICIANDO RUN() DA APLICAÇÃO PRINCIPAL ===")

            # Sistema de proteção contra loops
            self._setup_loop_protection()

            # Iniciar monitoramento de performance
            self.performance_monitor.start_monitoring()
            logging.info("Monitor de performance iniciado")

            # Verificar se widgets foram criados
            if not hasattr(self, 'ui_manager') or not self.ui_manager:
                logging.error("ERRO CRÍTICO: ui_manager não foi criado!")
                return

            logging.info("Widgets verificados - OK")

            # Mostrar a janela principal PRIMEIRO
            logging.info("Mostrando janela principal...")
            self.show_main_window()

            # Garantir que a janela está visível antes de popular abas
            self.update_idletasks()

            logging.info("Janela principal mostrada")

            # Forçar atualização da janela para garantir renderização
            self.update()
            self.focus_force()

            # Continuar inicialização
            self._continue_initialization()

            # Iniciar o loop principal com proteção
            logging.info("Iniciando mainloop com proteção anti-travamento...")
            self.mainloop()

        except KeyboardInterrupt:
            logging.info("Interrupção por teclado detectada")
            self._emergency_shutdown()
        except Exception as e:
            logging.error(f"Erro no run(): {e}")
            import traceback
            traceback.print_exc()
            self._emergency_shutdown()
            raise
        finally:
            # Garantir limpeza mesmo em caso de erro
            logging.debug("Finalizando método run()")
            self._cleanup_on_exit()

    def _on_data_loaded(self):
        """Callback chamado quando dados são carregados durante inicialização."""
        logging.info("Dados carregados - marcando para populacao posterior")
        # Apenas marcar que dados estão prontos
        self.controller.hosts_preloaded = True

    def _continue_initialization(self):
        """Continua a inicialização com population direta das abas."""

        # Aguardar até que TODAS as funcionalidades estejam 100% carregadas
        if hasattr(self.controller, 'hosts_preloaded') and self.controller.hosts_preloaded:
            logging.info("Dados pré-carregados detectados - aguardando carregamento 100% completo...")
            # Iniciar verificação completa das funcionalidades
            self.after(100, self._check_complete_readiness)
        else:
            # Carregar dados em background se não foram pré-carregados
            self._load_data_in_background()

        # Iniciar watchdog para monitorar o mainloop
        self._start_mainloop_watchdog()

    def _check_complete_readiness(self, attempt=0):
        """Verifica se TODAS as funcionalidades da aplicação estão 100% prontas."""
        max_attempts = 50  # Máximo 10 segundos (50 * 200ms)

        # Lista de verificações que devem estar TODAS prontas
        readiness_checks = {
            "window_visible": self._is_window_fully_visible(),
            "ui_manager_ready": self._is_ui_manager_ready(),
            "host_tab_view_ready": self._is_host_tab_view_ready(),
            "fonts_available": self._are_fonts_available(),
            "main_components_ready": self._are_main_components_ready(),
            "tkinter_root_ready": self._ensure_hidden_tkinter_root(),
            "performance_monitor_ready": self._is_performance_monitor_ready()
        }

        # Verificar se TODOS os componentes estão prontos
        all_ready = all(readiness_checks.values())
        not_ready = [name for name, ready in readiness_checks.items() if not ready]

        if all_ready:
            logging.info("100% CONFIRMADO: Todas as funcionalidades estão prontas!")
            logging.info("Executando população das abas...")
            self._safe_populate_tabs()
        else:
            if attempt < max_attempts:
                logging.debug(f"Aguardando componentes: {', '.join(not_ready)} (tentativa {attempt+1}/{max_attempts})")
                self.after(200, lambda: self._check_complete_readiness(attempt + 1))
            else:
                logging.warning(f"Timeout aguardando componentes: {', '.join(not_ready)}")
                logging.warning("Executando população mesmo sem todos os componentes prontos...")
                self._safe_populate_tabs()

    def _is_window_fully_visible(self):
        """Verifica se a janela está completamente visível."""
        try:
            return (self.winfo_viewable() and
                   self.winfo_width() > 100 and
                   self.winfo_height() > 100 and
                   self.state() == 'normal')
        except:
            return False

    def _is_ui_manager_ready(self):
        """Verifica se o ui_manager está pronto."""
        try:
            return (hasattr(self, 'ui_manager') and
                   self.ui_manager is not None and
                   hasattr(self.ui_manager, 'create_widgets'))
        except:
            return False

    def _is_host_tab_view_ready(self):
        """Verifica se o host_tab_view está pronto."""
        try:
            return (hasattr(self, 'host_tab_view') and
                   self.host_tab_view is not None and
                   hasattr(self.host_tab_view, 'tab_view') and
                   self.host_tab_view.tab_view is not None)
        except:
            return False

    def _are_fonts_available(self):
        """Verifica se as fontes CustomTkinter estão disponíveis."""
        try:
            import customtkinter
            import tkinter

            # Verificar se existe uma janela root para suporte de fontes
            root = tkinter._get_default_root()
            if root is None:
                return False

            # Tentar criar uma fonte de teste
            test_font = customtkinter.CTkFont(size=11)
            return True
        except Exception as e:
            logging.debug(f"Fontes não disponíveis: {e}")
            return False

    def _are_main_components_ready(self):
        """Verifica se os componentes principais estão prontos."""
        try:
            return (hasattr(self, 'controller') and
                   self.controller is not None and
                   hasattr(self, 'translator') and
                   self.translator is not None)
        except:
            return False

    def _ensure_hidden_tkinter_root(self):
        """Garante que existe uma janela Tk root mas mantém ela completamente oculta."""
        try:
            import tkinter

            # Verificar se já existe uma janela root
            root = tkinter._get_default_root()

            if root is None:
                # Criar janela root oculta
                root = tkinter.Tk()
                root.withdraw()  # Ocultar imediatamente
                root.attributes('-alpha', 0.0)  # Tornar completamente transparente
                root.geometry('1x1+9999+9999')  # Tamanho mínimo e posição fora da tela
                root.overrideredirect(True)  # Remover barra de título

                logging.debug("Janela Tk root oculta criada para suporte a fontes")
            else:
                # Se já existe, garantir que está oculta
                try:
                    root.withdraw()
                    root.attributes('-alpha', 0.0)
                    root.geometry('1x1+9999+9999')
                    root.overrideredirect(True)
                except:
                    pass  # Ignorar erros se a janela já estiver configurada

            return True

        except Exception as e:
            logging.debug(f"Erro ao configurar janela root oculta: {e}")
            return False

    def _is_performance_monitor_ready(self):
        """Verifica se o monitor de performance está pronto."""
        try:
            return (hasattr(self, 'performance_monitor') and
                   self.performance_monitor is not None and
                   hasattr(self.performance_monitor, 'start_monitoring'))
        except:
            return False

    def _safe_populate_tabs(self, attempt=0):
        """População segura das abas com tratamento de erros e retry."""
        max_attempts = 5

        # Verificar se fonts estão disponíveis
        try:
            import customtkinter
            # Tentar criar uma fonte de teste
            test_font = customtkinter.CTkFont(size=11)
            # Se chegou aqui, fonts estão disponíveis
            try:
                self._populate_tabs_directly()
                logging.info("Abas populadas com sucesso!")
                return
            except Exception as e:
                logging.error(f"Erro ao popular abas: {e}")
                # Se falhar, tentar com abordagem simples
                self._populate_tabs_simple()
                return
        except Exception as e:
            # Fonts ainda não estão disponíveis
            if attempt < max_attempts:
                logging.debug(f"Fonts não disponíveis na tentativa {attempt+1}, tentando novamente em 200ms...")
                self.after(200, lambda: self._safe_populate_tabs(attempt + 1))
            else:
                logging.warning("Fonts não disponíveis após várias tentativas, usando abordagem simples")
                self._populate_tabs_simple()

    def _populate_tabs_directly(self):
        """Popula abas diretamente sem verificações complexas."""
        # Verificar se componentes básicos existem
        if not hasattr(self, 'host_tab_view') or not self.host_tab_view:
            raise Exception("host_tab_view não disponível")

        if not hasattr(self.host_tab_view, 'tab_view') or not self.host_tab_view.tab_view:
            raise Exception("tab_view não disponível")

        # Population direta
        self.controller.populate_tabs_with_preloaded_data()

    def _populate_tabs_simple(self):
        """Population simplificada como fallback."""
        logging.info("Executando population simplificada...")
        try:
            # Criar apenas aba de placeholder sem fontes customizadas
            if hasattr(self, 'host_tab_view') and self.host_tab_view:
                placeholder_name = "Selecionar Host"
                try:
                    # Tentar adicionar placeholder de forma simples
                    placeholder_tab = self.host_tab_view.tab_view.add(placeholder_name)
                    # Configurar placeholder básico sem fonts customizadas
                    import customtkinter
                    label = customtkinter.CTkLabel(placeholder_tab, text="Selecione um host para começar")
                    label.pack(expand=True)
                    logging.info("Placeholder criado com sucesso")
                except Exception as e:
                    logging.error(f"Erro ao criar placeholder: {e}")
                    # Fallback final: usar Tkinter básico
                    try:
                        import tkinter
                        placeholder_tab = self.host_tab_view.tab_view.add(placeholder_name)
                        label = tkinter.Label(placeholder_tab, text="Selecione um host para começar", bg="gray90")
                        label.pack(expand=True)
                        logging.info("Placeholder Tkinter criado com sucesso")
                    except Exception as e2:
                        logging.error(f"Erro no fallback Tkinter: {e2}")
        except Exception as e:
            logging.error(f"Erro na population simplificada: {e}")

    
    def _setup_loop_protection(self):
        """Configura sistema de proteção contra loops infinitos."""
        import threading
        import time
        
        # Variáveis de controle de loop
        self._loop_active = True
        self._last_heartbeat = time.time()
        self._heartbeat_interval = 5.0  # Heartbeat a cada 5 segundos
        self._max_inactive_time = 10.0  # 10 segundos sem resposta = travamento
        self._watchdog_active = False
        
        # Contador de callbacks para detectar loops
        self._callback_count = 0
        self._callback_threshold = 1000  # Limite de callbacks por segundo
        self._callback_reset_time = time.time()
        
        logging.info("Sistema de proteção contra loops configurado")
    
    def _start_mainloop_watchdog(self):
        """Inicia o sistema de monitoramento simplificado do mainloop."""
        import threading

        def simple_watchdog():
            import time
            self._watchdog_active = True
            logging.debug("Sistema de monitoramento simplificado iniciado")

            while self._loop_active and self._watchdog_active:
                try:
                    current_time = time.time()

                    # Verificação básica - apenas detectar travamentos graves
                    if current_time - self._last_heartbeat > 30.0:  # 30 segundos (mais permissivo)
                        logging.warning("Mainloop não responde há 30 segundos")
                        # Não força encerramento - apenas avisa

                    # Aguardar mais tempo entre verificações
                    time.sleep(5.0)

                except Exception as e:
                    logging.debug(f"Erro no watchdog: {e}")
                    break

            logging.debug("Sistema de monitoramento finalizado")

        # Iniciar watchdog simplificado
        watchdog_thread = threading.Thread(target=simple_watchdog, daemon=True, name="SimpleWatchdog")
        watchdog_thread.start()

        # Iniciar heartbeat simplificado
        self._schedule_heartbeat()
    
    def _schedule_heartbeat(self):
        """Agenda o próximo heartbeat otimizado do mainloop."""
        if self._loop_active and self._watchdog_active and not self._is_closing:
            try:
                import time
                self._last_heartbeat = time.time()

                # Verificar se ainda estamos ativos antes de agendar
                if not self._is_closing:
                    # Usar uma função nomeada para evitar problemas com lambdas
                    heartbeat_id = self.after(15000, self._safe_heartbeat_callback)  # 15 segundos
                    # Armazenar ID para cancelamento posterior se necessário
                    if not hasattr(self, '_heartbeat_ids'):
                        self._heartbeat_ids = []
                    self._heartbeat_ids.append(heartbeat_id)

            except Exception as e:
                logging.debug(f"Erro no heartbeat: {e}")

    def _safe_heartbeat_callback(self):
        """Callback seguro para heartbeat que verifica estado antes de executar."""
        try:
            if not self._is_closing and self._loop_active and self._watchdog_active:
                self._schedule_heartbeat()
        except Exception as e:
            logging.debug(f"Erro no callback de heartbeat: {e}")
    
    def _emergency_shutdown(self):
        """Encerramento simplificado da aplicação."""
        logging.warning("=== ENCERRAMENTO SOLICITADO ===")

        try:
            # Parar sistemas de monitoramento
            self._loop_active = False
            self._watchdog_active = False

            # Encerramento gracioso
            if hasattr(self, 'quit'):
                logging.info("Executando encerramento gracioso...")
                self.quit()

        except Exception as e:
            logging.error(f"Erro no encerramento: {e}")
            try:
                self.destroy()
            except:
                pass
    
    def _cleanup_on_exit(self):
        """Limpeza completa de recursos ao sair."""
        try:
            logging.info("Executando limpeza de recursos...")

            # Parar sistema de proteção
            self._loop_active = False
            self._watchdog_active = False
            self._is_closing = True

            # Cancelar todos os callbacks pendentes primeiro
            self._cancel_all_pending_callbacks()

            # Limpeza de threads e recursos
            if hasattr(self, 'stop_monitoring_event'):
                try:
                    self.stop_monitoring_event.set()
                except Exception as e:
                    logging.debug(f"Erro ao parar threads: {e}")

            # Limpeza de monitores
            if hasattr(self, 'performance_monitor'):
                try:
                    self.performance_monitor.stop_monitoring()
                except Exception as e:
                    logging.debug(f"Erro ao parar performance monitor: {e}")

            # Limpeza de credenciais
            if hasattr(self, 'cred_service'):
                try:
                    self.cred_service.lock()
                except Exception as e:
                    logging.debug(f"Erro ao bloquear credenciais: {e}")

            # Salvar configurações
            if hasattr(self, 'settings_manager'):
                try:
                    self.settings_manager.save_ui_preferences()
                except Exception as e:
                    logging.debug(f"Erro ao salvar configurações: {e}")

            # Limpar cache de imagens para evitar referências órfãs
            self._cleanup_image_cache()

            logging.info("Limpeza de recursos concluída")

        except Exception as e:
            logging.error(f"Erro na limpeza: {e}")

    def _cleanup_image_cache(self):
        """Limpa cache de imagens para evitar referências órfãs."""
        try:
            # Limpar cache de ícones da aplicação
            if hasattr(self, '_icon_cache'):
                self._icon_cache.clear()

            # Limpar cache de imagens dos tabs se existir
            if hasattr(self, 'host_tab_view') and hasattr(self.host_tab_view, 'tab_manager'):
                if hasattr(self.host_tab_view.tab_manager, 'status_images'):
                    self.host_tab_view.tab_manager.status_images.clear()

            logging.debug("Cache de imagens limpo")

        except Exception as e:
            logging.debug(f"Erro ao limpar cache de imagens: {e}")
    
        
    def _cleanup_callbacks(self):
        """Limpa recursos e callbacks de forma segura."""
        try:
            self._callback_protection_active = False
            self._is_closing = True

            # Cancelar todos os callbacks agendados com after()
            self._cancel_all_pending_callbacks()

            # Limpar qualquer comando lambda pendente nos widgets
            self._clear_widget_commands()

            # Tentar limpar callbacks pendentes
            if hasattr(self, 'tk') and self.tk:
                self.tk.quit()
        except Exception as e:
            logging.debug(f"Erro na limpeza de callbacks: {e}")

    def _clear_widget_commands(self):
        """Remove comandos de todos os widgets para evitar callbacks pendentes."""
        try:
            # Lista de widgets que podem ter comandos
            widgets_to_clear = []

            # Adicionar botões principais se existirem
            if hasattr(self, 'add_host_button') and self.add_host_button:
                widgets_to_clear.append(self.add_host_button)

            if hasattr(self, 'tab_settings_button') and self.tab_settings_button:
                widgets_to_clear.append(self.tab_settings_button)

            if hasattr(self, 'actions_menu') and self.actions_menu:
                widgets_to_clear.append(self.actions_menu)

            if hasattr(self, 'appearance_mode_menu') and self.appearance_mode_menu:
                widgets_to_clear.append(self.appearance_mode_menu)

            if hasattr(self, 'language_menu') and self.language_menu:
                widgets_to_clear.append(self.language_menu)

            if hasattr(self, 'about_button') and self.about_button:
                widgets_to_clear.append(self.about_button)

            # Limpar comandos de todos os widgets
            for widget in widgets_to_clear:
                try:
                    if hasattr(widget, 'configure'):
                        widget.configure(command=None)
                        logging.debug(f"Comando removido de {widget.__class__.__name__}")
                except Exception as e:
                    logging.debug(f"Erro ao limpar comando de widget: {e}")

        except Exception as e:
            logging.debug(f"Erro ao limpar comandos de widgets: {e}")

    def _cancel_all_pending_callbacks(self):
        """Cancela todos os callbacks pendentes para evitar erros após fechamento."""
        try:
            # Lista de callbacks conhecidos para cancelar
            callback_attrs = [
                '_resize_timer',
                '_menu_action_timer',
                '_movement_timer'
            ]

            for attr in callback_attrs:
                if hasattr(self, attr) and getattr(self, attr):
                    try:
                        self.after_cancel(getattr(self, attr))
                        setattr(self, attr, None)
                    except Exception as e:
                        logging.debug(f"Erro ao cancelar {attr}: {e}")

            # Cancelar heartbeats pendentes
            if hasattr(self, '_heartbeat_ids'):
                for heartbeat_id in self._heartbeat_ids:
                    try:
                        self.after_cancel(heartbeat_id)
                    except Exception as e:
                        logging.debug(f"Erro ao cancelar heartbeat {heartbeat_id}: {e}")
                self._heartbeat_ids.clear()

            # Cancelar callbacks de componentes filhos
            self._cancel_child_callbacks()

            # Processar callbacks pendentes de forma segura
            try:
                # Processar apenas alguns callbacks pendentes para evitar loops
                for i in range(5):  # Máximo 5 iterações
                    if self._is_closing:
                        break
                    self.update_idletasks()
            except Exception as e:
                logging.debug(f"Erro ao processar callbacks pendentes: {e}")

        except Exception as e:
            logging.debug(f"Erro geral ao cancelar callbacks: {e}")

    def _cancel_child_callbacks(self):
        """Cancela callbacks de componentes filhos."""
        try:
            # Cancelar callbacks do MultiRowTabView
            if hasattr(self, 'host_tab_view') and self.host_tab_view:
                child_callback_attrs = ['_resize_after_id']
                for attr in child_callback_attrs:
                    if hasattr(self.host_tab_view, attr) and getattr(self.host_tab_view, attr):
                        try:
                            self.host_tab_view.after_cancel(getattr(self.host_tab_view, attr))
                            setattr(self.host_tab_view, attr, None)
                            logging.debug(f"Cancelado callback filho: {attr}")
                        except Exception as e:
                            logging.debug(f"Erro ao cancelar callback filho {attr}: {e}")

            # Cancelar callbacks de qualquer componente que tenha métodos cleanup
            components_with_cleanup = []

            # Verificar host_tab_view e seus subcomponentes
            if hasattr(self, 'host_tab_view') and self.host_tab_view:
                components_with_cleanup.append(self.host_tab_view)

                # Verificar tab_manager
                if hasattr(self.host_tab_view, 'tab_manager') and self.host_tab_view.tab_manager:
                    components_with_cleanup.append(self.host_tab_view.tab_manager)

            # Chamar cleanup em todos os componentes
            for component in components_with_cleanup:
                if hasattr(component, 'cleanup_callbacks'):
                    try:
                        component.cleanup_callbacks()
                        logging.debug(f"Cleanup realizado em: {component.__class__.__name__}")
                    except Exception as e:
                        logging.debug(f"Erro no cleanup de {component.__class__.__name__}: {e}")

        except Exception as e:
            logging.debug(f"Erro ao cancelar callbacks filhos: {e}")

    def _load_data_in_background(self):
        """Carrega dados apenas se não foram carregados durante inicialização."""
        try:
            # Se chegou aqui, dados não foram carregados - carregar agora
            logging.info("Dados não carregados durante inicialização - carregando agora...")

            # Mostrar indicador de carregamento na interface principal
            if hasattr(self, 'ui_manager') and hasattr(self.ui_manager, 'host_tab_view'):
                self.show_loading_indicator("Carregando dados...")

            # Usar after() para não bloquear UI
            self.after(100, self._start_data_loading_sequence)

        except Exception as e:
            logging.error(f"Erro no carregamento em background: {e}")
            self.hide_loading_indicator()

    def _start_data_loading_sequence(self):
        """Inicia a sequência de carregamento de dados usando after()."""
        try:
            logging.info("Iniciando carregamento de dados...")

            # Callback para atualizar status (não há janela de loading aqui)
            def update_status(msg):
                logging.debug(f"Carregamento: {msg}")
                if hasattr(self, 'loading_label') and self.loading_label:
                    self.update_loading_indicator(msg)

            # Carregar dados de forma síncrona (já que estamos na thread principal)
            self.controller.load_and_prepare_all_hosts(update_status)

            # Finalizar carregamento
            self.after(100, self._finalize_data_loading)

        except Exception as e:
            logging.error(f"Erro no carregamento de dados: {e}")
            self.hide_loading_indicator()


    def _finalize_data_loading(self):
        """Finaliza o carregamento de dados na thread principal."""
        try:
            # Popular abas com dados carregados
            self.controller.populate_tabs_with_preloaded_data()

            # Esconder indicador de carregamento
            self.hide_loading_indicator()

            logging.info("Carregamento de dados concluído")

        except Exception as e:
            logging.error(f"Erro ao finalizar carregamento: {e}")
            self.hide_loading_indicator()

    def test_translations(self):
        """Testa se as traduções estão funcionando corretamente."""
        try:
            test_keys = [
                "ping_title", "traceroute_title", "remote_actions_title",
                "sysinfo_title", "services_title", "event_logs_title",
                "remote_shell_title", "activity_title"
            ]
            
            logging.info("=== TESTE DE TRADUÇÕES ===")
            logging.info(f"Idioma atual: {self.current_language}")
            
            for key in test_keys:
                translated = self.translate(key)
                logging.info(f"{key}: '{translated}'")
                
            logging.info("=== FIM DO TESTE ===")
            
        except Exception as e:
            logging.error(f"Erro no teste de traduções: {e}")