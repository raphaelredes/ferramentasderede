# src/network/vendor_utils.py
import logging
import os
import threading
from datetime import datetime
from mac_vendor_lookup import MacLookup, BaseMacLookup

# Persist the OUI cache inside APP_DATA_DIR like every other app file. The
# library's default is `~/.cache/mac-vendors.txt`, which (a) lives outside
# %APPDATA%\FerramentasDeRede (inconsistent with CLAUDE.md's "logs/files go to
# APP_DATA_DIR" rule) and (b) in the PyInstaller bundle the other fallback
# locations (`sys.prefix/cache`, `os.path.dirname(__file__)/../../cache`) point
# at the ephemeral _MEIxxxx extraction dir and vanish between runs. Pinning the
# class attribute to APP_DATA_DIR makes the path stable and writable.
try:
    from src.config.settings import APP_DATA_DIR
    _CACHE_PATH = os.path.join(APP_DATA_DIR, "mac-vendors.txt")
    BaseMacLookup.cache_path = _CACHE_PATH
except Exception as e:  # pragma: no cover - settings should always import
    logging.error(f"Could not pin vendor cache to APP_DATA_DIR: {e}")
    _CACHE_PATH = BaseMacLookup.cache_path

# The cached list uses a compact `PREFIX:vendor\n` format (~30 bytes/line), NOT
# the raw 4-5 MB IEEE oui.txt. A complete registry is ~38k OUIs, so completeness
# is judged by RECORD COUNT, not byte size — a partial/truncated download (app
# killed mid-update) yields far fewer lines. We still *use* a short file as a
# fallback; `database_is_complete()` just reports it as not-fresh so the
# operator can choose to refresh.
_MIN_COMPLETE_DB_RECORDS = 20_000


