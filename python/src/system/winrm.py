import logging
from typing import List
from src.system.core.local_commands import run_powershell_command

def get_trusted_hosts() -> List[str]:
    """Get list of TrustedHosts from WinRM configuration."""
    command = "Get-Item WSMan:\\localhost\\Client\\TrustedHosts | Select-Object -ExpandProperty Value"
    result = run_powershell_command(command)
    if result['success']:
        hosts_str = result['output'].strip()
        if not hosts_str: return []
        return [h.strip() for h in hosts_str.split(',') if h.strip()]
    else:
        logging.error(f"Failed to get TrustedHosts: {result['error']}")
        return []

def set_trusted_hosts(hosts: List[str]) -> bool:
    """Set the list of TrustedHosts (replaces existing)."""
    hosts_str = ",".join(hosts)
    command = f"Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value '{hosts_str}' -Force"
    result = run_powershell_command(command)
    if result['success']:
        return True
    else:
        logging.error(f"Failed to set TrustedHosts: {result['error']}")
        return False

def add_trusted_host(host: str) -> bool:
    """Add a host to TrustedHosts (appends)."""
    current = get_trusted_hosts()
    if host in current:
        return True
    
    current.append(host)
    return set_trusted_hosts(current)

def clear_trusted_hosts() -> bool:
    """Clear all TrustedHosts."""
    command = "Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value '' -Force"
    result = run_powershell_command(command)
    if result['success']:
        return True
    else:
        logging.error(f"Failed to clear TrustedHosts: {result['error']}")
        return False
