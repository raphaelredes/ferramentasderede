import { useRef, useEffect } from 'react';
import { Play, Square, Eraser, DoorOpen } from 'lucide-react';
import { clsx } from 'clsx';
import { useTools } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';

/**
 * TCP port tester. Backed by high-concurrency ThreadPoolExecutor and adaptive timeouts.
 */
export function PortScanPanel() {
    const { portState, runPortScan, stopTool, clearToolOutput } = useTools();
    const { showToast } = useToast();

    const [target, setTarget] = usePersistedState('port_scan_tool_target', '');
    const [ports, setPorts] = usePersistedState('port_scan_tool_ports', '80, 443, 3389, 445');
    const outputEndRef = useRef<HTMLDivElement>(null);


    useEffect(() => {
        outputEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [portState.output]);

    const start = (mode?: 'top') => {
        const t = target.trim();
        if (!t) { showToast('Informe um host alvo.', 'error'); return; }
        if (!mode && !ports.trim()) { showToast('Informe as portas (ex.: 80, 443, 8000-8100).', 'error'); return; }
        runPortScan(t, ports, mode);
    };

    return (
        <div className="h-full flex flex-col space-y-4 min-h-0 overflow-hidden">
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-3 shrink-0">
                <div className="flex flex-wrap gap-4 items-end">
                    <div className="flex-1 min-w-[200px] space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Host alvo (IP ou Hostname)</label>
                        <input
                            type="text"
                            value={target}
                            onChange={(e) => setTarget(e.target.value)}
                            disabled={portState.isRunning}
                            placeholder="192.168.1.10"
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3.5 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono text-sm placeholder:text-zinc-500 disabled:opacity-60"
                            onKeyDown={(e) => { if (e.key === 'Enter' && !portState.isRunning) start(); }}
                        />
                    </div>
                    <div className="flex-1 min-w-[200px] space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Portas (lista ou faixa)</label>
                        <input
                            type="text"
                            value={ports}
                            onChange={(e) => setPorts(e.target.value)}
                            disabled={portState.isRunning}
                            placeholder="80, 443, 8000-8100"
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3.5 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono text-sm placeholder:text-zinc-500 disabled:opacity-60"
                            onKeyDown={(e) => { if (e.key === 'Enter' && !portState.isRunning) start(); }}
                        />
                    </div>
                    <div className="flex gap-2">
                        {!portState.isRunning ? (
                            <>
                                <button
                                    onClick={() => start()}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 hover:border-emerald-500/50 transition-colors shadow-sm"
                                >
                                    <Play size={16} />
                                    Testar Portas
                                </button>
                                <button
                                    onClick={() => start('top')}
                                    title="Escanear as 60 portas mais comuns da rede"
                                    className="flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 hover:border-zinc-600 transition-colors"
                                >
                                    Portas Comuns
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={() => stopTool('ports')}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 hover:border-red-500/50 transition-colors animate-pulse"
                            >
                                <Square size={16} />
                                Parar Teste
                            </button>
                        )}
                    </div>
                </div>
                <p className="text-[11px] text-zinc-500">
                    Varredura TCP paralela multi-thread. Suporta faixas grandes (ex.: <code className="text-zinc-400">1-9000</code>) com velocidade de até 1.200 portas/segundo.
                </p>
            </div>

            <div className="flex-1 min-h-0 bg-black rounded-xl border border-zinc-800 p-4 flex flex-col relative font-mono text-xs overflow-hidden">
                <div className="absolute top-2.5 right-2.5 z-10">
                    <button
                        onClick={() => clearToolOutput('ports')}
                        disabled={portState.isRunning}
                        className="p-1.5 text-zinc-500 hover:text-white transition-colors rounded-lg hover:bg-zinc-800 disabled:opacity-30 disabled:hover:text-zinc-500 disabled:hover:bg-transparent"
                        title={portState.isRunning ? 'Pare a varredura para limpar' : 'Limpar saída'}
                    >
                        <Eraser size={15} />
                    </button>
                </div>
                <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pr-2 space-y-0.5">
                    {portState.output.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <DoorOpen size={40} className="mb-3 opacity-20" />
                            <p className="text-xs">Informe um host e execute o teste para visualizar os resultados.</p>
                        </div>
                    ) : (
                        portState.output.map((line, i) => {
                            const isOpen = line.includes('[ABERTA]') || line.includes('aberta') || line.startsWith('[+]');
                            const isClosed = line.includes('[FECHADA]') || line.includes('fechada');
                            const isHeader = line.includes('Iniciando') || line.includes('Progresso:');
                            const isSummary = line.includes('concluído') || line.includes('Total de portas');
                            
                            return (
                                <div key={i} className={clsx(
                                    'whitespace-pre-wrap break-all leading-tight font-mono text-xs',
                                    isOpen && 'text-emerald-400 font-semibold',
                                    isClosed && 'text-zinc-500',
                                    isHeader && 'text-blue-400',
                                    isSummary && 'text-amber-400 font-semibold',
                                    !isOpen && !isClosed && !isHeader && !isSummary && 'text-zinc-300'
                                )}>
                                    {line}
                                </div>
                            );
                        })
                    )}
                    <div ref={outputEndRef} />
                </div>
            </div>
        </div>
    );
}
