import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useToast } from './ToastContext';
import { Host, HostStatistics } from '../types';

interface MonitoringStats {
    total: number;
    online: number;
    offline: number;
    avgLatency: number;
}

interface MonitoringContextType {
    hosts: Host[];
    stats: MonitoringStats;
    isLoading: boolean;
    lastUpdated: Date | null;
    refreshHosts: (silent?: boolean) => Promise<boolean>;
    uniqueGroups: string[];
}

const MonitoringContext = createContext<MonitoringContextType | undefined>(undefined);

export const MonitoringProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [hosts, setHosts] = useState<Host[]>([]);
    const [stats, setStats] = useState<MonitoringStats>({ total: 0, online: 0, offline: 0, avgLatency: 0 });
    const [isLoading, setIsLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const { showToast } = useToast();

    // Refs for polling control
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const isFirstLoad = useRef(true);

    const fetchHosts = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        try {
            // Fetch hosts and monitor stats in parallel
            const [hostsResponse, monitorResponse] = await Promise.all([
                fetch('http://127.0.0.1:8000/hosts'),
                fetch('http://127.0.0.1:8000/network/monitor')
            ]);

            if (!hostsResponse.ok) throw new Error('Failed to fetch hosts');
            // monitorResponse might fail if monitor is not running, but usually it returns empty dict

            const hostsData: Host[] = await hostsResponse.json();
            const monitorData: Record<string, HostStatistics> = monitorResponse.ok ? await monitorResponse.json() : {};

            // Merge stats into hosts
            const mergedHosts = hostsData.map(h => {
                const stats = monitorData[h.address];
                return {
                    ...h,
                    stats: stats || undefined,
                    // If we have real-time stats, use them for status, otherwise fallback to last_status
                    // But we don't overwrite last_status in the object, we just use stats for sorting/display
                };
            });

            // Sort: Online first, then by IP
            const sortedHosts = mergedHosts.sort((a, b) => {
                const isOnlineA = a.stats?.online ?? a.last_status ?? false;
                const isOnlineB = b.stats?.online ?? b.last_status ?? false;

                if (isOnlineA && !isOnlineB) return -1;
                if (!isOnlineA && isOnlineB) return 1;

                // IP sort
                const ipA = (a.ip || a.address).split('.').map(Number);
                const ipB = (b.ip || b.address).split('.').map(Number);
                for (let i = 0; i < 4; i++) {
                    if (ipA[i] < ipB[i]) return -1;
                    if (ipA[i] > ipB[i]) return 1;
                }
                return 0;
            });

            setHosts(sortedHosts);
            setLastUpdated(new Date());

            // Update aggregate stats
            const total = sortedHosts.length;
            const online = sortedHosts.filter(h => h.stats?.online ?? h.last_status).length;
            const offline = total - online;
            const latencies = sortedHosts
                .filter(h => h.stats?.latency !== undefined && h.stats.latency !== null && h.stats.latency > 0)
                .map(h => h.stats!.latency!);

            const avgLatency = latencies.length > 0
                ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
                : 0;

            setStats({ total, online, offline, avgLatency });
            return true; // Success

        } catch (error) {
            console.error('Error fetching hosts:', error);
            if (!silent) showToast('Erro ao carregar hosts', 'error');
            return false; // Failure
        } finally {
            if (!silent) setIsLoading(false);
            isFirstLoad.current = false;
        }
    }, [showToast]);

    // Initial load and polling
    // Initial load and polling
    useEffect(() => {
        let isMounted = true;
        let retryCount = 0;
        const maxRetries = 20; // Try for 20 seconds

        const initialFetch = async () => {
            while (retryCount < maxRetries && isMounted) {
                const success = await fetchHosts(retryCount > 0); // Silent on retries

                if (success) {
                    if (isMounted) {
                        // Start polling only after success
                        pollingIntervalRef.current = setInterval(() => {
                            fetchHosts(true);
                        }, 2000);
                    }
                    return;
                }

                retryCount++;
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            if (isMounted && retryCount >= maxRetries) {
                showToast('Não foi possível conectar ao servidor local.', 'error');
            }
        };

        initialFetch();

        return () => {
            isMounted = false;
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, [fetchHosts]);

    // Derived state: Unique Groups
    const uniqueGroups = Array.from(new Set(hosts.map(h => h.group).filter(Boolean) as string[])).sort();

    return (
        <MonitoringContext.Provider value={{
            hosts,
            stats,
            isLoading,
            lastUpdated,
            refreshHosts: (silent = false) => fetchHosts(silent),
            uniqueGroups
        }}>
            {children}
        </MonitoringContext.Provider>
    );
};

export const useMonitoring = () => {
    const context = useContext(MonitoringContext);
    if (context === undefined) {
        throw new Error('useMonitoring must be used within a MonitoringProvider');
    }
    return context;
};
