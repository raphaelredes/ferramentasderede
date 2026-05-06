import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { useToast } from './ToastContext';
import { API_BASE } from '../config/api';

interface ScannedHost {
    ip: string;
    hostname: string;
    mac: string;
    vendor: string;
    status: 'online' | 'offline';
}

interface ToolState {
    isRunning: boolean;
    output: string[];
    target: string;
    isOffline?: boolean;
}

interface ScanSession {
    id: string;
    cidr: string;
    results: ScannedHost[];
    status: string;
    progress: number;
    isRunning: boolean;
    availableRanges?: string[];
    availableCount?: number;
    mode?: 'quick' | 'full';
    sourceIp?: string;  // NIC source for the discovery scan (multi-VLAN)
}

interface ToolsContextType {
    // Independent States
    pingState: ToolState;
    traceState: ToolState;
    scanSessions: ScanSession[];
    activeSessionId: string | null;
    pendingAction: { type: 'ping' | 'traceroute'; target: string; id: string } | null;
    processedActionIds: Set<string>;
    markActionAsProcessed: (id: string) => void;

    // Actions
    setPingTarget: (target: string) => void;
    setTraceTarget: (target: string) => void;
    setPendingAction: (action: { type: 'ping' | 'traceroute'; target: string; id: string } | null) => void;

    createScanSession: (cidr: string, mode?: 'quick' | 'full') => string;
    closeScanSession: (id: string) => void;
    updateScanSession: (id: string, updates: Partial<ScanSession>) => void;
    setActiveSessionId: (id: string | null) => void;

    runPing: (target: string, sourceIp?: string) => Promise<void>;
    runTraceroute: (target: string, sourceIp?: string) => Promise<void>;
    runScanSession: (sessionId: string) => Promise<void>;

    stopTool: (tool: 'ping' | 'traceroute' | 'scanner', sessionId?: string) => void;
    clearToolOutput: (tool: 'ping' | 'traceroute') => void;
    isRunning: boolean;

    // Completion State
    completedTools: Set<string>;
    markToolAsCompleted: (tool: string) => void;
    clearCompletedTool: (tool: string) => void;
}

const ToolsContext = createContext<ToolsContextType | undefined>(undefined);

