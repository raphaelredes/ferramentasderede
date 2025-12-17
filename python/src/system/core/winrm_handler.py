# src/ferramentasderede/system/core/winrm_handler.py
# Lida com a conexão e execução de comandos via WinRM, com sessão e objeto PowerShell persistentes.

import time
import json
import base64
import logging
import subprocess
from pypsrp.wsman import WSMan
from pypsrp.powershell import PowerShell, RunspacePool
from pypsrp.exceptions import WinRMError
from requests.exceptions import ConnectionError, ConnectTimeout

class WinRMHandler:
    def __init__(self, target_ip, username, password):
        self.target_ip = target_ip
        self.username = username
        self.password = password
        self.wsman = None
        self.pool = None
        self.ps = None  # Objeto PowerShell persistente

    def connect(self):
        """Estabelece a conexão e abre um RunspacePool e PowerShell persistentes."""
        
        # Tentativa 1: Credenciais originais
        result = self._try_connect(self.username, self.password)
        if result.get("success"):
            return result

        # Tentativa 2: Se falhar e for email (UPN), tentar formato DOMAIN\User
        if "@" in self.username:
            try:
                user_part, domain_part = self.username.split("@", 1)
                # Tenta tanto com o domínio completo quanto com a primeira parte (chute para NetBIOS)
                alt_usernames = [f"{domain_part}\\{user_part}"]
                if "." in domain_part:
                    alt_usernames.append(f"{domain_part.split('.')[0]}\\{user_part}")

                for alt_user in alt_usernames:
                    logging.info(f"Tentando autenticação com formato alternativo: {alt_user}")
                    result_alt = self._try_connect(alt_user, self.password)
                    if result_alt.get("success"):
                        self.username = alt_user # Atualiza para usos futuros
                        return result_alt
            except Exception as e:
                logging.error(f"Erro ao tentar formatos alternativos de usuário: {e}")

        return result

    def _try_connect(self, username, password):
        """Tenta conectar com um conjunto específico de credenciais."""
        errors = []
        auth_methods = ['negotiate', 'ntlm', 'credssp']
        
        for method in auth_methods:
            try:
                logging.info(f"Tentando conexão WinRM com método: {method} para {self.target_ip} (User: {username})")
                
                wsman = WSMan(
                    server=self.target_ip, username=username, password=password,
                    ssl=False, connection_timeout=20, auth_method=method
                )
                pool = RunspacePool(wsman, configuration_name='Microsoft.PowerShell')
                pool.open()
                ps = PowerShell(pool)
                
                # Se sucesso, salva na instância
                self.wsman = wsman
                self.pool = pool
                self.ps = ps
                logging.info(f"Conexão WinRM bem sucedida com método: {method}")
                return {"success": True}
                
            except Exception as e:
                # Limpa recursos locais se falhar
                try: 
                    if 'pool' in locals() and pool: pool.close()
                except: pass
                try: 
                    if 'wsman' in locals() and wsman: wsman.close()
                except: pass
                
                error_str = str(e)
                logging.warning(f"Falha na autenticação WinRM ({method}): {error_str}")
                logging.debug(f"Detalhes do erro WinRM ({method}): {type(e).__name__}: {e}", exc_info=True)
                errors.append(f"{method}: {error_str}")
            except:
                pass
            self.pool = None
        
        if self.wsman:
            try:
                ps = PowerShell(pool)
                
                self.wsman = wsman
                self.pool = pool
                self.ps = ps
                logging.info("Conexão fallback localhost bem sucedida!")
                return {"success": True}
            except Exception as e:
                logging.warning(f"Fallback localhost falhou: {e}")
                errors.append(f"localhost_fallback: {e}")

        # Se falhou e não é localhost, verifica se é problema de TrustedHosts
        if self.target_ip not in ["127.0.0.1", "localhost"]:
            current_trusted = WinRMHandler.get_trusted_hosts()
            logging.info(f"Verificando TrustedHosts. Atual: '{current_trusted}', Alvo: '{self.target_ip}'")
            # Se não for *, verifica se o IP está na lista
            if current_trusted != "*":
                trusted_list = [h.strip() for h in current_trusted.split(',') if h.strip()]
                if self.target_ip not in trusted_list:
                    logging.warning(f"IP {self.target_ip} não está em TrustedHosts ({current_trusted}). Retornando erro TRUSTED_HOSTS_REQUIRED.")
                    return {"error": "TRUSTED_HOSTS_REQUIRED", "detail": "O IP alvo não está na lista de TrustedHosts."}

        logging.error(f"Falha em todos os métodos de autenticação para {self.target_ip}. Erros: {errors}")
        return {"error": "Falha em todos os métodos de autenticação:\n" + "\n".join(errors)}

    def close(self):
        """Fecha o RunspacePool e a conexão WSMan."""
        if self.pool:
            try:
                self.pool.close()
            except:
                pass
            self.pool = None
        if self.wsman:
            try:
                self.wsman.close()
            except:
                pass
            self.wsman = None
        self.ps = None

    def _clear_powershell_state(self):
        """Garante que a instância do PowerShell esteja limpa para um novo comando."""
        if self.ps:
            self.ps.commands.clear()
            # Limpa os streams individuais, pois ps.streams.clear() não existe
            # O stream 'output' é tratado de forma diferente no streaming e não precisa/deve ser limpo aqui.
            self.ps.streams.error.clear()
            self.ps.streams.verbose.clear()
            self.ps.streams.warning.clear()
            self.ps.streams.information.clear()
            self.ps.streams.debug.clear()

    def execute_script(self, script: str):
        """Executa um script simples e retorna a saída completa."""
        if not self.pool:
            return {"error": "Conexão não está ativa (pool não existe)."}
        
        # Cria uma nova instância de PowerShell para cada execução
        ps = PowerShell(self.pool)
        ps.add_script(script)
        output_list = ps.invoke()

        if ps.had_errors:
            error_msg = ""
            if ps.streams.error:
                error_msg = "\n".join([str(e) for e in ps.streams.error])
            else:
                error_msg = "Erro desconhecido no script PowerShell."
            
            # Escreve o erro no arquivo Errors.txt
            try:
                with open("Errors.txt", "a", encoding="utf-8") as f:
                    f.write(f"--- ERRO POWERSHELL ---\n{error_msg}\n-----------------------\n")
            except Exception as log_e:
                print(f"Falha ao escrever no Errors.txt: {log_e}")

            return {"error": f"Erro no Script Remoto: {error_msg}"}
        
        return {"success": True, "output": output_list}

    def execute_streaming_command(self, command: str):
        """Executa um comando e transmite a saída (stdout e stderr) em tempo real."""
        if not self.ps:
            yield "ERRO: Conexão não está ativa.\n"
            return

        self._clear_powershell_state()
        
        # Wrap in script block to handle native commands and merge streams
        # & { ... } ensures it runs as a block
        # *>&1 merges all streams (Error, Warning, etc.) into Success stream
        # Out-String -Stream ensures we get text lines
        ps_script = f"& {{ {command} }} *>&1 | Out-String -Stream"
        self.ps.add_script(f"$OutputEncoding = [System.Text.Encoding]::UTF8; {ps_script}")
        
        self.ps.begin_invoke()

        # Debug log
        try:
            with open("terminal_debug.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- CMD: {command} ---\n")
        except: pass

        while self.ps.invocation_state_info.state == 'Running':
            if self.ps.streams.output:
                for line in self.ps.streams.output:
                    s_line = str(line)
                    # Debug log
                    try:
                        with open("terminal_debug.log", "a", encoding="utf-8") as f:
                            f.write(f"OUT: {s_line}\n")
                    except: pass
                    yield s_line + "\n"
                self.ps.streams.output.clear()
            
            if self.ps.streams.error:
                for error in self.ps.streams.error:
                    s_err = str(error)
                    try:
                        with open("terminal_debug.log", "a", encoding="utf-8") as f:
                            f.write(f"ERR: {s_err}\n")
                    except: pass
                    yield f"ERRO: {s_err}\n"
                self.ps.streams.error.clear()
            
            time.sleep(0.1)

        # Pega qualquer saída restante
        if self.ps.streams.output:
            for line in self.ps.streams.output:
                s_line = str(line)
                try:
                    with open("terminal_debug.log", "a", encoding="utf-8") as f:
                        f.write(f"OUT (FINAL): {s_line}\n")
                except: pass
                yield s_line + "\n"
            self.ps.streams.output.clear()

        if self.ps.had_errors and self.ps.streams.error:
            for error in self.ps.streams.error:
                s_err = str(error)
                try:
                    with open("terminal_debug.log", "a", encoding="utf-8") as f:
                        f.write(f"ERR (FINAL): {s_err}\n")
                except: pass
                yield f"ERRO FINAL: {s_err}\n"
            self.ps.streams.error.clear()

    @staticmethod
    def get_trusted_hosts():
        """Retorna a lista atual de TrustedHosts."""
        try:
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", 
                   "(Get-Item WSMan:\\localhost\\Client\\TrustedHosts).Value"]
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.stdout.strip()
        except Exception as e:
            logging.error(f"Erro ao obter TrustedHosts: {e}")
            return ""

    @staticmethod
    def set_trusted_hosts(value):
        """Define o valor de TrustedHosts."""
        try:
            # Escape aspas simples se houver (embora IPs não tenham)
            safe_value = value.replace("'", "''")
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", 
                   f"Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value '{safe_value}' -Force"]
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Erro ao definir TrustedHosts: {e}")
            return False

    @staticmethod
    def add_trusted_host(ip):
        """Adiciona um IP aos TrustedHosts se não estiver lá."""
        current = WinRMHandler.get_trusted_hosts()
        if current == "*":
            return True # Já aceita tudo
        
        hosts = [h.strip() for h in current.split(',') if h.strip()]
        if ip in hosts:
            return True # Já está na lista

        new_value = f"{current}, {ip}" if current else ip
        return WinRMHandler.set_trusted_hosts(new_value)

    @staticmethod
    def remove_trusted_host(ip):
        """Remove um IP dos TrustedHosts."""
        current = WinRMHandler.get_trusted_hosts()
        if current == "*":
            return False # Não removemos se for wildcard global (configuração do usuário)
        
        hosts = [h.strip() for h in current.split(',') if h.strip()]
        if ip in hosts:
            hosts.remove(ip)
            new_value = ", ".join(hosts)
            return WinRMHandler.set_trusted_hosts(new_value)
        return True

class TemporaryTrustedHosts:
    """Context Manager para adicionar temporariamente um IP aos TrustedHosts."""
    def __init__(self, ip):
        self.ip = ip
        self.added = False

    def __enter__(self):
        # Verifica se já é confiável
        current = WinRMHandler.get_trusted_hosts()
        if current == "*" or self.ip in [h.strip() for h in current.split(',') if h.strip()]:
            self.added = False
            return self

        # Tenta adicionar
        if WinRMHandler.add_trusted_host(self.ip):
            self.added = True
        else:
            logging.error(f"Falha ao adicionar {self.ip} aos TrustedHosts temporariamente.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.added:
            WinRMHandler.remove_trusted_host(self.ip)