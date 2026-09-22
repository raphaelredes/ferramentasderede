# src/ferramentasderede/system/core/winrm_handler.py
# Lida com a conexão e execução de comandos via WinRM, com sessão e objeto PowerShell persistentes.

import time
import os
import json
import base64
import logging
import subprocess
from pypsrp.wsman import WSMan
from pypsrp.powershell import PowerShell, RunspacePool, PSInvocationState
from pypsrp.exceptions import WinRMError
from requests.exceptions import ConnectionError, ConnectTimeout

# Log files used to live in the CWD (wherever the app happened to be launched
# from), which made them invisible in production builds and littered the user's
# Desktop in dev. Now they live next to the app's data so a user / support
# person knows exactly where to look.
try:
    from src.config.settings import APP_DATA_DIR as _APP_DATA_DIR
except Exception:
    _APP_DATA_DIR = os.path.expanduser("~")

_ERRORS_LOG = os.path.join(_APP_DATA_DIR, "errors.log")
_TERMINAL_LOG = os.path.join(_APP_DATA_DIR, "terminal_debug.log")


def _append_log(path, text):
    """Best-effort log append. Never raises — if it can't write, it's gone."""
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass

class WinRMHandler:
    def __init__(self, target_ip, username, password, target_hostname=None):
        self.target_ip = target_ip
        self.username = username
        self.password = password
        resolved_fqdn, resolved_domain = self._resolve_target_fqdn_and_domain(target_ip)
        self.target_hostname = target_hostname or resolved_fqdn
        self.target_domain = resolved_domain
        self.wsman = None
        self.pool = None
        self.ps = None  # Objeto PowerShell persistente

    @classmethod
    def _resolve_target_fqdn_and_domain(cls, target_ip):
        """Resolve o IP alvo para um FQDN e domínio estritamente validados por DNS direto.

        Garante que qualquer FQDN retornado resolva de volta para target_ip via DNS,
        evitando contaminação de sufixo de domínio (ex: ADM-36494 resolvendo para
        10.212.134.100 no domínio local betim.pmb quando o alvo real é 10.10.90.7 no domínio saude.betim).
        """
        import re
        import socket
        if not target_ip or not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", target_ip):
            return target_ip, None

        short_name = None
        cand_domain = None

        # 1. Consulta o host no banco de dados local
        try:
            from api.routes.network import host_manager_instance
            for h in host_manager_instance.get_all_hosts():
                if h.get("ip") == target_ip or h.get("address") == target_ip:
                    cand = h.get("name") or h.get("hostname")
                    if cand and cand != target_ip:
                        short_name = cand.split(".")[0]
                    dom = h.get("domain")
                    if dom and dom not in ("N/A", "Unknown", "local"):
                        cand_domain = dom
                    break
        except Exception:
            pass

        # 2. DNS reverso se short_name ainda não conhecido
        if not short_name:
            try:
                rev_name = socket.gethostbyaddr(target_ip)[0]
                if rev_name and rev_name != target_ip:
                    if "." in rev_name:
                        try:
                            if socket.gethostbyname(rev_name) == target_ip:
                                return rev_name, rev_name.split(".", 1)[1]
                        except Exception:
                            pass
                        short_name = rev_name.split(".")[0]
                    else:
                        short_name = rev_name
            except Exception:
                pass

        if not short_name:
            return None, None

        # 3. Coleta domínios candidatos para testar resolução direta
        candidates = []
        seen = set()

        def add_c(d):
            if d and isinstance(d, str):
                c = d.strip()
                if c and c.lower() not in seen and c.lower() not in ("n/a", "unknown", "local"):
                    seen.add(c.lower())
                    candidates.append(c)

        if cand_domain:
            add_c(cand_domain)

        # Domínio configurado na rede do alvo em Configurações
        add_c(cls._domain_for_target_ip(target_ip))

        # Domínio gravado no current_user do host
        try:
            from api.routes.network import host_manager_instance
            for h in host_manager_instance.get_all_hosts():
                if h.get("ip") == target_ip or h.get("address") == target_ip:
                    cu = h.get("current_user")
                    if cu and "\\" in cu:
                        add_c(cu.split("\\")[0])
                    elif cu and "@" in cu:
                        add_c(cu.split("@")[1])
        except Exception:
            pass

        # Domínios de confiança conhecidos da floresta / rede corporativa
        for known in ("saude.betim", "betim.pmb", "transbetim.betim", "betim.mg", "semed.betim"):
            add_c(known)

        # Todas as redes cadastradas em Configurações
        try:
            from api.routes.settings import load_settings
            settings = load_settings()
            for net in (settings.networks or []):
                if net.enabled and net.domain:
                    add_c(net.domain)
        except Exception:
            pass

        add_c(os.environ.get("USERDNSDOMAIN"))
        add_c(os.environ.get("USERDOMAIN"))

        # 4. Testa cada FQDN candidato com resolução direta para bater com target_ip
        for d in candidates:
            fqdn_candidate = f"{short_name}.{d}"
            try:
                resolved_ip = socket.gethostbyname(fqdn_candidate)
                if resolved_ip == target_ip:
                    # Persiste o domínio descoberto no host_manager se estava ausente
                    try:
                        from api.routes.network import host_manager_instance
                        host_manager_instance.update_host_details(target_ip, hostname=short_name, domain=d)
                    except Exception:
                        pass
                    return fqdn_candidate, d
            except Exception:
                continue

        # 5. Se nenhum domínio candidato casou, verifica se o short_name sozinho resolve para o IP correto
        try:
            if socket.gethostbyname(short_name) == target_ip:
                return short_name, None
        except Exception:
            pass

        # NUNCA retorna um short_name que resolve para outro IP diferente de target_ip!
        return None, None

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

    def _candidate_domains(self):
        """Coleta domínios potenciais associados ao alvo ou ambiente operacional."""
        seen = set()
        candidates = []

        def add(d):
            if d and isinstance(d, str):
                cleaned = d.strip()
                if cleaned and cleaned not in seen and cleaned.lower() not in ("n/a", "unknown", "local"):
                    seen.add(cleaned)
                    candidates.append(cleaned)

        # 0. Domínio validado do alvo (prioridade máxima)
        if getattr(self, 'target_domain', None):
            add(self.target_domain)

        # 1. Domínio configurado na rede do alvo em Configurações
        add(self._domain_for_target_ip(self.target_ip))

        # 2. Domínio e usuário gravados no banco de dados para este host
        try:
            from api.routes.network import host_manager_instance
            for h in host_manager_instance.get_all_hosts():
                if h.get("ip") == self.target_ip or h.get("address") == self.target_ip:
                    add(h.get("domain"))
                    cu = h.get("current_user")
                    if cu and "\\" in cu:
                        add(cu.split("\\")[0])
                    elif cu and "@" in cu:
                        add(cu.split("@")[1])
        except Exception:
            pass

        # 3. Todos os domínios de redes cadastradas em Configurações
        try:
            from api.routes.settings import load_settings
            settings = load_settings()
            for net in (settings.networks or []):
                if net.enabled and net.domain:
                    add(net.domain)
        except Exception:
            pass

        # 4. Domínio do computador local (AD)
        add(os.environ.get("USERDNSDOMAIN"))
        add(os.environ.get("USERDOMAIN"))

        return candidates

    @staticmethod
    def _mask_username(username):
        """Mask a username for log / error messages.

        Multi-domain operators see DOMAIN\\user (or user@domain). The full
        string used to be echoed into the response `error` field and the log,
        which is an info-disclosure for anyone with read access to either.
        Keep the domain (operationally useful) and last 2 chars of the user
        for sanity — drop the rest."""
        if not username or not isinstance(username, str):
            return "???"
        # Split off domain prefix/suffix so we keep that part visible.
        if "@" in username:
            user_part, domain_part = username.split("@", 1)
            tail = user_part[-2:] if len(user_part) >= 2 else "*"
            return f"***{tail}@{domain_part}"
        if "\\" in username:
            domain_part, user_part = username.split("\\", 1)
            tail = user_part[-2:] if len(user_part) >= 2 else "*"
            return f"{domain_part}\\***{tail}"
        tail = username[-2:] if len(username) >= 2 else "*"
        return f"***{tail}"

    def _username_variants(self):
        """Build the ordered list of username variants to try.

        Heuristics:
          - Always try the user-provided value first.
          - If user@domain: also try domain\\user and netbios\\user.
          - If domain\\user with FQDN: also try user@domain AND netbios\\user (essential for NTLM).
          - If domain\\user with NetBIOS: also try user@fqdn using candidate domains.
          - If target_domain is known and differs from provided domain: also try target_domain variants.
          - If bare 'user': try target_domain variants, then candidate domains.
        """
        seen = set()
        variants = []

        def add(u):
            if u and u not in seen:
                seen.add(u)
                variants.append(u)

        add(self.username)
        candidate_domains = self._candidate_domains()
        tgt_domain = getattr(self, 'target_domain', None)

        if "@" in self.username:
            user_part, domain_part = self.username.split("@", 1)
            add(f"{domain_part}\\{user_part}")
            if "." in domain_part:
                add(f"{domain_part.split('.')[0]}\\{user_part}")
            # Se o alvo está em outro domínio, tenta variantes no domínio do alvo
            if tgt_domain and domain_part.lower() != tgt_domain.lower():
                add(f"{tgt_domain}\\{user_part}")
                add(f"{tgt_domain.split('.')[0]}\\{user_part}")
                add(f"{user_part}@{tgt_domain}")
            add(user_part)
        elif "\\" in self.username:
            domain_part, user_part = self.username.split("\\", 1)
            if "." in domain_part:
                # FQDN\user -> UPN (user@domain) and NetBIOS (netbios\user)
                add(f"{user_part}@{domain_part}")
                add(f"{domain_part.split('.')[0]}\\{user_part}")
            else:
                # NetBIOS\user -> try UPN with candidate DNS domains
                for cd in candidate_domains:
                    if "." in cd and cd.lower().startswith(domain_part.lower()):
                        add(f"{user_part}@{cd}")
                # Also try UPN with raw domain_part
                add(f"{user_part}@{domain_part}")
            # Se o alvo está em outro domínio, tenta variantes no domínio do alvo
            if tgt_domain and domain_part.lower() not in (tgt_domain.lower(), tgt_domain.split(".")[0].lower()):
                add(f"{tgt_domain}\\{user_part}")
                add(f"{tgt_domain.split('.')[0]}\\{user_part}")
                add(f"{user_part}@{tgt_domain}")
            add(user_part)
        else:
            # Bare username
            if tgt_domain:
                add(f"{tgt_domain.split('.')[0]}\\{self.username}")
                add(f"{self.username}@{tgt_domain}")
                add(f"{tgt_domain}\\{self.username}")
            for cd in candidate_domains:
                if "." in cd:
                    netbios = cd.split('.')[0]
                    add(f"{netbios}\\{self.username}")
                    add(f"{self.username}@{cd}")
                    add(f"{cd}\\{self.username}")
                else:
                    add(f"{cd}\\{self.username}")
                    add(f"{self.username}@{cd}")

        return variants

    def connect(self):
        """Estabelece a conexão e abre um RunspacePool e PowerShell persistentes.

        On success, the password is purged from this handler's attributes —
        pypsrp keeps its own copy internally, so subsequent execute_script
        calls still work, but the value is no longer sitting on `self` for
        the lifetime of the websocket / handler instance.
        """
        last_result = None
        had_qualified_auth_fail = False
        variants = self._username_variants()
        for variant in variants:
            if variant != self.username:
                logging.debug(f"Tentando variante de username: {self._mask_username(variant)}")
            result = self._try_connect(variant, self.password)
            if result.get("success"):
                self.username = variant
                self.password = None
                return result
            last_result = result
            # Don't keep retrying variants if the failure isn't auth-related (e.g. host down/port closed).
            if result.get("code") not in (None, "AUTH_FAILED", "CROSS_DOMAIN_AUTH"):
                break
            # If we already failed with a qualified form, avoid retrying bare form
            if "\\" in variant or "@" in variant:
                had_qualified_auth_fail = True
            if had_qualified_auth_fail and len(variants) <= 2:
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
                    f"Falha Kerberos contra {self.target_ip} ({method}). Provável domínio diferente do seu sem relação de confiança. "
                    f"Tente usuário no formato DOMINIO\\usuario ou usuario@dominio.")
        if (any(t in msg for t in ("0x80090308", "logon failure", "the user name or password", "unauthorized",
                                   "401", "access is denied", "access denied", "failed to authenticate"))
                or "authentication" in exc_name.lower()):
            if "@" not in self.username and "\\" not in self.username:
                return ("AUTH_FAILED",
                        f"Credenciais recusadas por {self.target_ip} ({method}). Em ambiente multi-domínio, "
                        f"informe o usuário como DOMINIO\\usuario ou usuario@dominio.")
            return ("AUTH_FAILED",
                    f"Credenciais recusadas por {self.target_ip} ({method}) (usuário: {self._mask_username(self.username)}).")
        return ("UNKNOWN", f"{exc_name}: {exc}")

    def _try_connect(self, username, password):
        """Tenta conectar com um conjunto específico de credenciais."""
        errors = []
        codes = []
        auth_methods = ['negotiate', 'ntlm']

        for method in auth_methods:
            try:
                logging.info(f"Tentando conexão WinRM com método: {method} para {self.target_ip} (User: {self._mask_username(username)})")

                ws_kwargs = {
                    "server": self.target_ip,
                    "username": username,
                    "password": password,
                    "ssl": False,
                    "connection_timeout": 20,
                    "auth": method,  # pypsrp parameter is 'auth', NOT 'auth_method'!
                }
                if self.target_hostname:
                    ws_kwargs["negotiate_hostname_override"] = self.target_hostname

                wsman = WSMan(**ws_kwargs)
                pool = RunspacePool(wsman, configuration_name='Microsoft.PowerShell')
                pool.open()
                ps = PowerShell(pool)

                self.wsman = wsman
                self.pool = pool
                self.ps = ps
                logging.info(f"Conexão WinRM bem sucedida com método: {method} (User: {self._mask_username(username)})")
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

        # Se conectar por IP com negotiate e ntlm falhou e tivermos hostname de domínio resolvido, tenta conectar direto pelo hostname
        if self.target_hostname and self.target_hostname != self.target_ip:
            try:
                logging.info(f"Tentando fallback WinRM via hostname: {self.target_hostname} com negotiate (User: {self._mask_username(username)})")
                wsman = WSMan(
                    server=self.target_hostname,
                    username=username,
                    password=password,
                    ssl=False,
                    connection_timeout=15,
                    auth='negotiate'
                )
                pool = RunspacePool(wsman, configuration_name='Microsoft.PowerShell')
                pool.open()
                ps = PowerShell(pool)
                self.wsman = wsman
                self.pool = pool
                self.ps = ps
                logging.info(f"Conexão WinRM bem sucedida via hostname: {self.target_hostname}")
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
                code, friendly = self._classify_error(e, f"hostname:{self.target_hostname}")
                logging.warning(f"WinRM falhou via hostname ({self.target_hostname}): {e}")
                errors.append(f"hostname ({self.target_hostname}): {friendly}")
                codes.append(code)
            self.pool = None

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

        # Hierarchy: If any attempt proved the target was reachable and rejected auth,
        # the primary code must reflect authentication failure, NOT network unreachable!
        priority = {
            "CROSS_DOMAIN_AUTH": 0,
            "AUTH_FAILED": 1,
            "TRUSTED_HOSTS_REQUIRED": 2,
            "WINRM_DISABLED": 3,
            "NETWORK_UNREACHABLE": 4,
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
            "AUTH_FAILED": (f"Credenciais recusadas por {self.target_ip} (usuário: {self._mask_username(self.username)}). "
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
            except Exception as e:
                logging.debug(f"pool.close() failed: {e}")
            self.pool = None
        if self.wsman:
            try:
                self.wsman.close()
            except Exception as e:
                logging.debug(f"wsman.close() failed: {e}")
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
            
            _append_log(_ERRORS_LOG, f"--- ERRO POWERSHELL ---\n{error_msg}\n-----------------------\n")

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

        _append_log(_TERMINAL_LOG, f"\n--- CMD: {command} ---\n")

        while self.ps.state == PSInvocationState.RUNNING:
            if self.ps.output:
                for line in self.ps.output:
                    s_line = str(line)
                    _append_log(_TERMINAL_LOG, f"OUT: {s_line}\n")
                    yield s_line + "\n"
                self.ps.output.clear()

            if self.ps.streams.error:
                for error in self.ps.streams.error:
                    s_err = str(error)
                    _append_log(_TERMINAL_LOG, f"ERR: {s_err}\n")
                    yield f"ERRO: {s_err}\n"
                self.ps.streams.error.clear()

            time.sleep(0.1)

        if self.ps.output:
            for line in self.ps.output:
                s_line = str(line)
                _append_log(_TERMINAL_LOG, f"OUT (FINAL): {s_line}\n")
                yield s_line + "\n"
            self.ps.output.clear()

        if self.ps.had_errors and self.ps.streams.error:
            for error in self.ps.streams.error:
                s_err = str(error)
                _append_log(_TERMINAL_LOG, f"ERR (FINAL): {s_err}\n")
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
    def _is_safe_trusted_value(value: str) -> bool:
        """IP/hostname/`*` allowlist mirroring `src.system.winrm._validate_entry`.

        WinRMHandler.set_trusted_hosts writes via the registry (no shell), so
        injection per se isn't possible here. But entries with commas, semis,
        or wildcards corrupt the TrustedHosts list semantics — e.g. a value
        of `*,evil` would silently widen TrustedHosts to permit anything.
        Reject everything that isn't a clean single entry."""
        import re as _re
        if not isinstance(value, str) or not value or len(value) > 253:
            return False
        return bool(_re.fullmatch(r"(?:\*|[A-Za-z0-9._\-]+)", value))

    @staticmethod
    def add_trusted_host(ip):
        """Adiciona um IP aos TrustedHosts se não estiver lá."""
        if not WinRMHandler._is_safe_trusted_value(ip):
            logging.warning(f"add_trusted_host: rejecting unsafe entry {ip!r}")
            return False
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
        if not WinRMHandler._is_safe_trusted_value(ip):
            logging.warning(f"remove_trusted_host: rejecting unsafe entry {ip!r}")
            return False
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