export const ToolsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Independent States
    const [pingState, setPingState] = useState<ToolState>({ isRunning: false, output: [], target: '8.8.8.8', isOffline: false });
    const [traceState, setTraceState] = useState<ToolState>({ isRunning: false, output: [], target: '8.8.8.8' });

    // Scanner State (Multi-Session)
    const [scanSessions, setScanSessions] = useState<ScanSession[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

    // Pending Action State (for auto-run from Dashboard)
    const [pendingAction, setPendingAction] = useState<{ type: 'ping' | 'traceroute'; target: string; id: string } | null>(null);
    const [processedActionIds, setProcessedActionIds] = useState<Set<string>>(new Set());

    const markActionAsProcessed = useCallback((id: string) => {
        setProcessedActionIds(prev => {
            const newSet = new Set(prev);
            newSet.add(id);
            return newSet;
        });
    }, []);

    // Completion State
    const [completedTools, setCompletedTools] = useState<Set<string>>(new Set());

    const markToolAsCompleted = useCallback((tool: string) => {
        setCompletedTools(prev => {
            const newSet = new Set(prev);
            newSet.add(tool);
            return newSet;
        });
    }, []);

    const clearCompletedTool = useCallback((tool: string) => {
        setCompletedTools(prev => {
            const newSet = new Set(prev);
            newSet.delete(tool);
            return newSet;
        });
    }, []);

    const isRunning = pingState.isRunning || traceState.isRunning || scanSessions.some(s => s.isRunning);

    // Abort Controllers (mapped by tool name or session ID)
    const abortControllers = useRef<{ [key: string]: AbortController | null }>({});
    const { showToast } = useToast();

    const setPingTarget = (target: string) => setPingState(prev => ({ ...prev, target }));
    const setTraceTarget = (target: string) => setTraceState(prev => ({ ...prev, target }));

    // Session Actions
    const createScanSession = useCallback((cidr: string, mode: 'quick' | 'full' = 'quick') => {
        const newSession: ScanSession = {
            id: crypto.randomUUID(),
            cidr: cidr,
            results: [],
            status: 'Pronto',
            progress: 0,
            isRunning: false,
            mode: mode
        };
        setScanSessions(prev => [...prev, newSession]);
        setActiveSessionId(newSession.id);
        return newSession.id;
    }, []);

    const closeScanSession = useCallback((id: string) => {
        // Abort if running
        if (abortControllers.current[`scanner_${id}`]) {
            abortControllers.current[`scanner_${id}`]?.abort();
            abortControllers.current[`scanner_${id}`] = null;
        }

        setScanSessions(prev => {
            const newSessions = prev.filter(s => s.id !== id);
            // If we closed the active one, switch to another
            if (activeSessionId === id) {
                // This side-effect inside setState is safe for the next render but we need to set activeSessionId separately
                // However, we can't easily do that here. 
                // Better logic: calculate new active ID outside or use an effect. 
                // For simplicity, we'll handle active ID update in the component or here if possible.
                // Actually, let's just let the component handle the "if empty create new" logic, 
                // or handle it here.
            }
            return newSessions;
        });

        // We need to update activeSessionId if the current one was closed
        if (activeSessionId === id) {
            // We can't access the *new* sessions here easily without double-state logic.
            // Let's just set it to null and let the UI pick the last one or the component handle it.
            setActiveSessionId(null);
        }
    }, [activeSessionId]);

    const updateScanSession = useCallback((id: string, updates: Partial<ScanSession>) => {
        setScanSessions(prev => prev.map(s => s.id === id ? { ...s, ...updates } : s));
    }, []);

    // Ping Statistics Ref
    const pingStatsRef = useRef({
        sent: 0,
        received: 0,
        times: [] as number[],
        consecutiveFailures: 0,
        consecutiveSuccess: 0,
        isOffline: false
    });

    const stopTool = useCallback((tool: 'ping' | 'traceroute' | 'scanner', sessionId?: string) => {
        const key = tool === 'scanner' && sessionId ? `scanner_${sessionId}` : tool;

        if (abortControllers.current[key]) {
            abortControllers.current[key]?.abort();
            abortControllers.current[key] = null;
        }

        // Call backend to stop command
        fetch(`${API_BASE}/tools/stop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: key })
        }).catch(console.error);

        if (tool === 'ping') {
            // Calculate and display stats
            const { sent, received, times } = pingStatsRef.current;
            const lost = sent - received;
            const lossPercent = sent > 0 ? Math.round((lost / sent) * 100) : 0;

            let min = 0, max = 0, avg = 0;
            if (times.length > 0) {
                min = Math.min(...times);
                max = Math.max(...times);
                avg = Math.round(times.reduce((a, b) => a + b, 0) / times.length);
            }

            const summary = [
                '\n',
                `Estatísticas do Ping para ${pingState.target}:`,
                `    Pacotes: Enviados = ${sent}, Recebidos = ${received}, Perdidos = ${lost} (${lossPercent}% de perda),`,
                'Aproximar um número redondo de vezes em milissegundos:',
                `    Mínimo = ${min}ms, Máximo = ${max}ms, Média = ${avg}ms`,
                '\n[Cancelado pelo usuário]'
            ].join('\n');

            setPingState(prev => ({ ...prev, isRunning: false, output: [...prev.output, summary] }));
        }
        if (tool === 'traceroute') setTraceState(prev => ({ ...prev, isRunning: false, output: [...prev.output, '\n[Cancelado pelo usuário]'] }));
        if (tool === 'scanner' && sessionId) {
            updateScanSession(sessionId, { isRunning: false, status: 'Cancelado pelo usuário.' });
        }
    }, [pingState.target, updateScanSession]);

    const clearToolOutput = useCallback((tool: 'ping' | 'traceroute') => {
        if (tool === 'ping') setPingState(prev => ({ ...prev, output: [], isOffline: false }));
        if (tool === 'traceroute') setTraceState(prev => ({ ...prev, output: [] }));
    }, []);

    const runPing = useCallback(async (target: string, sourceIp?: string) => {
        if (pingState.isRunning) return;

        setPingState(prev => ({ ...prev, isRunning: true, output: [], target, isOffline: false }));
        pingStatsRef.current = { sent: 0, received: 0, times: [], consecutiveFailures: 0, consecutiveSuccess: 0, isOffline: false }; // Reset stats
        abortControllers.current['ping'] = new AbortController();

        try {
            const response = await fetch(`${API_BASE}/tools/ping`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, task_id: 'ping', source_ip: sourceIp }),
                signal: abortControllers.current['ping'].signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);

                // Parse output for stats
                const lines = text.split('\n');
                for (const line of lines) {
                    if (!line.trim()) continue;

                    let isSuccess = false;
                    let isFailure = false;

                    // Increment sent for every reply or timeout attempt (simplified)
                    if (line.includes('Resposta de') || line.includes('Esgotado o tempo') || line.includes('Reply from') || line.includes('Request timed out') || line.includes('Host de destino inacessível') || line.includes('Destination host unreachable')) {
                        pingStatsRef.current.sent++;
                    }

                    if (line.includes('tempo=') || line.includes('time=')) {
                        pingStatsRef.current.received++;
                        isSuccess = true;
                        // Extract time
                        const match = line.match(/(?:tempo|time)[=<](\d+)ms/);
                        if (match && match[1]) {
                            pingStatsRef.current.times.push(parseInt(match[1]));
                        }
                    } else if (line.includes('Esgotado o tempo') || line.includes('Request timed out') || line.includes('Host de destino inacessível') || line.includes('Destination host unreachable')) {
                        isFailure = true;
                    }

                    // Smart Monitoring Logic
                    if (isSuccess) {
                        pingStatsRef.current.consecutiveSuccess++;
                        pingStatsRef.current.consecutiveFailures = 0;

                        // Recovery Check
                        if (pingStatsRef.current.isOffline && pingStatsRef.current.consecutiveSuccess >= 10) {
                            // Host recovered!
                            showToast(`Conexão com ${target} reestabelecida!`, 'success');

                            // Reset stats as if new test
                            pingStatsRef.current = {
                                sent: 1, // Count this current success
                                received: 1,
                                times: pingStatsRef.current.times.slice(-1), // Keep last time
                                consecutiveFailures: 0,
                                consecutiveSuccess: 1,
                                isOffline: false
                            };

                            // Clear output and reset offline state
                            setPingState(prev => ({
                                ...prev,
                                ...prev,
                                isOffline: false,
                                output: [`[SISTEMA] Conexão reestabelecida. Reiniciando estatísticas...\n${line}`]
                            }));
                            continue; // Skip normal output update for this line to avoid duplication
                        }
                    } else if (isFailure) {
                        pingStatsRef.current.consecutiveFailures++;
                        pingStatsRef.current.consecutiveSuccess = 0;
                    }

                    // Offline Check
                    const lost = pingStatsRef.current.sent - pingStatsRef.current.received;
                    const lossPercent = pingStatsRef.current.sent > 0 ? (lost / pingStatsRef.current.sent) * 100 : 0;

                    if (!pingStatsRef.current.isOffline && lost > 50 && lossPercent > 60) {
                        pingStatsRef.current.isOffline = true;
                        setPingState(prev => ({
                            ...prev,
                            isOffline: true,
                            output: ["\n⚠️ HOST PROVAVELMENTE OFFLINE...\n\nAguardando recuperação de conexão (10 respostas consecutivas)..."]
                        }));
                        // Don't add the current line to output if we just switched to offline mode
                        continue;
                    }
                }

                // Only update output if NOT offline (or if we just recovered)
                // We use a functional update to access the *current* state value inside the loop
                setPingState(prev => {
                    if (prev.isOffline) return prev; // Don't append lines while offline
                    return { ...prev, output: [...prev.output, text] };
                });
            }
            markToolAsCompleted('ping');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('Ping error:', error);
                setPingState(prev => ({ ...prev, output: [...prev.output, `\nErro: ${error.message}`] }));
            }
        } finally {
            setPingState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['ping'] = null;
        }
    }, [pingState.isRunning, showToast]);

    const runTraceroute = useCallback(async (target: string, sourceIp?: string) => {
        if (traceState.isRunning) return;

        setTraceState(prev => ({ ...prev, isRunning: true, output: [], target }));
        abortControllers.current['traceroute'] = new AbortController();

        try {
            const response = await fetch(`${API_BASE}/tools/traceroute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, task_id: 'traceroute', source_ip: sourceIp }),
                signal: abortControllers.current['traceroute'].signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                setTraceState(prev => ({ ...prev, output: [...prev.output, text] }));
            }
            markToolAsCompleted('traceroute');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('Traceroute error:', error);
                setTraceState(prev => ({ ...prev, output: [...prev.output, `\nErro: ${error.message}`] }));
            }
        } finally {
            setTraceState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['traceroute'] = null;
        }
    }, [traceState.isRunning]);

    // Ref to access latest sessions in async functions
    const sessionsRef = useRef<ScanSession[]>([]);
    useEffect(() => {
        sessionsRef.current = scanSessions;
    }, [scanSessions]);

    const runScanSession = useCallback(async (sessionId: string) => {
        const session = sessionsRef.current.find(s => s.id === sessionId);
        if (!session || !session.cidr) return;

        if (session.isRunning) {
            // Stop logic
            stopTool('scanner', sessionId);
            return;
        }

        const abortController = new AbortController();
        abortControllers.current[`scanner_${sessionId}`] = abortController;

        updateScanSession(sessionId, {
            isRunning: true,
            results: [],
            progress: 0,
            status: 'Iniciando...',
            availableRanges: [],
            availableCount: 0
        });

        try {
            // Fetch settings
            let timeout = 200;
            let concurrency = 50;
            try {
                const settingsRes = await fetch(`${API_BASE}/settings`);
                const settingsData = await settingsRes.json();
                if (settingsData.scanner) {
                    timeout = settingsData.scanner.ping_timeout || 200;
                    concurrency = settingsData.scanner.concurrency || 50;
                }
            } catch (e) { console.warn("Settings fetch failed", e); }

            const response = await fetch(`${API_BASE}/network/discovery`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cidr: session.cidr,
                    task_id: `scanner_${sessionId}`,
                    timeout,
                    max_workers: concurrency,
                    source_ip: session.sourceIp,
                }),
                signal: abortController.signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);

                        if (data.status === 'progress') {
                            updateScanSession(sessionId, { status: data.message, progress: data.progress });
                        } else if (data.status === 'completed') {
                            updateScanSession(sessionId, {
                                status: data.message,
                                progress: 100,
                                isRunning: false,
                                availableRanges: data.available_ranges,
                                availableCount: data.available_count
                            });
                        } else if (data.error) {
                            updateScanSession(sessionId, { status: `Erro: ${data.error}`, isRunning: false });
                        } else if (data.ip) {
                            // It's a host
                            setScanSessions(prev => prev.map(s => {
                                if (s.id !== sessionId) return s;
                                if (s.results.some(h => h.ip === data.ip)) return s;
                                return { ...s, results: [...s.results, data] };
                            }));
                        }
                    } catch (e) {
                        console.error("JSON parse error", e);
                    }
                }
            }
            markToolAsCompleted('scanner');
        } catch (err: any) {
            if (err.name !== 'AbortError') {
                updateScanSession(sessionId, { status: `Falha: ${err.message}`, isRunning: false });
            }
        } finally {
            // Ensure running is false if not already
            setScanSessions(prev => prev.map(s => s.id === sessionId && s.isRunning ? { ...s, isRunning: false } : s));
            abortControllers.current[`scanner_${sessionId}`] = null;
        }
    }, [updateScanSession, stopTool]);

    return (
        <ToolsContext.Provider value={{
            pingState,
            traceState,
            scanSessions,
            activeSessionId,
            setPingTarget,
            setTraceTarget,
            createScanSession,
            closeScanSession,
            updateScanSession,
            setActiveSessionId,
            runPing,
            runTraceroute,
            runScanSession,
            stopTool,
            clearToolOutput,
            isRunning,
            pendingAction,
            setPendingAction,
            processedActionIds,
            markActionAsProcessed,
            completedTools,
            markToolAsCompleted,
            clearCompletedTool
        }}>
            {children}
        </ToolsContext.Provider>
    );
};

export const useTools = () => {
    const context = useContext(ToolsContext);
    if (context === undefined) {
        throw new Error('useTools must be used within a ToolsProvider');
    }
    return context;
};
