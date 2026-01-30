import React from 'react';
import { Monitor, X, AlertCircle, Globe, Hash, Info, Clock, RefreshCw, Server, Power, Trash2, Check, Copy, Pencil, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Host } from '../../types';
import { RemoteAccessModal } from './RemoteAccessModal';

interface HostDetailsModalProps {
    isOpen: boolean;
    onClose: () => void;
    host: Host | null;
    hostStatus: Record<string, boolean>;
    onRefresh: () => void;
    onAction: (host: Host, type: 'shutdown' | 'restart' | 'wol' | 'message' | 'cancel', message?: string, delay?: number) => void;
    onDelete: (host: Host) => void;
    onSaveName: () => void;
    isEditingName: boolean;
    setIsEditingName: (isEditing: boolean) => void;
    editedName: string;
    setEditedName: (name: string) => void;
    modalStatus: { type: 'success' | 'error' | 'info', message: string } | null;
    handleModalCopy: (text: string, type: 'ip' | 'hostname') => void;
    copiedIp: boolean;
    copiedHostname: boolean;
    onUpdateHost?: (address: string, updates: any) => Promise<boolean>;
    scheduledAction?: { type: 'shutdown' | 'restart', endTime: number };
    onCancelAction?: (host: Host) => void;
}

export function HostDetailsModal({
    isOpen,
    onClose,
    host,
    hostStatus,
    onRefresh,
    onAction,
    onDelete,
    onSaveName,
    isEditingName,
    setIsEditingName,
    editedName,
    setEditedName,
    modalStatus,
    handleModalCopy,
    copiedIp,
    copiedHostname,
    onUpdateHost,
    scheduledAction,
    onCancelAction
}: HostDetailsModalProps) {
    const navigate = useNavigate();
    const [isRemoteModalOpen, setIsRemoteModalOpen] = React.useState(false);
    const [message, setMessage] = React.useState('');
    const [delay, setDelay] = React.useState(5);
    const [countdown, setCountdown] = React.useState<number | null>(null);
    const [isResolving, setIsResolving] = React.useState(false);

    React.useEffect(() => {
        if (scheduledAction) {
            const updateCountdown = () => {
                const remaining = Math.ceil((scheduledAction.endTime - Date.now()) / 1000);
                if (remaining > 0) {
                    setCountdown(remaining);
                } else {
                    setCountdown(null);
                }
            };
            updateCountdown();
            const timer = setInterval(updateCountdown, 1000);
            return () => clearInterval(timer);
        } else if (countdown !== null) {
            // Fallback for immediate actions that set countdown locally (legacy behavior or non-persisted)
            if (countdown <= 0) {
                setCountdown(null);
                return;
            }
            const timer = setInterval(() => {
                setCountdown(prev => (prev !== null ? prev - 1 : null));
            }, 1000);
            return () => clearInterval(timer);
        }
    }, [scheduledAction, countdown]);

    if (!isOpen || !host) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                <div className="p-6 border-b border-zinc-800 flex justify-between items-start">
                    <div className="flex items-center gap-4">
                        <div className={`p-3 rounded-xl ${hostStatus[host.address] ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                            <Monitor size={32} />
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                {isEditingName ? (
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="text"
                                            value={editedName}
                                            onChange={(e) => setEditedName(e.target.value)}
                                            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white text-xl font-bold focus:outline-none focus:border-blue-500"
                                            autoFocus
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') onSaveName();
                                                if (e.key === 'Escape') setIsEditingName(false);
                                            }}
                                        />
                                        <button
                                            onClick={onSaveName}
                                            className="p-1 bg-green-600 hover:bg-green-500 text-white rounded"
                                            title="Salvar"
                                        >
                                            <Check size={16} />
                                        </button>
                                        <button
                                            onClick={() => setIsEditingName(false)}
                                            className="p-1 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 rounded"
                                            title="Cancelar"
                                        >
                                            <X size={16} />
                                        </button>
                                    </div>
                                ) : (
                                    <>
                                        <h2 className="text-2xl font-bold text-white">{host.name || host.hostname || host.address}</h2>
                                        <button
                                            onClick={() => {
                                                setEditedName(host.name || '');
                                                setIsEditingName(true);
                                            }}
                                            className="p-1 text-zinc-500 hover:text-blue-400 transition-colors"
                                            title="Editar Apelido"
                                        >
                                            <Pencil size={16} />
                                        </button>
                                    </>
                                )}
                            </div>
                            <p className="text-zinc-400 font-mono">{host.ip || (/\d+\.\d+\.\d+\.\d+/.test(host.address) ? host.address : 'IP não disponível')}</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white"
                    >
                        <X size={24} />
                    </button>
                </div>

                {modalStatus && (
                    <div className={`px-6 py-2 flex items-center gap-2 text-sm ${modalStatus.type === 'error' ? 'bg-red-500/10 text-red-500' :
                        modalStatus.type === 'success' ? 'bg-green-500/10 text-green-500' :
                            'bg-blue-500/10 text-blue-500'
                        }`}>
                        <AlertCircle size={16} />
                        {modalStatus.message}
                    </div>
                )}

                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Left Column: Info & Stats */}
                    <div className="space-y-6">
                        {/* System Info Card */}
                        <div className="bg-zinc-950/50 rounded-xl border border-zinc-800/50 p-4 space-y-4">
                            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                                <Info size={14} />
                                Informações do Sistema
                            </h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500">Endereço IP</p>
                                    <div className="flex items-center gap-2">
                                        <Globe size={14} className="text-blue-500" />
                                        <span className="font-mono text-sm text-zinc-200">
                                            {host.ip || (/\d+\.\d+\.\d+\.\d+/.test(host.address) ? host.address : 'Não disponível')}
                                        </span>
                                        <button
                                            onClick={() => handleModalCopy(host.ip || (/\d+\.\d+\.\d+\.\d+/.test(host.address) ? host.address : ''), 'ip')}
                                            className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-white transition-colors"
                                        >
                                            {copiedIp ? <Check size={10} className="text-green-500" /> : <Copy size={10} />}
                                        </button>
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500">Hostname</p>
                                    <div className="flex items-center gap-2">
                                        <Monitor size={14} className="text-zinc-500" />
                                        <span className="text-sm text-zinc-200 truncate max-w-[120px]" title={host.hostname || ''}>
                                            {host.hostname || 'Não resolvido'}
                                        </span>
                                        {host.hostname && (
                                            <button
                                                onClick={() => handleModalCopy(host.hostname || '', 'hostname')}
                                                className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-white transition-colors"
                                            >
                                                {copiedHostname ? <Check size={10} className="text-green-500" /> : <Copy size={10} />}
                                            </button>
                                        )}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500">Domínio</p>
                                    <div className="flex items-center gap-2">
                                        <Hash size={14} className="text-purple-500" />
                                        <span className="text-sm text-zinc-200 truncate">
                                            {host.domain || 'Não detectado'}
                                        </span>
                                        {(!host.domain || host.domain === 'Não detectado') && (
                                            <button
                                                disabled={isResolving}
                                                onClick={async () => {
                                                    setIsResolving(true);
                                                    const controller = new AbortController();
                                                    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
                                                    try {
                                                        const res = await fetch(`http://127.0.0.1:8000/hosts/${host.address}/refresh`, {
                                                            method: 'POST',
                                                            signal: controller.signal
                                                        });
                                                        clearTimeout(timeoutId);
                                                        if (res.ok) {
                                                            onRefresh();
                                                        } else {
                                                            console.error('Falha na resolução:', res.statusText);
                                                        }
                                                    } catch (e: any) {
                                                        if (e.name === 'AbortError') {
                                                            console.error('Resolução de domínio excedeu o tempo limite.');
                                                        } else {
                                                            console.error(e);
                                                        }
                                                    } finally {
                                                        setIsResolving(false);
                                                    }
                                                }}
                                                className={`p-1 rounded transition-colors ${isResolving ? 'cursor-wait text-blue-500' : 'hover:bg-zinc-800 text-zinc-500 hover:text-white'}`}
                                                title="Tentar resolver domínio"
                                            >
                                                <RefreshCw size={12} className={isResolving ? "animate-spin" : ""} />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                <div className="space-y-1">
                                    <p className="text-xs text-zinc-500">MAC Address</p>
                                    <div className="flex items-center gap-2">
                                        <Activity size={14} className="text-yellow-500" />
                                        <span className="font-mono text-sm text-zinc-200 truncate">
                                            {host.mac || 'Não configurado'}
                                        </span>
                                    </div>
                                </div>

                                <div className="space-y-1 sm:col-span-2 border-t border-zinc-800/50 pt-3 mt-1">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-xs text-zinc-500">Última Verificação</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <Clock size={14} className="text-green-500" />
                                                <span className="text-sm text-zinc-200">
                                                    {host.last_checked ? new Date(host.last_checked).toLocaleString() : 'Nunca'}
                                                </span>
                                            </div>
                                        </div>
                                        <button
                                            onClick={onRefresh}
                                            className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-500 hover:text-white transition-colors bg-zinc-900 border border-zinc-800"
                                            title="Atualizar Status"
                                        >
                                            <RefreshCw size={14} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Network Stats Card */}
                        <div className="bg-zinc-950/50 rounded-xl border border-zinc-800/50 p-4 space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                                    <Activity size={14} />
                                    Estatísticas de Rede
                                </h3>
                                <button
                                    onClick={() => {
                                        if (onUpdateHost) {
                                            onUpdateHost(host.address, { reset_stats: true });
                                        }
                                    }}
                                    className="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-white transition-colors"
                                    title="Reiniciar Métricas"
                                >
                                    <RefreshCw size={14} />
                                </button>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <div className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/50">
                                    <p className="text-[10px] text-zinc-500 mb-1 uppercase tracking-wider">Latência</p>
                                    <div className="flex items-center gap-2">
                                        <Activity size={16} className="text-blue-500" />
                                        <span className="text-lg font-mono text-zinc-200">
                                            {host.stats?.latency ? `${Math.round(host.stats.latency)}ms` : '-'}
                                        </span>
                                    </div>
                                </div>
                                <div className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/50">
                                    <p className="text-[10px] text-zinc-500 mb-1 uppercase tracking-wider">Perda</p>
                                    <div className="flex items-center gap-2">
                                        <AlertCircle size={16} className="text-yellow-500" />
                                        <span className="text-lg font-mono text-zinc-200">
                                            {host.stats?.packet_loss_pct !== undefined ? `${host.stats.packet_loss_pct.toFixed(1)}%` : '-'}
                                        </span>
                                    </div>
                                </div>
                                <div className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/50">
                                    <p className="text-[10px] text-zinc-500 mb-1 uppercase tracking-wider">Pings</p>
                                    <div className="flex items-center gap-2">
                                        <Server size={16} className="text-green-500" />
                                        <span className="text-lg font-mono text-zinc-200">
                                            {host.stats?.total_packets || '-'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Right Column: Actions */}
                    <div className="flex flex-col gap-4">
                        <div className="grid grid-cols-2 gap-3">
                            <button
                                onClick={() => setIsRemoteModalOpen(true)}
                                className="flex flex-col items-center justify-center gap-2 p-4 bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 rounded-xl transition-all shadow-lg shadow-black/20 hover:shadow-blue-900/10 hover:-translate-y-0.5"
                            >
                                <Monitor size={24} />
                                <span className="text-sm font-semibold">Acesso Remoto</span>
                            </button>

                            <button
                                onClick={() => {
                                    onClose();
                                    navigate(`/host/${host.address}`, { state: { host: host } });
                                }}
                                className="flex flex-col items-center justify-center gap-2 p-4 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 rounded-xl transition-colors font-medium border border-zinc-700/50"
                            >
                                <Server size={24} />
                                <span className="text-sm font-semibold">Detalhes Avançados</span>
                            </button>
                        </div>

                        {/* Power & Message Actions */}
                        <div className="space-y-3 bg-zinc-950/30 p-4 rounded-xl border border-zinc-800/50">
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <input
                                        type="text"
                                        value={message}
                                        onChange={(e) => setMessage(e.target.value)}
                                        placeholder="Mensagem para o usuário (opcional)"
                                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg py-2 px-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
                                    />
                                </div>
                                <div className="relative w-24" title="Tempo de espera em segundos">
                                    <input
                                        type="number"
                                        value={delay}
                                        onChange={(e) => setDelay(Math.max(0, parseInt(e.target.value) || 0))}
                                        onFocus={(e) => e.target.select()}
                                        className={`w-full bg-zinc-950 border border-zinc-800 rounded-lg py-2 px-3 text-sm placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors text-center ${delay === 5 ? 'text-zinc-500' : 'text-white'}`}
                                        min="0"
                                    />
                                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-zinc-500 pointer-events-none">s</span>
                                </div>
                            </div>

                            <div className="grid grid-cols-4 gap-2">
                                <button
                                    onClick={() => onAction(host, 'message', message)}
                                    className="flex flex-col items-center gap-2 p-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-blue-400 rounded-xl transition-colors border border-zinc-700/50 hover:border-blue-500/30"
                                    title="Enviar Mensagem"
                                >
                                    <Info size={20} />
                                    <span className="text-[10px] font-medium">Mensagem</span>
                                </button>
                                <button
                                    onClick={() => {
                                        onAction(host, 'restart', message, delay);
                                    }}
                                    className="flex flex-col items-center gap-2 p-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-orange-400 rounded-xl transition-colors border border-zinc-700/50 hover:border-orange-500/30"
                                    title={`Reiniciar Sistema (${delay}s)`}
                                >
                                    <RefreshCw size={20} />
                                    <span className="text-[10px] font-medium">Reiniciar</span>
                                </button>
                                <button
                                    onClick={() => {
                                        onAction(host, 'shutdown', message, delay);
                                    }}
                                    className="flex flex-col items-center gap-2 p-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-red-400 rounded-xl transition-colors border border-zinc-700/50 hover:border-red-500/30"
                                    title={`Desligar Sistema (${delay}s)`}
                                >
                                    <Power size={20} />
                                    <span className="text-[10px] font-medium">Desligar</span>
                                </button>

                            </div>

                            {scheduledAction && onCancelAction && (
                                <div className="mt-2 p-3 bg-blue-950/30 rounded-xl border border-blue-800/50 flex items-center justify-between animate-in fade-in slide-in-from-top-2">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-blue-500/10 rounded-lg">
                                            <Clock size={16} className="text-blue-400" />
                                        </div>
                                        <div className="flex flex-col">
                                            <span className="text-sm font-medium text-zinc-200">
                                                {scheduledAction.type === 'restart' ? 'Reinicialização' : 'Desligamento'} Agendado
                                            </span>
                                            <span className="text-xs text-zinc-500">
                                                Executando em {countdown}s...
                                            </span>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => onCancelAction(host)}
                                        className="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-lg text-xs font-medium transition-colors border border-red-500/20 flex items-center gap-2"
                                    >
                                        <X size={12} />
                                        Cancelar Agora
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="mt-auto pt-4 border-t border-zinc-800/50">
                            <button
                                onClick={() => onDelete(host)}
                                className="w-full flex items-center justify-center gap-2 p-3 bg-zinc-950 hover:bg-red-950/30 text-zinc-500 hover:text-red-400 border border-zinc-800 hover:border-red-900/50 rounded-xl transition-colors text-sm font-medium"
                            >
                                <Trash2 size={18} />
                                Remover Host
                            </button>
                        </div>
                    </div>
                </div>
                <RemoteAccessModal
                    isOpen={isRemoteModalOpen}
                    onClose={() => setIsRemoteModalOpen(false)}
                    host={host}
                />
            </div>
        </div>
    );
}
