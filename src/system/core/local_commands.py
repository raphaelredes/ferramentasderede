# src/ferramentasderede/system/core/local_commands.py
# Executa comandos que rodam na máquina local mas interagem com um host remoto.

import os
import subprocess
import re
import shutil
import time
import logging

class LocalCommands:
    def __init__(self, target_ip):
        self.target_ip = target_ip

    def configure_remote_winrm_with_psexec(self, username, password, local_ip_to_trust):
        logging.info(f"Attempting to configure remote WinRM TrustedHosts on {self.target_ip} to trust {local_ip_to_trust}")

        if not shutil.which("psexec.exe"):
            logging.warning("psexec.exe not found in system PATH.")
            yield "ERRO: psexec.exe não foi encontrado no PATH do sistema.\n", None
            yield "Por favor, baixe o PsTools da Microsoft e adicione-o ao seu PATH.\n", None
            return # Removed return here as yield is used in the first lines

        yield f"Tentando configurar o host {self.target_ip} para confiar no IP {local_ip_to_trust}...\n", None
        ps_command = f"Set-Item wsman:\\localhost\\Client\\TrustedHosts -Value '{local_ip_to_trust}' -Force"
        
        full_command = [
            "psexec.exe", f"\\\\{self.target_ip}", "-s", "-accepteula",
            "-u", username, "-p", password,
            "powershell.exe", "-Command", ps_command
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