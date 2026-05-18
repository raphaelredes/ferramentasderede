import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useToast } from './ToastContext';
import { Host, HostStatistics } from '../types';
import { API_BASE } from '../config/api';

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
    const pollingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const isFirstLoad = useRef(true);
    // Mounted guard so awaited setState calls bail out after unmount. The
    // previous version created an AbortController in the effect but never
    // plumbed `signal` into the actual fetch() calls — so cleanup did nothing
    // about in-flight requests. This ref is set false in the effect cleanup
    // and read after every `await` here.
    const isMountedRef = useRef(true);
    // AbortController per fetchHosts call so cleanup can actually cancel a
    // request in flight (saves network + avoids racing against the next poll).
    const inflightAbortRef = useRef<AbortController | null>(null);

    const fetchHosts = useCallback(async (silent = false) => {
        if (!silent) setIsLoading(true);
        // Cancel any prior in-flight fetch (e.g. operator hits Refresh while
        // the previous /hosts request is still pending).
        inflightAbortRef.current?.abort();
        const controller = new AbortController();
        inflightAbortRef.current = controller;
        try {
            // Fetch hosts and monitor stats in parallel
            const [hostsResponse, monitorResponse] = await Promise.all([
                fetch(`${API_BASE}/hosts`, { signal: controller.signal }),
                fetch(`${API_BASE}/network/monitor`, { signal: controller.signal })
            ]);

            if (!hostsResponse.ok) throw new Error('Failed to fetch hosts');
            if (!isMountedRef.current) return false;

            const hostsData: Host[] = await hostsResponse.json();
            const monitorData: Record<string, HostStatistics> = monitorResponse.ok ? await monitorResponse.json() : {};
            if (!isMountedRef.current) return false;

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

                // IP sort. Backend can return null `ip`/`address` for hosts
                // discovered without a resolved address yet — fall back to
                // 0.0.0.0 so split('.') doesn't crash (same family as the
                // null.localeCompare crash already fixed elsewhere).
                const ipA = (a.ip ?? a.address ?? '0.0.0.0').split('.').map(Number);
                const ipB = (b.ip ?? b.address ?? '0.0.0.0').split('.').map(Number);
                for (let i = 0; i < 4; i++) {
                    const av = Number.isFinite(ipA[i]) ? ipA[i] : 0;
                    const bv = Number.isFinite(ipB[i]) ? ipB[i] : 0;
                    if (av < bv) return -1;
                    if (av > bv) return 1;
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

        } catch (error: unknown) {
            // AbortError on unmount / new fetch — not a real failure, don't toast.
            if ((error as { name?: string })?.name === 'AbortError') {
                return false;
            }
            console.error('Error fetching hosts:', error);
            if (!silent && isMountedRef.current) showToast('Erro ao carregar hosts', 'error');
            return false; // Failure
        } finally {
            if (inflightAbortRef.current === controller) {
                inflightAbortRef.current = null;
            }
            if (!silent && isMountedRef.current) setIsLoading(false);
            isFirstLoad.current = false;
        }
    }, [showToast]);

    // Initial load and polling with exponential backoff on failure.
    // Healthy state: poll every 2s. On failure: 2s -> 4s -> 8s -> ... cap 30s.
    useEffect(() => {
        isMountedRef.current = true;
        let retryCount = 0;
        const maxInitialRetries = 20;
        const baseInterval = 2000;
        const maxInterval = 30000;
        let currentInterval = baseInterval;
        let warnedDisconnected = false;

        const scheduleNext = () => {
            if (!isMountedRef.current) return;
            pollingTimeoutRef.current = setTimeout(poll, currentInterval);
        };

        const poll = async () => {
            if (!isMountedRef.current) return;
            const success = await fetchHosts(true);
            if (!isMountedRef.current) return;
            if (success) {
                if (warnedDisconnected) {
                    showToast('Conexão com o servidor restaurada.', 'success');
                    warnedDisconnected = false;
                }
                currentInterval = baseInterval;
            } else {
                currentInterval = Math.min(currentInterval * 2, maxInterval);
                if (!warnedDisconnected && currentInterval >= maxInterval) {
                    showToast('Servidor não responde. Tentando reconectar...', 'error');
                    warnedDisconnected = true;
                }
            }
            scheduleNext();
        };

        const initialFetch = async () => {
            while (retryCount < maxInitialRetries && isMountedRef.current) {
                const success = await fetchHosts(retryCount > 0);
                if (success) {
                    if (isMountedRef.current) scheduleNext();
                    return;
                }
                retryCount++;
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            if (isMountedRef.current && retryCount >= maxInitialRetries) {
                showToast('Não foi possível conectar ao servidor local.', 'error');
            }
        };

        initialFetch();

        return () => {
            isMountedRef.current = false;
            // Cancel the request currently in flight (if any) so the awaited
            // setState calls bail via the AbortError catch branch.
            inflightAbortRef.current?.abort();
            if (pollingTimeoutRef.current) {
                clearTimeout(pollingTimeoutRef.current);
                pollingTimeoutRef.current = null;
            }
        };
    }, [fetchHosts, showToast]);

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
