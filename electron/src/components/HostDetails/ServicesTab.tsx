import React, { useState } from 'react';
import { Play, Square, RotateCw, Search, Pause, Settings } from 'lucide-react';

interface ServicesTabProps {
    services: any[];
    handleServiceAction: (serviceName: string, action: string, startupType?: string) => void;
}

export const ServicesTab: React.FC<ServicesTabProps> = ({ services, handleServiceAction }) => {
    const [search, setSearch] = useState('');
    const [editingStartup, setEditingStartup] = useState<string | null>(null);

    const filteredServices = services.filter(svc =>
        svc.Name.toLowerCase().includes(search.toLowerCase()) ||
        svc.DisplayName.toLowerCase().includes(search.toLowerCase())
    );

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
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={18} />
                <input
                    type="text"
                    placeholder="Buscar serviço..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-zinc-800/50 border border-zinc-700/50 rounded-lg pl-10 pr-4 py-2 text-zinc-300 focus:outline-none focus:border-blue-500/50 transition-colors"
                />
            </div>

            <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left table-fixed">
                        <thead className="bg-zinc-900/50 text-zinc-400 text-sm sticky top-0 z-10 backdrop-blur-sm">
                            <tr>
                                <th className="p-4 font-medium w-1/4">Nome</th>
                                <th className="p-4 font-medium w-1/3">Display Name</th>
                                <th className="p-4 font-medium w-32">Status</th>
                                <th className="p-4 font-medium w-40">Tipo de Início</th>
                                <th className="p-4 font-medium text-right w-40">Ações</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-700/50">
                            {filteredServices.map((svc: any) => (
                                <tr key={svc.Name} className="hover:bg-zinc-700/20 transition-colors group">
                                    <td className="p-4 text-white font-medium truncate" title={svc.Name}>
                                        {svc.Name}
                                    </td>
                                    <td className="p-4 text-zinc-300 truncate" title={svc.DisplayName}>
                                        {svc.DisplayName}
                                    </td>
                                    <td className="p-4">
                                        <span className={`px-2 py-1 rounded text-xs font-medium inline-block w-full text-center ${(svc.Status === 'Running' || svc.Status === 4 || svc.Status === '4')
                                            ? 'bg-green-500/20 text-green-400'
                                            : (svc.Status === 'Paused' || svc.Status === 7 || svc.Status === '7')
                                                ? 'bg-yellow-500/20 text-yellow-400'
                                                : 'bg-zinc-700/50 text-zinc-400'
                                            }`}>
                                            {translateStatus(svc.Status)}
                                        </span>
                                    </td>
                                    <td className="p-4 text-zinc-400 text-sm truncate relative group/startup">
                                        {editingStartup === svc.Name ? (
                                            <select
                                                className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500 w-full"
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
                                                className="flex items-center justify-between cursor-pointer hover:text-white"
                                                onClick={() => setEditingStartup(svc.Name)}
                                                title="Clique para alterar"
                                            >
                                                <span>{translateStartType(svc.StartType)}</span>
                                                <Settings size={12} className="opacity-0 group-hover/startup:opacity-100 transition-opacity" />
                                            </div>
                                        )}
                                    </td>
                                    <td className="p-4 text-right">
                                        <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                            {(svc.Status === 'Stopped' || svc.Status === 1 || svc.Status === '1') ? (
                                                <button
                                                    onClick={() => handleServiceAction(svc.Name, 'start')}
                                                    className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-green-400 rounded border border-zinc-700/50 transition-colors"
                                                    title="Iniciar"
                                                >
                                                    <Play size={16} />
                                                </button>
                                            ) : (
                                                <>
                                                    <button
                                                        onClick={() => handleServiceAction(svc.Name, 'stop')}
                                                        className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-red-400 rounded border border-zinc-700/50 transition-colors"
                                                        title="Parar"
                                                    >
                                                        <Square size={16} />
                                                    </button>
                                                    {(svc.CanPauseAndContinue || svc.Status === 'Running' || svc.Status === 4) && (
                                                        <button
                                                            onClick={() => handleServiceAction(svc.Name, 'pause')}
                                                            className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-yellow-400 rounded border border-zinc-700/50 transition-colors"
                                                            title="Pausar"
                                                        >
                                                            <Pause size={16} />
                                                        </button>
                                                    )}
                                                </>
                                            )}
                                            <button
                                                onClick={() => handleServiceAction(svc.Name, 'restart')}
                                                className="p-1.5 hover:bg-blue-500/20 text-blue-400 rounded transition-colors"
                                                title="Reiniciar"
                                            >
                                                <RotateCw size={16} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};
