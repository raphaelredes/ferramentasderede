import React, { useState, useMemo } from 'react';
import { Play, Square, RotateCw, Search, Settings, CheckCircle2, XCircle, Clock } from 'lucide-react';

interface ServicesTabProps {
    services: any[];
    handleServiceAction: (serviceName: string, action: string, startupType?: string) => void;
}

type StatusFilter = 'all' | 'running' | 'stopped' | 'auto';

export const ServicesTab: React.FC<ServicesTabProps> = ({ services, handleServiceAction }) => {
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
    const [editingStartup, setEditingStartup] = useState<string | null>(null);

    const isRunning = (s: any) => s.Status === 'Running' || s.Status === 4 || s.Status === '4';
    const isStopped = (s: any) => s.Status === 'Stopped' || s.Status === 1 || s.Status === '1';
    const isAuto = (s: any) => s.StartType === 'Automatic' || s.StartType === 2 || s.StartType === '2' || s.StartType === 'AutomaticDelayedStart';

    const counts = useMemo(() => {
        let running = 0;
        let stopped = 0;
        let auto = 0;
        for (const s of services) {
            if (isRunning(s)) running++;
            if (isStopped(s)) stopped++;
            if (isAuto(s)) auto++;
        }
        return { total: services.length, running, stopped, auto };
    }, [services]);

    const filteredServices = useMemo(() => {
        return services.filter(svc => {
            const matchesSearch =
                (svc.Name || '').toLowerCase().includes(search.toLowerCase()) ||
                (svc.DisplayName || '').toLowerCase().includes(search.toLowerCase());

            if (!matchesSearch) return false;

            if (statusFilter === 'running') return isRunning(svc);
            if (statusFilter === 'stopped') return isStopped(svc);
            if (statusFilter === 'auto') return isAuto(svc);
            return true;
        });
    }, [services, search, statusFilter]);

    const translateStatus = (status: string | number) => {
        const s = status.toString();
        switch (s) {
            case 'Running':
            case '4': return 'Iniciado';
            case 'Stopped':
            case '1': return 'Parado';
            case 'Paused':
            case '7': return 'Pausado';
            case 'StartPending':
            case '2': return 'Iniciando...';
            case 'StopPending':
            case '3': return 'Parando...';
            case 'ContinuePending':
            case '5': return 'Continuando...';
            case 'PausePending':
            case '6': return 'Pausando...';
            default: return status;
        }
    };

    const translateStartType = (type: string | number) => {
        const t = type.toString();
        switch (t) {
            case 'Automatic':
            case '2': return 'Automático';
            case 'Manual':
            case '3': return 'Manual';
            case 'Disabled':
            case '4': return 'Desabilitado';
            case 'AutomaticDelayedStart': return 'Automático (Atraso)';
            case 'Boot':
            case '0': return 'Boot';
            case 'System':
            case '1': return 'Sistema';
            default: return type;
        }
    };

    const handleStartupChange = (serviceName: string, newType: string) => {
        handleServiceAction(serviceName, 'set_startup', newType);
        setEditingStartup(null);
    };

    return (
        <div className="space-y-4">
            {/* Header com Busca e Filtros Rápidos */}
            <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={17} />
                    <input
                        type="text"
                        placeholder="Buscar serviço por nome ou descrição..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-xl pl-9 pr-4 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500/60 transition-colors"
                    />
                </div>

                {/* Filtros em Pílulas */}
                <div className="flex items-center gap-1.5 bg-zinc-900/60 border border-zinc-800 p-1 rounded-xl shrink-0 overflow-x-auto">
                    <button
                        onClick={() => setStatusFilter('all')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            statusFilter === 'all'
                                ? 'bg-blue-600 text-white'
                                : 'text-zinc-400 hover:text-white'
                        }`}
                    >
                        Todos ({counts.total})
                    </button>
                    <button
                        onClick={() => setStatusFilter('running')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                            statusFilter === 'running'
                                ? 'bg-emerald-600 text-white'
                                : 'text-zinc-400 hover:text-emerald-400'
                        }`}
                    >
                        <CheckCircle2 size={13} />
                        Executando ({counts.running})
                    </button>
                    <button
                        onClick={() => setStatusFilter('stopped')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                            statusFilter === 'stopped'
                                ? 'bg-zinc-700 text-white'
                                : 'text-zinc-400 hover:text-zinc-300'
                        }`}
                    >
                        <XCircle size={13} />
                        Parados ({counts.stopped})
                    </button>
                    <button
                        onClick={() => setStatusFilter('auto')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                            statusFilter === 'auto'
                                ? 'bg-purple-600 text-white'
                                : 'text-zinc-400 hover:text-purple-400'
                        }`}
                    >
                        <Clock size={13} />
                        Automáticos ({counts.auto})
                    </button>
                </div>
            </div>

            {/* Tabela de Serviços */}
            <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden shadow-lg">
                <div className="overflow-x-auto">
                    <table className="w-full text-left table-fixed">
                        <thead className="bg-zinc-900/80 text-zinc-400 text-xs uppercase tracking-wider sticky top-0 z-10 backdrop-blur-sm border-b border-zinc-700/50">
                            <tr>
                                <th className="p-3.5 font-semibold w-1/4">Nome do Serviço</th>
                                <th className="p-3.5 font-semibold w-1/3">Descrição (Display Name)</th>
                                <th className="p-3.5 font-semibold w-28 text-center">Status</th>
                                <th className="p-3.5 font-semibold w-36">Tipo de Inicialização</th>
                                <th className="p-3.5 font-semibold text-right w-36">Ações Rápidas</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-700/40 text-sm">
                            {filteredServices.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-zinc-500">
                                        Nenhum serviço encontrado para o filtro selecionado.
                                    </td>
                                </tr>
                            ) : (
                                filteredServices.map((svc: any) => {
                                    const running = isRunning(svc);
                                    const stopped = isStopped(svc);

                                    return (
                                        <tr key={svc.Name} className="hover:bg-zinc-700/20 transition-colors group">
                                            <td className="p-3.5 text-white font-medium truncate font-mono text-xs" title={svc.Name}>
                                                {svc.Name}
                                            </td>
                                            <td className="p-3.5 text-zinc-300 truncate text-xs sm:text-sm" title={svc.DisplayName}>
                                                {svc.DisplayName}
                                            </td>
                                            <td className="p-3.5 text-center">
                                                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold inline-block ${
                                                    running
                                                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                                        : (svc.Status === 'Paused' || svc.Status === 7 || svc.Status === '7')
                                                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                                            : 'bg-zinc-700/40 text-zinc-400 border border-zinc-700/50'
                                                }`}>
                                                    {translateStatus(svc.Status)}
                                                </span>
                                            </td>
                                            <td className="p-3.5 text-zinc-400 text-xs truncate relative group/startup">
                                                {editingStartup === svc.Name ? (
                                                    <select
                                                        className="bg-zinc-900 border border-blue-500 rounded px-2 py-1 text-xs text-white focus:outline-none w-full"
                                                        defaultValue={svc.StartType}
                                                        onChange={(e) => handleStartupChange(svc.Name, e.target.value)}
                                                        onBlur={() => setEditingStartup(null)}
                                                        autoFocus
                                                    >
                                                        <option value="Automatic">Automático</option>
                                                        <option value="Manual">Manual</option>
                                                        <option value="Disabled">Desabilitado</option>
                                                        <option value="AutomaticDelayedStart">Automático (Atraso)</option>
                                                    </select>
                                                ) : (
                                                    <div
                                                        className="flex items-center justify-between cursor-pointer hover:text-white p-1 rounded hover:bg-zinc-700/30 transition-colors"
                                                        onClick={() => setEditingStartup(svc.Name)}
                                                        title="Clique para alterar tipo de inicialização"
                                                    >
                                                        <span>{translateStartType(svc.StartType)}</span>
                                                        <Settings size={12} className="opacity-40 group-hover/startup:opacity-100 transition-opacity text-blue-400" />
                                                    </div>
                                                )}
                                            </td>
                                            <td className="p-3.5 text-right">
                                                <div className="flex justify-end gap-1.5 opacity-90 group-hover:opacity-100 transition-opacity">
                                                    {stopped ? (
                                                        <button
                                                            onClick={() => handleServiceAction(svc.Name, 'start')}
                                                            className="p-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/20 transition-colors"
                                                            title="Iniciar Serviço"
                                                        >
                                                            <Play size={14} />
                                                        </button>
                                                    ) : (
                                                        <>
                                                            <button
                                                                onClick={() => handleServiceAction(svc.Name, 'restart')}
                                                                className="p-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-lg border border-blue-500/20 transition-colors"
                                                                title="Reiniciar Serviço"
                                                            >
                                                                <RotateCw size={14} />
                                                            </button>
                                                            <button
                                                                onClick={() => handleServiceAction(svc.Name, 'stop')}
                                                                className="p-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg border border-red-500/20 transition-colors"
                                                                title="Parar Serviço"
                                                            >
                                                                <Square size={14} />
                                                            </button>
                                                        </>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="p-3 bg-zinc-900/60 border-t border-zinc-700/40 text-xs text-zinc-400 flex items-center justify-between">
                    <span>
                        Exibindo <strong>{filteredServices.length}</strong> de <strong>{services.length}</strong> serviços
                    </span>
                    {search && (
                        <button
                            onClick={() => setSearch('')}
                            className="text-blue-400 hover:text-blue-300 font-medium"
                        >
                            Limpar busca
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};
