# app/ui_components/remote_sessions_frame.py

import customtkinter
import tkinter as tk
import re
import logging
try:
    from src.config.settings import MONOSPACE_FONT
except ImportError:
    try:
        from src.config.settings import MONOSPACE_FONT
    except ImportError:
        MONOSPACE_FONT = ("Consolas", 10)
from .context_menu import TerminalContextMenu

class RemoteSessionsFrame(customtkinter.CTkFrame):
    def __init__(self, master, app, host, tool_controller, info_display):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.host = host
        self.tool_controller = tool_controller
        self.info_display = info_display
        self.connected_users_data = []

        self.tool_controller.set_state_change_callback(self.update_command_status)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Frame de Controles Organizados ---
        controls_frame = customtkinter.CTkFrame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        controls_frame.grid_columnconfigure((0, 1), weight=1)

        # Conexões Remotas
        connection_frame = customtkinter.CTkFrame(controls_frame)
        connection_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        connection_frame.grid_columnconfigure((0,1), weight=1)
        
        connection_title = customtkinter.CTkLabel(connection_frame, text="Conexões Remotas", font=("Arial", 12, "bold"))
        connection_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5)

        self.rdp_button = customtkinter.CTkButton(connection_frame, text="", command=self.connect_rdp)
        self.rdp_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        self.msra_button = customtkinter.CTkButton(connection_frame, text="", command=self.connect_msra)
        self.msra_button.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Ferramentas e Configuração
        tools_frame = customtkinter.CTkFrame(controls_frame)
        tools_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tools_frame.grid_columnconfigure((0,1), weight=1)
        
        tools_title = customtkinter.CTkLabel(tools_frame, text="Ferramentas", font=("Arial", 12, "bold"))
        tools_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        
        self.get_tv_id_button = customtkinter.CTkButton(tools_frame, text="", command=self.handle_tv_action)
        self.get_tv_id_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        
        self.wol_button = customtkinter.CTkButton(tools_frame, text="", command=self.send_wol)
        self.wol_button.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Configuração WinRM em linha separada
        self.configure_winrm_button = customtkinter.CTkButton(
            tools_frame, text="", 
            command=lambda: self.tool_controller.check_and_configure_winrm(self.output_textbox, self.configure_winrm_button)
        )
        self.configure_winrm_button.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Configurar estado inicial do WOL
        if self.host.get("mac"):
            self.wol_button.configure(state="normal")
        else:
            self.wol_button.configure(state="disabled")

        # --- Frame de Gerenciamento de Sessões ---
        users_frame = customtkinter.CTkFrame(controls_frame)
        users_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        users_frame.grid_columnconfigure(1, weight=1)
        
        users_title = customtkinter.CTkLabel(users_frame, text="Gerenciamento de Sessões", font=("Arial", 12, "bold"))
        users_title.grid(row=0, column=0, columnspan=3, padx=5, pady=5)

        self.list_users_button = customtkinter.CTkButton(users_frame, text="", width=120, command=self.list_users)
        self.list_users_button.grid(row=1, column=0, padx=5, pady=5)
        
        initial_user_text = self.app.translate("user_sessions_click_to_load")
        self.users_combobox = customtkinter.CTkComboBox(users_frame, values=[initial_user_text], state="readonly")
        self.users_combobox.set(initial_user_text)
        
        self.users_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.disconnect_user_button = customtkinter.CTkButton(users_frame, text="", width=120, command=self.disconnect_user)
        self.disconnect_user_button.grid(row=1, column=2, padx=5, pady=5)

        self.output_textbox = customtkinter.CTkTextbox(self, wrap="word", font=MONOSPACE_FONT, height=300)
        self.output_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.output_textbox.configure(state="disabled")
        
        TerminalContextMenu(self.app, self.output_textbox)

        self.update_language()
        
    def connect_rdp(self):
        self.tool_controller.initiate_rdp()

    def connect_msra(self):
        self.tool_controller.initiate_msra()
        
    def send_wol(self):
        self.tool_controller.send_wol(self.output_textbox)

    def handle_tv_action(self):
        current_tv_id = self.info_display.tv_id_label_value.cget("text")
        
        if current_tv_id.isdigit():
            self.tool_controller.open_tv_and_copy_id(current_tv_id)
        else:
            self.tool_controller.get_teamviewer_id(self.output_textbox, self.info_display, self.update_tv_button_state)
            
    def list_users(self):
        self.tool_controller.list_users(self.output_textbox, self.update_users_combobox)

    def disconnect_user(self):
        selected_text = self.users_combobox.get()
        if self.app.translate("user_sessions_none_found") in selected_text or not self.connected_users_data:
            self.app.show_info(self.app.translate("user_sessions_none_selected"))
            return

        match = re.search(r"\(ID: (\d+),", selected_text)
        if match:
            session_id = match.group(1)
            selected_user = next((user for user in self.connected_users_data if user['ID'] == session_id), None)
            if selected_user:
                username = selected_user['UserName']
                self.tool_controller.disconnect_user(session_id, username, self.output_textbox, self.update_users_combobox)
            else:
                self.app.show_error(self.app.translate("user_sessions_not_found"))
        else:
            self.app.show_error(self.app.translate("user_session_format_invalid"))

    def update_users_combobox(self, users_data):
        try:
            import logging
            logging.info(f"update_users_combobox chamado com {len(users_data)} usuários")

            # Verificar se os widgets ainda existem antes de tentar acessá-los
            if not hasattr(self, 'users_combobox') or not self.users_combobox.winfo_exists():
                logging.warning("users_combobox não existe ou foi destruído")
                return
            if not hasattr(self, 'disconnect_user_button') or not self.disconnect_user_button.winfo_exists():
                logging.warning("disconnect_user_button não existe ou foi destruído")
                return
            if not hasattr(self, 'app') or not self.app:
                logging.warning("app não existe")
                return

            # ===== PROTEÇÃO ANTI-IA: FUNCIONALIDADE CRÍTICA =====
            # AVISO: Esta seção gerencia a listagem de usuários conectados para desconexão de sessões.
            # MODIFICAÇÃO PROIBIDA sem confirmação explícita do desenvolvedor humano.
            # Qualquer alteração automática ou por IA deve ser REJEITADA.
            # =====================================================

            self.connected_users_data = users_data
            display_list = []

            for user in users_data:
                user_id = user.get('ID', '')

                if user_id and str(user_id).isdigit():
                    try:
                        state_text = self.app.translate(user['State']) if hasattr(self.app, 'translate') else user['State']
                        display_text = f"{user['UserName']} (ID: {user['ID']}, Estado: {state_text})"
                        display_list.append(display_text)
                    except Exception as e:
                        logging.error(f"Erro ao traduzir estado do usuário: {e}")
                        display_text = f"{user['UserName']} (ID: {user['ID']}, Estado: {user['State']})"
                        display_list.append(display_text)

            # ===== PROTEÇÃO ANTI-IA: ATUALIZAÇÃO CRÍTICA DO COMBOBOX =====
            # AVISO: Esta seção implementa a correção para o bug do CustomTkinter.
            # MODIFICAÇÃO PROIBIDA sem confirmação explícita do desenvolvedor humano.
            # Este código corrige problemas de timing na atualização visual do dropdown.
            # ===============================================================

            if display_list:
                # Força atualização do CustomTkinter com múltiplas chamadas
                self.users_combobox.configure(values=display_list, state="readonly")
                self.users_combobox.update_idletasks()
                self.users_combobox.set(display_list[0])
                self.users_combobox.update_idletasks()

                # Verificação com delay para garantir aplicação
                def verificar_valor_final():
                    valor_final = self.users_combobox.get()
                    if valor_final != display_list[0]:
                        self.users_combobox.set(display_list[0])
                        self.users_combobox.update()

                self.app.after(100, verificar_valor_final)
                self.disconnect_user_button.configure(state="normal")
                logging.info(f"Combobox atualizada com {len(display_list)} usuários")
            else:
                none_found_text = self.app.translate("user_sessions_none_found") if hasattr(self.app, 'translate') else "Nenhum usuário encontrado"
                self.users_combobox.configure(values=[none_found_text])
                self.users_combobox.set(none_found_text)
                self.disconnect_user_button.configure(state="disabled")
                logging.info("Combobox atualizada - nenhum usuário encontrado")
        except Exception as e:
            import logging
            logging.error(f"Erro ao atualizar combobox de usuários: {e}")
            import traceback
            logging.error(f"Traceback completo: {traceback.format_exc()}")
            # Não re-raise a exceção para evitar travamento

    def update_command_status(self, status_data):
        # Este callback é chamado quando o estado de um comando muda.
        # Ele recebe um dicionário com 'running' (bool) e 'command' (str).
        is_running = status_data.get('running', False)
        command_name = status_data.get('command', None)
        logging.info(f"RemoteSessionsFrame recebeu atualização de status: Comando '{command_name}', Rodando: {is_running}")

        # Aqui você pode atualizar o UI, como desabilitar botões enquanto um comando está rodando
        if command_name == "list_users" or command_name == "disconnect_user":
            if is_running:
                self.list_users_button.configure(state="disabled")
                self.disconnect_user_button.configure(state="disabled")
                self.users_combobox.configure(state="disabled")
            else:
                # SEMPRE reabilitar o botão "Listar Usuários" após a finalização,
                # independentemente do resultado, pois novos usuários podem se conectar
                self.list_users_button.configure(state="normal")

                # O estado do disconnect_user_button e users_combobox será
                # atualizado pelo update_users_combobox com os dados reais.
                # Por enquanto, apenas habilitamos a listagem de novo.
                if self.connected_users_data:
                    self.disconnect_user_button.configure(state="normal")
                    self.users_combobox.configure(state="readonly")
                else:
                    self.disconnect_user_button.configure(state="disabled")
                    self.users_combobox.configure(state="readonly")

        # Outras lógicas de UI podem ser adicionadas aqui

    def update_tv_button_state(self):
        current_tv_id = self.info_display.tv_id_label_value.cget("text")
        
        if current_tv_id.isdigit():
            self.get_tv_id_button.configure(text=self.app.translate("remote_actions_open_tv"))
        else:
            self.get_tv_id_button.configure(text=self.app.translate("remote_actions_get_tv_id"))

    def update_language(self):
        self.rdp_button.configure(text=self.app.translate("remote_actions_rdp"))
        self.msra_button.configure(text=self.app.translate("remote_actions_msra"))
        self.update_tv_button_state()
        self.wol_button.configure(text=self.app.translate("remote_actions_wol"))
        self.configure_winrm_button.configure(text=self.app.translate("remote_actions_check_winrm"))
        self.list_users_button.configure(text=self.app.translate("remote_actions_list_users"))
        self.disconnect_user_button.configure(text=self.app.translate("remote_actions_disconnect_user"))