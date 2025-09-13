# src/ferramentasderede/ui/components/credential_service.py
# Lida com a criptografia, salvamento e carregamento de credenciais.

import json
import base64
import os
import hashlib
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
import customtkinter

from .custom_dialogs import PasswordInputDialog

CRED_FILE = "credentials.json.enc"
SALT_FILE = "csalt.key"
BACKUP_SUFFIX = ".backup"

class CredentialService:
    def __init__(self, base_dir):
        self.key = None
        self.credentials = {}
        self.salt = None
        self.cred_file_path = os.path.join(base_dir, CRED_FILE)
        self.salt_file_path = os.path.join(base_dir, SALT_FILE)
        self.backup_file_path = os.path.join(base_dir, CRED_FILE + BACKUP_SUFFIX)
        self._failed_attempts = 0
        self._max_failed_attempts = 5

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Deriva uma chave criptográfica da senha usando PBKDF2."""
        if not password:
            raise ValueError("Senha não pode estar vazia")
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # Alto número de iterações para segurança
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

    def _create_backup(self):
        """Cria um backup do arquivo de credenciais antes de modificações."""
        if os.path.exists(self.cred_file_path):
            try:
                import shutil
                shutil.copy2(self.cred_file_path, self.backup_file_path)
                logging.info("Backup do arquivo de credenciais criado")
            except Exception as e:
                logging.warning(f"Falha ao criar backup: {e}")

    def _restore_backup(self):
        """Restaura o backup em caso de erro."""
        if os.path.exists(self.backup_file_path):
            try:
                import shutil
                shutil.copy2(self.backup_file_path, self.cred_file_path)
                logging.info("Backup restaurado com sucesso")
                return True
            except Exception as e:
                logging.error(f"Falha ao restaurar backup: {e}")
        return False

    def unlock(self, password: str) -> bool:
        """Desbloqueia o cofre de credenciais ou cria um novo."""
        logging.info("Attempting to unlock credential vault.")
        
        # Verificar tentativas falhadas
        if self._failed_attempts >= self._max_failed_attempts:
            logging.warning("Máximo de tentativas de desbloqueio excedido")
            return False
        
        try:
            # Criar novo cofre se não existir
            if not os.path.exists(self.salt_file_path):
                logging.info("Salt file not found, creating new vault.")
                self.salt = secrets.token_bytes(32)  # Salt mais longo para maior segurança
                with open(self.salt_file_path, "wb") as f:
                    f.write(self.salt)
                self.key = self._derive_key(password, self.salt)
                self.credentials = {}
                self.save_credentials()
                logging.info("New vault created and unlocked successfully.")
                return True
            
            # Desbloquear cofre existente
            logging.debug("Salt file found, attempting to decrypt existing vault.")
            with open(self.salt_file_path, "rb") as f:
                self.salt = f.read()
            
            derived_key = self._derive_key(password, self.salt)
            
            # Verificar se o arquivo de credenciais existe
            if not os.path.exists(self.cred_file_path):
                logging.error("Credential file not found")
                self._failed_attempts += 1
                return False
            
            with open(self.cred_file_path, "rb") as f:
                encrypted_data = f.read()
            
            if not encrypted_data:
                logging.error("Credential file is empty")
                self._failed_attempts += 1
                return False
            
            f_suite = Fernet(derived_key)
            decrypted_data = f_suite.decrypt(encrypted_data)
            self.credentials = json.loads(decrypted_data.decode('utf-8'))
            self.key = derived_key
            self._failed_attempts = 0  # Reset contador de tentativas
            logging.info("Credential vault unlocked successfully.")
            return True
            
        except Exception as e:
            self._failed_attempts += 1
            logging.error(f"Failed to unlock credential vault (attempt {self._failed_attempts}): {e}")
            return False

    def is_unlocked(self):
        """Verifica se o cofre está desbloqueado."""
        return self.key is not None

    def lock(self):
        """Bloqueia o cofre e limpa dados sensíveis da memória."""
        self.key = None
        self.credentials.clear()
        self.salt = None
        self._failed_attempts = 0
        logging.info("Credential vault locked")

    def save_credentials(self):
        """Salva as credenciais criptografadas com backup automático."""
        if not self.is_unlocked():
            raise Exception("Serviço de credenciais não está desbloqueado.")
        
        # Criar backup antes de salvar
        self._create_backup()
        
        try:
            data_str = json.dumps(self.credentials, ensure_ascii=False)
            f_suite = Fernet(self.key)
            encrypted_data = f_suite.encrypt(data_str.encode('utf-8'))
            
            # Salvar em arquivo temporário primeiro
            temp_file = self.cred_file_path + ".tmp"
            with open(temp_file, "wb") as f:
                f.write(encrypted_data)
            
            # Mover para arquivo final (atomic operation)
            import shutil
            shutil.move(temp_file, self.cred_file_path)
            
            logging.info("Credentials saved successfully")
            
        except Exception as e:
            logging.error(f"Error saving credentials: {e}")
            # Tentar restaurar backup
            if self._restore_backup():
                raise Exception("Erro ao salvar credenciais. Backup restaurado.")
            else:
                raise Exception(f"Erro ao salvar credenciais: {e}")

    def change_master_password(self, old_password, new_password):
        """Altera a senha mestra do cofre."""
        if not self.is_unlocked() or not self.salt:
            return False, "O cofre não está desbloqueado."

        # Verificar senha atual
        key_from_old_pass = self._derive_key(old_password, self.salt)
        if key_from_old_pass != self.key:
            return False, "Senha mestra atual está incorreta."

        # Criar backup antes da alteração
        self._create_backup()

        try:
            new_key = self._derive_key(new_password, self.salt)
            old_key = self.key
            self.key = new_key
            
            # Salvar com nova chave
            self.save_credentials()
            
            logging.info("Master password changed successfully")
            return True, "Senha mestra alterada com sucesso!"
            
        except Exception as e:
            # Restaurar chave antiga em caso de erro
            self.key = old_key
            logging.error(f"Error changing master password: {e}")
            return False, f"Erro ao alterar senha mestra: {e}"

    def get_all_aliases(self) -> list:
        """Retorna lista de todos os aliases de credenciais."""
        if not self.is_unlocked(): 
            return []
        return sorted(list(self.credentials.keys()))

    def get_credential(self, alias: str) -> dict | None:
        """Retorna uma credencial específica."""
        if not self.is_unlocked(): 
            return None
        return self.credentials.get(alias)

    def add_or_update_credential(self, alias: str, username: str, password: str):
        """Adiciona ou atualiza uma credencial."""
        if not self.is_unlocked(): 
            return
        
        # Validar dados de entrada
        if not alias or not username or not password:
            raise ValueError("Alias, username e password são obrigatórios")
        
        if len(alias) > 100 or len(username) > 100:
            raise ValueError("Alias e username devem ter no máximo 100 caracteres")
        
        self.credentials[alias] = {
            "username": username, 
            "password": password,
            "created": self._get_timestamp(),
            "updated": self._get_timestamp()
        }
        self.save_credentials()
        logging.info(f"Credential added/updated: {alias}")

    def delete_credential(self, alias):
        """Remove uma credencial."""
        if not self.is_unlocked(): 
            return
        
        if alias in self.credentials:
            del self.credentials[alias]
            self.save_credentials()
            logging.info(f"Credential deleted: {alias}")

    def _get_timestamp(self):
        """Retorna timestamp atual para auditoria."""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_vault_info(self) -> dict:
        """Retorna informações sobre o cofre."""
        return {
            "is_unlocked": self.is_unlocked(),
            "credential_count": len(self.credentials) if self.is_unlocked() else 0,
            "has_backup": os.path.exists(self.backup_file_path),
            "failed_attempts": self._failed_attempts,
            "max_attempts": self._max_failed_attempts
        }