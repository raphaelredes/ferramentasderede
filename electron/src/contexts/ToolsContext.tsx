import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { useToast } from './ToastContext';
import { API_BASE } from '../config/api';

interface ScannedHost {
    ip: string;
    hostname: string;
    mac: string;
    vendor: string;
    status: 'online' | 'offline';
    ports?: number[];
    /** Probable device category (Impressora, Câmera IP, Workstation…). */
    device_type?: string;
    /** True when the type is a low-confidence guess (vendor/hostname only). */
    device_type_guess?: boolean;
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
    /** Operator-given label; falls back to cidr in the tab. */
    name?: string;
    /** Pinned tabs survive app restart and can't be closed by accident. */
    pinned?: boolean;
}

// localStorage persistence. Saves layout and discovered hosts so the user
// can see past scans on app reopen or tab switch.
const SCAN_SESSIONS_STORAGE_KEY = 'scanSessions';
const SCAN_SESSIONS_SCHEMA_VERSION = 2;

type PersistedSession = Pick<ScanSession, 'id' | 'cidr' | 'name' | 'pinned' | 'sourceIp' | 'mode' | 'results' | 'availableRanges' | 'availableCount'>;

function loadPersistedSessions(): { sessions: ScanSession[]; activeId: string | null } {
    try {
        const raw = localStorage.getItem(SCAN_SESSIONS_STORAGE_KEY);
        if (!raw) return { sessions: [], activeId: null };
        const parsed = JSON.parse(raw);
        if (!parsed || (parsed.v !== 1 && parsed.v !== 2) || !Array.isArray(parsed.sessions)) {
            return { sessions: [], activeId: null };
        }
        const sessions: ScanSession[] = (parsed.sessions as PersistedSession[])
            .filter(s => s && typeof s.id === 'string')
            .map(s => {
                const res = Array.isArray(s.results) ? s.results : [];
                return {
                    id: s.id,
                    cidr: s.cidr || '',
                    name: s.name,
                    pinned: !!s.pinned,
                    sourceIp: s.sourceIp,
                    mode: s.mode,
                    results: res,
                    status: res.length > 0 ? `Concluído (${res.length} hosts)` : 'Pronto',
                    progress: res.length > 0 ? 100 : 0,
                    isRunning: false,
                    availableRanges: Array.isArray(s.availableRanges) ? s.availableRanges : [],
                    availableCount: s.availableCount,
                };
            });
        const activeId = typeof parsed.activeId === 'string' && sessions.some(s => s.id === parsed.activeId)
            ? parsed.activeId
            : (sessions[0]?.id ?? null);
        return { sessions, activeId };
    } catch (e) {
        console.warn('Failed to parse persisted scan sessions; starting fresh.', e);
        return { sessions: [], activeId: null };
    }
}

function loadToolState(key: string, defaultTarget: string): ToolState {
    try {
        const raw = localStorage.getItem(`tool_state_${key}`);
        if (raw) {
            const parsed = JSON.parse(raw);
            return {
                isRunning: false,
                output: Array.isArray(parsed.output) ? parsed.output : [],
                target: parsed.target || defaultTarget,
                isOffline: !!parsed.isOffline,
            };
        }
    } catch {}
    return { isRunning: false, output: [], target: defaultTarget, isOffline: false };
}

function loadMtrState(): MtrState {
    try {
        const raw = localStorage.getItem('tool_state_mtr');
        if (raw) {
            const parsed = JSON.parse(raw);
            return {
                isRunning: false,
                target: parsed.target || '',
                hops: Array.isArray(parsed.hops) ? parsed.hops : [],
            };
        }
    } catch {}
    return { isRunning: false, target: '', hops: [] };
}


export interface PendingAction {
    type: 'ping' | 'traceroute';
    target: string;
    id: string;
    /** Optional NIC source IP — set when the host belongs to a configured network. */
    sourceIp?: string;
}

/** Options for a one-shot iperf client run. */
export interface IperfClientOptions {
    port?: number;
    sourceIp?: string;
    duration?: number;
    reverse?: boolean;
    udp?: boolean;
}

/** Options for starting the iperf server. */
export interface IperfServerOptions {
    port?: number;
    sourceIp?: string;
}

/** One row of the MTR per-hop table. */
export interface MtrHop {
    hop: number;
    address: string;
    loss_pct: number;
    sent: number;
    last: number | null;
    avg: number | null;
    best: number | null;
    worst: number | null;
    jitter: number | null;
}

