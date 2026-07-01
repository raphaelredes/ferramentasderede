import { useRef, useEffect, useState } from 'react';
import { Play, Square, Eraser, DoorOpen } from 'lucide-react';
import { clsx } from 'clsx';
import { useTools } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';

/**
 * TCP port tester. Backed by the existing scan_top_ports / test_specific_ports
 * generators (no source_ip — a TCP connect always uses the OS routing table).
 */
export function PortScanPanel() {
    const { portState, runPortScan, stopTool, clearToolOutput } = useTools();
    const { showToast } = useToast();

    const [target, setTarget] = useState('');
    const [ports, setPorts] = useState('80, 443, 3389, 445');
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
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-4">
                <div className="flex gap-4 items-end">
                    <div className="flex-1 space-y-2">
                        <label className="text-sm font-medium text-zinc-400">Host alvo (IP ou Hostname)</label>
                        <input
                            type="text"
                            value={target}
                            onChange={(e) => setTarget(e.target.value)}
                            disabled={portState.isRunning}
                            placeholder="192.168.1.10"
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500 disabled:opacity-60"
                            onKeyDown={(e) => { if (e.key === 'Enter' && !portState.isRunning) start(); }}
                        />
                    </div>
                    <div className="flex-1 space-y-2">
                        <label className="text-sm font-medium text-zinc-400">Portas (lista ou faixa)</label>
                        <input
                            type="text"
                            value={ports}
                            onChange={(e) => setPorts(e.target.value)}
                            disabled={portState.isRunning}
                            placeholder="80, 443, 8000-8100"
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500 disabled:opacity-60"
                            onKeyDown={(e) => { if (e.key === 'Enter' && !portState.isRunning) start(); }}
                        />
                    </div>
                    <div className="flex gap-2">
                        {!portState.isRunning ? (
                            <>
                                <button
                                    onClick={() => start()}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-emerald-400 border border-emerald-900/30 hover:border-emerald-500/50 transition-colors"
                                >
                                    <Play size={18} />
                                    Testar
                                </button>
                                <button
                                    onClick={() => start('top')}
                                    title="Escanear as portas mais comuns"
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 hover:border-zinc-600 transition-colors"
                                >
                                    Portas comuns
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={() => stopTool('ports')}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                            >
                                <Square size={18} />
                                Parar
                            </button>
                        )}
                    </div>
                </div>
                <p className="text-xs text-zinc-600">
                    Teste TCP connect. Aceita lista (<code className="text-zinc-500">80, 443</code>) ou faixa (<code className="text-zinc-500">8000-8100</code>). "Portas comuns" varre as portas mais usadas.
                </p>
            </div>

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm">
                <div className="absolute top-2 right-2 z-10">
                    <button
                        onClick={() => clearToolOutput('ports')}
                        disabled={portState.isRunning}
                        className="p-2 text-zinc-500 hover:text-white transition-colors rounded-lg hover:bg-zinc-800 disabled:opacity-30 disabled:hover:text-zinc-500 disabled:hover:bg-transparent"
                        title={portState.isRunning ? 'Pare a varredura para limpar' : 'Limpar'}
                    >
                        <Eraser size={16} />
                    </button>
                </div>
                <div className="flex-1 overflow-auto custom-scrollbar">
                    {portState.output.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <DoorOpen size={48} className="mb-4 opacity-20" />
                            <p>Informe um host e teste as portas.</p>
                        </div>
                    ) : (
                        portState.output.map((line, i) => (
                            <div key={i} className={clsx(
                                'whitespace-pre-wrap break-all leading-tight',
                                line.includes('[ABERTA]') || line.includes('aberta') ? 'text-green-400' : 'text-zinc-300'
                            )}>
                                {line}
                            </div>
                        ))
                    )}
                    <div ref={outputEndRef} />
                </div>
            </div>
        </div>
    );
}
