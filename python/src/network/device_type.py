# src/network/device_type.py
"""Best-effort device-TYPE inference for scanned hosts.

This is NOT model detection — a MAC address only carries the *manufacturer*
(OUI), never a model, and no public database maps MAC → model. What we *can* do
is combine three weak signals into a probable device category:

  * open ports   (strongest — 9100 ≈ printer, 554 ≈ IP camera, 3389 ≈ Windows)
  * vendor       (Cisco/Ubiquiti/Fortinet ≈ network gear, Apple ≈ Apple device)
  * hostname     (substrings like "printer", "cam", "srv", "ap-")

`infer_device_type` returns `(label_ptbr, is_guess)`. `is_guess` is False only
when a strong port signal makes the type near-certain; otherwise True, so the
UI can mark it as "provável" with a warning. Labels are PT-BR (UI language).
"""

# Strong port → type signals. A listening port on these is a near-definitive
# tell, so the result is NOT flagged as a guess.
_STRONG_PORT_TYPES = {
    9100: "Impressora",   # RAW/JetDirect — almost exclusively printers
    515: "Impressora",    # LPD
    631: "Impressora",    # IPP
    554: "Câmera IP",     # RTSP
    3389: "Workstation Windows",  # RDP
}

# Weaker port hints — combined with other signals, but always flagged as guess.
_WEAK_PORT_HINTS = {
    22: "Servidor/Linux",
    80: "Servidor Web",
    443: "Servidor Web",
    445: "Windows/SMB",
    139: "Windows/SMB",
    53: "Servidor DNS",
    1723: "Equipamento de rede",  # PPTP
}

# Vendor substring (lowercase) → type. Network OEMs are a fairly reliable tell.
_VENDOR_TYPES = [
    (("ubiquiti", "cisco", "fortinet", "mikrotik", "juniper", "aruba", "tp-link",
      "d-link", "netgear", "huawei", "zyxel"), "Equipamento de rede"),
    (("vmware", "virtualbox", "qemu", "kvm", "hyper-v", "oracle"), "Máquina virtual"),
    (("raspberry",), "Single-board (Raspberry Pi)"),
    (("apple",), "Dispositivo Apple"),
    (("brother", "epson", "xerox", "lexmark", "kyocera", "ricoh", "canon", "zebra"), "Impressora"),
    (("hikvision", "dahua", "axis", "hanwha"), "Câmera IP"),
    (("dell", "hewlett", "hp ", "lenovo", "intel", "asus", "asustek", "micro-star",
      "gigabyte", "supermicro"), "Workstation/PC"),
]

# Hostname substring (lowercase) → type. Weak but useful for named devices.
_HOSTNAME_HINTS = [
    (("printer", "impressora", "print", "_hp", "-hp", "jetdirect"), "Impressora"),
    (("cam", "camera", "câmera", "dvr", "nvr"), "Câmera IP"),
    (("srv", "server", "servidor", "-db", "sql", "host"), "Servidor"),
    (("ap-", "-ap", "switch", "router", "roteador", "gw-", "gateway", "firewall"), "Equipamento de rede"),
    (("nas", "synology", "qnap"), "Storage/NAS"),
    (("desktop-", "laptop-", "pc-", "ws-", "note-"), "Workstation/PC"),
    (("phone", "voip", "sip"), "Telefone IP"),
]


def infer_device_type(vendor=None, hostname=None, open_ports=None):
    """Return (label, is_guess).

    label is always a human PT-BR string; "Desconhecido" when nothing matched.
    is_guess is False only for strong port-based detections.
    """
    ports = set(open_ports or [])
    vendor_l = (vendor or "").lower()
    hostname_l = (hostname or "").lower()

    # 1. Strong port signal — highest confidence, not a guess.
    #    9100/554/3389 isolate device classes very well.
    for port, label in _STRONG_PORT_TYPES.items():
        if port in ports:
            # A printer that also speaks 3389 is implausible; first match wins,
            # and dict order puts printer ports before RDP intentionally.
            return label, False

    # 2. Vendor signal (camera/printer vendors are strong; rest are hints).
    for needles, label in _VENDOR_TYPES:
        if any(n in vendor_l for n in needles):
            # Camera/printer vendors are reliable enough to not flag; generic
            # PC OEMs are only a hint.
            strong = label in ("Câmera IP", "Impressora", "Equipamento de rede", "Máquina virtual")
            return label, not strong

    # 3. Hostname hint (always a guess).
    for needles, label in _HOSTNAME_HINTS:
        if any(n in hostname_l for n in needles):
            return label, True

    # 4. Weak port hint as a last resort (always a guess).
    for port, label in _WEAK_PORT_HINTS.items():
        if port in ports:
            return label, True

    return "Desconhecido", True
