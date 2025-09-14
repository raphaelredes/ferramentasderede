# app/app_controller.py

import threading
import time
from tkinter import filedialog
import customtkinter
import os
import shutil
import sys
import ipaddress
import logging

from src.network.tools import NetworkTools
from .host_manager import HostManager
from src.ui.components.add_host_dialog import AddHostDialog
from src.ui.components.remove_host_dialog import RemoveHostDialog
from src.ui.components.custom_input_dialog import CustomInputDialog
from src.ui.components.tab_settings_dialog import TabSettingsDialog
from src.ui.components.loading_window import LoadingWindow
from src.config.settings import (FAVORITES_FILE, UI_PREFS_FILE, DISCOVERY_CACHE_FILE, 
                     HOST_CHECK_BATCH_SIZE, HOST_CHECK_BATCH_DELAY)

def is_valid_ip(address):
    """Verifica se uma string é um endereço IPv4 válido."""
    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False

class AppController:
    def __init__(self, app):
        self.app = app
        self.network_tools = NetworkTools()
        self.host_manager = HostManager()

    def load_and_prepare_all_hosts(self, update_status_callback):
        """Carrega hosts do arquivo e verifica o status de cada um de forma otimizada."""
        logging.debug("Iniciando 'load_and_prepare_all_hosts' otimizado.")
        update_status_callback(self.app.translate("loading_hosts"))
        self.app.favorites = self.host_manager.get_all_hosts()
        
        total_hosts = len(self.app.favorites)
        logging.debug(f"Total de {total_hosts} hosts para verificar.")
        
        if total_hosts == 0:
            logging.debug("Nenhum host para verificar.")
            return
        
        # Usar ThreadPoolExecutor para melhor gerenciamento de threads
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        processed_hosts_count = 0
        lock = threading.Lock()
        
        def check_host(host):
            """Função worker otimizada para verificar um único host."""
            nonlocal processed_hosts_count
            logging.debug(f"Verificando host: {host['name']}")

            # Verificação rápida de status (apenas ping)
            status_is_online, current_ip = self.network_tools.resolve_and_check_status(host['name'])
            
            with lock:
                processed_hosts_count += 1
                update_status_callback(self.app.translate("checking_host_status", current=processed_hosts_count, total=total_hosts, hostname=host['name']))

                if current_ip is None:
                    status_is_online = False
                
                # Para o carregamento inicial, usar apenas o IP atual se disponível
                # A resolução de hostname será feita sob demanda quando necessário
                host['current_ip'] = current_ip if current_ip else host['ip']
                host['resolved_hostname'] = host['name']  # Usar nome original por enquanto

                # Verificar discrepância de IP apenas se houver mudança
                saved_ip_or_host = host['ip']
                if is_valid_ip(saved_ip_or_host) and current_ip and current_ip != saved_ip_or_host:
                    logging.warning(f"Discrepância de IP para {host['name']}. Salvo: {saved_ip_or_host}, Atual: {current_ip}")
                    self.app.ip_mismatches[host['name']] = current_ip
                
                new_status = 'online' if status_is_online else 'offline'
                self.app.host_statuses[host['ip']] = new_status
                logging.debug(f"Host {host['name']} status: {new_status}")

        # Otimização: Usar ThreadPoolExecutor com número otimizado de workers
        max_workers = min(HOST_CHECK_BATCH_SIZE, total_hosts, 20)  # Máximo 20 threads
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter todas as tarefas de uma vez
            future_to_host = {executor.submit(check_host, host): host for host in self.app.favorites}
            
            # Processar resultados conforme completam
            for future in as_completed(future_to_host):
                try:
                    future.result()  # Isso vai executar a função check_host
                except Exception as e:
                    host = future_to_host[future]
                    logging.error(f"Erro ao verificar host {host['name']}: {e}")

        logging.debug("'load_and_prepare_all_hosts' otimizado concluído.")
        
        # A resolução de hostname será feita sob demanda quando uma aba for selecionada
        
    def resolve_hostname_on_demand(self, host):
        """Resolve o hostname de um host sob demanda quando necessário."""
        try:
            if not host.get('resolved_hostname') or host['resolved_hostname'] == host['name']:
                # Apenas resolver se ainda não foi resolvido
                current_ip = host.get('current_ip', host['ip'])
                resolved_ip, resolved_hostname = self.network_tools.resolve_ip_and_hostname(current_ip)
                
                if resolved_hostname and resolved_hostname not in ["N/A", "Erro", "Inválido"]:
                    host['resolved_hostname'] = resolved_hostname
                    logging.debug(f"Hostname resolvido para {host['name']}: {resolved_hostname}")
                    
        except Exception as e:
            logging.error(f"Erro ao resolver hostname para {host['name']}: {e}")

    def _fetch_detailed_info_for_online_hosts(self, only_no_credentials=False):
        """Inicia uma thread para buscar detalhes (SO, RAM, etc.) dos hosts online.
           Se only_no_credentials for True, busca apenas para hosts que não precisam de credenciais."""
        logging.debug(f"Iniciando busca de informações detalhadas para hosts online (apenas sem credenciais: {only_no_credentials}).")
        thread = threading.Thread(target=self._detailed_info_worker, args=(only_no_credentials,), name="DetailedInfoFetcher", daemon=True)
        thread.start()


    def _detailed_info_worker(self):
        """Worker que busca informações detalhadas para cada host online."""
        logging.debug("Worker de informações detalhadas iniciado.")
        time.sleep(2)
        
        online_hosts = [
            host for host in self.app.favorites 
            if self.app.host_statuses.get(host['ip']) == 'online'
        ]
        logging.debug(f"Encontrados {len(online_hosts)} hosts online para buscar informações.")

        for i, host in enumerate(online_hosts):
            if self.app.stop_monitoring_event.is_set():
                logging.debug("Evento de parada detectado. Interrompendo busca de informações.")
                break
            
            logging.debug(f"Buscando informações para host {i+1}/{len(online_hosts)}: {host['name']}")
            host_data_sim = {'host_info': host}
            
            sys_info_controller = self.app.host_tab_view.get_tool_controller_for_host(host_data_sim, 'system')
            
            if sys_info_controller:
                sys_info_controller.get_sysinfo(store_only=True)
                logging.debug(f"Comando get_sysinfo despachado para {host['name']}.")
            else:
                logging.warning(f"Não foi possível obter o SystemInfoController para o host {host['name']}.")
            
            time.sleep(1)
        logging.debug("Worker de informações detalhadas concluído.")

    def populate_tabs_with_preloaded_data(self):
        """Usa os dados pré-carregados para popular a interface do usuário."""
        logging.debug("Populando abas com dados pré-carregados.")
        self.app.host_tab_view.populate_initial_tabs(self.app.favorites)
        self.app.is_fully_loaded = True
        logging.debug("Abas populadas e app marcado como totalmente carregado.")

    def reload_all_hosts_and_tabs(self, select_tab_named: str = None):
        logging.debug(f"Recarregando todos os hosts e abas. Selecionar aba: {select_tab_named}")
        # Recarregar hosts do arquivo para garantir dados atualizados
        self.host_manager.load_hosts()
        self.app.favorites = self.host_manager.get_all_hosts()
        logging.debug(f"Hosts recarregados: {len(self.app.favorites)} hosts encontrados")
        self.app.host_tab_view.clear_all_tabs()
        self.app.host_tab_view.populate_initial_tabs(self.app.favorites, select_tab_named=select_tab_named)
        logging.debug("Recarregamento concluído.")

    def open_tab_settings_dialog(self):
        original_hosts = self.host_manager.get_all_hosts()
        original_hosts_order = [h['name'] for h in original_hosts]
        original_nicknames = {h['name']: self.app.host_tab_view._get_display_name(h) for h in original_hosts}

        dialog = TabSettingsDialog(self.app, self.app, self.app.status_update_interval, original_hosts, self.app.ask_for_initial_info_on_select)
        self.app.center_popup_on_main_window(dialog, 600, 500)
        result = dialog.get_selection()
        if not result:
            return

        if (interval := result.get("interval")) is not None:
            self.app.status_update_interval = interval
        if (ask_setting := result.get("ask_initial_info")) is not None:
            self.app.ask_for_initial_info_on_select = ask_setting
        
        if (updated_hosts := result.get("updated_hosts")) is not None:
            new_hosts_order = [h['name'] for h in updated_hosts]
            nicknames_changed = any(original_nicknames.get(h['name']) != self.app.host_tab_view._get_display_name(h) for h in updated_hosts)

            if original_hosts_order != new_hosts_order or nicknames_changed:
                self.host_manager.update_hosts(updated_hosts)
                self.reload_all_hosts_and_tabs()
            else:
                self.host_manager.update_hosts(updated_hosts)
        
        self.app.settings_manager.save_ui_preferences()
        logging.info("Configurações das abas e do app salvas.")

    def _is_paused(self):
        """
        Verifica se o controller está pausado.
        """
        return getattr(self, '_paused', False)
    
    def _should_skip_heavy_operation(self):
        """
        Verifica se deve pular operações pesadas.
        """
        return self._is_paused() or getattr(self.app, '_static_mode', False)

    def add_new_host(self):
        logging.info("Tentativa de adicionar novo host.")
        dialog = AddHostDialog(self.app)
        self.app.center_popup_on_main_window(dialog, 500, 400)
        raw_input = dialog.get_input()
        
        if raw_input:
            logging.debug(f"Dados brutos do novo host: {raw_input}")
            parts = [p.strip() for p in raw_input.split(',')]
            name, ip, mac = "", "", ""

            if len(parts) == 1 and parts[0]:
                name, ip = parts[0], parts[0]
            elif len(parts) == 2 and parts[0] and parts[1]:
                name, ip = parts[0], parts[1]
            elif len(parts) >= 3 and parts[0] and parts[1]:
                name, ip, mac = parts[0], parts[1], parts[2]
            else:
                self.app.show_error(self.app.translate("error_invalid_format_add"))
                return
            
            # Variáveis para armazenar resultados da resolução
            resolution_data = {
                'resolved_ip': None,
                'resolved_hostname': None,
                'completed': False,
                'cancelled': False
            }
            
            # Criar janela de carregamento
            loading_window = LoadingWindow(
                self.app,
                description=f"Resolvendo informações para {name}...",
                on_cancel=lambda: self._cancel_resolution(resolution_data, loading_window)
            )
            self.app.center_popup_on_main_window(loading_window, 400, 150)
            
            def resolve_host_info():
                """Função para resolver informações do host em thread separada"""
                try:
                    logging.info(f"Resolvendo informações para o host: {name}")
                    
                    # Verificar cancelamento antes de iniciar
                    if resolution_data['cancelled']:
                        return
                    
                    # Resolver IP e hostname automaticamente
                    resolved_ip, resolved_hostname = self.network_tools.resolve_ip_and_hostname(ip)
                    
                    # Verificar cancelamento após resolução
                    if resolution_data['cancelled']:
                        return
                    
                    # Atualizar dados de resolução
                    resolution_data['resolved_ip'] = resolved_ip
                    resolution_data['resolved_hostname'] = resolved_hostname
                    resolution_data['completed'] = True
                    
                    # Continuar processamento na thread principal
                    self.app.after(0, lambda: self._complete_host_addition(
                        parts, name, ip, mac, resolution_data, loading_window
                    ))
                    
                except Exception as e:
                    logging.error(f"Erro ao resolver informações do host: {e}")
                    resolution_data['completed'] = True
                    # Continuar mesmo com erro
                    self.app.after(0, lambda: self._complete_host_addition(
                        parts, name, ip, mac, resolution_data, loading_window
                    ))
            
            # Executar resolução em thread separada (não bloqueia UI)
            resolution_thread = threading.Thread(target=resolve_host_info, daemon=True)
            resolution_thread.start()
            
            # A partir daqui, o processamento continua em _complete_host_addition
            return
    
    def _cancel_resolution(self, resolution_data, loading_window):
        """Cancela a resolução de host em andamento"""
        resolution_data['cancelled'] = True
        logging.info("Resolução de host cancelada pelo usuário")
        try:
            loading_window.destroy()
        except:
            pass
    
    def _complete_host_addition(self, parts, original_name, original_ip, mac, resolution_data, loading_window):
        """Completa a adição do host após a resolução (ou cancelamento)"""
        try:
            # Fechar janela de carregamento
            loading_window.destroy()
        except:
            pass
        
        # Verificar se foi cancelado
        if resolution_data['cancelled']:
            return
        
        name = original_name
        ip = original_ip
        resolved_ip = resolution_data.get('resolved_ip')
        resolved_hostname = resolution_data.get('resolved_hostname')
        
        # Usar os dados resolvidos se disponíveis
        if resolved_ip and resolved_ip not in ["Erro", "Inválido"]:
            ip = resolved_ip
            logging.debug(f"IP resolvido: {ip}")
        
        if resolved_hostname and resolved_hostname not in ["N/A", "Erro", "Inválido"]:
            # Se o nome original era igual ao IP, usar o hostname resolvido
            if name == parts[0] and parts[0] == parts[0]:  # Se era apenas um valor
                name = resolved_hostname
                logging.debug(f"Nome atualizado para hostname resolvido: {name}")
        
        new_host = {
            "name": name, 
            "ip": ip, 
            "mac": mac, 
            "nickname": "",
            "resolved_hostname": resolved_hostname if resolved_hostname not in ["N/A", "Erro", "Inválido"] else None,
            "current_ip": ip
        }
        
        nickname_dialog = CustomInputDialog(
            app=self.app,
            title=self.app.translate("ask_nickname_title"),
            text=self.app.translate("ask_nickname_text")
        )
        self.app.center_popup_on_main_window(nickname_dialog, 400, 250)
        nickname_input = nickname_dialog.get_input()
        if nickname_input is not None:
            new_host["nickname"] = nickname_input.strip()

        success, message = self.host_manager.add_host(new_host)
        if success:
            logging.info(f"Host '{name}' ({ip}) adicionado com sucesso.")
            self.app.favorites = self.host_manager.get_all_hosts()
            
            # Recarrega e retorna para a aba Home após adicionar novo host
            self.reload_all_hosts_and_tabs(select_tab_named="Home")
            
            # Verificar status do host e atualizar indicador (de forma assíncrona)
            self._check_and_update_host_status_async(new_host)
            
            # Mostrar notificação de sucesso
            self.app.show_toast_notification(f"Host '{name}' adicionado com sucesso.")
            
        else:
            logging.warning(f"Falha ao adicionar host '{name}' ({ip}): {message}")
            self.app.show_error(self.app.translate("error_host_exists"))
    
    def _check_and_update_host_status(self, host):
        """Verifica o status de um host e atualiza o indicador."""
        try:
            logging.debug(f"Verificando status do host: {host['name']}")
            
            # Verificar se o host está online
            status_is_online, current_ip = self.network_tools.resolve_and_check_status(host['name'])
            
            # Atualizar status na aplicação
            new_status = 'online' if status_is_online else 'offline'
            self.app.host_statuses[host['ip']] = new_status
            
            # Atualizar IP atual se diferente
            if current_ip and current_ip != host['ip']:
                host['current_ip'] = current_ip
                logging.debug(f"IP atualizado para {host['name']}: {current_ip}")
            
            # Atualizar indicador de status na aba
            self.app.host_tab_view.update_host_status_indicator(host['name'])
            
            logging.debug(f"Status do host {host['name']}: {new_status}")
            
        except Exception as e:
            logging.error(f"Erro ao verificar status do host {host['name']}: {e}")
    
    def _check_and_update_host_status_async(self, host):
        """Verifica o status de um host de forma assíncrona para não bloquear a UI."""
        def status_check_worker():
            try:
                self._check_and_update_host_status(host)
            except Exception as e:
                logging.error(f"Erro no worker de verificação de status para {host['name']}: {e}")
        
        # Executar em thread separada para não bloquear a interface
        import threading
        status_thread = threading.Thread(target=status_check_worker, daemon=True, name=f"StatusCheck-{host['name']}")
        status_thread.start()

    def rename_host_nickname(self, host_to_rename):
        logging.info(f"Tentativa de renomear apelido para o host: {host_to_rename.get('name')}")
        dialog = CustomInputDialog(
            app=self.app,
            title=self.app.translate("ask_nickname_title"),
            text=self.app.translate("ask_nickname_text")
        )
        self.app.center_popup_on_main_window(dialog, 400, 250)
        current_nickname = host_to_rename.get("nickname", "")
        dialog.entry.insert(0, current_nickname)
        
        new_nickname = dialog.get_input()
        
        if new_nickname is not None:
            logging.info(f"Novo apelido para '{host_to_rename['name']}': '{new_nickname.strip()}'")
            host_to_rename["nickname"] = new_nickname.strip()
            all_hosts = self.host_manager.get_all_hosts()
            for i, host in enumerate(all_hosts):
                if host['name'] == host_to_rename['name']:
                    all_hosts[i] = host_to_rename
                    break
            self.host_manager.update_hosts(all_hosts)
            
            self.reload_all_hosts_and_tabs()

    def add_discovered_hosts(self, hosts_to_add):
        logging.info(f"Tentativa de adicionar {len(hosts_to_add)} hosts descobertos.")
        if not hosts_to_add:
            return
            
        added_count = 0
        newly_added_hosts = []
        for host in hosts_to_add:
            new_host = {"name": host['name'], "ip": host['ip'], "mac": "", "nickname": ""}
            success, _ = self.host_manager.add_host(new_host)
            if success:
                self.app.host_tab_view.add_host_tab(new_host, switch_to=False)
                newly_added_hosts.append(new_host)
                added_count += 1
        
        if added_count > 0:
            logging.info(f"{added_count} hosts descobertos foram adicionados com sucesso.")
            self.app.favorites = self.host_manager.get_all_hosts()
            self.app.show_toast_notification(f"{added_count} novo(s) host(s) adicionado(s).")
        else:
            logging.info("Nenhum host descoberto foi adicionado (provavelmente já existiam).")
            self.app.show_toast_notification("Nenhum host novo para adicionar (já existiam na lista).")

    def open_remove_host_dialog(self):
        logging.info("Abrindo diálogo para remover hosts.")
        hosts = self.host_manager.get_all_hosts()
        if not hosts:
            self.app.show_info(self.app.translate("info_no_hosts_to_remove"))
            return
        
        dialog = RemoveHostDialog(self.app, self.app, hosts)
        self.app.center_popup_on_main_window(dialog, 500, 400)
        hosts_to_remove = dialog.get_selection()

        if hosts_to_remove:
            self.remove_host_list(hosts_to_remove)

    def remove_single_host(self, host_to_remove):
        display_name = self.app.host_tab_view._get_display_name(host_to_remove)
        
        if self.app.ask_yes_no(
            self.app.translate("title_confirm_action"),
            self.app.translate("confirm_remove_host_message", display_name=display_name)
        ):
            self.remove_host_list([host_to_remove])
            
    def remove_host_list(self, hosts_to_remove):
        logging.info(f"Removendo {len(hosts_to_remove)} hosts: {[h.get('name') for h in hosts_to_remove]}")
        self.app.focus_force()
        self.app.host_tab_view.tab_view.set("Home")
        # Otimização: evitar update durante resize
        if not getattr(self.app, '_resize_in_progress', False):
            self.app.update_idletasks()

        self.host_manager.remove_hosts(hosts_to_remove)
        self.app.favorites = self.host_manager.get_all_hosts()

        for host in hosts_to_remove:
            self.app.host_tab_view.remove_host_tab(host)
            if host['ip'] in self.app.host_statuses:
                del self.app.host_statuses[host['ip']]

    def import_hosts(self):
        logging.info("Iniciando processo de importação de hosts.")
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV Files", "*.csv"), ("All files", "*.*")],
            title="Importar Hosts de CSV"
        )
        if not filepath: return

        try:
            logging.debug(f"Arquivo de importação selecionado: {filepath}")
            imported_count = self.host_manager.import_from_csv(filepath)
            if imported_count > 0:
                logging.info(f"{imported_count} hosts importados com sucesso de {filepath}.")
                self.reload_all_hosts_and_tabs()
                self.app.show_info(f"{imported_count} host(s) importado(s) com sucesso!")
            else:
                logging.info(f"Nenhum host novo importado de {filepath} (provavelmente já existiam).")
                self.app.show_info("Nenhum host novo para importar (já existiam).")
        except IOError as e:
            logging.error(f"Erro de IO ao importar hosts de {filepath}: {e}")
            self.app.show_error(str(e))

    def export_hosts(self):
        logging.info("Iniciando processo de exportação de hosts.")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All files", "*.*")],
            title="Exportar Hosts para CSV"
        )
        if not filepath: return

        try:
            logging.debug(f"Arquivo de exportação selecionado: {filepath}")
            self.host_manager.export_to_csv(filepath)
            logging.info(f"Hosts exportados com sucesso para {filepath}.")
            self.app.show_info(f"Lista de hosts exportada com sucesso para {filepath}")
        except IOError as e:
            logging.error(f"Erro de IO ao exportar hosts para {filepath}: {e}")
            self.app.show_error(str(e))
            
    def factory_reset(self):
        logging.warning("Usuário iniciou o processo de restauração de fábrica.")
        confirmed = self.app.ask_yes_no(
            self.app.translate("factory_reset_confirm_title"),
            self.app.translate("factory_reset_confirm_message")
        )

        if not confirmed:
            logging.info("Restauração de fábrica cancelada pelo usuário.")
            return
        
        logging.warning("CONFIRMADO: Executando restauração de fábrica.")
        self.app.host_tab_view.clear_all_tabs()
        self.host_manager.clear_all_hosts()
        self.app.favorites.clear()
        self.app.host_statuses.clear()

        base_dir = self.app.base_dir
        other_files_to_delete = [
            os.path.join(base_dir, UI_PREFS_FILE),
            os.path.join(base_dir, DISCOVERY_CACHE_FILE)
        ]
        for f in other_files_to_delete:
            if os.path.exists(f):
                try: os.remove(f)
                except OSError as e: print(f"Erro ao apagar {f}: {e}")

        services_cache_dir = os.path.join(base_dir, "cache", "services")
        if os.path.isdir(services_cache_dir):
            try: shutil.rmtree(services_cache_dir)
            except OSError as e: print(f"Erro ao apagar o diretório de cache de serviços: {e}")
        
        self.app.show_info(self.app.translate("factory_reset_done_message"))
        self.app.destroy()

    def change_host_ip_manual(self, host, new_ip):
        """Atualiza o IP do host manualmente e retorna para a aba Home."""
        try:
            if not new_ip:
                return
            display_name = self.app.host_tab_view._get_display_name(host)
            logging.info(f"Alterando IP manualmente para host {host.get('name')} -> {new_ip}")
            
            # Atualizar o IP no host manager
            success = self.host_manager.update_host_ip(host['name'], new_ip)
            if not success:
                logging.error(f"Falha ao atualizar IP do host {host.get('name')}")
                return
            
            # Atualizar o IP na lista em memória
            for fav_host in self.app.favorites:
                if fav_host['name'] == host['name']:
                    fav_host['ip'] = new_ip
                    logging.debug(f"IP atualizado na lista em memória: {fav_host['name']} -> {new_ip}")
                    break
            
            # Recarrega e retorna para a aba Home
            self.reload_all_hosts_and_tabs(select_tab_named="Home")
        except Exception as e:
            logging.error(f"Erro ao alterar IP manualmente: {e}")

    def _on_tab_selected(self, host_data):
        logging.debug(f"_on_tab_selected chamado para host_data: {host_data}")
        host_info = host_data['host_info']
        host_name = host_info['name']
        logging.debug(f"Aba selecionada para o host: {host_name}")

        if host_name in self.app.ip_mismatches:
            new_ip = self.app.ip_mismatches[host_name]
            old_ip = host_info['ip']
            
            logging.info(f"Discrepância de IP detectada para {host_name}. Antigo: {old_ip}, Novo: {new_ip}")
            user_wants_update = self.app.ask_yes_no(
                title=self.app.translate("ip_mismatch_title"),
                message=self.app.translate("ip_mismatch_message", hostname=host_name, old_ip=old_ip, new_ip=new_ip)
            )
            if user_wants_update:
                # Antes de atualizar, verificar se o novo IP está em adaptador diferente
                label = None
                try:
                    from system.core.remote_commands import RemoteCommands
                    # Tentar com WinRM credenciais salvas/usuário final (se houver)
                    # Fallback: detectar localmente se o host é localhost
                    adapter_hint = None
                    # Heurística local: se o host é localhost, checar adaptadores locais
                    if old_ip in ["127.0.0.1", "::1", "localhost"]:
                        adapter_hint = self._detect_local_adapter_label_for_ip(new_ip)
                    else:
                        # Tentativa leve: abrir sessão sem credenciais (pode falhar, é opcional)
                        # Se a aplicação já tem uma sessão/credenciais, poderia integrá-las aqui.
                        # Como fallback, apenas etiqueta heurística pelo nome do IP (não confiável)
                        adapter_hint = None
                    label = adapter_hint
                except Exception as e:
                    logging.debug(f"Falha ao tentar detectar adaptador do novo IP: {e}")

                # Se conseguir identificar adaptador diferente, oferecer adicionar como segundo IP
                added_as_secondary = False
                if label:
                    try:
                        # Mapear label heurístico para tradução
                        adapter_key = "ip_label_network"
                        if label.lower().startswith('wi'): adapter_key = "ip_label_wifi"
                        elif label.lower().startswith('eth'): adapter_key = "ip_label_ethernet"
                        adapter_label = self.app.translate(adapter_key)
                        if self.app.ask_yes_no(
                            self.app.translate("ip_mismatch_new_adapter_title", hostname=host_name),
                            self.app.translate("ip_mismatch_new_adapter_message", hostname=host_name, old_ip=old_ip, new_ip=new_ip, adapter=adapter_label)
                        ):
                            if self.host_manager.add_secondary_ip(host_name, new_ip, label):
                                added_as_secondary = True
                    except Exception as e:
                        logging.debug(f"Erro ao perguntar/definir IP secundário: {e}")

                if not added_as_secondary:
                    logging.info(f"Atualizando IP principal para {host_name} -> {new_ip}")
                    self.host_manager.update_host_ip(host_name, new_ip)

                del self.app.ip_mismatches[host_name]
                display_name = self.app.host_tab_view._get_display_name(host_info)
                self.reload_all_hosts_and_tabs(select_tab_named=display_name)
                # Atualizar tooltip com IPs secundários, se houver
                try:
                    updated_hosts = self.host_manager.get_all_hosts()
                    for h in updated_hosts:
                        if h['name'] == host_name:
                            secondary = h.get('secondary_ips')
                            tab_data = self.app.host_tab_view.host_tabs_data.get(host_name, {})
                            info_display = tab_data.get('info_display')
                            if info_display:
                                self.app.after(0, info_display.update_info, None, None, None, None, secondary)
                            break
                except Exception as e:
                    logging.debug(f"Falha ao atualizar tooltip de IPs secundários: {e}")
                return
            else:
                logging.info(f"Usuário recusou a atualização de IP para {host_name}.")
                del self.app.ip_mismatches[host_name]

        self.app.host_tab_view.load_tools_for_host(host_data)

    def _detect_local_adapter_label_for_ip(self, ip):
        """Heurística local para classificar IP por adaptador (Wi‑Fi ou Ethernet)."""
        try:
            import subprocess, json, os
            # Windows: usar PowerShell Get-NetIPConfiguration (mais moderno) como heurística
            if os.name == 'nt':
                ps_cmd = [
                    'powershell', '-Command',
                    'Get-NetIPConfiguration | Where-Object {$_.IPv4Address -ne $null} | '
                    'Select-Object InterfaceAlias, InterfaceDescription, IPv4Address | '
                    'ConvertTo-Json -Compress'
                ]
                result = subprocess.run(ps_cmd, capture_output=True, text=True)
                data = result.stdout.strip()
                if not data:
                    return None
                try:
                    parsed = json.loads(data)
                    entries = parsed if isinstance(parsed, list) else [parsed]
                    for e in entries:
                        addr_obj = e.get('IPv4Address') or {}
                        ip_addr = addr_obj.get('IPv4Address') if isinstance(addr_obj, dict) else None
                        if ip_addr == ip:
                            alias = (e.get('InterfaceAlias') or '').lower()
                            desc = (e.get('InterfaceDescription') or '').lower()
                            if 'wi-fi' in alias or 'wifi' in alias or 'wireless' in alias or '802.11' in desc:
                                return 'Wi‑Fi'
                            if 'ethernet' in alias or 'realtek' in desc or 'intel(r) ethernet' in desc or 'gigabit network connection' in desc:
                                return 'Ethernet'
                            return 'Rede'
                except json.JSONDecodeError:
                    return None
            return None
        except Exception:
            return None

    def start_status_monitoring(self):
        logging.debug("Iniciando a thread de monitoramento de status.")
        monitor_thread = threading.Thread(target=self._status_monitoring_worker, name="StatusMonitor", daemon=True)
        monitor_thread.start()

    def _status_monitoring_worker(self):
        logging.debug("Worker de monitoramento de status iniciado.")
        time.sleep(self.app.status_update_interval)
        while not self.app.stop_monitoring_event.is_set():
            logging.debug("Iniciando novo ciclo de verificação de status.")
            hosts_to_check = self.host_manager.get_all_hosts()
            
            for host in hosts_to_check:
                if self.app.stop_monitoring_event.is_set():
                    logging.debug("Evento de parada detectado no meio do ciclo de monitoramento.")
                    break
                
                logging.debug(f"Monitoramento: Verificando host {host['name']}.")
                status_is_online, current_ip = self.network_tools.resolve_and_check_status(host['name'])
                
                if current_ip is None:
                    status_is_online = False
                
                saved_ip_or_host = host['ip']
                if is_valid_ip(saved_ip_or_host) and current_ip and current_ip != saved_ip_or_host:
                    self.app.ip_mismatches[host['name']] = current_ip
                
                new_status = 'online' if status_is_online else 'offline'
                
                if new_status != self.app.host_statuses.get(host['ip']):
                    logging.info(f"Status do host {host['name']} mudou para {new_status}.")
                    self.app.host_statuses[host['ip']] = new_status
                    self.app.after(0, self.app.host_tab_view.update_host_status_indicator, host['name'])
            
            logging.debug(f"Ciclo de verificação de status concluído. Aguardando {self.app.status_update_interval} segundos.")
            time.sleep(self.app.status_update_interval)
        logging.debug("Worker de monitoramento de status finalizado.")

    def is_any_tool_running(self):
        for tab_data in self.app.host_tab_view.host_tabs_data.values():
            if 'tool_controllers' in tab_data:
                for controller in tab_data['tool_controllers'].values():
                    if controller.is_running:
                        return True
        return False

    def start_background_resolver(self):
        logging.debug("Iniciando a thread do resolvedor de nomes em segundo plano.")
        resolver_thread = threading.Thread(target=self._background_resolver_worker, name="HostnameResolver", daemon=True)
        resolver_thread.start()

    def _background_resolver_worker(self):
        logging.debug("Worker do resolvedor de nomes iniciado.")
        time.sleep(5)
        while not self.app.stop_monitoring_event.is_set():
            if not self.is_any_tool_running():
                logging.debug("Nenhuma ferramenta ativa. Iniciando ciclo de resolução de nomes.")
                for host_name, tab_data in list(self.app.host_tab_view.host_tabs_data.items()):
                    if self.app.stop_monitoring_event.is_set():
                        logging.debug("Evento de parada detectado no resolvedor de nomes.")
                        break

                    info_display = tab_data.get("info_display")
                    if info_display:
                        current_hostname = info_display.hostname_label_value.cget("text")
                        ip_address = info_display.ip_label_value.cget("text")
                        
                        if current_hostname == ip_address:
                            logging.debug(f"Tentando resolver hostname para o IP {ip_address}.")
                            _, resolved_hostname = self.network_tools.resolve_ip_and_hostname(ip_address)
                            if resolved_hostname != "N/A" and resolved_hostname != "Erro":
                                logging.info(f"IP {ip_address} resolvido para {resolved_hostname}. Atualizando UI.")
                                self.app.after(0, info_display.update_info, None, None, resolved_hostname, None)
                            
                            time.sleep(1)
            else:
                logging.debug("Uma ou mais ferramentas estão ativas. Pulando ciclo de resolução de nomes.")

            time.sleep(10)
        logging.debug("Worker do resolvedor de nomes finalizado.")