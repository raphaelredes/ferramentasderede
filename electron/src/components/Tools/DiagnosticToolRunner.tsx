import { useRef } from 'react';
import { Play, Square, Terminal as TerminalIcon, Eraser, Activity } from 'lucide-react';
import { clsx } from 'clsx';
import type { NetworkConfig } from '../../pages/Settings';

interface DiagnosticToolRunnerProps {
    type: 'ping' | 'traceroute';
    state: { isRunning: boolean; output: string[] };
    target: string;
    setTarget: (t: string) => void;
    run: (t: string, sourceIp?: string) => void;
    stop: () => void;
    clear: () => void;
    colorClass: string;
    borderColorClass: string;
    sourceIp: string;
    setSourceIp: (v: string) => void;
    availableNetworks: NetworkConfig[];
}

export function DiagnosticToolRunner({
    type,
    state,
    target,
    setTarget,
    run,
    stop,
    clear,
    colorClass,
    borderColorClass,
    sourceIp,
    setSourceIp,
    availableNetworks,
}: DiagnosticToolRunnerProps) {
    const outputEndRef = useRef<HTMLDivElement>(null);

    return (
        <div className="h-full flex flex-col space-y-4 min-h-0 overflow-hidden">
            <div className="flex flex-wrap gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800 shrink-0">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Alvo (IP ou Hostname)</label>
                    <input
                        type="text"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        onFocus={() => { if (target === '8.8.8.8') setTarget(''); }}
                        placeholder="8.8.8.8"
                        className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500 ${target === '8.8.8.8' ? 'text-zinc-500' : 'text-white'}`}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !state.isRunning) run(target || '8.8.8.8', sourceIp || undefined);
                        }}
                    />
                </div>

                <div className="space-y-2 w-64">
                    <label className="text-sm font-medium text-zinc-400">Sair pela rede</label>
                    <select
                        value={sourceIp}
                        onChange={(e) => setSourceIp(e.target.value)}
                        disabled={state.isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-60"
                    >
                        <option value="">Automático (rota padrão)</option>
                        {availableNetworks.map(net => (
                            <option key={net.id} value={net.source_ip ?? ''} disabled={!net.source_ip}>
                                {net.name || net.cidr}
                                {net.source_ip ? ` — ${net.source_ip}` : ' (sem source IP)'}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={() => run(target || '8.8.8.8', sourceIp || undefined)}
                        disabled={state.isRunning}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors border",
                            state.isRunning
                                ? "bg-zinc-900 text-zinc-600 border-zinc-800 cursor-not-allowed"
                                : `bg-zinc-800 hover:bg-zinc-700 ${colorClass} ${borderColorClass}`
                        )}
                    >
                        {state.isRunning ? <Activity size={18} className="animate-spin" /> : <Play size={18} />}
                        {type === 'ping' ? 'Iniciar Ping' : 'Iniciar Traceroute'}
                    </button>

                    {state.isRunning && (
                        <button
                            onClick={stop}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                        >
                            <Square size={18} />
                            Parar
                        </button>
                    )}
                </div>
            </div>

            <div className="flex-1 min-h-0 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm">
                <div className="absolute top-2 right-2 z-10">
                    <button
                        onClick={clear}
                        className="p-2 text-zinc-500 hover:text-white transition-colors rounded-lg hover:bg-zinc-800"
                        title="Limpar Terminal"
                    >
                        <Eraser size={16} />
                    </button>
                </div>

                <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-2">
                    {state.output.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <TerminalIcon size={48} className="mb-4 opacity-20" />
                            <p>Aguardando comando...</p>
                        </div>
                    )}

                    {state.output.map((line, i) => (
                        <div key={i} className="whitespace-pre-wrap break-all text-zinc-300 leading-tight">
                            {line}
                        </div>
                    ))}
                    <div ref={outputEndRef} />
                </div>
            </div>
        </div>
    );
}
