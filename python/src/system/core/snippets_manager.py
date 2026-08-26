# python/src/system/core/snippets_manager.py
"""Gerenciador e repositório de Snippets / Scripts úteis no SQLite.

Permite listar, criar, editar e excluir scripts rápidos para execução
via WinRM, terminal ou Batch Runner.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from src.core.database import db, _retry_on_locked

DEFAULT_SNIPPETS = [
    {
        "title": "Limpar Cache DNS & Registrar",
        "description": "Executa flush no cache do resolvedor e força registro no DNS",
        "command": "ipconfig /flushdns ; ipconfig /registerdns",
        "category": "Rede",
        "type": "powershell"
    },
    {
        "title": "Reiniciar Spooler de Impressão",
        "description": "Força o reinício limpo do serviço de spooler de impressão",
        "command": "Stop-Service -Name Spooler -Force ; Start-Service -Name Spooler ; Get-Service -Name Spooler",
        "category": "Serviços",
        "type": "powershell"
    },
    {
        "title": "Auditoria de Espaço em Disco",
        "description": "Lista unidades de disco locais com espaço livre em GB e percentual",
        "command": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Livre (GB)';E={[math]::Round($_.Free/1GB,2)}}, @{N='Usado (GB)';E={[math]::Round($_.Used/1GB,2)}}",
        "category": "Diagnóstico",
        "type": "powershell"
    },
    {
        "title": "Verificar Status do BitLocker",
        "description": "Verifica se todos os volumes locais estão criptografados",
        "command": "Get-BitLockerVolume | Select-Object MountPoint, VolumeStatus, EncryptionPercentage, ProtectionStatus",
        "category": "Segurança",
        "type": "powershell"
    },
    {
        "title": "Forçar Atualização de GPO",
        "description": "Aplica políticas de grupo sem esperar reboot ou logon",
        "command": "gpupdate /force /wait:0",
        "category": "Active Directory",
        "type": "powershell"
    },
    {
        "title": "Dump de Tabela de Rotas e Adaptadores",
        "description": "Exibe detalhes de adaptadores de rede físicos e rotas ativas",
        "command": "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed ; Get-NetRoute -AddressFamily IPv4 | Select-Object DestinationPrefix, NextHop, RouteMetric",
        "category": "Rede",
        "type": "powershell"
    }
]


@_retry_on_locked()
def init_snippets_table():
    """Cria a tabela de snippets se não existir e insere os defaults."""
    with db._write_lock:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS script_snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    command TEXT NOT NULL,
                    category TEXT DEFAULT 'Geral',
                    type TEXT DEFAULT 'powershell',
                    created_at REAL NOT NULL
                )
            ''')
            
            cursor.execute('SELECT COUNT(*) FROM script_snippets')
            count = cursor.fetchone()[0]
            if count == 0:
                now = time.time()
                for s in DEFAULT_SNIPPETS:
                    cursor.execute('''
                        INSERT INTO script_snippets (title, description, command, category, type, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (s["title"], s["description"], s["command"], s["category"], s["type"], now))
            conn.commit()


@_retry_on_locked()
def list_snippets(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todos os snippets salvos, opcionalmente filtrados por categoria."""
    init_snippets_table()
    with db._get_connection() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute('SELECT id, title, description, command, category, type, created_at FROM script_snippets WHERE category = ? ORDER BY id ASC', (category,))
        else:
            cursor.execute('SELECT id, title, description, command, category, type, created_at FROM script_snippets ORDER BY id ASC')
        rows = cursor.fetchall()
        
    return [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "command": r[3],
            "category": r[4],
            "type": r[5],
            "created_at": r[6]
        }
        for r in rows
    ]


@_retry_on_locked()
def save_snippet(title: str, command: str, description: str = "", category: str = "Geral", snippet_type: str = "powershell") -> int:
    """Cria um novo snippet no repositório."""
    init_snippets_table()
    with db._write_lock:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO script_snippets (title, description, command, category, type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, description, command, category, snippet_type, time.time()))
            conn.commit()
            return cursor.lastrowid or 0


@_retry_on_locked()
def delete_snippet(snippet_id: int) -> bool:
    """Exclui um snippet pelo ID."""
    with db._write_lock:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM script_snippets WHERE id = ?', (snippet_id,))
            conn.commit()
            return cursor.rowcount > 0
