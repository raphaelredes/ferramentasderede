import { useState, useEffect } from 'react';
import { X, Download, BarChart2 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface HostMetricsModalProps {
    isOpen: boolean;
    onClose: () => void;
    hostName: string;
    hostIp: string;
    hostId?: number;
}

export function HostMetricsModal({ isOpen, onClose, hostName, hostIp, hostId }: HostMetricsModalProps) {
    const { showToast } = useToast();
    const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d' | '30d'>('24h');
    const [metricsData, setMetricsData] = useState<any>(null);

    const fetchMetrics = async () => {
        try {
            const url = hostId 
                ? `${API_BASE}/metrics/history/${hostId}?range=${timeRange}`
                : `${API_BASE}/metrics/history-by-ip/${hostIp}?range=${timeRange}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setMetricsData(data);
        } catch (err: any) {
            showToast(`Erro ao carregar métricas: ${err.message}`, 'error');
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchMetrics();
        }
    }, [isOpen, timeRange, hostId, hostIp]);

    if (!isOpen) return null;

    const summary = metricsData?.summary || {};
    const points = metricsData?.points || [];

    const handleExportReport = async () => {
        try {
            const res = await fetch(`${API_BASE}/reports/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    report_type: 'sla',
                    host_id: hostId || null,
                    ip_address: hostIp,
                    time_range: timeRange
                })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const html = await res.text();
            const blob = new Blob([html], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
            showToast('Relatório de SLA aberto para impressão!', 'success');
        } catch (err: any) {
            showToast(`Erro ao gerar relatório: ${err.message}`, 'error');
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950/50">
                    <div className="flex items-center gap-3">
                        <BarChart2 className="text-blue-400" size={22} />
                        <div>
                            <h2 className="text-base font-semibold text-zinc-100">{hostName}</h2>
                            <p className="text-xs text-zinc-400 font-mono">{hostIp}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex bg-zinc-950 p-1 rounded-lg border border-zinc-800 text-xs">
                            {(['1h', '6h', '24h', '7d', '30d'] as const).map(r => (
                                <button
                                    key={r}
                                    onClick={() => setTimeRange(r)}
                                    className={`px-2.5 py-1 rounded-md font-medium transition-colors ${timeRange === r ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-zinc-200'}`}
                                >
                                    {r}
                                </button>
                            ))}
                        </div>
                        <button
                            onClick={handleExportReport}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors border border-zinc-700"
                            title="Exportar Relatório SLA"
                        >
                            <Download size={14} />
                            Relatório
                        </button>
                        <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="p-6 space-y-6 overflow-y-auto">
                    {/* Summary KPI Cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl">
                            <div className="text-zinc-500 text-xs">Disponibilidade (SLA)</div>
                            <div className="text-xl font-bold text-emerald-400 mt-1">{summary.uptime_percent ?? 100}%</div>
                        </div>
                        <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl">
                            <div className="text-zinc-500 text-xs">Latência Média</div>
                            <div className="text-xl font-bold text-blue-400 mt-1">{summary.avg_latency ?? 0} ms</div>
                        </div>
                        <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl">
                            <div className="text-zinc-500 text-xs">Jitter Médio</div>
                            <div className="text-xl font-bold text-amber-400 mt-1">{summary.avg_jitter ?? 0} ms</div>
                        </div>
                        <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl">
                            <div className="text-zinc-500 text-xs">Qualidade MOS (VoIP)</div>
                            <div className="text-xl font-bold text-cyan-400 mt-1">{summary.mos_score ?? 4.5} / 5.0</div>
                        </div>
                    </div>

                    {/* Chart */}
                    <div className="bg-zinc-950 p-4 border border-zinc-800 rounded-xl space-y-2">
                        <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
                            <span className="font-semibold text-zinc-200">Histórico de Latência ({timeRange})</span>
                            <span>{points.length} amostras</span>
                        </div>
                        <div className="h-[240px] w-full">
                            {points.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={points} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                        <XAxis dataKey="time_label" stroke="#71717a" fontSize={11} />
                                        <YAxis stroke="#71717a" fontSize={11} />
                                        <Tooltip 
                                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px', fontSize: '12px' }}
                                            formatter={(value: any) => [`${value} ms`, 'Latência']}
                                        />
                                        <Area type="monotone" dataKey="latency_ms" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#latencyGradient)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-full flex items-center justify-center text-zinc-500 text-xs">
                                    Nenhum ponto registrado para esta janela temporal.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
