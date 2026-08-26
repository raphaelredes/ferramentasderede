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