/** MTR runs continuously and replaces the whole hop table each cycle. */
export interface MtrState {
    isRunning: boolean;
    target: string;
    hops: MtrHop[];
    error?: string;
}

interface ToolsContextType {
    // Independent States
    pingState: ToolState;
    traceState: ToolState;
    iperfServerState: ToolState;
    iperfClientState: ToolState;
    mtrState: MtrState;
    portState: ToolState;
    scanSessions: ScanSession[];
    activeSessionId: string | null;
    pendingAction: PendingAction | null;
    processedActionIds: Set<string>;
    markActionAsProcessed: (id: string) => void;

    // Actions
    setPingTarget: (target: string) => void;
    setTraceTarget: (target: string) => void;
    setPendingAction: (action: PendingAction | null) => void;

    createScanSession: (cidr: string, mode?: 'quick' | 'full') => string;
    closeScanSession: (id: string) => void;
    updateScanSession: (id: string, updates: Partial<ScanSession>) => void;
    renameScanSession: (id: string, name: string) => void;
    togglePinScanSession: (id: string) => void;
    setActiveSessionId: (id: string | null) => void;

    runPing: (target: string, sourceIp?: string) => Promise<void>;
    runTraceroute: (target: string, sourceIp?: string) => Promise<void>;
    runScanSession: (sessionId: string) => Promise<void>;
    startIperfServer: (opts?: IperfServerOptions) => Promise<void>;
    runIperfClient: (target: string, opts?: IperfClientOptions) => Promise<void>;
    runMtr: (target: string, sourceIp?: string) => Promise<void>;
    runPortScan: (target: string, ports: string, mode?: 'top') => Promise<void>;

    stopTool: (tool: 'ping' | 'traceroute' | 'scanner' | 'iperf-server' | 'iperf-client' | 'mtr' | 'ports', sessionId?: string) => void;
    clearToolOutput: (tool: 'ping' | 'traceroute' | 'iperf-server' | 'iperf-client' | 'ports') => void;
    isRunning: boolean;

    // Completion State
    completedTools: Set<string>;
    markToolAsCompleted: (tool: string) => void;
    clearCompletedTool: (tool: string) => void;
}

const ToolsContext = createContext<ToolsContextType | undefined>(undefined);

