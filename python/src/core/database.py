import sqlite3
import os
import json
import logging
from typing import List, Dict, Any, Optional
from ..config.settings import APP_DATA_DIR

DB_FILE = os.path.join(APP_DATA_DIR, "network_tools.db")

class DatabaseManager:
    def __init__(self):
        self.db_file = DB_FILE
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_file)

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

    def get_all_hosts(self) -> List[Dict[str, Any]]:
        """Retorna todos os hosts (com retry para evitar travamento)."""
        import time
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM hosts")
                    rows = cursor.fetchall()
                    
                    hosts = []
                    for row in rows:
                        host = dict(row)
                        # Parse JSON fields
                        try:
                            host['tags'] = json.loads(host['tags']) if host['tags'] else []
                            host['ports'] = json.loads(host['ports']) if host['ports'] else []
                        except:
                            host['tags'] = []
                            host['ports'] = []
                        hosts.append(host)
                    return hosts
            except sqlite3.OperationalError as e:
                # If database is locked, wait and retry
                if "locked" in str(e) and attempt < max_retries - 1:
                    logging.warning(f"Database locked, retrying get_all_hosts (attempt {attempt+1}/{max_retries})...")
                    time.sleep(0.1)
                else:
                    logging.error(f"Erro operacional ao buscar hosts: {e}")
                    return []
            except Exception as e:
                logging.error(f"Erro ao buscar hosts: {e}")
                return []
        return []

    def save_host(self, host: Dict[str, Any]) -> bool:
        """Salva ou atualiza um host."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                tags_json = json.dumps(host.get('tags', []))
                ports_json = json.dumps(host.get('ports', []))
                
                cursor.execute("""
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
                """, (
                    host.get('address'),
                    host.get('hostname'),
                    host.get('domain'),
                    host.get('mac'),
                    host.get('description'),
                    host.get('group_name'),
                    tags_json,
                    ports_json,
                    host.get('monitoring', True),
                    host.get('vendor'),
                    host.get('type'),
                    str(host.get('teamviewer_id')) if host.get('teamviewer_id') is not None else None,
                    host.get('last_checked'),
                    host.get('last_status')
                ))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar host {host.get('address')}: {e}")
            return False

    def delete_host(self, address: str) -> bool:
        """Remove um host pelo endereço."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM hosts WHERE address = ?", (address,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao deletar host {address}: {e}")
            return False

    def bulk_save_hosts(self, hosts: List[Dict[str, Any]]) -> bool:
        """Salva múltiplos hosts de uma vez (transação única)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                for host in hosts:
                    tags_json = json.dumps(host.get('tags', []))
                    ports_json = json.dumps(host.get('ports', []))
                    
                    cursor.execute("""
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
                    """, (
                        host.get('address'),
                        host.get('hostname'),
                        host.get('domain'),
                        host.get('mac'),
                        host.get('description'),
                        host.get('group_name'),
                        tags_json,
                        ports_json,
                        host.get('monitoring', True),
                        host.get('vendor'),
                        host.get('type'),
                        str(host.get('teamviewer_id')) if host.get('teamviewer_id') is not None else None,
                        host.get('last_checked'),
                        host.get('last_status')
                    ))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao salvar múltiplos hosts: {e}")
            return False

    def replace_all_hosts(self, hosts: List[Dict[str, Any]]) -> bool:
        """Substitui todos os hosts atomicamente (Delete All + Insert All numa única transação)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Limpar tabela dentro da transação
                cursor.execute("DELETE FROM hosts")
                
                # 2. Inserir novos hosts
                for host in hosts:
                    tags_json = json.dumps(host.get('tags', []))
                    ports_json = json.dumps(host.get('ports', []))
                    
                    cursor.execute("""
                        INSERT INTO hosts (address, hostname, domain, mac, description, group_name, tags, ports, monitoring, vendor, type, teamviewer_id, last_checked, last_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        host.get('address'),
                        host.get('hostname'),
                        host.get('domain'),
                        host.get('mac'),
                        host.get('description'),
                        host.get('group_name'),
                        tags_json,
                        ports_json,
                        host.get('monitoring', True),
                        host.get('vendor'),
                        host.get('type'),
                        str(host.get('teamviewer_id')) if host.get('teamviewer_id') is not None else None,
                        host.get('last_checked'),
                        host.get('last_status')
                    ))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Erro ao substituir todos os hosts: {e}")
            return False

    def reset_database(self):
        """Apaga todos os dados das tabelas e otimiza o banco."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM hosts")
                cursor.execute("DELETE FROM settings")
                # Adicione outras tabelas aqui se houver
                conn.commit()
                cursor.execute("VACUUM") # Reclaim space
                logging.info("Banco de dados resetado com sucesso.")
                return True
        except Exception as e:
            logging.error(f"Erro ao resetar banco de dados: {e}")
            return False

# Singleton instance
db = DatabaseManager()
