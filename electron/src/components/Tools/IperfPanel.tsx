import { useEffect, useRef, useState } from 'react';
import { Play, Square, Eraser, Server, Download, Copy, Check, AlertTriangle, Gauge } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useTools } from '../../contexts/ToolsContext';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';

import { usePersistedState } from '../../hooks/usePersistedState';

interface IperfStatus {
    available: boolean;
    version: string | null;
    path: string | null;
}

/**
 * Bandwidth-test panel (iperf2). Two modes:
 *  - Servidor: this machine listens; operators on other VLANs run the client
 *    against it. This is the primary use case ("test bandwidth up to the
 *    machine running the app").
 *  - Cliente: this machine probes an existing iperf server on the network.
 *
 * The source-IP selector picks the egress/listen NIC (multi-VLAN), mirroring
 * the Ping/Traceroute selectors.
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

    const [mode, setMode] = usePersistedState<'server' | 'client'>('iperf_tool_mode', 'server');

    // Server form
    const [serverPort, setServerPort] = usePersistedState('iperf_tool_server_port', '5201');
    const [serverSourceIp, setServerSourceIp] = usePersistedState('iperf_tool_server_source_ip', '');

    // Client form
    const [clientTarget, setClientTarget] = usePersistedState('iperf_tool_client_target', '');
    const [clientPort, setClientPort] = usePersistedState('iperf_tool_client_port', '5201');
    const [clientSourceIp, setClientSourceIp] = usePersistedState('iperf_tool_client_source_ip', '');
    const [clientDuration, setClientDuration] = usePersistedState('iperf_tool_client_duration', '10');
    const [clientReverse, setClientReverse] = usePersistedState('iperf_tool_client_reverse', false);
    const [clientUdp, setClientUdp] = usePersistedState('iperf_tool_client_udp', false);


    const [status, setStatus] = useState<IperfStatus | null>(null);
    const [copied, setCopied] = useState(false);
    const outputEndRef = useRef<HTMLDivElement>(null);

    // Probe binary availability so we can disable the panel with a clear
    // message instead of failing mid-stream.
    useEffect(() => {
        fetch(`${API_BASE}/tools/iperf/status`)
            .then(res => res.json())
            .then(setStatus)
            .catch(err => {
                console.debug('IperfPanel: status probe failed:', err);
                setStatus({ available: false, version: null, path: null });
            });
    }, []);

    const activeState = mode === 'server' ? iperfServerState : iperfClientState;

    // Auto-scroll the output to the bottom on new lines.
    useEffect(() => {
        outputEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [activeState.output]);

    // IP the operator should hand to the other side. Prefer the bound source IP
    // (server mode), else the first configured network source IP, else a hint.
    const serverDisplayIp = serverSourceIp
        || networks.find(n => n.source_ip)?.source_ip
        || '<IP-deste-PC>';
    const otherSideCommand = `iperf -c ${serverDisplayIp} -p ${serverPort || '5201'}`;

    const copyCommand = async () => {
        try {
            await navigator.clipboard.writeText(otherSideCommand);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch (e) {
            showToast('Não foi possível copiar o comando.', 'error');
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
        runIperfClient(target, {
            port,
            sourceIp: clientSourceIp || undefined,
            duration,
            reverse: clientReverse,
            udp: clientUdp,
        });
    };

    // Reusable source-IP <select> (egress/listen NIC).
    const sourceIpSelect = (value: string, setValue: (v: string) => void, disabled: boolean) => (
        <select
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={disabled}
            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-60"
        >
            <option value="">Automático (rota padrão)</option>
            {networks.map(net => (
                <option key={net.id} value={net.source_ip ?? ''} disabled={!net.source_ip}>
                    {net.name || net.cidr}
                    {net.source_ip ? ` — ${net.source_ip}` : ' (sem source IP)'}
                </option>
            ))}
        </select>
    );

    if (status && !status.available) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <AlertTriangle size={48} className="text-amber-500 mb-4" />
                <h3 className="text-lg font-semibold text-white mb-2">Teste de banda indisponível</h3>
                <p className="text-zinc-400 max-w-md">
                    O binário do iperf não foi encontrado nesta instalação. O teste de banda
                    requer o iperf empacotado no aplicativo. Reinstale a versão portátil mais recente.
                </p>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            {/* Sub-toggle Servidor | Cliente */}
            <div className="flex gap-2 bg-zinc-900 p-1 rounded-xl border border-zinc-800 w-fit">
                <button
                    onClick={() => setMode('server')}
                    className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        mode === 'server' ? 'bg-zinc-800 text-amber-400' : 'text-zinc-400 hover:text-white'
                    )}
                >
                    <Server size={16} />
                    Servidor (este PC recebe)
                    {iperfServerState.isRunning && <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />}
                </button>
                <button
                    onClick={() => setMode('client')}
                    className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        mode === 'client' ? 'bg-zinc-800 text-cyan-400' : 'text-zinc-400 hover:text-white'
                    )}
                >
                    <Gauge size={16} />
                    Cliente (testar até um servidor)
                    {iperfClientState.isRunning && <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />}
                </button>
            </div>

            {/* ===== SERVIDOR ===== */}
            {mode === 'server' && (
                <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-4">
                    <div className="flex gap-4 items-end">
                        <div className="space-y-2 w-32">
                            <label className="text-sm font-medium text-zinc-400">Porta</label>
                            <input
                                type="text"
                                value={serverPort}
                                onChange={(e) => setServerPort(e.target.value)}
                                disabled={iperfServerState.isRunning}
                                placeholder="5201"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono disabled:opacity-60"
                            />
                        </div>
                        <div className="space-y-2 w-64">
                            <label className="text-sm font-medium text-zinc-400">Escutar na rede</label>
                            {sourceIpSelect(serverSourceIp, setServerSourceIp, iperfServerState.isRunning)}
                        </div>
                        <div className="flex gap-2">
                            {!iperfServerState.isRunning ? (
                                <button
                                    onClick={handleStartServer}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-amber-400 border border-amber-900/30 hover:border-amber-500/50 transition-colors"
                                >
                                    <Play size={18} />
                                    Iniciar servidor
                                </button>
                            ) : (
                                <button
                                    onClick={() => stopTool('iperf-server')}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                                >
                                    <Square size={18} />
                                    Parar
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Comando para o outro lado */}
                    <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3">
                        <p className="text-xs text-zinc-500 mb-2">
                            No <strong className="text-zinc-300">outro computador</strong> (em qualquer VLAN), rode este comando para medir a banda até aqui:
                        </p>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 font-mono text-sm text-green-400 bg-black rounded px-3 py-2 break-all">
                                {otherSideCommand}
                            </code>
                            <button
                                onClick={copyCommand}
                                title="Copiar comando"
                                className="p-2 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors shrink-0"
                            >
                                {copied ? <Check size={16} className="text-green-400" /> : <Copy size={16} />}
                            </button>
                        </div>
                        {serverDisplayIp === '<IP-deste-PC>' && (
                            <p className="text-xs text-amber-500/80 mt-2">
                                Dica: selecione uma rede acima (ou cadastre o source IP em Configurações) para mostrar o IP exato deste PC no comando.
                            </p>
                        )}
                    </div>
                </div>
            )}

            {/* ===== CLIENTE ===== */}
            {mode === 'client' && (
                <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-4">
                    <div className="flex gap-4 items-end flex-wrap">
                        <div className="flex-1 min-w-48 space-y-2">
                            <label className="text-sm font-medium text-zinc-400">Servidor iperf (IP ou hostname)</label>
                            <input
                                type="text"
                                value={clientTarget}
                                onChange={(e) => setClientTarget(e.target.value)}
                                disabled={iperfClientState.isRunning}
                                placeholder="192.168.1.10"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono disabled:opacity-60"
                                onKeyDown={(e) => { if (e.key === 'Enter' && !iperfClientState.isRunning) handleRunClient(); }}
                            />
                        </div>
                        <div className="space-y-2 w-24">
                            <label className="text-sm font-medium text-zinc-400">Porta</label>
                            <input
                                type="text"
                                value={clientPort}
                                onChange={(e) => setClientPort(e.target.value)}
                                disabled={iperfClientState.isRunning}
                                placeholder="5201"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono disabled:opacity-60"
                            />
                        </div>
                        <div className="space-y-2 w-24">
                            <label className="text-sm font-medium text-zinc-400">Duração (s)</label>
                            <input
                                type="text"
                                value={clientDuration}
                                onChange={(e) => setClientDuration(e.target.value)}
                                disabled={iperfClientState.isRunning}
                                placeholder="10"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono disabled:opacity-60"
                            />
                        </div>
                        <div className="space-y-2 w-56">
                            <label className="text-sm font-medium text-zinc-400">Sair pela rede</label>
                            {sourceIpSelect(clientSourceIp, setClientSourceIp, iperfClientState.isRunning)}
                        </div>
                    </div>

                    <div className="flex items-center gap-6">
                        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={clientReverse}
                                onChange={(e) => setClientReverse(e.target.checked)}
                                disabled={iperfClientState.isRunning}
                                className="accent-cyan-500"
                            />
                            <Download size={14} className="text-zinc-400" />
                            Reverso (servidor envia, este PC recebe)
                        </label>
                        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={clientUdp}
                                onChange={(e) => setClientUdp(e.target.checked)}
                                disabled={iperfClientState.isRunning}
                                className="accent-cyan-500"
                            />
                            UDP
                        </label>

                        <div className="flex gap-2 ml-auto">
                            {!iperfClientState.isRunning ? (
                                <button
                                    onClick={handleRunClient}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-cyan-400 border border-cyan-900/30 hover:border-cyan-500/50 transition-colors"
                                >
                                    <Play size={18} />
                                    Testar banda
                                </button>
                            ) : (
                                <button
                                    onClick={() => stopTool('iperf-client')}
                                    className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-red-400 border border-red-900/30 hover:border-red-500/50 transition-colors"
                                >
                                    <Square size={18} />
                                    Parar
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ===== SAÍDA ===== */}
            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-4 overflow-hidden flex flex-col relative font-mono text-sm">
                <div className="absolute top-2 right-2 z-10">
                    <button
                        onClick={() => clearToolOutput(mode === 'server' ? 'iperf-server' : 'iperf-client')}
                        disabled={activeState.isRunning}
                        className="p-2 text-zinc-500 hover:text-white transition-colors rounded-lg hover:bg-zinc-800 disabled:opacity-30 disabled:hover:text-zinc-500 disabled:hover:bg-transparent"
                        title={activeState.isRunning ? 'Pare para limpar' : 'Limpar'}
                    >
                        <Eraser size={16} />
                    </button>
                </div>
                <div className="flex-1 overflow-auto custom-scrollbar">
                    {activeState.output.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                            <Gauge size={48} className="mb-4 opacity-20" />
                            <p>{mode === 'server' ? 'Inicie o servidor para receber testes de banda.' : 'Informe um servidor e teste a banda.'}</p>
                        </div>
                    ) : (
                        activeState.output.map((line, i) => (
                            <div key={i} className="whitespace-pre-wrap break-all text-zinc-300 leading-tight">
                                {line}
                            </div>
                        ))
                    )}
                    <div ref={outputEndRef} />
                </div>
            </div>
        </div>
    );
}
