# src/ui/components/multi_row_tab_view.py
# Sistema de abas com suporte a múltiplas linhas quando excede a largura da janela

import customtkinter
import tkinter
import logging
from typing import Dict, List, Optional, Callable


class MultiRowTabView(customtkinter.CTkFrame):
    def __init__(self, master, command: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)

        self.command = command
        self._tabs: Dict[str, Dict] = {}  # name -> {"frame": frame, "button": button, "row": row_index}
        self._current_tab = None
        self._tab_buttons: List[List[customtkinter.CTkButton]] = []  # Linhas de botões
        self._tab_rows: List[customtkinter.CTkFrame] = []  # Frames das linhas
        self._content_frame = None

        # Configurações de layout
        self.tab_height = 28
        self.tab_min_width = 60
        self.tab_max_width = 300  # Aumentar limite máximo para textos muito longos
        self.tab_spacing = 3
        self.row_spacing = 3
        self.tab_padding = 16  # Padding moderado (8px cada lado)

        self._setup_layout()

        # Bind para redimensionamento
        self.bind("<Configure>", self._on_resize)

        # Configuração de altura máxima (20% da janela)
        self.max_height_percentage = 0.20
        self._last_calculated_max_height = 100

        # Configurar altura inicial após um pequeno delay
        self.after(100, self._update_scroll_frame_height)

    def _setup_layout(self):
        """Configura o layout básico do componente."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Content frame expandirá

        # Criar frame inicial (será substituído dinamicamente)
        self.tabs_scroll_frame = None
        self.tabs_container = None
        self._current_frame_is_scrollable = False

        # Criar frame inicial não-scrollable
        self._create_tabs_frame(scrollable=False)

        # Frame para o conteúdo das abas
        self._content_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self._content_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

    def _create_tabs_frame(self, scrollable=False):
        """Cria o frame de abas (scrollable ou normal) conforme necessário."""
        # Destruir frame anterior se existir
        if self.tabs_scroll_frame:
            self.tabs_scroll_frame.destroy()

        if scrollable:
            # Criar frame scrollable
            self.tabs_scroll_frame = customtkinter.CTkScrollableFrame(
                self,
                fg_color="transparent",
                scrollbar_button_color=("gray70", "gray30"),
                scrollbar_button_hover_color=("gray60", "gray40"),
                height=50  # Altura inicial
            )
            self._current_frame_is_scrollable = True
        else:
            # Criar frame normal (sem scroll)
            self.tabs_scroll_frame = customtkinter.CTkFrame(
                self,
                fg_color="transparent",
                height=50  # Altura inicial
            )
            self._current_frame_is_scrollable = False

        self.tabs_scroll_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.tabs_scroll_frame.grid_columnconfigure(0, weight=1)

        # Container interno para as abas
        self.tabs_container = customtkinter.CTkFrame(self.tabs_scroll_frame, fg_color="transparent")
        self.tabs_container.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.tabs_container.grid_columnconfigure(0, weight=1)

    def add(self, name: str) -> customtkinter.CTkFrame:
        """Adiciona uma nova aba e retorna o frame de conteúdo."""
        if name in self._tabs:
            return self._tabs[name]["frame"]

        # Criar frame de conteúdo para a aba
        tab_frame = customtkinter.CTkFrame(self._content_frame, fg_color="transparent")
        tab_frame.grid(row=0, column=0, sticky="nsew")
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(0, weight=1)

        # Ocultar inicialmente
        tab_frame.grid_remove()

        # Criar botão da aba
        self._tabs[name] = {
            "frame": tab_frame,
            "button": None,
            "row": 0
        }

        # Reorganizar imediatamente
        self._reorganize_tabs()
        return tab_frame

    def delete(self, name: str):
        """Remove uma aba."""
        if name not in self._tabs:
            return

        tab_data = self._tabs[name]

        # Remover frame
        tab_data["frame"].destroy()

        # Remover botão
        if tab_data["button"]:
            tab_data["button"].destroy()

        # Remover dos dados
        del self._tabs[name]

        # Se era a aba atual, selecionar outra
        if self._current_tab == name:
            remaining_tabs = list(self._tabs.keys())
            if remaining_tabs:
                self.set(remaining_tabs[0])
            else:
                self._current_tab = None

        self._reorganize_tabs()

    def set(self, name: str):
        """Seleciona uma aba."""
        if name not in self._tabs:
            return

        # Ocultar aba atual
        if self._current_tab and self._current_tab in self._tabs:
            self._tabs[self._current_tab]["frame"].grid_remove()
            if self._tabs[self._current_tab]["button"]:
                self._tabs[self._current_tab]["button"].configure(
                    fg_color=("gray75", "gray25"),
                    text_color=("#1F1F1F", "#FFFFFF")
                )

        # Mostrar nova aba
        self._current_tab = name
        self._tabs[name]["frame"].grid()
        if self._tabs[name]["button"]:
            self._tabs[name]["button"].configure(
                fg_color=("gray65", "gray35"),
                text_color=("#000000", "#FFFFFF")  # Ainda mais escuro quando selecionado no tema claro
            )

        # Executar callback
        if self.command:
            try:
                self.command()
            except Exception as e:
                logging.error(f"Erro no callback da aba: {e}")

    def get(self) -> Optional[str]:
        """Retorna o nome da aba atualmente selecionada."""
        return self._current_tab

    def tab(self, name: str) -> Optional[customtkinter.CTkFrame]:
        """Retorna o frame de conteúdo de uma aba."""
        if name in self._tabs:
            return self._tabs[name]["frame"]
        return None

    @property
    def _name_list(self) -> List[str]:
        """Lista de nomes das abas (compatibilidade com CTkTabview)."""
        return list(self._tabs.keys())

    def _on_resize(self, event=None):
        """Chamado quando o componente é redimensionado."""
        if event and event.widget == self:
            # Cancelar reorganização pendente para evitar múltiplas chamadas
            if hasattr(self, '_resize_after_id'):
                self.after_cancel(self._resize_after_id)

            # Agendar reorganização única após pequeno delay
            self._resize_after_id = self.after(10, self._handle_resize_complete)

    def _handle_resize_complete(self):
        """Manipula o redimensionamento completo."""
        self._update_scroll_frame_height()
        self._reorganize_tabs()

    def _get_main_window_height(self):
        """Obtém a altura da janela principal da aplicação."""
        try:
            # Navegar pela hierarquia até encontrar a janela principal
            widget = self
            while widget and not isinstance(widget, (customtkinter.CTk, customtkinter.CTkToplevel)):
                widget = widget.master

            if widget:
                widget.update_idletasks()
                return widget.winfo_height()

            return 600  # Fallback
        except Exception:
            return 600  # Fallback

    def _update_scroll_frame_height(self):
        """Atualiza a altura do scroll frame e alterna entre scrollable/normal conforme necessário."""
        try:
            # Calcular altura necessária baseada no número de linhas de abas
            num_rows = len(self._tab_rows)

            if num_rows == 0:
                # Se não há abas, usar altura mínima
                needed_height = self.tab_height + 20
            else:
                # Calcular altura total necessária para todas as linhas com padding
                needed_height = (num_rows * (self.tab_height + self.row_spacing)) + 20
                # Remover o último row_spacing
                needed_height -= self.row_spacing

            # Obter altura máxima permitida (20% da janela principal)
            main_window_height = self._get_main_window_height()
            max_allowed_height = int(main_window_height * self.max_height_percentage)

            # Altura mínima para pelo menos 1 linha
            min_height = self.tab_height + 20
            max_allowed_height = max(max_allowed_height, min_height)

            # Determinar se precisa de scroll
            needs_scroll = needed_height > max_allowed_height

            # Verificar se precisa trocar tipo de frame
            if needs_scroll and not self._current_frame_is_scrollable:
                # Precisa de scroll mas está usando frame normal
                logging.debug("Trocando para frame scrollable")
                self._recreate_frame_with_scroll()
                final_height = max_allowed_height
            elif not needs_scroll and self._current_frame_is_scrollable:
                # Não precisa de scroll mas está usando frame scrollable
                logging.debug("Trocando para frame normal (sem scroll)")
                self._recreate_frame_without_scroll()
                final_height = needed_height
            else:
                # Tipo de frame correto, apenas ajustar altura
                final_height = max_allowed_height if needs_scroll else needed_height

            # Atualizar altura do frame
            try:
                current_height = self.tabs_scroll_frame.cget("height")
                if abs(final_height - current_height) > 5:
                    self.tabs_scroll_frame.configure(height=final_height)
                    logging.debug(f"Altura ajustada: {final_height}px (linhas: {num_rows}, scroll: {needs_scroll})")
            except:
                pass

        except Exception as e:
            logging.debug(f"Erro ao calcular altura do scroll frame: {e}")

    def _recreate_frame_with_scroll(self):
        """Recria o frame como scrollable e reconstrói as abas."""
        # Salvar dados das abas atuais
        tabs_data = dict(self._tabs)
        current_tab = self._current_tab

        # Recriar frame como scrollable
        self._create_tabs_frame(scrollable=True)

        # Recriar todas as abas
        self._rebuild_tabs(tabs_data, current_tab)

    def _recreate_frame_without_scroll(self):
        """Recria o frame como normal (sem scroll) e reconstrói as abas."""
        # Salvar dados das abas atuais
        tabs_data = dict(self._tabs)
        current_tab = self._current_tab

        # Recriar frame como normal
        self._create_tabs_frame(scrollable=False)

        # Recriar todas as abas
        self._rebuild_tabs(tabs_data, current_tab)

    def _rebuild_tabs(self, tabs_data, current_tab):
        """Reconstrói as abas após trocar tipo de frame."""
        # Limpar dados atuais
        self._tabs = {}
        self._tab_rows = []

        # Recriar abas na ordem correta
        if tabs_data:
            # Organizar abas
            self._reorganize_tabs()

            # Restaurar aba atual
            if current_tab and current_tab in self._tabs:
                self.set(current_tab)

    def _calculate_text_width(self, text: str, font_size: int = 11) -> int:
        """Calcula a largura necessária para exibir o texto completamente."""
        try:
            # Usar medição mais precisa baseada no texto real
            # Caracteres têm larguras diferentes, vamos ser mais conservadores

            # Análise de largura por tipo de caractere
            narrow_chars = text.count('i') + text.count('l') + text.count('t') + text.count('f') + text.count('j')
            wide_chars = text.count('m') + text.count('w') + text.count('M') + text.count('W')
            normal_chars = len(text) - narrow_chars - wide_chars

            # Larguras estimadas para fonte 11px
            narrow_width = narrow_chars * (font_size * 0.4)
            wide_width = wide_chars * (font_size * 0.8)
            normal_width = normal_chars * (font_size * 0.65)

            text_width = narrow_width + wide_width + normal_width

            # Padding otimizado para evitar cortes sem desperdiçar espaço
            total_width = text_width + self.tab_padding + 8  # Margem moderada

            # Aplicar limites mín/máx
            return max(self.tab_min_width, min(self.tab_max_width, int(total_width)))

        except Exception as e:
            logging.debug(f"Erro ao calcular largura do texto '{text}': {e}")
            return self.tab_min_width

    def _calculate_tab_widths(self, tab_names: List[str]) -> Dict[str, int]:
        """Calcula a largura otimizada para cada aba baseada no texto."""
        widths = {}
        for name in tab_names:
            widths[name] = self._calculate_text_width(name)
        return widths

    def _organize_tabs_in_rows(self, tab_names: List[str], tab_widths: Dict[str, int], available_width: int) -> List[List[str]]:
        """Organiza as abas em linhas de forma otimizada para maximizar o uso do espaço."""
        rows = []
        current_row = []
        current_row_width = 0

        logging.debug(f"Organizando {len(tab_names)} abas em largura disponível: {available_width}px")

        for i, tab_name in enumerate(tab_names):
            tab_width = tab_widths[tab_name]

            # Para o primeiro item da linha, não adicionar spacing
            spacing = self.tab_spacing if current_row else 0
            needed_width = tab_width + spacing

            logging.debug(f"Aba '{tab_name}': largura={tab_width}px, necessário={needed_width}px, linha_atual={current_row_width}px")

            # Verificar se a aba cabe na linha atual
            if current_row and (current_row_width + needed_width > available_width):
                # Linha atual está cheia, começar nova linha
                logging.debug(f"Linha cheia ({current_row_width}px), criando nova linha com {len(current_row)} abas")
                rows.append(current_row)
                current_row = [tab_name]
                current_row_width = tab_width
            else:
                # Aba cabe na linha atual
                current_row.append(tab_name)
                current_row_width += needed_width
                logging.debug(f"Aba adicionada à linha atual, total: {current_row_width}px")

        # Adicionar última linha se não estiver vazia
        if current_row:
            logging.debug(f"Última linha com {len(current_row)} abas, largura: {current_row_width}px")
            rows.append(current_row)

        logging.debug(f"Resultado: {len(rows)} linhas criadas")
        for i, row in enumerate(rows):
            total_width = sum(tab_widths[tab] for tab in row) + (len(row) - 1) * self.tab_spacing
            logging.debug(f"Linha {i+1}: {len(row)} abas, largura total: {total_width}px")

        return rows

    def _reorganize_tabs(self):
        """Reorganiza as abas em múltiplas linhas conforme necessário."""
        if not self._tabs:
            self._clear_tab_rows()
            return

        # Obter largura disponível de forma simples
        self.update_idletasks()
        available_width = self.tabs_container.winfo_width()

        # Se não conseguir obter largura, usar fallback conservador
        if available_width <= 120:
            # Tentar obter largura da janela principal
            try:
                main_window = self.winfo_toplevel()
                if main_window:
                    main_window.update_idletasks()
                    main_width = main_window.winfo_width()
                    if main_width > 200:
                        available_width = int(main_width * 0.85)
                    else:
                        available_width = 800  # Fallback seguro
                else:
                    available_width = 800
            except Exception:
                available_width = 800

        logging.debug(f"Largura do container: {available_width}px")

        # Limpar linhas existentes
        self._clear_tab_rows()

        # Calcular distribuição das abas em linhas
        tab_names = list(self._tabs.keys())
        if not tab_names:
            return

        # Calcular larguras específicas para cada aba baseada no texto
        tab_widths = self._calculate_tab_widths(tab_names)
        # Margem de segurança proporcional (mínimo 10px, máximo 20px)
        safety_margin = max(10, min(20, int(available_width * 0.05)))
        available_for_tabs = available_width - safety_margin
        logging.debug(f"Margem de segurança: {safety_margin}px, Largura para abas: {available_for_tabs}px")

        # Organizar abas em linhas de forma otimizada
        tab_rows_data = self._organize_tabs_in_rows(tab_names, tab_widths, available_for_tabs)

        # Criar abas organizadas por linhas
        for row_index, row_tabs in enumerate(tab_rows_data):
            # Criar linha se necessário
            self._create_tab_row(row_index)

            # Criar botões para cada aba da linha
            for col_index, tab_name in enumerate(row_tabs):
                tab_width = tab_widths[tab_name]

                # Criar botão da aba com largura específica
                button = self._create_tab_button(
                    tab_name,
                    self._tab_rows[row_index],
                    tab_width
                )

                # Posicionar botão
                button.grid(
                    row=0,
                    column=col_index,
                    padx=(0, self.tab_spacing if col_index < len(row_tabs) - 1 else 0),
                    pady=0,
                    sticky="w"  # Alinhar à esquerda para manter larguras específicas
                )

                # Atualizar dados da aba
                self._tabs[tab_name]["button"] = button
                self._tabs[tab_name]["row"] = row_index

        # Atualizar altura do scroll frame baseada no número de linhas criadas
        self._update_scroll_frame_height()

        # Aplicar estado da aba atual
        if self._current_tab and self._current_tab in self._tabs:
            if self._tabs[self._current_tab]["button"]:
                self._tabs[self._current_tab]["button"].configure(
                    fg_color=("gray65", "gray35")
                )


    def _create_tab_row(self, row_index: int):
        """Cria uma nova linha de abas."""
        while len(self._tab_rows) <= row_index:
            row_frame = customtkinter.CTkFrame(
                self.tabs_container,
                fg_color="transparent",
                height=self.tab_height
            )
            row_frame.grid(
                row=len(self._tab_rows),
                column=0,
                sticky="ew",
                pady=(0, self.row_spacing)
            )
            # Não configurar weight para evitar espaçamento irregular
            self._tab_rows.append(row_frame)

    def _create_tab_button(self, name: str, parent: customtkinter.CTkFrame, width: int) -> customtkinter.CTkButton:
        """Cria um botão de aba de forma simples e direta."""
        try:
            # Tentar criar botão com configuração completa
            return customtkinter.CTkButton(
                parent,
                text=name,
                width=width,
                height=self.tab_height,
                command=lambda: self.set(name),
                fg_color=("gray75", "gray25"),
                hover_color=("gray70", "gray30"),
                text_color=("#1F1F1F", "#FFFFFF"),
                corner_radius=6
            )
        except Exception as e:
            logging.debug(f"Erro ao criar botão completo: {e}")
            try:
                # Fallback: botão mais simples
                return customtkinter.CTkButton(
                    parent,
                    text=name,
                    width=width,
                    height=self.tab_height,
                    command=lambda: self.set(name)
                )
            except Exception as e2:
                logging.error(f"Erro crítico ao criar botão: {e2}")
                # Último recurso: botão mínimo
                return customtkinter.CTkButton(parent, text=name)

    def _clear_tab_rows(self):
        """Limpa todas as linhas de abas."""
        for row_frame in self._tab_rows:
            row_frame.destroy()
        self._tab_rows.clear()

        # Limpar referências de botões
        for tab_data in self._tabs.values():
            tab_data["button"] = None

    def configure(self, command=None, **kwargs):
        """Configura o componente."""
        if command is not None:
            self.command = command
        super().configure(**kwargs)

    def update_theme(self):
        """Atualiza as cores dos botões das abas quando o tema muda."""
        try:
            for tab_name, tab_data in self._tabs.items():
                button = tab_data.get("button")
                if button and button.winfo_exists():
                    is_selected = (tab_name == self._current_tab)
                    if is_selected:
                        button.configure(
                            fg_color=("gray65", "gray35"),
                            text_color=("#000000", "#FFFFFF")
                        )
                    else:
                        button.configure(
                            fg_color=("gray75", "gray25"),
                            text_color=("#1F1F1F", "#FFFFFF")
                        )
        except Exception as e:
            logging.debug(f"Error updating MultiRowTabView theme: {e}")

    def cleanup_callbacks(self):
        """Limpa todos os callbacks pendentes do componente."""
        try:
            # Cancelar callback de resize pendente
            if hasattr(self, '_resize_after_id') and self._resize_after_id:
                try:
                    self.after_cancel(self._resize_after_id)
                    self._resize_after_id = None
                    logging.debug("Callback de resize cancelado no MultiRowTabView")
                except Exception as e:
                    logging.debug(f"Erro ao cancelar callback de resize: {e}")

            # Cancelar callbacks de todos os botões de abas
            for tab_name, tab_data in self._tabs.items():
                if 'button' in tab_data and tab_data['button']:
                    try:
                        button = tab_data['button']
                        # Remover comando para evitar callbacks
                        button.configure(command=None)
                        logging.debug(f"Comando removido da aba {tab_name}")
                    except Exception as e:
                        logging.debug(f"Erro ao limpar comando da aba {tab_name}: {e}")

            logging.debug("Cleanup de callbacks do MultiRowTabView concluído")

        except Exception as e:
            logging.debug(f"Erro durante cleanup do MultiRowTabView: {e}")