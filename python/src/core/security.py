import os
import json
import base64
from cryptography.fernet import Fernet
from typing import List, Dict, Optional
import uuid

class SecurityManager:
    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir
        self.key_file = os.path.join(data_dir, "key.key")
        self.credentials_file = os.path.join(data_dir, "credentials.enc")
        self.key = self._load_or_generate_key()
        self.cipher_suite = Fernet(self.key)
        self.credentials = self._load_credentials()

    def _load_or_generate_key(self) -> bytes:
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(key)
            return key

    def _load_credentials(self) -> List[Dict]:
        if not os.path.exists(self.credentials_file):
            return []
        
        try:
            with open(self.credentials_file, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception as e:
            print(f"Erro ao carregar credenciais: {e}")
            return []

    def _save_credentials(self):
        data_json = json.dumps(self.credentials)
        encrypted_data = self.cipher_suite.encrypt(data_json.encode('utf-8'))
        with open(self.credentials_file, "wb") as f:
            f.write(encrypted_data)

    def add_credential(self, name: str, username: str, password: str, description: str = "") -> Dict:
        credential = {
            "id": str(uuid.uuid4()),
            "name": name,
            "username": username,
            "password": password, # Stored in memory as plain text inside the list, but file is encrypted
            "description": description
        }
        self.credentials.append(credential)
        self._save_credentials()
        return self._sanitize(credential)

    def get_credentials(self) -> List[Dict]:
        return [self._sanitize(c) for c in self.credentials]

    def get_credential_password(self, credential_id: str) -> Optional[str]:
        for c in self.credentials:
            if c["id"] == credential_id:
                return c["password"]
        return None

    def delete_credential(self, credential_id: str) -> bool:
        initial_len = len(self.credentials)
        self.credentials = [c for c in self.credentials if c["id"] != credential_id]
        if len(self.credentials) < initial_len:
            self._save_credentials()
            return True
        return False

    def _sanitize(self, credential: Dict) -> Dict:
        """Return credential without password for UI display"""
        c = credential.copy()
        if "password" in c:
            del c["password"]
        return c
