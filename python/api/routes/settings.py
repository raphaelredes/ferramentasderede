from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from typing import Optional, List
import json
import os
import shutil
import logging
from datetime import datetime
import sys

# Add parent directory to path to import modules from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.settings import HOSTS_FILE, APP_DATA_DIR
from src.system.core.local_commands import run_powershell_command
from src.system.backup import BackupManager

backup_manager = BackupManager()

router = APIRouter(tags=["settings"])

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ui_preferences.json")

# --- Models ---
class ScannerSettings(BaseModel):
    default_cidr: str = ""
    ping_timeout: int = 200 # ms
    concurrency: int = 50
    online_vendor_lookup: bool = False # threads

class RemoteSettings(BaseModel):
    auto_add_trusted_hosts: bool = False
    default_credential_id: Optional[str] = None
    auto_login: bool = False

class DashboardSettings(BaseModel):
    status_update_interval: int = 60 # seconds
    ping_monitor_interval: int = 5 # seconds
    notify_offline: bool = False
    notify_online: bool = False

class GeneralSettings(BaseModel):
    appearance_mode: str = "System"
    ask_initial_info: bool = True

class NetworkConfig(BaseModel):
    """A configured network (subnet/VLAN). Used for multi-domain environments
    where the analyst's machine sits on more than one network and discovery /
    ping / DNS need to be steered through a specific NIC and DNS server.

    NOTE on Pydantic v2: do NOT override `model_validate` as a classmethod —
    Pydantic v2 wires `__init__` and FastAPI request-body validation through
    `__pydantic_validator__`, which bypasses any subclass override. The
    `@field_validator` decorator is the supported hook and runs on both the
    constructor path and `model_validate(dict)`.
    """
    id: str
    name: str
    cidr: str
    source_ip: Optional[str] = None     # NIC address to use as ping/traceroute source
    dns_server: Optional[str] = None    # DNS server to query for hosts in this network
    domain: Optional[str] = None        # AD domain associated with this network
    enabled: bool = True

    @field_validator("dns_server", "source_ip")
    @classmethod
    def _must_be_ip(cls, v: Optional[str]):
        # dns_server / source_ip must be plain IP literals. dns_server is
        # particularly sensitive — a hostname here would let a malicious local
        # process steer dnspython at an attacker-controlled resolver. source_ip
        # is selected from local NICs anyway; rejecting non-IP shapes prevents
        # a hand-edited preferences file from smuggling something weird in.
        if v is None or v == "":
            return v
        import ipaddress
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"deve ser um endereço IP: {v!r}") from e
        return v

class Settings(BaseModel):
    general: GeneralSettings = GeneralSettings()
    scanner: ScannerSettings = ScannerSettings()
    remote: RemoteSettings = RemoteSettings()
    dashboard: DashboardSettings = DashboardSettings()
    networks: List[NetworkConfig] = []

