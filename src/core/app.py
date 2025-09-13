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
    def __init__(self, base_dir):
        super().__init__()
        
        self._is_closing = False
        self._callback_protection_active = False
        self.base_dir = base_dir

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
        
        # Não esconder a janela - ela deve ser visível desde o início

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
            
            # REMOVIDO: eventos Configure causam travamento
            # self.bind('<Configure>', self._on_configure_static)
            
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
                self.tk.call('wm', 'attributes', self._w, '-alpha', 0.99)  # Pequena transparência para forçar composição
                self.tk.call('wm', 'attributes', self._w, '-alpha', 1.0)   # Voltar à opacidade total
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
                self.iconphoto(True, self.app_photo_icon)

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
            self.minsize(1200, 700)  # Tamanho mínimo atualizado
            
            # Salvar dimensões para centralização
            self._window_width = width
            self._window_height = height
            
            logging.debug(f"Responsive size configured: {width}x{height} for screen {screen_width}x{screen_height}")
            
        except Exception as e:
            logging.error(f"Error setting responsive size: {e}")
            # Fallback para tamanho padrão (aproximadamente 80% de Full HD)
            self.wm_geometry("1536x864")  # 80% de 1920x1080
            self.minsize(1200, 700)
            self._window_width = 1536
            self._window_height = 864

    def _center_and_show_main_window(self):
        """
        Centraliza e mostra a janela principal usando EXATAMENTE a mesma lógica da BaseDialog.
        """
        try:
            # Atualizar para garantir que todas as dimensões estão corretas (janela ainda oculta)
            self.update_idletasks()
            
            # Obter geometria da tela (IGUAL BaseDialog)
            windows_info = self._get_windows_screen_info()
            if windows_info:
                screen_x, screen_y = 0, 0
                screen_width, screen_height = windows_info[2], windows_info[3]
                logging.debug(f"Using Windows API screen info: {screen_width}x{screen_height}")
            else:
                screen_x, screen_y = 0, 0
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                logging.debug(f"Using Tkinter screen info: {screen_width}x{screen_height}")
            
            # Usar 80% do tamanho do monitor atual
            window_width = int(screen_width * 0.8)
            window_height = int(screen_height * 0.8)
            
            # Garantir tamanho mínimo para usabilidade
            window_width = max(window_width, 1200)
            window_height = max(window_height, 700)
            
            # Garantir tamanho máximo para telas muito grandes
            window_width = min(window_width, 2400)  # Máximo para telas muito grandes
            window_height = min(window_height, 1400)
            
            # USAR A MESMA LÓGICA DA BaseDialog para centralização
            # Calcular posição central
            pos_x = screen_x + (screen_width - window_width) // 2
            pos_y = screen_y + (screen_height - window_height) // 2
            
            # Garantir que a janela não saia da tela (margem de 50px)
            margin = 50
            pos_x = max(screen_x + margin, min(pos_x, screen_x + screen_width - window_width - margin))
            pos_y = max(screen_y + margin, min(pos_y, screen_y + screen_height - window_height - margin))
            
            # Definir posição enquanto a janela ainda está oculta (IGUAL BaseDialog)
            geometry_string = f"+{int(pos_x)}+{int(pos_y)}"
            self.wm_geometry(geometry_string)
            
            # Agora mostrar a janela na posição correta (IGUAL BaseDialog)
            self.deiconify()
            
            # Configurar foco (IGUAL BaseDialog)
            self.lift()
            self.focus_force()
            
            logging.debug(f"Main window positioned at ({pos_x}, {pos_y}) with size ({window_width}x{window_height}) on screen ({screen_width}x{screen_height})")
            
        except Exception as e:
            logging.error(f"Error centering main window: {e}")
            # Fallback simples
            self.deiconify()
            self.lift()
            self.focus_force()

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
            if choice_key == "title_add_host":
                self.controller.add_new_host()
                action_executed = True
            elif choice_key == "title_remove_hosts":
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

    def on_closing(self):
        # Sempre perguntar confirmação, mesmo com comandos em andamento
        if self.ask_yes_no(self.translate("confirm_exit_title"), self.translate("confirm_exit_message")):
            self._is_closing = True
            
            # Limpar otimizadores de performance
            if hasattr(self, 'performance_optimizer'):
                self.performance_optimizer.cleanup()
            
            if hasattr(self, 'advanced_optimizer'):
                self.advanced_optimizer.cleanup()
                
            # Parar monitor de performance
            if hasattr(self, 'performance_monitor'):
                self.performance_monitor.stop_monitoring()
            
            self.cred_service.lock()
            try:
                if os.path.exists(os.path.join(self.base_dir, CRED_FILE)): os.remove(os.path.join(self.base_dir, CRED_FILE))
                if os.path.exists(os.path.join(self.base_dir, SALT_FILE)): os.remove(os.path.join(self.base_dir, SALT_FILE))
            except OSError as e:
                logging.error(f"Erro ao apagar arquivos do cofre: {e}")
            
            self.settings_manager.save_ui_preferences()
            self.stop_monitoring_event.set()
            
            # Fechar quaisquer diálogos abertos antes de destruir a aplicação
            try:
                for child in self.winfo_children():
                    if hasattr(child, 'destroy'):
                        try:
                            child.destroy()
                        except:
                            pass
            except:
                pass
            
            self.destroy()
    
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
        self.toast_label = customtkinter.CTkLabel(self, text=message, fg_color=("gray80", "#333333"), text_color=("gray10", "white"), corner_radius=10, font=("Arial", 12))
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
            # Sistema de proteção contra loops
            self._setup_loop_protection()
            
            # Iniciar monitoramento de performance
            self.performance_monitor.start_monitoring()
            logging.info("Monitor de performance iniciado")
            
            # Mostrar a janela principal primeiro (inicialização rápida)
            self.show_main_window()
            
            # Carregar dados em background após mostrar a janela
            self.after(100, self._load_data_in_background)
            
            # Iniciar watchdog para monitorar o mainloop
            self._start_mainloop_watchdog()
            
            # Iniciar o loop principal com proteção
            logging.info("Iniciando mainloop com proteção anti-travamento...")
            self.mainloop()
                
        except Exception as e:
            logging.error(f"Erro no run(): {e}")
            import traceback
            traceback.print_exc()
            self._emergency_shutdown()
            raise
        finally:
            # Garantir limpeza mesmo em caso de erro
            self._cleanup_on_exit()
    
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
        """Inicia o watchdog que monitora o mainloop."""
        import threading
        
        def watchdog_worker():
            import time
            self._watchdog_active = True
            logging.info("Watchdog do mainloop iniciado")
            
            while self._loop_active and self._watchdog_active:
                try:
                    current_time = time.time()
                    
                    # Verificar se o mainloop está respondendo
                    if current_time - self._last_heartbeat > self._max_inactive_time:
                        logging.error("DETECTADO: Mainloop travado há mais de 10 segundos!")
                        logging.error("Iniciando encerramento de emergência...")
                        self._emergency_shutdown()
                        break
                    
                    # Verificar se há muitos callbacks (possível loop)
                    if current_time - self._callback_reset_time >= 1.0:
                        if self._callback_count > self._callback_threshold:
                            logging.error(f"DETECTADO: Loop de callbacks! {self._callback_count} callbacks em 1 segundo")
                            logging.error("Iniciando encerramento de emergência...")
                            self._emergency_shutdown()
                            break
                        
                        # Reset contador
                        self._callback_count = 0
                        self._callback_reset_time = current_time
                    
                    # Aguardar antes da próxima verificação
                    time.sleep(2.0)
                    
                except Exception as e:
                    logging.error(f"Erro no watchdog: {e}")
                    break
            
            logging.info("Watchdog do mainloop finalizado")
        
        # Iniciar watchdog em thread separada
        watchdog_thread = threading.Thread(target=watchdog_worker, daemon=True, name="MainloopWatchdog")
        watchdog_thread.start()
        
        # Iniciar heartbeat do mainloop
        self._schedule_heartbeat()
    
    def _schedule_heartbeat(self):
        """Agenda o próximo heartbeat do mainloop."""
        if self._loop_active and self._watchdog_active:
            try:
                import time
                self._last_heartbeat = time.time()
                self._callback_count += 1
                
                # Agendar próximo heartbeat
                self.after(int(self._heartbeat_interval * 1000), self._schedule_heartbeat)
                
            except Exception as e:
                logging.error(f"Erro no heartbeat: {e}")
                self._emergency_shutdown()
    
    def _emergency_shutdown(self):
        """Encerramento de emergência da aplicação."""
        logging.critical("=== ENCERRAMENTO DE EMERGÊNCIA ATIVADO ===")
        
        try:
            # Parar watchdog
            self._loop_active = False
            self._watchdog_active = False
            
            # Tentar encerramento gracioso primeiro
            if hasattr(self, 'quit'):
                logging.info("Tentando encerramento gracioso...")
                self.quit()
            
            # Force timeout para encerramento
            import threading
            def force_exit():
                import time
                import os
                time.sleep(3)  # Aguardar 3 segundos para encerramento gracioso
                logging.critical("Forçando encerramento do processo...")
                os._exit(1)
            
            force_thread = threading.Thread(target=force_exit, daemon=True)
            force_thread.start()
            
        except Exception as e:
            logging.critical(f"Erro no encerramento de emergência: {e}")
            import os
            os._exit(1)
    
    def _cleanup_on_exit(self):
        """Limpeza de recursos ao sair."""
        try:
            logging.info("Executando limpeza de recursos...")
            
            # Parar sistema de proteção
            self._loop_active = False
            self._watchdog_active = False
            
            # Limpeza de threads e recursos
            if hasattr(self, 'stop_monitoring_event'):
                self.stop_monitoring_event.set()
            
            # Limpeza de credenciais
            if hasattr(self, 'cred_service'):
                self.cred_service.lock()
            
            # Salvar configurações
            if hasattr(self, 'settings_manager'):
                self.settings_manager.save_ui_preferences()
            
            logging.info("Limpeza de recursos concluída")
            
        except Exception as e:
            logging.error(f"Erro na limpeza: {e}")
    
    def _add_emergency_close_button(self):
        """Adiciona um botão de fechamento de emergência."""
        try:
            import customtkinter
            
            # Criar botão de emergência no canto superior direito
            self.emergency_button = customtkinter.CTkButton(
                self,
                text="✕",
                width=30,
                height=30,
                font=customtkinter.CTkFont(size=16, weight="bold"),
                fg_color="red",
                hover_color="darkred",
                command=self._emergency_close
            )
            self.emergency_button.place(relx=0.98, rely=0.02, anchor="ne")
            
        except Exception as e:
            logging.error(f"Erro ao criar botão de emergência: {e}")
    
    def _emergency_close(self):
        """Fechamento de emergência da aplicação."""
        logging.info("Fechamento de emergência ativado")
        try:
            self.quit()
            self.destroy()
        except:
            import os
            os._exit(0)
        
    def _cleanup_callbacks(self):
        """Limpa recursos e callbacks."""
        try:
            self._callback_protection_active = False
            # Tentar limpar callbacks pendentes
            if hasattr(self, 'tk') and self.tk:
                self.tk.quit()
        except:
            pass
    
    def _load_data_in_background(self):
        """Carrega dados em background após a interface estar visível."""
        try:
            # Mostrar indicador de carregamento (se disponível)
            if hasattr(self, 'ui_manager') and hasattr(self.ui_manager, 'host_tab_view'):
                self.show_loading_indicator("Carregando dados...")
            else:
                logging.debug("UI ainda não está pronta para indicador de carregamento")
            
            # Carregar dados em thread separada para não bloquear a UI
            import threading
            loading_thread = threading.Thread(
                target=self._background_data_loading,
                daemon=True
            )
            loading_thread.start()
            
        except Exception as e:
            logging.error(f"Erro no carregamento em background: {e}")
            self.hide_loading_indicator()
    
    def _background_data_loading(self):
        """Executa o carregamento de dados em thread separada."""
        try:
            # Carregar dados iniciais
            self.controller.load_and_prepare_all_hosts(lambda msg: None)
            
            # Atualizar UI na thread principal
            self.after(0, self._finalize_data_loading)
            
        except Exception as e:
            logging.error(f"Erro no carregamento de dados: {e}")
            self.after(0, self.hide_loading_indicator)
    
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