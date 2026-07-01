import { useRef, useEffect, useState } from 'react';
import { Play, Square, Eraser, Ruler } from 'lucide-react';
import { useStreamingTool } from './useStreamingTool';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';

/** Path MTU discovery — finds the largest unfragmented packet to a target. */
export function PmtuPanel() {
    const { output, isRunning, run, stop, clear } = useStreamingTool('/tools/pmtu', 'pmtu');
    const { showToast } = useToast();
    const { networks } = useNetworks();

    const [target, setTarget] = useState('8.8.8.8');
    const [sourceIp, setSourceIp] = useState('');
    const endRef = useRef<HTMLDivElement>(null);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [output]);

    const start = () => {
        const t = target.trim();
        if (!t) { showToast('Informe o alvo.', 'error'); return; }
        run({ target: t, source_ip: sourceIp || undefined });
    };

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Alvo (IP ou Hostname)</label>
                    <input type="text" value={target} onChange={e => setTarget(e.target.value)} disabled={isRunning}
                        onFocus={() => { if (target === '8.8.8.8') setTarget(''); }}
                        onKeyDown={e => { if (e.key === 'Enter' && !isRunning) start(); }}
                        className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 font-mono disabled:opacity-60 ${target === '8.8.8.8' ? 'text-zinc-500' : 'text-white'}`} />
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
                    <button onClick={start} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-teal-400 border border-teal-900/30 hover:border-teal-500/50 transition-colors">
                        <Play size={18} /> Descobrir MTU
                    </button>
                ) : (
                    <button onClick={stop} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors">
                        <Square size={18} /> Parar
                    </button>
                )}
            </div>
            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm">
                <button onClick={clear} disabled={isRunning} title="Limpar" className="absolute top-2 right-2 z-10 p-2 text-zinc-500 hover:text-white rounded-lg hover:bg-zinc-800 disabled:opacity-30">
                    <Eraser size={16} />
                </button>
                <div className="flex-1 overflow-auto custom-scrollbar">
                    {output.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <Ruler size={48} className="mb-4 opacity-20" />
                            <p>Descobre o maior pacote que passa sem fragmentar (MTU do caminho).</p>
                        </div>
                    ) : output.map((l, i) => <div key={i} className="whitespace-pre-wrap break-all text-zinc-300 leading-tight">{l}</div>)}
                    <div ref={endRef} />
                </div>
            </div>
        </div>
    );
}
