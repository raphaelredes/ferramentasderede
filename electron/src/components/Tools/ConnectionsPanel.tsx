import { useState, useCallback, useEffect } from 'react';
import { RefreshCw, Network as NetworkIcon, Cpu } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface Conn {
    proto: string; local: string; remote: string;
    status: string; pid: number | null; process: string | null;
}

/** Local connection table (netstat -ano + process name) via psutil. */
export function ConnectionsPanel() {
    const { showToast } = useToast();
    const [conns, setConns, clearConns] = usePersistedState<Conn[]>('connections_tool_data', []);
    const [kind, setKind] = usePersistedState<'inet' | 'tcp' | 'udp'>('connections_tool_kind', 'inet');
    const [filter, setFilter] = usePersistedState('connections_tool_filter', '');
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('connections_tool_last_run', null);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async (k: 'inet' | 'tcp' | 'udp') => {
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/connections?kind=${k}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setConns(data.connections || []);
            setLastRunAt(new Date().toISOString());
        } catch (e: any) {
            showToast('Erro ao listar conexões: ' + e.message, 'error');
        } finally { setBusy(false); }
    }, [showToast, setConns, setLastRunAt]);

    useEffect(() => {
        if (!conns.length) {
            load(kind);
        }
    }, [kind, load]);


    const f = filter.trim().toLowerCase();
    const shown = f
        ? conns.filter(c =>
            c.local.toLowerCase().includes(f) ||
            c.remote.toLowerCase().includes(f) ||
            (c.process || '').toLowerCase().includes(f) ||
            String(c.pid || '').includes(f))
        : conns;

    const statusColor = (s: string) =>
        s === 'ESTABELECIDA' ? 'text-green-400' : s === 'OUVINDO' ? 'text-sky-400' : 'text-zinc-400';

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-3 items-center bg-zinc-900 p-4 rounded-xl border border-zinc-800 flex-wrap">
                <div className="flex gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800">
                    {(['inet', 'tcp', 'udp'] as const).map(k => (
                        <button key={k} onClick={() => setKind(k)}
                            className={clsx('px-3 py-1 rounded text-sm font-medium transition-colors',
                                kind === k ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white')}>
                            {k === 'inet' ? 'Todas' : k.toUpperCase()}
                        </button>
                    ))}
                </div>
                <input type="text" value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filtrar por IP, porta, processo ou PID..."
                    className="flex-1 min-w-48 bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono text-sm placeholder:text-zinc-500" />
                <button onClick={() => load(kind)} disabled={busy}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors disabled:opacity-60">
                    <RefreshCw size={16} className={busy ? 'animate-spin' : ''} /> Atualizar
                </button>
            </div>

            {conns.length > 0 && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={`${conns.length} conexões ativas`}
                    onClear={() => { clearConns(); setLastRunAt(null); }}
                />
            )}

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col">

                {shown.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-zinc-600">
                        <NetworkIcon size={48} className="mb-4 opacity-20" />
                        <p>{busy ? 'Carregando...' : 'Nenhuma conexão para mostrar.'}</p>
                    </div>
                ) : (
                    <div className="flex-1 overflow-auto custom-scrollbar">
                        <table className="w-full text-sm font-mono">
                            <thead className="sticky top-0 bg-zinc-950 text-zinc-500 border-b border-zinc-800">
                                <tr>
                                    <th className="text-left px-3 py-2 font-medium">Proto</th>
                                    <th className="text-left px-3 py-2 font-medium">Local</th>
                                    <th className="text-left px-3 py-2 font-medium">Remoto</th>
                                    <th className="text-left px-3 py-2 font-medium">Estado</th>
                                    <th className="text-left px-3 py-2 font-medium">Processo</th>
                                    <th className="text-right px-3 py-2 font-medium">PID</th>
                                </tr>
                            </thead>
                            <tbody>
                                {shown.map((c, i) => (
                                    <tr key={i} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                                        <td className="px-3 py-1.5 text-zinc-500">{c.proto}</td>
                                        <td className="px-3 py-1.5 text-zinc-300">{c.local}</td>
                                        <td className="px-3 py-1.5 text-zinc-400">{c.remote}</td>
                                        <td className={clsx('px-3 py-1.5', statusColor(c.status))}>{c.status}</td>
                                        <td className="px-3 py-1.5 text-zinc-200 flex items-center gap-1.5">{c.process && <Cpu size={11} className="text-zinc-600" />}{c.process || '—'}</td>
                                        <td className="px-3 py-1.5 text-right text-zinc-500">{c.pid ?? '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                <div className="px-4 py-1.5 border-t border-zinc-800 text-xs text-zinc-600">
                    {shown.length} conexões{f ? ` (de ${conns.length})` : ''}. Conexões de outros usuários exigem privilégio de administrador.
                </div>
            </div>
        </div>
    );
}
