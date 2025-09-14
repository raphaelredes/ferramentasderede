# app/ui_components/event_log_frame.py
# Frame para visualizar logs de eventos remotos com uma tabela interativa.

import customtkinter
from tkinter import ttk
import tkinter as tk
import logging
from datetime import datetime, timezone

class EventLogFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.host = host
        self.tool_controller = tool_controller
        self.tool_controller.event_log_frame = self  # Passa a referência do frame para o controller
        self.all_logs = []
        logging.info(f"EventLogFrame initialized for host: {self.host.get('name', self.host.get('ip', 'Unknown'))}")

        self._create_widgets()
        self.update_language()
        
        # Buscar logs automaticamente após um pequeno delay
        self.after(500, self._auto_fetch_logs)

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Linha dos controles
        self.grid_rowconfigure(1, weight=1) # Linha da tabela (expandir)
        self.grid_rowconfigure(2, weight=0) # Linha do painel de detalhes (fixo)

        # --- Frame de Controles ---
        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure(7, weight=1)

        self.log_name_label = customtkinter.CTkLabel(controls_frame, text="")
        self.log_name_label.grid(row=0, column=0, padx=(10, 5), pady=5)
        self.log_name_combo = customtkinter.CTkComboBox(controls_frame, values=["Application", "System", "Security"])
        self.log_name_combo.set("Application")
        self.log_name_combo.grid(row=0, column=1, padx=5, pady=5)

        self.level_label = customtkinter.CTkLabel(controls_frame, text="")
        self.level_label.grid(row=0, column=2, padx=(10, 5), pady=5)
        self.level_combo = customtkinter.CTkComboBox(controls_frame, values=["Error", "Warning", "Information"])
        self.level_combo.set("Error")
        self.level_combo.grid(row=0, column=3, padx=5, pady=5)
        
        self.count_label = customtkinter.CTkLabel(controls_frame, text="")
        self.count_label.grid(row=0, column=4, padx=(10, 5), pady=5)
        self.count_entry = customtkinter.CTkEntry(controls_frame, width=60)
        self.count_entry.insert(0, "50")
        self.count_entry.grid(row=0, column=5, padx=5, pady=5)
        
        self.fetch_button = customtkinter.CTkButton(controls_frame, text="", command=self.fetch_logs)
        self.fetch_button.grid(row=0, column=6, padx=(10, 5), pady=5)
        
        self.filter_entry = customtkinter.CTkEntry(controls_frame, placeholder_text="")
        self.filter_entry.grid(row=0, column=7, padx=(5, 10), pady=5, sticky="ew")
        self.filter_entry.bind("<KeyRelease>", self._filter_logs)

        # --- Container para Tabela de Logs com Scrollbar ---
        current_mode = customtkinter.get_appearance_mode().lower()
        if current_mode == "light":
            table_bg = "#F8F9FA"
        else:
            table_bg = "#2B2B2B"
            
        table_frame = customtkinter.CTkFrame(self, fg_color=table_bg)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 5))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        # --- CONFIGURAR ESTILOS ANTES DE CRIAR O TREEVIEW ---
        self._configure_styles()
        
        # --- Tabela de Logs (Treeview) ---
        self.tree = ttk.Treeview(table_frame, columns=("Time", "Level", "Source", "ID"), show="headings", style="Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_log_select)
        
        # --- Scrollbar ---
        scrollbar = customtkinter.CTkScrollbar(table_frame, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Configurar headers iniciais (serão atualizados pelo update_language)
        self.tree.heading("Time", text="Time")
        self.tree.heading("Level", text="Level") 
        self.tree.heading("Source", text="Source")
        self.tree.heading("ID", text="ID")
        
        # Configurar larguras das colunas
        self.tree.column("Time", width=150, anchor="w")
        self.tree.column("Level", width=80, anchor="center")
        self.tree.column("Source", width=120, anchor="w")
        self.tree.column("ID", width=80, anchor="center")
        
        # Não adicionar mensagem placeholder - deixar tabela vazia quando não há logs

        # --- Painel de Detalhes ---
        self.details_textbox = customtkinter.CTkTextbox(self, height=200, wrap="word")
        self.details_textbox.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.details_textbox.configure(state="disabled")

    def _add_placeholder_message(self):
        """Adiciona uma mensagem placeholder inicial para evitar tela branca."""
        # Remover mensagem placeholder - deixar tabela vazia quando não há logs
        # Isso proporciona uma aparência mais limpa
        pass


    def _apply_appearance_mode(self, color_value):
        """
        Aplica a cor correta baseada no modo de aparência atual.
        Usa cores melhoradas para o tema claro.
        """
        # Se for uma tupla, extrair a cor correta baseada no modo
        if isinstance(color_value, tuple) and len(color_value) == 2:
            current_mode = customtkinter.get_appearance_mode()
            if current_mode.lower() == "light":
                base_color = color_value[0]
            else:
                base_color = color_value[1]
        elif isinstance(color_value, str):
            base_color = color_value
        else:
            # Se não conseguir determinar, usar valor padrão
            return "#FFFFFF"
        
        # Aplicar melhorias se for tema claro
        current_mode = customtkinter.get_appearance_mode()
        if current_mode.lower() == "light":
            # Mapear cores específicas para versões melhoradas
            enhanced_colors = {
                "#EAEAEA": "#FBFBFB",  # Cor de linha alternada mais sutil
                "#F0F0F0": "#F8F9FA",  # Fundo de cabeçalho mais suave
                "gray90": "#FAFAFA",   # Fundo geral mais suave
                "gray80": "#F3F3F3",   # Hover mais sutil
                "gray86": "#F8F9FA",   # Fundo do frame mais suave
                "gray17": "#2B2B2B",   # Para modo escuro
            }
            return enhanced_colors.get(base_color, base_color)
        else:
            return base_color

    def _configure_styles(self):
        """Configura a aparência do Treeview para combinar com o tema do CustomTkinter."""
        try:
            # Obter cores do tema atual
            current_mode = customtkinter.get_appearance_mode().lower()
            
            if current_mode == "light":
                bg_color = "#F8F9FA"  # Fundo claro melhorado
                text_color = "white"    # Texto branco
                header_bg = "#E9ECEF"  # Cabeçalho claro
                oddrow_color = "#FBFBFB"  # Linha alternada
                evenrow_color = "#F8F9FA"  # Linha par
                selected_color = "#007BFF"  # Seleção azul
            else:
                bg_color = "#2B2B2B"  # Fundo escuro
                text_color = "#FFFFFF"  # Texto branco
                header_bg = "#3C3C3C"  # Cabeçalho escuro
                oddrow_color = "#252525"  # Linha alternada escura
                evenrow_color = "#2B2B2B"  # Linha par escura
                selected_color = "#007BFF"  # Seleção azul
            
            logging.debug(f"EventLogFrame colors - bg: {bg_color}, text: {text_color}, header: {header_bg}")
            
            # Configurar estilo do Treeview
            style = ttk.Style()
            style.theme_use("clam")
            
            # Configuração principal do Treeview
            style.configure("Treeview", 
                            background=bg_color, 
                            foreground=text_color, 
                            fieldbackground=bg_color, 
                            borderwidth=0,
                            relief="flat",
                            rowheight=25)  # Altura das linhas
            
            # Configuração do cabeçalho
            style.configure("Treeview.Heading", 
                            background=header_bg, 
                            foreground=text_color, 
                            relief="flat",
                            borderwidth=0,
                            font=("Arial", 9, "bold"))
            
            # Mapeamento de estados
            style.map("Treeview",
                      background=[('selected', selected_color)],
                      foreground=[('selected', '#FFFFFF')])
            
            style.map("Treeview.Heading",
                      background=[('active', header_bg)],
                      relief=[('pressed', 'flat'), ('active', 'flat')])
            
            # Configurar tags para linhas alternadas
            if hasattr(self, 'tree'):
                self.tree.tag_configure('oddrow', background=oddrow_color)
                self.tree.tag_configure('evenrow', background=evenrow_color)
                self.tree.tag_configure('selected', background=selected_color, foreground='#FFFFFF')
            
        except Exception as e:
            logging.error(f"Error configuring EventLogFrame styles: {e}")
            # Fallback para cores padrão
            if hasattr(self, 'tree'):
                self.tree.tag_configure('oddrow', background="#F5F5F5")
                self.tree.tag_configure('evenrow', background="#FFFFFF")

    def update_theme(self):
        """
        Atualiza o tema do componente. Chamado quando o tema da aplicação muda.
        """
        try:
            # Reconfigurar estilos
            self._configure_styles()
            
            # Atualizar cor do frame container
            current_mode = customtkinter.get_appearance_mode().lower()
            if current_mode == "light":
                table_bg = "#F8F9FA"
            else:
                table_bg = "#2B2B2B"
            
            # Encontrar e atualizar o table_frame
            for child in self.winfo_children():
                if isinstance(child, customtkinter.CTkFrame):
                    # Verificar se é o table_frame (primeiro frame com grid_rowconfigure)
                    try:
                        child.configure(fg_color=table_bg)
                        break
                    except:
                        continue
            
            # Forçar atualização visual do Treeview
            if hasattr(self, 'tree'):
                self.tree.update_idletasks()
                # Reaplicar tags para garantir que as cores sejam atualizadas
                for item in self.tree.get_children():
                    tags = self.tree.item(item, 'tags')
                    self.tree.item(item, tags=tags)
            
            # Forçar atualização geral
            self.update_idletasks()
            
            logging.debug("EventLogFrame theme updated successfully")
            
        except Exception as e:
            logging.error(f"Error updating EventLogFrame theme: {e}")

    def _auto_fetch_logs(self):
        """Busca logs automaticamente na inicialização."""
        logging.debug("Auto-fetching event logs on initialization")
        self.fetch_logs()

    def fetch_logs(self):
        log_name = self.log_name_combo.get()
        level = self.level_combo.get()
        try:
            count = int(self.count_entry.get())
            if count <= 0: raise ValueError
        except ValueError:
            self.app.show_error(self.app.translate("error_invalid_log_count"))
            logging.warning(f"Invalid log count input: {self.count_entry.get()}")
            return
        
        self._clear_display()
        self.tool_controller.get_event_logs(log_name, level, count)

    def update_log_display(self, log_data):
        # Limpar exibição anterior
        self._clear_display()

        # Converter para lista com segurança (pode ser generator)
        try:
            if isinstance(log_data, (list, tuple)):
                self.all_logs = list(log_data)
            elif hasattr(log_data, '__iter__') and log_data is not None:
                # Pode ser generator; converter explicitamente
                self.all_logs = list(log_data)
            else:
                self.all_logs = []
        except Exception as e:
            logging.error(f"Error converting log data to list: {e}")
            self.all_logs = []

        logging.debug(f"Updating UI with {len(self.all_logs)} event logs.")
        if self.all_logs:
            logging.debug(f"First log entry: {self.all_logs[0]}")

        # Popular a tabela
        self._populate_treeview(self.all_logs)

    def display_error(self, message):
        self._clear_display()
        self.details_textbox.configure(state="normal")
        self.details_textbox.insert("1.0", message)
        logging.error(f"Displaying event log error: {message}")
        self.details_textbox.configure(state="disabled")

    def _populate_treeview(self, logs):
        logging.debug(f"_populate_treeview called with {len(logs)} logs")
        
        # Limpar a tabela primeiro
        self.tree.delete(*self.tree.get_children())
        
        for i, log in enumerate(logs):
            logging.debug(f"Processing log {i}: {log}")
            
            time_created_str = log.get("TimeCreated")
            time_str = ""
            if time_created_str:
                try:
                    # Converte a data ISO 8601 para o fuso horário local
                    utc_time = datetime.fromisoformat(time_created_str.rstrip("Z")).replace(tzinfo=timezone.utc)
                    local_time = utc_time.astimezone(tz=None)
                    time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    time_str = time_created_str # Usa o valor original se a conversão falhar
            
            values = (
                time_str,
                log.get("LevelDisplayName", "N/A"),
                log.get("ProviderName", "N/A"),
                log.get("Id", "N/A")
            )
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            # Usar índice numérico como ID para consistência
            item_id = f"log_{i}"  # Prefixo para evitar conflitos
            self.tree.insert("", "end", values=values, iid=item_id, tags=(tag,))
            
        logging.debug(f"Treeview populated with {len(self.tree.get_children())} items")

    def _on_log_select(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        try:
            # Obter o ID do item selecionado
            item_id = selected_item[0]
            
            # Extrair o índice do ID (formato: "log_X")
            if item_id.startswith("log_"):
                try:
                    item_index = int(item_id[4:])  # Remove "log_" e converte para int
                    if item_index >= len(self.all_logs):
                        logging.warning(f"Invalid item index: {item_index}, max: {len(self.all_logs) - 1}")
                        return
                    log_entry = self.all_logs[item_index]
                except (ValueError, TypeError):
                    logging.error(f"Invalid log ID format: {item_id}")
                    return
            else:
                # Fallback: buscar pelos valores (para compatibilidade)
                item_values = self.tree.item(item_id, 'values')
                if not item_values:
                    return
                
                # Buscar o log correspondente pelos valores
                for i, log in enumerate(self.all_logs):
                    time_created_str = log.get("TimeCreated")
                    time_str = ""
                    if time_created_str:
                        try:
                            utc_time = datetime.fromisoformat(time_created_str.rstrip("Z")).replace(tzinfo=timezone.utc)
                            local_time = utc_time.astimezone(tz=None)
                            time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
                        except (ValueError, TypeError):
                            time_str = time_created_str
                    
                    log_values = (
                        time_str,
                        log.get("LevelDisplayName", "N/A"),
                        log.get("ProviderName", "N/A"),
                        log.get("Id", "N/A")
                    )
                    
                    if log_values == item_values:
                        log_entry = log
                        break
                else:
                    # Se não encontrar, usar o primeiro item
                    if self.all_logs:
                        log_entry = self.all_logs[0]
                    else:
                        return
            
            # Exibir detalhes do log
            self.details_textbox.configure(state="normal")
            self.details_textbox.delete("1.0", "end")
            self.details_textbox.insert("1.0", log_entry.get("Message", "Nenhuma mensagem detalhada disponível."))
            self.details_textbox.configure(state="disabled")
            
        except Exception as e:
            logging.error(f"Error selecting log item: {e}")
            # Em caso de erro, exibir mensagem informativa
            self.details_textbox.configure(state="normal")
            self.details_textbox.delete("1.0", "end")
            self.details_textbox.insert("1.0", "Erro ao carregar detalhes do log selecionado.")
            self.details_textbox.configure(state="disabled")

    def _filter_logs(self, event=None):
        filter_term = self.filter_entry.get().lower()
        self.tree.delete(*self.tree.get_children())
        
        if not filter_term:
            filtered_logs = self.all_logs
        else:
            filtered_logs = [
                log for log in self.all_logs
                if filter_term in str(log.get("ProviderName", "")).lower() or \
                   filter_term in str(log.get("Message", "")).lower() or \
                   filter_term in str(log.get("Id", ""))
            ]
        self._populate_treeview(filtered_logs)

    def _clear_display(self):
        self.tree.delete(*self.tree.get_children())
        self.details_textbox.configure(state="normal")
        self.details_textbox.delete("1.0", "end")
        self.details_textbox.configure(state="disabled")
        self.all_logs = []

    def update_language(self):
        self.log_name_label.configure(text=self.app.translate("event_log_log_name"))
        self.level_label.configure(text=self.app.translate("event_log_level"))
        self.count_label.configure(text=self.app.translate("event_log_quantity"))
        self.fetch_button.configure(text=self.app.translate("event_logs_fetch"))
        self.filter_entry.configure(placeholder_text=self.app.translate("event_log_filter_placeholder"))

        # Atualiza os cabeçalhos da tabela
        self.tree.heading("Time", text=self.app.translate("event_log_col_time"))
        self.tree.heading("Level", text=self.app.translate("event_log_col_level"))
        self.tree.heading("Source", text=self.app.translate("event_log_col_source"))
        self.tree.heading("ID", text=self.app.translate("event_log_col_id"))
        
        # Reconfigura o estilo para o caso de mudança de tema (claro/escuro)
        self._configure_styles()