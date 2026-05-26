import React, { memo } from 'react';
import { Monitor, AlertTriangle, Copy, Power, GripVertical, Activity, Network as NetworkIcon, Server, Trash2, Plus, Check, X, Info, RefreshCw, FolderInput } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import { Host, HostStatistics, HostUpdate } from '../../types';
import { RemoteAccessModal } from './RemoteAccessModal';
import { useToast } from '../../contexts/ToastContext';

interface HostCardProps {
    host: Host;
    index: number;
    isOnline: boolean;
    stats: HostStatistics;
    handleToggleMonitoring: (e: React.MouseEvent, host: Host) => void;
    setDetailsHost: (host: Host) => void;
    setIsDetailsModalOpen: (isOpen: boolean) => void;
    isDragDisabled: boolean;
    // dnd-kit props
    setNodeRef?: (node: HTMLElement | null) => void;
    style?: React.CSSProperties;
    attributes?: any;
    listeners?: any;
    isDragging?: boolean;
    isOverlay?: boolean;
    onPing?: (host: Host) => void;
    onTraceroute?: (host: Host) => void;
    onDelete?: (host: Host) => void;
    onUpdateHost?: (address: string, updates: HostUpdate) => Promise<boolean>;
    activeContextMenu?: string | null;
    onContextMenuOpen?: (id: string | null) => void;
    onViewDetails?: (host: Host) => void;
    onSetGroup?: (host: Host) => void;
}

