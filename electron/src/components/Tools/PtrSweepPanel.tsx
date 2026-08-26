import { useRef, useState, useCallback } from 'react';
import { Play, Square, Globe2, Server } from 'lucide-react';
import { useStreamingTool } from './useStreamingTool';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface PtrRow { ip: string; hostname: string; }

/** Reverse-DNS sweep over a CIDR → live table of resolved names (VLAN inventory). */
export function PtrSweepPanel() {
    const { isRunning, run, stop } = useStreamingTool('/tools/ptr-sweep', 'ptr-sweep');
    const { showToast } = useToast();
    const { networks } = useNetworks();

    const [cidr, setCidr] = usePersistedState('ptr_sweep_tool_cidr', '');
    const [dnsServer, setDnsServer] = usePersistedState('ptr_sweep_tool_dns_server', '');
    const [rows, setRows, clearRows] = usePersistedState<PtrRow[]>('ptr_sweep_tool_rows', []);
    const [progress, setProgress] = useState(0);
    const [summary, setSummary] = usePersistedState<string | null>('ptr_sweep_tool_summary', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('ptr_sweep_tool_last_run', null);
    const bufferRef = useRef('');

    const dnsNetworks = networks.filter(n => n.dns_server);

    const handleChunk = useCallback((text: string) => {
        bufferRef.current += text;
        const lines = bufferRef.current.split('\n');
        bufferRef.current = lines.pop() || '';
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const d = JSON.parse(line);
                if (d.result) {
                    setRows(prev => [...prev, d.result]);
                } else if (typeof d.progress === 'number') {
                    setProgress(d.progress);
                } else if (d.done) {
                    setProgress(100);
                    setSummary(`Concluído: ${d.resolved} de ${d.total} endereços resolveram.`);
                    setLastRunAt(new Date().toISOString());
                } else if (d.cancelled) {
                    setSummary(`Cancelado: ${d.resolved} resolvidos.`);
                    setLastRunAt(new Date().toISOString());
                } else if (d.error) {
                    setSummary(`Erro: ${d.error}`);
                    setLastRunAt(new Date().toISOString());
                    showToast(d.error, 'error');
                }
            } catch { /* partial line; ignore */ }
        }
    }, [showToast, setRows, setSummary, setLastRunAt]);

    const start = () => {
        const c = cidr.trim();
        if (!c) { showToast('Informe um CIDR (ex.: 10.0.30.0/24).', 'error'); return; }
        setRows([]); setProgress(0); setSummary(null); bufferRef.current = '';
        setLastRunAt(new Date().toISOString());
        run({ cidr: c, dns_server: dnsServer || undefined }, handleChunk);
    };


    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">CIDR da rede/VLAN</label>
                    <input type="text" value={cidr} onChange={e => setCidr(e.target.value)} disabled={isRunning}
                        placeholder="10.0.30.0/24" onKeyDown={e => { if (e.key === 'Enter' && !isRunning) start(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500 disabled:opacity-60" />
                </div>
                <div className="space-y-2 w-64">
                    <label className="text-sm font-medium text-zinc-400">Servidor DNS</label>
                    <select value={dnsServer} onChange={e => setDnsServer(e.target.value)} disabled={isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-60">
                        <option value="">Resolver do sistema</option>
                        {dnsNetworks.map(n => <option key={n.id} value={n.dns_server ?? ''}>{n.name || n.cidr} — {n.dns_server}</option>)}
                    </select>
                </div>
                {!isRunning ? (
                    <button onClick={start} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-sky-400 border border-sky-900/30 hover:border-sky-500/50 transition-colors">
                        <Play size={18} /> Varrer
                    </button>
                ) : (
                    <button onClick={stop} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors">
                        <Square size={18} /> Parar
                    </button>
                )}
            </div>

            {(isRunning || progress > 0) && (
                <div className="space-y-1">
                    <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div className="h-full bg-sky-500 transition-all duration-300" style={{ width: `${progress}%` }} />
                    </div>
                    <p className="text-xs text-zinc-500">{summary ?? `${rows.length} nomes resolvidos · ${progress}%`}</p>
                </div>
            )}

            {(rows.length > 0 || summary) && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={cidr || null}
                    onClear={() => { clearRows(); setSummary(null); setLastRunAt(null); }}
                />
            )}

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col">


                {rows.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-zinc-600">
                        <Globe2 size={48} className="mb-4 opacity-20" />
                        <p>{isRunning ? 'Resolvendo nomes...' : 'Resolve o nome de todos os IPs de um CIDR (inventário da VLAN).'}</p>
                    </div>
                ) : (
                    <div className="flex-1 overflow-auto custom-scrollbar">
                        <table className="w-full text-sm font-mono">
                            <thead className="sticky top-0 bg-zinc-950 text-zinc-500 border-b border-zinc-800">
                                <tr><th className="text-left px-4 py-2 font-medium">IP</th><th className="text-left px-4 py-2 font-medium">Hostname (PTR)</th></tr>
                            </thead>
                            <tbody>
                                {rows.map((r, i) => (
                                    <tr key={i} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                                        <td className="px-4 py-1.5 text-zinc-400">{r.ip}</td>
                                        <td className="px-4 py-1.5 text-sky-400 flex items-center gap-2"><Server size={12} className="text-zinc-600" />{r.hostname}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