class VendorUtils:
    # Pre-loaded prefix dict (OUI[6 hex] -> vendor str). Loaded ONCE, then read
    # concurrently from the discovery worker threads. The mac_vendor_lookup
    # MacLookup.lookup() path runs an asyncio loop via run_until_complete, which
    # is NOT safe to call from N worker threads against a shared singleton loop
    # (RuntimeError: loop already running). A plain dict read, by contrast, is
    # thread-safe in CPython. So we load the dict up front and look up in-memory.
    _prefixes = None
    _prefixes_lock = threading.Lock()

    # Serializes the background update so two scans don't both kick off a 4 MB
    # download. Single-process app, so a module-level lock is sufficient.
    _update_lock = threading.Lock()
    _update_in_progress = False

    # Fallback OUI database — used when the public DB is missing (offline first
    # run) or the prefix is too new to be in the cached file. Covers common
    # corporate / lab vendors and the most-seen virtualization platforms.
    CUSTOM_OUI_DB = {
        # Single-board / IoT
        "B8:27:EB": "Raspberry Pi Foundation",
        "DC:A6:32": "Raspberry Pi Foundation",
        "E4:5F:01": "Raspberry Pi Foundation",
        "D8:3A:DD": "Raspberry Pi Foundation",
        # Virtualization
        "52:54:00": "QEMU/KVM",
        "08:00:27": "Oracle (VirtualBox)",
        "00:50:56": "VMware",
        "00:0C:29": "VMware",
        "00:05:69": "VMware",
        "00:1C:14": "VMware",
        "00:15:5D": "Microsoft Hyper-V",
        "00:03:FF": "Microsoft",
        # Workstation / laptop OEMs (common corporate)
        "00:14:22": "Dell",
        "00:1A:A0": "Dell",
        "00:21:9B": "Dell",
        "00:24:E8": "Dell",
        "F4:8E:38": "Dell",
        "B0:83:FE": "Dell",
        "00:1B:78": "HP",
        "00:1F:29": "HP",
        "00:25:B3": "HP",
        "9C:8E:99": "HP",
        "1C:C1:DE": "HP",
        "00:21:5D": "HP",
        "00:21:5A": "HP",
        "00:0F:FE": "HP",
        "00:13:21": "HP",
        "00:1E:0B": "HP",
        "00:25:64": "HP",
        "70:5A:0F": "HP",
        "98:E7:F4": "HP",
        "AC:1F:6B": "Super Micro / HP",
        "00:23:7D": "Lenovo",
        "00:21:CC": "Lenovo (FLEX)",
        "20:7B:D2": "Lenovo",
        "54:E1:AD": "Lenovo",
        "8C:16:45": "Lenovo",
        # Network gear (frequently shows up in scans)
        "00:1B:0D": "Cisco",
        "00:0C:CE": "Cisco",
        "00:0F:23": "Cisco",
        "00:1A:30": "Cisco",
        "00:24:14": "Cisco",
        "F0:F7:55": "Cisco",
        "00:0E:84": "Cisco",
        "44:D9:E7": "Ubiquiti",
        "DC:9F:DB": "Ubiquiti",
        "F0:9F:C2": "Ubiquiti",
        "FC:EC:DA": "Ubiquiti",
        "00:09:0F": "Fortinet",
        # Printers
        "00:80:77": "Brother",
        "00:00:48": "Epson",
        "08:00:37": "Xerox",
        # Apple (mac/iphone in mixed environments)
        "00:25:00": "Apple",
        "AC:DE:48": "Apple",
        "F0:18:98": "Apple",
        "C8:2A:14": "Apple",
    }

    @classmethod
    def load_prefixes(cls, force=False):
        """Load the OUI prefix dict into memory ONCE for thread-safe lookups.

        Returns the dict (possibly empty). Safe to call from many threads — the
        first caller does the work under a lock, the rest get the cached dict.
        Never blocks on the network: if no local file exists, the dict is empty
        and lookups fall back to CUSTOM_OUI_DB / "Desconhecido".
        """
        if cls._prefixes is not None and not force:
            return cls._prefixes
        with cls._prefixes_lock:
            if cls._prefixes is not None and not force:
                return cls._prefixes
            prefixes = {}
            try:
                location = BaseMacLookup().find_vendors_list()
                if location:
                    with open(location, mode="rb") as f:
                        for line in f.read().splitlines():
                            if b":" not in line:
                                continue
                            prefix, vendor = line.split(b":", 1)
                            # Keys are 6 hex chars uppercase, no separators —
                            # matches AsyncMacLookup.lookup's `mac[:6]` indexing.
                            prefixes[prefix.strip().upper()] = vendor.strip().decode(
                                "utf-8", errors="replace"
                            )
            except Exception as e:
                logging.debug(f"Failed to load OUI prefixes: {e}")
            cls._prefixes = prefixes
            return cls._prefixes

    @staticmethod
    def _normalize_mac(mac_address):
        """Return (display_mac 'AA:BB:..', lookup_key 'AABBCC') or (None, None)."""
        if not mac_address:
            return None, None
        display = mac_address.replace("-", ":").upper()
        key = display.replace(":", "")
        if len(key) < 6:
            return display, None
        return display, key[:6].encode("ascii", errors="ignore")

    @classmethod
    def get_vendor(cls, mac_address):
        """Return the vendor name for a MAC. Thread-safe and offline-first.

        1. CUSTOM_OUI_DB (covers VMs, RPis, common corporate prefixes).
        2. In-memory prefix dict loaded from the cached IEEE list.
        3. "Desconhecido".
        """
        display, key = cls._normalize_mac(mac_address)
        if not display:
            return "Desconhecido"

        # 1. Custom/fallback DB (8-char "AA:BB:CC" prefix).
        if len(display) >= 8:
            prefix8 = display[:8]
            if prefix8 in cls.CUSTOM_OUI_DB:
                return cls.CUSTOM_OUI_DB[prefix8]

        # 2. In-memory IEEE prefix dict (thread-safe read).
        if key:
            prefixes = cls.load_prefixes()
            vendor = prefixes.get(key)
            if vendor:
                return vendor

        return "Desconhecido"

    @staticmethod
    def get_vendor_online(mac_address):
        """Back-compat alias. The cached/in-memory DB is preferred; we never do
        a per-lookup online call (that would block the scan). Kept so existing
        callers don't break."""
        return VendorUtils.get_vendor(mac_address)

    @classmethod
    def database_is_complete(cls):
        """True if a local OUI list exists and looks complete (not truncated)."""
        return cls.get_database_info()["complete"]

    @classmethod
    def get_database_info(cls):
        """Status for the UI: path, presence, completeness, last update, count."""
        info = {
            "path": _CACHE_PATH,
            "present": False,
            "complete": False,
            "last_updated": None,
            "count": 0,
            "size_bytes": 0,
        }
        try:
            location = BaseMacLookup().find_vendors_list()
            if location:
                info["present"] = True
                info["size_bytes"] = os.path.getsize(location)
                last = BaseMacLookup().get_last_updated()
                if isinstance(last, datetime):
                    info["last_updated"] = last.isoformat()
            # Record count is the completeness signal. Use the in-memory dict if
            # it's already loaded (free); otherwise load it (cheap, ~38k entries).
            count = len(cls.load_prefixes())
            info["count"] = count
            info["complete"] = count >= _MIN_COMPLETE_DB_RECORDS
        except Exception as e:
            logging.debug(f"get_database_info failed: {e}")
        return info

    @classmethod
    def update_database(cls):
        """Download a fresh IEEE OUI list. ONLINE and blocking — call only from
        an explicit operator action (endpoint), never from the scan path.

        Writes to a temp file and atomically renames into place so a kill
        mid-download can't leave a truncated cache that later reads as 'fresh'.
        """
        import tempfile

        with cls._update_lock:
            if cls._update_in_progress:
                return False, "Atualização já em andamento."
            cls._update_in_progress = True
        try:
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            # Download to a sibling temp file via the library, then validate and
            # atomically replace. We point the library at the temp path by
            # swapping cache_path for the duration of the call.
            fd, tmp_path = tempfile.mkstemp(
                prefix="mac-vendors-", suffix=".tmp", dir=os.path.dirname(_CACHE_PATH)
            )
            os.close(fd)
            original = BaseMacLookup.cache_path
            try:
                BaseMacLookup.cache_path = tmp_path
                MacLookup().update_vendors()
            finally:
                BaseMacLookup.cache_path = original

            # Validate by record count, not bytes (compact format ~30 B/line).
            tmp_records = 0
            if os.path.exists(tmp_path):
                try:
                    with open(tmp_path, "rb") as f:
                        tmp_records = sum(1 for line in f if b":" in line)
                except OSError:
                    tmp_records = 0
            if tmp_records < _MIN_COMPLETE_DB_RECORDS:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    pass
                return False, (
                    f"Download incompleto ({tmp_records} registros). Base não atualizada. "
                    "Verifique a conexão/proxy e tente novamente."
                )

            os.replace(tmp_path, _CACHE_PATH)
            # Force-reload the in-memory dict so the running app uses the fresh DB.
            cls.load_prefixes(force=True)
            count = len(cls._prefixes or {})
            return True, f"Base de fabricantes atualizada ({count} registros)."
        except Exception as e:
            return False, f"Erro ao atualizar base de fabricantes: {str(e)}"
        finally:
            with cls._update_lock:
                cls._update_in_progress = False
