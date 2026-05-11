import os
import subprocess
import re
import logging

def get_mac_from_arp(ip_address=None):
    """
    Obtém o endereço MAC de um IP usando a tabela ARP local.
    Se ip_address for None, retorna uma lista de dicionários {'ip': ip, 'mac': mac} com toda a tabela ARP.
    """
    try:
        if os.name == 'nt':
            # No Windows, arp -a exibe a tabela
            if ip_address:
                cmd = ["arp", "-a", ip_address]
            else:
                cmd = ["arp", "-a"]
            encoding = 'cp850'
        else:
            if ip_address:
                cmd = ["arp", "-n", ip_address]
            else:
                cmd = ["arp", "-n"]
            encoding = 'utf-8'

            # Executa o comando arp
            result = subprocess.run(cmd, capture_output=True, text=True, encoding=encoding, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, timeout=2)
        output = result.stdout
        
        if ip_address:
            # Comportamento original: retorna apenas o MAC do IP específico
            mac_regex = r"([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})"
            matches = re.finditer(mac_regex, output)
            for match in matches:
                mac = match.group(0).replace('-', ':').upper()
                if mac != "FF:FF:FF:FF:FF:FF":
                    return mac
            return None
        else:
            # Novo comportamento: retorna lista de entradas
            entries = []
            
            lines = output.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # Tentar extrair IP e MAC
                # Regex mais flexível para capturar IP e MAC na mesma linha
                # Exemplo Windows: 192.168.1.1          10-00-00-00-00-01     dynamic
                # Exemplo Linux: ? (192.168.1.1) at 10:00:00:00:00:01 [ether] on eth0
                
                # Procura por IP seguido de algo e depois MAC
                # IP: \d{1,3}(?:\.\d{1,3}){3}
                # MAC: (?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}
                
                match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})\s+((?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})", line)
                
                if match:
                    ip = match.group(1)
                    mac = match.group(2).replace('-', ':').upper()
                    
                    # Ignorar broadcast/multicast
                    if mac == "FF:FF:FF:FF:FF:FF" or ip.startswith("224.") or ip.endswith(".255"):
                        continue
                        
                    entries.append({"ip": ip, "mac": mac})
            
            return entries

    except Exception as e:
        # logging.error(f"Erro ao obter MAC para {ip_address}: {e}")
        return None if ip_address else []

    # Fallback: Se a busca específica falhou (ou retornou nada), tentar pegar a tabela completa
    # Isso ajuda quando "arp -a IP" não retorna nada mas o IP está na tabela geral
    if ip_address:
        try:
            full_table = get_mac_from_arp(None) # Chamada recursiva para pegar tudo
            for entry in full_table:
                if entry['ip'] == ip_address:
                    return entry['mac']
        except Exception as e:
            logging.debug(f"ARP full-table fallback for {ip_address} failed: {e}")
            
    return None

def get_mac_from_netbios(ip_address):
    """Obtém o endereço MAC de um IP usando NetBIOS (nbtstat)."""
    try:
        if os.name == 'nt':
            # nbtstat -A <IP>
            cmd = ["nbtstat", "-A", ip_address]
            encoding = 'cp850'
            
            # Adicionar timeout e flags para evitar janela
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding=encoding, 
                errors='replace', 
                creationflags=subprocess.CREATE_NO_WINDOW, 
                timeout=3
            )
            output = result.stdout
            
            # Procura por "MAC Address = XX-XX-XX-XX-XX-XX" ou "Endereço MAC = ..."
            # Regex flexível para hífens ou dois pontos
            mac_regex = r"([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})"
            match = re.search(mac_regex, output)
            
            if match:
                return match.group(0).replace('-', ':').upper()
        
        return None
    except Exception as e:
        # logging.error(f"Erro ao obter MAC via NetBIOS para {ip_address}: {e}")
        return None

def resolve_mac_address(ip_address):
    """Tenta resolver o MAC address usando ARP e depois NetBIOS (se Windows)."""
    mac = get_mac_from_arp(ip_address)
    if not mac and os.name == 'nt':
        mac = get_mac_from_netbios(ip_address)
    return mac
