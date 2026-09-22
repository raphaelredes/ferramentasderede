# python/src/network/tls_check.py
"""Inspetor TLS / SSL Avançado:

- Extração da Cadeia Completa de Certificados (Chain of Trust: Leaf -> Intermediate -> Root)
- Auditoria de Protocolos Depreciados (TLS 1.0, 1.1, 1.2, 1.3)
- Suporte e Negociação ALPN (HTTP/2, HTTP/1.1)
- Avaliação de Robustez de Cifras (PFS e AEAD)
"""

import socket
import ssl
import logging
import warnings
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.x509.oid import ExtensionOID
    _HAS_CRYPTO = True
except Exception as e:
    _HAS_CRYPTO = False
    logging.warning(f"cryptography indisponível: {e}")


def _test_protocol_version(host: str, port: int, version: ssl.TLSVersion, timeout: float = 2.0) -> bool:
    """Verifica se o servidor aceita negociar uma versão específica de TLS."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
            except Exception:
                pass
            ctx.minimum_version = version
            ctx.maximum_version = version
            with socket.create_connection((host, port), timeout=timeout) as s:
                with ctx.wrap_socket(s, server_hostname=host):
                    return True
    except Exception:
        return False


def _evaluate_cipher(cipher_name: Optional[str], tls_version: Optional[str]) -> Dict[str, Any]:
    """Avalia se a cifra negociada possui PFS (Perfect Forward Secrecy) e AEAD."""
    if not cipher_name:
        return {"name": "Desconhecida", "grade": "unknown", "pfs": False, "aead": False, "rating": "Desconhecida"}

    c_upper = cipher_name.upper()

    # TLS 1.3 ciphers possuem PFS e AEAD por especificação padrão
    is_tls13 = (tls_version == "TLSv1.3")
    is_pfs = is_tls13 or ("ECDHE" in c_upper) or ("DHE" in c_upper)
    is_aead = ("GCM" in c_upper) or ("CHACHA20" in c_upper) or ("POLY1305" in c_upper) or ("CCM" in c_upper)
    is_weak = ("CBC" in c_upper) or ("RC4" in c_upper) or ("3DES" in c_upper) or ("DES" in c_upper)

    if (is_pfs and is_aead) or is_tls13:
        grade = "strong"
        rating = "Forte (PFS + AEAD)"
    elif is_weak:
        grade = "weak"
        rating = "Fraca / Insegura"
    else:
        grade = "moderate"
        rating = "Moderada"

    return {
        "name": cipher_name,
        "grade": grade,
        "pfs": is_pfs,
        "aead": is_aead,
        "rating": rating
    }


def _parse_cert_details(cert) -> Dict[str, Any]:
    """Extrai detalhes estruturados de um certificado cryptography x509."""
    def _name_str(n):
        try:
            return n.rfc4514_string()
        except Exception:
            return str(n)

    # Extração de SANs
    sans = []
    try:
        ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        sans = ext.value.get_values_for_type(x509.DNSName)
    except Exception:
        sans = []

    # Validade
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

    # Common Name (CN)
    cn = None
    try:
        from cryptography.x509.oid import NameOID
        cns = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cns:
            cn = cns[0].value
    except Exception:
        pass

    # Issuer CN / Organization
    issuer_org = None
    try:
        from cryptography.x509.oid import NameOID
        orgs = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        if orgs:
            issuer_org = orgs[0].value
    except Exception:
        pass

    return {
        "cn": cn,
        "subject": _name_str(cert.subject),
        "issuer": _name_str(cert.issuer),
        "issuer_org": issuer_org,
        "serial": format(cert.serial_number, "x"),
        "sans": sans,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "days_to_expiry": days_to_expiry,
        "is_expired": is_expired,
        "not_yet_valid": not_yet_valid,
        "signature_algorithm": getattr(cert.signature_hash_algorithm, "name", None),
    }


def check_certificate(host: str, port: int = 443, timeout: float = 6.0) -> Dict[str, Any]:
    """Retorna análise completa do host TLS:

    - Certificado Folha e Cadeia de Confiança (Chain of Trust)
    - Protocolos TLS aceitos (detecção de TLS 1.0 e 1.1 obsoletos)
    - Negociação ALPN (HTTP/2 vs HTTP/1.1)
    - Avaliação de robustez da cifra
    """
    clean_host = (host or "").strip()
    if not clean_host:
        return {"ok": False, "error": "Informe um host válido."}

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_alpn_protocols(['h2', 'http/1.1'])
    except Exception:
        pass

    der_chain = []
    negotiated_version = None
    negotiated_cipher = None
    alpn_proto = None

    try:
        with socket.create_connection((clean_host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=clean_host) as ssock:
                negotiated_version = ssock.version()
                cipher_tuple = ssock.cipher()
                negotiated_cipher = cipher_tuple[0] if cipher_tuple else None
                alpn_proto = ssock.selected_alpn_protocol()
                try:
                    der_chain = ssock.get_unverified_chain() or []
                except Exception:
                    der = ssock.getpeercert(binary_form=True)
                    if der:
                        der_chain = [der]
    except ssl.SSLError as e:
        return {"ok": False, "error": f"Erro SSL/TLS: {e}"}
    except socket.timeout:
        return {"ok": False, "error": "Tempo limite esgotado ao conectar no servidor."}
    except (socket.gaierror, ConnectionRefusedError, OSError) as e:
        return {"ok": False, "error": f"Falha de conexão com {clean_host}:{port} - {e}"}

    if not der_chain:
        return {"ok": False, "error": "O servidor não enviou nenhum certificado durante o handshake."}

    if not _HAS_CRYPTO:
        return {
            "ok": True,
            "host": clean_host,
            "port": port,
            "tls_version": negotiated_version,
            "cipher": negotiated_cipher,
            "alpn": alpn_proto,
            "warning": "Biblioteca cryptography indisponível para leitura detalhada de certificados."
        }

    # Parse da Cadeia de Certificados
    chain_parsed = []
    for der in der_chain:
        try:
            c = x509.load_der_x509_certificate(der, default_backend())
            chain_parsed.append(_parse_cert_details(c))
        except Exception as e:
            logging.debug(f"Erro ao parsear certificado da cadeia: {e}")

    leaf = chain_parsed[0] if chain_parsed else {}

    # Auditoria de Protocolos em background rápido
    # Testar TLS 1.0, 1.1, 1.2 e 1.3
    protocol_audit = {
        "TLSv1.0": _test_protocol_version(clean_host, port, ssl.TLSVersion.TLSv1, timeout=1.5),
        "TLSv1.1": _test_protocol_version(clean_host, port, ssl.TLSVersion.TLSv1_1, timeout=1.5),
        "TLSv1.2": _test_protocol_version(clean_host, port, ssl.TLSVersion.TLSv1_2, timeout=1.5),
        "TLSv1.3": _test_protocol_version(clean_host, port, ssl.TLSVersion.TLSv1_3, timeout=1.5),
    }

    # Avaliação da Cifra
    cipher_eval = _evaluate_cipher(negotiated_cipher, negotiated_version)

    has_deprecated_tls = protocol_audit["TLSv1.0"] or protocol_audit["TLSv1.1"]

    return {
        "ok": True,
        "host": clean_host,
        "port": port,
        "subject": leaf.get("subject"),
        "issuer": leaf.get("issuer"),
        "cn": leaf.get("cn"),
        "serial": leaf.get("serial"),
        "sans": leaf.get("sans", []),
        "not_before": leaf.get("not_before"),
        "not_after": leaf.get("not_after"),
        "days_to_expiry": leaf.get("days_to_expiry"),
        "is_expired": leaf.get("is_expired"),
        "not_yet_valid": leaf.get("not_yet_valid"),
        "tls_version": negotiated_version,
        "cipher": negotiated_cipher,
        "cipher_eval": cipher_eval,
        "signature_algorithm": leaf.get("signature_algorithm"),
        "alpn": alpn_proto or "Nenhum (HTTP/1.1)",
        "chain": chain_parsed,
        "chain_length": len(chain_parsed),
        "protocols": protocol_audit,
        "has_deprecated_protocols": has_deprecated_tls,
    }
