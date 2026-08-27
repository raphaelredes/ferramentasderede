import { Play, Square, Activity, GitBranch } from 'lucide-react';
import { clsx } from 'clsx';
import { useTools } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

/**
 * MTR-style path monitor. Streams a per-hop table (latency / jitter / loss)
 * that refreshes every cycle — the best view for "where on the route to VLAN X
 * is the latency/loss coming from". Pure Python backend via icmplib.
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

    // Color the loss cell: green at 0, amber under 20%, red above.
    const lossClass = (loss: number) =>
        loss <= 0 ? 'text-green-400' : loss < 20 ? 'text-amber-400' : 'text-red-400';

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Alvo (IP ou Hostname)</label>
                    <input
                        type="text"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        onFocus={() => { if (target === '8.8.8.8') setTarget(''); }}
                        disabled={mtrState.isRunning}
                        placeholder="8.8.8.8"
                        className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500 disabled:opacity-60 ${target === '8.8.8.8' ? 'text-zinc-500' : 'text-white'}`}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !mtrState.isRunning) start(); }}
                    />
                </div>
                <div className="space-y-2 w-64">
                    <label className="text-sm font-medium text-zinc-400">Sair pela rede</label>
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
                            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-rose-400 border border-rose-900/30 hover:border-rose-500/50 transition-colors"
                        >
                            <Play size={18} />
                            Iniciar MTR
                        </button>
                    ) : (
                        <button
                            onClick={() => stopTool('mtr')}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                        >
                            <Square size={18} />
                            Parar
                        </button>
                    )}
                </div>
            </div>

            {mtrState.hops.length > 0 && mtrState.lastRunAt && (
                <LastExecutionBadge
                    timestamp={mtrState.lastRunAt}
                    target={target}
                    onClear={() => clearToolOutput('mtr')}
                />
            )}

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col">

                {mtrState.error && (
                    <div className="px-4 py-2 bg-red-500/10 border-b border-red-900/40 text-red-400 text-sm">
                        {mtrState.error}
                    </div>
                )}
                {mtrState.hops.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-zinc-600">
                        <GitBranch size={48} className="mb-4 opacity-20" />
                        <p>{mtrState.isRunning ? 'Traçando rota...' : 'Inicie o MTR para monitorar a rota salto a salto.'}</p>
                    </div>
                ) : (
                    <div className="flex-1 overflow-auto custom-scrollbar">
                        <table className="w-full text-sm font-mono">
                            <thead className="sticky top-0 bg-zinc-950 text-zinc-500 border-b border-zinc-800">
                                <tr>
                                    <th className="text-left px-3 py-2 font-medium">#</th>
                                    <th className="text-left px-3 py-2 font-medium">Host</th>
                                    <th className="text-right px-3 py-2 font-medium">Perda%</th>
                                    <th className="text-right px-3 py-2 font-medium">Env</th>
                                    <th className="text-right px-3 py-2 font-medium">Último</th>
                                    <th className="text-right px-3 py-2 font-medium">Média</th>
                                    <th className="text-right px-3 py-2 font-medium">Melhor</th>
                                    <th className="text-right px-3 py-2 font-medium">Pior</th>
                                    <th className="text-right px-3 py-2 font-medium">Jitter</th>
                                </tr>
                            </thead>
                            <tbody>
                                {mtrState.hops.map((h) => (
                                    <tr key={h.hop} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                                        <td className="px-3 py-1.5 text-zinc-500">{h.hop}</td>
                                        <td className="px-3 py-1.5 text-zinc-300">{h.address}</td>
                                        <td className={clsx('px-3 py-1.5 text-right font-medium', lossClass(h.loss_pct))}>{h.loss_pct.toFixed(1)}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-500">{h.sent}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-300">{h.last ?? '—'}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-300">{h.avg ?? '—'}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-400">{h.best ?? '—'}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-400">{h.worst ?? '—'}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-400">{h.jitter ?? '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                <div className="px-4 py-1.5 border-t border-zinc-800 text-xs text-zinc-600 flex items-center gap-2">
                    {mtrState.isRunning && <Activity size={12} className="animate-spin text-rose-400" />}
                    Tempos em ms. Saltos com <code className="text-zinc-500">*</code> não responderam ao ICMP (comum em firewalls — não significa falha na rota).
                </div>
            </div>
        </div>
    );
}
