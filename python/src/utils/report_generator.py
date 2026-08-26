# python/src/utils/report_generator.py
"""Gerador de relatórios técnicos e executivos em formato HTML e CSV.

Produz relatórios formatados prontos para impressão (PDF via navegador)
ou documentação corporativa para auditoria de inventário, SLA e segurança.
"""

import time
from typing import List, Dict, Any, Optional

HTML_TEMPLATE_HEADER = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #f8fafc; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #3b82f6; padding-bottom: 16px; margin-bottom: 24px; }}
        h1 {{ margin: 0; font-size: 24px; color: #60a5fa; }}
        .meta {{ font-size: 13px; color: #94a3b8; text-align: right; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
        .badge-green {{ background: #065f46; color: #34d399; }}
        .badge-red {{ background: #7f1d1d; color: #f87171; }}
        .badge-blue {{ background: #1e3a8a; color: #60a5fa; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
        th {{ background: #0f172a; color: #cbd5e1; text-align: left; padding: 12px; border-bottom: 2px solid #334155; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #334155; color: #e2e8f0; }}
        tr:nth-child(even) {{ background: #1e293b; }}
        tr:nth-child(odd) {{ background: #182234; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .summary-card {{ background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #334155; }}
        .summary-card .label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; }}
        .summary-card .value {{ font-size: 22px; font-weight: bold; color: #38bdf8; margin-top: 4px; }}
        .footer {{ margin-top: 32px; font-size: 12px; color: #64748b; text-align: center; border-top: 1px solid #334155; padding-top: 16px; }}
        @media print {{
            body {{ background: #fff; color: #000; padding: 0; }}
            .container {{ background: #fff; color: #000; box-shadow: none; border: none; padding: 0; }}
            th {{ background: #f1f5f9; color: #000; border-bottom: 2px solid #000; }}
            td {{ color: #000; border-bottom: 1px solid #ddd; }}
            .summary-card {{ background: #f8fafc; border: 1px solid #ddd; color: #000; }}
            .summary-card .value {{ color: #0284c7; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>{title}</h1>
            <div style="font-size: 14px; color: #94a3b8; margin-top: 4px;">Ferramentas de Rede &bull; Diagnóstico & Auditoria</div>
        </div>
        <div class="meta">
            <div><strong>Gerado em:</strong> {generated_at}</div>
            <div><strong>Tipo:</strong> {report_type}</div>
        </div>
    </div>
"""

HTML_TEMPLATE_FOOTER = """
    <div class="footer">
        Relatório gerado automaticamente pelo Ferramentas de Rede. Documento confidencial de infraestrutura.
    </div>
</div>
</body>
</html>
"""


def generate_inventory_report_html(hosts: List[Dict[str, Any]]) -> str:
    """Gera relatório HTML de inventário de hosts e status."""
    total_hosts = len(hosts)
    online_hosts = sum(1 for h in hosts if h.get("status") == "online")
    offline_hosts = total_hosts - online_hosts

    summary_html = f"""
    <div class="summary-grid">
        <div class="summary-card">
            <div class="label">Total de Dispositivos</div>
            <div class="value">{total_hosts}</div>
        </div>
        <div class="summary-card">
            <div class="label">Hosts Online</div>
            <div class="value" style="color: #34d399;">{online_hosts}</div>
        </div>
        <div class="summary-card">
            <div class="label">Hosts Offline</div>
            <div class="value" style="color: #f87171;">{offline_hosts}</div>
        </div>
        <div class="summary-card">
            <div class="label">Disponibilidade Geral</div>
            <div class="value">{round((online_hosts / total_hosts * 100) if total_hosts else 100, 1)}%</div>
        </div>
    </div>
    """

    rows_html = ""
    for h in hosts:
        status = h.get("status", "unknown")
        badge_class = "badge-green" if status == "online" else "badge-red"
        rows_html += f"""
        <tr>
            <td><strong>{h.get('name') or 'N/A'}</strong></td>
            <td><code>{h.get('address') or h.get('ip') or 'N/A'}</code></td>
            <td>{h.get('group_name') or h.get('group') or 'Geral'}</td>
            <td>{h.get('vendor') or 'Desconhecido'}</td>
            <td><span class="badge {badge_class}">{status.upper()}</span></td>
            <td>{f"{h.get('latency')} ms" if h.get('latency') is not None else '-'}</td>
        </tr>
        """

    table_html = f"""
    <table>
        <thead>
            <tr>
                <th>Nome do Host</th>
                <th>Endereço IP</th>
                <th>Grupo / VLAN</th>
                <th>Fabricante (MAC)</th>
                <th>Status</th>
                <th>Latência</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """

    now_str = time.strftime("%d/%m/%Y às %H:%M:%S")
    header = HTML_TEMPLATE_HEADER.format(
        title="Relatório de Inventário e Status de Rede",
        generated_at=now_str,
        report_type="Inventário Corporativo"
    )
    return header + summary_html + table_html + HTML_TEMPLATE_FOOTER


def generate_sla_report_html(host_name: str, ip: str, metrics: Dict[str, Any]) -> str:
    """Gera relatório HTML de SLA e histórico de latência."""
    summary = metrics.get("summary", {})
    points = metrics.get("points", [])

    summary_html = f"""
    <div class="summary-grid">
        <div class="summary-card">
            <div class="label">Uptime (SLA)</div>
            <div class="value" style="color: #34d399;">{summary.get('uptime_percent', 100)}%</div>
        </div>
        <div class="summary-card">
            <div class="label">Latência Média</div>
            <div class="value">{summary.get('avg_latency', 0)} ms</div>
        </div>
        <div class="summary-card">
            <div class="label">Jitter Médio</div>
            <div class="value">{summary.get('avg_jitter', 0)} ms</div>
        </div>
        <div class="summary-card">
            <div class="label">Qualidade MOS</div>
            <div class="value" style="color: #38bdf8;">{summary.get('mos_score', 4.5)} / 5.0</div>
        </div>
    </div>
    """

    rows_html = ""
    for p in points[-50:]:  # Últimas 50 amostras
        is_up = p.get("is_online", True)
        badge = '<span class="badge badge-green">UP</span>' if is_up else '<span class="badge badge-red">DOWN</span>'
        rows_html += f"""
        <tr>
            <td>{p.get('time_label', '-')}</td>
            <td>{badge}</td>
            <td>{p.get('latency_ms', '-')} ms</td>
            <td>{p.get('jitter_ms', 0)} ms</td>
            <td>{p.get('packet_loss', 0)}%</td>
        </tr>
        """

    table_html = f"""
    <h3>Amostras Recentes de Monitoramento ({host_name} - {ip})</h3>
    <table>
        <thead>
            <tr>
                <th>Horário</th>
                <th>Status</th>
                <th>Latência</th>
                <th>Jitter</th>
                <th>Perda</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    """

    now_str = time.strftime("%d/%m/%Y às %H:%M:%S")
    header = HTML_TEMPLATE_HEADER.format(
        title=f"Relatório de SLA & Latência: {host_name}",
        generated_at=now_str,
        report_type="SLA & Performance"
    )
    return header + summary_html + table_html + HTML_TEMPLATE_FOOTER
