import { useState, useCallback } from 'react';
import { Host, HostStatistics } from '../types';

export function useHosts() {
    const [hosts, setHosts] = useState<Host[]>([]);
    const [loading, setLoading] = useState(true);
    const [backendError, setBackendError] = useState<string | null>(null);
    const [hostStatus, setHostStatus] = useState<Record<string, boolean>>({});
    const [hostStats, setHostStats] = useState<Record<string, HostStatistics>>({});

    const fetchHosts = useCallback(async (sortBy: string, hostOrder: string[]) => {
        setLoading(true);
        setBackendError(null);
        try {
            const response = await fetch('http://localhost:8000/hosts');
            if (!response.ok) throw new Error('Falha ao carregar hosts');
            const data = await response.json();

            let sortedData = data;
            if (sortBy === 'manual' && hostOrder.length > 0) {
                sortedData = [...data].sort((a: Host, b: Host) => {
                    const indexA = hostOrder.indexOf(a.address);
                    const indexB = hostOrder.indexOf(b.address);
                    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                    if (indexA !== -1) return -1;
                    if (indexB !== -1) return 1;
                    return 0;
                });
            }

            setHosts(sortedData);
        } catch (error: unknown) {
            console.error('Erro ao buscar hosts:', error);
            setBackendError(error instanceof Error ? error.message : String(error));
        } finally {
            setLoading(false);
        }
    }, []);
    const updateStatuses = useCallback(async () => {
        try {
            const response = await fetch('http://localhost:8000/network/monitor');
            if (response.ok) {
                const data = await response.json() as Record<string, HostStatistics>;
                const newStatus: Record<string, boolean> = {};
                const newStats: Record<string, HostStatistics> = {};

                let hostsUpdated = false;

                // Use functional update to access current hosts without adding dependency
                setHosts(prevHosts => {
                    const newHosts = [...prevHosts];
                    let hasChanges = false;

                    Object.entries(data).forEach(([address, item]) => {
                        newStatus[address] = item.online;
                        newStats[address] = {
                            online: item.online,
                            latency: item.latency,
                            average_latency: item.average_latency,
                            packet_loss: item.packet_loss,
                            packet_loss_pct: item.packet_loss_pct,
                            total_packets: item.total_packets,
                            calibration_done: item.calibration_done,
                            history: item.history,
                            ports_status: item.ports_status,
                            hostname: item.hostname,
                            domain: item.domain
                        };

                        // Check if hostname/domain changed and update host list
                        const hostIndex = newHosts.findIndex(h => h.address === address);
                        if (hostIndex !== -1) {
                            const host = newHosts[hostIndex];
                            if ((item.hostname && host.hostname !== item.hostname) ||
                                (item.domain && host.domain !== item.domain)) {
                                newHosts[hostIndex] = {
                                    ...host,
                                    hostname: item.hostname || host.hostname,
                                    domain: item.domain || host.domain
                                };
                                hasChanges = true;
                            }
                        }
                    });

                    return hasChanges ? newHosts : prevHosts;
                });

                setHostStatus(newStatus);
                setHostStats(newStats);
                return data; // Return data for dynamic polling
            }
            return null;
        } catch (error) {
            console.error('Error fetching monitor data:', error);
            return null;
        }
    }, []);

    return {
        hosts,
        setHosts,
        loading,
        backendError,
        hostStatus,
        hostStats,
        fetchHosts,
        updateStatuses
    };
}
