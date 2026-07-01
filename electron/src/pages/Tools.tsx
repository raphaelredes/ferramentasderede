import { useState, useRef, useEffect } from 'react';
import { Play, Square, Terminal as TerminalIcon, Eraser, Network as NetworkIcon, Activity, Gauge, GitBranch, DoorOpen, Globe, Zap, Ruler, Globe2, Lock, Calculator, Clock, Router, Stethoscope, Compass, Wrench } from 'lucide-react';
import { clsx } from 'clsx';
import { NetworkScanner } from '../components/Tools/NetworkScanner';
import { IperfPanel } from '../components/Tools/IperfPanel';
import { MtrPanel } from '../components/Tools/MtrPanel';
import { PortScanPanel } from '../components/Tools/PortScanPanel';
import { DnsPanel } from '../components/Tools/DnsPanel';
import { TrafficPanel } from '../components/Tools/TrafficPanel';
import { TcpPingPanel } from '../components/Tools/TcpPingPanel';
import { PmtuPanel } from '../components/Tools/PmtuPanel';
import { PtrSweepPanel } from '../components/Tools/PtrSweepPanel';
import { TlsPanel } from '../components/Tools/TlsPanel';
import { SubnetPanel } from '../components/Tools/SubnetPanel';
import { NtpPanel } from '../components/Tools/NtpPanel';
import { SnmpPanel } from '../components/Tools/SnmpPanel';
import { HttpPanel } from '../components/Tools/HttpPanel';
import { ConnectionsPanel } from '../components/Tools/ConnectionsPanel';
import { Host } from '../types';
import { useTools } from '../contexts/ToolsContext';
import { useToast } from '../contexts/ToastContext';
import { useNetworks } from '../hooks/useNetworks';
import { API_BASE } from '../config/api';
import type { NetworkConfig } from './Settings';

// Tool identifiers across all categories.
type ToolId =
    | 'ping' | 'traceroute' | 'mtr' | 'tcp-ping' | 'pmtu'
    | 'scanner' | 'ports' | 'ptr-sweep'
    | 'dns' | 'tls'
    | 'iperf' | 'traffic' | 'http'
    | 'snmp' | 'ntp' | 'subnet' | 'connections';

interface ToolDef { id: ToolId; label: string; icon: React.ReactNode; }
interface ToolCategory { id: string; label: string; icon: React.ReactNode; tools: ToolDef[]; }

// Two-level navigation: categories → tools. Keeps 16 tools navigable.
const TOOL_CATEGORIES: ToolCategory[] = [
    {
        id: 'diag', label: 'Diagnóstico', icon: <Stethoscope size={16} />, tools: [
            { id: 'ping', label: 'Ping', icon: <Activity size={16} /> },
            { id: 'traceroute', label: 'Traceroute', icon: <NetworkIcon size={16} /> },
            { id: 'mtr', label: 'MTR', icon: <GitBranch size={16} /> },
            { id: 'tcp-ping', label: 'TCP Ping', icon: <Zap size={16} /> },
            { id: 'pmtu', label: 'Path MTU', icon: <Ruler size={16} /> },
        ],
    },
    {
        id: 'disco', label: 'Descoberta', icon: <Compass size={16} />, tools: [
            { id: 'scanner', label: 'Scanner de Rede', icon: <TerminalIcon size={16} /> },
            { id: 'ports', label: 'Portas', icon: <DoorOpen size={16} /> },
            { id: 'ptr-sweep', label: 'PTR Sweep', icon: <Globe2 size={16} /> },
        ],
    },
    {
        id: 'dns', label: 'DNS & Nomes', icon: <Globe size={16} />, tools: [
            { id: 'dns', label: 'Consulta DNS', icon: <Globe size={16} /> },
            { id: 'tls', label: 'Certificado TLS', icon: <Lock size={16} /> },
        ],
    },
    {
        id: 'banda', label: 'Banda & Web', icon: <Gauge size={16} />, tools: [
            { id: 'iperf', label: 'Banda (iPerf)', icon: <Gauge size={16} /> },
            { id: 'traffic', label: 'Tráfego', icon: <NetworkIcon size={16} /> },
            { id: 'http', label: 'HTTP', icon: <Globe size={16} /> },
        ],
    },
    {
        id: 'infra', label: 'Infra & Cálculo', icon: <Wrench size={16} />, tools: [
            { id: 'snmp', label: 'SNMP', icon: <Router size={16} /> },
            { id: 'ntp', label: 'NTP', icon: <Clock size={16} /> },
            { id: 'subnet', label: 'Sub-rede', icon: <Calculator size={16} /> },
            { id: 'connections', label: 'Conexões', icon: <NetworkIcon size={16} /> },
        ],
    },
];

