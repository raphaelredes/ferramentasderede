import { HelpButton } from '../HelpButton';
import type { NetworkConfig } from '../../pages/Settings';

interface Props {
    uniqueGroups: string[];
    activeGroupTab: string;
    onGroupTabChange: (tab: string) => void;
    networks: NetworkConfig[];
    activeNetworkTab: string;
    onNetworkTabChange: (tab: string) => void;
}

/**
 * Two-row filter strip that lives just under the dashboard header:
 *   1. Group tabs (always rendered: Todos / Sem Grupo / one per group)
 *   2. Network tabs (rendered only when there are configured networks)
 *
 * Pure presentational — all state lives in Dashboard.tsx so the tabs
 * stay in sync with the host filtering logic.
 */
export function GroupNetworkTabs({
    uniqueGroups,
    activeGroupTab,
    onGroupTabChange,
    networks,
    activeNetworkTab,
    onNetworkTabChange,
}: Props) {
    const groupTabClass = (active: boolean) =>
        `px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap ${
            active ? 'text-blue-400 border-b-2 border-blue-400' : 'text-zinc-400 hover:text-white'
        }`;

    const netTabClass = (active: boolean) =>
        `px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap ${
            active
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                : 'text-zinc-400 hover:text-white border border-transparent'
        }`;

    return (
        <>
            <div className="flex gap-2 border-b border-zinc-800 mb-4 overflow-x-auto custom-scrollbar pb-2">
                <button
                    onClick={() => onGroupTabChange('all')}
                    className={groupTabClass(activeGroupTab === 'all')}
                >
                    Todos
                </button>
                <button
                    onClick={() => onGroupTabChange('ungrouped')}
                    className={groupTabClass(activeGroupTab === 'ungrouped')}
                >
                    Sem Grupo
                </button>
                {uniqueGroups.map(group => (
                    <button
                        key={group}
                        onClick={() => onGroupTabChange(group)}
                        className={groupTabClass(activeGroupTab === group)}
                    >
                        {group}
                    </button>
                ))}
                <div className="ml-auto flex items-center">
                    <HelpButton
                        title="Grupos e Filtros"
                        description="Use as abas para filtrar hosts por grupo. 'Sem Grupo' mostra hosts que ainda não foram categorizados."
                    />
                </div>
            </div>

            {networks.length > 0 && (
                <div className="flex gap-2 border-b border-zinc-800 mb-4 overflow-x-auto custom-scrollbar pb-2">
                    <span className="px-2 py-2 text-xs font-medium text-zinc-500 whitespace-nowrap">Rede:</span>
                    <button
                        onClick={() => onNetworkTabChange('all')}
                        className={netTabClass(activeNetworkTab === 'all')}
                    >
                        Todas
                    </button>
                    <button
                        onClick={() => onNetworkTabChange('unassigned')}
                        className={netTabClass(activeNetworkTab === 'unassigned')}
                    >
                        Sem rede
                    </button>
                    {networks.map(net => (
                        <button
                            key={net.id}
                            onClick={() => onNetworkTabChange(net.id)}
                            title={net.cidr}
                            className={netTabClass(activeNetworkTab === net.id)}
                        >
                            {net.name || net.cidr}
                        </button>
                    ))}
                    <div className="ml-auto flex items-center">
                        <HelpButton
                            title="Filtro por Rede / VLAN"
                            description="Filtra hosts pela rede cadastrada em Configurações. 'Sem rede' mostra hosts cujo IP não está em nenhuma rede cadastrada."
                        />
                    </div>
                </div>
            )}
        </>
    );
}
