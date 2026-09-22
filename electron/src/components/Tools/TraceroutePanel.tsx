import { useState, useMemo, useRef, useEffect } from 'react';
import {
    Play,
    Square,
    GitBranch,
    Activity,
    Terminal,
    LayoutList,
    ShieldCheck,
    Zap,
    AlertTriangle,
    CheckCircle2,
    Copy,
    Check,
    ArrowRight
} from 'lucide-react';
import { clsx } from 'clsx';
import { useTools, TracerouteHop } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface TraceroutePanelProps {
    target?: string;
    setTarget?: (t: string) => void;
    sourceIp?: string;
    setSourceIp?: (ip: string) => void;
}

export function TraceroutePanel(props?: TraceroutePanelProps) {
    const { traceState, runTraceroute, stopTool, clearToolOutput } = useTools();
    const { showToast } = useToast();
    const { networks } = useNetworks();

    // Persisted state fallback se não fornecido via props
    const [persistedTarget, setPersistedTarget] = usePersistedState('tools_local_trace_target', '8.8.8.8');
    const [persistedSourceIp, setPersistedSourceIp] = usePersistedState('tools_trace_source_ip', '');
    const [viewMode, setViewMode] = usePersistedState<'visual' | 'raw'>('traceroute_view_mode', 'visual');

    const target = props?.target ?? persistedTarget;
    const setTarget = props?.setTarget ?? setPersistedTarget;
    const sourceIp = props?.sourceIp ?? persistedSourceIp;
    const setSourceIp = props?.setSourceIp ?? setPersistedSourceIp;

    const [copied, setCopied] = useState(false);
    const terminalEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll do terminal quando em modo bruto
    useEffect(() => {
        if (viewMode === 'raw' && traceState.isRunning) {
            terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [traceState.output, viewMode, traceState.isRunning]);

    const handleStart = () => {
        const t = target.trim();
        if (!t) {
            showToast('Informe um alvo para rastreamento.', 'error');
            return;
        }
        runTraceroute(t, sourceIp || undefined);
    };

    const copyTerminalOutput = () => {
        if (!traceState.output || traceState.output.length === 0) return;
        navigator.clipboard.writeText(traceState.output.join(''));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        showToast('Saída copiada para a área de transferência!', 'success');
    };

    // Métricas analíticas dos saltos
    const summary = useMemo(() => {
        const hops = traceState.hops;
        if (!hops || hops.length === 0) return null;

        const respondingHops = hops.filter(h => !h.loss && h.avg_ms !== null);
        let slowestHop: TracerouteHop | null = null;
        let maxAvg = -1;

        respondingHops.forEach(h => {
            if ((h.avg_ms ?? 0) > maxAvg) {
                maxAvg = h.avg_ms ?? 0;
                slowestHop = h;
            }
        });

        // ASNs únicos transitados (ignorando não identificados e RFC1918)
        const uniqueAsnsList: { asn: string; name: string }[] = [];
        const seenAsns = new Set<string>();

        hops.forEach(h => {
            if (h.asn && h.asn !== '—' && h.asn !== 'RFC1918' && !seenAsns.has(h.asn)) {
                seenAsns.add(h.asn);
                uniqueAsnsList.push({ asn: h.asn, name: h.as_name });
            }
        });

        const lastHop = hops[hops.length - 1];
        const isCompleted = !traceState.isRunning && hops.length > 0;
        const reachedTarget = isCompleted && lastHop && !lastHop.loss;

        return {
            totalHops: hops.length,
            uniqueAsnsCount: seenAsns.size,
            uniqueAsnsList,
            slowest: slowestHop as TracerouteHop | null,
            reachedTarget,
            isCompleted,
            hasTimeouts: hops.some(h => h.loss || (h.rtts && h.rtts.some(r => r === null))),
        };
    }, [traceState.hops, traceState.isRunning]);

    // Formatação de RTT com badge de cor
    const renderRttBadge = (rtt: number | null) => {
        if (rtt === null) {
            return <span className="text-rose-400/90 font-mono font-bold">*</span>;
        }
        let color = 'text-emerald-400';
        if (rtt >= 100) color = 'text-rose-400 font-bold';
        else if (rtt >= 40) color = 'text-amber-400 font-medium';

        return <span className={clsx('font-mono', color)}>{rtt}ms</span>;
    };

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Barra de Controles */}
            <div className="flex flex-wrap gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800 shrink-0">
                <div className="flex-1 min-w-[240px] space-y-2">
                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Alvo (IP ou Hostname)
                    </label>
                    <input
                        type="text"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        onFocus={() => { if (target === '8.8.8.8') setTarget(''); }}
                        onBlur={() => {
                            if (target) {
                                let clean = target.trim().replace(/^['"]|['"]$/g, '');
                                clean = clean.replace(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, '').split('/')[0].split('?')[0].split('#')[0];
                                if (clean.includes(':') && !clean.startsWith('[')) clean = clean.split(':')[0];
                                clean = clean.replace(/\.+$/, '').trim();
                                if (clean && clean !== target) setTarget(clean);
                            }
                        }}
                        disabled={traceState.isRunning}
                        placeholder="8.8.8.8 ou google.com"
                        className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500 transition-colors font-mono placeholder:text-zinc-500 text-sm ${target === '8.8.8.8' ? 'text-zinc-500' : 'text-white'}`}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !traceState.isRunning) handleStart();
                        }}
                    />
                </div>

                <div className="space-y-2 w-64">
                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Sair pela rede (Multi-VLAN)
                    </label>
                    <select
                        value={sourceIp}
                        onChange={(e) => setSourceIp(e.target.value)}
                        disabled={traceState.isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors disabled:opacity-60"
                    >
                        <option value="">Automático (rota padrão)</option>
                        {networks.map(net => (
                            <option key={net.id} value={net.source_ip ?? ''} disabled={!net.source_ip}>
                                {net.name || net.cidr}{net.source_ip ? ` — ${net.source_ip}` : ' (sem source IP)'}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Botões de Ação e Alternância de Visualização */}
                <div className="flex items-center gap-2">
                    {!traceState.isRunning ? (
                        <button
                            onClick={handleStart}
                            className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-md shadow-purple-600/20 transition-all text-sm"
                        >
                            <Play size={16} />
                            Iniciar Traceroute
                        </button>
                    ) : (
                        <button
                            onClick={() => stopTool('traceroute')}
                            className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/40 hover:border-red-500/50 transition-all text-sm"
                        >
                            <Square size={16} />
                            Parar
                        </button>
                    )}

                    {/* Toggle Visual / Terminal */}
                    <div className="flex bg-zinc-950 p-1 rounded-lg border border-zinc-800 ml-2">
                        <button
                            type="button"
                            onClick={() => setViewMode('visual')}
                            className={clsx(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                                viewMode === 'visual'
                                    ? "bg-purple-600/20 text-purple-300 border border-purple-500/40"
                                    : "text-zinc-400 hover:text-zinc-200"
                            )}
                            title="Tabela de Rota com ASNs e Operadoras BGP"
                        >
                            <LayoutList size={14} />
                            <span>Visual BGP</span>
                        </button>
                        <button
                            type="button"
                            onClick={() => setViewMode('raw')}
                            className={clsx(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                                viewMode === 'raw'
                                    ? "bg-purple-600/20 text-purple-300 border border-purple-500/40"
                                    : "text-zinc-400 hover:text-zinc-200"
                            )}
                            title="Terminal de Saída Bruta (Console)"
                        >
                            <Terminal size={14} />
                            <span>Terminal</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Cards Analíticos de Resumo */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 shrink-0">
                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Saltos na Rota</span>
                            <span className="text-base font-bold font-mono text-zinc-100">{summary.totalHops} saltos</span>
                            <span className="text-[10px] text-zinc-400 block truncate">
                                {traceState.isRunning ? 'Rastreando caminho...' : summary.reachedTarget ? 'Destino alcançado' : 'Rastreamento finalizado'}
                            </span>
                        </div>
                        <GitBranch size={18} className="text-purple-400 opacity-60" />
                    </div>

                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Redes / Trânsito BGP</span>
                            <span className="text-base font-bold font-mono text-indigo-300">{summary.uniqueAsnsCount} ASNs</span>
                            <span className="text-[10px] text-zinc-400 block truncate" title={summary.uniqueAsnsList.map(a => `${a.asn} (${a.name})`).join(', ')}>
                                {summary.uniqueAsnsList.length > 0 ? summary.uniqueAsnsList.map(a => a.asn).join(', ') : 'Rede Local'}
                            </span>
                        </div>
                        <ShieldCheck size={18} className="text-indigo-400 opacity-60" />
                    </div>

                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Maior Latência (Salto Crítico)</span>
                            <span className="text-base font-bold font-mono text-amber-400">
                                {summary.slowest?.avg_ms !== null && summary.slowest?.avg_ms !== undefined ? `${summary.slowest.avg_ms} ms` : '—'}
                            </span>
                            <span className="text-[10px] text-zinc-400 font-mono block truncate">
                                {summary.slowest ? `Salto #${summary.slowest.hop} (${summary.slowest.asn !== '—' ? summary.slowest.asn : summary.slowest.ip})` : '—'}
                            </span>
                        </div>
                        <Zap size={18} className="text-amber-400 opacity-60" />
                    </div>

                    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg px-3 py-2 flex items-center justify-between">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Qualidade do Caminho</span>
                            <span className={clsx('text-base font-bold font-mono', summary.hasTimeouts ? 'text-amber-400' : 'text-emerald-400')}>
                                {summary.hasTimeouts ? 'Com Descartes (*)' : '100% Responsivo'}
                            </span>
                            <span className="text-[10px] text-zinc-400 block truncate">
                                {summary.hasTimeouts ? 'Firewall/rate-limit intermediário' : 'Sem perda de pacotes'}
                            </span>
                        </div>
                        {summary.hasTimeouts ? (
                            <AlertTriangle size={18} className="text-amber-400 opacity-70" />
                        ) : (
                            <CheckCircle2 size={18} className="text-emerald-400 opacity-70" />
                        )}
                    </div>
                </div>
            )}

            {/* Badge de Última Execução */}
            {traceState.lastRunAt && (
                <LastExecutionBadge
                    timestamp={traceState.lastRunAt}
                    target={target}
                    onClear={() => clearToolOutput('traceroute')}
                />
            )}

            {/* Visualização de Nós / Fluxo de Topologia (Breadcrumb Flow) */}
            {viewMode === 'visual' && traceState.hops.length > 0 && (
                <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl px-4 py-3 overflow-x-auto custom-scrollbar shrink-0">
                    <div className="flex items-center gap-2 min-w-max">
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 text-zinc-300 text-xs font-mono">
                            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                            <span>Origem (Você)</span>
                        </div>

                        {traceState.hops.map((hop) => (
                            <div key={hop.hop} className="flex items-center gap-2">
                                <ArrowRight size={13} className="text-zinc-600 shrink-0" />
                                <div
                                    className={clsx(
                                        "flex flex-col px-2.5 py-1 rounded-lg border text-xs font-mono transition-all",
                                        hop.loss
                                            ? "bg-zinc-900/60 border-zinc-800 text-zinc-500"
                                            : "bg-zinc-900 border-zinc-700/80 text-zinc-200 shadow-sm"
                                    )}
                                    title={`Salto #${hop.hop}\nIP: ${hop.ip}\nHost: ${hop.hostname || '—'}\nASN: ${hop.asn} (${hop.as_name})\nRTT Médio: ${hop.avg_ms ?? '*'} ms`}
                                >
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[10px] font-bold text-zinc-500">#{hop.hop}</span>
                                        <span className="font-semibold text-zinc-300 truncate max-w-[120px]">
                                            {hop.hostname ? hop.hostname.split('.')[0] : hop.ip}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 mt-0.5 text-[10px]">
                                        {hop.asn && hop.asn !== '—' ? (
                                            <span className="text-purple-400 font-bold">{hop.asn}</span>
                                        ) : (
                                            <span className="text-zinc-600">LAN</span>
                                        )}
                                        <span className={clsx(
                                            (hop.avg_ms ?? 0) >= 100 ? 'text-rose-400' : (hop.avg_ms ?? 0) >= 40 ? 'text-amber-400' : 'text-emerald-400'
                                        )}>
                                            {hop.avg_ms !== null ? `${hop.avg_ms}ms` : '*'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))}

                        {traceState.isRunning && (
                            <div className="flex items-center gap-2">
                                <ArrowRight size={13} className="text-zinc-600 shrink-0" />
                                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-purple-950/40 border border-purple-800/40 text-purple-300 text-xs font-mono animate-pulse">
                                    <Activity size={12} className="animate-spin" />
                                    <span>Próximo salto...</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Conteúdo Principal (Tabela Visual BGP ou Terminal Bruto) */}
            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col min-h-0">
                {viewMode === 'visual' ? (
                    traceState.hops.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-zinc-600 p-6">
                            <GitBranch size={48} className="mb-3 opacity-20 text-purple-400" />
                            <p className="text-sm font-medium text-zinc-400">
                                {traceState.isRunning ? 'Traçando rota e descobrindo ASNs das operadoras...' : 'Inicie o Traceroute para mapear o caminho completo até o destino.'}
                            </p>
                            <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                Exibe o IP, tempo de cada sonda, latência média e identifica o BGP ASN e nome do provedor para cada roteador via Team Cymru.
                            </p>
                        </div>
                    ) : (
                        <div className="flex-1 overflow-auto custom-scrollbar">
                            <table className="w-full text-xs font-mono">
                                <thead className="sticky top-0 bg-zinc-950 text-zinc-400 border-b border-zinc-800 z-10">
                                    <tr>
                                        <th className="text-left px-3 py-2 font-semibold w-12">#</th>
                                        <th className="text-left px-3 py-2 font-semibold min-w-[200px]">Host / IP</th>
                                        <th className="text-left px-3 py-2 font-semibold min-w-[220px]">Operadora & BGP ASN</th>
                                        <th className="text-right px-3 py-2 font-semibold w-20">Sonda 1</th>
                                        <th className="text-right px-3 py-2 font-semibold w-20">Sonda 2</th>
                                        <th className="text-right px-3 py-2 font-semibold w-20">Sonda 3</th>
                                        <th className="text-right px-3 py-2 font-semibold w-24">Latência Média</th>
                                        <th className="text-center px-3 py-2 font-semibold w-28">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-900">
                                    {traceState.hops.map((h) => {
                                        const rtt1 = h.rtts?.[0] ?? null;
                                        const rtt2 = h.rtts?.[1] ?? null;
                                        const rtt3 = h.rtts?.[2] ?? null;
                                        const isTimeoutAll = h.loss;
                                        const isPartialTimeout = !isTimeoutAll && (rtt1 === null || rtt2 === null || rtt3 === null);

                                        return (
                                            <tr key={h.hop} className="hover:bg-zinc-900/50 transition-colors">
                                                <td className="px-3 py-2 text-zinc-500 font-bold">{h.hop}</td>
                                                <td className="px-3 py-2">
                                                    <div className="flex flex-col">
                                                        <span className="text-zinc-200 font-medium">{h.ip}</span>
                                                        {h.hostname && (
                                                            <span className="text-zinc-500 text-[11px] truncate max-w-sm" title={h.hostname}>
                                                                {h.hostname}
                                                            </span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-3 py-2">
                                                    {h.asn && h.asn !== '—' ? (
                                                        <div className="flex items-center gap-1.5">
                                                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 shrink-0">
                                                                {h.asn}
                                                            </span>
                                                            <span className="text-zinc-300 truncate text-[11px]" title={h.as_name}>
                                                                {h.as_name}
                                                            </span>
                                                            {h.country && h.country !== '—' && (
                                                                <span className="text-[10px] text-zinc-500 px-1 py-0.2 bg-zinc-800 rounded font-semibold ml-auto shrink-0">
                                                                    {h.country}
                                                                </span>
                                                            )}
                                                        </div>
                                                    ) : (
                                                        <span className="text-zinc-600">—</span>
                                                    )}
                                                </td>
                                                <td className="px-3 py-2 text-right">{renderRttBadge(rtt1)}</td>
                                                <td className="px-3 py-2 text-right">{renderRttBadge(rtt2)}</td>
                                                <td className="px-3 py-2 text-right">{renderRttBadge(rtt3)}</td>
                                                <td className="px-3 py-2 text-right">
                                                    {h.avg_ms !== null ? (
                                                        <span className={clsx(
                                                            "font-bold font-mono",
                                                            h.avg_ms >= 100 ? "text-rose-400" : h.avg_ms >= 40 ? "text-amber-400" : "text-emerald-400"
                                                        )}>
                                                            {h.avg_ms} ms
                                                        </span>
                                                    ) : (
                                                        <span className="text-zinc-600 font-mono">*</span>
                                                    )}
                                                </td>
                                                <td className="px-3 py-2 text-center">
                                                    {isTimeoutAll ? (
                                                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">
                                                            Esgotado
                                                        </span>
                                                    ) : isPartialTimeout ? (
                                                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                                            Parcial
                                                        </span>
                                                    ) : (
                                                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                                            OK
                                                        </span>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )
                ) : (
                    /* Terminal Bruto */
                    <div className="flex-1 flex flex-col min-h-0 bg-black p-4 font-mono text-xs">
                        <div className="flex justify-between items-center pb-2 mb-2 border-b border-zinc-800 text-zinc-500 text-xs">
                            <span className="flex items-center gap-1.5">
                                <Terminal size={14} className="text-purple-400" />
                                Console Bruto do Traceroute
                            </span>
                            <button
                                onClick={copyTerminalOutput}
                                className="flex items-center gap-1 text-xs px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
                            >
                                {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                <span>{copied ? 'Copiado!' : 'Copiar'}</span>
                            </button>
                        </div>
                        <div className="flex-1 overflow-auto custom-scrollbar whitespace-pre-wrap text-zinc-300 select-text">
                            {traceState.output.length === 0 ? (
                                <span className="text-zinc-600 italic">Nenhum dado gerado ainda. Clique em 'Iniciar Traceroute'.</span>
                            ) : (
                                traceState.output.map((line, idx) => (
                                    <span key={idx}>{line}</span>
                                ))
                            )}
                            <div ref={terminalEndRef} />
                        </div>
                    </div>
                )}

                {/* Rodapé Informativo */}
                <div className="px-4 py-2 border-t border-zinc-800 text-xs text-zinc-500 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                        {traceState.isRunning && <Activity size={13} className="animate-spin text-purple-400" />}
                        <span>Resolução BGP ASN e Operadora via Team Cymru DNS RFC 1035. Tempos em ms.</span>
                    </div>
                    <span className="text-zinc-600 text-[11px]">Saltos com * indicam firewall descartando ICMP Time-to-Live Exceeded</span>
                </div>
            </div>
        </div>
    );
}
