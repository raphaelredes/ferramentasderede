import { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Play, Square, Terminal as TerminalIcon, Eraser, Network as NetworkIcon, Activity } from 'lucide-react';
import { clsx } from 'clsx';
import { NetworkScanner } from '../components/Tools/NetworkScanner';
import { Host } from '../types';
import { useTools } from '../contexts/ToolsContext';

export function Tools() {
    const [activeTab, setActiveTab] = useState<'ping' | 'traceroute' | 'scanner'>('ping');

    // Use Global Context
    const {
        pingState,
        traceState,
        runPing,
        runTraceroute,
        stopTool,
        clearToolOutput
    } = useTools();

    const [localPingTarget, setLocalPingTarget] = useState('8.8.8.8');
    const [localTraceTarget, setLocalTraceTarget] = useState('8.8.8.8');

    const outputEndRef = useRef<HTMLDivElement>(null);
    const [existingHosts, setExistingHosts] = useState<Host[]>([]);

    const scrollToBottom = () => {
        outputEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    // Scroll on output change
    useEffect(() => {
        scrollToBottom();
    }, [pingState.output, traceState.output, activeTab]);

    // Handle navigation state
    const location = useLocation();
    useEffect(() => {
        if (location.state) {
            const { target, tool, autoRun } = location.state as { target?: string; tool?: 'ping' | 'traceroute'; autoRun?: boolean };

            if (tool) {
                setActiveTab(tool);
            }

            if (target) {
                if (tool === 'ping' || !tool) {
                    setLocalPingTarget(target);
                    if (autoRun && !pingState.isRunning) {
                        runPing(target);
                    }
                }
                if (tool === 'traceroute') {
                    setLocalTraceTarget(target);
                    if (autoRun && !traceState.isRunning) {
                        runTraceroute(target);
                    }
                }
            }

            // Clear state to prevent re-running on simple re-renders (though location.state persists until navigation)
            // Ideally we'd replace history but for now this is fine as long as we check isRunning
            window.history.replaceState({}, document.title);
        }
    }, [location.state, runPing, runTraceroute, pingState.isRunning, traceState.isRunning]);

    // Fetch existing hosts on mount
    useEffect(() => {
        fetch('http://127.0.0.1:8000/hosts')
            .then(res => res.json())
            .then(data => setExistingHosts(data))
            .catch(console.error);
    }, []);

    const handleAddHost = async (host: Host) => {
        try {
            const res = await fetch('http://127.0.0.1:8000/hosts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(host),
            });

            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.detail || 'Erro ao adicionar host');
            }

            // Refresh existing hosts
            const hostsRes = await fetch('http://127.0.0.1:8000/hosts');
            const hostsData = await hostsRes.json();
            setExistingHosts(hostsData);

        } catch (error) {
            console.error('Failed to add host:', error);
            alert('Erro ao adicionar host: ' + (error as Error).message);
        }
    };

    const renderDiagnosticTool = (
        type: 'ping' | 'traceroute',
        state: { isRunning: boolean; output: string[] },
        target: string,
        setTarget: (t: string) => void,
        run: (t: string) => void,
        stop: () => void,
        clear: () => void,
        icon: React.ReactNode,
        colorClass: string,
        borderColorClass: string
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
                            if (e.key === 'Enter' && !state.isRunning) run(target || '8.8.8.8');
                        }}
                    />
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={() => run(target || '8.8.8.8')}
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

            <div className="flex gap-2 border-b border-zinc-800">
                <button
                    onClick={() => setActiveTab('ping')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'ping' ? 'border-blue-500 text-blue-500' : 'border-transparent text-zinc-400 hover:text-white'}`}
                >
                    <Activity size={16} />
                    Ping
                    {pingState.isRunning && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}
                </button>
                <button
                    onClick={() => setActiveTab('traceroute')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'traceroute' ? 'border-purple-500 text-purple-500' : 'border-transparent text-zinc-400 hover:text-white'}`}
                >
                    <NetworkIcon size={16} />
                    Traceroute
                    {traceState.isRunning && <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />}
                </button>
                <button
                    onClick={() => setActiveTab('scanner')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'scanner' ? 'border-green-500 text-green-500' : 'border-transparent text-zinc-400 hover:text-white'}`}
                >
                    <TerminalIcon size={16} />
                    Scanner de Rede
                </button>
            </div>

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
                'border-blue-900/30 hover:border-blue-500/50'
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
                'border-purple-900/30 hover:border-purple-500/50'
            )}

            {activeTab === 'scanner' && (
                <NetworkScanner onAddHost={handleAddHost} existingHosts={existingHosts} />
            )}
        </div>
    );
}
