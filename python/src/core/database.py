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
    """Retry on `database is locked` / SQLITE_BUSY errors. Other errors propagate.

    Uses `sqlite_errorcode` (Python 3.11+) when available — 5 = SQLITE_BUSY,
    6 = SQLITE_LOCKED. Falls back to a string match for older interpreters,
    but the string is locale-dependent in some builds so prefer the code.
    """
    def _is_locked(exc: sqlite3.OperationalError) -> bool:
        code = getattr(exc, "sqlite_errorcode", None)
        if code in (5, 6):
            return True
        return "locked" in str(exc).lower() or "busy" in str(exc).lower()

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if _is_locked(e) and attempt < max_retries - 1:
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
                        current_user TEXT,                 -- last known interactive user (host-probe)
                        last_boot TEXT,                    -- last known LastBootUpTime (host-probe)
                        system_disk_free_gb REAL,          -- free space on SystemDrive in GB (host-probe)
                        resolved_ip TEXT,                  -- forward-resolved IPv4 when `address` is a hostname; survives restarts
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
                'domain': 'TEXT',
                # host-probe (Sprint: opportunistic data collection)
                'current_user': 'TEXT',
                'last_boot': 'TEXT',
                'system_disk_free_gb': 'REAL',
                # forward-DNS result when `address` is a hostname. Lets the UI
                # show the real IP without depending on the in-memory monitor
                # state (which is lost on restart).
                'resolved_ip': 'TEXT',
            }
            
            # One-time cleanup: hosts created by older versions persisted the
            # literal "Unknown" as the description (= UI nickname) when no
            # operator label was given. The new code uses IP / hostname as the
            # display fallback and never writes "Unknown" — but legacy rows
            # still carry it. Clear so the UI shows the IP/hostname fallback.
            try:
                cursor.execute(
                    "UPDATE hosts SET description = NULL WHERE description = 'Unknown'"
                )
            except Exception as _e:
                logging.debug(f"Unknown-nickname migration skipped: {_e}")

            # SQLite DDL can't parameter-bind identifiers, so we f-string. The
            # values come from the hardcoded dict above — never user input —
            # but guard with asserts so a future caller who adds a column from
            # a config file can't smuggle SQL.
            allowed_dtypes = {'TEXT', 'BOOLEAN', 'REAL', 'INTEGER'}
            for col, dtype in new_columns.items():
                if col not in columns:
                    assert col.isidentifier(), f"unsafe column name: {col!r}"
                    assert dtype in allowed_dtypes, f"unsafe dtype: {dtype!r}"
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

    # Single source of truth for the columns we write through save_host /
    # bulk_save_hosts / replace_all_hosts. Listing them once avoids the bug
    # where _UPSERT_SQL and the replace_all_hosts INSERT drift out of sync
    # — which is how `resolved_ip` and the host-probe columns (current_user,
    # last_boot, system_disk_free_gb) silently got zeroed on every PATCH
    # that went through the slow path.
    _WRITE_COLUMNS = [
        'address', 'hostname', 'domain', 'mac', 'description', 'group_name',
        'tags', 'ports', 'monitoring', 'vendor', 'type', 'teamviewer_id',
        'last_checked', 'last_status',
        'resolved_ip',
        'current_user', 'last_boot', 'system_disk_free_gb',
    ]
    _UPSERT_SQL = (
        f"INSERT INTO hosts ({', '.join(_WRITE_COLUMNS)}) "
        f"VALUES ({', '.join(['?'] * len(_WRITE_COLUMNS))}) "
        "ON CONFLICT(address) DO UPDATE SET "
        + ", ".join(
            f"{col}=excluded.{col}"
            for col in _WRITE_COLUMNS
            if col != 'address'
        )
        + ", updated_at=CURRENT_TIMESTAMP"
    )

    @staticmethod
    def _row_params(host: Dict[str, Any]):
        """Tuple matching _WRITE_COLUMNS order. Adding a column here means:
        (1) extend _WRITE_COLUMNS, (2) append the value here, (3) update
        update_hosts in HostManager to pass it through. Otherwise the column
        gets `NULL` written on every replace_all_hosts pass."""
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
            host.get('resolved_ip'),
            host.get('current_user'),
            host.get('last_boot'),
            host.get('system_disk_free_gb'),
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
    def update_host_status(self, address: str, last_status: Optional[bool], last_checked: Optional[str]) -> bool:
        """Atualiza só os campos voláteis do ping de um host (last_status, last_checked).

        Usado pelo monitor a cada tick (~1×/s/host). Substitui o padrão antigo de
        `replace_all_hosts` no callback, que reescrevia a tabela inteira a cada
        ping — gargalo crítico em redes com ≥100 hosts.
        """
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE hosts
                        SET last_status = ?, last_checked = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE address = ?
                        """,
                        (last_status, last_checked, address),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logging.exception(f"Erro ao atualizar status do host {address}: {e}")
                return False

    @_retry_on_locked()
    def update_host_fields(self, address: str, fields: Dict[str, Any]) -> bool:
        """Atualiza um subconjunto arbitrário de colunas para um host.

        Mais barato que ler-modificar-salvar via `save_host` quando só uma coluna
        muda (ex.: monitor descobre MAC novo, hostname novo via DNS reverso, IP
        resolvido para o nome). Aceita apenas chaves whitelisted.
        """
        if not fields:
            return False
        allowed = {
            'hostname', 'domain', 'mac', 'description', 'group_name',
            'monitoring', 'vendor', 'type', 'teamviewer_id',
            'last_checked', 'last_status',
            'current_user', 'last_boot', 'system_disk_free_gb',
            'resolved_ip',
        }
        # tags/ports are JSON columns — handle them explicitly if needed.
        sanitized = {k: v for k, v in fields.items() if k in allowed}
        if not sanitized:
            return False
        with self._write_lock:
            try:
                set_clause = ", ".join(f"{k} = ?" for k in sanitized) + ", updated_at = CURRENT_TIMESTAMP"
                params = list(sanitized.values()) + [address]
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"UPDATE hosts SET {set_clause} WHERE address = ?", params)
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                logging.exception(f"Erro ao atualizar campos do host {address}: {e}")
                return False

    @_retry_on_locked()
    def replace_all_hosts(self, hosts: List[Dict[str, Any]]) -> bool:
        """Substitui todos os hosts atomicamente (DELETE + INSERT na mesma transação).

        Uses the same _WRITE_COLUMNS constant as save_host so that columns added
        later (resolved_ip, current_user, last_boot, system_disk_free_gb) are
        preserved across the DELETE/INSERT instead of silently NULLed. Before
        the refactor the INSERT was a separate hard-coded list of 14 columns;
        adding resolved_ip didn't update it, so every PATCH that went through
        the slow path wiped the IP cache the monitor had just resolved.
        """
        cols = ", ".join(self._WRITE_COLUMNS)
        placeholders = ", ".join(["?"] * len(self._WRITE_COLUMNS))
        sql = f"INSERT INTO hosts ({cols}) VALUES ({placeholders})"
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM hosts")
                    cursor.executemany(sql, [self._row_params(h) for h in hosts])
                    conn.commit()
                    return True
            except Exception as e:
                logging.exception(f"Erro ao substituir todos os hosts: {e}")
                return False

    @_retry_on_locked()
    def clear_all_hosts(self) -> bool:
        """Apaga todos os hosts. Respeita write_lock + retry decorator —
        bypass-direto via `_get_connection()` (como o legado em HostManager)
        contornava a serialização e podia causar `database is locked` quando
        outra task estava no meio de um INSERT."""
        with self._write_lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM hosts")
                    conn.commit()
                return True
            except Exception as e:
                logging.exception(f"Erro ao limpar hosts: {e}")
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
