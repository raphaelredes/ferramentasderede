import { useEffect, useState, useCallback } from 'react';
import { API_BASE } from '../config/api';
import type { NetworkConfig } from '../pages/Settings';

/**
 * Loads the configured `networks` list from /settings.
 * Returns only enabled entries — useful for source_ip selectors in
 * Ping / Traceroute / Discovery in multi-VLAN environments.
 */
export function useNetworks() {
    const [networks, setNetworks] = useState<NetworkConfig[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_BASE}/settings`);
            if (!res.ok) return;
            const data = await res.json();
            const list: NetworkConfig[] = Array.isArray(data?.networks) ? data.networks : [];
            setNetworks(list.filter(n => n.enabled));
        } catch (e) {
            console.error('useNetworks: falha ao carregar', e);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    return { networks, isLoading, refresh };
}
