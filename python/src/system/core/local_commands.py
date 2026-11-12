# src/ferramentasderede/system/core/local_commands.py
# Executa comandos que rodam na máquina local mas interagem com um host remoto.

import os
import subprocess
import re
import shutil
import time
import logging
import ipaddress


# Username must match Windows account naming rules — letters, digits, underscore,
# dash, period, and an optional domain prefix (DOMAIN\\user) or UPN suffix
# (user@domain.tld). Rejects anything that could be PowerShell metacharacters.
_USERNAME_RE = re.compile(r"^(?:[A-Za-z0-9_.\-]{1,64}\\)?[A-Za-z0-9_.\-]{1,64}(?:@[A-Za-z0-9_.\-]{1,255})?$")


def _is_safe_ip(value: str) -> bool:
    """True if `value` parses cleanly as an IP address. Hostnames are deliberately
    rejected here because the only callers below pipe the value into PowerShell /
    psexec where DNS resolution adds attack surface."""
    if not isinstance(value, str) or not value:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _is_safe_username(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return bool(_USERNAME_RE.match(value))


def run_powershell_command(command):
    """Executa um comando PowerShell localmente."""
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == 'nt' else 0
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
            startupinfo.wShowWindow = 0
        process = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            creationflags=creation_flags,
            startupinfo=startupinfo
        )
        return {
            "success": process.returncode == 0,
            "output": process.stdout,
            "error": process.stderr
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

class LocalCommands:
    def __init__(self, target_ip):
        self.target_ip = target_ip

    def configure_remote_winrm_with_psexec(self, username, password, local_ip_to_trust):
        # Validate inputs before we let them anywhere near psexec / PowerShell.
        # Without this, a value like "'; <ps>; '" smuggled into `local_ip_to_trust`
        # was being interpolated straight into a `Set-Item ... -Value '{ip}'`
        # script body — i.e. arbitrary remote PowerShell as SYSTEM.
        if not _is_safe_ip(self.target_ip):
            yield f"ERRO: IP de destino inválido ({self.target_ip!r}).\n", False
            return
        if not _is_safe_ip(local_ip_to_trust):
            yield f"ERRO: IP local a confiar inválido ({local_ip_to_trust!r}).\n", False
            return
        if not _is_safe_username(username):
            yield "ERRO: nome de usuário contém caracteres inválidos.\n", False
            return

        logging.info(f"Attempting to configure remote WinRM TrustedHosts on {self.target_ip} to trust {local_ip_to_trust}")

        if not shutil.which("psexec.exe"):
            logging.warning("psexec.exe not found in system PATH.")
            yield "ERRO: psexec.exe não foi encontrado no PATH do sistema.\n", None
            yield "Por favor, baixe o PsTools da Microsoft e adicione-o ao seu PATH.\n", None
            return

        yield f"Tentando configurar o host {self.target_ip} para confiar no IP {local_ip_to_trust}...\n", None
        # local_ip_to_trust is already validated as an IP literal — safe to
        # interpolate without further escaping.
        ps_command = f"Set-Item wsman:\\localhost\\Client\\TrustedHosts -Value '{local_ip_to_trust}' -Force"

        # Note: psexec's `-p <password>` puts the password on the command line of
        # the local psexec.exe invocation, where any local user with debug rights
        # or Process Explorer can read it from the process table. The legacy code
        # accepted this risk because we're talking to a local helper, but it's
        # explicitly flagged by CLAUDE.md as "never log/expose passwords".
        # Mitigation here: keep the arg list (so password is at least a separate
        # argv element, not concatenated into a shell string), and never log it.
        full_command = [
            "psexec.exe", f"\\\\{self.target_ip}", "-s", "-accepteula",
            "-u", username, "-p", password,
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", ps_command,
        ]

        try:
            process = subprocess.run(
                full_command,
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            yield process.stdout + "\n", None
            if process.stderr:
                yield "ERRO: " + process.stderr + "\n", None

            if process.returncode == 0:
                yield "Configuração do TrustedHosts enviada com sucesso!\n", True
            else:
                yield "Falha ao executar o comando de configuração.\n", False

        except Exception as e:
            yield f"Exceção ao executar PsExec para configurar WinRM: {e}\n", None

    def enable_remote_winrm_with_psexec(self, username, password):
        """Habilita WinRM no host remoto usando PsExec (serviço + firewall)."""
        if not _is_safe_ip(self.target_ip):
            return False, f"IP de destino inválido ({self.target_ip!r})."
        if not _is_safe_username(username):
            return False, "Nome de usuário contém caracteres inválidos."

        logging.info(f"Attempting to ENABLE WinRM remotely on {self.target_ip} via PsExec")
        if not shutil.which("psexec.exe"):
            logging.warning("psexec.exe not found in system PATH for enable_remote_winrm.")
            return False, "psexec.exe não foi encontrado no PATH deste computador. Baixe o PsTools e adicione ao PATH."

        ps_command = (
            "Enable-PSRemoting -Force; "
            "Set-Service WinRM -StartupType Automatic; "
            "netsh advfirewall firewall set rule group=\"Windows Remote Management\" new enable=yes; "
            "if ((Get-Service WinRM).Status -ne 'Running') { Start-Service WinRM }; "
            "Write-Output 'WINRM_ENABLED'"
        )

        full_command = [
            "psexec.exe", f"\\\\{self.target_ip}", "-s", "-accepteula",
            "-u", username, "-p", password,
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command
        ]

        try:
            process = subprocess.run(
                full_command,
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            logging.debug(f"PsExec enable_remote_winrm stdout: {stdout}")
            logging.debug(f"PsExec enable_remote_winrm stderr: {stderr}")
            if process.returncode == 0 and 'WINRM_ENABLED' in stdout:
                return True, "WinRM habilitado com sucesso no host remoto."
            # Alguns ambientes retornam 0 mesmo sem a string; considerar sucesso se sem erros críticos
            if process.returncode == 0 and 'ERROR' not in stdout.upper() and not stderr.strip():
                return True, "WinRM possivelmente habilitado. Tentando reconectar."
            return False, f"Falha ao habilitar WinRM remotamente. Código {process.returncode}. Saída: {stderr or stdout}"
        except Exception as e:
            logging.error(f"Exceção ao habilitar WinRM remotamente via PsExec: {e}")
            return False, f"Exceção ao executar PsExec para habilitar WinRM: {e}"
    def enable_remote_winrm(self, username, password):
        """Habilita WinRM no host remoto usando Agendador de Tarefas nativo (schtasks), SCM (sc.exe) ou PsExec."""
        target = str(self.target_ip).strip()
        if not target:
            return False, "Endereço ou IP de destino inválido."
        if not _is_safe_username(username):
            return False, "Nome de usuário contém caracteres inválidos."

        logging.info(f"Tentando habilitar WinRM remotamente em {target} com usuário {username}")
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
        startupinfo.wShowWindow = 0
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        task_name = f"WinRM_Enable_{int(time.time())}"
        ps_enable = (
            "Enable-PSRemoting -Force; "
            "Set-Service WinRM -StartupType Automatic; "
            "netsh advfirewall firewall set rule group='Windows Remote Management' new enable=yes; "
            "netsh advfirewall firewall add rule name='WinRM 5985' dir=in action=allow protocol=TCP localport=5985; "
            "Start-Service WinRM -ErrorAction SilentlyContinue"
        )
        task_cmd = f"powershell.exe -ExecutionPolicy Bypass -Command \"{ps_enable}\""

        # 1. Tentativa Principal: Agendador de Tarefas Remoto (schtasks.exe - 100% nativo do Windows, roda como SYSTEM)
        try:
            create_args = [
                "schtasks.exe", "/create",
                "/s", target,
                "/u", username,
                "/p", password,
                "/ru", "SYSTEM",
                "/tn", task_name,
                "/tr", task_cmd,
                "/sc", "ONCE",
                "/st", "00:00",
                "/f"
            ]
            res_create = subprocess.run(
                create_args,
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                check=False, creationflags=creation_flags, startupinfo=startupinfo
            )

            out_text = (res_create.stdout or "") + (res_create.stderr or "")
            if res_create.returncode == 0 or "criada" in out_text.lower() or "created" in out_text.lower():
                # Dispara a execução imediatamente
                run_args = [
                    "schtasks.exe", "/run",
                    "/s", target,
                    "/u", username,
                    "/p", password,
                    "/tn", task_name
                ]
                subprocess.run(
                    run_args,
                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                    check=False, creationflags=creation_flags, startupinfo=startupinfo
                )

                # Aguarda execução dos comandos no host remoto
                time.sleep(4)

                # Remove a tarefa temporária
                del_args = [
                    "schtasks.exe", "/delete",
                    "/s", target,
                    "/u", username,
                    "/p", password,
                    "/tn", task_name,
                    "/f"
                ]
                subprocess.run(
                    del_args,
                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                    check=False, creationflags=creation_flags, startupinfo=startupinfo
                )

                # Verifica se a porta 5985 já está respondendo
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.5)
                try:
                    s.connect((target, 5985))
                    s.close()
                    return True, "WinRM habilitado com sucesso no host remoto (porta 5985 aberta)."
                except Exception:
                    # Mesmo se o socket ainda demorar para responder, a tarefa foi executada no host
                    return True, "Comando de habilitação do WinRM disparado com sucesso via Agendador de Tarefas."
            else:
                logging.warning(f"schtasks falhou em {target}: {out_text.strip()}")
        except Exception as e:
            logging.warning(f"Exceção no schtasks em {target}: {e}")

        # 2. Tentativa Secundária: Service Control Manager remoto (sc.exe com IPC$ autenticado)
        try:
            from .hoptodesk_manager import HopToDeskManager
            connected_ipc = False
            try:
                connected_ipc = HopToDeskManager._connect_smb_share(target, username, password)
            except Exception:
                pass

            sc_config = ["sc.exe", f"\\{target}", "config", "WinRM", "start=", "auto"]
            subprocess.run(sc_config, capture_output=True, text=True, creationflags=creation_flags, startupinfo=startupinfo)
            sc_start = ["sc.exe", f"\\{target}", "start", "WinRM"]
            res_sc2 = subprocess.run(sc_start, capture_output=True, text=True, creationflags=creation_flags, startupinfo=startupinfo)

            if connected_ipc:
                HopToDeskManager._disconnect_smb_share(target)

            sc_out = (res_sc2.stdout or "") + (res_sc2.stderr or "")
            if res_sc2.returncode == 0 or "running" in sc_out.lower() or "execu" in sc_out.lower():
                return True, "Serviço WinRM iniciado com sucesso no host remoto via SCM."
        except Exception as e:
            logging.warning(f"SCM remoto falhou em {target}: {e}")

        # 3. Tentativa Terciária: PsExec (se instalado no sistema)
        if shutil.which("psexec.exe"):
            return self.enable_remote_winrm_with_psexec(username, password)

        return False, "Não foi possível habilitar o WinRM automaticamente. Certifique-se de que a conta possui privilégios de administrador de rede e que a porta 445 (SMB/RPC) está acessível no destino."
