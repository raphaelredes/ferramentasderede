import os
import shutil
import logging
import zipfile
from datetime import datetime, timedelta
from typing import List, Dict
import glob

from src.config.settings import (
    APP_DATA_DIR,
    HOSTS_FILE,
    CRED_FILE,
    SALT_FILE,
    UI_PREFS_FILE,
    FAVORITES_FILE
)

class BackupManager:
    def __init__(self):
        self.backup_dir = os.path.join(APP_DATA_DIR, "backups")
        self.files_to_backup = [
            HOSTS_FILE,
            CRED_FILE,
            SALT_FILE,
            UI_PREFS_FILE,
            FAVORITES_FILE,
            os.path.join(APP_DATA_DIR, "network_tools.db")
        ]
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, prefix: str = "daily_backup") -> Dict[str, str]:
        """Creates a zip backup of all critical files."""
        try:
            # Ensure hosts.json is up-to-date from DB before backing up
            try:
                from src.core.host_manager import HostManager
                manager = HostManager()
                manager.export_to_json_file(HOSTS_FILE)
            except Exception as e:
                logging.warning(f"Failed to refresh hosts.json from DB before backup: {e}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{prefix}_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            files_backed_up = []
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in self.files_to_backup:
                    if os.path.exists(file_path):
                        # Store with basename only to avoid full path structure in zip
                        zipf.write(file_path, os.path.basename(file_path))
                        files_backed_up.append(os.path.basename(file_path))
            
            if not files_backed_up:
                # If no files were found, remove empty zip
                os.remove(backup_path)
                return {"status": "skipped", "message": "No files to backup."}

            logging.info(f"Backup created successfully: {backup_path}")
            return {
                "status": "success", 
                "path": backup_path, 
                "files": files_backed_up,
                "timestamp": timestamp
            }
            
        except Exception as e:
            logging.error(f"Backup creation failed: {e}")
            return {"status": "error", "message": str(e)}

    def cleanup_old_backups(self, retention_days: int = 7):
        """Removes backups older than retention_days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Find all zip files in backup dir
            backup_files = glob.glob(os.path.join(self.backup_dir, "*.zip"))
            
            deleted_count = 0
            for file_path in backup_files:
                # Get file modification time
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_time < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    logging.info(f"Deleted old backup: {file_path}")
            
            return {"status": "success", "deleted_count": deleted_count}
            
        except Exception as e:
            logging.error(f"Backup cleanup failed: {e}")
            return {"status": "error", "message": str(e)}

    def list_backups(self) -> List[Dict]:
        """Lists available backups sorted by date (newest first)."""
        backups = []
        try:
            files = glob.glob(os.path.join(self.backup_dir, "*.zip"))
            for f in files:
                stats = os.stat(f)
                backups.append({
                    "filename": os.path.basename(f),
                    "path": f,
                    "size": stats.st_size,
                    "created": datetime.fromtimestamp(stats.st_mtime).isoformat()
                })
            
            # Sort by created date descending
            backups.sort(key=lambda x: x["created"], reverse=True)
            return backups
        except Exception as e:
            logging.error(f"Error listing backups: {e}")
            return []

    def delete_backup(self, filename: str) -> Dict[str, str]:
        """Deletes a specific backup file."""
        backup_path = os.path.join(self.backup_dir, filename)
        
        if not os.path.exists(backup_path):
            return {"status": "error", "message": "Backup file not found."}
            
        try:
            os.remove(backup_path)
            logging.info(f"Deleted backup: {backup_path}")
            return {"status": "success", "message": f"Backup {filename} deleted successfully."}
        except Exception as e:
            logging.error(f"Failed to delete backup {filename}: {e}")
            return {"status": "error", "message": str(e)}

    def restore_backup(self, filename: str) -> Dict[str, str]:
        """Restores files from a specific backup zip."""
        backup_path = os.path.join(self.backup_dir, filename)
        
        if not os.path.exists(backup_path):
            return {"status": "error", "message": "Backup file not found."}
            
        try:
            restored_files = []
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                # Extract to temp dir first or directly? 
                # Directly to APP_DATA_DIR is fine as we want to overwrite
                
                # Security check: ensure filenames don't contain paths
                for member in zipf.namelist():
                    if ".." in member or "/" in member or "\\" in member:
                         logging.warning(f"Skipping suspicious file in backup: {member}")
                         continue
                    
                    # Extract to APP_DATA_DIR
                    zipf.extract(member, APP_DATA_DIR)
                    restored_files.append(member)
            
            # If hosts.json was restored, we need to re-import it into the DB and restore Trusted Hosts
            if os.path.basename(HOSTS_FILE) in restored_files:
                try:
                    from src.core.host_manager import HostManager
                    manager = HostManager()
                    success, msg = manager.import_from_json_file(HOSTS_FILE)
                    if success:
                        logging.info("Successfully re-imported hosts and trusted hosts from restored backup.")
                    else:
                        logging.error(f"Failed to re-import hosts from restored backup: {msg}")
                except Exception as e:
                    logging.error(f"Error re-importing hosts after restore: {e}")

            logging.info(f"Restored backup {filename}")
            return {"status": "success", "restored_files": restored_files}
            
        except Exception as e:
            logging.error(f"Restore failed: {e}")
            return {"status": "error", "message": str(e)}

    def run_daily_backup_check(self):
        """Checks if a backup is needed for today and runs it."""
        try:
            today_str = datetime.now().strftime("%Y%m%d")
            
            # Check if any backup from today exists
            existing_backups = glob.glob(os.path.join(self.backup_dir, f"*{today_str}*.zip"))
            
            if not existing_backups:
                logging.info("No backup found for today. Creating daily backup...")
                self.create_backup(prefix="daily_backup")
                self.cleanup_old_backups()
            else:
                logging.info("Daily backup already exists.")
                
        except Exception as e:
            logging.error(f"Daily backup check failed: {e}")