# --- Helpers ---
#
# `ui_preferences.json` was previously "encrypted" with Fernet using a key file
# (`key.key`) sitting next to it in APP_DATA_DIR. That offers zero protection:
# anyone with read access to the file has read access to the key, by design.
# We now store it as plaintext JSON to be honest about the threat model — UI
# preferences + network/VLAN config + a credential_id pointer (no actual
# secrets). Real credentials still live in the PBKDF2 + AES-GCM SecureVault.
# Disk-level protection (BitLocker / FileVault) is the right tool for the
# concerns this used to pretend to address.
#
# Migration path: on load, try plaintext first. If that fails because the file
# is still in the legacy encrypted format, decrypt once via the legacy
# SecurityManager and rewrite as plaintext so future loads are direct.
def load_settings() -> Settings:
    if not os.path.exists(SETTINGS_FILE):
        return Settings()
    try:
        # 1. Plaintext (current format).
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Settings(**data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # likely legacy encrypted blob — fall through.

        # 2. Legacy: decrypt with Fernet, parse, then rewrite as plaintext so
        #    we only pay the migration cost once.
        from src.core.security import SecurityManager
        from src.config.settings import APP_DATA_DIR
        sec_manager = SecurityManager(APP_DATA_DIR)
        json_str = sec_manager.load_encrypted_file(SETTINGS_FILE)
        data = json.loads(json_str)
        settings = Settings(**data)
        try:
            save_settings_to_file(settings)
            logging.info("ui_preferences.json migrated from legacy encrypted format to plaintext.")
        except Exception as e:
            logging.warning(f"failed to rewrite ui_preferences.json as plaintext: {e}")
        return settings

    except Exception as e:
        logging.exception(f"Error loading settings: {e}")
        return Settings()

def save_settings_to_file(settings: Settings):
    try:
        json_str = json.dumps(settings.model_dump(), indent=4)
        # Atomic write: tmp file + rename so a crash mid-write doesn't corrupt
        # the prefs file (the legacy code wrote in-place).
        tmp_path = SETTINGS_FILE + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        os.replace(tmp_path, SETTINGS_FILE)
    except Exception as e:
        logging.exception(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings.")

# --- Endpoints ---

@router.get("/settings", response_model=Settings)
def get_settings():
    return load_settings()

@router.post("/settings")
def save_settings(settings: Settings):
    save_settings_to_file(settings)
    return {"status": "success", "message": "Settings saved successfully."}

# --- Trusted Hosts Management ---

@router.get("/settings/trusted-hosts")
def get_trusted_hosts():
    """Get list of TrustedHosts from WinRM configuration."""
    from src.system.core.winrm_handler import WinRMHandler
    hosts = WinRMHandler.get_trusted_hosts()
    # Normalize return type to list of strings
    if not hosts:
        return []
    if hosts == "*":
        return ["*"]
    return [h.strip() for h in hosts.split(',') if h.strip()]

def _validate_trusted_host_value(host: str) -> bool:
    """TrustedHosts entries are IPs, hostnames, or `*` (wildcard).
    Reject anything that could be passed as a registry value injection."""
    if not isinstance(host, str) or not host:
        return False
    if len(host) > 253:
        return False
    if host == "*":
        return True
    import re
    # Accept IPv4, single hostname, or comma-separated list of either.
    parts = [p.strip() for p in host.split(",") if p.strip()]
    if not parts:
        return False
    for part in parts:
        if part == "*":
            continue
        if not re.fullmatch(r"[A-Za-z0-9._\-]+", part):
            return False
    return True


@router.post("/settings/trusted-hosts")
def add_trusted_host(host: str):
    """Add a host to TrustedHosts (requires Admin)."""
    if not _validate_trusted_host_value(host):
        raise HTTPException(status_code=400, detail="Valor de host inválido para TrustedHosts.")
    from src.system.core.winrm_handler import WinRMHandler
    if WinRMHandler.add_trusted_host(host):
        return {"status": "success", "message": f"Added {host} to TrustedHosts."}
    else:
        raise HTTPException(status_code=500, detail="Failed to add TrustedHost.")

@router.delete("/settings/trusted-hosts")
def remove_trusted_host_endpoint(host: Optional[str] = None):
    """Remove a single TrustedHost or clear all."""
    from src.system.core.winrm_handler import WinRMHandler
    if host:
        if not _validate_trusted_host_value(host):
            raise HTTPException(status_code=400, detail="Valor de host inválido para TrustedHosts.")
        if WinRMHandler.remove_trusted_host(host):
            return {"status": "success", "message": f"Removed {host} from TrustedHosts."}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove TrustedHost.")
    else:
        # Clear all logic (set to empty string)
        if WinRMHandler.set_trusted_hosts(""):
            return {"status": "success", "message": "TrustedHosts cleared."}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear TrustedHosts.")

# --- Data Management ---

@router.get("/settings/export")
def export_hosts():
    """Download the hosts.json file with fresh data from DB."""
    try:
        # Generate fresh hosts.json from DB
        from src.core.host_manager import HostManager
        manager = HostManager()
        
        # We overwrite the legacy HOSTS_FILE to keep it in sync and use it for export
        if manager.export_to_json_file(HOSTS_FILE):
            filename = f"hosts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            return FileResponse(HOSTS_FILE, media_type='application/json', filename=filename)
        else:
            raise HTTPException(status_code=500, detail="Failed to generate export file.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

# Cap import payload at 5 MB. A real hosts.json with even 10k entries is well
# under 500 KB; anything bigger is either a backup corrupted on upload or a
# DoS attempt. Without the cap, `await file.read()` could OOM the backend on
# an arbitrarily large upload.
_MAX_IMPORT_BYTES = 5 * 1024 * 1024


@router.post("/settings/import")
async def import_hosts(file: UploadFile = File(...)):
    """Upload and replace hosts (supports encrypted and legacy plain JSON)."""
    # Content-Type is advisory; reject the obviously wrong cases (binary
    # blobs, executables). Genuine JSON uploads from the renderer arrive with
    # either "application/json" or "application/octet-stream" (for encrypted
    # backups, which are raw bytes).
    if file.content_type and file.content_type not in (
        "application/json",
        "application/octet-stream",
        "text/plain",
        "",
    ):
        raise HTTPException(status_code=400, detail="Tipo de arquivo não suportado.")

    try:
        # Streaming-read with cap to avoid OOM. UploadFile.read accepts an int
        # but doesn't enforce a hard limit on its own across all FastAPI
        # versions, so we read in chunks and bail if we exceed the cap.
        contents = bytearray()
        chunk_size = 64 * 1024
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            contents.extend(chunk)
            if len(contents) > _MAX_IMPORT_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Arquivo maior que {_MAX_IMPORT_BYTES // (1024 * 1024)} MB.",
                )
        contents = bytes(contents)

        data = None
        # Try to decrypt first
        try:
            from src.core.security import SecurityManager
            from src.config.settings import APP_DATA_DIR
            sec_manager = SecurityManager(APP_DATA_DIR)
            # contents is bytes, decrypt_data expects bytes and returns bytes
            decrypted_bytes = sec_manager.decrypt_data(contents)
            data = json.loads(decrypted_bytes.decode('utf-8'))
        except Exception:
            # Fallback to plain text (legacy support). Sanitize the error path
            # — the previous code echoed the raw parse exception, which can
            # include attacker-controlled bytes near the parse failure.
            try:
                data = json.loads(contents.decode('utf-8'))
            except Exception:
                raise HTTPException(status_code=400, detail="Formato inválido. Esperado JSON ou backup cifrado.")

        if data is None:
             raise HTTPException(status_code=400, detail="Failed to parse file data.")
        
        hosts_data = []
        trusted_hosts_data = []

        # Handle new format {'hosts': [], 'trusted_hosts': []}
        if isinstance(data, dict) and 'hosts' in data:
            hosts_data = data['hosts']
            trusted_hosts_data = data.get('trusted_hosts', [])
        elif isinstance(data, list):
            # Legacy format
            hosts_data = data
        elif isinstance(data, dict):
             # Handle potential dict wrapper from legacy
            hosts_data = list(data.values())
            if not isinstance(hosts_data, list):
                 hosts_data = [] # Fallback
        
        if not isinstance(hosts_data, list):
             raise HTTPException(status_code=400, detail="Invalid JSON format: expected a list of hosts.")

        # Use HostManager to save to DB
        from src.core.host_manager import HostManager
        manager = HostManager()
        manager.update_hosts(hosts_data)

        # Restore Trusted Hosts if present. Filter through the strict
        # validator BEFORE handing to set_trusted_hosts — a malicious backup
        # could otherwise smuggle entries like "evil'; rm -rf; '" that, while
        # the underlying writer now sanitizes too, shouldn't even reach the
        # decision boundary. set_trusted_hosts is itself fail-closed if any
        # entry is unsafe; we filter first so partially-valid imports still
        # apply their clean entries instead of bouncing the whole list.
        if trusted_hosts_data:
            from src.system.winrm import set_trusted_hosts, _validate_entry
            safe_entries = [h for h in trusted_hosts_data if _validate_entry(h)]
            rejected = [h for h in trusted_hosts_data if not _validate_entry(h)]
            if rejected:
                logging.warning(
                    f"/settings/import: rejected {len(rejected)} unsafe trusted_hosts entries: {rejected!r}"
                )
            if safe_entries and not set_trusted_hosts(safe_entries):
                logging.warning("/settings/import: set_trusted_hosts returned False (defensive validators rejected at writer layer)")

        return {"status": "success", "message": "Hosts imported successfully."}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file.")
    except HTTPException:
        raise
    except Exception:
        # Sanitize the error path — exception text could include attacker-
        # controlled bytes from the parse failure path.
        logging.exception("/settings/import failed")
        raise HTTPException(status_code=500, detail="Import failed.")

@router.post("/settings/reset")
def factory_reset():
    """Clear all data and settings."""
    try:
        # 1. Reset SQLite Database (Truncate tables instead of deleting file to avoid locks)
        from src.core.database import DatabaseManager
        db_manager = DatabaseManager()
        db_success = db_manager.reset_database()
        
        if not db_success:
            logging.warning("Failed to reset database tables.")

        # 2. Clear Trusted Hosts
        from src.system.winrm import clear_trusted_hosts
        clear_trusted_hosts()

        # 3. Delete other configuration files
        files_to_delete = [
            HOSTS_FILE,
            # os.path.join(APP_DATA_DIR, "network_tools.db"), # Do not delete DB file anymore
            os.path.join(APP_DATA_DIR, "ui_preferences.json"),
            os.path.join(APP_DATA_DIR, "discovery_cache.json"),
            os.path.join(APP_DATA_DIR, "credentials.enc"),
            os.path.join(APP_DATA_DIR, "key.salt"),
            os.path.join(APP_DATA_DIR, "favorites.json"),
            os.path.join(APP_DATA_DIR, "vault_meta.json"),
            # Legacy
            os.path.join(APP_DATA_DIR, "settings.json")
        ]

        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                logging.warning(f"Failed to delete {file_path}: {e}")

        return {"status": "success", "message": f"Factory reset complete. Database cleared, Trusted Hosts cleared, and {deleted_count} files deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")

# --- Backup Management ---

@router.get("/settings/backups")
def list_backups():
    """List available automated backups."""
    return backup_manager.list_backups()

@router.post("/settings/backups/create")
def create_manual_backup():
    """Trigger a manual backup."""
    result = backup_manager.create_backup(prefix="manual_backup")
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@router.post("/settings/backups/{filename}/restore")
def restore_backup(filename: str):
    """Restore a specific backup."""
    result = backup_manager.restore_backup(filename)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@router.delete("/settings/backups/{filename}")
def delete_backup(filename: str):
    """Delete a specific backup."""
    result = backup_manager.delete_backup(filename)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
