# python/src/network/toast_notifier.py
"""Módulo de notificações nativas do Windows Toast para alertas de rede.

Dispara notificações leves de sistema quando hosts mudam de estado
(online/offline) ou atingem limiares críticos de perda de pacotes.
"""

import subprocess
import threading
import logging
from typing import Optional

def _escape_ps_string(text: str) -> str:
    """Escapa aspas simples e caracteres especiais para segurança no PowerShell."""
    return text.replace("'", "''").replace('"', '`"')


def send_windows_toast(title: str, message: str, sound: bool = True):
    """Envia uma notificação Toast nativa do Windows de forma assíncrona."""
    def _run_toast():
        try:
            safe_title = _escape_ps_string(title)
            safe_message = _escape_ps_string(message)
            
            # Script PowerShell para Windows 10/11 Toast Notification via WinRT / XML
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            
            $template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{safe_title}</text>
            <text>{safe_message}</text>
        </binding>
    </visual>
</toast>
"@
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Ferramentas de Rede")
            $notifier.Show($toast)
            """
            
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                timeout=5
            )
        except Exception as e:
            logging.debug(f"Falha ao emitir Windows Toast: {e}")

    # Disparar em thread daemon para nunca bloquear o backend
    threading.Thread(target=_run_toast, daemon=True).start()


def notify_host_status_change(hostname: str, ip: str, is_online: bool):
    """Atalho para notificar transição de status de host monitorado."""
    if is_online:
        title = "🟢 Host Recuperado"
        msg = f"O host {hostname} ({ip}) voltou a responder ao monitoramento."
    else:
        title = "🔴 Alerta: Host Indisponível"
        msg = f"O host {hostname} ({ip}) parou de responder aos pings."
    
    send_windows_toast(title, msg)
