import sqlite3
import os
import json
import logging
import threading
import time
from functools import wraps
from typing import List, Dict, Any, Optional
from ..config.settings import APP_DATA_DIR

DB_FILE = os.path.join(APP_DATA_DIR, "network_tools.db")

# 10s of retry inside SQLite itself before raising OperationalError.
# Combined with WAL mode this makes concurrent reads/writes far more robust
# under the load of monitor threads + API + UI hitting the DB at once.
_BUSY_TIMEOUT_MS = 10_000


def _retry_on_locked(max_retries: int = 5, base_delay: float = 0.1):
    """Retry on `database is locked` errors. Other errors propagate."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logging.warning(
                            f"Database locked in {fn.__name__}, retry {attempt + 1}/{max_retries} after {delay:.2f}s"
                        )
                        time.sleep(delay)
                        continue
                    raise
            return fn(*args, **kwargs)
        return wrapper
    return decorator


class DatabaseManager:
    def __init__(self):
        self.db_file = DB_FILE
        # Serialize writes from threads in this process.
        # SQLite + WAL handles cross-connection concurrency, but a single Python
        # connection is not thread-safe and we observed lock contention.
        self._write_lock = threading.RLock()
        self._init_db()

    def _get_connection(self):
        # timeout makes sqlite3 block up to N seconds waiting for a lock
        # before raising OperationalError. busy_timeout PRAGMA below reinforces it.
        conn = sqlite3.connect(self.db_file, timeout=10.0)
        conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")
        return conn

    def _init_db(self):
        """Inicializa o banco de dados e cria as tabelas se não existirem."""
        try:
            with self._get_connection() as conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL;")
                
                cursor = conn.cursor()
                
                # Tabela de Hosts
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS hosts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL UNIQUE,
                        hostname TEXT,
                        domain TEXT,
                        mac TEXT,
                        description TEXT,
                        group_name TEXT,
                        tags TEXT, -- JSON array
                        ports TEXT, -- JSON array
                        monitoring BOOLEAN DEFAULT 1,
                        vendor TEXT,
                        type TEXT,
                        teamviewer_id TEXT,
                        last_checked TEXT,
                        last_status BOOLEAN,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Tabela de Configurações (chave-valor)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                
                conn.commit()
                
                # Migração de Schema (adicionar colunas se não existirem em bancos antigos)
                self._migrate_schema(conn)
                
        except Exception as e:
            logging.error(f"Erro ao inicializar banco de dados: {e}")

    def _migrate_schema(self, conn):
        """Verifica e adiciona colunas faltantes."""
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(hosts)")
            columns = [info[1] for info in cursor.fetchall()]
            
            new_columns = {
                'vendor': 'TEXT',
                'type': 'TEXT',
                'teamviewer_id': 'TEXT',
                'last_checked': 'TEXT',
                'last_status': 'BOOLEAN',
                'domain': 'TEXT'
            }
            
            for col, dtype in new_columns.items():
                if col not in columns:
                    logging.info(f"Adicionando coluna {col} à tabela hosts...")
                    cursor.execute(f"ALTER TABLE hosts ADD COLUMN {col} {dtype}")
            
            conn.commit()
        except Exception as e:
            logging.error(f"Erro na migração de schema: {e}")

    @_retry_on_locked()
    def get_all_hosts(self) -> List[Dict[str, Any]]:
        """Retorna todos os hosts."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM hosts")
                rows = cursor.fetchall()

                hosts = []
                for row in rows:
                    host = dict(row)
                    try:
                        host['tags'] = json.loads(host['tags']) if host['tags'] else []
                        host['ports'] = json.loads(host['ports']) if host['ports'] else []
                    except (json.JSONDecodeError, TypeError):
                        host['tags'] = []
                        host['ports'] = []
                    hosts.append(host)
                return hosts
        except Exception as e:
            logging.exception(f"Erro ao buscar hosts: {e}")
            return []

    _UPSERT_SQL = """
        INSERT INTO hosts (address, hostname, domain, mac, description, group_name, tags, ports, monitoring, vendor, type, teamviewer_id, last_checked, last_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(address) DO UPDATE SET
            hostname=excluded.hostname,
            domain=excluded.domain,
            mac=excluded.mac,
            description=excluded.description,
            group_name=excluded.group_name,
            tags=excluded.tags,
            ports=excluded.ports,
            monitoring=excluded.monitoring,
            vendor=excluded.vendor,
            type=excluded.type,
            teamviewer_id=excluded.teamviewer_id,
            last_checked=excluded.last_checked,
            last_status=excluded.last_status,
            updated_at=CURRENT_TIMESTAMP
    """

    @staticmethod
    def _row_params(host: Dict[str, Any]):
        return (
            host.get('address'),
            host.get('hostname'),
            host.get('domain'),
            host.get('mac'),
            host.get('description'),
            host.get('group_name'),
            json.dumps(host.get('tags', [])),
            json.dumps(host.get('ports', [])),
            host.get('monitoring', True),
            host.get('vendor'),
            host.get('type'),
            str(host.get('teamviewer_id')) if host.get('teamviewer_id') is not None else None,
            host.get('last_checked'),
            host.get('last_status'),
        )

    @_retry_on_locked()
    def save_host(self, host: Dict[str, Any]) -> bool:
        """Salva ou atualiza um host."""
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(self._UPSERT_SQL, self._row_params(host))
                    conn.commit()
                    return True
            except Exception as e:
                logging.exception(f"Erro ao salvar host {host.get('address')}: {e}")
                return False

    @_retry_on_locked()
    def delete_host(self, address: str) -> bool:
        """Remove um host pelo endereço."""
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM hosts WHERE address = ?", (address,))
                    conn.commit()
                    return True
            except Exception as e:
                logging.exception(f"Erro ao deletar host {address}: {e}")
                return False

    @_retry_on_locked()
    def bulk_save_hosts(self, hosts: List[Dict[str, Any]]) -> bool:
        """Salva múltiplos hosts de uma vez (transação única)."""
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.executemany(self._UPSERT_SQL, [self._row_params(h) for h in hosts])
                    conn.commit()
                    return True
            except Exception as e:
                logging.exception(f"Erro ao salvar múltiplos hosts: {e}")
                return False

    @_retry_on_locked()
    def replace_all_hosts(self, hosts: List[Dict[str, Any]]) -> bool:
        """Substitui todos os hosts atomicamente (DELETE + INSERT na mesma transação)."""
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM hosts")
                    cursor.executemany(
                        """
                        INSERT INTO hosts (address, hostname, domain, mac, description, group_name, tags, ports, monitoring, vendor, type, teamviewer_id, last_checked, last_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [self._row_params(h) for h in hosts],
                    )
                    conn.commit()
                    return True
            except Exception as e:
                logging.exception(f"Erro ao substituir todos os hosts: {e}")
                return False

    @_retry_on_locked()
    def reset_database(self):
        """Apaga todos os dados das tabelas e otimiza o banco."""
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM hosts")
                    cursor.execute("DELETE FROM settings")
                    conn.commit()
                # VACUUM cannot run inside a transaction; reopen.
                with self._get_connection() as conn:
                    conn.execute("VACUUM")
                logging.info("Banco de dados resetado com sucesso.")
                return True
            except Exception as e:
                logging.exception(f"Erro ao resetar banco de dados: {e}")
                return False

# Singleton instance
db = DatabaseManager()
