# python/api/routes/l2_discovery.py
"""Endpoints da API para descoberta de Camada 2 (LLDP/CDP), SMB e Conflitos ARP."""

import ipaddress
import logging
import re
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
import src.network.lldp_cdp as lldp_cdp
import src.network.smb_scanner as smb_scanner
import src.network.arp_conflicts as arp_conflicts

router = APIRouter(prefix="/l2", tags=["Descoberta L2 & SMB"])

_TARGET_RE = re.compile(r"^(?:(?:\d{1,3}\.){3}\d{1,3}|[A-Za-z0-9][A-Za-z0-9._\-]{0,252})$")


def _validate_optional_ip(value: Optional[str]) -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    cleaned = str(value).strip()
    try:
        ipaddress.ip_address(cleaned)
    except ValueError as exc:
        raise ValueError(f"interface_ip inválido: {value!r}") from exc
    return cleaned


def _validate_target(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Alvo inválido.")
    cleaned = value.strip()
    if not cleaned or not _TARGET_RE.match(cleaned):
        raise ValueError(f"Alvo inválido: {value!r}")
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", cleaned):
        if not all(0 <= int(o) <= 255 for o in cleaned.split(".")):
            raise ValueError(f"Endereço IPv4 inválido: {value!r}")
    return cleaned


class LLDPListenRequest(BaseModel):
    interface_ip: Optional[str] = Field(None, description="IP da interface/NIC de rede")
    timeout_seconds: Optional[int] = Field(15, ge=1, le=60, description="Tempo limite em segundos para escuta")

    @field_validator("interface_ip")
    @classmethod
    def _interface_ip_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_ip(v)


class SMBSharesRequest(BaseModel):
    target: str = Field(..., description="IP ou Hostname do alvo")
    username: Optional[str] = Field(None, description="Usuário para autenticação")
    password: Optional[str] = Field(None, description="Senha para autenticação")

    @field_validator("target")
    @classmethod
    def _target_must_be_safe(cls, v: str) -> str:
        return _validate_target(v)


@router.post("/lldp-listen")
async def listen_lldp_cdp(req: LLDPListenRequest) -> Dict[str, Any]:
    """Escuta e decodifica anúncios LLDP/CDP de switches conectados."""
    try:
        return lldp_cdp.capture_l2_discovery(
            interface_ip=req.interface_ip,
            timeout_seconds=req.timeout_seconds or 15
        )
    except Exception as exc:
        logging.error(f"Erro na escuta LLDP/CDP: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/smb-shares")
async def get_smb_shares(req: SMBSharesRequest) -> Dict[str, Any]:
    """Descobre e audita compartilhamentos SMB no host remoto."""
    try:
        return smb_scanner.scan_smb_shares(
            target_host=req.target,
            username=req.username,
            password=req.password
        )
    except Exception as exc:
        logging.error(f"Erro ao escanear compartilhamentos SMB para {req.target}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/arp-conflicts")
async def check_arp_conflicts(interface_ip: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Inspeciona tabela ARP e identifica conflitos de IP e anomalias."""
    try:
        clean_ip = _validate_optional_ip(interface_ip)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return arp_conflicts.inspect_arp_table(interface_ip=clean_ip)
    except Exception as exc:
        logging.error(f"Erro ao verificar conflitos ARP: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
