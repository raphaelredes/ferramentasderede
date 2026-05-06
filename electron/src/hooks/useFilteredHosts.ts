import { useMemo } from 'react';
import { Host } from '../types';

export type FilterStatus = 'all' | 'monitored' | 'unmonitored';
export type SortBy = 'name' | 'status' | 'ip' | 'manual';

interface Args {
    hosts: Host[];
    searchTerm: string;
    filterStatus: FilterStatus;
    activeGroupTab: string;       // 'all' | 'ungrouped' | <group name>
    activeNetworkTab: string;     // 'all' | 'unassigned' | <network id>
    sortBy: SortBy;
    hostOrder: string[];          // manual order (addresses)
}

/**
 * Centralizes filter + sort for the dashboard host list.
 *
 * Why a hook: Dashboard.tsx had a 60-line .filter().sort() chain inline
 * with mixed concerns (search / status / group / network / sort) and a
 * couple of null-safety bugs that already bit us once. Memoized to avoid
 * recomputing on every render — only re-runs when inputs actually change.
 */
export function useFilteredHosts({
    hosts,
    searchTerm,
    filterStatus,
    activeGroupTab,
    activeNetworkTab,
    sortBy,
    hostOrder,
}: Args): Host[] {
    return useMemo(() => {
        const search = searchTerm.toLowerCase();

        const filtered = hosts.filter(host => {
            const matchesSearch =
                (host.name || '').toLowerCase().includes(search) ||
                (host.address || '').includes(searchTerm) ||
                (host.hostname && host.hostname.toLowerCase().includes(search));

            const matchesStatus =
                filterStatus === 'all' ? true :
                    filterStatus === 'monitored' ? !!host.monitoring :
                        !host.monitoring;

            const matchesGroup =
                activeGroupTab === 'all' ? true :
                    activeGroupTab === 'ungrouped' ? !host.group :
                        host.group === activeGroupTab;

            const matchesNetwork =
                activeNetworkTab === 'all' ? true :
                    activeNetworkTab === 'unassigned' ? !host.network_id :
                        host.network_id === activeNetworkTab;

            return matchesSearch && matchesStatus && matchesGroup && matchesNetwork;
        });

        return filtered.sort((a, b) => {
            // Defensive: discovery / legacy DBs may emit null name/address.
            const aName = a.name ?? a.hostname ?? a.address ?? '';
            const bName = b.name ?? b.hostname ?? b.address ?? '';
            const aAddr = a.address ?? '';
            const bAddr = b.address ?? '';

            if (sortBy === 'manual') {
                const indexA = hostOrder.indexOf(aAddr);
                const indexB = hostOrder.indexOf(bAddr);
                if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                if (indexA !== -1) return -1;
                if (indexB !== -1) return 1;
                return aName.localeCompare(bName);
            }

            if (sortBy === 'name') return aName.localeCompare(bName);

            if (sortBy === 'ip') {
                const ipA = aAddr.split('.').map(Number);
                const ipB = bAddr.split('.').map(Number);
                for (let i = 0; i < 4; i++) {
                    if (ipA[i] < ipB[i]) return -1;
                    if (ipA[i] > ipB[i]) return 1;
                }
                return 0;
            }

            if (sortBy === 'status') {
                const isOnlineA = a.stats?.online ?? a.last_status ?? false;
                const isOnlineB = b.stats?.online ?? b.last_status ?? false;
                if (isOnlineA && !isOnlineB) return -1;
                if (!isOnlineA && isOnlineB) return 1;
                return 0;
            }

            return 0;
        });
    }, [hosts, searchTerm, filterStatus, activeGroupTab, activeNetworkTab, sortBy, hostOrder]);
}
