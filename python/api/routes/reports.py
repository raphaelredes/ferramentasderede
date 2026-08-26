# python/api/routes/reports.py
"""Endpoints da API para geração e download de relatórios técnicos."""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
import src.utils.report_generator as report_generator
import src.network.metrics_history as metrics_history
from src.core.database import db

router = APIRouter(prefix="/reports", tags=["Relatórios & Auditoria"])


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(..., description="Tipo do relatório: 'inventory' ou 'sla'")
    host_id: Optional[int] = Field(None, description="ID do host (para relatório de SLA)")
    ip_address: Optional[str] = Field(None, description="IP do host (para relatório de SLA)")
    time_range: Optional[str] = Field("24h", description="Janela de tempo: 24h, 7d, 30d")


@router.post("/generate")
async def generate_report(req: ReportGenerateRequest) -> Response:
    """Gera um relatório HTML completo pronto para visualização e impressão PDF."""
    try:
        if req.report_type == "inventory":
            hosts = db.get_all_hosts()
            html_content = report_generator.generate_inventory_report_html(hosts)
            return Response(content=html_content, media_type="text/html")
            
        elif req.report_type == "sla":
            metrics = metrics_history.get_host_metrics_history(
                host_id=req.host_id,
                ip_address=req.ip_address,
                time_range=req.time_range or "24h"
            )
            
            host_name = "Host"
            host_ip = req.ip_address or ""
            if req.ip_address:
                h = db.get_host(req.ip_address)
                if h:
                    host_name = h.get("hostname") or h.get("address") or "Host"
                    host_ip = h.get("address") or req.ip_address

            html_content = report_generator.generate_sla_report_html(
                host_name=host_name,
                ip=host_ip,
                metrics=metrics
            )
            return Response(content=html_content, media_type="text/html")
        else:
            raise HTTPException(status_code=400, detail=f"Tipo de relatório '{req.report_type}' inválido.")

    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Erro ao gerar relatório {req.report_type}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
