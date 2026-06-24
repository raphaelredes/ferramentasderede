import { useEffect, useState } from 'react';
import {
    Area, AreaChart, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import { Activity, TrendingUp } from 'lucide-react';
import { API_BASE } from '../../config/api';

interface MetricPoint {
    ts: number;
    online: number;      // 1/0
    latency: number | null;
    packet_loss_pct: number | null;
}

interface MetricsResponse {
    address: string;
    range: string;
    sample_count: number;
    uptime_pct: number | null;
    points: MetricPoint[];
}

type RangeKey = '24h' | '7d';

/**
 * Persistent uptime/latency history for a host. Self-contained: fetches
 * /hosts/{address}/metrics and renders independent of WinRM auth (works for any
 * monitored host). Empty state when no samples exist yet — the sampler writes
 * one point per minute, so a freshly-added host shows data after a few minutes.
 */
export const HostHistoryTab: React.FC<{ address: string }> = ({ address }) => {
    const [range, setRange] = useState<RangeKey>('24h');
    const [data, setData] = useState<MetricsResponse | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        (async () => {
            try {
                const res = await fetch(`${API_BASE}/hosts/${encodeURIComponent(address)}/metrics?range=${range}`);
                const json = await res.json();
                if (!cancelled) setData(res.ok ? json : null);
            } catch {
                if (!cancelled) setData(null);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [address, range]);

    // Recharts wants plottable rows. Map epoch→label and keep latency null for
    // offline points so the area breaks instead of dropping to zero (which would
    // read as "0 ms", not "down").
    const chartData = (data?.points || []).map(p => ({
        ts: p.ts,
        label: formatTick(p.ts, range),
        latency: p.online ? p.latency : null,
        online: p.online,
    }));

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-white flex items-center gap-2">
                    <Activity size={20} className="text-blue-400" />
                    Histórico de Disponibilidade
                </h3>
                <div className="flex items-center gap-1 bg-zinc-900/50 border border-zinc-800 rounded-lg p-1">
                    {(['24h', '7d'] as RangeKey[]).map(r => (
                        <button
                            key={r}
                            onClick={() => setRange(r)}
                            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${range === r
                                ? 'bg-blue-600 text-white'
                                : 'text-zinc-400 hover:text-white'}`}
                        >
                            {r === '24h' ? 'Últimas 24h' : 'Últimos 7 dias'}
                        </button>
                    ))}
                </div>
            </div>

            {loading ? (
                <div className="h-64 flex items-center justify-center text-zinc-500">Carregando histórico…</div>
            ) : !data || data.sample_count === 0 ? (
                <div className="h-64 flex flex-col items-center justify-center text-zinc-500 gap-3 bg-zinc-800/30 rounded-xl border border-zinc-700/50">
                    <TrendingUp size={32} className="opacity-40" />
                    <p className="text-sm text-center max-w-xs">
                        Ainda não há histórico para este host. O monitoramento grava uma amostra por minuto —
                        volte em alguns minutos.
                    </p>
                </div>
            ) : (
                <>
                    {/* Uptime summary */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                            <p className="text-zinc-400 text-xs mb-1">Disponibilidade ({range === '24h' ? '24h' : '7d'})</p>
                            <p className={`text-2xl font-semibold ${uptimeColor(data.uptime_pct)}`}>
                                {data.uptime_pct !== null ? `${data.uptime_pct}%` : '—'}
                            </p>
                        </div>
                        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                            <p className="text-zinc-400 text-xs mb-1">Amostras</p>
                            <p className="text-2xl font-semibold text-white">{data.sample_count}</p>
                        </div>
                    </div>

                    {/* Latency area chart */}
                    <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                        <p className="text-zinc-300 text-sm mb-3">Latência (ms)</p>
                        <div className="h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                    <XAxis dataKey="label" tick={{ fill: '#71717a', fontSize: 11 }} minTickGap={40} />
                                    <YAxis tick={{ fill: '#71717a', fontSize: 11 }} width={40} />
                                    <Tooltip
                                        contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: 8, color: '#e4e4e7' }}
                                        labelStyle={{ color: '#a1a1aa' }}
                                        formatter={(value: any) => [value === null ? 'offline' : `${value} ms`, 'Latência']}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="latency"
                                        stroke="#3b82f6"
                                        fill="url(#latGrad)"
                                        strokeWidth={2}
                                        connectNulls={false}
                                        dot={false}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

function uptimeColor(pct: number | null): string {
    if (pct === null) return 'text-zinc-400';
    if (pct >= 99) return 'text-green-400';
    if (pct >= 90) return 'text-yellow-400';
    return 'text-red-400';
}

function formatTick(ts: number, range: RangeKey): string {
    const d = new Date(ts * 1000);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    if (range === '24h') return `${hh}:${mm}`;
    // 7d: show day/month + hour
    const dd = String(d.getDate()).padStart(2, '0');
    const mo = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}/${mo} ${hh}h`;
}
