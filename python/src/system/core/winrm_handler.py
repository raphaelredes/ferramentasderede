# src/ferramentasderede/system/core/winrm_handler.py
# Lida com a conexão e execução de comandos via WinRM, com sessão e objeto PowerShell persistentes.

import time
import json
import base64
import logging
import subprocess
from pypsrp.wsman import WSMan
from pypsrp.powershell import PowerShell, RunspacePool, PSInvocationState
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

    @staticmethod
    def _domain_for_target_ip(ip_address):
        """Look up the AD domain configured for the network this IP belongs to.

        Returns the domain string (e.g. "dominio-a.local") or None if no
        configured network matches or if Settings can't be loaded.

        Imported lazily to avoid circular imports between system and api layers.
        """
        try:
            import ipaddress
            from api.routes.settings import load_settings
            settings = load_settings()
            ip_obj = ipaddress.ip_address(ip_address)
            for net in (settings.networks or []):
                if not net.enabled or not net.domain:
                    continue
                try:
                    if ip_obj in ipaddress.ip_network(net.cidr, strict=False):
                        return net.domain
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            logging.debug(f"_domain_for_target_ip failed: {e}")
        return None

    def _username_variants(self):
        """Build the ordered list of username variants to try.

        Heuristics:
          - Always try the user-provided value first.
          - If user@domain: also try domain\\user and netbios\\user.
          - If domain\\user: also try user@domain.
          - If bare 'user' AND the target IP is in a network with a configured
            domain: try user@domain and domain\\user too. This is the
            cross-domain auto-helper — if the analyst on Domínio A tries
            to reach a machine in Domínio B without qualifying, we reach
            for the right qualifier from settings instead of failing fast.
        """
        seen = set()
        variants = []

        def add(u):
            if u and u not in seen:
                seen.add(u)
                variants.append(u)

        add(self.username)

        if "@" in self.username:
            user_part, domain_part = self.username.split("@", 1)
            add(f"{domain_part}\\{user_part}")
            if "." in domain_part:
                add(f"{domain_part.split('.')[0]}\\{user_part}")
        elif "\\" in self.username:
            domain_part, user_part = self.username.split("\\", 1)
            # No reliable way to recover full UPN from a NetBIOS name, but
            # if the input was already FQDN\\user we can flip it.
            if "." in domain_part:
                add(f"{user_part}@{domain_part}")
        else:
            # Bare username — consult settings for the target's domain.
            target_domain = self._domain_for_target_ip(self.target_ip)
            if target_domain:
                add(f"{self.username}@{target_domain}")
                add(f"{target_domain}\\{self.username}")
                if "." in target_domain:
                    add(f"{target_domain.split('.')[0]}\\{self.username}")

        return variants

    def connect(self):
        """Estabelece a conexão e abre um RunspacePool e PowerShell persistentes."""
        last_result = None
        for variant in self._username_variants():
            if variant != self.username:
                logging.info(f"Tentando variante de username: {variant}")
            result = self._try_connect(variant, self.password)
            if result.get("success"):
                self.username = variant
                return result
            last_result = result
            # Don't keep retrying variants if the failure isn't auth-related.
            if result.get("code") not in (None, "AUTH_FAILED", "CROSS_DOMAIN_AUTH"):
                break

        return last_result or {"error": "Falha ao conectar.", "code": "UNKNOWN"}

    def _classify_error(self, exc, method):
        """Classify a WinRM exception into a stable error code + friendly message.

        Codes:
          AUTH_FAILED          — credenciais inválidas
          CROSS_DOMAIN_AUTH    — credenciais válidas mas domínio errado / sem trust
          NETWORK_UNREACHABLE  — sem rota/timeout
          WINRM_DISABLED       — porta 5985 fechada / serviço parado
          TRUSTED_HOSTS_REQUIRED — máquina não está em TrustedHosts
          UNKNOWN              — outros
        """
        msg = str(exc).lower()
        exc_name = type(exc).__name__

        if isinstance(exc, ConnectTimeout) or "timed out" in msg or "timeout" in msg:
            return ("NETWORK_UNREACHABLE",
                    f"Tempo esgotado conectando em {self.target_ip}:5985 ({method}). Verifique rota e firewall.")
        if isinstance(exc, ConnectionError) or "connection refused" in msg or "actively refused" in msg:
            return ("WINRM_DISABLED",
                    f"Porta WinRM (5985) recusada em {self.target_ip}. O serviço WinRM pode estar desabilitado no destino "
                    f"(rode `Enable-PSRemoting -Force` no host alvo).")
        if "no route to host" in msg or "unreachable" in msg or "name or service not known" in msg:
            return ("NETWORK_UNREACHABLE",
                    f"Sem rota até {self.target_ip}. Cheque a NIC e a tabela de rotas (`route print`).")
        if "trusted" in msg and "host" in msg:
            return ("TRUSTED_HOSTS_REQUIRED",
                    f"{self.target_ip} não está em TrustedHosts.")
        # NTLM / Kerberos auth-specific signatures
        if any(t in msg for t in ("kerberos", "spn", "kdc")):
            return ("CROSS_DOMAIN_AUTH",
                    f"Falha Kerberos contra {self.target_ip}. Provável domínio diferente do seu sem relação de confiança. "
                    f"Tente usuário no formato DOMINIO\\usuario ou usuario@dominio.")
        if any(t in msg for t in ("0x80090308", "logon failure", "the user name or password", "unauthorized", "401", "access is denied", "access denied")):
            # Could be wrong password OR wrong domain — give a hint
            if "@" not in self.username and "\\" not in self.username:
                return ("AUTH_FAILED",
                        f"Credenciais recusadas por {self.target_ip}. Em ambiente multi-domínio, "
                        f"informe o usuário como DOMINIO\\usuario ou usuario@dominio.")
            return ("AUTH_FAILED",
                    f"Credenciais recusadas por {self.target_ip} (usuário: {self.username}).")
        return ("UNKNOWN", f"{exc_name}: {exc}")

    def _try_connect(self, username, password):
        """Tenta conectar com um conjunto específico de credenciais."""
        errors = []
        codes = []
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

                self.wsman = wsman
                self.pool = pool
                self.ps = ps
                logging.info(f"Conexão WinRM bem sucedida com método: {method}")
                return {"success": True}

            except Exception as e:
                try:
                    if 'pool' in locals() and pool: pool.close()
                except Exception:
                    pass
                try:
                    if 'wsman' in locals() and wsman: wsman.close()
                except Exception:
                    pass

                code, friendly = self._classify_error(e, method)
                logging.warning(f"WinRM falhou ({method}) [{code}]: {e}")
                logging.debug(f"Detalhes ({method}): {type(e).__name__}: {e}", exc_info=True)
                errors.append(f"{method}: {friendly}")
                codes.append(code)
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
            if current_trusted != "*":
                trusted_list = [h.strip() for h in current_trusted.split(',') if h.strip()]
                if self.target_ip not in trusted_list:
                    logging.warning(f"IP {self.target_ip} não está em TrustedHosts ({current_trusted}).")
                    return {"error": "TRUSTED_HOSTS_REQUIRED", "code": "TRUSTED_HOSTS_REQUIRED",
                            "detail": "O IP alvo não está na lista de TrustedHosts."}

        # Pick the most informative code observed across attempts
        priority = {
            "WINRM_DISABLED": 0,
            "NETWORK_UNREACHABLE": 1,
            "TRUSTED_HOSTS_REQUIRED": 2,
            "CROSS_DOMAIN_AUTH": 3,
            "AUTH_FAILED": 4,
            "UNKNOWN": 5,
        }
        primary_code = sorted(codes, key=lambda c: priority.get(c, 99))[0] if codes else "UNKNOWN"
        # Friendly summary keyed off the primary code, with all per-method details below.
        summary_map = {
            "WINRM_DISABLED": f"WinRM parece desabilitado em {self.target_ip}. Rode `Enable-PSRemoting -Force` no destino.",
            "NETWORK_UNREACHABLE": f"Sem conectividade até {self.target_ip}. Verifique rota e firewall.",
            "TRUSTED_HOSTS_REQUIRED": f"{self.target_ip} não está em TrustedHosts.",
            "CROSS_DOMAIN_AUTH": (f"Autenticação Kerberos falhou contra {self.target_ip}. "
                                  f"Provável domínio diferente sem relação de confiança — tente DOMINIO\\usuario ou usuario@dominio."),
            "AUTH_FAILED": (f"Credenciais recusadas por {self.target_ip} (usuário: {self.username}). "
                            f"Em multi-domínio, informe DOMINIO\\usuario ou usuario@dominio."),
            "UNKNOWN": f"Falha em todos os métodos de autenticação para {self.target_ip}.",
        }
        logging.error(f"WinRM falhou para {self.target_ip}. Código principal: {primary_code}")
        return {
            "error": summary_map[primary_code],
            "code": primary_code,
            "details": errors,
        }

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

        while self.ps.state == PSInvocationState.RUNNING:
            if self.ps.output:
                for line in self.ps.output:
                    s_line = str(line)
                    # Debug log
                    try:
                        with open("terminal_debug.log", "a", encoding="utf-8") as f:
                            f.write(f"OUT: {s_line}\n")
                    except: pass
                    yield s_line + "\n"
                self.ps.output.clear()
            
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
        if self.ps.output:
            for line in self.ps.output:
                s_line = str(line)
                try:
                    with open("terminal_debug.log", "a", encoding="utf-8") as f:
                        f.write(f"OUT (FINAL): {s_line}\n")
                except: pass
                yield s_line + "\n"
            self.ps.output.clear()

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
        """Retorna a lista atual de TrustedHosts via Registry (evita PowerShell/AV)."""
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN\Client"
            # OpenKey defaults to KEY_READ
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                value, type_ = winreg.QueryValueEx(key, "TrustedHosts")
                return value
        except FileNotFoundError:
            return ""
        except Exception as e:
            logging.error(f"Erro ao obter TrustedHosts via Registry: {e}")
            return ""

    @staticmethod
    def set_trusted_hosts(value):
        """Define o valor de TrustedHosts via Registry (evita PowerShell/AV)."""
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN\Client"
            # Precisamos de acesso de escrita
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "TrustedHosts", 0, winreg.REG_SZ, value)
            return True
        except Exception as e:
            logging.error(f"Erro ao definir TrustedHosts via Registry: {e}")
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