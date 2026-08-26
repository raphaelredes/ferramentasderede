# python/api/routes/metrics.py
"""Endpoints da API para histórico de métricas de rede e relatórios de SLA."""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import src.network.metrics_history as metrics_history

router = APIRouter(prefix="/metrics", tags=["Métricas & SLA"])


class RecordMetricRequest(BaseModel):
    host_id: Optional[int] = Field(None, description="ID do host monitorado")
    ip_address: str = Field(..., description="Endereço IP do host")
    latency_ms: Optional[float] = Field(None, description="Latência medida em ms")
    packet_loss: float = Field(0.0, description="Percentual de perda de pacotes")
    is_online: bool = Field(True, description="Status online do host")
    jitter_ms: float = Field(0.0, description="Jitter medido em ms")


@router.post("/record")
async def record_host_metric(req: RecordMetricRequest) -> Dict[str, str]:
    """Registra uma medição pontual de métrica no histórico."""
    try:
        metrics_history.record_metric(
            host_id=req.host_id,
            ip_address=req.ip_address,
            latency_ms=req.latency_ms,
            packet_loss=req.packet_loss,
            is_online=req.is_online,
            jitter_ms=req.jitter_ms
        )
        return {"status": "ok"}
    except Exception as exc:
        logging.error(f"Erro ao salvar métrica para {req.ip_address}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history/{host_id}")
async def get_metrics_by_host_id(
    host_id: int,
    range: str = Query("24h", description="Janela temporal: 1h, 6h, 24h, 7d, 30d")
) -> Dict[str, Any]:
    """Retorna a série temporal e métricas de SLA/Uptime para um host_id."""
    try:
        return metrics_history.get_host_metrics_history(host_id=host_id, time_range=range)
    except Exception as exc:
        logging.error(f"Erro ao buscar histórico do host {host_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history-by-ip/{ip_address}")
async def get_metrics_by_ip(
    ip_address: str,
    range: str = Query("24h", description="Janela temporal: 1h, 6h, 24h, 7d, 30d")
) -> Dict[str, Any]:
    """Retorna a série temporal e métricas de SLA/Uptime por endereço IP."""
    try:
        return metrics_history.get_host_metrics_history(ip_address=ip_address, time_range=range)
    except Exception as exc:
        logging.error(f"Erro ao buscar histórico para IP {ip_address}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
