# src/ferramentasderede/ui/components/host_tab_manager/tab_manager.py
# Gerencia o widget CTkTabview, suas abas, status e eventos de hosts salvos.

import customtkinter
import logging
import tkinter
from PIL import Image, ImageDraw
from .home_tab_manager import HomeTabManager

class HostTabManager:
    def __init__(self, tab_view_widget, app, on_tab_change_callback):
        self.tab_view = tab_view_widget
        self.app = app
        self.on_tab_change_callback = on_tab_change_callback

        self.host_tabs_data = {}
        self.status_images = {}
        self.placeholder_name = "Home"
        self.right_clicked_tab_name = None

        # Sistema responsivo para abas
        self.overflow_dropdown = None
        self.overflow_button = None
        self.hidden_tabs = []
        self.max_visible_tabs = 8  # Máximo de abas visíveis antes do dropdown

        self._create_context_menu()
        self.tab_view.configure(command=self._on_tab_selected)

        # Monitorar mudanças de tamanho usando método alternativo
        self._start_size_monitoring()

        # Adicionar bind para detecção de redimensionamento mais responsiva
        # CustomTkinter não suporta bind diretamente, usar winfo_toplevel()
        try:
            # Bind no widget pai (janela principal) para detectar redimensionamento
            self.tab_view.winfo_toplevel().bind("<Configure>", self._on_widget_configure)
        except Exception as e:
            logging.debug(f"Não foi possível configurar bind de Configure: {e}")

    def _create_context_menu(self):
        self.context_menu = tkinter.Menu(self.tab_view, tearoff=0)

    def show_context_menu(self, event, clicked_button):
        """
        Mostra o menu de contexto. O botão clicado é passado diretamente como argumento.
        """
        clicked_tab_name = clicked_button.cget("text").strip()
        self.context_menu.delete(0, "end")
        
        if clicked_tab_name and clicked_tab_name != self.placeholder_name:
            self.right_clicked_tab_name = clicked_tab_name
            
            rename_text = self.app.translate("context_menu_set_nickname")
            self.context_menu.add_command(label=rename_text, command=self.rename_selected_host)
            change_ip_text = self.app.translate("context_menu_change_ip")
            self.context_menu.add_command(label=change_ip_text, command=self.change_ip_selected_host)
            
            self.context_menu.add_separator()
            
            delete_text = self.app.translate("context_menu_delete_host", display_name=self.right_clicked_tab_name)
            self.context_menu.add_command(label=delete_text, command=self.delete_selected_host)
            
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def get_host_from_clicked_tab(self):
        if not self.right_clicked_tab_name:
            return None
        return next((data['host_info'] for data in self.host_tabs_data.values() if self._get_display_name(data['host_info']) == self.right_clicked_tab_name), None)

    def delete_selected_host(self):
        host_to_remove = self.get_host_from_clicked_tab()
        if host_to_remove:
            self.app.controller.remove_single_host(host_to_remove)
        self.right_clicked_tab_name = None

    def rename_selected_host(self):
        host_to_rename = self.get_host_from_clicked_tab()
        if host_to_rename:
            self.app.controller.rename_host_nickname(host_to_rename)
        self.right_clicked_tab_name = None

    def change_ip_selected_host(self):
        host = self.get_host_from_clicked_tab()
        if host:
            try:
                from ..custom_input_dialog import CustomInputDialog
                dialog = CustomInputDialog(
                    app=self.app,
                    title=self.app.translate("context_menu_change_ip"),
                    text=self.app.translate("tab_settings_ip_label")
                )
                self.app.center_popup_on_main_window(dialog, 380, 180)
                new_ip = dialog.get_input()
                if new_ip:
                    self.app.controller.change_host_ip_manual(host, new_ip.strip())
            except Exception as e:
                import logging
                logging.error(f"Erro ao alterar IP manualmente: {e}")
        self.right_clicked_tab_name = None

    def _on_tab_selected(self, *args):
        selected_tab_name = self.tab_view.get()
        if selected_tab_name is None or selected_tab_name == self.placeholder_name:
            if self.app.host_tab_view.home_tab_manager:
                self.app.host_tab_view.home_tab_manager.update_home_buttons_state()
            return

        # Se há abas ocultas e a aba selecionada não está visível, reorganizar
        if self.hidden_tabs and selected_tab_name in self.hidden_tabs:
            self._make_tab_visible(selected_tab_name)

        # Verificar se precisa reorganizar o overflow após mudança de aba
        self.app.after(100, self._check_tabs_overflow)

        host_name_key = next((k for k, d in self.host_tabs_data.items() if self._get_display_name(d['host_info']) == selected_tab_name), None)
        if host_name_key:
            host_data = self.host_tabs_data.get(host_name_key)
            if host_data and self.on_tab_change_callback:
                self.on_tab_change_callback(host_data)

    def _get_display_name(self, host_info):
        base = host_info.get('nickname', '').strip() or host_info.get('name')
        try:
            ip = host_info.get('ip')
            if ip in ['127.0.0.1', '::1', 'localhost']:
                return f"{base} (localhost)"
        except Exception:
            pass
        return base

    def clear_all(self):
        for name in self.get_all_tab_names():
            try: self.tab_view.delete(name)
            except Exception: pass
        self.host_tabs_data.clear()

    def add_tab(self, host, switch_to=True):
        host_name_key = host['name']
        display_name = self._get_display_name(host)
        if display_name in self.tab_view._name_list: return
        self.tab_view.add(display_name)
        self.host_tabs_data[host_name_key] = {"host_info": host}
        self.app.after(50, lambda: self._store_button_reference_and_update_status(host_name_key, display_name))

        # Verificar se precisa mostrar dropdown após adicionar aba
        self.app.after(100, self._check_tabs_overflow)

        if switch_to:
            # Aguardar um pouco para garantir que a aba foi criada
            self.app.after(150, lambda: self.tab_view.set(display_name))
            logging.debug(f"Aba '{display_name}' será selecionada automaticamente")

    def remove_tab(self, host):
        host_name_key = host['name']
        display_name = self._get_display_name(host)
        if display_name in self.tab_view._name_list: self.tab_view.delete(display_name)
        if host_name_key in self.host_tabs_data: del self.host_tabs_data[host_name_key]

        # Remover da lista de abas ocultas se estiver lá
        if display_name in self.hidden_tabs:
            self.hidden_tabs.remove(display_name)

        # Verificar se ainda precisa do dropdown após remover aba
        self.app.after(100, self._check_tabs_overflow)

    def populate_initial(self, hosts, select_tab_named: str = None):
        self.clear_all()
        for host in hosts:
            self.add_tab(host, switch_to=False)

        # Selecionar aba antes da verificação de overflow
        if select_tab_named and select_tab_named in self.tab_view._name_list:
            self.tab_view.set(select_tab_named)
            # Disparar callback manualmente após seleção programática
            self.app.after(100, lambda: self._on_tab_selected())
        else:
            self.tab_view.set(self.placeholder_name)

        # Verificar se precisa do dropdown após carregar e selecionar abas
        # Usar delays maiores para garantir que o layout esteja estabilizado
        self.app.after(1000, self._check_tabs_overflow)
        self.app.after(2000, self._check_tabs_overflow)  # Verificação adicional com delay maior
    
    def _create_status_image(self, color, size=10):
        if color in self.status_images: return self.status_images[color]
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, size - 1, size - 1), fill=color)
        ctk_image = customtkinter.CTkImage(light_image=image, dark_image=image, size=(size, size))
        self.status_images[color] = ctk_image
        return ctk_image

    def update_status_indicator(self, host_name_key):
        host_data = self.host_tabs_data.get(host_name_key)
        if not host_data or 'button_widget' not in host_data or not host_data['button_widget']: return
        button = host_data['button_widget']
        ip = host_data['host_info']['ip']
        status = self.app.host_statuses.get(ip, 'unknown')
        status_colors = {"online": "#2ECC71", "offline": "#E74C3C", "unknown": "#808080"}
        color_hex = status_colors.get(status, status_colors["unknown"])
        display_name = self._get_display_name(host_data['host_info'])
        status_image = self._create_status_image(color_hex)
        try:
            if button and button.winfo_exists():
                button.configure(image=status_image, compound="left", text=f" {display_name}")
        except Exception as e:
            print(f"Não foi possível atualizar o indicador de status para {display_name}: {e}")
            
    def _store_button_reference_and_update_status(self, host_name_key, display_name):
        if hasattr(self.tab_view, '_segmented_button') and self.tab_view._segmented_button.winfo_exists() and display_name in self.tab_view._segmented_button._buttons_dict:
            button = self.tab_view._segmented_button._buttons_dict[display_name]
            if host_name_key in self.host_tabs_data:
                self.host_tabs_data[host_name_key]['button_widget'] = button
                # CORREÇÃO DEFINITIVA: Usa lambda para passar o botão específico como argumento.
                button.bind("<Button-3>", lambda event, b=button: self.show_context_menu(event, b))
                self.update_status_indicator(host_name_key)
    
    def get_all_tab_names(self):
        return [name for name in self.tab_view._name_list if name != self.placeholder_name]
        
    def get_current_tab_name(self):
        """Retorna o nome da aba atualmente selecionada."""
        return self.tab_view.get()

    def update_language(self):
        for host_name_key in list(self.host_tabs_data.keys()):
            self.update_status_indicator(host_name_key)

    def _start_size_monitoring(self):
        """Inicia o monitoramento periódico do tamanho da janela."""
        self.last_width = 0
        self.last_configure_time = 0
        self._monitor_size()

    def _on_widget_configure(self, event):
        """Callback para detecção de redimensionamento via evento Configure."""
        try:
            import time
            current_time = time.time()

            # Evitar múltiplas chamadas muito próximas (debounce)
            if current_time - self.last_configure_time < 0.1:
                return

            self.last_configure_time = current_time

            # Verificar se é uma mudança de largura significativa
            current_width = self.tab_view.winfo_width()
            if abs(current_width - self.last_width) > 5 and current_width > 1:
                logging.debug(f"Configure event: largura mudou para {current_width}px")
                # Agendar verificação após um pequeno delay para garantir que o layout foi atualizado
                self.app.after(50, self._check_tabs_overflow)

        except Exception as e:
            logging.debug(f"Erro no configure event: {e}")

    def _monitor_size(self):
        """Monitora mudanças de tamanho da janela periodicamente."""
        try:
            current_width = self.tab_view.winfo_width()

            # Detectar mudanças menores também (±5px) para maior responsividade
            if abs(current_width - self.last_width) > 5 and current_width > 1:
                width_increased = current_width > self.last_width
                self.last_width = current_width

                # Log para debug
                logging.debug(f"Mudança de largura detectada: {current_width}px ({'aumentou' if width_increased else 'diminuiu'})")

                # Verificar overflow imediatamente
                self._check_tabs_overflow()

                # Se a janela aumentou e há abas ocultas, verificar novamente em breve
                if width_increased and self.hidden_tabs:
                    self.app.after(100, self._check_tabs_overflow)

            # Verificação contínua mais frequente quando há abas ocultas
            next_check_interval = 250 if self.hidden_tabs else 500
            self.app.after(next_check_interval, self._monitor_size)

        except Exception as e:
            logging.warning(f"Erro ao monitorar tamanho: {e}")
            # Reagendar mesmo com erro
            self.app.after(1000, self._monitor_size)

    def _check_tabs_overflow(self):
        """Verifica se as abas estão estourando e gerencia o dropdown."""
        try:
            total_tabs = len(self.tab_view._name_list)

            # Se temos apenas 1 aba (Home), não precisamos do dropdown
            if total_tabs <= 1:
                self._hide_overflow_dropdown()
                return

            # Calcular número máximo de abas baseado na largura da janela
            available_width = self.tab_view.winfo_width()
            if available_width <= 1:  # Ainda não renderizado
                self.app.after(200, self._check_tabs_overflow)
                return

            # Estimar largura mais precisa baseada no conteúdo real das abas
            total_estimated_width = 0
            for tab_name in self.tab_view._name_list:
                # Calcular largura mais precisa considerando:
                # - Cada caractere ocupa ~8-10px
                # - Padding interno da aba (~30px)
                # - Ícone de status (~20px)
                # - Margem entre abas (~4px)
                char_width = len(tab_name) * 10  # Mais conservador
                padding_and_icon = 54  # Padding + ícone + margem
                estimated_tab_width = char_width + padding_and_icon

                # Mínimo para abas muito curtas, máximo para evitar abas enormes
                estimated_tab_width = max(120, min(estimated_tab_width, 220))
                total_estimated_width += estimated_tab_width

            # Reservar espaço para o botão dropdown e margem de segurança
            dropdown_button_width = 80  # Mais espaço para botão e segurança
            tabs_overflow = total_estimated_width > (available_width - dropdown_button_width)

            # MELHORIA: Verificar se há abas ocultas que podem ser mostradas
            if self.hidden_tabs and not tabs_overflow:
                # Calcular quantas abas ocultas podem ser mostradas agora
                self._try_to_show_hidden_tabs(available_width, dropdown_button_width)

            # Ativar dropdown mais cedo para evitar texto cortado
            if tabs_overflow and total_tabs >= 2:  # Ativar com apenas 2 abas se necessário
                self._show_overflow_dropdown()
                logging.debug(f"Overflow detectado: {total_estimated_width}px > {available_width-dropdown_button_width}px disponível")
            elif not self.hidden_tabs:  # Só ocultar se não há abas ocultas
                self._hide_overflow_dropdown()

        except Exception as e:
            logging.warning(f"Erro ao verificar overflow das abas: {e}")

    def _try_to_show_hidden_tabs(self, available_width, dropdown_button_width):
        """Tenta mostrar abas ocultas quando há espaço disponível."""
        try:
            if not self.hidden_tabs:
                return

            # Calcular largura atual das abas visíveis
            visible_tabs = [tab for tab in self.tab_view._name_list if tab not in self.hidden_tabs]
            current_width = 0

            for tab_name in visible_tabs:
                char_width = len(tab_name) * 10
                padding_and_icon = 54
                estimated_tab_width = max(120, min(char_width + padding_and_icon, 220))
                current_width += estimated_tab_width

            # Verificar quantas abas ocultas podem ser mostradas
            usable_width = available_width - dropdown_button_width
            tabs_to_show = []

            for tab_name in self.hidden_tabs[:]:  # Cópia da lista para modificar durante iteração
                char_width = len(tab_name) * 10
                padding_and_icon = 54
                estimated_tab_width = max(120, min(char_width + padding_and_icon, 220))

                # Verificar se esta aba cabe no espaço disponível
                if current_width + estimated_tab_width <= usable_width:
                    tabs_to_show.append(tab_name)
                    current_width += estimated_tab_width
                    self.hidden_tabs.remove(tab_name)
                else:
                    break  # Não cabe, parar de tentar

            # Mostrar as abas que cabem
            if tabs_to_show:
                self._show_specific_tabs(tabs_to_show)
                logging.debug(f"Mostrando {len(tabs_to_show)} abas ocultas: {tabs_to_show}")

                # Se não há mais abas ocultas, remover o dropdown
                if not self.hidden_tabs:
                    self._hide_overflow_dropdown()
                else:
                    # Atualizar o dropdown com as abas restantes
                    self._update_overflow_button_position()

        except Exception as e:
            logging.error(f"Erro ao tentar mostrar abas ocultas: {e}")

    def _show_specific_tabs(self, tabs_to_show):
        """Mostra abas específicas que estavam ocultas."""
        try:
            if hasattr(self.tab_view, '_segmented_button') and self.tab_view._segmented_button:
                for tab_name in tabs_to_show:
                    if tab_name in self.tab_view._segmented_button._buttons_dict:
                        button = self.tab_view._segmented_button._buttons_dict[tab_name]
                        if button and button.winfo_exists():
                            button.grid()  # Mostrar novamente
        except Exception as e:
            logging.error(f"Erro ao mostrar abas específicas: {e}")

    def _update_overflow_arrow_position(self):
        """Atualiza a posição da seta de overflow baseado nas abas visíveis."""
        try:
            # A seta está integrada na última aba visível, não precisa reposicionar
            # Apenas atualizar se a última aba visível mudou
            if hasattr(self, 'overflow_arrow_tab'):
                visible_tabs = [tab for tab in self.tab_view._name_list if tab not in self.hidden_tabs]
                if visible_tabs and visible_tabs[-1] != self.overflow_arrow_tab:
                    # A última aba mudou, remover seta da aba anterior e adicionar na nova
                    self._hide_overflow_dropdown()
                    self._create_overflow_arrow()
                    logging.debug(f"Seta movida para nova última aba: {visible_tabs[-1]}")
        except Exception as e:
            logging.error(f"Erro ao atualizar posição da seta overflow: {e}")

    def _show_overflow_dropdown(self):
        """Mostra o dropdown com as abas que não cabem, organizando melhor as abas visíveis."""
        try:
            # Identificar abas que devem ficar ocultas
            all_tabs = self.tab_view._name_list[:]
            current_tab = self.tab_view.get()

            # Calcular quantas abas cabem baseado na largura disponível
            available_width = self.tab_view.winfo_width()
            dropdown_button_width = 80  # Espaço para botão "..."
            usable_width = available_width - dropdown_button_width

            # Priorizar a aba atual para ficar sempre visível
            prioritized_tabs = []
            other_tabs = []

            for tab in all_tabs:
                if tab == current_tab:
                    prioritized_tabs.append(tab)
                else:
                    other_tabs.append(tab)

            # Reorganizar: aba atual primeiro, depois as outras
            organized_tabs = prioritized_tabs + other_tabs

            # Calcular quantas abas realmente cabem, considerando tamanho real
            cumulative_width = 0
            max_tabs_that_fit = 0

            for tab_name in organized_tabs:
                # Usar a mesma fórmula de cálculo da detecção de overflow
                char_width = len(tab_name) * 10
                padding_and_icon = 54
                estimated_tab_width = max(120, min(char_width + padding_and_icon, 220))

                if cumulative_width + estimated_tab_width <= usable_width:
                    cumulative_width += estimated_tab_width
                    max_tabs_that_fit += 1
                else:
                    break

            # Garantir que pelo menos 1 aba seja visível (sempre a atual)
            max_tabs_that_fit = max(1, max_tabs_that_fit)

            if len(all_tabs) > max_tabs_that_fit:
                # Determinar abas visíveis e ocultas baseado na organização
                visible_tabs = organized_tabs[:max_tabs_that_fit]
                self.hidden_tabs = organized_tabs[max_tabs_that_fit:]

                logging.debug(f"Organizando {max_tabs_that_fit} abas visíveis (aba atual: {current_tab}), ocultando {len(self.hidden_tabs)} abas")

                # Ocultar abas excedentes fisicamente
                self._hide_excess_tabs()

                # Criar seta se não existir (com delay para estabilizar layout)
                if not hasattr(self, 'overflow_arrow_tab'):
                    self.app.after(1500, self._create_overflow_arrow)  # Delay maior para estabilizar

                # Atualizar o dropdown
                self._update_overflow_dropdown()
            else:
                self._hide_overflow_dropdown()

        except Exception as e:
            logging.error(f"Erro ao mostrar dropdown de overflow: {e}")

    def _hide_overflow_dropdown(self):
        """Oculta o dropdown e remove a seta quando não é necessário."""
        try:
            # Remover seta do último host se existir
            if hasattr(self, 'overflow_arrow_tab') and hasattr(self, 'original_tab_text'):
                if (hasattr(self.tab_view, '_segmented_button') and
                    self.tab_view._segmented_button and
                    self.overflow_arrow_tab in self.tab_view._segmented_button._buttons_dict):

                    button = self.tab_view._segmented_button._buttons_dict[self.overflow_arrow_tab]
                    if button and button.winfo_exists():
                        # Restaurar texto original sem seta
                        button.configure(text=self.original_tab_text)
                        # Não tentar remover bind - deixar o sistema gerenciar

                # Limpar referências
                delattr(self, 'overflow_arrow_tab')
                delattr(self, 'original_tab_text')

            if self.overflow_button:
                self.overflow_button = None
            if self.overflow_dropdown:
                self.overflow_dropdown.destroy()
                self.overflow_dropdown = None

            # Mostrar novamente todas as abas que estavam ocultas
            self._show_all_tabs()
            self.hidden_tabs = []

            logging.debug("Seta de overflow removida")
        except Exception as e:
            logging.warning(f"Erro ao ocultar dropdown: {e}")

    def _hide_excess_tabs(self):
        """Oculta visualmente as abas que excedem o limite SEM CRIAR GAPS."""
        try:
            if hasattr(self.tab_view, '_segmented_button') and self.tab_view._segmented_button:
                self._rebuild_tab_layout()
        except Exception as e:
            logging.error(f"Erro ao ocultar abas excedentes: {e}")

    def _show_all_tabs(self):
        """Mostra novamente todas as abas ocultas SEM CRIAR GAPS."""
        try:
            if hasattr(self.tab_view, '_segmented_button') and self.tab_view._segmented_button:
                # Limpar lista de abas ocultas
                self.hidden_tabs = []
                self._rebuild_tab_layout()
        except Exception as e:
            logging.error(f"Erro ao mostrar todas as abas: {e}")

    def _rebuild_tab_layout(self):
        """Reconstrói o layout das abas eliminando gaps entre elas."""
        try:
            if not hasattr(self.tab_view, '_segmented_button') or not self.tab_view._segmented_button:
                return

            segmented_button = self.tab_view._segmented_button
            all_tabs = self.tab_view._name_list[:]

            # Determinar quais abas são visíveis (não estão em hidden_tabs)
            visible_tabs = [tab for tab in all_tabs if tab not in self.hidden_tabs]

            # Reconstruir o grid layout completamente
            col = 0
            for tab in all_tabs:
                if tab in segmented_button._buttons_dict:
                    button = segmented_button._buttons_dict[tab]
                    if button and button.winfo_exists():
                        if tab in visible_tabs:
                            # Reposicionar botão na nova coluna sequencial
                            button.grid(row=0, column=col, padx=0, pady=0, sticky="ew")
                            col += 1
                        else:
                            # Completamente remover do grid
                            button.grid_forget()

        except Exception as e:
            logging.error(f"Erro ao reconstruir layout das abas: {e}")

    def _create_overflow_arrow(self):
        """Adiciona uma seta discreta ao último host FISICAMENTE visível para indicar mais opções."""
        try:
            if not hasattr(self.tab_view, '_segmented_button') or not self.tab_view._segmented_button:
                logging.warning("Não foi possível encontrar o container das abas")
                return

            segmented_button = self.tab_view._segmented_button

            # Encontrar a aba com maior número de coluna no grid (última posição física)
            last_visible_tab = None
            max_column = -1

            for tab in self.tab_view._name_list:
                if tab not in self.hidden_tabs and tab in segmented_button._buttons_dict:
                    button = segmented_button._buttons_dict[tab]
                    if button and button.winfo_exists():
                        try:
                            # Obter informações do grid
                            grid_info = button.grid_info()
                            if grid_info and 'column' in grid_info:
                                col = grid_info['column']
                                if col > max_column:
                                    max_column = col
                                    last_visible_tab = tab
                        except Exception as e:
                            logging.debug(f"Erro ao obter grid_info para {tab}: {e}")

            if not last_visible_tab:
                logging.warning("Não foi possível identificar o último host visível fisicamente")
                return

            # Encontrar o botão da última aba fisicamente visível
            if last_visible_tab in segmented_button._buttons_dict:
                last_button = segmented_button._buttons_dict[last_visible_tab]

                if last_button and last_button.winfo_exists():
                    # Obter o texto atual do botão (sem seta)
                    current_text = last_button.cget("text")
                    if not current_text.endswith("▼"):
                        # Adicionar seta ao texto da aba
                        new_text = f"{current_text} ▼"
                        last_button.configure(text=new_text)

                        # Armazenar texto original e referência para remover depois
                        self.overflow_arrow_tab = last_visible_tab
                        self.original_tab_text = current_text

                        # Bind do clique para interceptar seta ANTES do comportamento original
                        last_button.bind("<Button-1>", self._on_arrow_click)

                        logging.debug(f"Seta adicionada no último host fisicamente visível: {last_visible_tab} (coluna {max_column})")

        except Exception as e:
            logging.error(f"Erro ao criar seta de overflow: {e}")

    def _on_arrow_click(self, event):
        """Intercepta clique na seta para mostrar dropdown ao invés de mudar de aba."""
        try:
            # Verificar se o clique foi na área da seta (lado direito do botão)
            button_width = event.widget.winfo_width()
            click_x = event.x

            logging.debug(f"Clique detectado: x={click_x}, largura={button_width}, área_seta={button_width * 0.75}")

            # Se clicou nos últimos 25% da aba (área da seta), mostrar dropdown
            if click_x > button_width * 0.75:
                logging.debug("Clique na área da seta - abrindo dropdown")

                # Agendar abertura do dropdown para evitar interferência
                self.app.after_idle(self._show_overflow_dropdown_safe)

                # Impedir completamente a propagação do evento
                return "break"

            # Se clicou no nome do host, permitir mudança normal de aba
            logging.debug("Clique na área do nome - permitindo seleção da aba")
            return None

        except Exception as e:
            logging.error(f"Erro no clique da seta: {e}")
            return None  # Permitir o comportamento normal em caso de erro

    def _show_overflow_dropdown_safe(self):
        """Mostra o dropdown de forma segura após o processamento do clique."""
        try:
            if self.hidden_tabs and len(self.hidden_tabs) > 0:
                # Evitar loop se dropdown já existe
                if hasattr(self, 'overflow_dropdown') and self.overflow_dropdown:
                    try:
                        if self.overflow_dropdown.winfo_exists():
                            self.overflow_dropdown.destroy()
                    except:
                        pass
                    self.overflow_dropdown = None

                # Usar delay pequeno para evitar conflitos
                self.app.after(50, self._create_overflow_dropdown_delayed)
        except Exception as e:
            logging.error(f"Erro ao mostrar dropdown de forma segura: {e}")

    def _create_overflow_dropdown_delayed(self):
        """Cria dropdown com delay para evitar conflitos."""
        try:
            if hasattr(self, 'hidden_tabs') and self.hidden_tabs:
                self._create_overflow_dropdown()
        except Exception as e:
            logging.error(f"Erro ao criar dropdown com delay: {e}")

    def _toggle_overflow_dropdown(self):
        """Alterna a visibilidade do dropdown."""
        if self.overflow_dropdown and self.overflow_dropdown.winfo_exists():
            self.overflow_dropdown.destroy()
            self.overflow_dropdown = None
        else:
            self._create_overflow_dropdown()

    def _create_overflow_dropdown(self):
        """Cria o menu dropdown melhorado apenas com abas ocultas."""
        try:
            # Verificar se há abas ocultas para mostrar
            if not hasattr(self, 'hidden_tabs') or not self.hidden_tabs:
                return

            # Limpar dropdown existente de forma segura
            if hasattr(self, 'overflow_dropdown') and self.overflow_dropdown:
                try:
                    if self.overflow_dropdown.winfo_exists():
                        self.overflow_dropdown.destroy()
                except:
                    pass
                finally:
                    self.overflow_dropdown = None

            # Verificar se a aplicação ainda está ativa
            if not hasattr(self, 'app') or not self.app or not self.app.winfo_exists():
                return

            # Criar dropdown com estilo melhorado
            self.overflow_dropdown = tkinter.Menu(
                self.tab_view,
                tearoff=0,
                font=('Segoe UI', 9),
                bg='#2B2B2B',
                fg='#FFFFFF',
                activebackground='#404040',
                activeforeground='#FFFFFF',
                relief='flat',
                borderwidth=1
            )

            # Obter status dos hosts para mostrar indicadores
            current_tab = self.tab_view.get()

            # Adicionar título do menu
            if self.hidden_tabs:
                self.overflow_dropdown.add_command(
                    label=f"▼ Hosts Ocultos ({len(self.hidden_tabs)})",
                    state='disabled',
                    font=('Segoe UI', 9, 'bold')
                )
                self.overflow_dropdown.add_separator()

            # Adicionar apenas abas que estão na lista de hidden_tabs
            for tab_name in self.hidden_tabs:
                if tab_name != self.placeholder_name:
                    # Obter status do host para o indicador
                    status_indicator = "●" if tab_name == current_tab else "○"

                    # Buscar status do host
                    host_status = "unknown"
                    for host_name_key, host_data in self.host_tabs_data.items():
                        if self._get_display_name(host_data['host_info']) == tab_name:
                            ip = host_data['host_info']['ip']
                            host_status = self.app.host_statuses.get(ip, 'unknown')
                            break

                    # Indicador de status colorido
                    status_colors = {
                        'online': '🟢',
                        'offline': '🔴',
                        'unknown': '⚪'
                    }
                    status_icon = status_colors.get(host_status, '⚪')

                    # Texto com formatação melhorada
                    display_text = f"{status_icon} {tab_name}"
                    if tab_name == current_tab:
                        display_text = f"▶ {status_icon} {tab_name}"

                    self.overflow_dropdown.add_command(
                        label=display_text,
                        command=lambda name=tab_name: self._select_tab_from_dropdown(name)
                    )

            # Mostrar o dropdown na posição da aba com seta
            if (hasattr(self, 'overflow_arrow_tab') and
                hasattr(self.tab_view, '_segmented_button') and
                self.tab_view._segmented_button and
                self.overflow_arrow_tab in self.tab_view._segmented_button._buttons_dict):

                arrow_button = self.tab_view._segmented_button._buttons_dict[self.overflow_arrow_tab]
                if arrow_button and arrow_button.winfo_exists():
                    # Posicionar dropdown no canto direito da aba (onde está a seta)
                    x = arrow_button.winfo_rootx() + arrow_button.winfo_width() - 50
                    y = arrow_button.winfo_rooty() + arrow_button.winfo_height() + 2
                    self.overflow_dropdown.post(x, y)
                    logging.debug(f"Dropdown melhorado criado com {len(self.hidden_tabs)} abas ocultas na posição da seta")

        except Exception as e:
            logging.error(f"Erro ao criar dropdown: {e}")

    def _select_tab_from_dropdown(self, tab_name):
        """Seleciona uma aba através do dropdown."""
        try:
            logging.debug(f"Selecionando aba {tab_name} através do dropdown")

            # Primeiro, fechar o dropdown
            if self.overflow_dropdown:
                self.overflow_dropdown.destroy()
                self.overflow_dropdown = None

            # Reorganizar as abas: mover a aba selecionada para uma posição visível
            self._make_tab_visible(tab_name)

            # Agora selecionar a aba
            self.tab_view.set(tab_name)

            # Disparar o callback de mudança de aba
            self._on_tab_selected()

        except Exception as e:
            logging.error(f"Erro ao selecionar aba do dropdown: {e}")

    def _make_tab_visible(self, tab_name):
        """Move uma aba oculta para a posição visível mantendo alinhamento natural SEM GAPS."""
        try:
            if tab_name not in self.hidden_tabs:
                return  # Já está visível

            logging.debug(f"Movendo aba {tab_name} para posição visível sem gaps")

            # Remover a seta da aba atual se existir
            if hasattr(self, 'overflow_arrow_tab') and hasattr(self, 'original_tab_text'):
                if (hasattr(self.tab_view, '_segmented_button') and
                    self.tab_view._segmented_button and
                    self.overflow_arrow_tab in self.tab_view._segmented_button._buttons_dict):

                    old_arrow_button = self.tab_view._segmented_button._buttons_dict[self.overflow_arrow_tab]
                    if old_arrow_button and old_arrow_button.winfo_exists():
                        old_arrow_button.configure(text=self.original_tab_text)

            # ESTRATÉGIA DEFINITIVA: Reorganizar abas fisicamente para eliminar gaps
            all_tabs = self.tab_view._name_list[:]

            # Calcular quantas abas cabem (incluindo sempre a selecionada)
            available_width = self.tab_view.winfo_width()
            dropdown_button_width = 80
            usable_width = available_width - dropdown_button_width

            # Determinar ordem de prioridade: aba selecionada primeiro, depois ordem original
            priority_tabs = [tab_name] + [tab for tab in all_tabs if tab != tab_name]

            # Calcular quais abas serão visíveis
            cumulative_width = 0
            new_visible_tabs = []

            for tab in priority_tabs:
                char_width = len(tab) * 10
                padding_and_icon = 54
                estimated_tab_width = max(120, min(char_width + padding_and_icon, 220))

                if cumulative_width + estimated_tab_width <= usable_width:
                    new_visible_tabs.append(tab)
                    cumulative_width += estimated_tab_width

            # Reorganizar na ordem original (preservando ordem visual natural)
            final_visible_tabs = [tab for tab in all_tabs if tab in new_visible_tabs]

            # Atualizar hidden_tabs
            self.hidden_tabs = [tab for tab in all_tabs if tab not in final_visible_tabs]

            # CHAVE: Reconstruir layout físico das abas para eliminar gaps
            self._rebuild_tab_layout()

            # Adicionar seta na última aba visível se há abas ocultas (com delay para estabilizar layout)
            if self.hidden_tabs:
                self.app.after(1500, self._create_overflow_arrow)  # Delay maior para estabilizar
            else:
                # Limpar referências se não há abas ocultas
                if hasattr(self, 'overflow_arrow_tab'):
                    delattr(self, 'overflow_arrow_tab')
                if hasattr(self, 'original_tab_text'):
                    delattr(self, 'original_tab_text')

            logging.debug(f"Aba {tab_name} agora visível. Visíveis: {final_visible_tabs}, Ocultas: {len(self.hidden_tabs)}")

        except Exception as e:
            logging.error(f"Erro ao tornar aba visível: {e}")

    def _update_overflow_dropdown(self):
        """Atualiza o conteúdo do dropdown."""
        if self.overflow_dropdown and self.overflow_dropdown.winfo_exists():
            self.overflow_dropdown.destroy()
            self.overflow_dropdown = None