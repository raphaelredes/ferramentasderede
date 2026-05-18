import os
import json
import base64
import secrets
import logging
import threading
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from src.config.settings import CRED_FILE, SALT_FILE, VAULT_META_FILE

class SecureVault:
    def __init__(self):
        self.credentials = {}
        self.master_key = None
        self.is_unlocked = False
        self.salt = None

        # Constants
        self.ITERATIONS = 600000 # High iteration count for security
        self.KEY_LENGTH = 32 # AES-256

        # Serialize add/save/unlock so two concurrent FastAPI threads can't
        # race on `os.replace(tmp, CRED_FILE)`. The previous design used a
        # shared `CRED_FILE + ".tmp"` path — two writers both opening that
        # collided on Windows with [WinError 32] (file in use by another
        # process), and the loser's mutation to `self.credentials` was lost.
        self._save_lock = threading.RLock()

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derives a 32-byte key from the password using PBKDF2HMAC."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        return kdf.derive(password.encode('utf-8'))

    def unlock(self, password: str, hint: str = None) -> bool:
        """Unlocks the vault using the provided password. Optionally sets a hint if creating a new vault."""
        try:
            if not os.path.exists(SALT_FILE):
                # New vault
                logging.info("Creating new vault...")
                self.salt = secrets.token_bytes(32)
                # Atomic write so a crash mid-save can't leave a half-written
                # salt that locks the operator out of their own vault.
                tmp_salt = SALT_FILE + ".tmp"
                with open(tmp_salt, 'wb') as f:
                    f.write(self.salt)
                os.replace(tmp_salt, SALT_FILE)

                self.master_key = self._derive_key(password, self.salt)
                self.credentials = {}
                self.is_unlocked = True
                self.save()

                # Save hint if provided
                if hint:
                    self.set_hint(hint)

                return True

            # Existing vault
            with open(SALT_FILE, 'rb') as f:
                self.salt = f.read()

            derived_key = self._derive_key(password, self.salt)
            
            if not os.path.exists(CRED_FILE):
                # Salt exists but cred file missing? Treat as empty vault with this key.
                self.master_key = derived_key
                self.credentials = {}
                self.is_unlocked = True
                return True

            with open(CRED_FILE, 'rb') as f:
                data = f.read()
                nonce = data[:12]
                ciphertext = data[12:]

            aesgcm = AESGCM(derived_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            self.credentials = json.loads(plaintext.decode('utf-8'))
            self.master_key = derived_key
            self.is_unlocked = True
            return True

        except Exception as e:
            logging.error(f"Failed to unlock vault: {e}")
            return False

    def lock(self):
        """Locks the vault and clears the master key from memory.

        Acquire `_save_lock` for symmetry — save() already holds it across
        the encrypt + write window, so by the time we get the lock here, any
        in-flight save() has either completed or hasn't started. Today
        save()'s local AESGCM object insulates it from `master_key = None`
        mid-write, but the symmetry prevents a future maintainer from
        breaking that subtle invariant.
        """
        with self._save_lock:
            self.master_key = None
            self.credentials = {}
            self.is_unlocked = False
        logging.info("Vault locked.")

    def save(self):
        """Saves the vault to disk using AES-GCM encryption."""
        if not self.is_unlocked or not self.master_key:
            raise Exception("Vault is locked.")

        with self._save_lock:
            try:
                data_json = json.dumps(self.credentials).encode('utf-8')
                aesgcm = AESGCM(self.master_key)
                nonce = secrets.token_bytes(12)
                ciphertext = aesgcm.encrypt(nonce, data_json, None)

                # Atomic write with a UNIQUE tmp filename per call. The single
                # shared `.tmp` path used previously raced under concurrent
                # add_credential / save calls (Windows [WinError 32]). Each
                # writer now has its own tmp; os.replace is still atomic.
                tmp_path = f"{CRED_FILE}.tmp.{secrets.token_hex(4)}"
                with open(tmp_path, 'wb') as f:
                    f.write(nonce + ciphertext)
                os.replace(tmp_path, CRED_FILE)

                logging.info("Vault saved successfully.")
            except Exception as e:
                logging.error(f"Error saving vault: {e}")
                raise

    def add_credential(self, entry):
        """Adds or updates a credential entry."""
        if not self.is_unlocked:
            raise Exception("Vault is locked.")
        
        entry_id = entry.get('id') or secrets.token_hex(8)
        entry['id'] = entry_id
        self.credentials[entry_id] = entry
        self.save()
        return entry

    def get_credential(self, entry_id):
        if not self.is_unlocked: return None
        return self.credentials.get(entry_id)

    def delete_credential(self, entry_id):
        if not self.is_unlocked: return
        if entry_id in self.credentials:
            del self.credentials[entry_id]
            self.save()

    def get_all_credentials(self, include_passwords: bool = False):
        """Returns the credential list. Passwords are stripped by default so the
        list can travel over the wire to the renderer without exposing secrets;
        the renderer must call /security/credentials/decrypt to retrieve one
        password at a time when the operator clicks "show". An accidental XSS
        or DevTools peek would previously have leaked every password at once."""
        if not self.is_unlocked:
            return []
        creds = list(self.credentials.values())
        if include_passwords:
            return creds
        sanitized = []
        for cred in creds:
            safe = {k: v for k, v in cred.items() if k != "password"}
            sanitized.append(safe)
        return sanitized

    def set_hint(self, hint: str):
        """Saves a password hint to a separate JSON file."""
        try:
            with open(VAULT_META_FILE, 'w') as f:
                json.dump({"hint": hint}, f)
        except Exception as e:
            logging.error(f"Failed to save vault hint: {e}")

    def get_hint(self) -> str:
        """Retrieves the password hint if it exists."""
        try:
            if os.path.exists(VAULT_META_FILE):
                with open(VAULT_META_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("hint", "")
            return ""
        except Exception as e:
            logging.error(f"Failed to get vault hint: {e}")
            return ""

    def reset(self):
        """Resets the vault by deleting all related files."""
        try:
            self.lock()
            if os.path.exists(CRED_FILE):
                os.remove(CRED_FILE)
            if os.path.exists(SALT_FILE):
                os.remove(SALT_FILE)
            if os.path.exists(VAULT_META_FILE):
                os.remove(VAULT_META_FILE)
            logging.info("Vault reset successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to reset vault: {e}")
            return False
