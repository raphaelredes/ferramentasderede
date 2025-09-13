# src/ferramentasderede/ui/components/host_tab_manager/tool_factory.py
# Responsável por criar o conjunto de frames e controladores de ferramentas para um host.

import customtkinter
from ..tool_controllers.network_tool_controller import NetworkToolController
from ..tool_controllers.remote_actions_controller import RemoteActionsController
from ..tool_controllers.sysinfo_controller import SysInfoController
from ..tool_controllers.services_controller import ServicesController
from ..tool_controllers.event_log_controller import EventLogController
from ..tool_controllers.remote_shell_controller import RemoteShellController
from ..tool_controllers.activity_controller import ActivityController
from ..info_widgets import HostInfoDisplay
import logging

class ToolFrameFactory:
    def __init__(self, app):
        self.app = app
        self.tool_tab_views = [] # Rastreia todas as tool_tab_view criadas
        self.tab_name_mappings = {} # Mapeia nomes originais para traduzidos
        
    def create_host_skeleton(self, parent_tab_frame):
        parent_tab_frame.grid_rowconfigure(1, weight=1)
        parent_tab_frame.grid_columnconfigure(0, weight=1)
        
        info_display = HostInfoDisplay(parent_tab_frame, self.app)
        info_display.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        info_display.update_info(ip="...", hostname=self.app.translate("loading_text"), subnet_mask="...")
        
        tools_container = customtkinter.CTkFrame(parent_tab_frame, fg_color="transparent")
        tools_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        tools_container.grid_rowconfigure(0, weight=1)
        tools_container.grid_columnconfigure(0, weight=1)
        
        tool_tab_view = customtkinter.CTkTabview(tools_container)
        tool_tab_view.grid(row=0, column=0, sticky="nsew")
        
        # Definir as chaves de tradução para as abas (ordem define a primeira aba carregada)
        self.tool_tab_keys = [
            "ping_title", "traceroute_title", "remote_actions_title",
            "sysinfo_title", "services_title", "event_logs_title",
            "remote_shell_title", "activity_title"
        ]
        
        # Criar todas as abas com nomes traduzidos
        for key in self.tool_tab_keys:
            translated_name = self.app.translate(key)
            tool_tab_view.add(translated_name)
            
            # Armazenar o mapeamento para uso futuro
            self.tab_name_mappings[key] = translated_name
            
            # Adicionar placeholder para cada aba
            placeholder_frame = customtkinter.CTkFrame(tool_tab_view.tab(translated_name))
            placeholder_frame.pack(fill="both", expand=True)
            
            placeholder_label = customtkinter.CTkLabel(
                placeholder_frame, 
                text=self.app.translate("loading_text"),
                font=customtkinter.CTkFont(size=14)
            )
            placeholder_label.pack(expand=True)

        # Ocultar as sub-abas por padrão até que a resolução seja concluída
        tool_tab_view.grid_remove()

        self.tool_tab_views.append(tool_tab_view)
        return info_display, tool_tab_view

    def update_language(self):
        """Atualiza os nomes das abas e o conteúdo dos frames carregados."""
        logging.debug("Iniciando atualização de idioma no ToolFactory")
        
        for tool_tab_view in self.tool_tab_views:
            if not tool_tab_view.winfo_exists():
                continue
            
            try:
                # Recriar completamente as abas com os novos nomes traduzidos
                self._recreate_tabs_with_new_language(tool_tab_view)
                
                # Atualizar linguagem de todos os frames carregados
                self._update_frames_language(tool_tab_view)
                        
            except Exception as e:
                logging.error(f"Erro geral ao atualizar linguagem do tool_tab_view: {e}")
        
        logging.debug("Atualização de idioma no ToolFactory concluída")

    def _recreate_tabs_with_new_language(self, tool_tab_view):
        """Recria as abas com os novos nomes traduzidos."""
        try:
            # Armazenar o conteúdo atual das abas
            current_content = {}
            current_selection = tool_tab_view.get()
            
            # Coletar conteúdo de todas as abas existentes
            for key in self.tool_tab_keys:
                old_name = self.tab_name_mappings.get(key, key)
                if old_name in tool_tab_view._tab_dict:
                    tab_frame = tool_tab_view._tab_dict[old_name]
                    current_content[key] = [widget for widget in tab_frame.winfo_children()]
            
            # Limpar todas as abas existentes
            for name in tool_tab_view._name_list[:]:  # Cópia da lista para evitar modificação durante iteração
                try:
                    tool_tab_view.delete(name)
                except:
                    pass
            
            # Recriar abas com novos nomes traduzidos
            for key in self.tool_tab_keys:
                new_name = self.app.translate(key)
                self.tab_name_mappings[key] = new_name
                tool_tab_view.add(new_name)
                
                # Restaurar conteúdo se existia
                if key in current_content:
                    tab_frame = tool_tab_view._tab_dict[new_name]
                    for widget in current_content[key]:
                        try:
                            widget.pack_forget()
                            widget.pack(in_=tab_frame, fill="both", expand=True)
                        except:
                            pass
                else:
                    # Adicionar placeholder se não havia conteúdo
                    placeholder_frame = customtkinter.CTkFrame(tool_tab_view.tab(new_name))
                    placeholder_frame.pack(fill="both", expand=True)
                    
                    placeholder_label = customtkinter.CTkLabel(
                        placeholder_frame, 
                        text=self.app.translate("loading_text"),
                        font=customtkinter.CTkFont(size=14)
                    )
                    placeholder_label.pack(expand=True)
            
            # Restaurar seleção se possível
            if current_selection:
                try:
                    tool_tab_view.set(current_selection)
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"Erro ao recriar abas: {e}")

    def _update_frames_language(self, tool_tab_view):
        """Atualiza a linguagem de todos os frames carregados."""
        try:
            for tab_name in tool_tab_view._name_list:
                tab_frame = tool_tab_view._tab_dict.get(tab_name)
                if tab_frame:
                    for widget in tab_frame.winfo_children():
                        if hasattr(widget, 'update_language') and callable(widget.update_language):
                            try:
                                widget.update_language()
                            except Exception as e:
                                logging.warning(f"Erro ao atualizar linguagem do widget: {e}")
        except Exception as e:
            logging.error(f"Erro ao atualizar frames: {e}")

    def create_controllers(self, host, hostname):
        return {
            'network': NetworkToolController(self.app, host, hostname),
            'remote': RemoteActionsController(self.app, host, hostname),
            'system_info': SysInfoController(self.app, host, hostname),
            'services': ServicesController(self.app, host, hostname),
            'event_log': EventLogController(self.app, host, hostname),
            'remote_shell': RemoteShellController(self.app, host, hostname),
            'activity': ActivityController(self.app, host, hostname)
        }

    def create_tool_frame_on_demand(self, tab_name_key, tab_view, host, controllers, info_display):
        from ..ping_frame import PingFrame
        from ..traceroute_frame import TracerouteFrame
        from ..remote_sessions_frame import RemoteSessionsFrame
        from ..system_tools_frame import SystemToolsFrame
        from ..services_frame import ServicesFrame
        from ..event_log_frame import EventLogFrame
        from ..remote_shell_frame import RemoteShellFrame
        
        frame_map = {
            "ping_title": (PingFrame, controllers['network']),
            "traceroute_title": (TracerouteFrame, controllers['network']),
            "remote_actions_title": (RemoteSessionsFrame, controllers['remote'], {"info_display": info_display}),
            "sysinfo_title": (SystemToolsFrame, controllers['system_info'], {"info_display": info_display}),
            "services_title": (ServicesFrame, controllers['services']),
            "event_logs_title": (EventLogFrame, controllers['event_log']),
            "remote_shell_title": (RemoteShellFrame, controllers['remote_shell'])
        }

        # Usar o nome traduzido atual
        tab_name_translated = self.tab_name_mappings.get(tab_name_key, self.app.translate(tab_name_key))
        parent_tab = tab_view.tab(tab_name_translated)

        # Limpa qualquer conteúdo placeholder ou antigo antes de adicionar o novo frame
        for widget in parent_tab.winfo_children():
            widget.destroy()

        if tab_name_key in frame_map:
            frame_info = frame_map[tab_name_key]
            if len(frame_info) == 2:
                FrameClass, controller = frame_info
                frame = FrameClass(parent_tab, self.app, host, controller)
            else:
                FrameClass, controller, kwargs = frame_info
                frame = FrameClass(parent_tab, self.app, host, controller, **kwargs)
            frame.pack(fill="both", expand=True)

        elif tab_name_key == "activity_title":
            controllers['activity'].handle_activity_tab_first_load(parent_tab)

        if tab_name_key in ["ping_title", "traceroute_title"]:
            ping_frame = self.find_widget_by_class(tab_view.tab(self.tab_name_mappings.get("ping_title", self.app.translate("ping_title"))), PingFrame)
            trace_frame = self.find_widget_by_class(tab_view.tab(self.tab_name_mappings.get("traceroute_title", self.app.translate("traceroute_title"))), TracerouteFrame)
            
            def update_network_buttons(status_data=None):
                if ping_frame and ping_frame.winfo_exists(): ping_frame.update_button_state()
                if trace_frame and trace_frame.winfo_exists(): trace_frame.update_button_state()
            controllers['network'].set_state_change_callback(update_network_buttons)

    def find_widget_by_class(self, parent, widget_class):
        for child in parent.winfo_children():
            if isinstance(child, widget_class):
                return child
        return None