# src/network/vendor_utils.py
import logging
import os
from mac_vendor_lookup import MacLookup, BaseMacLookup

class VendorUtils:
    _mac_lookup = None
    _initialized = False

    # Fallback/Custom OUI Database for devices that might not be in the public list yet
    # or for specific local overrides.
    CUSTOM_OUI_DB = {
        "B8:27:EB": "Raspberry Pi Foundation",
        "DC:A6:32": "Raspberry Pi Foundation",
        "E4:5F:01": "Raspberry Pi Foundation",
        "D8:3A:DD": "Raspberry Pi Foundation",
        "52:54:00": "QEMU/KVM",
        "08:00:27": "Oracle (VirtualBox)",
    }

    @classmethod
    def _initialize(cls):
        if cls._initialized:
            return

        try:
            cls._mac_lookup = MacLookup()
            # Check if DB exists, if not try to update (might fail if offline)
            # MacLookup stores DB in a standard location.
            # We can try a dummy lookup to see if it works/loads.
            try:
                cls._mac_lookup.lookup("00:00:00:00:00:00")
            except Exception:
                # If lookup fails (likely DB missing), try to update
                logging.info("Vendor DB not found or invalid. Attempting to download...")
                try:
                    cls._mac_lookup.update_vendors()
                    logging.info("Vendor DB downloaded successfully.")
                except Exception as e:
                    logging.warning(f"Failed to download Vendor DB: {e}. Vendor lookup may be limited.")
            
            cls._initialized = True
        except Exception as e:
            logging.error(f"Failed to initialize MacLookup: {e}")

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
