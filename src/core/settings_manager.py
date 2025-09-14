# app/app_settings_manager.py
# Gerencia as configurações da aplicação, como tema, idioma e preferências.

import os
import json
import logging
import customtkinter
from src.config.settings import UI_PREFS_FILE, STATUS_UPDATE_INTERVAL
from src.utils.theme import ThemeEnhancer

class AppSettingsManager:
    def __init__(self, app):
        self.app = app
        self.translator = app.translator
        self.base_dir = app.base_dir
        self.theme_enhancer = ThemeEnhancer(app)

    def load_ui_preferences(self):
        """Carrega as preferências de UI do arquivo JSON."""
        try:
            prefs_path = os.path.join(self.base_dir, UI_PREFS_FILE)
            if os.path.exists(prefs_path):
                with open(prefs_path, "r") as f:
                    prefs = json.load(f)
                    self.app.current_language = prefs.get("language", "pt-BR")
                    self.app.current_appearance_mode = prefs.get("appearance_mode", "System")
                    self.app.status_update_interval = prefs.get("status_update_interval", STATUS_UPDATE_INTERVAL)
                    self.app.ask_for_initial_info_on_select = prefs.get("ask_initial_info", True)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Erro ao carregar UI Prefs: {e}")
        finally:
            self.translator.set_language(self.app.current_language)
            customtkinter.set_appearance_mode(self.app.current_appearance_mode)
            # Aplicar cores melhoradas se for tema claro
            if self.app.current_appearance_mode.lower() == "light":
                self.theme_enhancer.apply_enhanced_colors()

    def save_ui_preferences(self):
        """Salva as preferências de UI atuais no arquivo JSON."""
        try:
            prefs_path = os.path.join(self.base_dir, UI_PREFS_FILE)
            prefs = {
                "language": self.app.current_language, 
                "appearance_mode": self.app.current_appearance_mode,
                "status_update_interval": self.app.status_update_interval,
                "ask_initial_info": self.app.ask_for_initial_info_on_select
            }
            with open(prefs_path, "w") as f:
                json.dump(prefs, f, indent=4)
        except Exception as e:
            logging.error(f"Erro ao salvar UI Prefs: {e}")

    def change_language_event(self, new_language_display_name: str):
        """Lida com a mudança de idioma a partir do menu."""
        try:
            lang_code = self.get_language_code(new_language_display_name)
            if lang_code != self.app.current_language:
                logging.debug(f"Changing language from {self.app.current_language} to {lang_code}")
                
                # Limpar cache de traduções ANTES de mudar o idioma
                self.app.clear_translation_cache()
                
                # Atualizar tradutor
                self.translator.set_language(lang_code)
                self.translator.previous_lang = self.app.current_language
                self.app.current_language = lang_code
                
                # Forçar atualização completa de todas as traduções
                self.app.force_update_translations()
                
                # Salvar preferências
                self.save_ui_preferences()
                
                # Forçar atualização da interface (otimizado)
                if not getattr(self.app, '_resize_in_progress', False):
                    self.app.update_idletasks()
                
                logging.debug(f"Language change completed: {lang_code}")
            else:
                logging.debug(f"Language already set to {lang_code}")
                
        except Exception as e:
            logging.error(f"Erro ao mudar idioma: {e}")
            # Tentar restaurar o idioma anterior em caso de erro
            try:
                if hasattr(self, 'translator') and hasattr(self.translator, 'previous_lang'):
                    self.translator.set_language(self.translator.previous_lang)
                    self.app.current_language = self.translator.previous_lang
                    logging.debug("Idioma restaurado após erro")
            except:
                pass

    def get_language_display_name(self, lang_code):
        return {"pt-BR": "Português", "en-US": "English", "es-ES": "Español"}.get(lang_code, "Português")

    def get_language_code(self, display_name):
        return {"Português": "pt-BR", "English": "en-US", "Español": "es-ES"}.get(display_name, "pt-BR")

    def change_appearance_mode_event(self, new_appearance_mode_display_name: str):
        """
        Lida com a mudança de tema de aparência.
        Implementa transição suave em background para evitar ghosting.
        """
        mode_map = {
            self.app.translate("label_light"): "Light", 
            self.app.translate("label_dark"): "Dark", 
            self.app.translate("label_system"): "System"
        }
        new_mode = mode_map.get(new_appearance_mode_display_name)
        if new_mode and new_mode != self.app.current_appearance_mode:
            logging.debug(f"Starting smooth theme transition from {self.app.current_appearance_mode} to {new_mode}")
            
            # Se for "System", detectar o tema atual do sistema
            if new_mode == "System":
                try:
                    # Detectar tema do sistema usando múltiplas abordagens
                    system_theme = self._detect_system_theme()
                    logging.debug(f"System theme detected: {system_theme}")
                    # Aplicar o tema detectado
                    new_mode = system_theme
                except Exception as e:
                    logging.error(f"Error detecting system theme: {e}")
                    new_mode = "Dark"  # Fallback para escuro
            
            # Usar o novo sistema de transição suave em background
            def on_transition_complete():
                self.app.current_appearance_mode = new_mode
                self.save_ui_preferences()
                logging.debug("Smooth appearance mode change completed successfully")
            
            # Executar transição suave em background
            self.theme_enhancer.smooth_theme_transition(new_mode, on_transition_complete)
    
    def _notify_theme_change(self):
        """
        Notifica todos os componentes sobre a mudança de tema para atualização em lote.
        Isso evita o efeito de ghosting causado por atualizações individuais.
        """
        try:
            # Lista de componentes que precisam ser atualizados
            components_to_update = []
            
            # Verificar e adicionar host_tab_view se existir
            if hasattr(self.app, 'host_tab_view') and self.app.host_tab_view:
                components_to_update.append(self.app.host_tab_view)
            
            # Atualizar todos os componentes em lote
            for component in components_to_update:
                try:
                    # Verificar se o componente tem método update_theme
                    if hasattr(component, 'update_theme'):
                        component.update_theme()
                    
                    # Para host_tab_view, atualizar também suas abas
                    if hasattr(component, 'tab_view') and hasattr(component.tab_view, '_tab_dict'):
                        for tab_name, tab_frame in component.tab_view._tab_dict.items():
                            # Procurar por frames filhos que tenham update_theme
                            self._update_tab_theme_recursive(tab_frame)
                            
                except Exception as e:
                    logging.warning(f"Failed to update theme for component {component}: {e}")
            
            logging.debug(f"Theme update completed for {len(components_to_update)} components")
            
        except Exception as e:
            logging.error(f"Error during theme change notification: {e}")
    
    def _update_tab_theme_recursive(self, widget):
        """
        Atualiza tema recursivamente em widgets filhos.
        """
        try:
            # Se o widget tem método update_theme, chama
            if hasattr(widget, 'update_theme'):
                widget.update_theme()
            
            # Procura recursivamente por widgets filhos
            if hasattr(widget, 'winfo_children'):
                for child in widget.winfo_children():
                    self._update_tab_theme_recursive(child)
                    
        except Exception as e:
            logging.debug(f"Error updating theme recursively for widget: {e}")

    def get_appearance_mode_display_name(self, mode_name: str):
        key_map = {"Light": "label_light", "Dark": "label_dark", "System": "label_system"}
        translation_key = key_map.get(mode_name, "label_system")
        return self.app.translate(translation_key)

    def _detect_system_theme(self):
        """
        Detecta o tema atual do sistema Windows usando múltiplas abordagens.
        Retorna 'Light' ou 'Dark'.
        """
        import platform
        
        if platform.system() != "Windows":
            return "Dark"  # Fallback para sistemas não-Windows
        
        try:
            # Abordagem 1: Usar winreg para verificar AppsUseLightTheme
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    if value == 1:
                        return "Light"
                    else:
                        return "Dark"
            except (FileNotFoundError, OSError) as e:
                logging.debug(f"Registry approach failed: {e}")
            
            # Abordagem 2: Usar winreg para verificar SystemUsesLightTheme
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
                    if value == 1:
                        return "Light"
                    else:
                        return "Dark"
            except (FileNotFoundError, OSError) as e:
                logging.debug(f"SystemUsesLightTheme approach failed: {e}")
            
            # Abordagem 3: Usar ctypes para verificar DWM
            try:
                import ctypes
                from ctypes import wintypes
                
                # Definir estruturas necessárias
                class DWMCOLORIZATIONPARAMS(ctypes.Structure):
                    _fields_ = [
                        ("clrColor", wintypes.DWORD),
                        ("clrAfterGlow", wintypes.DWORD),
                        ("nIntensity", wintypes.UINT),
                        ("clrAfterGlowBalance", wintypes.UINT),
                        ("clrBlurBalance", wintypes.UINT),
                        ("clrGlassReflectionIntensity", wintypes.UINT),
                        ("fOpaque", wintypes.BOOL)
                    ]
                
                # Carregar dwmapi.dll
                dwmapi = ctypes.windll.dwmapi
                
                # Obter parâmetros de colorização
                params = DWMCOLORIZATIONPARAMS()
                result = dwmapi.DwmGetColorizationParameters(ctypes.byref(params))
                
                if result == 0:  # S_OK
                    # Se fOpaque for True, provavelmente é tema escuro
                    if params.fOpaque:
                        return "Dark"
                    else:
                        return "Light"
                        
            except Exception as e:
                logging.debug(f"DWM approach failed: {e}")
            
            # Abordagem 4: Verificar se o tema atual é "Dark" no registro
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    try:
                        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                        return "Light" if value == 1 else "Dark"
                    except FileNotFoundError:
                        # Se não encontrar AppsUseLightTheme, verificar outras chaves
                        pass
                        
                # Verificar se existe alguma chave relacionada ao tema escuro
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    try:
                        # Tentar outras chaves possíveis
                        value, _ = winreg.QueryValueEx(key, "EnableTransparency")
                        # Se EnableTransparency existe, provavelmente é tema claro
                        return "Light"
                    except FileNotFoundError:
                        pass
                        
            except Exception as e:
                logging.debug(f"Alternative registry approach failed: {e}")
            
            # Abordagem 5: Verificar o tema atual do sistema
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                   r"Software\Microsoft\Windows\CurrentVersion\Themes") as key:
                    try:
                        theme_file, _ = winreg.QueryValueEx(key, "CurrentTheme")
                        # Se o tema contém "dark" ou "Dark", é tema escuro
                        if "dark" in theme_file.lower():
                            return "Dark"
                        else:
                            return "Light"
                    except FileNotFoundError:
                        pass
            except Exception as e:
                logging.debug(f"Theme file approach failed: {e}")
            
            # Fallback: usar CustomTkinter para detectar
            try:
                current_theme = customtkinter.get_appearance_mode()
                if current_theme in ["Light", "Dark"]:
                    return current_theme
            except Exception as e:
                logging.debug(f"CustomTkinter approach failed: {e}")
            
            # Último fallback: assumir tema escuro (mais comum)
            logging.warning("All theme detection methods failed, using Dark as fallback")
            return "Dark"
            
        except Exception as e:
            logging.error(f"Error in system theme detection: {e}")
            return "Dark"  # Fallback final