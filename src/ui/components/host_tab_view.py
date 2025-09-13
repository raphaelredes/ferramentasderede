# app/ui_components/host_tab_view.py
# Orquestra a exibição e o conteúdo das abas de host.

import customtkinter
import threading
import ipaddress
import logging
from .host_tab_manager.tab_manager import HostTabManager
from .host_tab_manager.home_tab_manager import HomeTabManager
from .host_tab_manager.tool_factory import ToolFrameFactory
from .tab_status_indicator import TabStatusIndicator

def is_valid_ip(address):
    """Verifica se uma string é um endereço IPv4 válido."""
    try:
        import ipaddress
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False

class HostTabView(customtkinter.CTkFrame):
    def __init__(self, master, app, controller):
        super().__init__(master, fg_color="transparent")
        logging.info("Initializing HostTabView")
        self.app = app
        self.controller = controller
        
        self.loaded_tabs = set()
        
        self.tool_factory = ToolFrameFactory(self.app)
        
        self.tab_view_container = customtkinter.CTkFrame(self, fg_color="transparent")
        self.tab_view_container.pack(fill="both", expand=True)
        
        self.tab_view = customtkinter.CTkTabview(self.tab_view_container, fg_color="transparent")
        self.tab_view.pack(side="left", fill="both", expand=True)

        self.tab_manager = HostTabManager(self.tab_view, self.app, self.controller._on_tab_selected)
        
        # Inicializar indicador de status
        self.status_indicator = TabStatusIndicator(self.tab_view)
        
        self.home_tab_manager = None

        # Botão de configurações
        self.settings_button = customtkinter.CTkButton(
            self.tab_view_container, text="⚙️", width=30, height=30, 
            font=customtkinter.CTkFont(size=20), fg_color="transparent",
            hover=False, command=self.controller.open_tab_settings_dialog
        )
        self.settings_button.pack(side="right", anchor="ne", padx=5, pady=5)
        
        # Botão para adicionar novo host
        self.add_host_button = customtkinter.CTkButton(
            self.tab_view_container, text="+", width=30, height=30, 
            font=customtkinter.CTkFont(size=20, weight="bold"), fg_color="transparent",
            hover_color=("gray70", "gray30"), command=self.controller.add_new_host
        )
        self.add_host_button.pack(side="right", anchor="ne", padx=(0, 5), pady=5)
        
        # Adicionar tooltip melhorado ao botão
        from .enhanced_tooltip import create_tooltip
        self.add_host_tooltip = create_tooltip(self.add_host_button, self.app.translate("add_host_button_tooltip"))
        
    def start_command_status(self, tab_name, command_name):
        """Inicia o indicador de status para um comando."""
        self.status_indicator.start_command(tab_name, command_name)
        
    def finish_command_status(self, tab_name, success=True):
        """Finaliza o indicador de status para um comando."""
        self.status_indicator.finish_command(tab_name, success)
        
    def clear_all_status_indicators(self):
        """Limpa todos os indicadores de status."""
        self.status_indicator.clear_all_indicators()

    def load_tools_for_host(self, host_data):        
        logging.debug(f"load_tools_for_host chamado para host_data: {host_data}")
        host_info = host_data['host_info']
        host_name_key = host_info['name']

        if host_name_key in self.loaded_tabs:
            return
        
        display_name = self.tab_manager._get_display_name(host_info)
        logging.info(f"Loading tools for host tab: {display_name}")
        tab_frame = self.tab_manager.tab_view.tab(display_name)
        
        info_display, tool_tab_view = self.tool_factory.create_host_skeleton(tab_frame)
        host_data.update({
            "info_display": info_display,
            "tool_tab_view": tool_tab_view,
            "loaded_tool_tabs": set()
        })

        # Ocultar as sub-abas imediatamente após criação
        self._hide_tool_tabs_during_resolution(tool_tab_view, display_name)

        def resolve_and_prepare_tools():
            # Usar o IP atual do host (que pode ter sido atualizado)
            ip = host_info['ip']
            hostname = host_info.get('resolved_hostname', host_info['name'])
            
            # Se o IP é válido, usar diretamente; caso contrário, tentar resolver
            if not is_valid_ip(ip):
                target_for_connection = host_info['name']
                ip, hostname = self.controller.network_tools.resolve_ip_and_hostname(target_for_connection)
            
            def setup_ui_and_controllers():
                info_display.update_info(ip=ip, hostname=hostname)
                
                # Carregar ferramentas de forma lazy
                self._load_tools_lazy(host_data, ip, hostname)
                
                # Mostrar as sub-abas após a resolução
                self._show_tool_tabs_after_resolution(tool_tab_view, display_name)
                
                # Marcar como carregado
                self.loaded_tabs.add(host_name_key)
                
            # Executar na thread principal para evitar problemas de UI
            self.app.after(0, setup_ui_and_controllers)
        
        # Executar resolução em thread separada para não bloquear UI
        threading.Thread(target=resolve_and_prepare_tools, daemon=True).start()

    def _load_tools_lazy(self, host_data, ip, hostname):
        """Carrega ferramentas on-demand ao selecionar a sub-aba (lazy)."""
        try:
            tool_tab_view = host_data.get("tool_tab_view")
            if not tool_tab_view or not tool_tab_view.winfo_exists():
                return

            # Preparar host com IP resolvido
            host_with_resolved_ip = host_data['host_info'].copy()
            host_with_resolved_ip['ip'] = ip

            # Criar controladores para este host e armazenar
            controllers = self.tool_factory.create_controllers(host_with_resolved_ip, hostname)
            host_data["tool_controllers"] = controllers

            # Callback ao selecionar uma sub-aba de ferramenta
            def on_tool_tab_select():
                selected_translated = tool_tab_view.get()
                # Mapear para a key original
                selected_key = next(
                    (key for key in self.tool_factory.tool_tab_keys if self.app.translate(key) == selected_translated),
                    None
                )
                if selected_key and selected_key not in host_data["loaded_tool_tabs"]:
                    self.tool_factory.create_tool_frame_on_demand(
                        selected_key, tool_tab_view, host_with_resolved_ip, controllers, host_data.get("info_display")
                    )
                    host_data["loaded_tool_tabs"].add(selected_key)

            tool_tab_view.configure(command=on_tool_tab_select)

            # Carregar a primeira aba (ping) imediatamente
            first_key = self.tool_factory.tool_tab_keys[0]
            self.tool_factory.create_tool_frame_on_demand(
                first_key, tool_tab_view, host_with_resolved_ip, controllers, host_data.get("info_display")
            )
            host_data["loaded_tool_tabs"].add(first_key)

        except Exception as e:
            logging.error(f"Erro ao configurar carregamento lazy das ferramentas: {e}")

    def _load_single_tool_lazy(self, host_data, tool_name, ip, hostname):
        """Carrega uma ferramenta específica de forma lazy."""
        try:
            if tool_name not in host_data["loaded_tool_tabs"]:
                self._load_single_tool(host_data, tool_name, ip, hostname)
                host_data["loaded_tool_tabs"].add(tool_name)
        except Exception as e:
            logging.error(f"Erro ao carregar ferramenta {tool_name}: {e}")

    def _load_single_tool(self, host_data, tool_name, ip, hostname):
        """Carrega uma ferramenta específica."""
        try:
            tool_tab_view = host_data["tool_tab_view"]
            
            # Mapear nomes de ferramentas para chaves de tradução
            tool_name_to_key = {
                'ping': 'ping_title',
                'traceroute': 'traceroute_title',
                'scanner': 'scanner_title',
                'system_info': 'sysinfo_title',
                'services': 'services_title',
                'remote_actions': 'remote_actions_title',
                'event_log': 'event_logs_title',
                'remote_shell': 'remote_shell_title',
                'activity': 'activity_title'
            }
            
            # Obter o nome da aba traduzido
            tab_key = tool_name_to_key.get(tool_name)
            if not tab_key:
                logging.error(f"Chave de tradução não encontrada para ferramenta: {tool_name}")
                return
                
            tab_name = self.app.translate(tab_key)
            parent_tab = tool_tab_view.tab(tab_name)
            
            # Limpar placeholder se existir
            for widget in parent_tab.winfo_children():
                widget.destroy()
            
            if tool_name == 'ping':
                from .ping_frame import PingFrame
                ping_frame = PingFrame(parent_tab, self.app, host_data['host_info'], self.controller.network_tools)
                ping_frame.pack(fill="both", expand=True)
                
            elif tool_name == 'traceroute':
                from .traceroute_frame import TracerouteFrame
                traceroute_frame = TracerouteFrame(parent_tab, self.app, host_data['host_info'], self.controller.network_tools)
                traceroute_frame.pack(fill="both", expand=True)
                
            # Comentando outras ferramentas até serem corrigidas
            # elif tool_name == 'scanner':
            #     from .discover_dialog import DiscoverDialog
            #     scanner_frame = DiscoverDialog(parent_tab, self.app, self.controller, ip, hostname)
            #     scanner_frame.pack(fill="both", expand=True)
                
            # elif tool_name == 'system_info':
            #     from .system_info_panel import SystemInfoPanel
            #     sysinfo_frame = SystemInfoPanel(parent_tab, self.app)
            #     sysinfo_frame.pack(fill="both", expand=True)
                
            # elif tool_name == 'services':
            #     from .services_frame import ServicesFrame
            #     services_frame = ServicesFrame(parent_tab, self.app, host_data['host_info'], self.controller.services_tools)
            #     services_frame.pack(fill="both", expand=True)
                
            # elif tool_name == 'remote_actions':
            #     from .remote_actions_frame import RemoteActionsFrame
            #     remote_frame = RemoteActionsFrame(parent_tab, self.app, host_data['host_info'], self.controller.remote_tools)
            #     remote_frame.pack(fill="both", expand=True)
                
        except Exception as e:
            logging.error(f"Erro ao carregar ferramenta {tool_name}: {e}")

    def get_tool_controller_for_host(self, host_data, tool_key):
        """
        Obtém ou cria os controladores de ferramentas para um host e retorna o específico.
        Usado pelo AppController para o pré-carregamento de dados.
        """
        host_info = host_data['host_info']
        logging.debug(f"Attempting to get tool controller '{tool_key}' for host: {host_info.get('name', host_info.get('ip'))}")
        host_name_key = host_info['name']

        # Se os controladores já existem para este host, retorna o solicitado
        tab_data = self.host_tabs_data.get(host_name_key, {})
        if 'tool_controllers' in tab_data:
            return tab_data['tool_controllers'].get(tool_key)

        # Se não, cria todos os controladores para o host
        ip = host_info.get('ip')
        hostname = host_info.get('name')
        
        # Garante que temos um IP para criar os controladores
        if not is_valid_ip(ip):
            ip, hostname = self.controller.network_tools.resolve_ip_and_hostname(hostname)
            if not ip:
                logging.warning(f"Could not resolve IP for host {host_name_key}. Cannot create tool controller.")
                return None # Não foi possível resolver, não pode criar controlador
            logging.debug(f"Resolved IP for {host_name_key}: {ip}")

        host_with_resolved_ip = host_info.copy()
        host_with_resolved_ip['ip'] = ip

        controllers = self.tool_factory.create_controllers(host_with_resolved_ip, hostname)
        
        # Armazena os controladores recém-criados nos dados da aba
        if host_name_key in self.host_tabs_data:
            self.host_tabs_data[host_name_key]["tool_controllers"] = controllers
        else:
            # Isso pode acontecer se a aba ainda não foi totalmente inicializada
            self.host_tabs_data[host_name_key] = {"tool_controllers": controllers}
        logging.debug(f"Tool controllers created for {host_name_key}")
        return controllers.get(tool_key)

    def clear_all_tabs(self):
        logging.info("Clearing all host tabs")
        self.tab_manager.clear_all()
        self.loaded_tabs.clear()

    def add_host_tab(self, host, switch_to=True):
        logging.info(f"Adding host tab for: {host.get('name', host.get('ip'))}")
        self.tab_manager.add_tab(host, switch_to)

    def remove_host_tab(self, host):
        logging.info(f"Removing host tab for: {host.get('name', host.get('ip'))}")
        host_name_key = host['name']
        self.tab_manager.remove_tab(host)
        logging.debug(f"Removed host tab from manager: {host_name_key}")
        if host_name_key in self.loaded_tabs:
            self.loaded_tabs.remove(host_name_key)
            
    def populate_initial_tabs(self, hosts, select_tab_named: str = None):
        if self.tab_manager.placeholder_name not in self.tab_view._name_list:
            placeholder_tab = self.tab_view.add(self.tab_manager.placeholder_name)
            # Passa a referência do HostTabManager para o HomeTabManager
            from .host_tab_manager.home_tab_manager import HomeTabManager
            self.home_tab_manager = HomeTabManager(placeholder_tab, self.app, self)
        
        logging.info("Populating initial host tabs")
        self.tab_manager.populate_initial(hosts, select_tab_named)

    def update_host_status_indicator(self, host_name_key):
        self.tab_manager.update_status_indicator(host_name_key)
        logging.debug(f"Updated status indicator for host tab: {host_name_key}")
        
    def _get_display_name(self, host_info):
        return self.tab_manager._get_display_name(host_info)
        
    def get_all_tab_names(self):
        return self.tab_manager.get_all_tab_names()
        
    @property
    def host_tabs_data(self):
        return self.tab_manager.host_tabs_data

    def update_language(self):
        logging.debug("Updating language across host tabs")
        
        # Atualizar gerenciador de abas
        self.tab_manager.update_language()
        
        # Atualizar aba Home se existir
        if self.home_tab_manager:
            self.home_tab_manager.update_language()
        
        # Atualizar tooltip do botão de adicionar host
        if hasattr(self, 'add_host_tooltip'):
            self.add_host_tooltip.update_text(self.app.translate("add_host_button_tooltip"))
        
        # Propaga a atualização de idioma para a fábrica de ferramentas
        self.tool_factory.update_language()
        
        # Atualiza os info_displays que já foram carregados
        for host_name_key, tab_data in self.host_tabs_data.items():
            if host_name_key in self.loaded_tabs and "info_display" in tab_data:
                try:
                    tab_data["info_display"].update_language()
                except Exception as e:
                    logging.warning(f"Erro ao atualizar info_display para {host_name_key}: {e}")
        
        logging.debug("Language update completed in HostTabView")
    
    def _is_paused(self):
        """
        Verifica se o HostTabView está pausado.
        """
        return getattr(self, '_paused', False)
    
    def _should_skip_heavy_operation(self):
        """
        Verifica se deve pular operações pesadas.
        """
        return self._is_paused() or getattr(self.app, '_static_mode', False)

    def update_theme(self):
        """
        Atualiza o tema de todos os componentes carregados.
        Chamado quando o tema da aplicação muda.
        """
        logging.debug("Updating theme in HostTabView")
        
        # Atualiza tema da aba Home se existir
        if self.home_tab_manager and hasattr(self.home_tab_manager, 'home_frame'):
            if hasattr(self.home_tab_manager.home_frame, 'update_theme'):
                self.home_tab_manager.home_frame.update_theme()
        
        # Atualiza tema das abas de host carregadas
        for host_name_key, tab_data in self.host_tabs_data.items():
            if host_name_key in self.loaded_tabs:
                try:
                    # Atualiza cada frame da aba se tiver método update_theme
                    for frame_name, frame in tab_data.items():
                        if hasattr(frame, 'update_theme'):
                            frame.update_theme()
                            logging.debug(f"Updated theme for {frame_name} in host {host_name_key}")
                except Exception as e:
                    logging.warning(f"Failed to update theme for host tab {host_name_key}: {e}")
        
        logging.debug("Theme update completed in HostTabView")

    def _hide_tool_tabs_during_resolution(self, tool_tab_view, display_name):
        """Oculta as sub-abas durante a resolução de informações."""
        try:
            # Forçar atualização da UI antes de ocultar
            self.app.update_idletasks()
            
            # Ocultar o widget de abas completamente
            tool_tab_view.grid_remove()
            
            # Criar um frame de loading se não existir
            parent = tool_tab_view.master
            if not hasattr(parent, '_loading_frame'):
                loading_frame = customtkinter.CTkFrame(parent, fg_color="transparent")
                loading_frame.grid(row=0, column=0, sticky="nsew")
                
                loading_label = customtkinter.CTkLabel(
                    loading_frame, 
                    text=f"Resolvendo informações para {display_name}...",
                    font=customtkinter.CTkFont(size=14),
                    text_color="gray"
                )
                loading_label.pack(expand=True)
                
                parent._loading_frame = loading_frame
                parent._loading_label = loading_label
            else:
                # Atualizar o texto do loading
                parent._loading_label.configure(text=f"Resolvendo informações para {display_name}...")
                parent._loading_frame.grid()
            
            # Forçar atualização da UI após ocultar
            self.app.update_idletasks()
            logging.debug(f"Hidden tool tabs for {display_name} during resolution")
        except Exception as e:
            logging.warning(f"Failed to hide tool tabs for {display_name}: {e}")

    def _show_tool_tabs_after_resolution(self, tool_tab_view, display_name):
        """Mostra as sub-abas após a resolução de informações."""
        try:
            # Ocultar o frame de loading
            parent = tool_tab_view.master
            if hasattr(parent, '_loading_frame'):
                parent._loading_frame.grid_remove()
            
            # Mostrar o widget de abas
            tool_tab_view.grid()
            
            # Forçar atualização da UI após mostrar
            self.app.update_idletasks()
            logging.debug(f"Shown tool tabs for {display_name} after resolution")
        except Exception as e:
            logging.warning(f"Failed to show tool tabs for {display_name}: {e}")