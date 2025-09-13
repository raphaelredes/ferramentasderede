# app/host_manager.py
# Gerencia a lógica de dados para a lista de hosts: carregar, salvar, adicionar, remover, etc.

import os
import json
import csv
import logging
from src.config.settings import FAVORITES_FILE

class HostManager:
    def __init__(self):
        self.hosts = []
        self.load_hosts()

    def load_hosts(self):
        """Carrega a lista de hosts do arquivo JSON."""
        try:
            if os.path.exists(FAVORITES_FILE):
                with open(FAVORITES_FILE, "r") as f:
                    self.hosts = json.load(f)
            else:
                self.hosts = [{"name": "localhost", "ip": "127.0.0.1", "mac": "", "nickname": ""}]
                self.save_hosts()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Erro ao carregar hosts: {e}")
            self.hosts = []

    def save_hosts(self):
        """Salva a lista atual de hosts no arquivo JSON."""
        try:
            with open(FAVORITES_FILE, "w") as f:
                json.dump(self.hosts, f, indent=4)
        except Exception as e:
            logging.error(f"Erro ao salvar hosts: {e}")

    def get_all_hosts(self):
        """Retorna uma cópia da lista de hosts."""
        return list(self.hosts)

    def add_host(self, new_host_data):
        """Adiciona um novo host à lista e salva. Retorna True se bem-sucedido."""
        name = new_host_data['name']
        ip = new_host_data['ip']
        if any(h['name'] == name or h['ip'] == ip for h in self.hosts):
            return False, "Host com este nome ou IP já existe."
        
        self.hosts.append(new_host_data)
        self.save_hosts()
        return True, "Host adicionado com sucesso."

    def remove_hosts(self, hosts_to_remove):
        """Remove uma lista de hosts e salva as alterações."""
        hosts_to_remove_names = {h['name'] for h in hosts_to_remove}
        self.hosts = [h for h in self.hosts if h['name'] not in hosts_to_remove_names]
        self.save_hosts()

    def update_host_ip(self, host_name, new_ip):
        """Encontra um host pelo nome e atualiza seu endereço IP principal."""
        host_found = False
        for host in self.hosts:
            if host['name'] == host_name:
                old_ip = host['ip']
                host['ip'] = new_ip
                host_found = True
                logging.debug(f"Host {host_name}: IP atualizado de {old_ip} para {new_ip}")
                break
        if host_found:
            self.save_hosts()
            logging.debug(f"Hosts salvos após atualização do IP para {host_name}")
        else:
            logging.warning(f"Host {host_name} não encontrado para atualização de IP")
        return host_found

    def add_secondary_ip(self, host_name, ip, label=None):
        """Adiciona um IP secundário ao host, com rótulo opcional (ex.: Wi‑Fi, Ethernet)."""
        for host in self.hosts:
            if host['name'] == host_name:
                secondary = host.get('secondary_ips') or []
                # Evitar duplicatas
                if not any(entry.get('ip') == ip for entry in secondary):
                    secondary.append({'ip': ip, 'label': label or ''})
                    host['secondary_ips'] = secondary
                    self.save_hosts()
                return True
        return False

    def clear_all_hosts(self):
        """Limpa a lista de hosts em memória e salva o estado vazio no disco."""
        self.hosts.clear()
        self.save_hosts()

    def update_hosts(self, updated_hosts_list):
        """Substitui a lista de hosts inteira. Usado para reordenar/renomear."""
        self.hosts = updated_hosts_list
        self.save_hosts()

    def import_from_csv(self, filepath):
        """Importa hosts de um arquivo CSV, ignorando duplicatas."""
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

                    if not any(h['name'] == name or h['ip'] == ip for h in self.hosts):
                        self.hosts.append({
                            "name": name, "ip": ip, "mac": mac, "nickname": nickname
                        })
                        imported_count += 1
            
            if imported_count > 0:
                self.save_hosts()
            return imported_count
        except Exception as e: # Consider more specific exceptions if possible
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
            # The exception is re-raised, so logging here might be redundant if caller logs
            raise IOError(f"Erro ao exportar arquivo: {e}")