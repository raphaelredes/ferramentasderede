# app/network/tls_check.py
#
# TLS certificate inspector: connects to host:port, completes the handshake,
# and reports the leaf certificate's subject / issuer / SAN / validity window /
# days-to-expiry. Pure stdlib `ssl`+`socket` for the handshake; `cryptography`
# (already a dependency) for robust DER parsing.
#
# WHY this matters here: a multi-domain/multi-VLAN analyst constantly chases
# expiring internal certs on appliances and intranet services. This surfaces
# expiry without leaving the app, and works against any TLS port (443, 8443,
# 636/LDAPS, 993, etc.).

import socket
import ssl
import logging
from datetime import datetime, timezone


def check_certificate(host, port=443, timeout=6.0):
    """Return a dict describing the TLS leaf cert of host:port.

    We deliberately DON'T verify the chain (CERT_NONE) — the goal is to inspect
    whatever the server presents, including self-signed / internal-CA certs the
    local trust store doesn't know. That's the realistic corporate case.

    Returns {"ok": bool, ...fields} ; on failure {"ok": False, "error": str}.
    """
    # Permissive context: we want the cert even if it's self-signed/expired.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    der = None
    negotiated_version = None
    negotiated_cipher = None
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            # SNI matters: many hosts serve different certs per server_name.
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
                negotiated_version = ssock.version()
                cipher = ssock.cipher()
                negotiated_cipher = cipher[0] if cipher else None
    except ssl.SSLError as e:
        return {"ok": False, "error": f"Erro TLS: {e}"}
    except socket.timeout:
        return {"ok": False, "error": "Tempo esgotado ao conectar."}
    except (socket.gaierror, ConnectionRefusedError, OSError) as e:
        return {"ok": False, "error": f"Falha de conexão: {e}"}

    if not der:
        return {"ok": False, "error": "O servidor não apresentou certificado."}

    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        cert = x509.load_der_x509_certificate(der, default_backend())
    except Exception as e:
        logging.warning(f"TLS cert parse failed for {host}:{port}: {e}")
        return {"ok": False, "error": f"Não foi possível ler o certificado: {e}"}

    def _name(n):
        try:
            return n.rfc4514_string()
        except Exception as e:
            logging.debug(f"TLS name format fallback: {e}")
            return str(n)

    # SAN list (the modern source of truth for which names a cert covers).
    sans = []
    try:
        from cryptography.x509.oid import ExtensionOID
        ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        from cryptography import x509 as _x509
        sans = ext.value.get_values_for_type(_x509.DNSName)
    except Exception as e:
        # No SAN extension (older/internal certs) or parse issue — log so a
        # silent empty list isn't mistaken for "cert truly has no SANs".
        logging.debug(f"TLS SAN extraction for {host}:{port}: {e}")
        sans = []

    # Validity. cryptography exposes *_utc on modern versions; fall back to the
    # naive attributes and tag them UTC for older builds.
    try:
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
    except AttributeError:
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days_to_expiry = (not_after - now).days
    is_expired = now > not_after
    not_yet_valid = now < not_before

    return {
        "ok": True,
        "host": host,
        "port": port,
        "subject": _name(cert.subject),
        "issuer": _name(cert.issuer),
        "serial": format(cert.serial_number, "x"),
        "sans": sans,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "days_to_expiry": days_to_expiry,
        "is_expired": is_expired,
        "not_yet_valid": not_yet_valid,
        "tls_version": negotiated_version,
        "cipher": negotiated_cipher,
        "signature_algorithm": getattr(cert.signature_hash_algorithm, "name", None),
    }
