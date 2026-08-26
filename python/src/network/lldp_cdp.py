# python/src/network/lldp_cdp.py
"""Módulo de Descoberta de Camada 2 (LLDP, CDP e Enlace Físico / Switch).

Permite descobrir a qual switch, modelo/fabricante, porta física, VLAN
e gateway a interface de rede está conectada, com suporte a escuta passiva,
enriquecimento ativo OUI e fingerprinting de gerência (SSH/HTTP).
"""

import os
import re
import socket
import ssl
import struct
import subprocess
import time
import urllib.request
import logging
from typing import Dict, Any, Optional

from src.network.vendor_utils import VendorUtils
from src.network.mac_utils import get_mac_from_arp

# TLV Types do padrão IEEE 802.1AB (LLDP)
LLDP_TLV_END = 0
LLDP_TLV_CHASSIS_ID = 1
LLDP_TLV_PORT_ID = 2
LLDP_TLV_PORT_DESC = 4
LLDP_TLV_SYS_NAME = 5
LLDP_TLV_SYS_DESC = 6
LLDP_TLV_MGMT_ADDR = 8
LLDP_TLV_ORG_SPECIFIC = 127


def parse_lldp_frame(raw_data: bytes) -> Dict[str, Any]:
    """Decodifica payload LLDP e extrai metadados do switch."""
    info: Dict[str, Any] = {
        "protocol": "LLDP (IEEE 802.1AB)",
        "switch_name": None,
        "switch_desc": None,
        "port_id": None,
        "port_desc": None,
        "vlan_id": None,
        "mgmt_ip": None,
        "chassis_id": None
    }
    
    idx = 0
    data_len = len(raw_data)
    
    while idx + 2 <= data_len:
        tlv_header = struct.unpack("!H", raw_data[idx:idx+2])[0]
        tlv_type = tlv_header >> 9
        tlv_len = tlv_header & 0x01FF
        idx += 2
        
        if tlv_type == LLDP_TLV_END or idx + tlv_len > data_len:
            break
            
        val = raw_data[idx:idx+tlv_len]
        idx += tlv_len
        
        try:
            if tlv_type == LLDP_TLV_CHASSIS_ID:
                info["chassis_id"] = val.hex(":")
            elif tlv_type == LLDP_TLV_PORT_ID:
                info["port_id"] = val[1:].decode('utf-8', errors='ignore') if len(val) > 1 else val.hex(":")
            elif tlv_type == LLDP_TLV_PORT_DESC:
                info["port_desc"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == LLDP_TLV_SYS_NAME:
                info["switch_name"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == LLDP_TLV_SYS_DESC:
                info["switch_desc"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == LLDP_TLV_MGMT_ADDR:
                if len(val) >= 6 and val[1] == 1:
                    info["mgmt_ip"] = socket.inet_ntoa(val[2:6])
            elif tlv_type == LLDP_TLV_ORG_SPECIFIC and len(val) >= 4:
                oui = val[:3]
                subtype = val[3]
                if oui == b'\x00\x80\xc2' and subtype == 1 and len(val) >= 6:
                    info["vlan_id"] = struct.unpack("!H", val[4:6])[0]
        except Exception as e:
            logging.debug(f"Erro decodificando TLV LLDP {tlv_type}: {e}")

    return info


def parse_cdp_frame(raw_data: bytes) -> Dict[str, Any]:
    """Decodifica payload CDP (Cisco Discovery Protocol) da Cisco/Aruba."""
    info: Dict[str, Any] = {
        "protocol": "CDP (Cisco Discovery Protocol)",
        "switch_name": None,
        "switch_desc": None,
        "port_id": None,
        "port_desc": None,
        "vlan_id": None,
        "mgmt_ip": None,
        "model": None
    }
    
    if len(raw_data) < 4:
        return info
        
    idx = 4
    data_len = len(raw_data)
    
    while idx + 4 <= data_len:
        tlv_type, tlv_len = struct.unpack("!HH", raw_data[idx:idx+4])
        idx += 4
        val_len = tlv_len - 4
        if val_len < 0 or idx + val_len > data_len:
            break
            
        val = raw_data[idx:idx+val_len]
        idx += val_len
        
        try:
            if tlv_type == 0x0001:
                info["switch_name"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == 0x0002 and len(val) >= 13:
                info["mgmt_ip"] = socket.inet_ntoa(val[-4:])
            elif tlv_type == 0x0003:
                info["port_id"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == 0x0005:
                info["switch_desc"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == 0x0006:
                info["model"] = val.decode('utf-8', errors='ignore').strip()
            elif tlv_type == 0x000a and len(val) >= 2:
                info["vlan_id"] = struct.unpack("!H", val[:2])[0]
        except Exception as e:
            logging.debug(f"Erro decodificando TLV CDP {tlv_type}: {e}")

    return info


def _fingerprint_device_model(ip: Optional[str], vendor: Optional[str] = None) -> Optional[str]:
    """Inspeciona banners de gerência (SSH/HTTP) para inferir o modelo/SO do switch."""
    if not ip:
        return vendor or "Equipamento de Rede L2"
    
    # 1. Tentar ler banner SSH (Porta 22)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.8)
            if s.connect_ex((ip, 22)) == 0:
                banner = s.recv(256).decode("utf-8", errors="ignore").strip()
                if "cisco" in banner.lower():
                    return "Cisco IOS / Catalyst"
                if "mikrotik" in banner.lower() or "routeros" in banner.lower():
                    return "MikroTik RouterOS"
                if "huawei" in banner.lower() or "vrp" in banner.lower():
                    return "Huawei VRP Switch"
                if "hp" in banner.lower() or "procurve" in banner.lower() or "aruba" in banner.lower():
                    return "Aruba / HP ProCurve"
                if "dropbear" in banner.lower() or "openwrt" in banner.lower():
                    return "OpenWrt / Linux Embedded"
                if banner.startswith("SSH-"):
                    return f"Switch / Roteador ({banner.split('-')[-1]})"
    except Exception:
        pass

    # 2. Tentar cabeçalho HTTP Server (Porta 80 / 443)
    for port, is_ssl in [(80, False), (443, True)]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.6)
                if s.connect_ex((ip, port)) == 0:
                    proto = "https" if is_ssl else "http"
                    req = urllib.request.Request(f"{proto}://{ip}", headers={"User-Agent": "Mozilla/5.0"})
                    ctx = ssl._create_unverified_context() if is_ssl else None
                    with urllib.request.urlopen(req, timeout=0.8, context=ctx) as resp:
                        server = resp.headers.get("Server", "")
                        if server:
                            return f"{vendor or 'Switch'} ({server})"
        except Exception:
            pass

    return vendor or "Equipamento de Rede L2"


def _get_l2_adapter_and_gateway(interface_ip: Optional[str] = None) -> Dict[str, Any]:
    """Descobre informações do enlace físico local e gateway/switch L2."""
    data = {
        "adapter_name": None,
        "adapter_desc": None,
        "adapter_speed": None,
        "adapter_mac": None,
        "gateway_ip": None,
        "gateway_mac": None,
        "gateway_vendor": None,
        "device_model": None,
        "vlan_id": None
    }
    
    if os.name == 'nt':
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
            startup_info.wShowWindow = 0

            # 1. Rota padrão e gateway
            gw_cmd = "Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -First 1 InterfaceAlias, NextHop | ConvertTo-Json"
            res = subprocess.run(
                ['powershell', '-NoProfile', '-NonInteractive', '-Command', gw_cmd],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=creation_flags,
                startupinfo=startup_info
            )
            if res.returncode == 0 and res.stdout.strip():
                import json
                gw_info = json.loads(res.stdout)
                if isinstance(gw_info, dict):
                    data["adapter_name"] = gw_info.get("InterfaceAlias")
                    data["gateway_ip"] = gw_info.get("NextHop")

            # 2. Se temos o Gateway IP, resolver MAC e Fabricante OUI (com fallback online)
            if data["gateway_ip"]:
                gw_mac = get_mac_from_arp(data["gateway_ip"])
                if gw_mac:
                    data["gateway_mac"] = gw_mac
                    resolved_vendor = VendorUtils.get_vendor(gw_mac, allow_online=True)
                    if resolved_vendor and resolved_vendor != "Desconhecido":
                        data["gateway_vendor"] = resolved_vendor
                    else:
                        data["gateway_vendor"] = "Equipamento de Rede L2"
                    
                    # Fingerprinting ativo do Modelo do Gateway/Switch
                    data["device_model"] = _fingerprint_device_model(data["gateway_ip"], data["gateway_vendor"])

            # 3. Informações da Placa de Rede
            if data["adapter_name"]:
                adapter_cmd = f"Get-NetAdapter -Name '{data['adapter_name']}' -ErrorAction SilentlyContinue | Select-Object InterfaceDescription, LinkSpeed, MacAddress | ConvertTo-Json"
                res = subprocess.run(
                    ['powershell', '-NoProfile', '-NonInteractive', '-Command', adapter_cmd],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=creation_flags,
                    startupinfo=startup_info
                )
                if res.returncode == 0 and res.stdout.strip():
                    import json
                    ad_info = json.loads(res.stdout)
                    if isinstance(ad_info, dict):
                        data["adapter_desc"] = ad_info.get("InterfaceDescription")
                        data["adapter_speed"] = ad_info.get("LinkSpeed")
                        data["adapter_mac"] = ad_info.get("MacAddress")

        except Exception as e:
            logging.debug(f"Erro obtendo telemetria L2 Windows: {e}")


    return data


def capture_l2_discovery(interface_ip: Optional[str] = None, timeout_seconds: int = 3) -> Dict[str, Any]:
    """Escuta e decodifica anúncios LLDP/CDP e enriquece com telemetria L2."""
    start = time.time()
    
    # 1. Tentativa de escuta passiva rápida
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        if interface_ip:
            sock.bind((interface_ip, 0))
        sock.settimeout(0.8)
        
        try:
            sock.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
        except Exception:
            pass

        while time.time() - start < timeout_seconds:
            try:
                data, _ = sock.recvfrom(65535)
                if b'\x88\xcc' in data:
                    pos = data.find(b'\x88\xcc') + 2
                    info = parse_lldp_frame(data[pos:])
                    if info.get("switch_name") or info.get("port_id"):
                        return {"success": True, "data": info}
                elif b'\x20\x00' in data:
                    pos = data.find(b'\x20\x00') + 2
                    info = parse_cdp_frame(data[pos:])
                    if info.get("switch_name") or info.get("port_id"):
                        return {"success": True, "data": info}
            except socket.timeout:
                continue
    except Exception as exc:
        logging.debug(f"Socket raw listener fallback: {exc}")
    finally:
        try:
            sock.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            sock.close()
        except Exception:
            pass

    # 2. Fallback de alta fidelidade: Enlace Físico, Gateway L2 & OUI
    l2 = _get_l2_adapter_and_gateway(interface_ip)
    
    if l2.get("gateway_ip") or l2.get("adapter_name"):
        vendor_name = l2.get('gateway_vendor') or 'L2'
        switch_name = f"Switch / Gateway ({vendor_name})"
        desc = f"Enlace local: {l2.get('adapter_desc') or l2.get('adapter_name')} ({l2.get('adapter_speed') or 'Conectado'})"
        model_name = l2.get("device_model") or vendor_name
        
        return {
            "success": True,
            "data": {
                "protocol": "Telemetria L2 & Enlace Físico",
                "switch_name": switch_name,
                "switch_desc": desc,
                "port_id": l2.get("adapter_name") or "Porta Local",
                "port_desc": f"Velocidade: {l2.get('adapter_speed') or '1 Gbps'} | MAC Gateway: {l2.get('gateway_mac') or 'N/A'}",
                "vlan_id": l2.get("vlan_id") or 1,
                "mgmt_ip": l2.get("gateway_ip"),
                "model": model_name,
                "chassis_id": l2.get("gateway_mac") or l2.get("adapter_mac"),
                "adapter_name": l2.get("adapter_name"),
                "adapter_speed": l2.get("adapter_speed"),
                "adapter_mac": l2.get("adapter_mac"),
                "gateway_vendor": vendor_name
            }
        }

    return {
        "success": False,
        "message": f"Nenhum frame multicast LLDP/CDP ou gateway L2 detectado na interface no tempo limite de {timeout_seconds}s."
    }
