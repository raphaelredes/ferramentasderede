# src/ferramentasderede/ui/components/credential_dialog.py

import customtkinter
import os
from .base_dialog import BaseDialog
import logging
from .vault_prompt_dialog import VaultPromptDialog
from .custom_dialogs import PasswordInputDialog
from .credential_service import SALT_FILE

class CredentialDialog(BaseDialog):
    def __init__(self, app, target_server_ip, default_domain, cred_service=None):
        logging.info(f"Opening credential dialog for target: {target_server_ip}")
        # Timeout de 30 segundos para diálogo de credenciais
        super().__init__(app, title=app.translate("credentials_title"), timeout_seconds=30)
        self.cred_service = cred_service
        self._user_input = (None, None)
        
        self.default_domain = default_domain
        
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)

        message_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("credentials_message", target=target_server_ip), wraplength=460)
        message_label.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        self.saved_cred_combo = None
        
        # --- Campos de Entrada (Criados ANTES da lógica que os utiliza) ---
        user_domain_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        user_domain_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        user_domain_frame.grid_columnconfigure((0, 1), weight=1)

        self.user_label = customtkinter.CTkLabel(user_domain_frame, text=self.app.translate("ui_user"), anchor="w")
        self.user_label.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.user_entry = customtkinter.CTkEntry(user_domain_frame)
        self.user_entry.grid(row=1, column=0, padx=(0, 10), sticky="ew")
        self.user_entry.bind("<Return>", self._ok_event)
        self.user_entry.bind("<Key>", lambda e: self.set_manual_entry())

        self.domain_label = customtkinter.CTkLabel(user_domain_frame, text=self.app.translate("ui_domain"), anchor="w")
        self.domain_label.grid(row=0, column=1, padx=(10, 0), sticky="ew")
        self.domain_entry = customtkinter.CTkEntry(user_domain_frame)
        self.domain_entry.insert(0, self.default_domain)
        self.domain_entry.grid(row=1, column=1, padx=(10, 0), sticky="ew")
        self.domain_entry.bind("<Return>", self._ok_event)
        self.domain_entry.bind("<Key>", lambda e: self.set_manual_entry())

        self.password_label = customtkinter.CTkLabel(main_frame, text=self.app.translate("ui_password"), anchor="w")
        self.password_label.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        
        self.password_entry = customtkinter.CTkEntry(main_frame, show="*")
        self.password_entry.grid(row=5, column=0, sticky="ew")
        self.password_entry.bind("<Return>", self._ok_event)
        self.password_entry.bind("<Key>", lambda e: self.set_manual_entry())

        # --- Credenciais Salvas (Lógica executada DEPOIS da criação dos campos) ---
        if self.cred_service and self.cred_service.is_unlocked():
            saved_identifiers = self.cred_service.get_all_aliases()
            if saved_identifiers:
                label_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
                label_frame.grid(row=1, column=0, sticky="ew")
                label_frame.grid_columnconfigure(0, weight=1)
                saved_cred_label = customtkinter.CTkLabel(label_frame, text=self.app.translate("vault_use_saved_credential"))
                saved_cred_label.grid(row=0, column=0, sticky="w")
                help_button = customtkinter.CTkButton(label_frame, text=self.app.translate("label_help_short"), width=25, height=25, font=customtkinter.CTkFont(size=16), fg_color="transparent", command=self.app.show_security_info_dialog)
                help_button.grid(row=0, column=1, sticky="e")

                display_options = [self.app.translate("vault_manual_entry")] + saved_identifiers
                self.saved_cred_combo = customtkinter.CTkComboBox(main_frame, values=display_options, command=self.on_saved_cred_select)
                self.saved_cred_combo.grid(row=2, column=0, sticky="ew", pady=(0, 15))
                
                identifier_to_select = None
                last_used = self.app.last_used_creds_by_domain.get(self.default_domain.lower())
                if last_used and last_used in saved_identifiers:
                    identifier_to_select = last_used
                else:
                    domain_creds = [s for s in saved_identifiers if s.lower().startswith(self.default_domain.lower() + "\\")]
                    if len(domain_creds) == 1:
                        identifier_to_select = domain_creds[0]
                
                if identifier_to_select:
                    self.saved_cred_combo.set(identifier_to_select)
                    self.on_saved_cred_select(identifier_to_select)
                else:
                    self.saved_cred_combo.set(self.app.translate("vault_manual_entry"))

        # --- Botões de Ação ---
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="e", padx=20, pady=(10, 20))

        self.ok_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_confirm"), command=self._ok_event)
        self.ok_button.pack(side="left", padx=(0, 5))

        self.cancel_button = customtkinter.CTkButton(button_frame, text=self.app.translate("label_cancel"), command=self._cancel_event, fg_color="gray50")
        self.cancel_button.pack(side="left")
        
        self.bind("<Escape>", self._cancel_event)
        self.after(100, lambda: self.user_entry.focus())

    def set_manual_entry(self):
        """Updates the ComboBox to 'Manual Entry' if the user types."""
        if self.saved_cred_combo:
            self.saved_cred_combo.set(self.app.translate("vault_manual_entry"))
            logging.debug("Set credential combo to manual entry due to user typing.")

    def on_saved_cred_select(self, selected_identifier):
        """Carrega a credencial selecionada ou limpa os campos para entrada manual."""
        logging.info(f"Credential combo selected: {selected_identifier}")
        if selected_identifier == self.app.translate("vault_manual_entry"):
            self.user_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            self.domain_entry.delete(0, "end")
            self.domain_entry.insert(0, self.default_domain)
            self.user_entry.focus()
            return

        if self.cred_service:
            logging.debug(f"Attempting to get credential for alias: {selected_identifier}")
            cred_data = self.cred_service.get_credential(selected_identifier)
            if cred_data:
                logging.debug("Credential data retrieved successfully.")
                # Do NOT log the password

                password = cred_data.get("password", "")
                user_part, domain_part = selected_identifier, ""
                if "\\" in selected_identifier:
                    domain_part, user_part = selected_identifier.split("\\", 1)
                self.user_entry.delete(0, "end"); self.user_entry.insert(0, user_part)
                self.domain_entry.delete(0, "end"); self.domain_entry.insert(0, domain_part)
                self.password_entry.delete(0, "end"); self.password_entry.insert(0, password)
                self.password_entry.focus()
            else:
                logging.warning(f"Credential data not found for alias: {selected_identifier}")

    def _ok_event(self, event=None):
        domain, username, password = self.domain_entry.get().strip(), self.user_entry.get().strip(), self.password_entry.get()
        if not username:
            logging.warning("Input validation failed: Username is empty.")
            self.app.show_error(self.app.translate("error_user_empty"), widget_to_focus=self.user_entry)
            return

        full_username = f"{domain}\\{username}" if domain else username
        self._user_input = (full_username, password)
        
        is_manual_entry = self.saved_cred_combo is None or self.saved_cred_combo.get() == self.app.translate("vault_manual_entry")

        if is_manual_entry:
            cred_service = self.app.cred_service
            salt_file_path = os.path.join(self.app.base_dir, SALT_FILE)
            logging.debug(f"Manual entry used. Salt file path: {salt_file_path}")

            if cred_service.is_unlocked():
                logging.debug("Credential service is unlocked.")
                # Caso 1: Cofre já existe e está desbloqueado. Pergunta se quer salvar.
                logging.info(f"Prompting user to save credential for {full_username}.")
                if self.app.ask_yes_no(self.app.translate("vault_save_credential_title"), self.app.translate("vault_save_credential_prompt", user=full_username)):
                    logging.info(f"User chose to save credential for {full_username}. Attempting to add/update.")
                    cred_service.add_or_update_credential(alias=full_username, username=full_username, password=password)
                    logging.info(f"Credential saved successfully for {full_username}.")
                    self.app.show_toast_notification(self.app.translate("vault_credential_saved", user=full_username))

            elif not os.path.exists(salt_file_path) and not self.app.vault_prompt_decision_made:
                # Caso 2: Cofre não existe E o usuário ainda não foi perguntado nesta sessão.
                logging.info("Credential vault does not exist and user hasn't been prompted this session. Showing vault prompt dialog.")
                self.app.vault_prompt_decision_made = True  # Marcar que a pergunta foi feita.

                prompt_dialog = VaultPromptDialog(self.app)
                prompt_dialog.wait()
                logging.info(f"Vault prompt dialog result: {prompt_dialog.get_result()}")
                if prompt_dialog.get_result():  # Usuário disse SIM para criar o cofre.
                    title, prompt = self.app.translate("vault_create_title"), self.app.translate("vault_create_prompt")
                    pwd_dialog = PasswordInputDialog(self.app, title, prompt)
                    master_password = pwd_dialog.get_input()

                    if master_password:
                        if cred_service.unlock(master_password):
                            logging.info("Credential vault unlocked successfully after creation.")
                            # Cofre criado com sucesso, salva a credencial atual diretamente.
                            logging.info(f"Attempting to save credential for {full_username} after vault creation.")
                            cred_service.add_or_update_credential(alias=full_username, username=full_username, password=password)
                            logging.info(f"Credential saved successfully after vault creation for {full_username}.")
                            self.app.show_toast_notification(self.app.translate("vault_credential_saved", user=full_username))
                        else:
                            logging.error("Failed to unlock credential vault after creation.")
                    else:
                        logging.info("Master password not provided for vault creation.")

        if domain:
            logging.debug(f"Storing last used credential for domain {domain.lower()}: {full_username}")
            self.app.last_used_creds_by_domain[domain.lower()] = full_username
        logging.info(f"Credential dialog confirmed for user: {full_username}")
        self._dialog_result = self._user_input
        self.destroy()

    def _cancel_event(self, event=None):
        logging.info("Credential dialog cancelled.")
        self._user_input = (None, None)
        self._dialog_result = self._user_input
        self.destroy()

    def get_input(self):
        self.wait_with_timeout()
        return self._user_input