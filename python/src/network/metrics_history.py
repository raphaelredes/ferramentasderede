# python/src/network/metrics_history.py
"""Módulo de persistência de séries temporais de métricas de rede no SQLite.

Armazena histórico de latência, jitter, perda de pacotes e status para cálculo
de disponibilidade (Uptime/SLA) e análise temporal no Dashboard.
"""

import time
import logging
from typing import Dict, Any, Optional
from src.core.database import db, _retry_on_locked

# Criação da tabela de métricas se não existir
@_retry_on_locked()
def init_metrics_table():
    """Garante que a tabela de métricas de rede existe no SQLite."""
    with db._write_lock:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS host_metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id INTEGER,
                    ip_address TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    latency_ms REAL,
                    packet_loss REAL DEFAULT 0,
                    is_online INTEGER NOT NULL,
                    jitter_ms REAL DEFAULT 0
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_host_time ON host_metrics_history(host_id, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_ip_time ON host_metrics_history(ip_address, timestamp)')
            conn.commit()


@_retry_on_locked()
def record_metric(host_id: Optional[int], ip_address: str, latency_ms: Optional[float],
                  packet_loss: float = 0.0, is_online: bool = True, jitter_ms: float = 0.0):
    """Grava um ponto de métrica no banco de dados com timestamp atual."""
    try:
        now = time.time()
        with db._write_lock:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO host_metrics_history 
                    (host_id, ip_address, timestamp, latency_ms, packet_loss, is_online, jitter_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (host_id, ip_address, now, latency_ms, packet_loss, 1 if is_online else 0, jitter_ms))
                conn.commit()
    except Exception as e:
        logging.debug(f"Erro ao gravar métrica de histórico: {e}")


@_retry_on_locked()
def get_host_metrics_history(host_id: Optional[int] = None, ip_address: Optional[str] = None,
                             time_range: str = "24h") -> Dict[str, Any]:
    """Retorna histórico de métricas com agregações de SLA, min, max, avg e jitter."""
    init_metrics_table()
    now = time.time()
    seconds_map = {
        "1h": 3600,
        "6h": 21600,
        "24h": 86400,
        "7d": 604800,
        "30d": 2592000
    }
    window_seconds = seconds_map.get(time_range, 86400)
    cutoff = now - window_seconds

    with db._get_connection() as conn:
        cursor = conn.cursor()
        if host_id:
            cursor.execute('''
                SELECT timestamp, latency_ms, packet_loss, is_online, jitter_ms
                FROM host_metrics_history
                WHERE host_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            ''', (host_id, cutoff))
        elif ip_address:
            cursor.execute('''
                SELECT timestamp, latency_ms, packet_loss, is_online, jitter_ms
                FROM host_metrics_history
                WHERE ip_address = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            ''', (ip_address, cutoff))
        else:
            return {"points": [], "summary": {}}

        rows = cursor.fetchall()

    if not rows:
        return {
            "points": [],
            "summary": {
                "total_checks": 0,
                "uptime_percent": 100.0,
                "avg_latency": 0.0,
                "min_latency": 0.0,
                "max_latency": 0.0,
                "avg_jitter": 0.0,
                "avg_packet_loss": 0.0,
                "mos_score": 4.5
            }
        }

    points = []
    latencies = []
    jitters = []
    online_count = 0
    total_loss = 0.0

    step = max(1, len(rows) // 150)
    for i, row in enumerate(rows):
        ts, lat, loss, online, jit = row
        is_up = bool(online)
        if is_up:
            online_count += 1
            if lat is not None:
                latencies.append(lat)
            if jit is not None:
                jitters.append(jit)
        total_loss += (loss or 0)

        if i % step == 0 or i == len(rows) - 1:
            points.append({
                "timestamp": ts,
                "time_label": time.strftime("%H:%M", time.localtime(ts)) if window_seconds <= 86400 else time.strftime("%d/%m %H:%M", time.localtime(ts)),
                "latency_ms": round(lat, 2) if lat is not None else None,
                "packet_loss": round(loss or 0, 1),
                "is_online": is_up,
                "jitter_ms": round(jit or 0, 2)
            })

    total_checks = len(rows)
    uptime_pct = round((online_count / total_checks) * 100, 2) if total_checks > 0 else 100.0
    avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    min_lat = round(min(latencies), 2) if latencies else 0.0
    max_lat = round(max(latencies), 2) if latencies else 0.0
    avg_jit = round(sum(jitters) / len(jitters), 2) if jitters else 0.0
    avg_loss = round(total_loss / total_checks, 2) if total_checks > 0 else 0.0

    effective_latency = avg_lat + (avg_jit * 2) + 10
    r_factor = 93.2 - (effective_latency / 40.0) - (avg_loss * 2.5)
    r_factor = max(0, min(100, r_factor))
    mos_score = 1.0 + (0.035 * r_factor) + (r_factor * (100 - r_factor) * (r_factor - 60) * 7.0 / 1000000.0)
    mos_score = max(1.0, min(4.5, round(mos_score, 2)))

    return {
        "points": points,
        "summary": {
            "total_checks": total_checks,
            "uptime_percent": uptime_pct,
            "avg_latency": avg_lat,
            "min_latency": min_lat,
            "max_latency": max_lat,
            "avg_jitter": avg_jit,
            "avg_packet_loss": avg_loss,
            "mos_score": mos_score
        }
    }


@_retry_on_locked()
def purge_old_metrics(retention_days: int = 30):
    """Remove registros de métricas mais antigos que retention_days para economizar disco."""
    try:
        cutoff = time.time() - (retention_days * 86400)
        with db._write_lock:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM host_metrics_history WHERE timestamp < ?', (cutoff,))
                conn.commit()
    except Exception as e:
        logging.debug(f"Erro ao purgar métricas antigas: {e}")
