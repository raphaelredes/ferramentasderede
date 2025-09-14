# src/ferramentasderede/ui/components/credential_manager_dialog.py
# Janela para gerenciar credenciais salvas.

import customtkinter
import logging
from .base_dialog import BaseDialog

class CredentialManagerDialog(BaseDialog):
    def __init__(self, app, cred_service):
        super().__init__(app=app, title=app.translate("actions_manage_creds"))
        self.cred_service = cred_service
        self.current_edit_alias = None
        logging.info("CredentialManagerDialog opened.")

        # Definir tamanho mínimo adequado para o conteúdo
        self.minsize(650, 450)
        self.bind("<Escape>", self.destroy)

        main_frame = customtkinter.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=2, minsize=200)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # --- Frame da Esquerda (Lista e Ações) ---
        left_frame = customtkinter.CTkFrame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        list_label = customtkinter.CTkLabel(left_frame, text=self.app.translate("vault_saved_credentials"))
        list_label.grid(row=0, column=0, sticky="w", pady=(10, 5), padx=10)

        # Adicionar ícone de ajuda
        help_button = customtkinter.CTkButton(
            left_frame, 
            text="?", 
            width=25, 
            height=25,
            command=self.show_credentials_help,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40")
        )
        help_button.grid(row=0, column=1, sticky="e", pady=(10, 5), padx=(0, 10))

        self.aliases_listbox = customtkinter.CTkScrollableFrame(left_frame)
        self.aliases_listbox.grid(row=1, column=0, sticky="nsew", padx=10)
        self.alias_radio_buttons = []
        self.selected_alias_var = customtkinter.StringVar(value="")

        actions_frame = customtkinter.CTkFrame(left_frame, fg_color="transparent")
        actions_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        actions_frame.grid_columnconfigure(0, weight=1)

        self.add_button = customtkinter.CTkButton(actions_frame, text=self.app.translate("vault_add_new_credential"), command=self.show_add_new_view)
        self.add_button.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.remove_button = customtkinter.CTkButton(actions_frame, text=self.app.translate("vault_remove_selected"), command=self.remove_selected, fg_color="red")
        self.remove_button.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        
        self.change_pass_button = customtkinter.CTkButton(actions_frame, text=self.app.translate("vault_change_master_password"), command=self.show_change_password_view)
        self.change_pass_button.grid(row=2, column=0, sticky="ew")
        
        # --- Frame da Direita (Detalhes ou Adicionar Novo) ---
        self.right_frame = customtkinter.CTkFrame(main_frame)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.populate_aliases_list()
        self.check_view_state()

    def check_view_state(self):
        """Verifica se há credenciais e mostra a view apropriada (detalhes ou adicionar)."""
        aliases = self.cred_service.get_all_aliases()
        if not aliases:
            logging.info("No saved credentials found. Showing add new credential view.")
            self.show_add_new_view()
        else:
            if not self.selected_alias_var.get() or self.selected_alias_var.get() not in aliases:
                first_alias = aliases[0]
                self.selected_alias_var.set(first_alias)
            self.show_details_view()

    def clear_right_frame(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()

    def show_details_view(self):
        self.clear_right_frame()
        logging.info(f"Showing details view for alias: {self.selected_alias_var.get()}")
        self.right_frame.grid_rowconfigure(5, weight=1)

        details_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_credential_details"), font=("", 14, "bold"))
        details_label.grid(row=0, column=0, sticky="w", pady=(15, 20), padx=20)
        
        identifier_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_identifier_user"))
        identifier_label.grid(row=1, column=0, sticky="w", padx=20)
        self.identifier_value = customtkinter.CTkLabel(self.right_frame, text="", anchor="w", fg_color=("gray85", "gray17"), corner_radius=6)
        self.identifier_value.grid(row=2, column=0, sticky="ew", pady=(5, 15), ipady=5, padx=20)
        
        pass_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_saved_password"))
        pass_label.grid(row=3, column=0, sticky="w", padx=20)
        self.pass_value = customtkinter.CTkLabel(self.right_frame, text="", anchor="w", fg_color=("gray85", "gray17"), corner_radius=6)
        self.pass_value.grid(row=4, column=0, sticky="ew", pady=(5, 15), ipady=5, padx=20)
        
        self.edit_button = customtkinter.CTkButton(self.right_frame, text=self.app.translate("label_edit"), command=self.show_edit_view)
        self.edit_button.grid(row=5, column=0, sticky="ew", padx=20, pady=10)

        self.load_alias_details()
        self.remove_button.configure(state="normal")

    def show_add_new_view(self):
        self.clear_right_frame()
        logging.info("Showing add new credential view.")
        self.selected_alias_var.set("")
        self.current_edit_alias = None
        self._setup_edit_view(is_new=True)

    def show_edit_view(self):
        self.clear_right_frame()
        self.current_edit_alias = self.selected_alias_var.get()
        cred_data = self.cred_service.get_credential(self.current_edit_alias)
        logging.info(f"Showing edit view for alias: {self.current_edit_alias}")

        if not cred_data:
            logging.error(f"Credential '{self.current_edit_alias}' not found for editing.")
            self.check_view_state()
            self.app.show_error(self.app.translate("vault_error_credential_not_found", alias=self.current_edit_alias))
            return
            
        self._setup_edit_view(is_new=False, cred_data=cred_data)

    def _setup_edit_view(self, is_new, cred_data=None):
        self.right_frame.grid_rowconfigure(8, weight=1)

        logging.debug(f"Setting up {'new' if is_new else 'edit'} credential view.")
        title_key = "vault_add_new_credential" if is_new else "vault_credential_details"
        add_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate(title_key), font=("", 14, "bold"))
        add_label.grid(row=0, column=0, sticky="w", pady=(15, 20), padx=20)

        user_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("ui_user"))
        user_label.grid(row=1, column=0, sticky="w", padx=20)
        self.new_user_entry = customtkinter.CTkEntry(self.right_frame)
        self.new_user_entry.grid(row=2, column=0, sticky="ew", pady=(5, 10), padx=20)
        
        domain_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("ui_domain_optional"))
        domain_label.grid(row=3, column=0, sticky="w", padx=20)
        self.new_domain_entry = customtkinter.CTkEntry(self.right_frame)
        self.new_domain_entry.grid(row=4, column=0, sticky="ew", pady=(5, 10), padx=20)
        
        pass_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("ui_password"))
        pass_label.grid(row=5, column=0, sticky="w", padx=20)
        self.new_pass_entry = customtkinter.CTkEntry(self.right_frame, show="*")
        self.new_pass_entry.grid(row=6, column=0, sticky="ew", pady=(5, 15), padx=20)

        if cred_data:
            # CORREÇÃO: Usa o alias (chave) como fonte segura para extrair domínio e usuário
            alias_to_parse = self.current_edit_alias
            password = cred_data.get('password', '')
            domain, user = "", alias_to_parse
            
            if "\\" in alias_to_parse:
                domain, user = alias_to_parse.split("\\", 1)
            
            self.new_user_entry.insert(0, user)
            self.new_domain_entry.insert(0, domain)
            self.new_pass_entry.insert(0, password)

        button_frame = customtkinter.CTkFrame(self.right_frame, fg_color="transparent")
        button_frame.grid(row=7, column=0, padx=20, pady=10)

        if is_new:
            save_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_save"), command=self.save_new_credential)
            save_button.pack()
        else:
            save_edit_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_save"), command=self._confirm_edit_changes)
            save_edit_button.pack(side="left", padx=5)
            cancel_edit_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_cancel"), command=self.check_view_state, fg_color="gray50")
            cancel_edit_button.pack(side="left", padx=5)

        for entry in [self.new_user_entry, self.new_domain_entry, self.new_pass_entry]:
            entry.bind("<Return>", self.save_new_credential if is_new else self._confirm_edit_changes)
            
        self.remove_button.configure(state="disabled" if is_new else "normal")

    def show_change_password_view(self):
        self.clear_right_frame()
        logging.info("Showing change master password view.")
        self.right_frame.grid_rowconfigure(9, weight=1)
        
        title_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_change_master_password"), font=("", 14, "bold"))
        title_label.grid(row=0, column=0, sticky="w", pady=(15, 20), padx=20)
        
        # Seção da senha atual
        current_pass_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_current_password"))
        current_pass_label.grid(row=1, column=0, sticky="w", pady=(5,0), padx=20)
        self.current_pass_entry = customtkinter.CTkEntry(self.right_frame, show="*")
        self.current_pass_entry.grid(row=2, column=0, sticky="ew", pady=(5,15), padx=20)
        
        # Separador visual
        separator = customtkinter.CTkFrame(self.right_frame, height=2, fg_color=("gray70", "gray30"))
        separator.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 15))
        
        # Seção da nova senha
        new_section_label = customtkinter.CTkLabel(self.right_frame, text="Nova Senha Mestra", font=("", 12, "bold"))
        new_section_label.grid(row=4, column=0, sticky="w", pady=(0, 10), padx=20)
        
        new_pass_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_new_password"))
        new_pass_label.grid(row=5, column=0, sticky="w", padx=20)
        self.new_pass_entry_change = customtkinter.CTkEntry(self.right_frame, show="*")
        self.new_pass_entry_change.grid(row=6, column=0, sticky="ew", pady=(5,10), padx=20)
        
        confirm_pass_label = customtkinter.CTkLabel(self.right_frame, text=self.app.translate("vault_confirm_new_password"))
        confirm_pass_label.grid(row=7, column=0, sticky="w", padx=20)
        self.confirm_pass_entry = customtkinter.CTkEntry(self.right_frame, show="*")
        self.confirm_pass_entry.grid(row=8, column=0, sticky="ew", pady=(5,15), padx=20)
        
        button_frame = customtkinter.CTkFrame(self.right_frame, fg_color="transparent")
        button_frame.grid(row=9, column=0, padx=20, pady=10)
        confirm_button = customtkinter.CTkButton(button_frame, text=self.app.translate("vault_confirm_change"), command=self._confirm_password_change)
        confirm_button.pack(side="left", padx=5)
        cancel_button = customtkinter.CTkButton(button_frame, text=self.app.translate("vault_cancel_change"), command=self.check_view_state, fg_color="gray50")
        cancel_button.pack(side="left", padx=5)

    def _confirm_password_change(self):
        current_pass, new_pass, confirm_pass = self.current_pass_entry.get(), self.new_pass_entry_change.get(), self.confirm_pass_entry.get()
        
        # Validações básicas
        if not current_pass:
            self.app.show_error("Senha atual é obrigatória")
            return
            
        if not new_pass:
            logging.warning("Attempted to change master password with empty new password.")
            self.app.show_error(self.app.translate("vault_error_new_password_empty"))
            return
            
        if new_pass != confirm_pass:
            logging.warning("Attempted to change master password, new passwords mismatch.")
            self.app.show_error(self.app.translate("vault_error_new_passwords_mismatch"))
            return
        
        # Tentar alterar a senha
        success, message = self.cred_service.change_master_password(current_pass, new_pass)
        if success:
            logging.info("Master password changed successfully.")
            self.app.show_toast_notification(self.app.translate("vault_success_password_changed"))
            # Limpar campos
            self.current_pass_entry.delete(0, "end")
            self.new_pass_entry_change.delete(0, "end")
            self.confirm_pass_entry.delete(0, "end")
            self.check_view_state()
        else:
            self.app.show_error(message)

    def populate_aliases_list(self):
        for widget in self.aliases_listbox.winfo_children(): widget.destroy()
        self.alias_radio_buttons.clear()
        logging.info("Populating aliases list.")
        for alias in self.cred_service.get_all_aliases():
            rb = customtkinter.CTkRadioButton(self.aliases_listbox, text=alias, variable=self.selected_alias_var, value=alias, command=self.show_details_view)
            rb.pack(anchor="w", padx=5, pady=2)
            self.alias_radio_buttons.append(rb)

    def load_alias_details(self):
        alias = self.selected_alias_var.get()
        if not alias: return
        logging.debug(f"Loading details for alias: {alias}")
        cred = self.cred_service.get_credential(alias)
        if cred:
            self.identifier_value.configure(text=f"  {alias}")
            self.pass_value.configure(text=f"  {'*' * 10}")

    def remove_selected(self):
        alias = self.selected_alias_var.get()
        if not alias:
            logging.warning("Attempted to remove credential but no alias was selected.")
            self.app.show_info(self.app.translate("vault_no_credential_selected"))
            return
        logging.info(f"Attempting to remove credential: {alias}")
        if self.app.ask_yes_no(self.app.translate("title_confirm_action"), self.app.translate("vault_confirm_remove_prompt", alias=alias)):
            try:
                self.cred_service.delete_credential(alias)
                logging.info(f"Credential removed successfully: {alias}")
                self.selected_alias_var.set("")
                self.populate_aliases_list()
                self.check_view_state()
                self.app.show_toast_notification(self.app.translate("vault_credential_removed", alias=alias))
            except Exception as e:
                logging.error(f"Error removing credential {alias}: {e}", exc_info=True)
                self.app.show_error(f"Erro ao remover credencial {alias}: {e}") # Provide some feedback to user

    def save_new_credential(self, event=None):
        user, domain, password = self.new_user_entry.get().strip(), self.new_domain_entry.get().strip(), self.new_pass_entry.get()
        if not user:
            logging.warning("Attempted to save new credential with empty username.")
            self.app.show_error(self.app.translate("error_user_empty"), widget_to_focus=self.new_user_entry)
            return
        alias = f"{domain}\\{user}" if domain else user
        logging.info(f"Attempting to save new credential with alias: {alias}")
        # CORREÇÃO: Garante que o 'username' salvo seja o alias completo
        self.cred_service.add_or_update_credential(alias, alias, password)
        logging.info(f"New credential saved successfully: {alias}")
        self.app.show_toast_notification(self.app.translate("vault_credential_saved", user=alias))
        self.populate_aliases_list()
        self.selected_alias_var.set(alias)
        self.check_view_state()

    def _confirm_edit_changes(self, event=None):
        user, domain, password = self.new_user_entry.get().strip(), self.new_domain_entry.get().strip(), self.new_pass_entry.get() # Passwords shouldn't be logged
        if not user:
            logging.warning("Attempted to save edited credential with empty username.")
            self.app.show_error(self.app.translate("error_user_empty"), widget_to_focus=self.new_user_entry)
            return
        new_alias = f"{domain}\\{user}" if domain else user
        logging.info(f"Attempting to save edited credential from '{self.current_edit_alias}' to '{new_alias}'")
        if new_alias != self.current_edit_alias:
            logging.debug(f"Alias changed. Deleting old credential: {self.current_edit_alias}")
            self.cred_service.delete_credential(self.current_edit_alias)

        # CORREÇÃO: Garante que o 'username' salvo seja o alias completo
        self.cred_service.add_or_update_credential(new_alias, new_alias, password)
        self.app.show_toast_notification(self.app.translate("vault_credential_saved", user=new_alias))
        
        self.populate_aliases_list()
        self.selected_alias_var.set(new_alias)
        self.check_view_state()

    def show_credentials_help(self):
        """Mostra uma janela de ajuda explicando como o sistema de credenciais funciona."""
        help_text = """
🔐 **Sistema de Credenciais Seguras**

**Como funciona:**
• Suas credenciais são criptografadas com uma senha mestra
• A senha mestra nunca é salva - você deve digitá-la sempre que abrir a aplicação
• As credenciais ficam salvas localmente no seu computador
• Todas as senhas são apagadas da memória ao sair da aplicação

**Segurança:**
• Criptografia AES-256 com salt único
• 480.000 iterações de derivação de chave (PBKDF2)
• Senha mestra nunca armazenada em disco
• Backup automático antes de modificações

**Uso:**
• Adicione credenciais para hosts que você acessa frequentemente
• A aplicação usará automaticamente as credenciais salvas
• Você pode editar ou remover credenciais a qualquer momento

**Dicas:**
• Use uma senha mestra que você consiga lembrar
• Nunca compartilhe sua senha mestra
• Faça backup dos arquivos de credenciais se necessário
        """
        
        # Criar janela de ajuda
        help_window = customtkinter.CTkToplevel(self)
        help_window.title("Ajuda - Sistema de Credenciais")
        help_window.geometry("500x400")
        help_window.resizable(False, False)
        help_window.transient(self)
        help_window.grab_set()
        
        # Centralizar no monitor da aplicação principal
        if hasattr(self.app, 'center_popup_on_main_window'):
            self.app.center_popup_on_main_window(help_window, 500, 400)
        
        # Centralizar na janela pai (fallback)
        help_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (help_window.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (help_window.winfo_height() // 2)
        help_window.geometry(f"+{x}+{y}")
        
        # Frame principal
        main_frame = customtkinter.CTkFrame(help_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Título
        title_label = customtkinter.CTkLabel(
            main_frame, 
            text="Sistema de Credenciais", 
            font=("", 16, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Texto de ajuda
        help_textbox = customtkinter.CTkTextbox(main_frame, wrap="word")
        help_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 20))
        help_textbox.insert("1.0", help_text)
        help_textbox.configure(state="disabled")
        
        # Botão fechar
        close_button = customtkinter.CTkButton(
            main_frame, 
            text="Fechar", 
            command=help_window.destroy
        )
        close_button.pack(pady=(0, 10))
        
        # Focar na janela de ajuda
        help_window.focus_set()