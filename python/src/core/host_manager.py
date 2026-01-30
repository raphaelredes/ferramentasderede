# app/host_manager.py
# Gerencia a lógica de dados para a lista de hosts: carregar, salvar, adicionar, remover, etc.
# Agora usando SQLite via DatabaseManager para melhor performance e escalabilidade.

import os
import json
import csv
import logging
from src.config.settings import FAVORITES_FILE
from src.core.database import db

class HostManager:
    def __init__(self):
        self.hosts = []
        self._migrate_from_json()
        self.load_hosts()

    def _migrate_from_json(self):
        """Migra dados do hosts.json para o SQLite se o banco estiver vazio."""
        try:
            # Verificar se o banco já tem dados
            existing_hosts = db.get_all_hosts()
            if existing_hosts:
                return # Já migrado ou em uso

            if os.path.exists(FAVORITES_FILE):
                logging.info("Iniciando migração de hosts.json para SQLite...")
                with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle new format {'hosts': [], 'trusted_hosts': []} or legacy list
                json_hosts = []
                if isinstance(data, dict) and 'hosts' in data:
                    json_hosts = data['hosts']
                elif isinstance(data, list):
                    json_hosts = data
                elif isinstance(data, dict):
                    json_hosts = list(data.values())

                hosts_to_save = []
                for h in json_hosts:
                    if not isinstance(h, dict): continue
                    # Adaptar estrutura do JSON antigo para o novo schema
                    host_data = {
                        'address': h.get('ip'),
                        'hostname': h.get('name'),
                        'mac': h.get('mac'),
                        'description': h.get('nickname'), # Mapeando nickname -> description
                        'group_name': h.get('group'),
                        'tags': h.get('tags', []),
                        'ports': h.get('ports', []),
                        'monitoring': h.get('monitoring', True)
                    }
                    hosts_to_save.append(host_data)
                
                if hosts_to_save:
                    db.bulk_save_hosts(hosts_to_save)
                    logging.info(f"Migração concluída: {len(hosts_to_save)} hosts importados.")
                    
                    # Renomear arquivo antigo para backup
                    backup_file = FAVORITES_FILE + ".bak"
                    if not os.path.exists(backup_file):
                        os.rename(FAVORITES_FILE, backup_file)
        except Exception as e:
            logging.error(f"Erro na migração de dados: {e}")

    def load_hosts(self):
        """Carrega a lista de hosts do banco de dados."""
        try:
            db_hosts = db.get_all_hosts()
            # Converter formato do DB para o formato esperado pela UI (compatibilidade)
            self.hosts = []
            for h in db_hosts:
                self.hosts.append({
                    'name': h['hostname'], # UI usa 'name'
                    'ip': h['address'],    # UI usa 'ip'
                    'domain': h.get('domain'),
                    'mac': h['mac'],
                    'nickname': h['description'],
                    'group': h['group_name'],
                    'tags': h['tags'],
                    'ports': h['ports'],
                    'monitoring': bool(h['monitoring']),
                    'vendor': h.get('vendor'),
                    'type': h.get('type'),
                    'teamviewer_id': h.get('teamviewer_id'),
                    'last_checked': h.get('last_checked'),
                    'last_status': bool(h.get('last_status')) if h.get('last_status') is not None else None
                })
        except Exception as e:
            logging.error(f"Erro ao carregar hosts do DB: {e}")
            self.hosts = []

    def save_hosts(self):
        """
        Salva a lista atual de hosts no banco.
        Nota: Idealmente, métodos individuais (add/remove) deveriam chamar o DB diretamente,
        mas mantemos isso para compatibilidade com código legado que manipula self.hosts diretamente.
        """
        try:
            # Converter formato da UI de volta para o DB
            hosts_to_save = []
            for h in self.hosts:
                hosts_to_save.append({
                    'address': h.get('ip'),
                    'hostname': h.get('name'),
                    'domain': h.get('domain'),
                    'mac': h.get('mac'),
                    'description': h.get('nickname'),
                    'group_name': h.get('group'),
                    'tags': h.get('tags', []),
                    'ports': h.get('ports', []),
                    'monitoring': h.get('monitoring', True),
                    'vendor': h.get('vendor'),
                    'type': h.get('type'),
                    'teamviewer_id': h.get('teamviewer_id'),
                    'last_checked': h.get('last_checked'),
                    'last_status': h.get('last_status')
                })
            db.bulk_save_hosts(hosts_to_save)
        except Exception as e:
            logging.error(f"Erro ao salvar hosts no DB: {e}")

    def export_to_json_file(self, file_path: str):
        """Exports the current hosts from DB to an encrypted JSON file."""
        try:
            self.load_hosts() # Ensure we have the latest data from DB
            
            # Fetch Trusted Hosts
            from src.system.winrm import get_trusted_hosts
            trusted_hosts = get_trusted_hosts()

            # Create export structure
            export_data = {
                "hosts": self.hosts,
                "trusted_hosts": trusted_hosts
            }
            
            json_str = json.dumps(export_data, indent=4)
            
            # Encrypt and save
            from src.core.security import SecurityManager
            from src.config.settings import APP_DATA_DIR
            sec_manager = SecurityManager(APP_DATA_DIR)
            sec_manager.save_encrypted_file(file_path, json_str)
            
            logging.info(f"Hosts and TrustedHosts exported successfully (encrypted) to {file_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to export hosts to JSON: {e}")
            return False

    def import_from_json_file(self, file_path: str):
        """Imports hosts and Trusted Hosts from a JSON file (encrypted or plain) into DB and System."""
        try:
            if not os.path.exists(file_path):
                return False, "File not found."

            data = None
            
            # Try to load as encrypted first
            try:
                from src.core.security import SecurityManager
                from src.config.settings import APP_DATA_DIR
                sec_manager = SecurityManager(APP_DATA_DIR)
                json_str = sec_manager.load_encrypted_file(file_path)
                data = json.loads(json_str)
            except Exception:
                # Fallback to plain text (legacy support)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    return False, f"Failed to load file (invalid format or decryption failed): {e}"
            
            if data is None:
                return False, "Failed to parse file data."

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
                 return False, "Invalid JSON format: expected a list of hosts."

            # Update Hosts in DB
            self.update_hosts(hosts_data)

            # Restore Trusted Hosts if present
            if trusted_hosts_data:
                from src.system.winrm import set_trusted_hosts
                set_trusted_hosts(trusted_hosts_data)
                
            logging.info(f"Imported {len(hosts_data)} hosts and {len(trusted_hosts_data)} trusted hosts from {file_path}")
            return True, "Import successful."
        except Exception as e:
            logging.error(f"Failed to import hosts from JSON: {e}")
            return False, str(e)

    def get_all_hosts(self):
        """Retorna todos os hosts."""
        self.load_hosts() # Garantir dados frescos
        return self.hosts

    def add_host(self, new_host_data):
        """Adiciona um novo host à lista e ao banco."""
        name = new_host_data.get('name')
        ip = new_host_data.get('ip')
        
        # Verificar duplicatas em memória (rápido) ou DB
        # Vamos confiar no DB constraint de UNIQUE(address) mas verificar nome também
        # Se name for None ou vazio, não verificar duplicidade de nome
        if any((name and h['name'] == name) or h['ip'] == ip for h in self.hosts):
            return False, "Host com este nome ou IP já existe."
        
        # Salvar no DB
        db_host = {
            'address': ip,
            'hostname': name,
            'mac': new_host_data.get('mac'),
            'description': new_host_data.get('nickname'),
            'group_name': new_host_data.get('group'),
            'tags': new_host_data.get('tags', []),
            'ports': new_host_data.get('ports', []),
            'monitoring': new_host_data.get('monitoring', True),
            'vendor': new_host_data.get('vendor'),
            'type': new_host_data.get('type'),
            'teamviewer_id': new_host_data.get('teamviewer_id')
        }
        
        if db.save_host(db_host):
            self.hosts.append(new_host_data)
            return True, "Host adicionado com sucesso."
        else:
            return False, "Erro ao salvar no banco de dados."

    def remove_hosts(self, hosts_to_remove):
        """Remove uma lista de hosts."""
        for h in hosts_to_remove:
            ip = h.get('ip')
            if ip:
                db.delete_host(ip)
        
        # Atualizar lista em memória
        hosts_to_remove_ips = {h['ip'] for h in hosts_to_remove}
        self.hosts = [h for h in self.hosts if h['ip'] not in hosts_to_remove_ips]

    def update_host_ip(self, host_name, new_ip):
        """Encontra um host pelo nome e atualiza seu endereço IP principal."""
        
        host_found = False
        target_host = None
        
        for host in self.hosts:
            if host['name'] == host_name:
                target_host = host
                break
        
        if target_host:
            old_ip = target_host['ip']
            
            try:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE hosts SET address = ? WHERE address = ?", (new_ip, old_ip))
                    conn.commit()
                
                target_host['ip'] = new_ip
                host_found = True
                logging.debug(f"Host {host_name}: IP atualizado de {old_ip} para {new_ip}")
            except Exception as e:
                logging.error(f"Erro ao atualizar IP no DB: {e}")
                
        return host_found

    def update_host_details(self, ip, hostname=None, domain=None):
        """Atualiza detalhes específicos (hostname, domínio) de um host."""
        host_found = False
        
        # Atualizar em memória
        for host in self.hosts:
            if host['ip'] == ip:
                if hostname: host['name'] = hostname # UI usa 'name' como hostname
                if domain: host['domain'] = domain
                host_found = True
                break
        
        # Atualizar no DB
        if host_found:
            try:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    updates = []
                    params = []
                    
                    if hostname:
                        updates.append("hostname = ?")
                        params.append(hostname)
                    
                    if domain:
                        updates.append("domain = ?")
                        params.append(domain)
                        
                    if updates:
                        params.append(ip)
                        sql = f"UPDATE hosts SET {', '.join(updates)} WHERE address = ?"
                        cursor.execute(sql, params)
                        conn.commit()
                        logging.debug(f"Host {ip}: Detalhes atualizados (Hostname: {hostname}, Domain: {domain})")
                        return True
            except Exception as e:
                logging.error(f"Erro ao atualizar detalhes do host {ip} no DB: {e}")
                
        return False

    def add_secondary_ip(self, host_name, ip, label=None):
        """Adiciona um IP secundário ao host."""
        # SQLite schema atual não suporta secondary_ips explicitamente na tabela principal
        # Vamos armazenar no campo 'tags' ou criar uma tabela relacionada no futuro.
        pass

    def clear_all_hosts(self):
        """Limpa a lista de hosts."""
        try:
            with db._get_connection() as conn:
                conn.execute("DELETE FROM hosts")
                conn.commit()
            self.hosts.clear()
        except Exception as e:
            logging.error(f"Erro ao limpar hosts: {e}")

    def update_hosts(self, updated_hosts_list):
        """Substitui a lista de hosts inteira atomicamente."""
        
        hosts_to_save = []
        for h in updated_hosts_list:
             hosts_to_save.append({
                'address': h.get('ip'),
                'hostname': h.get('name'),
                'domain': h.get('domain'),
                'mac': h.get('mac'),
                'description': h.get('nickname'),
                'group_name': h.get('group'),
                'tags': h.get('tags', []),
                'ports': h.get('ports', []),
                'monitoring': h.get('monitoring', True),
                'vendor': h.get('vendor'),
                'type': h.get('type'),
                'teamviewer_id': h.get('teamviewer_id'),
                'last_checked': h.get('last_checked'),
                'last_status': h.get('last_status')
            })
        
        if db.replace_all_hosts(hosts_to_save):
            self.hosts = updated_hosts_list

    def import_from_csv(self, filepath):
        """Importa hosts de um arquivo CSV."""
        imported_count = 0
        try:
            with open(filepath, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                
                for row in reader:
                    if len(row) < 2: continue
                    
                    name, ip = row[0].strip(), row[1].strip()
                    mac = row[2].strip() if len(row) > 2 else ""
                    nickname = row[3].strip() if len(row) > 3 else ""

                    # Verificar duplicatas
                    if any(h['name'] == name or h['ip'] == ip for h in self.hosts):
                        continue

                    new_host = {
                        "name": name, "ip": ip, "mac": mac, "nickname": nickname
                    }
                    self.add_host(new_host)
                    imported_count += 1
            
            return imported_count
        except Exception as e:
            raise IOError(f"Erro ao importar arquivo: {e}")

    def export_to_csv(self, filepath):
        """Exporta a lista atual de hosts para um arquivo CSV."""
        try:
            with open(filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["name", "ip", "mac", "nickname"])
                for host in self.hosts:
                    writer.writerow([
                        host.get("name", ""),
                        host.get("ip", ""),
                        host.get("mac", ""),
                        host.get("nickname", "")
                    ])
        except Exception as e:
            raise IOError(f"Erro ao exportar arquivo: {e}")