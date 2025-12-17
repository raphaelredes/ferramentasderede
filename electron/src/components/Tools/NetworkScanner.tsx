import React, { useEffect } from 'react';
import {
    Search,
    Play,
    Square,
    Monitor,
    Wifi,
    Server,
    Laptop,
    Globe,
    Cpu,
    Plus,
    X,
    LayoutList
} from 'lucide-react';
import { Host } from '../../types';
import { useTools } from '../../contexts/ToolsContext';
import { useLoading } from '../../contexts/LoadingContext';

interface NetworkScannerProps {
    onAddHost: (host: Host) => void;
    existingHosts: Host[];
}



export const NetworkScanner: React.FC<NetworkScannerProps> = ({ onAddHost, existingHosts }) => {
    const {
        scanSessions,
        activeSessionId,
        createScanSession,
        closeScanSession,
        updateScanSession,
        setActiveSessionId,
        runScanSession
    } = useTools();

    const { setLoading } = useLoading();

    // Update global loading state whenever sessions change
    useEffect(() => {
        const isAnySessionRunning = scanSessions.some(s => s.isRunning);
        setLoading('tools', isAnySessionRunning);
    }, [scanSessions, setLoading]);

    // Initialize with a default session if empty
    useEffect(() => {
        const init = async () => {
            if (scanSessions.length === 0) {
                let defaultCidr = '';
                try {
                    // Try settings first
                    const settingsRes = await fetch('http://localhost:8000/settings');
                    const settingsData = await settingsRes.json();
                    if (settingsData.scanner?.default_cidr) {
                        defaultCidr = settingsData.scanner.default_cidr;
                    } else {
                        // Fallback to local network
                        const localRes = await fetch('http://localhost:8000/network/local');
                        const localData = await localRes.json();
                        if (localData.network) {
                            defaultCidr = localData.network;
                        }
                    }
                } catch (e) {
                    console.error("Failed to init default CIDR", e);
                }

                if (defaultCidr) {
                    createScanSession(defaultCidr);
                } else {
                    createScanSession('');
                }
            }
        };
        // Only run if absolutely no sessions (first load)
        if (scanSessions.length === 0) {
            init();
        }
    }, []); // Empty dependency array to run only once on mount if empty

    // Ensure active session is set if sessions exist but active is null
    useEffect(() => {
        if (scanSessions.length > 0 && !activeSessionId) {
            setActiveSessionId(scanSessions[0].id);
        }
    }, [scanSessions, activeSessionId, setActiveSessionId]);

    const handleCloseSession = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        closeScanSession(id);
    };

    const startScan = (sessionId: string) => {
        runScanSession(sessionId);
    };

    const getVendorIcon = (vendor: string, hostname: string) => {
        const v = (vendor || '').toLowerCase();
        const h = (hostname || '').toLowerCase();

        if (v.includes('apple')) return <Laptop className="text-zinc-400" />;
        if (v.includes('microsoft') || h.includes('desktop') || h.includes('laptop')) return <Monitor className="text-blue-400" />;
        if (v.includes('vmware') || v.includes('virtualbox') || v.includes('qemu')) return <Server className="text-purple-400" />;
        if (v.includes('raspberry') || v.includes('ubiquiti') || v.includes('cisco')) return <Wifi className="text-orange-400" />;
        if (v.includes('intel') || v.includes('dell') || v.includes('hp')) return <Cpu className="text-zinc-400" />;

        return <Globe className="text-zinc-500" />;
    };

    const activeSession = scanSessions.find(s => s.id === activeSessionId);

    return (
        <div className="flex flex-col h-full bg-zinc-950/50 rounded-xl border border-zinc-800/50 overflow-hidden">
            {/* Tabs Header */}
            <div className="flex items-center bg-zinc-900/50 border-b border-zinc-800/50 overflow-x-auto no-scrollbar">
                {scanSessions.map(session => (
                    <div
                        key={session.id}
                        onClick={() => setActiveSessionId(session.id)}
                        className={`
                            group flex items-center gap-2 px-4 py-3 text-sm font-medium cursor-pointer border-r border-zinc-800/50 min-w-[160px] max-w-[240px] transition-colors
                            ${activeSessionId === session.id
                                ? 'bg-zinc-800/50 text-white border-b-2 border-b-blue-500'
                                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30'}
                        `}
                    >
                        <div className="flex-1 truncate flex items-center gap-2">
                            {session.isRunning ? <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" /> : <LayoutList size={14} />}
                            <span className="truncate">{session.cidr || 'Nova Varredura'}</span>
                        </div>
                        <button
                            onClick={(e) => handleCloseSession(session.id, e)}
                            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-zinc-700 rounded-full transition-all"
                        >
                            <X size={12} />
                        </button>
                    </div>
                ))}
                <button
                    onClick={() => createScanSession('')}
                    className="p-3 text-zinc-500 hover:text-white hover:bg-zinc-800/50 transition-colors"
                    title="Nova Aba"
                >
                    <Plus size={18} />
                </button>
            </div>

            {/* Active Session Content */}
            {activeSession && (
                <div className="flex flex-col flex-1 overflow-hidden">
                    {/* Controls */}
                    <div className="p-4 border-b border-zinc-800/50 bg-zinc-900/30 flex items-center gap-4">
                        <div className="flex-1 flex items-center gap-2 bg-zinc-900/50 border border-zinc-800 rounded-lg px-3 py-2">
                            <Search size={18} className="text-zinc-500" />
                            <input
                                type="text"
                                value={activeSession.cidr}
                                onChange={(e) => updateScanSession(activeSession.id, { cidr: e.target.value })}
                                placeholder="Ex: 192.168.1.0/24"
                                className="bg-transparent border-none outline-none text-zinc-200 text-sm w-full placeholder-zinc-600"
                                disabled={activeSession.isRunning}
                                onKeyDown={(e) => e.key === 'Enter' && startScan(activeSession.id)}
                            />
                        </div>

                        <button
                            onClick={() => startScan(activeSession.id)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all border ${activeSession.isRunning
                                ? 'bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20'
                                : 'bg-zinc-800 hover:bg-zinc-700 text-blue-400 border-blue-900/30 hover:border-blue-500/50'
                                }`}
                        >
                            {activeSession.isRunning ? (
                                <>
                                    <Square size={16} fill="currentColor" />
                                    Parar
                                </>
                            ) : (
                                <>
                                    <Play size={16} fill="currentColor" />
                                    Escanear
                                </>
                            )}
                        </button>
                    </div>

                    {/* Status Bar */}
                    {(activeSession.isRunning || activeSession.status) && (
                        <div className="px-4 py-2 bg-zinc-900/50 border-b border-zinc-800/50 text-xs text-zinc-400 flex items-center justify-between">
                            <span>{activeSession.status}</span>
                            {activeSession.isRunning && (
                                <div className="flex items-center gap-2">
                                    <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-blue-500 transition-all duration-300"
                                            style={{ width: `${activeSession.progress}%` }}
                                        />
                                    </div>
                                    <span className="text-blue-500">{activeSession.progress}%</span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Results Grid */}
                    <div className="flex-1 overflow-y-auto p-4">
                        {activeSession.results.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-500 gap-4">
                                <div className="w-16 h-16 rounded-2xl bg-zinc-900/50 flex items-center justify-center border border-zinc-800/50">
                                    <Search size={32} className="opacity-50" />
                                </div>
                                <p className="text-sm">Inicie uma varredura para encontrar dispositivos na rede.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                                {activeSession.results.map((host) => {
                                    const isAdded = existingHosts.some(h => h.address === host.ip);

                                    return (
                                        <div key={host.ip} className="group bg-zinc-900/30 hover:bg-zinc-800/50 border border-zinc-800/50 hover:border-zinc-700 rounded-xl p-3 transition-all duration-200">
                                            <div className="flex items-start justify-between mb-2">
                                                <div className="p-2 bg-zinc-950 rounded-lg border border-zinc-800 group-hover:border-zinc-700 transition-colors">
                                                    {getVendorIcon(host.vendor, host.hostname)}
                                                </div>
                                                <div className={`w-2 h-2 rounded-full ${host.status === 'online' ? 'bg-green-500' : 'bg-zinc-700'}`} />
                                            </div>

                                            <div className="mb-3">
                                                <h3 className="text-zinc-100 font-medium text-lg tracking-tight">{host.ip}</h3>
                                                <p className="text-zinc-400 text-xs truncate" title={host.hostname || 'Sem hostname'}>
                                                    {host.hostname || 'Unknown Host'}
                                                </p>
                                            </div>

                                            <div className="space-y-1 mb-3">
                                                <div className="flex items-center justify-between text-[10px] text-zinc-500">
                                                    <span>MAC</span>
                                                    <span className="font-mono text-zinc-400">{host.mac || 'Desconhecido'}</span>
                                                </div>
                                                <div className="flex items-center justify-between text-[10px] text-zinc-500">
                                                    <span>Vendor</span>
                                                    <span className="text-zinc-400 truncate max-w-[100px]" title={host.vendor}>{host.vendor || 'Desconhecido'}</span>
                                                </div>
                                            </div>

                                            <button
                                                onClick={() => !isAdded && onAddHost({
                                                    address: host.ip,
                                                    name: host.hostname || host.ip,
                                                    type: 'generic',
                                                    monitoring: true,
                                                    mac: host.mac,
                                                    vendor: host.vendor,
                                                    hostname: host.hostname
                                                })}
                                                disabled={isAdded}
                                                className={`w-full py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${isAdded
                                                    ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                                                    : 'bg-zinc-800 hover:bg-blue-600 text-zinc-300 hover:text-white border border-zinc-700 hover:border-blue-500'
                                                    }`}
                                            >
                                                {isAdded ? (
                                                    <>Adicionado</>
                                                ) : (
                                                    <>
                                                        <Plus size={12} />
                                                        Adicionar no painel
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div >
    );
};