export const HostCard = memo(function HostCard({
    host,
    index,
    isOnline,
    stats,
    handleToggleMonitoring,
    setDetailsHost,
    setIsDetailsModalOpen,
    isDragDisabled,
    setNodeRef,
    style,
    attributes,
    listeners,
    isDragging,
    isOverlay,
    onPing,
    onTraceroute,
    onDelete,
    onUpdateHost,
    activeContextMenu,
    onContextMenuOpen,
    onViewDetails,
    onSetGroup
}: HostCardProps) {
    const [isRemoteModalOpen, setIsRemoteModalOpen] = React.useState(false);
    const { showToast } = useToast();

    // Port Addition State
    const [isAddingPort, setIsAddingPort] = React.useState(false);
    const [newPort, setNewPort] = React.useState('');
    const [selectedPort, setSelectedPort] = React.useState<number | null>(null);
    const [optimisticPorts, setOptimisticPorts] = React.useState<number[]>(host.ports || []);

    // Sync optimistic ports with host ports when host updates
    React.useEffect(() => {
        setOptimisticPorts(host.ports || []);
    }, [host.ports]);

    // Context Menu State
    const [contextMenu, setContextMenu] = React.useState<{ x: number; y: number } | null>(null);
    const contextMenuRef = React.useRef<HTMLDivElement>(null);

    // Close context menu on click outside
    React.useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
                setContextMenu(null);
                setSelectedPort(null);
                if (onContextMenuOpen) onContextMenuOpen(null);
            }
        };

        const handleScroll = () => {
            if (contextMenu) {
                setContextMenu(null);
                setSelectedPort(null);
            }
        };

        document.addEventListener('click', handleClick);
        document.addEventListener('contextmenu', handleClick);
        document.addEventListener('scroll', handleScroll, true);

        return () => {
            document.removeEventListener('click', handleClick);
            document.removeEventListener('contextmenu', handleClick);
            document.removeEventListener('scroll', handleScroll, true);
        };
    }, [contextMenu]);

    const handleContextMenu = (e: React.MouseEvent) => {
        if (isDragging || isOverlay) return;
        e.preventDefault();
        e.stopPropagation();

        if (onContextMenuOpen) {
            onContextMenuOpen(host.address);
        }

        let x = e.clientX;
        let y = e.clientY;

        // Adjust for right edge (w-48 = 192px, adding buffer)
        if (x + 200 > window.innerWidth) {
            x = x - 200;
        }

        // Adjust for bottom edge (approximate menu height ~320px)
        const MENU_HEIGHT = 320;
        if (y + MENU_HEIGHT > window.innerHeight) {
            y = y - MENU_HEIGHT;
            // Ensure we don't go off the top
            if (y < 0) y = 0;
        }

        setContextMenu({ x, y });
        setSelectedPort(null); // Reset selected port for main card context menu
    };

    const handlePortContextMenu = (e: React.MouseEvent, port: number) => {
        e.preventDefault();
        e.stopPropagation();

        if (onContextMenuOpen) {
            onContextMenuOpen(host.address);
        }

        let x = e.clientX;
        let y = e.clientY;

        if (x + 200 > window.innerWidth) x = x - 200;
        if (y + 100 > window.innerHeight) y = y - 100;

        setContextMenu({ x, y });
        setSelectedPort(port);
    };

    // Close if another menu is opened
    React.useEffect(() => {
        if (activeContextMenu !== undefined && activeContextMenu !== host.address) {
            setContextMenu(null);
        }
    }, [activeContextMenu, host.address]);

    const handleAddPort = async () => {
        if (!newPort) {
            setIsAddingPort(false);
            return;
        }
        const port = parseInt(newPort, 10);
        if (isNaN(port) || port < 1 || port > 65535) {
            showToast('Porta inválida', 'error');
            return;
        }
        if (optimisticPorts.includes(port)) {
            showToast('Porta já monitorada', 'error');
            setIsAddingPort(false);
            setNewPort('');
            return;
        }

        // Optimistic update
        setOptimisticPorts(prev => [...prev, port]);
        setIsAddingPort(false);
        setNewPort('');

        if (onUpdateHost) {
            const currentPorts = host.ports || [];
            const success = await onUpdateHost(host.address, { ports: [...currentPorts, port] });
            if (success) {
                showToast('Porta adicionada', 'success');
            } else {
                // Revert if failed
                setOptimisticPorts(prev => prev.filter(p => p !== port));
                showToast('Erro ao adicionar porta', 'error');
            }
        }
    };

    const widthClasses = isOverlay
        ? 'w-full h-full'
        : 'w-full md:w-[calc(50%-0.5rem)] lg:w-[calc(33.333%-0.667rem)] xl:w-[calc(25%-0.75rem)]';

    // Effective online: must pass both the instantaneous flag AND the consolidated state
    // (sustained loss > 60% OR never responded). Avoids "green dot + HOST OFFLINE body" when
    // a single ping sneaks through on an otherwise dead host.
    const isSmartOffline = stats.total_packets > 50 && stats.packet_loss_pct > 60;
    const neverOnline = stats.calibration_done && stats.has_ever_been_online === false;
    const effectiveIsOnline = isOnline && !isSmartOffline && !neverOnline;

    // Prepare data for sparkline
    const sparklineData = React.useMemo(() => {
        if (!stats.history || stats.history.length < 2) return [];
        return stats.history.map((point: { latency: number }) => ({
            latency: point.latency || 0
        }));
    }, [stats.history]);

    return (
        <>
            <div
                ref={setNodeRef}
                style={style}
                {...attributes}
                onClick={() => {
                    if (!isDragging && !isOverlay) {
                        // showToast('Click detected', 'info'); // Debug
                        if (onViewDetails) {
                            onViewDetails(host);
                        } else {
                            setDetailsHost(host);
                            setIsDetailsModalOpen(true);
                        }
                    }
                }}
                onContextMenu={handleContextMenu}
                className={`group relative bg-zinc-900 border rounded-xl p-4 transition-all cursor-pointer overflow-hidden 
                ${widthClasses}
                ${isOverlay
                        ? 'border-blue-500 shadow-2xl ring-2 ring-blue-500/20 rotate-2 scale-105 z-50 cursor-grabbing'
                        : isDragging
                            ? 'opacity-30 border-dashed border-zinc-700'
                            : 'border-zinc-800 hover:border-zinc-700 hover:shadow-lg'
                    }`}
            >
                {/* Fallback button for Webview if card click fails */}
                {/* Fallback button removed as per user request */}
                <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div
                            {...listeners}
                            className={`p-2 rounded-lg cursor-grab active:cursor-grabbing hover:bg-zinc-800 transition-colors ${host.monitoring === false ? 'bg-zinc-500/10 text-zinc-500' : (effectiveIsOnline ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500')} ${isDragDisabled ? 'cursor-default opacity-50' : ''}`}
                            onClick={(e) => e.stopPropagation()}
                            title={isDragDisabled ? "Reordenação desativada (Filtro ativo ou modo de ordenação não manual)" : "Arrastar para reordenar"}
                        >
                            {!isDragDisabled ? <GripVertical size={20} /> : <Monitor size={20} />}
                        </div>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2 group/name">
                                {(() => {
                                    const rawName = host.name || host.hostname || host.address;
                                    // Check if it looks like an IP address
                                    const isIp = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(rawName || '');
                                    // If it's an IP, show full. If it's a hostname, show only the first part (host without domain)
                                    const displayName = rawName ? (isIp ? rawName : rawName.split('.')[0]) : '';
                                    const isLong = displayName.length > 12;

                                    return (
                                        <h3
                                            className={`font-medium truncate max-w-[150px] ${isLong ? 'text-xs' : 'text-sm'} ${host.monitoring === false ? 'text-zinc-500' : 'text-white'}`}
                                            title={rawName}
                                        >
                                            {displayName}
                                        </h3>
                                    );
                                })()}
                            </div>
                            <div className="flex items-center gap-2 group/ip">
                                <p className="text-xs text-zinc-500 font-mono">{stats.ip || host.ip || (/\d+\.\d+\.\d+\.\d+/.test(host.address) ? host.address : 'Resolvendo...')}</p>
                                {host.network_name && (
                                    <span
                                        className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] font-medium border border-blue-500/20 truncate max-w-[120px]"
                                        title={`Rede: ${host.network_name}`}
                                    >
                                        {host.network_name}
                                    </span>
                                )}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        navigator.clipboard.writeText(stats.ip || host.ip || host.address);
                                        showToast('Endereço IP copiado!', 'success');
                                    }}
                                    className="opacity-0 group-hover/ip:opacity-100 p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-all"
                                    title="Copiar IP"
                                    aria-label={`Copiar IP ${stats.ip || host.ip || host.address}`}
                                >
                                    <Copy size={12} aria-hidden="true" />
                                </button>
                            </div>
                        </div>
                    </div>
                    <div className="absolute top-4 right-4 flex items-center gap-2">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setIsRemoteModalOpen(true);
                            }}
                            className="p-1.5 rounded-lg text-blue-400 hover:bg-zinc-800 hover:text-blue-300 transition-colors"
                            title="Acesso Remoto (RDP, MSRA, TeamViewer)"
                            aria-label="Abrir acesso remoto"
                        >
                            <Monitor size={14} aria-hidden="true" />
                        </button>
                        <button
                            onClick={(e) => handleToggleMonitoring(e, host)}
                            className={`p-1.5 rounded-lg transition-colors ${host.monitoring === false ? 'text-zinc-600 hover:bg-zinc-800 hover:text-zinc-400' : 'text-green-500/50 hover:text-green-500 hover:bg-zinc-800'}`}
                            title={host.monitoring === false ? "Ativar monitoramento" : "Desativar monitoramento"}
                            aria-label={host.monitoring === false ? "Ativar monitoramento" : "Desativar monitoramento"}
                            aria-pressed={host.monitoring !== false}
                        >
                            <Power size={14} aria-hidden="true" />
                        </button>
                        <div
                            className={`w-2 h-2 rounded-full ${host.monitoring === false ? 'bg-zinc-700' : (effectiveIsOnline ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-red-500')}`}
                            role="status"
                            aria-label={host.monitoring === false ? 'Monitoramento pausado' : (effectiveIsOnline ? 'Host online' : 'Host offline')}
                        />
                    </div>
                </div>

                {
                    host.monitoring === false ? (
                        <div className="flex flex-col items-center justify-center py-2 text-zinc-500 gap-2 bg-zinc-950/30 rounded-lg border border-zinc-800/50 h-[74px]">
                            <div className="flex items-center gap-2">
                                <Power size={16} className="text-zinc-600" />
                                <span className="text-xs font-medium">Monitoramento Pausado</span>
                            </div>
                        </div>
                    ) : (!stats.calibration_done) ? (
                        <div className="flex flex-col items-center justify-center py-2 text-zinc-500 gap-2 bg-zinc-950/30 rounded-lg border border-zinc-800/50 h-[74px] relative overflow-hidden">
                            <div className="flex items-center gap-2 z-10">
                                <Activity className="animate-pulse text-blue-500" size={16} />
                                <span className="text-xs font-medium text-zinc-400">Calibrando métricas...</span>
                            </div>
                            <div className="w-48 h-1 bg-zinc-800/50 rounded-full overflow-hidden z-10">
                                <div
                                    className="h-full bg-blue-500/50 transition-all duration-500 ease-out relative"
                                    style={{ width: `${(stats.total_packets / 5) * 100}%` }}
                                >
                                    <div className="absolute inset-0 bg-white/20 animate-[shimmer_1s_infinite]" />
                                </div>
                            </div>
                            {/* Subtle background pulse */}
                            <div className="absolute inset-0 bg-blue-500/5 animate-pulse" />
                        </div>
                    ) : (!stats.has_ever_been_online || stats.packet_loss_pct > 60) ? (
                        <div className="flex flex-col items-center justify-center py-2 text-red-500 gap-2 bg-red-500/5 rounded-lg border border-red-500/20 h-[74px]">
                            <div className="flex items-center gap-2">
                                <AlertTriangle className="animate-pulse" size={18} />
                                <span className="text-sm font-bold tracking-wide">HOST OFFLINE</span>
                            </div>
                        </div>
                    ) : (
                        <div className="relative h-[74px]">
                            {/* Sparkline Background */}
                            <div className="absolute inset-0 opacity-20 pointer-events-none">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={sparklineData}>
                                        <defs>
                                            <linearGradient id={`colorLatency-${index}`} x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <Area
                                            type="monotone"
                                            dataKey="latency"
                                            stroke="#3b82f6"
                                            fillOpacity={1}
                                            fill={`url(#colorLatency-${index})`}
                                            strokeWidth={1}
                                            isAnimationActive={false}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>

                            <div className="relative z-10 grid grid-cols-3 gap-2 h-full">
                                <div className="bg-zinc-950/50 rounded p-2 backdrop-blur-sm border border-zinc-800/50">
                                    <p className="text-zinc-500 mb-1">Latência</p>
                                    <p className={`font-mono ${stats.average_latency && stats.average_latency > 100 ? 'text-yellow-500' : 'text-zinc-300'}`}>
                                        {stats.average_latency ? `${Math.round(stats.average_latency)}ms` : '-'}
                                    </p>
                                </div>
                                <div className="bg-zinc-950/50 rounded p-2 backdrop-blur-sm border border-zinc-800/50">
                                    <p className="text-zinc-500 mb-1">Perda</p>
                                    <div className="flex items-center gap-1" title={stats.packet_loss_pct > 5 ? "Alta perda de pacotes detectada" : undefined}>
                                        <p className={`font-mono ${stats.packet_loss_pct >= 5 ? 'text-red-500' :
                                            stats.packet_loss_pct >= 2 ? 'text-yellow-500' :
                                                'text-zinc-300'
                                            }`}>
                                            {stats.packet_loss_pct.toFixed(1)}%
                                        </p>
                                        {stats.packet_loss_pct >= 5 && (
                                            <AlertTriangle size={12} className="text-red-500" />
                                        )}
                                    </div>
                                </div>
                                <div className="bg-zinc-950/50 rounded p-2 backdrop-blur-sm border border-zinc-800/50">
                                    <p className="text-zinc-500 mb-1">Pings</p>
                                    <p className="font-mono text-zinc-300">{stats.total_packets}</p>
                                </div>
                            </div>
                        </div>
                    )
                }

                {/* Ports Status */}
                {(optimisticPorts.length > 0) || onUpdateHost ? (
                    <div className="mt-3 flex flex-wrap items-center gap-2 relative z-10 border-t border-zinc-800/50 pt-3">
                        <span className="text-[10px] uppercase font-medium text-zinc-600 mr-1">Portas:</span>
                        {optimisticPorts.map((port) => {
                            const isOpen = stats.ports_status ? stats.ports_status[port] : undefined;
                            return (
                                <div
                                    key={port}
                                    className="flex items-center gap-1.5 bg-zinc-950/50 rounded px-2 py-1 border border-zinc-800/50 cursor-context-menu hover:bg-zinc-900 transition-colors"
                                    title={`Porta ${port}: ${isOpen === true ? 'Aberta' : isOpen === false ? 'Fechada' : 'Verificando...'} (Clique direito para opções)`}
                                    onContextMenu={(e) => handlePortContextMenu(e, port)}
                                >
                                    <div className={`w-1.5 h-1.5 rounded-full ${isOpen === true ? 'bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.4)]' :
                                        isOpen === false ? 'bg-red-500' :
                                            'bg-zinc-500 animate-pulse'
                                        }`} />
                                    <span className="text-[10px] font-mono text-zinc-400">{port}</span>
                                </div>
                            );
                        })}

                        {/* Add Port Button */}
                        {onUpdateHost && (
                            isAddingPort ? (
                                <div className="flex items-center gap-1 bg-zinc-950/50 rounded px-1 py-0.5 border border-zinc-800/50">
                                    <input
                                        autoFocus
                                        type="text"
                                        value={newPort}
                                        onChange={(e) => setNewPort(e.target.value.replace(/\D/g, ''))}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') handleAddPort();
                                            if (e.key === 'Escape') {
                                                setIsAddingPort(false);
                                                setNewPort('');
                                            }
                                            e.stopPropagation();
                                        }}
                                        onClick={(e) => e.stopPropagation()}
                                        className="w-12 bg-transparent text-[10px] font-mono text-zinc-300 outline-none text-center"
                                        placeholder="PORT"
                                    />
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleAddPort(); }}
                                        className="p-0.5 hover:bg-green-500/20 text-green-500 rounded"
                                    >
                                        <Check size={10} />
                                    </button>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setIsAddingPort(false);
                                            setNewPort('');
                                        }}
                                        className="p-0.5 hover:bg-red-500/20 text-red-500 rounded"
                                    >
                                        <X size={10} />
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setIsAddingPort(true);
                                    }}
                                    className="flex items-center gap-1.5 bg-zinc-950/30 hover:bg-zinc-800 rounded px-2 py-1 border border-zinc-800/50 border-dashed transition-colors group/add"
                                    title="Monitorar porta"
                                >
                                    <Plus size={10} className="text-zinc-500 group-hover/add:text-zinc-300" />
                                </button>
                            )
                        )}
                    </div>
                ) : null}

                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors pointer-events-none" />

                <RemoteAccessModal
                    isOpen={isRemoteModalOpen}
                    onClose={() => setIsRemoteModalOpen(false)}
                    host={host}
                />

                {/* Context Menu */}
                {contextMenu && (
                    <div
                        ref={contextMenuRef}
                        className="fixed z-50 w-48 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-1 overflow-hidden"
                        style={{ top: contextMenu.y, left: contextMenu.x }}
                        onContextMenu={(e) => e.preventDefault()}
                    >
                        {selectedPort ? (
                            <button
                                onClick={async (e) => {
                                    e.stopPropagation();
                                    if (onUpdateHost && host.ports) {
                                        // Optimistic update
                                        setOptimisticPorts(prev => prev.filter(p => p !== selectedPort));
                                        setContextMenu(null); // Close menu immediately

                                        const newPorts = host.ports.filter(p => p !== selectedPort);
                                        const success = await onUpdateHost(host.address, { ports: newPorts });
                                        if (success) {
                                            showToast(`Porta ${selectedPort} removida`, 'success');
                                        } else {
                                            // Revert if failed
                                            setOptimisticPorts(prev => [...prev, selectedPort!]);
                                            showToast('Erro ao remover porta', 'error');
                                        }
                                    }
                                    setContextMenu(null);
                                    setSelectedPort(null);
                                }}
                                className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 flex items-center gap-2"
                            >
                                <Trash2 size={14} />
                                Remover Porta {selectedPort}
                            </button>
                        ) : (
                            <>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onPing?.(host);
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <Activity size={14} />
                                    Ping
                                </button>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onTraceroute?.(host);
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <NetworkIcon size={14} />
                                    Traceroute
                                </button>
                                <button
                                    onClick={async (e) => {
                                        e.stopPropagation();
                                        setContextMenu(null);
                                        if (!onUpdateHost) return;
                                        // Wait on the PATCH before announcing success — the
                                        // previous fire-and-forget toast lied when the backend
                                        // 404'd or the host wasn't found in the monitor.
                                        const ok = await onUpdateHost(host.address, { reset_stats: true });
                                        if (ok) {
                                            showToast('Estatísticas de ping reiniciadas', 'success');
                                        } else {
                                            showToast('Erro ao reiniciar estatísticas', 'error');
                                        }
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <RefreshCw size={14} />
                                    Reiniciar Métricas
                                </button>
                                <div className="h-px bg-zinc-800 my-1" />
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setIsRemoteModalOpen(true);
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <Monitor size={14} />
                                    Acesso Remoto
                                </button>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setDetailsHost(host);
                                        setIsDetailsModalOpen(true);
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <Info size={14} />
                                    Detalhes
                                </button>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (onViewDetails) {
                                            onViewDetails(host);
                                        } else {
                                            setDetailsHost(host);
                                            setIsDetailsModalOpen(true);
                                        }
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <Server size={14} />
                                    Detalhes Avançados
                                </button>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (onSetGroup) {
                                            onSetGroup(host);
                                        }
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white flex items-center gap-2"
                                >
                                    <FolderInput size={14} />
                                    Definir Grupo
                                </button>
                                <div className="h-px bg-zinc-800 my-1" />
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDelete?.(host);
                                        setContextMenu(null);
                                    }}
                                    className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 flex items-center gap-2"
                                >
                                    <Trash2 size={14} />
                                    Remover Host
                                </button>
                            </>
                        )}
                    </div>
                )}
            </div >
        </>
    );
});
