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
        self.tab_height = 32
        self.tab_min_width = 120
        self.tab_max_width = 200
        self.tab_spacing = 2
        self.row_spacing = 2

        self._setup_layout()

        # Bind para redimensionamento
        self.bind("<Configure>", self._on_resize)

    def _setup_layout(self):
        """Configura o layout básico do componente."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Content frame expandirá

        # Frame para as abas (múltiplas linhas)
        self.tabs_container = customtkinter.CTkFrame(self, fg_color="transparent", height=50)
        self.tabs_container.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        self.tabs_container.grid_columnconfigure(0, weight=1)

        # Frame para o conteúdo das abas
        self._content_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self._content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

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
                    fg_color=("gray75", "gray25")
                )

        # Mostrar nova aba
        self._current_tab = name
        self._tabs[name]["frame"].grid()
        if self._tabs[name]["button"]:
            self._tabs[name]["button"].configure(
                fg_color=("gray65", "gray35")
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
            self.after_idle(self._reorganize_tabs)

    def _reorganize_tabs(self):
        """Reorganiza as abas em múltiplas linhas conforme necessário."""
        if not self._tabs:
            self._clear_tab_rows()
            return

        # Obter largura disponível
        self.update_idletasks()
        available_width = self.tabs_container.winfo_width()
        if available_width <= 1:
            # Se ainda não foi renderizado, agendar para depois
            self.after(100, self._reorganize_tabs)
            return

        # Limpar linhas existentes
        self._clear_tab_rows()

        # Calcular distribuição das abas em linhas
        tab_names = list(self._tabs.keys())
        if not tab_names:
            return

        # Calcular largura de cada aba
        num_tabs = len(tab_names)
        tab_width = max(
            self.tab_min_width,
            min(self.tab_max_width, (available_width - 20) // num_tabs - self.tab_spacing)
        )

        # Calcular quantas abas cabem por linha
        tabs_per_row = max(1, (available_width - 20) // (tab_width + self.tab_spacing))

        # Distribuir abas em linhas
        current_row = 0
        current_col = 0

        for tab_name in tab_names:
            # Criar nova linha se necessário
            if current_col == 0:
                self._create_tab_row(current_row)

            # Criar botão da aba
            button = self._create_tab_button(
                tab_name,
                self._tab_rows[current_row],
                tab_width
            )

            # Posicionar botão
            button.grid(
                row=0,
                column=current_col,
                padx=(0, self.tab_spacing),
                pady=0,
                sticky="ew"
            )

            # Atualizar dados da aba
            self._tabs[tab_name]["button"] = button
            self._tabs[tab_name]["row"] = current_row

            # Próxima posição
            current_col += 1
            if current_col >= tabs_per_row:
                current_col = 0
                current_row += 1

        # Ajustar altura do container de abas
        num_rows = len(self._tab_rows)
        total_height = num_rows * (self.tab_height + self.row_spacing) - self.row_spacing + 10
        self.tabs_container.configure(height=total_height)

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
            row_frame.grid_columnconfigure(0, weight=1)
            self._tab_rows.append(row_frame)

    def _create_tab_button(self, name: str, parent: customtkinter.CTkFrame, width: int) -> customtkinter.CTkButton:
        """Cria um botão de aba."""
        button = customtkinter.CTkButton(
            parent,
            text=name,
            width=width,
            height=self.tab_height,
            command=lambda: self.set(name),
            fg_color=("gray75", "gray25"),
            hover_color=("gray70", "gray30"),
            font=customtkinter.CTkFont(size=12),
            compound="left"  # Permitir imagem + texto
        )
        return button

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