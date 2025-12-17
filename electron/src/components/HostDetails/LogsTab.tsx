import React, { useState } from 'react';
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

export const LogsTab: React.FC<LogsTabProps> = ({ logs, formatDate }) => {
    const [search, setSearch] = useState('');
    const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
    const [copiedField, setCopiedField] = useState<string | null>(null);

    const filteredLogs = logs.filter(log =>
        (log.Message?.toLowerCase() || '').includes(search.toLowerCase()) ||
        (log.ProviderName?.toLowerCase() || '').includes(search.toLowerCase()) ||
        log.Id.toString().includes(search)
    );

    const handleCopy = (text: string, field: string) => {
        navigator.clipboard.writeText(text);
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 2000);
    };

    return (
        <div className="flex flex-col h-full space-y-4 relative">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
                <input
                    type="text"
                    placeholder="Buscar nos logs (Mensagem, Fonte, ID)..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-zinc-800/50 border border-zinc-700/50 rounded-lg pl-10 pr-4 py-2 text-zinc-300 focus:outline-none focus:border-blue-500/50 transition-colors"
                />
            </div>

            <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden flex flex-col flex-1">
                <div className="overflow-auto flex-1 custom-scrollbar">
                    <table className="w-full text-left table-fixed">
                        <thead className="bg-zinc-900/50 text-zinc-400 text-sm sticky top-0 backdrop-blur-sm z-10">
                            <tr>
                                <th className="p-4 font-medium w-16">Nível</th>
                                <th className="p-4 font-medium w-48">Data/Hora</th>
                                <th className="p-4 font-medium w-48">Fonte</th>
                                <th className="p-4 font-medium w-24">ID</th>
                                <th className="p-4 font-medium">Mensagem</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-700/50">
                            {filteredLogs.map((log, i) => (
                                <tr
                                    key={i}
                                    onClick={() => setSelectedLog(log)}
                                    className="hover:bg-zinc-700/20 transition-colors cursor-pointer group"
                                >
                                    <td className="p-4">
                                        {log.LevelDisplayName === 'Error' && <AlertCircle size={18} className="text-red-400" />}
                                        {log.LevelDisplayName === 'Warning' && <AlertTriangle size={18} className="text-yellow-400" />}
                                        {log.LevelDisplayName === 'Information' && <Info size={18} className="text-blue-400" />}
                                    </td>
                                    <td className="p-4 text-zinc-400 text-sm whitespace-nowrap">
                                        {formatDate(log.TimeCreated)}
                                    </td>
                                    <td className="p-4 text-zinc-300 text-sm truncate" title={log.ProviderName}>
                                        {log.ProviderName}
                                    </td>
                                    <td className="p-4 text-zinc-400 text-sm">{log.Id}</td>
                                    <td className="p-4 text-zinc-300 text-sm truncate group-hover:text-blue-400 transition-colors">
                                        {log.Message}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Log Details Modal */}
            {selectedLog && (
                <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm rounded-xl animate-in fade-in duration-200">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-2xl shadow-2xl flex flex-col max-h-full" onClick={e => e.stopPropagation()}>
                        <div className="p-4 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/50 rounded-t-xl">
                            <div className="flex items-center gap-3">
                                {selectedLog.LevelDisplayName === 'Error' && <AlertCircle size={20} className="text-red-400" />}
                                {selectedLog.LevelDisplayName === 'Warning' && <AlertTriangle size={20} className="text-yellow-400" />}
                                {selectedLog.LevelDisplayName === 'Information' && <Info size={20} className="text-blue-400" />}
                                <h3 className="text-lg font-semibold text-white">Detalhes do Evento</h3>
                            </div>
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <div className="p-6 overflow-y-auto custom-scrollbar space-y-6">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500 uppercase tracking-wider">Data e Hora</p>
                                    <p className="text-zinc-300 font-mono text-sm">{formatDate(selectedLog.TimeCreated)}</p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500 uppercase tracking-wider">ID do Evento</p>
                                    <p className="text-zinc-300 font-mono text-sm">{selectedLog.Id}</p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500 uppercase tracking-wider">Fonte (Provider)</p>
                                    <p className="text-zinc-300 font-mono text-sm">{selectedLog.ProviderName}</p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500 uppercase tracking-wider">Nível</p>
                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${selectedLog.LevelDisplayName === 'Error' ? 'bg-red-500/10 text-red-400' :
                                        selectedLog.LevelDisplayName === 'Warning' ? 'bg-yellow-500/10 text-yellow-400' :
                                            'bg-blue-500/10 text-blue-400'
                                        }`}>
                                        {selectedLog.LevelDisplayName}
                                    </span>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <p className="text-xs text-zinc-500 uppercase tracking-wider">Mensagem</p>
                                    <button
                                        onClick={() => handleCopy(selectedLog.Message, 'message')}
                                        className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                                    >
                                        {copiedField === 'message' ? <Check size={12} /> : <Copy size={12} />}
                                        {copiedField === 'message' ? 'Copiado!' : 'Copiar'}
                                    </button>
                                </div>
                                <div className="bg-zinc-950/50 rounded-lg border border-zinc-800/50 p-4 font-mono text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                                    {selectedLog.Message}
                                </div>
                            </div>
                        </div>

                        <div className="p-4 border-t border-zinc-800 bg-zinc-900/50 rounded-b-xl flex justify-end">
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm font-medium transition-colors"
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
