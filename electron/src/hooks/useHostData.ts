import { useState, useCallback } from 'react';
import { SystemInfo, Service, LogEntry, Session } from '../types';

export function useHostData(ip: string | undefined) {
    const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
    const [services, setServices] = useState<Service[]>([]);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [teamViewerId, setTeamViewerId] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const saveToCache = useCallback((newData: Partial<{
        systemInfo: SystemInfo;
        services: Service[];
        logs: LogEntry[];
        sessions: Session[];
        teamViewerId: string;
    }>) => {
        if (!ip) return;
        const cacheKey = `host_details_${ip}`;
        const existing = localStorage.getItem(cacheKey);
        let data = existing ? JSON.parse(existing) : {};

        data = { ...data, ...newData, timestamp: new Date().toISOString() };
        localStorage.setItem(cacheKey, JSON.stringify(data));
        setLastUpdated(new Date());
    }, [ip]);

    const loadFromCache = useCallback(() => {
        if (!ip) return false;
        const cacheKey = `host_details_${ip}`;
        const cached = localStorage.getItem(cacheKey);

        if (cached) {
            try {
                const data = JSON.parse(cached);
                if (data.systemInfo) setSystemInfo(data.systemInfo);
                if (data.services) setServices(data.services);
                if (data.logs) setLogs(data.logs);
                if (data.sessions) setSessions(data.sessions);
                if (data.teamViewerId) setTeamViewerId(data.teamViewerId);
                if (data.timestamp) setLastUpdated(new Date(data.timestamp));
                return !!data.systemInfo;
            } catch (e) {
                console.error("Failed to load cache", e);
            }
        }
        return false;
    }, [ip]);

    const fetchData = async (
        activeTab: string | string[],
        user: string,
        pass: string,
        tempAuth: boolean = false
    ) => {
        if (!ip) return;
        setLoading(true);
        setError(null);

        const tabs = Array.isArray(activeTab) ? activeTab : [activeTab];

        const headers: HeadersInit = {
            'Content-Type': 'application/json'
        };
        if (tempAuth) {
            headers['X-Temp-Auth'] = 'true';
        }

        try {
            if (tabs.includes('info')) {
                const resInfo = await fetch('http://127.0.0.1:8000/system/info', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ target_ip: ip, username: user, password: pass })
                });

                if (!resInfo.ok) {
                    const err = await resInfo.json().catch(() => ({}));
                    if (resInfo.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                        throw new Error("TRUSTED_HOSTS_REQUIRED");
                    }
                    throw new Error(err.detail || 'Falha ao obter informações do sistema');
                }

                const dataInfo = await resInfo.json();
                setSystemInfo(dataInfo);
                saveToCache({ systemInfo: dataInfo });

                // Fetch TeamViewer ID (streamed)
                const resTv = await fetch('http://127.0.0.1:8000/system/teamviewer', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ target_ip: ip, username: user, password: pass })
                });

                if (resTv.ok && resTv.body) {
                    const reader = resTv.body.getReader();
                    const { value } = await reader.read();
                    if (value) {
                        const text = new TextDecoder().decode(value);
                        try {
                            const json = JSON.parse(text);
                            if (json.code === "TRUSTED_HOSTS_REQUIRED") {
                                throw new Error("TRUSTED_HOSTS_REQUIRED");
                            }
                            if (json.data) {
                                setTeamViewerId(json.data);
                                saveToCache({ teamViewerId: json.data });
                                fetch(`http://127.0.0.1:8000/hosts/${ip}`, {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ teamviewer_id: json.data })
                                }).catch(() => { });
                            }
                        } catch (e: unknown) {
                            if (e instanceof Error && e.message === "TRUSTED_HOSTS_REQUIRED") throw e;
                        }
                    }
                }
            }

            if (tabs.includes('services')) {
                const res = await fetch('http://127.0.0.1:8000/system/services', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ target_ip: ip, username: user, password: pass })
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                        throw new Error("TRUSTED_HOSTS_REQUIRED");
                    }
                    throw new Error(err.detail || 'Falha ao obter serviços');
                }
                const data = await res.json();
                const servicesList = Array.isArray(data) ? data : [];
                setServices(servicesList);
                saveToCache({ services: servicesList });
            }

            if (tabs.includes('sessions')) {
                const res = await fetch('http://127.0.0.1:8000/system/sessions', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ target_ip: ip, username: user, password: pass })
                });

                if (res.ok && res.body) {
                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const text = decoder.decode(value);
                        if (text.includes("TRUSTED_HOSTS_REQUIRED")) {
                            throw new Error("TRUSTED_HOSTS_REQUIRED");
                        }

                        const lines = text.split('\n');
                        for (const line of lines) {
                            if (!line.trim()) continue;
                            try {
                                const json = JSON.parse(line);
                                if (json.code === "TRUSTED_HOSTS_REQUIRED") {
                                    throw new Error("TRUSTED_HOSTS_REQUIRED");
                                }
                                if (json.data && Array.isArray(json.data)) {
                                    setSessions(json.data);
                                    saveToCache({ sessions: json.data });
                                }
                            } catch (e: unknown) {
                                if (e instanceof Error && e.message === "TRUSTED_HOSTS_REQUIRED") throw e;
                                console.error("Error parsing session line:", line, e);
                            }
                        }
                    }
                } else if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                        throw new Error("TRUSTED_HOSTS_REQUIRED");
                    }
                    throw new Error(err.detail || 'Falha ao obter sessões');
                }
            }

            if (tabs.includes('logs')) {
                const res = await fetch('http://127.0.0.1:8000/system/logs', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ target_ip: ip, username: user, password: pass, log_name: 'System', level: 'Error', count: 20 })
                });

                if (res.ok && res.body) {
                    const reader = res.body.getReader();
                    const newLogs: LogEntry[] = [];
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        const text = new TextDecoder().decode(value);
                        if (text.includes("TRUSTED_HOSTS_REQUIRED")) {
                            throw new Error("TRUSTED_HOSTS_REQUIRED");
                        }
                        const lines = text.split('\n');
                        for (const line of lines) {
                            if (!line) continue;
                            try {
                                const data = JSON.parse(line);
                                if (data.code === "TRUSTED_HOSTS_REQUIRED") {
                                    throw new Error("TRUSTED_HOSTS_REQUIRED");
                                }
                                if (!data.error) newLogs.push(data);
                            } catch (e: unknown) {
                                if (e instanceof Error && e.message === "TRUSTED_HOSTS_REQUIRED") throw e;
                            }
                        }
                        setLogs([...newLogs]);
                    }
                    saveToCache({ logs: newLogs });
                } else if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                        throw new Error("TRUSTED_HOSTS_REQUIRED");
                    }
                    throw new Error(err.detail || 'Falha ao obter logs');
                }
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
            throw err;
        } finally {
            setLoading(false);
        }
    };

    return {
        systemInfo,
        services,
        logs,
        sessions,
        teamViewerId,
        lastUpdated,
        loading,
        error,
        fetchData,
        loadFromCache,
        saveToCache,
        setServices,
        setSessions
    };
}
