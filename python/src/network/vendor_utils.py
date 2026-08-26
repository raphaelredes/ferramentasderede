# src/network/vendor_utils.py
"""Módulo de identificação e enriquecimento de fabricantes (OUI) via MAC Address.

Suporta banco local em memória (IEEE OUI), cache dinâmico em disco e
fallback para APIs REST públicas de alta velocidade (maclookup.app e macvendors.com).
"""

import json
import logging
import os
import threading
import urllib.request
from datetime import datetime
from typing import Optional, Dict, Any
from mac_vendor_lookup import MacLookup, BaseMacLookup

try:
    from src.config.settings import APP_DATA_DIR
    _CACHE_PATH = os.path.join(APP_DATA_DIR, "mac-vendors.txt")
    _DYNAMIC_CACHE_PATH = os.path.join(APP_DATA_DIR, "mac-vendors-dynamic.json")
    BaseMacLookup.cache_path = _CACHE_PATH
except Exception as e:
    logging.error(f"Could not pin vendor cache to APP_DATA_DIR: {e}")
    _CACHE_PATH = BaseMacLookup.cache_path
    _DYNAMIC_CACHE_PATH = "mac-vendors-dynamic.json"

_MIN_COMPLETE_DB_RECORDS = 20_000


class VendorUtils:
    _prefixes = None
    _prefixes_lock = threading.Lock()
    _update_lock = threading.Lock()
    _update_in_progress = False
    _dynamic_cache: Dict[str, str] = {}
    _dynamic_loaded = False

    # Base estendida de OUIs mais comuns para resposta offline instantânea (0ms)
    CUSTOM_OUI_DB = {
        # Cisco Systems
        "00:25:B4": "Cisco Systems, Inc",
        "00:1B:0D": "Cisco", "00:0C:CE": "Cisco", "00:0F:23": "Cisco",
        "00:1A:30": "Cisco", "00:24:14": "Cisco", "F0:F7:55": "Cisco",
        "00:0E:84": "Cisco", "70:81:05": "Cisco", "00:26:0B": "Cisco",
        "00:1D:71": "Cisco", "50:06:04": "Cisco", "00:22:BD": "Cisco",
        # HP / Aruba
        "00:1B:78": "HP", "00:1F:29": "HP", "00:25:B3": "HP", "9C:8E:99": "HP",
        "1C:C1:DE": "HP", "00:21:5D": "HP", "00:21:5A": "HP", "00:0F:FE": "HP",
        "00:13:21": "HP", "00:1E:0B": "HP", "00:25:64": "HP", "70:5A:0F": "HP",
        "98:E7:F4": "HP", "AC:1F:6B": "Super Micro / HP", "00:0B:86": "Aruba Networks",
        "20:4C:03": "Aruba Networks", "94:B4:0F": "Aruba Networks",
        # Dell / VMware / Microsoft
        "00:14:22": "Dell", "00:1A:A0": "Dell", "00:21:9B": "Dell", "00:24:E8": "Dell",
        "F4:8E:38": "Dell", "B0:83:FE": "Dell", "52:54:00": "QEMU/KVM",
        "08:00:27": "Oracle (VirtualBox)", "00:50:56": "VMware", "00:0C:29": "VMware",
        "00:05:69": "VMware", "00:1C:14": "VMware", "00:15:5D": "Microsoft Hyper-V",
        # Ubiquiti / Mikrotik / Huawei / Fortinet / Juniper
        "44:D9:E7": "Ubiquiti", "DC:9F:DB": "Ubiquiti", "F0:9F:C2": "Ubiquiti",
        "FC:EC:DA": "Ubiquiti", "00:09:0F": "Fortinet", "48:8B:0A": "MikroTik",
        "6C:3B:6B": "MikroTik", "B8:69:F4": "MikroTik", "00:E0:FC": "Huawei",
        "70:7B:E8": "Huawei", "00:05:86": "Juniper Networks",
        # Placas de Rede Realtek / Intel
        "9C:6B:00": "Realtek Semiconductor", "00:E0:4C": "Realtek Semiconductor",
        "00:1B:21": "Intel", "00:1F:3B": "Intel", "68:05:CA": "Intel",
        # Apple / Outros
        "00:25:00": "Apple", "AC:DE:48": "Apple", "F0:18:98": "Apple", "C8:2A:14": "Apple",
        "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi", "E4:5F:01": "Raspberry Pi"
    }

    @classmethod
    def _load_dynamic_cache(cls):
        """Carrega cache dinâmico persistido em JSON."""
        if cls._dynamic_loaded:
            return
        cls._dynamic_loaded = True
        try:
            if os.path.exists(_DYNAMIC_CACHE_PATH):
                with open(_DYNAMIC_CACHE_PATH, "r", encoding="utf-8") as f:
                    cls._dynamic_cache = json.load(f)
        except Exception as e:
            logging.debug(f"Falha ao carregar cache dinâmico de MAC: {e}")

    @classmethod
    def _save_dynamic_cache(cls):
        """Salva cache dinâmico em JSON de forma segura."""
        try:
            os.makedirs(os.path.dirname(_DYNAMIC_CACHE_PATH), exist_ok=True)
            with open(_DYNAMIC_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(cls._dynamic_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.debug(f"Falha ao salvar cache dinâmico de MAC: {e}")

    @classmethod
    def load_prefixes(cls, force=False):
        """Carrega a base IEEE local em memória para buscas thread-safe rápidas."""
        if cls._prefixes is not None and not force:
            return cls._prefixes
        with cls._prefixes_lock:
            if cls._prefixes is not None and not force:
                return cls._prefixes
            prefixes = {}
            try:
                location = BaseMacLookup().find_vendors_list()
                if location and os.path.exists(location):
                    with open(location, mode="rb") as f:
                        for line in f.read().splitlines():
                            if b":" not in line:
                                continue
                            prefix, vendor = line.split(b":", 1)
                            prefixes[prefix.strip().upper()] = vendor.strip().decode("utf-8", errors="replace")
            except Exception as e:
                logging.debug(f"Erro ao carregar prefixos OUI locais: {e}")
            cls._prefixes = prefixes
            return cls._prefixes

    @staticmethod
    def _normalize_mac(mac_address: str):
        """Normaliza MAC para 'AA:BB:CC:DD:EE:FF' e chave de 6 hex 'AABBCC'."""
        if not mac_address:
            return None, None
        display = mac_address.replace("-", ":").upper()
        key = display.replace(":", "")
        if len(key) < 6:
            return display, None
        return display, key[:6].encode("ascii", errors="ignore")

    @classmethod
    def lookup_vendor_online(cls, mac_address: str, timeout: float = 2.0) -> Optional[str]:
        """Consulta online APIs REST públicas para resolver MACs novos ou não indexados."""
        display, key = cls._normalize_mac(mac_address)
        if not display:
            return None

        # 1. Tentar api.maclookup.app (JSON, rápido e estável)
        try:
            url = f"https://api.maclookup.app/v2/macs/{display}"
            req = urllib.request.Request(url, headers={"User-Agent": "FerramentasDeRede/1.4.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    company = data.get("company")
                    if company and company.strip():
                        return company.strip()
        except Exception as e:
            logging.debug(f"API maclookup.app falhou para {mac_address}: {e}")

        # 2. Fallback para api.macvendors.com
        try:
            url = f"https://api.macvendors.com/{display}"
            req = urllib.request.Request(url, headers={"User-Agent": "FerramentasDeRede/1.4.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    text = resp.read().decode("utf-8", errors="ignore").strip()
                    if text and "errors" not in text.lower():
                        return text
        except Exception as e:
            logging.debug(f"API macvendors.com falhou para {mac_address}: {e}")

        return None

    @classmethod
    def get_vendor(cls, mac_address: str, allow_online: bool = True) -> str:
        """Obtém o fabricante de um endereço MAC via banco offline ou pesquisa online."""
        display, key = cls._normalize_mac(mac_address)
        if not display:
            return "Desconhecido"

        # 1. Base Estendida Integrada (0ms)
        if len(display) >= 8:
            prefix8 = display[:8]
            if prefix8 in cls.CUSTOM_OUI_DB:
                return cls.CUSTOM_OUI_DB[prefix8]

        # 2. Base Local IEEE em memória (se baixada)
        if key:
            prefixes = cls.load_prefixes()
            vendor = prefixes.get(key)
            if vendor:
                return vendor

        # 3. Cache Dinâmico persistido
        cls._load_dynamic_cache()
        if display in cls._dynamic_cache:
            return cls._dynamic_cache[display]
        prefix_hex = display[:8]
        if prefix_hex in cls._dynamic_cache:
            return cls._dynamic_cache[prefix_hex]

        # 4. Consulta Online em Tempo Real (Fallback Inteligente)
        if allow_online:
            online_vendor = cls.lookup_vendor_online(mac_address, timeout=2.0)
            if online_vendor:
                cls._dynamic_cache[display[:8]] = online_vendor
                cls._save_dynamic_cache()
                return online_vendor

        return "Desconhecido"

    @classmethod
    def get_database_info(cls) -> Dict[str, Any]:
        """Informa status da base OUI local para a interface."""
        info = {"path": _CACHE_PATH, "present": False, "complete": False, "last_updated": None, "count": 0, "size_bytes": 0}
        try:
            location = BaseMacLookup().find_vendors_list()
            if location and os.path.exists(location):
                info["present"] = True
                info["size_bytes"] = os.path.getsize(location)
                last = BaseMacLookup().get_last_updated()
                if isinstance(last, datetime):
                    info["last_updated"] = last.isoformat()
            count = len(cls.load_prefixes())
            info["count"] = count
            info["complete"] = count >= _MIN_COMPLETE_DB_RECORDS
        except Exception as e:
            logging.debug(f"get_database_info falhou: {e}")
        return info

    @classmethod
    def update_database(cls):
        """Baixa base completa IEEE OUI em segundo plano."""
        import tempfile
        with cls._update_lock:
            if cls._update_in_progress:
                return False, "Atualização já em andamento."
            cls._update_in_progress = True
        try:
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix="mac-vendors-", suffix=".tmp", dir=os.path.dirname(_CACHE_PATH))
            os.close(fd)
            original = BaseMacLookup.cache_path
            try:
                BaseMacLookup.cache_path = tmp_path
                MacLookup().update_vendors()
            finally:
                BaseMacLookup.cache_path = original

            tmp_records = 0
            if os.path.exists(tmp_path):
                try:
                    with open(tmp_path, "rb") as f:
                        tmp_records = sum(1 for line in f if b":" in line)
                except OSError:
                    tmp_records = 0
            if tmp_records < _MIN_COMPLETE_DB_RECORDS:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return False, f"Download incompleto ({tmp_records} registros)."

            os.replace(tmp_path, _CACHE_PATH)
            cls.load_prefixes(force=True)
            return True, f"Base atualizada com sucesso ({len(cls._prefixes or {})} registros)."
        except Exception as e:
            return False, f"Erro ao atualizar base de fabricantes: {str(e)}"
        finally:
            with cls._update_lock:
                cls._update_in_progress = False
