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
                // Prefer the resolved IPv4 over `address` — hosts cadastrados por
                // nome têm `address` = hostname, e splitting "srv01.acme.local"
                // by "." gives [NaN, NaN, ...] so the NaN comparisons (always
                // false) leave their relative order undefined. Fall back to
                // 0.0.0.0 so hostname-only hosts cluster at the top instead of
                // shuffling randomly between renders.
                const ipA = (a.ip ?? aAddr ?? '0.0.0.0').split('.').map(Number);
                const ipB = (b.ip ?? bAddr ?? '0.0.0.0').split('.').map(Number);
                for (let i = 0; i < 4; i++) {
                    const av = Number.isFinite(ipA[i]) ? ipA[i] : 0;
                    const bv = Number.isFinite(ipB[i]) ? ipB[i] : 0;
                    if (av < bv) return -1;
                    if (av > bv) return 1;
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