export function Tools() {
    const [activeTab, setActiveTab] = useState<ToolId>('ping');
    const [activeCategory, setActiveCategory] = useState<string>('diag');
    const { showToast } = useToast();

    // Use Global Context
    const {
        pingState,
        traceState,
        iperfServerState,
        iperfClientState,
        mtrState,
        portState,
        runPing,
        runTraceroute,
        stopTool,
        clearToolOutput,
        pendingAction,
        setPendingAction,
        processedActionIds,
        markActionAsProcessed
    } = useTools();

    const [localPingTarget, setLocalPingTarget] = useState('8.8.8.8');
    const [localTraceTarget, setLocalTraceTarget] = useState('8.8.8.8');
    const [pingSourceIp, setPingSourceIp] = useState<string>('');     // '' = auto (rota default)
    const [traceSourceIp, setTraceSourceIp] = useState<string>('');

    const { networks } = useNetworks();

    const outputEndRef = useRef<HTMLDivElement>(null);
    const [existingHosts, setExistingHosts] = useState<Host[]>([]);

    // Handle pending actions from context (e.g. from Dashboard)
    useEffect(() => {
        if (pendingAction) {
            // Skip if already processed this exact action ID
            if (processedActionIds.has(pendingAction.id)) {
                return;
            }

            const { type, target, sourceIp } = pendingAction;

            if (type === 'ping') {
                setActiveCategory('diag');
                setActiveTab('ping');
                setLocalPingTarget(target);
                if (sourceIp !== undefined) setPingSourceIp(sourceIp);
                // Auto-run disabled per user request
            } else if (type === 'traceroute') {
                setActiveCategory('diag');
                setActiveTab('traceroute');
                setLocalTraceTarget(target);
                if (sourceIp !== undefined) setTraceSourceIp(sourceIp);
                // Auto-run disabled per user request
            }

            // Mark as processed in Context (survives remounts)
            markActionAsProcessed(pendingAction.id);

            // Clear pending action immediately
            setPendingAction(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pendingAction, setPendingAction, processedActionIds, markActionAsProcessed]);

    useEffect(() => {
        // Best-effort: pre-load host list so the scanner can mark "already
        // added" without flicker. Failure here just means new scan results
        // won't be deduplicated against existing hosts — graceful degradation,
        // so no toast. Intentionally silent.
        fetch(`${API_BASE}/hosts`)
            .then(res => res.json())
            .then(setExistingHosts)
            .catch(err => {
                console.debug('Tools: pre-load /hosts failed (autocomplete dedupe will degrade gracefully):', err);
            });
    }, []);

    // Running indicator per tool, for the category/tab dots. Tools whose running
    // state lives in their own component (self-contained panels) report false
    // here — their tab simply doesn't show a global dot, which is fine.
    const toolIsRunning = (id: ToolId): boolean => {
        switch (id) {
            case 'ping': return pingState.isRunning;
            case 'traceroute': return traceState.isRunning;
            case 'mtr': return mtrState.isRunning;
            case 'ports': return portState.isRunning;
            case 'iperf': return iperfServerState.isRunning || iperfClientState.isRunning;
            default: return false;
        }
    };

    const handleAddHost = async (host: Host) => {
        try {
            const res = await fetch(`${API_BASE}/hosts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(host),
            });

            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.detail || 'Erro ao adicionar host');
            }

            // Refresh existing hosts
            const hostsRes = await fetch(`${API_BASE}/hosts`);
            const hostsData = await hostsRes.json();
            setExistingHosts(hostsData);

        } catch (error) {
            console.error('Failed to add host:', error);
            showToast('Erro ao adicionar host: ' + (error as Error).message, 'error');
        }
    };

    const renderDiagnosticTool = (
        type: 'ping' | 'traceroute',
        state: { isRunning: boolean; output: string[] },
        target: string,
        setTarget: (t: string) => void,
        run: (t: string, sourceIp?: string) => void,
        stop: () => void,
        clear: () => void,
        _icon: React.ReactNode,
        colorClass: string,
        borderColorClass: string,
        sourceIp: string,
        setSourceIp: (v: string) => void,
        availableNetworks: NetworkConfig[],
    ) => (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Alvo (IP ou Hostname)</label>
                    <input
                        type="text"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        onFocus={() => { if (target === '8.8.8.8') setTarget(''); }}
                        placeholder="8.8.8.8"
                        className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500 ${target === '8.8.8.8' ? 'text-zinc-500' : 'text-white'}`}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !state.isRunning) run(target || '8.8.8.8', sourceIp || undefined);
                        }}
                    />
                </div>

                <div className="space-y-2 w-64">
                    <label className="text-sm font-medium text-zinc-400">Sair pela rede</label>
                    <select
                        value={sourceIp}
                        onChange={(e) => setSourceIp(e.target.value)}
                        disabled={state.isRunning}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-60"
                    >
                        <option value="">Automático (rota padrão)</option>
                        {availableNetworks.map(net => (
                            <option key={net.id} value={net.source_ip ?? ''} disabled={!net.source_ip}>
                                {net.name || net.cidr}
                                {net.source_ip ? ` — ${net.source_ip}` : ' (sem source IP)'}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={() => run(target || '8.8.8.8', sourceIp || undefined)}
                        disabled={state.isRunning}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors border",
                            state.isRunning
                                ? "bg-zinc-900 text-zinc-600 border-zinc-800 cursor-not-allowed"
                                : `bg-zinc-800 hover:bg-zinc-700 ${colorClass} ${borderColorClass}`
                        )}
                    >
                        {state.isRunning ? <Activity size={18} className="animate-spin" /> : <Play size={18} />}
                        {type === 'ping' ? 'Iniciar Ping' : 'Iniciar Traceroute'}
                    </button>

                    {state.isRunning && (
                        <button
                            onClick={stop}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                        >
                            <Square size={18} />
                            Parar
                        </button>
                    )}
                </div>
            </div>

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm">
                <div className="absolute top-2 right-2 z-10">
                    <button
                        onClick={clear}
                        className="p-2 text-zinc-500 hover:text-white transition-colors rounded-lg hover:bg-zinc-800"
                        title="Limpar Terminal"
                    >
                        <Eraser size={16} />
                    </button>
                </div>

                <div className="flex-1 overflow-auto custom-scrollbar">
                    {state.output.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <TerminalIcon size={48} className="mb-4 opacity-20" />
                            <p>Aguardando comando...</p>
                        </div>
                    )}

                    {state.output.map((line, i) => (
                        <div key={i} className="whitespace-pre-wrap break-all text-zinc-300 leading-tight">
                            {line}
                        </div>
                    ))}
                    <div ref={outputEndRef} />
                </div>
            </div>
        </div>
    );

    return (
        <div className="h-full flex flex-col space-y-6 p-6">
            <header>
                <h2 className="text-2xl font-bold text-white">Ferramentas de Rede</h2>
                <p className="text-zinc-400">Diagnóstico e verificação de conectividade.</p>
            </header>

            {/* Level 1: categories */}
            <div className="flex gap-2 flex-wrap shrink-0">
                {TOOL_CATEGORIES.map(cat => {
                    const isActive = activeCategory === cat.id;
                    // Light up the category if any tool inside it is running.
                    const catRunning = cat.tools.some(t => toolIsRunning(t.id));
                    return (
                        <button
                            key={cat.id}
                            onClick={() => {
                                setActiveCategory(cat.id);
                                // Jump to the category's first tool if the current
                                // active tool isn't part of it.
                                if (!cat.tools.some(t => t.id === activeTab)) {
                                    setActiveTab(cat.tools[0].id);
                                }
                            }}
                            className={clsx(
                                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors border',
                                isActive
                                    ? 'bg-zinc-800 text-white border-zinc-700'
                                    : 'bg-zinc-900/50 text-zinc-400 hover:text-white border-transparent hover:border-zinc-800'
                            )}
                        >
                            {cat.icon}
                            {cat.label}
                            {catRunning && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}
                        </button>
                    );
                })}
            </div>

            {/* Level 2: tools within the active category */}
            <div className="flex gap-2 border-b border-zinc-800 overflow-x-auto custom-scrollbar shrink-0">
                {(TOOL_CATEGORIES.find(c => c.id === activeCategory)?.tools ?? []).map(tool => {
                    const isActive = activeTab === tool.id;
                    return (
                        <button
                            key={tool.id}
                            onClick={() => setActiveTab(tool.id)}
                            className={clsx(
                                'px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap',
                                isActive ? 'border-blue-500 text-blue-400' : 'border-transparent text-zinc-400 hover:text-white'
                            )}
                        >
                            {tool.icon}
                            {tool.label}
                            {toolIsRunning(tool.id) && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}
                        </button>
                    );
                })}
            </div>

            <div className="flex-1 min-h-0">
                {activeTab === 'ping' && renderDiagnosticTool(
                    'ping',
                    pingState,
                    localPingTarget,
                    setLocalPingTarget,
                    runPing,
                    () => stopTool('ping'),
                    () => clearToolOutput('ping'),
                    <Activity size={18} />,
                    'text-blue-400',
                    'border-blue-900/30 hover:border-blue-500/50',
                    pingSourceIp,
                    setPingSourceIp,
                    networks,
                )}

                {activeTab === 'traceroute' && renderDiagnosticTool(
                    'traceroute',
                    traceState,
                    localTraceTarget,
                    setLocalTraceTarget,
                    runTraceroute,
                    () => stopTool('traceroute'),
                    () => clearToolOutput('traceroute'),
                    <NetworkIcon size={18} />,
                    'text-purple-400',
                    'border-purple-900/30 hover:border-purple-500/50',
                    traceSourceIp,
                    setTraceSourceIp,
                    networks,
                )}

                {activeTab === 'mtr' && <MtrPanel />}
                {activeTab === 'tcp-ping' && <TcpPingPanel />}
                {activeTab === 'pmtu' && <PmtuPanel />}

                {activeTab === 'scanner' && (
                    <NetworkScanner onAddHost={handleAddHost} existingHosts={existingHosts} />
                )}

                {activeTab === 'ports' && <PortScanPanel />}
                {activeTab === 'ptr-sweep' && <PtrSweepPanel />}

                {activeTab === 'dns' && <DnsPanel />}
                {activeTab === 'tls' && <TlsPanel />}

                {activeTab === 'iperf' && <IperfPanel />}
                {activeTab === 'traffic' && <TrafficPanel />}
                {activeTab === 'http' && <HttpPanel />}

                {activeTab === 'snmp' && <SnmpPanel />}
                {activeTab === 'ntp' && <NtpPanel />}
                {activeTab === 'subnet' && <SubnetPanel />}
                {activeTab === 'connections' && <ConnectionsPanel />}
            </div>
        </div>
    );
}
