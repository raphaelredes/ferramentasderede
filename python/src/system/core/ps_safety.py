"""PowerShell input sanitization for remote command builders.

The `_load_script` flow in RemoteCommands does `str.replace("__KEY__", value)`
on .ps1 templates. If the placeholder sits inside a single-quoted PS literal —
which is how every template here uses them — then a value containing `'` can
close the string and inject arbitrary PowerShell on the remote host.

These helpers let callers pick the right shape: strict regex for things that
must match a known pattern (service names, log names, dates), and a PS
literal escape for free-text fields like shutdown messages that the operator
should be allowed to type in Portuguese with accents and punctuation.

Validators here are the LAST line of defense — every caller should also
shape its input via Pydantic typing. Goal: even if a route accidentally
forwards untrusted input, the script payload stays well-formed.
"""

from __future__ import annotations

import re


# --- strict patterns --------------------------------------------------------

# Service names: Windows service names are restricted to a relatively tame set.
# Real names include letters, digits, period, underscore, hyphen. Cap at 256
# (Windows limit is 256 chars for service names).
_SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9._\-]{1,256}$")

# Event log names: "System", "Application", "Security", "Microsoft-Windows-...",
# etc. Slashes and forward slashes appear in the "Channel" form. Cap at 255.
_LOG_NAME_RE = re.compile(r"^[A-Za-z0-9 ._\-/]{1,255}$")

# Service actions: enum-style.
_SERVICE_ACTIONS = {"start", "stop", "restart", "pause", "set_startup"}

# StartupType values accepted by `Set-Service -StartupType`.
_SERVICE_STARTUP_TYPES = {"Automatic", "Manual", "Disabled", "AutomaticDelayedStart"}

# ISO-8601 datetimes that PowerShell's Get-Date accepts. The user_activity
# script passes them inside `Get-Date -Date '...'`.
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+\-]\d{2}:?\d{2})?)?$"
)


def validate_service_name(value: object) -> str:
    if not isinstance(value, str) or not _SERVICE_NAME_RE.match(value):
        raise ValueError(f"invalid service name: {value!r}")
    return value


def validate_log_name(value: object) -> str:
    if not isinstance(value, str) or not _LOG_NAME_RE.match(value):
        raise ValueError(f"invalid log name: {value!r}")
    return value


def validate_service_action(value: object) -> str:
    if value not in _SERVICE_ACTIONS:
        raise ValueError(f"invalid service action: {value!r}")
    return value  # type: ignore[return-value]


def validate_service_startup_type(value: object) -> str:
    if value not in _SERVICE_STARTUP_TYPES:
        raise ValueError(f"invalid startup type: {value!r}")
    return value  # type: ignore[return-value]


def validate_iso_datetime(value: object) -> str:
    if not isinstance(value, str) or not _ISO_DATETIME_RE.match(value):
        raise ValueError(f"invalid ISO datetime: {value!r}")
    return value


def validate_event_count(value: object, max_count: int = 1000) -> int:
    """Bound the number of event log records a single fetch can return.

    Beyond a few thousand the WinRM stream is slow enough that the operator is
    better served by tightening the filter — and unbounded `count` makes
    /system/logs a cheap DoS lever."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid event count: {value!r}")
    if n < 1 or n > max_count:
        raise ValueError(f"event count out of range [1, {max_count}]: {n}")
    return n


# --- free-text escape -------------------------------------------------------

def escape_ps_single_quoted(value: str, max_length: int = 512) -> str:
    """Escape a free-text string for safe embedding in a single-quoted PS literal.

    In PowerShell `'..'` is a *verbatim* string — the only metacharacter is `'`
    itself, which is escaped as `''`. So as long as we (a) reject NUL and
    control characters, (b) cap length, and (c) double single-quotes, the
    value can never close the literal.

    Caller is responsible for embedding the result inside `'...'` — this
    helper does NOT add the wrapping quotes.
    """
    if not isinstance(value, str):
        value = str(value)
    if "\x00" in value:
        raise ValueError("string contains NUL byte")
    if len(value) > max_length:
        raise ValueError(f"string longer than {max_length} chars")
    # Drop other ASCII control chars (kept: \t, \n, \r — shutdown -c rejects
    # CR/LF anyway, but msg.exe accepts them).
    cleaned = "".join(c for c in value if c >= " " or c in "\t\n\r")
    return cleaned.replace("'", "''")
