import { useRef, useEffect } from 'react';
import { Play, Square, Eraser, Zap } from 'lucide-react';
import { useStreamingTool } from './useStreamingTool';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

/**
 * TCP ping: liveness + latency via TCP handshake, for hosts that block ICMP
 * (the AD-domain default). Streaming text output.
 */
export function TcpPingPanel() {
    const { output, isRunning, run, stop, clear, lastRunAt } = useStreamingTool('/tools/tcp-ping', 'tcp-ping');
    const { showToast } = useToast();
    const { networks } = useNetworks();

    const [target, setTarget] = usePersistedState('tcp_ping_tool_target', '');
    const [port, setPort] = usePersistedState('tcp_ping_tool_port', '3389');
    const [count, setCount] = usePersistedState('tcp_ping_tool_count', '4');
    const [sourceIp, setSourceIp] = usePersistedState('tcp_ping_tool_source_ip', '');
    const endRef = useRef<HTMLDivElement>(null);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [output]);

    const start = () => {
        const t = target.trim();
        if (!t) { showToast('Informe o host alvo.', 'error'); return; }
        const p = parseInt(port, 10);
        if (!p || p < 1 || p > 65535) { showToast('Porta inválida (1–65535).', 'error'); return; }
        let n = parseInt(count, 10); if (!n || n < 1) n = 4; if (n > 100) n = 100;
        run({ target: t, port: p, count: n, source_ip: sourceIp || undefined });
    };


    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800 flex-wrap">
                <div className="flex-1 min-w-48 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Host alvo</label>
                    <input type="text" value={target} onChange={e => setTarget(e.target.value)} disabled={isRunning}
                        placeholder="192.168.1.10" onKeyDown={e => { if (e.key === 'Enter' && !isRunning) start(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500 disabled:opacity-60" />
                </div>
                <div className="space-y-2 w-24">
                    <label className="text-sm font-medium text-zinc-400">Porta</label>
                    <input type="text" value={port} onChange={e => setPort(e.target.value)} disabled={isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 font-mono disabled:opacity-60" />
                </div>
                <div className="space-y-2 w-20">
                    <label className="text-sm font-medium text-zinc-400">Nº</label>
                    <input type="text" value={count} onChange={e => setCount(e.target.value)} disabled={isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 font-mono disabled:opacity-60" />
                </div>
                <div className="space-y-2 w-52">
                    <label className="text-sm font-medium text-zinc-400">Sair pela rede</label>
                    <select value={sourceIp} onChange={e => setSourceIp(e.target.value)} disabled={isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-60">
                        <option value="">Automático</option>
                        {networks.map(n => <option key={n.id} value={n.source_ip ?? ''} disabled={!n.source_ip}>{n.name || n.cidr}{n.source_ip ? ` — ${n.source_ip}` : ' (sem IP)'}</option>)}
                    </select>
                </div>
                {!isRunning ? (
                    <button onClick={start} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-cyan-400 border border-cyan-900/30 hover:border-cyan-500/50 transition-colors">
                        <Play size={18} /> Testar
                    </button>
                ) : (
                    <button onClick={stop} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors">
                        <Square size={18} /> Parar
                    </button>
                )}
            </div>

            {output.length > 0 && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={target ? `${target}:${port}` : null}
                    onClear={clear}
                />
            )}

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm">

                <button onClick={clear} disabled={isRunning} title="Limpar" className="absolute top-2 right-2 z-10 p-2 text-zinc-500 hover:text-white rounded-lg hover:bg-zinc-800 disabled:opacity-30">
                    <Eraser size={16} />
                </button>
                <div className="flex-1 overflow-auto custom-scrollbar">
                    {output.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <Zap size={48} className="mb-4 opacity-20" />
                            <p>TCP ping — funciona mesmo quando o host bloqueia ICMP.</p>
                        </div>
                    ) : output.map((l, i) => <div key={i} className="whitespace-pre-wrap break-all text-zinc-300 leading-tight">{l}</div>)}
                    <div ref={endRef} />
                </div>
            </div>
        </div>
    );
}
