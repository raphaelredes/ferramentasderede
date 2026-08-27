import { useEffect, useRef, useState, useCallback } from 'react';
import { Play, Square, ArrowDown, ArrowUp, Network as NetworkIcon } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface NicSnapshot {
    bytes_sent: number;
    bytes_recv: number;
    packets_sent: number;
    packets_recv: number;
    is_up: boolean;
    speed_mbps: number;
}
interface TrafficSnapshot {
    ts: number;
    nics: Record<string, NicSnapshot>;
}
interface NicRate {
    name: string;
    upBps: number;
    downBps: number;
    isUp: boolean;
    speedMbps: number;
}

/** Format bytes/sec into a human rate (bits or bytes). We show bits/s — the
 *  unit network engineers expect for link throughput. */
function fmtRate(bytesPerSec: number): string {
    const bits = bytesPerSec * 8;
    if (bits >= 1e9) return `${(bits / 1e9).toFixed(2)} Gbps`;
    if (bits >= 1e6) return `${(bits / 1e6).toFixed(2)} Mbps`;
    if (bits >= 1e3) return `${(bits / 1e3).toFixed(1)} Kbps`;
    return `${bits.toFixed(0)} bps`;
}

/**
 * Per-NIC throughput monitor via psutil. Polls /network/traffic on a recursive
 * setTimeout (per project rule: never setInterval for a fallible API call) and
 * computes rates from the delta between successive cumulative-counter samples.
 */
export function TrafficPanel() {
    const [running, setRunning] = useState(false);
    const [rates, setRates, clearRates] = usePersistedState<NicRate[]>('traffic_tool_rates', []);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('traffic_tool_last_run', null);
    const [error, setError] = useState<string | null>(null);

    const prevRef = useRef<TrafficSnapshot | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const runningRef = useRef(false);


    const poll = useCallback(async () => {
        if (!runningRef.current) return;
        try {
            const res = await fetch(`${API_BASE}/network/traffic`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const snap: TrafficSnapshot = await res.json();
            setError(null);

            const prev = prevRef.current;
            if (prev) {
                const dt = snap.ts - prev.ts;
                if (dt > 0) {
                    const next: NicRate[] = [];
                    for (const [name, cur] of Object.entries(snap.nics)) {
                        const old = prev.nics[name];
                        if (!old) continue;
                        next.push({
                            name,
                            upBps: Math.max(0, (cur.bytes_sent - old.bytes_sent) / dt),
                            downBps: Math.max(0, (cur.bytes_recv - old.bytes_recv) / dt),
                            isUp: cur.is_up,
                            speedMbps: cur.speed_mbps,
                        });
                    }
                    // Busiest first, then by name.
                    next.sort((a, b) => (b.upBps + b.downBps) - (a.upBps + a.downBps) || a.name.localeCompare(b.name));
                    setRates(next);
                    setLastRunAt(new Date().toISOString());
                }
            }
            prevRef.current = snap;
        } catch (e: any) {
            setError(e.message);
        } finally {
            // Recursive setTimeout with a steady 1s cadence; only re-arms while running.
            if (runningRef.current) {
                timerRef.current = setTimeout(poll, 1000);
            }
        }
    }, [setRates, setLastRunAt]);

    const start = () => {
        prevRef.current = null;
        setError(null);
        runningRef.current = true;
        setRunning(true);
        poll();
    };

    const stop = useCallback(() => {
        runningRef.current = false;
        setRunning(false);
        if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    }, []);

    // Stop polling on unmount.
    useEffect(() => () => stop(), [stop]);

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex items-center gap-4 bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1">
                    <p className="text-sm text-zinc-300 font-medium">Tráfego por interface</p>
                    <p className="text-xs text-zinc-600">Taxa de transferência em tempo real por NIC (amostra a cada 1s).</p>
                </div>
                {!running ? (
                    <button
                        onClick={start}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-indigo-400 border border-indigo-900/30 hover:border-indigo-500/50 transition-colors"
                    >
                        <Play size={18} />
                        Iniciar
                    </button>
                ) : (
                    <button
                        onClick={stop}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                    >
                        <Square size={18} />
                        Parar
                    </button>
                )}
            </div>

            {rates.length > 0 && lastRunAt && !running && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={`${rates.length} interfaces ativas`}
                    onClear={() => { clearRates(); setLastRunAt(null); }}
                />
            )}

            {error && (
                <div className="px-4 py-2 bg-red-500/10 border border-red-900/40 rounded-lg text-red-400 text-sm">
                    Erro ao coletar tráfego: {error}
                </div>
            )}


            <div className="flex-1 overflow-auto custom-scrollbar">
                {rates.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <NetworkIcon size={48} className="mb-4 opacity-20" />
                        <p>{running ? 'Calculando taxas...' : 'Inicie para ver o tráfego por interface.'}</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {rates.map((nic) => (
                            <div key={nic.name} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                                <div className="flex items-center justify-between mb-3">
                                    <span className="font-medium text-zinc-200 truncate" title={nic.name}>{nic.name}</span>
                                    {nic.speedMbps > 0 && (
                                        <span className="text-xs text-zinc-600 shrink-0">{nic.speedMbps} Mbps link</span>
                                    )}
                                </div>
                                <div className="flex gap-6">
                                    <div className="flex items-center gap-2">
                                        <ArrowDown size={18} className="text-green-400" />
                                        <div>
                                            <div className="text-xs text-zinc-500">Download</div>
                                            <div className="font-mono text-green-400 font-medium">{fmtRate(nic.downBps)}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <ArrowUp size={18} className="text-blue-400" />
                                        <div>
                                            <div className="text-xs text-zinc-500">Upload</div>
                                            <div className="font-mono text-blue-400 font-medium">{fmtRate(nic.upBps)}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
