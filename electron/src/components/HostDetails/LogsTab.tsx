import React, { useState, useMemo } from 'react';
import { AlertCircle, Info, AlertTriangle, Search, X, Copy, Check } from 'lucide-react';

interface LogEntry {
    TimeCreated: string;
    Id: number;
    LevelDisplayName: string;
    ProviderName: string;
    Message: string;
}

interface LogsTabProps {
    logs: LogEntry[];
    formatDate: (date: string) => string;
}

type LogFilter = 'all' | 'error' | 'warning' | 'info';

export const LogsTab: React.FC<LogsTabProps> = ({ logs, formatDate }) => {
    const [search, setSearch] = useState('');
    const [filterLevel, setFilterLevel] = useState<LogFilter>('all');
    const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
    const [copiedField, setCopiedField] = useState<string | null>(null);

    const counts = useMemo(() => {
        let error = 0;
        let warning = 0;
        let info = 0;
        for (const log of logs) {
            const lvl = (log.LevelDisplayName || '').toLowerCase();
            if (lvl === 'error' || lvl === 'erro' || lvl === 'critical') error++;
            else if (lvl === 'warning' || lvl === 'aviso') warning++;
            else info++;
        }
        return { total: logs.length, error, warning, info };
    }, [logs]);

    const filteredLogs = useMemo(() => {
        return logs.filter(log => {
            const lvl = (log.LevelDisplayName || '').toLowerCase();
            if (filterLevel === 'error' && lvl !== 'error' && lvl !== 'erro' && lvl !== 'critical') return false;
            if (filterLevel === 'warning' && lvl !== 'warning' && lvl !== 'aviso') return false;
            if (filterLevel === 'info' && lvl !== 'information' && lvl !== 'info') return false;

            if (!search) return true;
            const term = search.toLowerCase();
            return (
                (log.Message?.toLowerCase() || '').includes(term) ||
                (log.ProviderName?.toLowerCase() || '').includes(term) ||
                log.Id.toString().includes(term)
            );
        });
    }, [logs, search, filterLevel]);

    const handleCopy = (text: string, field: string) => {
        navigator.clipboard.writeText(text);
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 2000);
    };

    return (
        <div className="flex flex-col h-full space-y-4 relative">
            {/* Header: Busca e Filtros de Gravidade */}
            <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={17} />
                    <input
                        type="text"
                        placeholder="Buscar nos logs (Mensagem, Provedor/Fonte, Event ID)..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-xl pl-9 pr-4 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500/60 transition-colors"
                    />
                </div>

                <div className="flex items-center gap-1.5 bg-zinc-900/60 border border-zinc-800 p-1 rounded-xl shrink-0 overflow-x-auto">
                    <button
                        onClick={() => setFilterLevel('all')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            filterLevel === 'all' ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white'
                        }`}
                    >
                        Todos ({counts.total})
                    </button>
                    <button
                        onClick={() => setFilterLevel('error')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                            filterLevel === 'error' ? 'bg-red-600 text-white' : 'text-zinc-400 hover:text-red-400'
                        }`}
                    >
                        <AlertCircle size={13} />
                        Erros ({counts.error})
                    </button>
                    <button
                        onClick={() => setFilterLevel('warning')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                            filterLevel === 'warning' ? 'bg-amber-600 text-white' : 'text-zinc-400 hover:text-amber-400'
                        }`}
                    >
                        <AlertTriangle size={13} />
                        Avisos ({counts.warning})
                    </button>
                    <button
                        onClick={() => setFilterLevel('info')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                            filterLevel === 'info' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-blue-400'
                        }`}
                    >
                        <Info size={13} />
                        Info ({counts.info})
                    </button>
                </div>
            </div>

            {/* Tabela de Eventos */}
            <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden flex flex-col flex-1 shadow-lg">
                <div className="overflow-auto flex-1 custom-scrollbar">
                    <table className="w-full text-left table-fixed">
                        <thead className="bg-zinc-900/80 text-zinc-400 text-xs uppercase tracking-wider sticky top-0 backdrop-blur-sm z-10 border-b border-zinc-700/50">
                            <tr>
                                <th className="p-3.5 font-semibold w-16 text-center">Nível</th>
                                <th className="p-3.5 font-semibold w-44">Data / Hora</th>
                                <th className="p-3.5 font-semibold w-48">Fonte (Provider)</th>
                                <th className="p-3.5 font-semibold w-24 text-center">ID Evento</th>
                                <th className="p-3.5 font-semibold">Mensagem do Evento</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-700/40 text-sm">
                            {filteredLogs.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-zinc-500">
                                        Nenhum evento registrado para o critério selecionado.
                                    </td>
                                </tr>
                            ) : (
                                filteredLogs.map((log, i) => {
                                    const lvl = (log.LevelDisplayName || '').toLowerCase();
                                    const isErr = lvl === 'error' || lvl === 'erro' || lvl === 'critical';
                                    const isWarn = lvl === 'warning' || lvl === 'aviso';

                                    return (
                                        <tr
                                            key={i}
                                            onClick={() => setSelectedLog(log)}
                                            className={`transition-colors cursor-pointer group ${
                                                isErr ? 'hover:bg-red-500/10 bg-red-950/5' :
                                                isWarn ? 'hover:bg-amber-500/10 bg-amber-950/5' :
                                                'hover:bg-zinc-700/20'
                                            }`}
                                        >
                                            <td className="p-3.5 text-center">
                                                {isErr && <AlertCircle size={17} className="text-red-400 inline" />}
                                                {isWarn && <AlertTriangle size={17} className="text-amber-400 inline" />}
                                                {!isErr && !isWarn && <Info size={17} className="text-blue-400 inline" />}
                                            </td>
                                            <td className="p-3.5 text-zinc-400 text-xs whitespace-nowrap font-mono">
                                                {formatDate(log.TimeCreated)}
                                            </td>
                                            <td className="p-3.5 text-zinc-300 text-xs truncate" title={log.ProviderName}>
                                                {log.ProviderName}
                                            </td>
                                            <td className="p-3.5 text-zinc-400 font-mono text-xs text-center">
                                                {log.Id}
                                            </td>
                                            <td className="p-3.5 text-zinc-300 text-xs truncate group-hover:text-blue-400 transition-colors">
                                                {log.Message}
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
                        Exibindo <strong>{filteredLogs.length}</strong> de <strong>{logs.length}</strong> eventos
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

            {/* Modal de Detalhes do Evento */}
            {selectedLog && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150"
                    onClick={() => setSelectedLog(null)}
                >
                    <div
                        className="bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-in zoom-in-95 duration-150"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="p-5 border-b border-zinc-800 flex justify-between items-center bg-zinc-950/60">
                            <div className="flex items-center gap-3">
                                {selectedLog.LevelDisplayName?.toLowerCase() === 'error' && <AlertCircle size={22} className="text-red-400" />}
                                {selectedLog.LevelDisplayName?.toLowerCase() === 'warning' && <AlertTriangle size={22} className="text-amber-400" />}
                                {selectedLog.LevelDisplayName?.toLowerCase() !== 'error' && selectedLog.LevelDisplayName?.toLowerCase() !== 'warning' && <Info size={22} className="text-blue-400" />}
                                <div>
                                    <h3 className="text-base font-bold text-white">Detalhes do Evento do Windows</h3>
                                    <span className="text-xs text-zinc-400">Event Viewer (Visualizador de Eventos)</span>
                                </div>
                            </div>
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="p-1.5 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="p-6 overflow-y-auto custom-scrollbar space-y-5 text-sm">
                            <div className="grid grid-cols-2 gap-4 bg-zinc-950/50 p-4 rounded-xl border border-zinc-800">
                                <div className="space-y-0.5">
                                    <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-semibold">Data / Hora</span>
                                    <p className="text-zinc-200 font-mono text-xs">{formatDate(selectedLog.TimeCreated)}</p>
                                </div>
                                <div className="space-y-0.5">
                                    <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-semibold">ID do Evento</span>
                                    <p className="text-zinc-200 font-mono text-xs font-bold">{selectedLog.Id}</p>
                                </div>
                                <div className="space-y-0.5">
                                    <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-semibold">Fonte (Provider)</span>
                                    <p className="text-zinc-200 text-xs font-medium truncate" title={selectedLog.ProviderName}>{selectedLog.ProviderName}</p>
                                </div>
                                <div className="space-y-0.5">
                                    <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-semibold">Nível</span>
                                    <div>
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                                            selectedLog.LevelDisplayName?.toLowerCase() === 'error' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                                            selectedLog.LevelDisplayName?.toLowerCase() === 'warning' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                                            'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                        }`}>
                                            {selectedLog.LevelDisplayName}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider">Mensagem Completa</span>
                                    <button
                                        onClick={() => handleCopy(selectedLog.Message, 'msg')}
                                        className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
                                    >
                                        {copiedField === 'msg' ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                                        {copiedField === 'msg' ? 'Copiado!' : 'Copiar Mensagem'}
                                    </button>
                                </div>
                                <div className="bg-zinc-950/80 rounded-xl border border-zinc-800 p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto custom-scrollbar">
                                    {selectedLog.Message}
                                </div>
                            </div>
                        </div>

                        <div className="p-4 border-t border-zinc-800 bg-zinc-950/60 flex justify-end">
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg transition-colors"
                            >
                                Fechar
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
