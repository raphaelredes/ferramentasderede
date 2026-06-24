import React, { useEffect, useRef } from 'react';
import { API_BASE } from '../../config/api';
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
    LayoutList,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Upload,
    HelpCircle,
    Pin,
    PinOff
} from 'lucide-react';
import { Host } from '../../types';
import { useTools } from '../../contexts/ToolsContext';
import { useNetworks } from '../../hooks/useNetworks';

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
        renameScanSession,
        togglePinScanSession,
        setActiveSessionId,
        runScanSession,
        stopTool
    } = useTools();

    // Inline-rename state: which tab is being renamed + its draft text.
    const [renamingId, setRenamingId] = React.useState<string | null>(null);
    const [renameDraft, setRenameDraft] = React.useState('');

    const startRename = (session: { id: string; name?: string; cidr: string }) => {
        setRenamingId(session.id);
        setRenameDraft(session.name || session.cidr || '');
    };
    const commitRename = () => {
        if (renamingId) renameScanSession(renamingId, renameDraft);
        setRenamingId(null);
        setRenameDraft('');
    };

    const { networks } = useNetworks();

    const hasInitialized = useRef(false);

    // Initialize with a default session if empty
    useEffect(() => {
        const init = async () => {
            if (hasInitialized.current) return;
            hasInitialized.current = true;

            if (scanSessions.length === 0) {
                let defaultCidr = '';
                try {
                    // Try settings first
                    const settingsRes = await fetch(`${API_BASE}/settings`);
                    const settingsData = await settingsRes.json();
                    if (settingsData.scanner?.default_cidr) {
                        defaultCidr = settingsData.scanner.default_cidr;
                    } else {
                        // Fallback to local network
                        const localRes = await fetch(`${API_BASE}/network/local`);
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

    const toggleScan = (session: { id: string; isRunning: boolean }) => {
        // Explicit branch instead of relying on runScanSession's internal
        // re-entry detection. A double click here used to be able to spawn
        // a second pass before the first stop took effect.
        if (session.isRunning) {
            stopTool('scanner', session.id);
        } else {
            runScanSession(session.id);
        }
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

    // Sorting State
    const [sortBy, setSortBy] = React.useState<'ip' | 'name' | 'vendor'>('ip');
    const [sortDirection, setSortDirection] = React.useState<'asc' | 'desc'>('asc');
    const [viewMode, setViewMode] = React.useState<'results' | 'available'>('results');

    const sortHosts = (hosts: any[]) => {
        return [...hosts].sort((a, b) => {
            let comparison = 0;
            switch (sortBy) {
                case 'ip': {
                    // Coalesce ip to a known-good value before split — defensive
                    // against the same null-IP corner that crashed host sort
                    // elsewhere.
                    const ipA = (a.ip ?? '0.0.0.0').split('.').map(Number);
                    const ipB = (b.ip ?? '0.0.0.0').split('.').map(Number);
                    for (let i = 0; i < 4; i++) {
                        const av = Number.isFinite(ipA[i]) ? ipA[i] : 0;
                        const bv = Number.isFinite(ipB[i]) ? ipB[i] : 0;
                        if (av !== bv) {
                            comparison = av - bv;
                            break;
                        }
                    }
                    break;
                }
                case 'name': {
                    const nameA = (a.hostname || a.ip || '').toLowerCase();
                    const nameB = (b.hostname || b.ip || '').toLowerCase();
                    comparison = nameA.localeCompare(nameB);
                    break;
                }
                case 'vendor': {
                    const vendorA = (a.vendor || '').toLowerCase();
                    const vendorB = (b.vendor || '').toLowerCase();
                    comparison = vendorA.localeCompare(vendorB);
                    break;
                }
            }
            return sortDirection === 'asc' ? comparison : -comparison;
        });
    };

    const sortedResults = activeSession ? sortHosts(activeSession.results) : [];

    const exportToCSV = async () => {
        if (!activeSession) return;

        let csvContent = '';
        let filename = '';

        // RFC-4180 quoting: wrap in quotes and double any internal quote.
        // Vendor names from IEEE can contain commas/quotes; the old `"${cell}"`
        // produced malformed CSV for those.
        const csvCell = (value: unknown) => `"${String(value ?? '').replace(/"/g, '""')}"`;

        if (viewMode === 'results') {
            if (activeSession.results.length === 0) return;

            const headers = ['IP', 'Hostname', 'Fabricante', 'Tipo', 'MAC', 'Status'];
            const rows = activeSession.results.map(host => [
                host.ip,
                host.hostname || '',
                host.vendor || '',
                host.device_type ? `${host.device_type}${host.device_type_guess ? ' (provável)' : ''}` : '',
                host.mac || '',
                host.status
            ]);

            csvContent = [
                headers.map(csvCell).join(','),
                ...rows.map(row => row.map(csvCell).join(','))
            ].join('\n');

            filename = `scan_results_${activeSession.cidr.replace(/[\/\\]/g, '_')}_${new Date().toISOString().slice(0, 10)}.csv`;
        } else if (viewMode === 'available') {
            if (!activeSession.availableRanges || activeSession.availableRanges.length === 0) return;

            const headers = ['IP/Range'];
            const rows = activeSession.availableRanges.map(range => [range]);

            csvContent = [
                headers.map(csvCell).join(','),
                ...rows.map(row => row.map(csvCell).join(','))
            ].join('\n');

            filename = `available_ips_${activeSession.cidr.replace(/[\/\\]/g, '_')}_${new Date().toISOString().slice(0, 10)}.csv`;
        }

        if (!csvContent) return;

        try {
            let path: string | null = null;
            if (window.electron && window.electron.saveFileAs) {
                path = await window.electron.saveFileAs(filename, csvContent);
            } else if (window.pywebview?.api?.saveFileAs) {
                path = await window.pywebview.api.saveFileAs(filename, csvContent);
            }

            if (path) {
                if (window.electron && window.electron.showItemInFolder) {
                    window.electron.showItemInFolder(path);
                } else if (window.pywebview?.api?.showItemInFolder) {
                    window.pywebview.api.showItemInFolder(path);
                }
            }
        } catch (e) {
            console.error("Error exporting CSV:", e);
        }
    };

    const [showInfoModal, setShowInfoModal] = React.useState(false);

    return (
        <div className="flex flex-col h-full bg-zinc-950/50 rounded-xl border border-zinc-800/50 overflow-hidden">
            {/* Tabs Header */}
            <div className="flex items-center bg-zinc-900/50 border-b border-zinc-800/50 overflow-x-auto no-scrollbar">
                {scanSessions.map(session => (
                    <div
                        key={session.id}
                        onClick={() => renamingId !== session.id && setActiveSessionId(session.id)}
                        className={`
                            group flex items-center gap-2 px-4 py-3 text-sm font-medium cursor-pointer border-r border-zinc-800/50 min-w-[160px] max-w-[240px] transition-colors
                            ${activeSessionId === session.id
                                ? 'bg-zinc-800/50 text-white border-b-2 border-b-blue-500'
                                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30'}
                        `}
                    >
                        <div className="flex-1 truncate flex items-center gap-2">
                            {session.pinned
                                ? <Pin size={14} className="text-blue-400 shrink-0" fill="currentColor" />
                                : session.isRunning
                                    ? <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                                    : <LayoutList size={14} className="shrink-0" />}
                            {renamingId === session.id ? (
                                <input
                                    autoFocus
                                    value={renameDraft}
                                    onChange={(e) => setRenameDraft(e.target.value)}
                                    onClick={(e) => e.stopPropagation()}
                                    onBlur={commitRename}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') commitRename();
                                        else if (e.key === 'Escape') { setRenamingId(null); setRenameDraft(''); }
                                    }}
                                    placeholder={session.cidr || 'Nome da aba'}
                                    className="flex-1 min-w-0 bg-zinc-950 border border-blue-500/50 rounded px-1.5 py-0.5 text-sm text-white outline-none"
                                />
                            ) : (
                                <span
                                    className="truncate"
                                    title="Duplo-clique para renomear"
                                    onDoubleClick={(e) => { e.stopPropagation(); startRename(session); }}
                                >
                                    {session.name || session.cidr || 'Nova Varredura'}
                                </span>
                            )}
                        </div>
                        {renamingId !== session.id && (
                            <div className="flex items-center gap-0.5">
                                <button
                                    onClick={(e) => { e.stopPropagation(); togglePinScanSession(session.id); }}
                                    className={`p-1 rounded-full transition-all hover:bg-zinc-700 ${session.pinned ? 'text-blue-400 opacity-100' : 'opacity-0 group-hover:opacity-100 text-zinc-400'}`}
                                    title={session.pinned ? 'Desafixar aba' : 'Fixar aba'}
                                >
                                    {session.pinned ? <PinOff size={12} /> : <Pin size={12} />}
                                </button>
                                {!session.pinned && (
                                    <button
                                        onClick={(e) => handleCloseSession(session.id, e)}
                                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-zinc-700 rounded-full transition-all"
                                        title="Fechar aba"
                                    >
                                        <X size={12} />
                                    </button>
                                )}
                            </div>
                        )}
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
                                onKeyDown={(e) => e.key === 'Enter' && !activeSession.isRunning && toggleScan(activeSession)}
                            />
                        </div>

                        <select
                            value={activeSession.sourceIp ?? ''}
                            onChange={(e) => {
                                const sel = e.target.value;
                                const net = networks.find(n => n.source_ip === sel);
                                updateScanSession(activeSession.id, {
                                    sourceIp: sel || undefined,
                                    // Auto-preencher o CIDR se a rede tiver um e o campo estiver vazio ou inalterado
                                    cidr: net?.cidr && !activeSession.cidr ? net.cidr : activeSession.cidr,
                                });
                            }}
                            disabled={activeSession.isRunning}
                            title="Sair pela rede (NIC source) — útil em multi-VLAN"
                            className="bg-zinc-900/50 border border-zinc-800 text-zinc-300 px-3 py-2 rounded-lg text-sm focus:outline-none focus:border-blue-500/50 hover:bg-zinc-800/50 transition-colors disabled:opacity-60 max-w-[220px]"
                        >
                            <option value="">Rede automática</option>
                            {networks.map(net => (
                                <option key={net.id} value={net.source_ip ?? ''} disabled={!net.source_ip}>
                                    {net.name || net.cidr}
                                    {net.source_ip ? ` — ${net.source_ip}` : ' (sem source IP)'}
                                </option>
                            ))}
                        </select>

                        {viewMode === 'results' && (
                            <div className="flex items-center gap-2">
                                <div className="relative">
                                    <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                                    <select
                                        value={sortBy}
                                        onChange={(e) => setSortBy(e.target.value as 'ip' | 'name' | 'vendor')}
                                        className="bg-zinc-900/50 border border-zinc-800 text-zinc-300 pl-9 pr-8 py-2 rounded-lg focus:outline-none focus:border-blue-500/50 appearance-none cursor-pointer hover:bg-zinc-800/50 transition-colors text-sm"
                                    >
                                        <option value="ip">IP</option>
                                        <option value="name">Nome</option>
                                        <option value="vendor">Fabricante</option>
                                    </select>
                                </div>
                                <button
                                    onClick={() => setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')}
                                    className="p-2 bg-zinc-900/50 border border-zinc-800 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800/50 transition-colors"
                                    title={sortDirection === 'asc' ? "Crescente" : "Decrescente"}
                                >
                                    {sortDirection === 'asc' ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
                                </button>
                            </div>
                        )}

                        <button
                            onClick={exportToCSV}
                            disabled={viewMode === 'results' ? activeSession.results.length === 0 : (!activeSession.availableRanges || activeSession.availableRanges.length === 0)}
                            className={`p-2 bg-zinc-900/50 border border-zinc-800 rounded-lg transition-colors ${(viewMode === 'results' ? activeSession.results.length === 0 : (!activeSession.availableRanges || activeSession.availableRanges.length === 0))
                                    ? 'text-zinc-600 cursor-not-allowed'
                                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                                }`}
                            title="Exportar CSV"
                        >
                            <Upload size={16} />
                        </button>

                        <button
                            onClick={() => toggleScan(activeSession)}
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

                    {/* View Tabs */}
                    <div className="flex items-center px-4 border-b border-zinc-800/50 bg-zinc-900/20">
                        <button
                            onClick={() => setViewMode('results')}
                            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${viewMode === 'results'
                                ? 'border-blue-500 text-blue-400'
                                : 'border-transparent text-zinc-500 hover:text-zinc-300'
                                }`}
                        >
                            Dispositivos Encontrados ({activeSession.results.length})
                        </button>
                        <button
                            onClick={() => setViewMode('available')}
                            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${viewMode === 'available'
                                ? 'border-blue-500 text-blue-400'
                                : 'border-transparent text-zinc-500 hover:text-zinc-300'
                                }`}
                        >
                            IPs Disponíveis {activeSession.availableCount !== undefined ? `(${activeSession.availableCount})` : ''}
                            {viewMode === 'available' && (
                                <div
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setShowInfoModal(true);
                                    }}
                                    className="p-1 hover:bg-blue-500/20 rounded-full transition-colors cursor-pointer"
                                    title="Informações sobre disponibilidade"
                                >
                                    <div className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[10px] font-bold">i</div>
                                </div>
                            )}
                        </button>
                    </div>

                    {/* Content Area */}
                    <div className="flex-1 overflow-y-auto p-4">
                        {viewMode === 'results' ? (
                            activeSession.results.length === 0 ? (
                                <div className="h-full flex flex-col items-center justify-center text-zinc-500 gap-4">
                                    <div className="w-16 h-16 rounded-2xl bg-zinc-900/50 flex items-center justify-center border border-zinc-800/50">
                                        <Search size={32} className="opacity-50" />
                                    </div>
                                    <p className="text-sm">Inicie uma varredura para encontrar dispositivos na rede.</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                                    {sortedResults.map((host) => {
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
                                                    {host.vendor && host.vendor !== 'Desconhecido' && (
                                                        <p className="text-zinc-500 text-[11px] truncate mt-0.5" title={`Fabricante: ${host.vendor}`}>
                                                            {host.vendor}
                                                        </p>
                                                    )}
                                                    {host.device_type && host.device_type !== 'Desconhecido' && (
                                                        <div className="flex items-center gap-1 mt-1.5">
                                                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                                                {host.device_type}
                                                            </span>
                                                            {host.device_type_guess && (
                                                                <span
                                                                    title="Tipo provável, identificado por fabricante, hostname e/ou portas abertas. Pode estar incorreto."
                                                                    className="text-zinc-500 hover:text-zinc-300 cursor-help"
                                                                >
                                                                    <HelpCircle size={12} />
                                                                </span>
                                                            )}
                                                        </div>
                                                    )}
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
                            )
                        ) : (
                            // Available IPs View
                            <div className="h-full">
                                {(!activeSession.availableRanges || activeSession.availableRanges.length === 0) ? (
                                    <div className="h-full flex flex-col items-center justify-center text-zinc-500 gap-4">
                                        <p className="text-sm">Nenhum IP disponível ou varredura não concluída.</p>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
                                        {activeSession.availableRanges.map((range, idx) => (
                                            <div key={idx} className="bg-zinc-900/30 border border-zinc-800/50 rounded-lg p-3 flex items-center justify-center text-zinc-400 text-sm font-mono hover:bg-zinc-800/50 hover:text-zinc-200 transition-colors">
                                                {range}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Info Modal */}
            {showInfoModal && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[9999] flex items-center justify-center p-4" onClick={() => setShowInfoModal(false)}>
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 max-w-sm w-full shadow-2xl animate-in fade-in zoom-in duration-200" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center gap-3 text-blue-400 mb-4">
                            <div className="p-2 bg-blue-500/10 rounded-full">
                                <div className="w-6 h-6 rounded-full border-2 border-current flex items-center justify-center text-sm font-bold">i</div>
                            </div>
                            <h3 className="text-lg font-bold">Informação Importante</h3>
                        </div>
                        <p className="text-zinc-300 text-sm leading-relaxed">
                            A disponibilidade é baseada apenas no momento do ping.
                            <br /><br />
                            <span className="text-zinc-400">Isso não garante que o IP esteja realmente livre, pois a máquina pode estar desligada, desconectada ou bloqueando solicitações ICMP (Ping).</span>
                        </p>
                        <button
                            onClick={() => setShowInfoModal(false)}
                            className="mt-6 w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg font-medium transition-colors"
                        >
                            Entendi
                        </button>
                    </div>
                </div>
            )}
        </div >
    );
};
