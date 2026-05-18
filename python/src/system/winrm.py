"""Legacy thin wrappers around TrustedHosts management.

This module used to build PowerShell command strings via f-string interpolation
(`Set-Item ... -Value '{hosts_str}' -Force`). A list entry containing `'` could
close the quoted literal and execute arbitrary PowerShell — the entry list
flows from `/settings/import` (operator uploads a JSON backup), so a malicious
backup file from any source rooted on the same machine could RCE the operator
account on import.

The new implementation delegates to `WinRMHandler` (registry-based) and rejects
any entry that isn't a clean IP/hostname/`*`, mirroring the validator already
in place for `/settings/trusted-hosts`.
"""
import logging
import re
from typing import List

# IP literal, hostname, or wildcard. No quotes, semicolons, backticks, or
# anything else a PowerShell parser would notice.
_SAFE_TRUSTED_HOST_RE = re.compile(r"^(?:\*|[A-Za-z0-9._\-]{1,253})$")


def _validate_entry(host: str) -> bool:
    return isinstance(host, str) and bool(_SAFE_TRUSTED_HOST_RE.match(host))


def get_trusted_hosts() -> List[str]:
    """Get list of TrustedHosts from WinRM configuration."""
    from src.system.core.winrm_handler import WinRMHandler
    raw = WinRMHandler.get_trusted_hosts()
    if not raw:
        return []
    if raw == "*":
        return ["*"]
    return [h.strip() for h in raw.split(",") if h.strip()]


def set_trusted_hosts(hosts: List[str]) -> bool:
    """Set the list of TrustedHosts (replaces existing).

    Every entry is validated; the call fails closed if any entry would be
    unsafe to embed in the PowerShell registry-set call. WinRMHandler.
    set_trusted_hosts writes the registry value directly, so even with safe
    entries the value never sees a shell parser."""
    from src.system.core.winrm_handler import WinRMHandler
    if not isinstance(hosts, list):
        logging.error("set_trusted_hosts: expected list, got %r", type(hosts))
        return False
    safe = []
    for h in hosts:
        if not _validate_entry(h):
            logging.warning("set_trusted_hosts: rejecting unsafe entry %r", h)
            return False
        safe.append(h)
    value = ",".join(safe)
    return bool(WinRMHandler.set_trusted_hosts(value))


def add_trusted_host(host: str) -> bool:
    """Add a host to TrustedHosts (appends)."""
    if not _validate_entry(host):
        logging.warning("add_trusted_host: rejecting unsafe entry %r", host)
        return False
    current = get_trusted_hosts()
    if host in current:
        return True
    current.append(host)
    return set_trusted_hosts(current)


def clear_trusted_hosts() -> bool:
    """Clear all TrustedHosts."""
    from src.system.core.winrm_handler import WinRMHandler
    return bool(WinRMHandler.set_trusted_hosts(""))


def remove_trusted_host(host: str) -> bool:
    """Remove a single host from TrustedHosts."""
    if not _validate_entry(host):
        logging.warning("remove_trusted_host: rejecting unsafe entry %r", host)
        return False
    current = get_trusted_hosts()
    if host not in current:
        return True
    current.remove(host)
    if not current:
        return clear_trusted_hosts()
    return set_trusted_hosts(current)
