import { useState, useEffect } from 'react';
import { Terminal as TerminalIcon, Network as NetworkIcon, Activity, Gauge, GitBranch, DoorOpen, Globe, Zap, Ruler, Globe2, Lock, Calculator, Clock, Router, Stethoscope, Compass, Wrench, ShieldAlert, FolderGit2, AlertTriangle } from 'lucide-react';
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
import { AdToolsPanel } from '../components/Tools/AdToolsPanel';
import { LldpCdpPanel } from '../components/Tools/LldpCdpPanel';
import { SmbSharePanel } from '../components/Tools/SmbSharePanel';
import { ArpConflictPanel } from '../components/Tools/ArpConflictPanel';
import { DiagnosticToolRunner } from '../components/Tools/DiagnosticToolRunner';
import { Host } from '../types';
import { useTools } from '../contexts/ToolsContext';
import { useToast } from '../contexts/ToastContext';
import { useNetworks } from '../hooks/useNetworks';
import { API_BASE } from '../config/api';

// Tool identifiers across all categories.
type ToolId =
    | 'ping' | 'traceroute' | 'mtr' | 'tcp-ping' | 'pmtu'
    | 'scanner' | 'ports' | 'ptr-sweep' | 'lldp' | 'smb' | 'arp'
    | 'ad'
    | 'dns' | 'tls'
    | 'iperf' | 'traffic' | 'http'
    | 'snmp' | 'ntp' | 'subnet' | 'connections';

interface ToolDef { id: ToolId; label: string; icon: React.ReactNode; }
interface ToolCategory { id: string; label: string; icon: React.ReactNode; tools: ToolDef[]; }

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
        id: 'ad', label: 'Active Directory', icon: <ShieldAlert size={16} />, tools: [
            { id: 'ad', label: 'Diagnóstico AD', icon: <ShieldAlert size={16} /> },
        ],
    },
    {
        id: 'disco', label: 'Descoberta & L2', icon: <Compass size={16} />, tools: [
            { id: 'scanner', label: 'Scanner de Rede', icon: <TerminalIcon size={16} /> },
            { id: 'lldp', label: 'Switch / L2 (LLDP)', icon: <Router size={16} /> },
            { id: 'smb', label: 'Pastas SMB', icon: <FolderGit2 size={16} /> },
            { id: 'arp', label: 'Conflitos ARP', icon: <AlertTriangle size={16} /> },
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
    const [pingSourceIp, setPingSourceIp] = useState<string>('');
    const [traceSourceIp, setTraceSourceIp] = useState<string>('');

    const { networks } = useNetworks();
    const [existingHosts, setExistingHosts] = useState<Host[]>([]);

    useEffect(() => {
        if (pendingAction) {
            if (processedActionIds.has(pendingAction.id)) return;

            const { type, target, sourceIp } = pendingAction;
            if (type === 'ping') {
                setActiveCategory('diag');
                setActiveTab('ping');
                setLocalPingTarget(target);
                if (sourceIp !== undefined) setPingSourceIp(sourceIp);
            } else if (type === 'traceroute') {
                setActiveCategory('diag');
                setActiveTab('traceroute');
                setLocalTraceTarget(target);
                if (sourceIp !== undefined) setTraceSourceIp(sourceIp);
            }

            markActionAsProcessed(pendingAction.id);
            setPendingAction(null);
        }
    }, [pendingAction, setPendingAction, processedActionIds, markActionAsProcessed]);

    useEffect(() => {
        fetch(`${API_BASE}/hosts`)
            .then(res => res.json())
            .then(setExistingHosts)
            .catch(err => {
                console.debug('Tools: pre-load /hosts failed:', err);
            });
    }, []);

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

            const hostsRes = await fetch(`${API_BASE}/hosts`);
            const hostsData = await hostsRes.json();
            setExistingHosts(hostsData);
        } catch (error) {
            console.error('Failed to add host:', error);
            showToast('Erro ao adicionar host: ' + (error as Error).message, 'error');
        }
    };

    return (
        <div className="h-full flex flex-col space-y-4 p-5 min-h-0 overflow-hidden">
            <header className="shrink-0">
                <h2 className="text-2xl font-bold text-white">Ferramentas de Rede</h2>
                <p className="text-zinc-400 text-sm">Diagnóstico e verificação de conectividade corporativa.</p>
            </header>

            {/* Level 1: categories */}
            <div className="flex gap-2 flex-wrap shrink-0">
                {TOOL_CATEGORIES.map(cat => {
                    const isActive = activeCategory === cat.id;
                    const catRunning = cat.tools.some(t => toolIsRunning(t.id));
                    return (
                        <button
                            key={cat.id}
                            onClick={() => {
                                setActiveCategory(cat.id);
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

            <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
                {activeTab === 'ping' && (
                    <DiagnosticToolRunner
                        type="ping"
                        state={pingState}
                        target={localPingTarget}
                        setTarget={setLocalPingTarget}
                        run={runPing}
                        stop={() => stopTool('ping')}
                        clear={() => clearToolOutput('ping')}
                        colorClass="text-blue-400"
                        borderColorClass="border-blue-900/30 hover:border-blue-500/50"
                        sourceIp={pingSourceIp}
                        setSourceIp={setPingSourceIp}
                        availableNetworks={networks}
                    />
                )}

                {activeTab === 'traceroute' && (
                    <DiagnosticToolRunner
                        type="traceroute"
                        state={traceState}
                        target={localTraceTarget}
                        setTarget={setLocalTraceTarget}
                        run={runTraceroute}
                        stop={() => stopTool('traceroute')}
                        clear={() => clearToolOutput('traceroute')}
                        colorClass="text-purple-400"
                        borderColorClass="border-purple-900/30 hover:border-purple-500/50"
                        sourceIp={traceSourceIp}
                        setSourceIp={setTraceSourceIp}
                        availableNetworks={networks}
                    />
                )}

                {activeTab === 'ad' && <AdToolsPanel defaultSourceIp={pingSourceIp} />}
                {activeTab === 'lldp' && <LldpCdpPanel defaultSourceIp={pingSourceIp} />}
                {activeTab === 'smb' && <SmbSharePanel />}
                {activeTab === 'arp' && <ArpConflictPanel defaultSourceIp={pingSourceIp} />}
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
