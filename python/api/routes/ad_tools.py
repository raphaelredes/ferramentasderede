# python/api/routes/ad_tools.py
"""Endpoints da API para diagnóstico especializado de Active Directory."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import src.network.ad_tools as ad_tools

router = APIRouter(prefix="/ad", tags=["Active Directory"])


class ADPortTestRequest(BaseModel):
    target: str = Field(..., description="IP ou FQDN do Domain Controller")
    source_ip: Optional[str] = Field(None, description="IP da interface de saída (NIC/VLAN)")
    timeout: Optional[float] = Field(1.5, description="Timeout por porta em segundos")


class ADSRVTestRequest(BaseModel):
    domain: str = Field(..., description="Nome do domínio Active Directory (ex: corp.local)")
    dns_server: Optional[str] = Field(None, description="Servidor DNS específico a consultar")
    site: Optional[str] = Field(None, description="Nome do Site AD opcional")


class ADTimeSkewRequest(BaseModel):
    target: str = Field(..., description="IP ou FQDN do PDC Emulator / Domain Controller")
    source_ip: Optional[str] = Field(None, description="IP da interface de saída")


@router.post("/test-ports")
async def test_ad_port_matrix(req: ADPortTestRequest) -> Dict[str, Any]:
    """Testa a matriz de portas essenciais do Active Directory para o DC informado."""
    try:
        results = ad_tools.test_ad_port_matrix(
            target_host=req.target,
            source_ip=req.source_ip,
            timeout=req.timeout or 1.5
        )
        open_count = sum(1 for r in results if r.get("open"))
        return {
            "target": req.target,
            "total_ports": len(results),
            "open_ports": open_count,
            "status": "HEALTHY" if open_count == len(results) else ("DEGRADED" if open_count > 0 else "UNREACHABLE"),
            "results": results
        }
    except Exception as exc:
        logging.error(f"Erro ao testar portas AD para {req.target}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-srv")
async def test_ad_srv_records(req: ADSRVTestRequest) -> Dict[str, Any]:
    """Consulta e valida registros DNS SRV críticos para localização de DCs."""
    try:
        results = ad_tools.test_ad_srv_records(
            domain=req.domain,
            dns_server=req.dns_server,
            site=req.site
        )
        found_count = sum(1 for r in results if r.get("found"))
        return {
            "domain": req.domain,
            "dns_server": req.dns_server,
            "total_queries": len(results),
            "found_count": found_count,
            "results": results
        }
    except Exception as exc:
        logging.error(f"Erro ao validar registros SRV para {req.domain}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/check-skew")
async def check_ad_time_skew(req: ADTimeSkewRequest) -> Dict[str, Any]:
    """Verifica desvio de relógio (Time Skew) com o Domain Controller para Kerberos."""
    try:
        return ad_tools.check_kerberos_time_skew(
            target_host=req.target,
            source_ip=req.source_ip
        )
    except Exception as exc:
        logging.error(f"Erro ao checar time skew para {req.target}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


class ADFSMORequest(BaseModel):
    domain: Optional[str] = Field(None, description="Nome do domínio AD (opcional)")


class ADReplicationRequest(BaseModel):
    dc_target: Optional[str] = Field(None, description="Nome ou IP do DC alvo (opcional)")


@router.post("/fsmo")
async def get_ad_fsmo(req: ADFSMORequest) -> Dict[str, Any]:
    """Descobre e mapeia os 5 detentores de funções FSMO no Active Directory."""
    try:
        res = ad_tools.get_ad_fsmo_roles(domain=req.domain)
        if not res.get("ok"):
            raise HTTPException(status_code=500, detail=res.get("error", "Erro ao consultar FSMO"))
        return res
    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Erro ao consultar FSMO: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/replication")
async def get_ad_replication(req: ADReplicationRequest) -> Dict[str, Any]:
    """Audita a replicação do Active Directory com repadmin /replsummary."""
    try:
        res = ad_tools.check_ad_replication(dc_target=req.dc_target)
        if not res.get("ok"):
            raise HTTPException(status_code=500, detail=res.get("error", "Erro ao auditar replicação"))
        return res
    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Erro ao auditar replicação: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

