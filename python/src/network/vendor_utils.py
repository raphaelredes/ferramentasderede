# src/network/vendor_utils.py
import logging
import os
from mac_vendor_lookup import MacLookup, BaseMacLookup

class VendorUtils:
    _mac_lookup = None
    _initialized = False

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
        "00:21:5A": "HP",
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
    def _initialize(cls):
        """Best-effort initialization. NEVER blocks on network — if the cached
        DB exists it gets used; if not, lookups fall back to CUSTOM_OUI_DB
        and "Desconhecido". Use update_database() to explicitly refresh.
        """
        if cls._initialized:
            return
        try:
            cls._mac_lookup = MacLookup()
            cls._initialized = True
        except Exception as e:
            logging.error(f"Failed to initialize MacLookup: {e}")
            cls._initialized = True  # Don't retry forever; fallback DB still works.

    @staticmethod
    def get_vendor(mac_address):
        """
        Returns the vendor name for a given MAC address.
        Uses mac-vendor-lookup library with a fallback to a custom list.
        """
        if not mac_address:
            return "Desconhecido"
        
        # Normalize MAC
        mac = mac_address.replace("-", ":").upper()
        
        # 1. Check Custom/Fallback DB first (for VMs, RPis, etc. if needed)
        if len(mac) >= 8:
            prefix = mac[:8]
            if prefix in VendorUtils.CUSTOM_OUI_DB:
                return VendorUtils.CUSTOM_OUI_DB[prefix]

        # 2. Use MacLookup Library
        if not VendorUtils._initialized:
            VendorUtils._initialize()

        if VendorUtils._mac_lookup:
            try:
                return VendorUtils._mac_lookup.lookup(mac)
            except KeyError:
                pass # Not found in DB
            except Exception as e:
                # logging.debug(f"MacLookup error for {mac}: {e}")
                pass

        return "Desconhecido"

    @staticmethod
    def get_vendor_online(mac_address):
        """
        Legacy/Fallback online lookup.
        Now primarily delegates to get_vendor since the local DB is preferred.
        But we can keep the online logic as a second fallback if needed, 
        or just alias it to get_vendor to save bandwidth.
        """
        return VendorUtils.get_vendor(mac_address)

    @staticmethod
    def update_database():
        """
        Manually triggers a database update.
        """
        try:
            if not VendorUtils._initialized:
                VendorUtils._mac_lookup = MacLookup()
            
            VendorUtils._mac_lookup.update_vendors()
            VendorUtils._initialized = True
            return True, "Banco de dados de fabricantes atualizado com sucesso."
        except Exception as e:
            return False, f"Erro ao atualizar banco de dados: {str(e)}"
