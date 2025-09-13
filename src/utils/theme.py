# app/theme_enhancer.py
# Módulo para melhorar as cores dos temas e implementar carregamento suave.

import customtkinter
import logging
import threading
import time


class ThemeEnhancer:
    """
    Classe para melhorar as cores dos temas e implementar transições suaves.
    """
    
    # Paleta de cores melhorada para o tema claro
    ENHANCED_LIGHT_COLORS = {
        # Cores principais mais suaves e modernas
        "primary_blue": "#0078D4",      # Azul Microsoft mais suave
        "primary_blue_hover": "#106EBE", # Hover mais sutil
        
        # Cores de status mais elegantes
        "success_green": "#107C10",      # Verde mais escuro e profissional
        "success_green_hover": "#0F6E0F",
        "warning_orange": "#FF8C00",     # Laranja mais suave
        "warning_orange_hover": "#E67E00",
        "error_red": "#D13438",          # Vermelho mais suave
        "error_red_hover": "#B52D30",
        
        # Cores de fundo mais elegantes
        "light_bg": "#FAFAFA",           # Fundo mais suave que branco puro
        "card_bg": "#FFFFFF",            # Cartões em branco puro
        "hover_bg": "#F3F3F3",           # Hover mais sutil
        
        # Cores de texto melhoradas
        "text_primary": "#1F1F1F",       # Texto principal mais suave que preto
        "text_secondary": "#605E5C",     # Texto secundário cinza elegante
        "text_disabled": "#8A8886",      # Texto desabilitado mais legível
        
        # Cores de borda mais elegantes
        "border_light": "#E1DFDD",       # Bordas muito sutis
        "border_medium": "#C8C6C4",      # Bordas médias
        "border_dark": "#A19F9D",        # Bordas mais definidas
        
        # Cores para Treeview melhoradas
        "treeview_bg": "#FFFFFF",        # Fundo branco puro
        "treeview_selected": "#E3F2FD",  # Seleção azul muito clara
        "treeview_hover": "#F5F5F5",     # Hover cinza muito claro
        "treeview_header": "#F8F9FA",    # Cabeçalho cinza muito claro
        "treeview_odd": "#FBFBFB",       # Linhas alternadas quase imperceptíveis
        "treeview_even": "#FFFFFF",      # Linhas pares em branco
    }
    
    # Tokens de tema para harmonização de botões/frames
    TOKENS_LIGHT = {
        "primary": "#0078D4",
        "primary_hover": "#106EBE",
        "on_primary": "#FFFFFF",
        "surface": "#FAFAFA",
        "surface_alt": "#FFFFFF",
        "text": "#1F1F1F",
        "text_muted": "#605E5C",
        "border": "#E1DFDD",
    }

    TOKENS_DARK = {
        "primary": "#4FA8FF",
        "primary_hover": "#3B8ED0",
        "on_primary": "#FFFFFF",
        "surface": "#262626",
        "surface_alt": "#1E1E1E",
        "text": "#E5E5E5",
        "text_muted": "#B3B3B3",
        "border": "#3A3A3A",
    }
    
    def __init__(self, app):
        self.app = app
        self.is_transitioning = False
        self.transition_lock = threading.Lock()
        self._hidden_windows = []
        
    def get_enhanced_color(self, color_key, fallback=None):
        """
        Obtém uma cor melhorada baseada na chave fornecida.
        """
        current_mode = customtkinter.get_appearance_mode().lower()
        
        if current_mode == "light":
            return self.ENHANCED_LIGHT_COLORS.get(color_key, fallback or color_key)
        else:
            # Para tema escuro, usar cores padrão do CustomTkinter (já são boas)
            return fallback or color_key
    
    def apply_enhanced_colors(self):
        """
        Aplica as cores melhoradas aos componentes da aplicação.
        """
        current_mode = customtkinter.get_appearance_mode().lower()
        
        if current_mode != "light":
            return  # Só melhorar tema claro por enquanto
            
        try:
            # Aplicar cores melhoradas aos componentes específicos
            self._enhance_treeview_colors()
            self._enhance_button_colors()
            self._enhance_frame_colors()
            
            # Aplicar tokens de cor após melhorar componentes
            self.apply_tokens_to_app()
            logging.debug("Enhanced light theme colors applied successfully")
            
        except Exception as e:
            logging.error(f"Error applying enhanced colors: {e}")
    
    def _enhance_treeview_colors(self):
        """
        Melhora as cores dos Treeviews para o tema claro.
        """
        # Atualizar cores do Treeview no HomeFrame
        if hasattr(self.app, 'host_tab_view') and self.app.host_tab_view:
            if hasattr(self.app.host_tab_view, 'home_tab_manager'):
                home_manager = self.app.host_tab_view.home_tab_manager
                if hasattr(home_manager, 'home_frame'):
                    self._apply_enhanced_treeview_to_frame(home_manager.home_frame)
        
        # Encontrar e atualizar todos os EventLogFrames
        self._update_all_event_log_frames()
    
    def _apply_enhanced_treeview_to_frame(self, frame):
        """
        Aplica cores melhoradas a um frame específico que contém Treeview.
        """
        if hasattr(frame, 'tree') and hasattr(frame, 'update_theme'):
            frame.update_theme()
    
    def _update_all_event_log_frames(self):
        """
        Atualiza todos os EventLogFrames com cores melhoradas.
        """
        if hasattr(self.app, 'host_tab_view') and self.app.host_tab_view:
            for host_name_key, tab_data in self.app.host_tab_view.host_tabs_data.items():
                if host_name_key in self.app.host_tab_view.loaded_tabs:
                    for frame_name, frame in tab_data.items():
                        if hasattr(frame, 'update_theme') and 'event_log' in frame_name.lower():
                            frame.update_theme()
    
    def _enhance_button_colors(self):
        """
        Melhora as cores dos botões para o tema claro.
        """
        # Esta função pode ser expandida para aplicar cores específicas a botões
        pass
    
    def _enhance_frame_colors(self):
        """
        Melhora as cores dos frames para o tema claro.
        """
        # Esta função pode ser expandida para aplicar cores específicas a frames
        pass
    
    def smooth_theme_transition(self, new_mode, callback=None):
        """
        Executa uma transição suave de tema em background.
        """
        if self.is_transitioning:
            logging.debug("Theme transition already in progress, skipping")
            return
            
        def transition_worker():
            with self.transition_lock:
                self.is_transitioning = True
                
                try:
                    logging.debug(f"Starting smooth theme transition to {new_mode}")
                    
                    # Esconder a interface temporariamente para evitar ghosting
                    self.app.after(0, self._hide_interface_for_transition)
                    
                    # Pausa mínima otimizada
                    time.sleep(0.05)
                    
                    # Aplicar o novo tema
                    self.app.after(0, lambda: self._apply_theme_in_background(new_mode))
                    
                    # Pausa otimizada para aplicação do tema
                    time.sleep(0.08)
                    
                    # Aplicar cores melhoradas se for tema claro
                    if new_mode.lower() == "light":
                        self.app.after(0, self.apply_enhanced_colors)
                        time.sleep(0.05)
                    
                    # Revelar a interface com o novo tema
                    self.app.after(0, self._reveal_interface_after_transition)
                    
                    # Executar callback se fornecido
                    if callback:
                        self.app.after(0, callback)
                        
                    logging.debug("Smooth theme transition completed")
                    
                except Exception as e:
                    logging.error(f"Error during smooth theme transition: {e}")
                    # Em caso de erro, garantir que a interface seja revelada
                    self.app.after(0, self._reveal_interface_after_transition)
                    
                finally:
                    self.is_transitioning = False
        
        # Executar transição em thread separada
        thread = threading.Thread(target=transition_worker, daemon=True)
        thread.start()
    
    def _hide_interface_for_transition(self):
        """
        Esconde temporariamente a interface durante a transição.
        """
        try:
            # Esconder todas as janelas (principal e popups) para evitar ghosting
            self._hidden_windows = []
            import tkinter as tk
            def try_withdraw(win):
                try:
                    if hasattr(win, 'winfo_exists') and win.winfo_exists():
                        # Só retirar janelas visíveis
                        if hasattr(win, 'winfo_viewable') and win.winfo_viewable():
                            self._hidden_windows.append(win)
                            win.withdraw()
                except Exception:
                    pass

            # Janela principal
            try_withdraw(self.app)
            # Popups e demais toplevels
            try:
                for child in self.app.winfo_children():
                    # Considerar apenas toplevels/frames-raiz com withdraw
                    if hasattr(child, 'withdraw'):
                        try_withdraw(child)
            except Exception:
                pass

            # Sincronizar estado
            self.app.update_idletasks()
            
        except Exception as e:
            logging.debug(f"Error hiding interface: {e}")
    
    def _create_transition_overlay(self):
        """
        Cria uma overlay de transição (opcional).
        """
        try:
            # Criar um frame overlay simples
            if not hasattr(self, 'transition_overlay'):
                self.transition_overlay = customtkinter.CTkFrame(
                    self.app, 
                    fg_color=("white", "gray10"),
                    corner_radius=0
                )
                
                # Label de loading
                from core.app import App
                loading_label = customtkinter.CTkLabel(
                    self.transition_overlay,
                    text=getattr(self.app, 'translate', lambda k: 'Aplicando tema...')('theme_applying'),
                    font=customtkinter.CTkFont(size=14)
                )
                loading_label.pack(expand=True)
            
            # Mostrar overlay
            self.transition_overlay.place(x=0, y=0, relwidth=1, relheight=1)
            self.transition_overlay.lift()
            
        except Exception as e:
            logging.debug(f"Error creating transition overlay: {e}")
    
    def _apply_theme_in_background(self, new_mode):
        """
        Aplica o tema em background.
        """
        try:
            customtkinter.set_appearance_mode(new_mode)
            self.app.current_appearance_mode = new_mode
            
            # Atualizar todos os componentes da interface
            self._update_all_components_theme()
            
            # Notificar mudança de tema
            if hasattr(self.app.settings_manager, '_notify_theme_change'):
                self.app.settings_manager._notify_theme_change()
                
        except Exception as e:
            logging.error(f"Error applying theme in background: {e}")
    
    def _update_all_components_theme(self):
        """
        Atualiza o tema de todos os componentes da interface.
        """
        try:
            # Atualizar HostTabView (que contém todos os frames)
            if hasattr(self.app, 'host_tab_view') and self.app.host_tab_view:
                if hasattr(self.app.host_tab_view, 'update_theme'):
                    self.app.host_tab_view.update_theme()
            
            # Atualizar componentes específicos que podem estar ativos
            if hasattr(self.app, 'home_frame') and self.app.home_frame:
                if hasattr(self.app.home_frame, 'update_theme'):
                    self.app.home_frame.update_theme()
            
            # Atualizar menu superior e rodapé (AppUIManager) se necessário
            if hasattr(self.app, 'ui_manager') and hasattr(self.app.ui_manager, 'update_ui_texts'):
                # Reaplicar textos e garantir coerência de cores em botões/menus
                self.app.ui_manager.update_ui_texts()

            # Aplicar tokens de tema em toda a árvore
            self.apply_tokens_to_app()

            # Forçar atualização da interface
            self.app.update_idletasks()
            
            logging.debug("All components theme updated successfully")
            
        except Exception as e:
            logging.error(f"Error updating components theme: {e}")

    def get_tokens(self):
        """Retorna o dicionário de tokens conforme o modo atual."""
        mode = customtkinter.get_appearance_mode().lower()
        return self.TOKENS_LIGHT if mode == "light" else self.TOKENS_DARK

    def apply_tokens_to_app(self):
        """Aplica tokens globalmente na aplicação de forma segura/recursiva."""
        try:
            tokens = self.get_tokens()
            self._apply_tokens_recursive(self.app, tokens)
        except Exception as e:
            logging.debug(f"Error applying tokens to app: {e}")

    def _apply_tokens_recursive(self, widget, tokens):
        """Aplica tokens recursivamente a widgets conhecidos do CustomTkinter."""
        try:
            import customtkinter as ctk

            def _cget(w, key):
                try: return w.cget(key)
                except Exception: return None

            def _set(w, **kwargs):
                try: w.configure(**kwargs)
                except Exception: pass

            # Frames
            if isinstance(widget, ctk.CTkFrame):
                fg = _cget(widget, 'fg_color')
                if fg and fg != 'transparent':
                    _set(widget, fg_color=tokens['surface'])

            # Labels
            if isinstance(widget, ctk.CTkLabel):
                _set(widget, text_color=tokens['text'])

            # Botões
            if isinstance(widget, ctk.CTkButton):
                fg = _cget(widget, 'fg_color')
                if fg and fg != 'transparent':
                    _set(widget, fg_color=tokens['primary'], hover_color=tokens['primary_hover'], text_color=tokens['on_primary'])
                else:
                    # Botões transparentes: apenas garantir contraste do texto
                    _set(widget, text_color=tokens['text'])

            # OptionMenu
            if isinstance(widget, ctk.CTkOptionMenu):
                _set(widget, fg_color=tokens['surface_alt'])
                # Alguns temas suportam estas opções
                _set(widget, button_color=tokens['primary'])
                _set(widget, button_hover_color=tokens['primary_hover'])
                _set(widget, text_color=tokens['text'])

            # Textbox
            if hasattr(ctk, 'CTkTextbox') and isinstance(widget, ctk.CTkTextbox):
                _set(widget, fg_color=tokens['surface_alt'])
                _set(widget, text_color=tokens['text'])
                _set(widget, border_color=tokens['border'])

            # Tabview
            if isinstance(widget, ctk.CTkTabview):
                _set(widget, fg_color=tokens['surface'])

            # Prosseguir recursivamente
            if hasattr(widget, 'winfo_children'):
                for child in widget.winfo_children():
                    self._apply_tokens_recursive(child, tokens)

        except Exception as e:
            logging.debug(f"Error applying tokens recursively: {e}")
    
    def _reveal_interface_after_transition(self):
        """
        Revela a interface após a transição de tema.
        """
        try:
            # Forçar atualização do tema aplicado antes de mostrar
            self.app.update_idletasks()

            # Reexibir todas as janelas que foram ocultadas
            try:
                for win in getattr(self, '_hidden_windows', []) or []:
                    try:
                        if hasattr(win, 'deiconify'):
                            win.deiconify()
                            win.update_idletasks()
                    except Exception:
                        pass
            finally:
                self._hidden_windows = []

            # Atualização final
            try:
                self.app.update()
            except Exception:
                pass
            
        except Exception as e:
            logging.debug(f"Error revealing interface: {e}")
