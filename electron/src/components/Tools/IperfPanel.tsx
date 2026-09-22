import { useEffect, useRef, useState, useMemo } from 'react';
import {
    Play, Square, Eraser, Server, Download, Copy, Check,
    AlertTriangle, Gauge, Wifi, Activity, Zap,
    Terminal, Info, ChevronDown, ChevronUp, Layers
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useTools } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { useMonitoring } from '../../contexts/MonitoringContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface IperfStatus {
    available: boolean;
    version: string | null;
    path: string | null;
}

interface NetworkInterface {
    name: string;
    ip: string;
    netmask?: string;
    prefix?: number;
    cidr?: string;
    is_up: boolean;
    mac?: string;
}

/**
 * Painel de teste de banda com iperf2.
 * Suporta modo Servidor (este computador aguarda testes de outros hosts)
 * e modo Cliente (testa a velocidade até outro host/servidor iperf).
 */
export function IperfPanel() {
    const {
        iperfServerState,
        iperfClientState,
        startIperfServer,
        runIperfClient,
        stopTool,
        clearToolOutput,
    } = useTools();
    const { showToast } = useToast();
    const { networks } = useNetworks();
    const { hosts } = useMonitoring();

    const [mode, setMode] = usePersistedState<'server' | 'client'>('iperf_tool_mode', 'server');

    // Server form state
    const [serverPort, setServerPort] = usePersistedState('iperf_tool_server_port', '5201');
    const [serverSourceIp, setServerSourceIp] = usePersistedState('iperf_tool_server_source_ip', '');
    const [autostartServer, setAutostartServer] = usePersistedState<boolean>('iperf_autostart_server', false);

    // Client form state
    const [clientTarget, setClientTarget] = usePersistedState('iperf_tool_client_target', '');
    const [clientPort, setClientPort] = usePersistedState('iperf_tool_client_port', '5201');
    const [clientSourceIp, setClientSourceIp] = usePersistedState('iperf_tool_client_source_ip', '');
    const [clientDuration, setClientDuration] = usePersistedState('iperf_tool_client_duration', '10');
    const [clientReverse, setClientReverse] = usePersistedState('iperf_tool_client_reverse', false);
    const [clientUdp, setClientUdp] = usePersistedState('iperf_tool_client_udp', false);
    const [clientParallel, setClientParallel] = usePersistedState('iperf_tool_client_parallel', '1');

    // State for local NICs and UI interaction
    const [localInterfaces, setLocalInterfaces] = useState<NetworkInterface[]>([]);
    const [selectedDisplayIp, setSelectedDisplayIp] = useState<string>('');
    const [status, setStatus] = useState<IperfStatus | null>(null);
    const [copiedCmd2, setCopiedCmd2] = useState(false);
    const [copiedCmd3, setCopiedCmd3] = useState(false);
    const [copiedIp, setCopiedIp] = useState(false);
    const [copiedLog, setCopiedLog] = useState(false);
    const [showQuickGuide, setShowQuickGuide] = useState(false);
    const [autoScroll, setAutoScroll] = useState(true);

    const outputEndRef = useRef<HTMLDivElement>(null);
    const consoleContainerRef = useRef<HTMLDivElement>(null);

    // Probe status of the iperf binary
    useEffect(() => {
        fetch(`${API_BASE}/tools/iperf/status`)
            .then(res => res.json())
            .then(setStatus)
            .catch(err => {
                console.debug('IperfPanel: status probe failed:', err);
                setStatus({ available: false, version: null, path: null });
            });
    }, []);

    // Load active network interfaces to display real machine IPs
    useEffect(() => {
        fetch(`${API_BASE}/network/interfaces`)
            .then(res => res.ok ? res.json() : [])
            .then((data: NetworkInterface[]) => {
                if (Array.isArray(data)) {
                    setLocalInterfaces(data);
                }
            })
            .catch(err => {
                console.debug('IperfPanel: falha ao listar interfaces:', err);
            });
    }, []);

    const activeState = mode === 'server' ? iperfServerState : iperfClientState;

    // Filter valid active IPv4s
    const activeIps = useMemo(() => {
        return localInterfaces.filter(
            iface => iface.ip && !iface.ip.startsWith('127.') && !iface.ip.startsWith('169.254.')
        );
    }, [localInterfaces]);

    const primaryIp = activeIps[0]?.ip || '127.0.0.1';

    // Resolved IP displayed in the command
    const serverDisplayIp = useMemo(() => {
        if (serverSourceIp) return serverSourceIp;
        if (selectedDisplayIp && activeIps.some(i => i.ip === selectedDisplayIp)) {
            return selectedDisplayIp;
        }
        return primaryIp;
    }, [serverSourceIp, selectedDisplayIp, primaryIp, activeIps]);

    const otherSideCommand = `iperf -c ${serverDisplayIp} -p ${serverPort || '5201'}`;
    const otherSideCommandIperf3 = `iperf3 -c ${serverDisplayIp} -p ${serverPort || '5201'}`;

    // Auto-scroll handler
    useEffect(() => {
        if (autoScroll) {
            outputEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [activeState.output, autoScroll]);

    // Detect user scroll to toggle auto-scroll
    const handleScroll = () => {
        if (!consoleContainerRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = consoleContainerRef.current;
        const isNearBottom = scrollHeight - scrollTop - clientHeight < 40;
        setAutoScroll(isNearBottom);
    };

    // Live Metrics Parser
    const liveMetrics = useMemo(() => {
        let latestBandwidth: string | null = null;
        let latestTransfer: string | null = null;
        let latestInterval: string | null = null;
        let latestJitter: string | null = null;
        let latestLoss: string | null = null;
        let connectedClient: string | null = null;

        for (const line of activeState.output) {
            // Check connected with line:
            // [  4] local 10.10.38.14 port 5201 connected with 10.10.38.15 port 54321
            const connMatch = line.match(/connected with\s+([0-9a-fA-F.:]+)\s+port\s+(\d+)/i);
            if (connMatch) {
                connectedClient = `${connMatch[1]}:${connMatch[2]}`;
            }

            // Match interval lines:
            // [  4]  0.0- 1.0 sec  112 MBytes   940 Mbits/sec
            // [  3]  0.0- 1.0 sec  1.19 MBytes  10.0 Mbits/sec  0.035 ms    0/  850 (0%)
            const match = line.match(/\[\s*[\d\w]+\]\s+([\d.]+-\s*[\d.]+\s*sec)\s+([\d.]+\s*[KMGkmg]Bytes)\s+([\d.]+\s*[KMGkmg]bits\/sec)(?:\s+([\d.]+\s*ms)\s+(\d+\/\s*\d+\s*\([\d.]+%\)))?/i);
            if (match) {
                latestInterval = match[1].trim();
                latestTransfer = match[2].trim();
                latestBandwidth = match[3].trim();
                if (match[4]) latestJitter = match[4].trim();
                if (match[5]) latestLoss = match[5].trim();
            }
        }

        return {
            bandwidth: latestBandwidth,
            transfer: latestTransfer,
            interval: latestInterval,
            jitter: latestJitter,
            loss: latestLoss,
            connectedClient,
        };
    }, [activeState.output]);

    const copyToClipboard = async (text: string, setFlag: (v: boolean) => void, successMessage: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setFlag(true);
            showToast(successMessage, 'success');
            setTimeout(() => setFlag(false), 1500);
        } catch {
            showToast('Falha ao copiar para a área de transferência.', 'error');
        }
    };

    const handleStartServer = () => {
        const port = parseInt(serverPort, 10);
        if (!port || port < 1 || port > 65535) {
            showToast('Porta inválida. Use 1–65535.', 'error');
            return;
        }
        startIperfServer({ port, sourceIp: serverSourceIp || undefined });
    };

    const handleRunClient = () => {
        const target = clientTarget.trim();
        if (!target) {
            showToast('Informe o endereço do servidor iperf.', 'error');
            return;
        }
        const port = parseInt(clientPort, 10);
        if (!port || port < 1 || port > 65535) {
            showToast('Porta inválida. Use 1–65535.', 'error');
            return;
        }
        let duration = parseInt(clientDuration, 10);
        if (!duration || duration < 1) duration = 10;
        if (duration > 60) duration = 60;
        const parallel = parseInt(clientParallel, 10) || 1;

        runIperfClient(target, {
            port,
            sourceIp: clientSourceIp || undefined,
            duration,
            reverse: clientReverse,
            udp: clientUdp,
            parallel,
        });
    };

    const sourceIpSelect = (value: string, setValue: (v: string) => void, disabled: boolean) => (
        <select
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={disabled}
            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-60"
        >
            <option value="">Automático (escutar em todas as interfaces / 0.0.0.0)</option>
            {activeIps.map(iface => (
                <option key={iface.ip} value={iface.ip}>
                    {iface.name}: {iface.ip}
                </option>
            ))}
            {networks.map(net => {
                if (!net.source_ip || activeIps.some(i => i.ip === net.source_ip)) return null;
                return (
                    <option key={net.id} value={net.source_ip}>
                        {net.name || net.cidr} — {net.source_ip} (Perfil)
                    </option>
                );
            })}
        </select>
    );

    if (status && !status.available) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <AlertTriangle size={48} className="text-amber-500 mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Teste de banda indisponível</h3>
                <p className="text-zinc-400 max-w-md">
                    O binário do iperf2 não foi encontrado nesta instalação. Reinstale ou recompile a versão portátil para utilizar o teste de banda.
                </p>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            {/* Header: Modo Servidor | Cliente e Status do Serviço */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex gap-2 bg-zinc-900 p-1 rounded-xl border border-zinc-800 w-fit">
                    <button
                        onClick={() => setMode('server')}
                        className={clsx(
                            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                            mode === 'server'
                                ? 'bg-zinc-800 text-amber-400 shadow-sm border border-zinc-700/50'
                                : 'text-zinc-400 hover:text-white'
                        )}
                    >
                        <Server size={16} />
                        Servidor (este PC recebe)
                        {iperfServerState.isRunning && (
                            <span className="flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                            </span>
                        )}
                    </button>
                    <button
                        onClick={() => setMode('client')}
                        className={clsx(
                            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                            mode === 'client'
                                ? 'bg-zinc-800 text-cyan-400 shadow-sm border border-zinc-700/50'
                                : 'text-zinc-400 hover:text-white'
                        )}
                    >
                        <Gauge size={16} />
                        Cliente (testar até um servidor)
                        {iperfClientState.isRunning && (
                            <span className="flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                            </span>
                        )}
                    </button>
                </div>

                {/* Status Badge */}
                <div className="flex items-center gap-3">
                    {mode === 'server' && (
                        <div className={clsx(
                            'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium',
                            iperfServerState.isRunning
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
                        )}>
                            <div className={clsx(
                                'w-2 h-2 rounded-full',
                                iperfServerState.isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'
                            )} />
                            <span>
                                {iperfServerState.isRunning
                                    ? `Servidor iPerf Ativo na Porta ${serverPort}`
                                    : 'Servidor iPerf Inativo'}
                            </span>
                        </div>
                    )}
                    {mode === 'client' && (
                        <div className={clsx(
                            'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium',
                            iperfClientState.isRunning
                                ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
                                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
                        )}>
                            <div className={clsx(
                                'w-2 h-2 rounded-full',
                                iperfClientState.isRunning ? 'bg-cyan-400 animate-pulse' : 'bg-zinc-600'
                            )} />
                            <span>
                                {iperfClientState.isRunning
                                    ? `Testando banda para ${clientTarget}:${clientPort}`
                                    : 'Pronto para testar'}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* ===== MODO SERVIDOR ===== */}
            {mode === 'server' && (
                <div className="bg-zinc-900 p-5 rounded-xl border border-zinc-800 space-y-4 shadow-lg shadow-black/20">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                        <div className="md:col-span-3 space-y-1.5">
                            <label className="text-xs font-medium text-zinc-400">Porta de Escuta</label>
                            <input
                                type="text"
                                value={serverPort}
                                onChange={(e) => setServerPort(e.target.value)}
                                disabled={iperfServerState.isRunning}
                                placeholder="5201"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-amber-500 transition-colors font-mono text-sm disabled:opacity-60"
                            />
                        </div>

                        <div className="md:col-span-6 space-y-1.5">
                            <label className="text-xs font-medium text-zinc-400">Vincular a Interface / Rede</label>
                            {sourceIpSelect(serverSourceIp, setServerSourceIp, iperfServerState.isRunning)}
                        </div>

                        <div className="md:col-span-3 flex items-center gap-2">
                            {!iperfServerState.isRunning ? (
                                <button
                                    onClick={handleStartServer}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:border-amber-500/60 transition-all text-sm shadow-sm"
                                >
                                    <Play size={16} />
                                    Iniciar Servidor
                                </button>
                            ) : (
                                <button
                                    onClick={() => stopTool('iperf-server')}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 hover:border-red-500/60 transition-all text-sm shadow-sm"
                                >
                                    <Square size={16} />
                                    Parar Servidor
                                </button>
                            )}
                        </div>
                    </div>

                    {/* IPs Detectados Neste PC */}
                    <div className="space-y-1.5 pt-1">
                        <div className="flex items-center justify-between text-xs text-zinc-400">
                            <span className="font-medium flex items-center gap-1.5">
                                <Wifi size={13} className="text-amber-400" />
                                IP Atual Deste Computador:
                            </span>
                            <span className="text-zinc-500 text-[11px]">Clique em um IP para alterar o comando</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {activeIps.length === 0 ? (
                                <span className="text-xs text-zinc-500 italic">Identificando interfaces de rede...</span>
                            ) : (
                                activeIps.map((iface) => {
                                    const isSelected = serverDisplayIp === iface.ip;
                                    return (
                                        <button
                                            key={iface.ip}
                                            type="button"
                                            onClick={() => {
                                                setSelectedDisplayIp(iface.ip);
                                                showToast(`IP ${iface.ip} (${iface.name}) selecionado no comando`, 'info');
                                            }}
                                            className={clsx(
                                                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-all border',
                                                isSelected
                                                    ? 'bg-amber-500/15 border-amber-500/60 text-amber-300 shadow-sm shadow-amber-500/10 font-bold'
                                                    : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
                                            )}
                                            title={`Interface: ${iface.name} (${iface.cidr || iface.ip})`}
                                        >
                                            <span className={clsx('w-2 h-2 rounded-full', isSelected ? 'bg-amber-400' : 'bg-zinc-600')} />
                                            <span className="text-[11px] text-zinc-400 font-sans font-normal mr-0.5">{iface.name}:</span>
                                            <span className="font-mono">{iface.ip}</span>
                                        </button>
                                    );
                                })
                            )}
                        </div>
                    </div>

                    {/* Caixa de Comando para o Outro Computador */}
                    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-zinc-400 font-medium flex items-center gap-1.5">
                                <Terminal size={14} className="text-emerald-400" />
                                Comando para executar no computador de teste (em qualquer VLAN):
                            </span>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => copyToClipboard(serverDisplayIp, setCopiedIp, 'IP copiado!')}
                                    className="flex items-center gap-1 px-2 py-1 text-[11px] bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded border border-zinc-800 transition-colors"
                                    title="Copiar apenas o endereço IP"
                                >
                                    {copiedIp ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                                    <span>Copiar IP ({serverDisplayIp})</span>
                                </button>
                            </div>
                        </div>

                        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                            <div className="flex-1 font-mono text-sm text-green-400 bg-black/90 border border-zinc-800/80 rounded-lg px-3 py-2.5 break-all flex items-center justify-between">
                                <code>{otherSideCommand}</code>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                                <button
                                    onClick={() => copyToClipboard(otherSideCommand, setCopiedCmd2, 'Comando iperf2 copiado!')}
                                    title="Copiar comando iperf"
                                    className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors border border-zinc-700"
                                >
                                    {copiedCmd2 ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                                    <span>Copiar (iperf)</span>
                                </button>
                                <button
                                    onClick={() => copyToClipboard(otherSideCommandIperf3, setCopiedCmd3, 'Comando iperf3 copiado!')}
                                    title="Copiar comando iperf3"
                                    className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium rounded-lg transition-colors border border-zinc-700"
                                >
                                    {copiedCmd3 ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                                    <span>iperf3</span>
                                </button>
                            </div>
                        </div>

                        {/* Checkbox de Inicialização Automática */}
                        <div className="pt-2 border-t border-zinc-800/70 flex flex-wrap items-center justify-between gap-3">
                            <label className="flex items-center gap-2.5 text-xs text-zinc-300 hover:text-white cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={autostartServer}
                                    onChange={(e) => {
                                        setAutostartServer(e.target.checked);
                                        showToast(
                                            e.target.checked
                                                ? 'Servidor iPerf configurado para iniciar automaticamente ao abrir o programa.'
                                                : 'Inicialização automática do servidor desativada.',
                                            'info'
                                        );
                                    }}
                                    className="w-4 h-4 rounded accent-amber-500 bg-zinc-900 border-zinc-700 cursor-pointer"
                                />
                                <span className="font-medium">Sempre que executar o programa já inicializar o servidor iPerf</span>
                            </label>

                            <button
                                type="button"
                                onClick={() => setShowQuickGuide(!showQuickGuide)}
                                className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1 transition-colors"
                            >
                                <Info size={13} />
                                <span>Como rodar no cliente?</span>
                                {showQuickGuide ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                            </button>
                        </div>

                        {/* Guia Rápido Retrátil */}
                        {showQuickGuide && (
                            <div className="mt-2 p-3 bg-zinc-900/90 border border-zinc-800 rounded-lg text-xs text-zinc-400 space-y-2">
                                <div className="font-semibold text-zinc-200">Instruções para o Computador Remoto:</div>
                                <div className="space-y-1 pl-1">
                                    <p>• <strong>Windows:</strong> Abra o prompt ou PowerShell e execute <code className="text-green-400 font-mono">{otherSideCommand}</code>.</p>
                                    <p>• <strong>Linux / Debian / Ubuntu:</strong> Instale com <code className="text-cyan-400 font-mono">sudo apt install iperf</code> e execute o comando.</p>
                                    <p>• <strong>Redes / VLANs diferentes:</strong> Certifique-se de que a porta TCP <code className="text-amber-400 font-mono">{serverPort}</code> esteja liberada no firewall de entrada deste computador.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ===== MODO CLIENTE ===== */}
            {mode === 'client' && (
                <div className="bg-zinc-900 p-5 rounded-xl border border-zinc-800 space-y-4 shadow-lg shadow-black/20">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                        <div className="md:col-span-5 space-y-1.5">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-medium text-zinc-400">Servidor iPerf Alvo (IP ou Hostname)</label>
                                <button
                                    type="button"
                                    onClick={() => setClientTarget('127.0.0.1')}
                                    disabled={iperfClientState.isRunning}
                                    className="text-[11px] text-cyan-400 hover:underline disabled:opacity-50"
                                >
                                    Testar este PC (localhost)
                                </button>
                            </div>
                            <input
                                type="text"
                                value={clientTarget}
                                onChange={(e) => setClientTarget(e.target.value)}
                                disabled={iperfClientState.isRunning}
                                placeholder="ex.: 10.10.38.10 ou srv-iperf.corp"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500 transition-colors font-mono text-sm disabled:opacity-60"
                                onKeyDown={(e) => { if (e.key === 'Enter' && !iperfClientState.isRunning) handleRunClient(); }}
                            />
                        </div>

                        <div className="md:col-span-2 space-y-1.5">
                            <label className="text-xs font-medium text-zinc-400">Porta</label>
                            <input
                                type="text"
                                value={clientPort}
                                onChange={(e) => setClientPort(e.target.value)}
                                disabled={iperfClientState.isRunning}
                                placeholder="5201"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500 transition-colors font-mono text-sm disabled:opacity-60"
                            />
                        </div>

                        <div className="md:col-span-2 space-y-1.5">
                            <label className="text-xs font-medium text-zinc-400">Duração (segundos)</label>
                            <input
                                type="text"
                                value={clientDuration}
                                onChange={(e) => setClientDuration(e.target.value)}
                                disabled={iperfClientState.isRunning}
                                placeholder="10"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500 transition-colors font-mono text-sm disabled:opacity-60"
                            />
                        </div>

                        <div className="md:col-span-3 space-y-1.5">
                            <label className="text-xs font-medium text-zinc-400">Sair Pela Interface</label>
                            {sourceIpSelect(clientSourceIp, setClientSourceIp, iperfClientState.isRunning)}
                        </div>
                    </div>

                    {/* Presets de Tempo e Seletor Rápido de Hosts */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-zinc-800/60">
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-zinc-500">Duração rápida:</span>
                            {['5', '10', '30', '60'].map((sec) => (
                                <button
                                    key={sec}
                                    type="button"
                                    onClick={() => setClientDuration(sec)}
                                    disabled={iperfClientState.isRunning}
                                    className={clsx(
                                        'px-2 py-0.5 rounded text-xs transition-colors border',
                                        clientDuration === sec
                                            ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-bold'
                                            : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-white'
                                    )}
                                >
                                    {sec}s
                                </button>
                            ))}

                            <span className="text-zinc-600 mx-1">|</span>

                            <span className="text-xs text-zinc-500">Threads (-P):</span>
                            {['1', '2', '4', '8'].map((num) => (
                                <button
                                    key={num}
                                    type="button"
                                    onClick={() => setClientParallel(num)}
                                    disabled={iperfClientState.isRunning}
                                    className={clsx(
                                        'px-2 py-0.5 rounded text-xs transition-colors border',
                                        clientParallel === num
                                            ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-bold'
                                            : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-white'
                                    )}
                                    title={`${num} fluxo(s) paralelo(s)`}
                                >
                                    {num}x
                                </button>
                            ))}
                        </div>

                        {/* Seletor rápido de alvos a partir do Painel */}
                        {hosts.length > 0 && (
                            <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                                <span>Alvo monitorado:</span>
                                <select
                                    onChange={(e) => {
                                        if (e.target.value) setClientTarget(e.target.value);
                                    }}
                                    disabled={iperfClientState.isRunning}
                                    value=""
                                    className="bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded px-2.5 py-1 focus:outline-none focus:border-cyan-500"
                                >
                                    <option value="" disabled>Escolha um host...</option>
                                    {hosts.map(h => (
                                        <option key={h.address} value={h.ip || h.address}>
                                            {h.name || h.hostname || h.address} ({h.ip || h.address})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    {/* Opções Avançadas e Botão de Disparo */}
                    <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
                        <div className="flex items-center gap-6">
                            <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={clientReverse}
                                    onChange={(e) => setClientReverse(e.target.checked)}
                                    disabled={iperfClientState.isRunning}
                                    className="w-4 h-4 rounded accent-cyan-500 bg-zinc-900 border-zinc-700"
                                />
                                <Download size={14} className="text-zinc-400" />
                                <span>Modo Reverso (servidor envia, este PC recebe / download)</span>
                            </label>

                            <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer select-none">
                                <input
                                    type="checkbox"
                                    checked={clientUdp}
                                    onChange={(e) => setClientUdp(e.target.checked)}
                                    disabled={iperfClientState.isRunning}
                                    className="w-4 h-4 rounded accent-cyan-500 bg-zinc-900 border-zinc-700"
                                />
                                <Zap size={14} className="text-zinc-400" />
                                <span>UDP (medição de perda de pacotes e jitter)</span>
                            </label>
                        </div>

                        <div className="flex gap-2">
                            {!iperfClientState.isRunning ? (
                                <button
                                    onClick={handleRunClient}
                                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:border-cyan-500/60 transition-all text-sm shadow-sm"
                                >
                                    <Play size={16} />
                                    Iniciar Teste de Banda
                                </button>
                            ) : (
                                <button
                                    onClick={() => stopTool('iperf-client')}
                                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 hover:border-red-500/60 transition-all text-sm shadow-sm"
                                >
                                    <Square size={16} />
                                    Parar Teste
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ===== DASHBOARD DE MÉTRICAS EM TEMPO REAL ===== */}
            {(liveMetrics.bandwidth || activeState.isRunning || liveMetrics.connectedClient) && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-zinc-900/90 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
                        <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                            <span>Largura de Banda</span>
                            <Gauge size={15} className="text-cyan-400" />
                        </div>
                        <div className="text-xl font-bold text-white font-mono tracking-tight">
                            {liveMetrics.bandwidth || (activeState.isRunning ? 'Medindo...' : '—')}
                        </div>
                        <div className="text-[11px] text-zinc-500 mt-1">
                            {liveMetrics.interval ? `Intervalo: ${liveMetrics.interval}` : 'Taxa de transferência'}
                        </div>
                    </div>

                    <div className="bg-zinc-900/90 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
                        <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                            <span>Volume Transferido</span>
                            <Activity size={15} className="text-emerald-400" />
                        </div>
                        <div className="text-xl font-bold text-emerald-400 font-mono tracking-tight">
                            {liveMetrics.transfer || (activeState.isRunning ? 'Transferindo...' : '—')}
                        </div>
                        <div className="text-[11px] text-zinc-500 mt-1">Total de dados transmitidos</div>
                    </div>

                    <div className="bg-zinc-900/90 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
                        <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                            <span>{liveMetrics.jitter ? 'Jitter / Perda' : 'Conexão'}</span>
                            <Zap size={15} className="text-amber-400" />
                        </div>
                        <div className="text-base font-bold text-zinc-200 font-mono truncate">
                            {liveMetrics.jitter
                                ? `${liveMetrics.jitter} (${liveMetrics.loss || '0%'})`
                                : liveMetrics.connectedClient || (mode === 'server' ? `Porta ${serverPort}` : `${clientTarget || 'Alvo'}`)}
                        </div>
                        <div className="text-[11px] text-zinc-500 mt-1 truncate">
                            {liveMetrics.connectedClient ? `Remoto: ${liveMetrics.connectedClient}` : 'Status do socket'}
                        </div>
                    </div>

                    <div className="bg-zinc-900/90 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between shadow-sm">
                        <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
                            <span>Estado da Sessão</span>
                            <Layers size={15} className="text-blue-400" />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={clsx(
                                'w-2.5 h-2.5 rounded-full',
                                activeState.isRunning ? 'bg-emerald-400 animate-ping' : 'bg-zinc-600'
                            )} />
                            <span className="text-sm font-semibold text-zinc-200">
                                {activeState.isRunning
                                    ? (mode === 'server' ? 'Ouvindo conexões' : 'Teste em andamento')
                                    : 'Sessão concluída'}
                            </span>
                        </div>
                        <div className="text-[11px] text-zinc-500 mt-1">
                            {mode === 'server' ? 'Servidor iperf2' : 'Cliente iperf2'}
                        </div>
                    </div>
                </div>
            )}

            {/* Badge de Última Execução */}
            {activeState.output.length > 0 && activeState.lastRunAt && (
                <LastExecutionBadge
                    timestamp={activeState.lastRunAt}
                    target={mode === 'server' ? `Servidor :${serverPort}` : `Cliente -> ${clientTarget || 'alvo'}:${clientPort}`}
                    onClear={() => clearToolOutput(mode === 'server' ? 'iperf-server' : 'iperf-client')}
                />
            )}

            {/* ===== TERMINAL DE SAÍDA ===== */}
            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm shadow-inner min-h-[220px]">
                {/* Ações do Terminal */}
                <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 bg-zinc-900/90 backdrop-blur-sm border border-zinc-800 rounded-lg p-1">
                    <button
                        onClick={() => copyToClipboard(activeState.output.join('\n'), setCopiedLog, 'Log completo copiado!')}
                        disabled={activeState.output.length === 0}
                        className="p-1.5 text-zinc-400 hover:text-white transition-colors rounded hover:bg-zinc-800 disabled:opacity-30"
                        title="Copiar saída completa do console"
                    >
                        {copiedLog ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                    </button>
                    <button
                        onClick={() => clearToolOutput(mode === 'server' ? 'iperf-server' : 'iperf-client')}
                        disabled={activeState.isRunning || activeState.output.length === 0}
                        className="p-1.5 text-zinc-400 hover:text-red-400 transition-colors rounded hover:bg-zinc-800 disabled:opacity-30"
                        title={activeState.isRunning ? 'Pare o teste para limpar' : 'Limpar saída'}
                    >
                        <Eraser size={14} />
                    </button>
                </div>

                <div
                    ref={consoleContainerRef}
                    onScroll={handleScroll}
                    className="flex-1 overflow-auto custom-scrollbar"
                >
                    {activeState.output.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600 text-center p-6 select-none">
                            <Gauge size={44} className="mb-3 opacity-20" />
                            <p className="font-sans text-sm font-medium">
                                {mode === 'server'
                                    ? 'Inicie o servidor para aguardar conexões de teste de banda de outros PCs da rede.'
                                    : 'Informe o endereço do servidor de destino e clique em Iniciar Teste de Banda.'}
                            </p>
                            <p className="font-sans text-xs text-zinc-600 mt-1">
                                Os pacotes e métricas aparecerão aqui em tempo real durante a transmissão.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-0.5">
                            {activeState.output.map((line, i) => {
                                const isSummary = line.includes('0.0-') && (line.includes('GBytes') || line.includes('MBytes'));
                                const isConnected = line.includes('connected with');
                                const isError = line.toLowerCase().includes('erro') || line.toLowerCase().includes('failed');

                                return (
                                    <div
                                        key={i}
                                        className={clsx(
                                            'whitespace-pre-wrap break-all text-xs leading-relaxed',
                                            isError ? 'text-red-400 font-semibold' :
                                            isConnected ? 'text-cyan-400 font-semibold bg-cyan-950/20 px-1 rounded' :
                                            isSummary ? 'text-emerald-300 font-bold bg-emerald-950/20 px-1 rounded' :
                                            'text-zinc-300'
                                        )}
                                    >
                                        {line}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                    <div ref={outputEndRef} />
                </div>
            </div>
        </div>
    );
}
