import { Plus } from 'lucide-react';

interface DashboardHeaderProps {
    onAddHost: () => void;
    totalHosts?: number;
    onlineHosts?: number;
}

export function DashboardHeader({ onAddHost, totalHosts, onlineHosts }: DashboardHeaderProps) {
    return (
        <div className="flex justify-between items-center mb-8">
            <div>
                <h1 className="text-3xl font-bold text-white mb-2">Painel de Monitoramento</h1>
                <div className="flex items-center gap-4 text-zinc-400">
                    <p>Visão geral do status da rede e dispositivos</p>
                    {totalHosts !== undefined && (
                        <>
                            <span className="w-1 h-1 bg-zinc-600 rounded-full"></span>
                            <span className="text-sm">
                                {totalHosts} hosts ({onlineHosts} online)
                            </span>
                        </>
                    )}
                </div>
            </div>
            <div className="flex items-center gap-3">
                <button
                    onClick={onAddHost}
                    className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 rounded-lg transition-colors font-medium"
                >
                    <Plus size={20} />
                    Adicionar Host
                </button>
            </div>
        </div>
    );
}
