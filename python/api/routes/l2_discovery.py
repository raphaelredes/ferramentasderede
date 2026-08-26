# python/api/routes/l2_discovery.py
"""Endpoints da API para descoberta de Camada 2 (LLDP/CDP), SMB e Conflitos ARP."""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import src.network.lldp_cdp as lldp_cdp
import src.network.smb_scanner as smb_scanner
import src.network.arp_conflicts as arp_conflicts

router = APIRouter(prefix="/l2", tags=["Descoberta L2 & SMB"])


class LLDPListenRequest(BaseModel):
    interface_ip: Optional[str] = Field(None, description="IP da interface/NIC de rede")
    timeout_seconds: Optional[int] = Field(15, description="Tempo limite em segundos para escuta")


class SMBSharesRequest(BaseModel):
    target: str = Field(..., description="IP ou Hostname do alvo")
    username: Optional[str] = Field(None, description="Usuário para autenticação")
    password: Optional[str] = Field(None, description="Senha para autenticação")


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
        return arp_conflicts.inspect_arp_table(interface_ip=interface_ip)
    except Exception as exc:
        logging.error(f"Erro ao verificar conflitos ARP: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