export const ToolsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Independent States
    const [pingState, setPingState] = useState<ToolState>(() => loadToolState('ping', '8.8.8.8'));
    const [traceState, setTraceState] = useState<ToolState>(() => loadToolState('trace', '8.8.8.8'));
    // iperf server: this machine listens; iperf client: this machine probes a remote server.
    const [iperfServerState, setIperfServerState] = useState<ToolState>(() => loadToolState('iperf_server', ''));
    const [iperfClientState, setIperfClientState] = useState<ToolState>(() => loadToolState('iperf_client', ''));
    const [mtrState, setMtrState] = useState<MtrState>(loadMtrState);
    const [portState, setPortState] = useState<ToolState>(() => loadToolState('port', ''));

    // Scanner State (Multi-Session) — rehydrated from localStorage (pinned tabs,
    // layout and discovered hosts survive restart).
    const [scanSessions, setScanSessions] = useState<ScanSession[]>(() => loadPersistedSessions().sessions);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(() => loadPersistedSessions().activeId);

    // Pending Action State (for auto-run from Dashboard)
    const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
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

    const isRunning = pingState.isRunning || traceState.isRunning || iperfServerState.isRunning || iperfClientState.isRunning || mtrState.isRunning || portState.isRunning || scanSessions.some(s => s.isRunning);

    // Abort Controllers (mapped by tool name or session ID)
    const abortControllers = useRef<{ [key: string]: AbortController | null }>({});
    const { showToast } = useToast();

    const OUTPUT_CAP = 2000;
    const TRIM_MARKER = '[... linhas mais antigas removidas — buffer limitado a 2000 ...]';
    const trimOutput = (arr: string[]) =>
        arr.length > OUTPUT_CAP ? [TRIM_MARKER, ...arr.slice(-(OUTPUT_CAP - 1))] : arr;

    useEffect(() => {
        return () => {
            for (const key of Object.keys(abortControllers.current)) {
                try { abortControllers.current[key]?.abort(); } catch { /* noop */ }
                abortControllers.current[key] = null;
            }
        };
    }, []);

    // Persist scan sessions to localStorage on every change.
    useEffect(() => {
        try {
            const payload = {
                v: SCAN_SESSIONS_SCHEMA_VERSION,
                activeId: activeSessionId,
                sessions: scanSessions.map<PersistedSession>(s => ({
                    id: s.id,
                    cidr: s.cidr,
                    name: s.name,
                    pinned: s.pinned,
                    sourceIp: s.sourceIp,
                    mode: s.mode,
                    results: s.results,
                    availableRanges: s.availableRanges,
                    availableCount: s.availableCount,
                })),
            };
            localStorage.setItem(SCAN_SESSIONS_STORAGE_KEY, JSON.stringify(payload));
        } catch (e) {
            console.warn('Failed to persist scan sessions', e);
        }
    }, [scanSessions, activeSessionId]);

    // Persist tools states to localStorage
    useEffect(() => {
        if (!pingState.isRunning) {
            try { localStorage.setItem('tool_state_ping', JSON.stringify({ target: pingState.target, output: pingState.output, isOffline: pingState.isOffline })); } catch {}
        }
    }, [pingState.target, pingState.output, pingState.isRunning, pingState.isOffline]);

    useEffect(() => {
        if (!traceState.isRunning) {
            try { localStorage.setItem('tool_state_trace', JSON.stringify({ target: traceState.target, output: traceState.output })); } catch {}
        }
    }, [traceState.target, traceState.output, traceState.isRunning]);

    useEffect(() => {
        if (!portState.isRunning) {
            try { localStorage.setItem('tool_state_port', JSON.stringify({ target: portState.target, output: portState.output })); } catch {}
        }
    }, [portState.target, portState.output, portState.isRunning]);

    useEffect(() => {
        if (!iperfClientState.isRunning) {
            try { localStorage.setItem('tool_state_iperf_client', JSON.stringify({ target: iperfClientState.target, output: iperfClientState.output })); } catch {}
        }
    }, [iperfClientState.target, iperfClientState.output, iperfClientState.isRunning]);

    useEffect(() => {
        if (!mtrState.isRunning) {
            try { localStorage.setItem('tool_state_mtr', JSON.stringify({ target: mtrState.target, hops: mtrState.hops })); } catch {}
        }
    }, [mtrState.target, mtrState.hops, mtrState.isRunning]);


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
        setScanSessions(prev => {
            const target = prev.find(s => s.id === id);
            // Pinned tabs can't be closed — the UI hides the X, this is the
            // belt-and-suspenders guard for any other call path.
            if (target?.pinned) return prev;

            // Abort if running (only once we know we're actually closing it).
            if (abortControllers.current[`scanner_${id}`]) {
                abortControllers.current[`scanner_${id}`]?.abort();
                abortControllers.current[`scanner_${id}`] = null;
            }

            const closedIndex = prev.findIndex(s => s.id === id);
            const newSessions = prev.filter(s => s.id !== id);

            // Pick the next active tab here (not in a downstream effect): the
            // neighbour to the left, or the new first tab, or null if empty.
            setActiveSessionId(currentActive => {
                if (currentActive !== id) return currentActive; // closed a non-active tab
                if (newSessions.length === 0) return null;
                const nextIndex = Math.max(0, closedIndex - 1);
                return newSessions[Math.min(nextIndex, newSessions.length - 1)].id;
            });

            return newSessions;
        });
    }, []);

    const updateScanSession = useCallback((id: string, updates: Partial<ScanSession>) => {
        setScanSessions(prev => prev.map(s => s.id === id ? { ...s, ...updates } : s));
    }, []);

    const renameScanSession = useCallback((id: string, name: string) => {
        const trimmed = name.trim();
        // Empty name clears the override (tab falls back to showing the CIDR).
        setScanSessions(prev => prev.map(s => s.id === id ? { ...s, name: trimmed || undefined } : s));
    }, []);

    const togglePinScanSession = useCallback((id: string) => {
        setScanSessions(prev => prev.map(s => s.id === id ? { ...s, pinned: !s.pinned } : s));
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

    const stopTool = useCallback((tool: 'ping' | 'traceroute' | 'scanner' | 'iperf-server' | 'iperf-client' | 'mtr' | 'ports', sessionId?: string) => {
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

            setPingState(prev => ({ ...prev, isRunning: false, output: trimOutput([...prev.output, summary]) }));
        }
        if (tool === 'traceroute') setTraceState(prev => ({ ...prev, isRunning: false, output: trimOutput([...prev.output, '\n[Cancelado pelo usuário]']) }));
        if (tool === 'iperf-server') setIperfServerState(prev => ({ ...prev, isRunning: false, output: trimOutput([...prev.output, '\n[Servidor parado pelo usuário]']) }));
        if (tool === 'iperf-client') setIperfClientState(prev => ({ ...prev, isRunning: false, output: trimOutput([...prev.output, '\n[Cancelado pelo usuário]']) }));
        if (tool === 'mtr') setMtrState(prev => ({ ...prev, isRunning: false }));
        if (tool === 'ports') setPortState(prev => ({ ...prev, isRunning: false, output: trimOutput([...prev.output, '\n[Cancelado pelo usuário]']) }));
        if (tool === 'scanner' && sessionId) {
            updateScanSession(sessionId, { isRunning: false, status: 'Cancelado pelo usuário.' });
        }
    }, [pingState.target, updateScanSession]);

    const clearToolOutput = useCallback((tool: 'ping' | 'traceroute' | 'iperf-server' | 'iperf-client' | 'ports') => {
        if (tool === 'ping') setPingState(prev => ({ ...prev, output: [], isOffline: false }));
        if (tool === 'traceroute') setTraceState(prev => ({ ...prev, output: [] }));
        if (tool === 'iperf-server') setIperfServerState(prev => ({ ...prev, output: [] }));
        if (tool === 'iperf-client') setIperfClientState(prev => ({ ...prev, output: [] }));
        if (tool === 'ports') setPortState(prev => ({ ...prev, output: [] }));
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
                    return { ...prev, output: trimOutput([...prev.output, text]) };
                });
            }
            markToolAsCompleted('ping');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('Ping error:', error);
                setPingState(prev => ({ ...prev, output: trimOutput([...prev.output, `\nErro: ${error.message}`]) }));
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
                setTraceState(prev => ({ ...prev, output: trimOutput([...prev.output, text]) }));
            }
            markToolAsCompleted('traceroute');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('Traceroute error:', error);
                setTraceState(prev => ({ ...prev, output: trimOutput([...prev.output, `\nErro: ${error.message}`]) }));
            }
        } finally {
            setTraceState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['traceroute'] = null;
        }
    }, [traceState.isRunning]);

    const startIperfServer = useCallback(async (opts?: IperfServerOptions) => {
        // Race-free re-entrancy guard (see runMtr).
        if (abortControllers.current['iperf-server']) return;
        abortControllers.current['iperf-server'] = new AbortController();

        const label = opts?.sourceIp ? `porta ${opts.port ?? 5201} (via ${opts.sourceIp})` : `porta ${opts?.port ?? 5201}`;
        setIperfServerState(prev => ({ ...prev, isRunning: true, output: [`Iniciando servidor iperf na ${label}...`], target: String(opts?.port ?? 5201) }));

        try {
            const response = await fetch(`${API_BASE}/tools/iperf/server`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: 'iperf-server', port: opts?.port ?? 5201, source_ip: opts?.sourceIp }),
                signal: abortControllers.current['iperf-server'].signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                setIperfServerState(prev => ({ ...prev, output: trimOutput([...prev.output, text]) }));
            }
            markToolAsCompleted('iperf-server');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('iperf server error:', error);
                setIperfServerState(prev => ({ ...prev, output: trimOutput([...prev.output, `\nErro: ${error.message}`]) }));
            }
        } finally {
            setIperfServerState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['iperf-server'] = null;
        }
    }, [markToolAsCompleted]);

    const runIperfClient = useCallback(async (target: string, opts?: IperfClientOptions) => {
        // Race-free re-entrancy guard (see runMtr).
        if (abortControllers.current['iperf-client']) return;
        abortControllers.current['iperf-client'] = new AbortController();

        setIperfClientState(prev => ({ ...prev, isRunning: true, output: [`Testando banda até ${target}...`], target }));

        try {
            const response = await fetch(`${API_BASE}/tools/iperf/client`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target,
                    task_id: 'iperf-client',
                    port: opts?.port ?? 5201,
                    source_ip: opts?.sourceIp,
                    duration: opts?.duration ?? 10,
                    reverse: opts?.reverse ?? false,
                    udp: opts?.udp ?? false,
                }),
                signal: abortControllers.current['iperf-client'].signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                setIperfClientState(prev => ({ ...prev, output: trimOutput([...prev.output, text]) }));
            }
            markToolAsCompleted('iperf-client');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('iperf client error:', error);
                setIperfClientState(prev => ({ ...prev, output: trimOutput([...prev.output, `\nErro: ${error.message}`]) }));
            }
        } finally {
            setIperfClientState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['iperf-client'] = null;
        }
    }, [markToolAsCompleted]);

    const runMtr = useCallback(async (target: string, sourceIp?: string) => {
        // Synchronous re-entrancy guard: a live run always holds a non-null
        // controller. Checking state (mtrState.isRunning) is stale-closure prone
        // and lets a fast double-click spawn two fetches, leaking the first
        // AbortController. The ref check is race-free.
        if (abortControllers.current['mtr']) return;
        abortControllers.current['mtr'] = new AbortController();

        setMtrState({ isRunning: true, target, hops: [], error: undefined });

        try {
            const response = await fetch(`${API_BASE}/tools/mtr`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, task_id: 'mtr', source_ip: sourceIp }),
                signal: abortControllers.current['mtr'].signal
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
                        if (data.hops) {
                            setMtrState(prev => ({ ...prev, hops: data.hops }));
                        } else if (data.error) {
                            setMtrState(prev => ({ ...prev, error: data.error }));
                        }
                        // {status:'started'} is informational — ignored.
                    } catch (e) {
                        console.debug('MTR JSON parse skip:', e);
                    }
                }
            }
            markToolAsCompleted('mtr');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('MTR error:', error);
                setMtrState(prev => ({ ...prev, error: error.message }));
            }
        } finally {
            setMtrState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['mtr'] = null;
        }
    }, [markToolAsCompleted]);

    const runPortScan = useCallback(async (target: string, ports: string, mode?: 'top') => {
        // Race-free re-entrancy guard (see runMtr).
        if (abortControllers.current['ports']) return;
        abortControllers.current['ports'] = new AbortController();

        const header = mode === 'top' ? `Verificando portas comuns em ${target}...` : `Verificando portas em ${target}...`;
        setPortState({ isRunning: true, output: [header], target });

        try {
            const response = await fetch(`${API_BASE}/tools/ports`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, ports: mode === 'top' ? undefined : ports, mode, task_id: 'ports' }),
                signal: abortControllers.current['ports'].signal
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const text = decoder.decode(value);
                setPortState(prev => ({ ...prev, output: trimOutput([...prev.output, text]) }));
            }
            markToolAsCompleted('ports');
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                console.error('Port scan error:', error);
                setPortState(prev => ({ ...prev, output: trimOutput([...prev.output, `\nErro: ${error.message}`]) }));
            }
        } finally {
            setPortState(prev => ({ ...prev, isRunning: false }));
            abortControllers.current['ports'] = null;
        }
    }, [markToolAsCompleted]);

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
            let resolveVendors = true;
            try {
                const settingsRes = await fetch(`${API_BASE}/settings`);
                const settingsData = await settingsRes.json();
                if (settingsData.scanner) {
                    timeout = settingsData.scanner.ping_timeout || 200;
                    concurrency = settingsData.scanner.concurrency || 50;
                    // online_vendor_lookup gates the ARP→manufacturer pass.
                    resolveVendors = settingsData.scanner.online_vendor_lookup !== false;
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
                    resolve_vendors: resolveVendors,
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
                        } else if (data.status === 'vendor_update' && data.ip) {
                            // Post-scan ARP pass: merge MAC/vendor (and a refined
                            // type) into the card that's already on screen. Never
                            // downgrade a confident port-based type to a guess —
                            // only overwrite device_type when the update carries one.
                            setScanSessions(prev => prev.map(s => {
                                if (s.id !== sessionId) return s;
                                return {
                                    ...s,
                                    results: s.results.map(h => h.ip === data.ip
                                        ? {
                                            ...h,
                                            mac: data.mac ?? h.mac,
                                            vendor: data.vendor ?? h.vendor,
                                            ...(data.device_type !== undefined ? {
                                                device_type: data.device_type,
                                                device_type_guess: data.device_type_guess,
                                            } : {}),
                                        }
                                        : h),
                                };
                            }));
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
            iperfServerState,
            iperfClientState,
            mtrState,
            portState,
            scanSessions,
            activeSessionId,
            setPingTarget,
            setTraceTarget,
            createScanSession,
            closeScanSession,
            updateScanSession,
            renameScanSession,
            togglePinScanSession,
            setActiveSessionId,
            runPing,
            runTraceroute,
            runScanSession,
            startIperfServer,
            runIperfClient,
            runMtr,
            runPortScan,
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
