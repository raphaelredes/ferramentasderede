import { useMemo } from 'react';
import { Play, Square, Activity, GitBranch, Zap, AlertTriangle, ShieldCheck } from 'lucide-react';
import { clsx } from 'clsx';
import { useTools } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';
import { Sparkline } from './Sparkline';

/**
 * MTR-style path monitor com BGP ASN, Sparklines ao vivo e Jitter RFC 1889.
 * Streams a per-hop table (latency / jitter / loss / ASN / trend) that refreshes every cycle.
 */
export function MtrPanel() {
    const { mtrState, runMtr, stopTool, clearToolOutput } = useTools();
    const { showToast } = useToast();
    const { networks } = useNetworks();

    const [target, setTarget] = usePersistedState('mtr_tool_target', '8.8.8.8');
    const [sourceIp, setSourceIp] = usePersistedState('mtr_tool_source_ip', '');

    const start = () => {
        const t = target.trim();
        if (!t) { showToast('Informe um alvo.', 'error'); return; }
        runMtr(t, sourceIp || undefined);
    };

    // Cor da célula de perda
    const lossClass = (loss: number) =>
        loss <= 0 ? 'text-emerald-400' : loss < 20 ? 'text-amber-400' : 'text-rose-400 font-bold';

    // Métricas analíticas do MTR em tempo real
    const summary = useMemo(() => {
        if (!mtrState.hops || mtrState.hops.length === 0) return null;
        const validHops = mtrState.hops.filter(h => h.address && h.address !== '*');
        
        let worstLossHop = mtrState.hops[0];
        let slowestHop = validHops[0] || mtrState.hops[0];

        mtrState.hops.forEach(h => {
            if (h.loss_pct > (worstLossHop?.loss_pct ?? -1)) worstLossHop = h;
        });

        validHops.forEach(h => {
            if ((h.avg ?? 0) > (slowestHop?.avg ?? 0)) slowestHop = h;
        });

        // Contagem de ASNs únicos
        const asns = new Set(mtrState.hops.map(h => h.asn).filter(a => a && a !== '—' && a !== 'RFC1918'));

        return {
            totalHops: mtrState.hops.length,
            uniqueAsns: asns.size,
            slowest: slowestHop,
            worstLoss: worstLossHop,
        };
    }, [mtrState.hops]);

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Controles de Entrada */}
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800 shrink-0">
                <div className="flex-1 space-y-2">
                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Alvo (IP ou Hostname)
                    </label>
                    <input
                        type="text"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        onFocus={() => { if (target === '8.8.8.8') setTarget(''); }}
                        disabled={mtrState.isRunning}
                        placeholder="8.8.8.8 ou google.com"
                        className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500 text-sm ${target === '8.8.8.8' ? 'text-zinc-500' : 'text-white'}`}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !mtrState.isRunning) start(); }}
                    />
                </div>
                <div className="space-y-2 w-64">
                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Sair pela rede (Multi-VLAN)
                    </label>
                    <select
                        value={sourceIp}
                        onChange={(e) => setSourceIp(e.target.value)}
                        disabled={mtrState.isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-60"
                    >
                        <option value="">Automático (rota padrão)</option>
                        {networks.map(net => (
                            <option key={net.id} value={net.source_ip ?? ''} disabled={!net.source_ip}>
                                {net.name || net.cidr}{net.source_ip ? ` — ${net.source_ip}` : ' (sem source IP)'}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="flex gap-2">
                    {!mtrState.isRunning ? (
                        <button
                            onClick={start}
                            className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-600/20 transition-all text-sm"
                        >
                            <Play size={16} />
                            Iniciar MTR
                        </button>
                    ) : (
                        <button
                            onClick={() => stopTool('mtr')}
                            className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/40 hover:border-red-500/50 transition-all text-sm"
                        >
                            <Square size={16} />
                            Parar
                        </button>
                    )}
                </div>
            </div>

            {/* Cards de Resumo Analítico (quando há dados) */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 shrink-0">
                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Saltos Descobertos</span>
                            <span className="text-base font-bold font-mono text-zinc-100">{summary.totalHops} saltos</span>
                        </div>
                        <GitBranch size={18} className="text-blue-400 opacity-60" />
                    </div>

                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Redes BGP / Trânsito</span>
                            <span className="text-base font-bold font-mono text-indigo-300">{summary.uniqueAsns} ASNs</span>
                        </div>
                        <ShieldCheck size={18} className="text-indigo-400 opacity-60" />
                    </div>

                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Maior Latência Média</span>
                            <span className="text-base font-bold font-mono text-amber-400">
                                {summary.slowest?.avg !== null ? `${summary.slowest.avg} ms` : '—'}
                            </span>
                            <span className="text-[10px] text-zinc-500 font-mono block">Salto #{summary.slowest?.hop} ({summary.slowest?.address})</span>
                        </div>
                        <Zap size={18} className="text-amber-400 opacity-60" />
                    </div>

                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Maior Perda de Pacotes</span>
                            <span className={clsx('text-base font-bold font-mono', (summary.worstLoss?.loss_pct ?? 0) > 0 ? 'text-rose-400' : 'text-emerald-400')}>
                                {summary.worstLoss?.loss_pct ?? 0}%
                            </span>
                            <span className="text-[10px] text-zinc-500 font-mono block">Salto #{summary.worstLoss?.hop} ({summary.worstLoss?.address})</span>
                        </div>
                        <AlertTriangle size={18} className={(summary.worstLoss?.loss_pct ?? 0) > 0 ? 'text-rose-400 opacity-80' : 'text-emerald-400 opacity-60'} />
                    </div>
                </div>
            )}

            {mtrState.hops.length > 0 && mtrState.lastRunAt && (
                <LastExecutionBadge
                    timestamp={mtrState.lastRunAt}
                    target={target}
                    onClear={() => clearToolOutput('mtr')}
                />
            )}

            {/* Tabela do MTR */}
            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col min-h-0">
                {mtrState.error && (
                    <div className="px-4 py-2 bg-rose-500/10 border-b border-rose-900/40 text-rose-400 text-xs flex items-center gap-2">
                        <AlertTriangle size={14} />
                        {mtrState.error}
                    </div>
                )}

                {mtrState.hops.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-zinc-600">
                        <GitBranch size={48} className="mb-3 opacity-20" />
                        <p className="text-sm font-medium text-zinc-400">
                            {mtrState.isRunning ? 'Traçando rota inicial e resolvendo ASNs...' : 'Inicie o MTR para monitorar a rota salto a salto.'}
                        </p>
                        <p className="text-xs text-zinc-600 mt-1">
                            Calcula Jitter RFC 1889, perdas e exibe operadoras BGP em tempo real.
                        </p>
                    </div>
                ) : (
                    <div className="flex-1 overflow-auto custom-scrollbar">
                        <table className="w-full text-xs font-mono">
                            <thead className="sticky top-0 bg-zinc-950 text-zinc-400 border-b border-zinc-800 z-10">
                                <tr>
                                    <th className="text-left px-3 py-2 font-semibold">#</th>
                                    <th className="text-left px-3 py-2 font-semibold">Host / IP</th>
                                    <th className="text-left px-3 py-2 font-semibold">Operadora & BGP ASN</th>
                                    <th className="text-right px-3 py-2 font-semibold">Perda%</th>
                                    <th className="text-right px-3 py-2 font-semibold">Env</th>
                                    <th className="text-right px-3 py-2 font-semibold">Último</th>
                                    <th className="text-right px-3 py-2 font-semibold">Média</th>
                                    <th className="text-right px-3 py-2 font-semibold">Melhor</th>
                                    <th className="text-right px-3 py-2 font-semibold">Pior</th>
                                    <th className="text-right px-3 py-2 font-semibold" title="Jitter RFC 1889 (variação estatística pacote a pacote)">Jitter</th>
                                    <th className="text-center px-3 py-2 font-semibold">Tendência (RTT)</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-900">
                                {mtrState.hops.map((h) => (
                                    <tr key={h.hop} className="hover:bg-zinc-900/50 transition-colors">
                                        <td className="px-3 py-2 text-zinc-500 font-bold">{h.hop}</td>
                                        <td className="px-3 py-2 text-zinc-200 font-medium">
                                            {h.address}
                                        </td>
                                        <td className="px-3 py-2 max-w-64 truncate">
                                            {h.asn && h.asn !== '—' ? (
                                                <div className="flex items-center gap-1.5 truncate">
                                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 shrink-0">
                                                        {h.asn}
                                                    </span>
                                                    <span className="text-zinc-400 truncate text-[11px]" title={h.as_name}>
                                                        {h.as_name}
                                                    </span>
                                                </div>
                                            ) : (
                                                <span className="text-zinc-600">—</span>
                                            )}
                                        </td>
                                        <td className={clsx('px-3 py-2 text-right font-bold', lossClass(h.loss_pct))}>
                                            {h.loss_pct.toFixed(1)}%
                                        </td>
                                        <td className="px-3 py-2 text-right text-zinc-500">{h.sent}</td>
                                        <td className="px-3 py-2 text-right text-zinc-300 font-semibold">{h.last !== null ? `${h.last}ms` : '—'}</td>
                                        <td className="px-3 py-2 text-right text-zinc-300 font-semibold">{h.avg !== null ? `${h.avg}ms` : '—'}</td>
                                        <td className="px-3 py-2 text-right text-emerald-400/80">{h.best !== null ? `${h.best}ms` : '—'}</td>
                                        <td className="px-3 py-2 text-right text-rose-400/80">{h.worst !== null ? `${h.worst}ms` : '—'}</td>
                                        <td className="px-3 py-2 text-right text-amber-300 font-medium">{h.jitter !== null ? `${h.jitter}ms` : '—'}</td>
                                        <td className="px-3 py-2 text-center">
                                            <Sparkline history={h.history || []} width={100} height={18} />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                <div className="px-4 py-2 border-t border-zinc-800 text-xs text-zinc-500 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                        {mtrState.isRunning && <Activity size={13} className="animate-spin text-rose-400" />}
                        <span>Tempos em ms. Jitter calculado segundo RFC 1889. Mapeamento ASN via Team Cymru.</span>
                    </div>
                    <span className="text-zinc-600 text-[11px]">Saltos com * indicam firewall descartando ICMP direto</span>
                </div>
            </div>
        </div>
    );
}
