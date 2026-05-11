import React, { useEffect } from 'react';
import { AlertTriangle, X, Clock, Users, RotateCw, Loader2, Power } from 'lucide-react';
import { clsx } from 'clsx';
import { Host } from '../../types';
import { PrePowerCheckData } from '../../utils/prePowerCheck';

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onProceed: () => void;
    host: Host | null;
    type: 'shutdown' | 'restart';
    /** null while loading; data when ready */
    check: PrePowerCheckData | null;
    /** unrecoverable error (host unreachable, no perms, etc.) — operator still
     *  decides whether to proceed without info */
    error: string | null;
}

const ACTION_LABEL: Record<Props['type'], string> = {
    shutdown: 'Desligar',
    restart: 'Reiniciar',
};

function formatUptime(minutes: number | null): string {
    if (minutes === null) return 'desconhecido';
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const remMin = minutes % 60;
    if (hours < 24) return remMin > 0 ? `${hours} h ${remMin} min` : `${hours} h`;
    const days = Math.floor(hours / 24);
    const remHours = hours % 24;
    return remHours > 0 ? `${days} d ${remHours} h` : `${days} d`;
}

export function PrePowerActionModal({
    isOpen,
    onClose,
    onProceed,
    host,
    type,
    check,
    error,
}: Props) {
    useEffect(() => {
        if (!isOpen) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [isOpen, onClose]);

    if (!isOpen || !host) return null;

    const isLoading = !check && !error;
    const actionLabel = ACTION_LABEL[type];

    // Build the list of warnings we'll surface as a summary. If empty, operator
    // can confirm the action without ceremony.
    const warnings: { icon: React.ReactNode; text: React.ReactNode; severity: 'high' | 'low' }[] = [];
    if (check) {
        const activeSessions = check.sessions.filter(s => {
            const st = (s.state || '').toLowerCase();
            return st.includes('active') || st.includes('ativo');
        });
        const disconnectedSessions = check.sessions.filter(s => {
            const st = (s.state || '').toLowerCase();
            return st.includes('disc');
        });
        if (activeSessions.length > 0) {
            warnings.push({
                icon: <Users size={16} />,
                severity: 'high',
                text: (
                    <>
                        <strong>{activeSessions.length}</strong> usuário(s) com sessão ativa: {' '}
                        <span className="font-mono text-xs">
                            {activeSessions.map(s => s.user).join(', ')}
                        </span>
                    </>
                ),
            });
        }
        if (disconnectedSessions.length > 0 && activeSessions.length === 0) {
            // Disconnected-only is a softer warning than active sessions.
            warnings.push({
                icon: <Users size={16} />,
                severity: 'low',
                text: (
                    <>
                        {disconnectedSessions.length} sessão(ões) desconectada(s): {' '}
                        <span className="font-mono text-xs">
                            {disconnectedSessions.map(s => s.user).join(', ')}
                        </span>
                    </>
                ),
            });
        }
        if (typeof check.uptime_minutes === 'number' && check.uptime_minutes < 10) {
            warnings.push({
                icon: <Clock size={16} />,
                severity: 'high',
                text: (
                    <>
                        Host reiniciou há <strong>{formatUptime(check.uptime_minutes)}</strong>. Tem certeza?
                    </>
                ),
            });
        }
        if (type === 'shutdown' && check.pending_reboot) {
            warnings.push({
                icon: <RotateCw size={16} />,
                severity: 'low',
                text: (
                    <>
                        Há reinício pendente ({check.pending_reasons.join(', ')}). Desligar agora não aplica.
                    </>
                ),
            });
        }
    }

    const noProblems = !isLoading && !error && warnings.length === 0;

    return (
        <div
            // z-[110] keeps this above HostDetailsModal (z-[100]), like the
            // delete/confirmation modals.
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[110] p-4"
            onClick={onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-lg p-6 shadow-2xl"
                onClick={(e) => e.stopPropagation()}
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="prepower-title"
            >
                <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div
                            className={clsx(
                                'p-2 rounded-lg',
                                warnings.some(w => w.severity === 'high')
                                    ? 'bg-red-500/10 text-red-400'
                                    : warnings.length > 0
                                        ? 'bg-yellow-500/10 text-yellow-400'
                                        : 'bg-blue-500/10 text-blue-400'
                            )}
                            aria-hidden="true"
                        >
                            {warnings.some(w => w.severity === 'high') ? <AlertTriangle size={20} /> : <Power size={20} />}
                        </div>
                        <div>
                            <h3 id="prepower-title" className="text-lg font-semibold text-white">
                                {actionLabel} {host.name || host.address}?
                            </h3>
                            <p className="text-xs text-zinc-500 font-mono mt-0.5">
                                {host.ip || host.address}
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="text-zinc-400 hover:text-white" aria-label="Fechar">
                        <X size={18} />
                    </button>
                </div>

                <div className="space-y-3 mb-5">
                    {isLoading && (
                        <div className="flex items-center gap-2 text-sm text-zinc-400 py-2">
                            <Loader2 size={16} className="animate-spin text-blue-400" />
                            Verificando estado do host…
                        </div>
                    )}

                    {error && (
                        <div className="flex items-start gap-2 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg text-sm">
                            <AlertTriangle size={16} className="text-yellow-400 mt-0.5 shrink-0" />
                            <div className="text-zinc-300">
                                Não foi possível verificar o estado do host: <span className="text-yellow-400">{error}</span>.
                                Você pode prosseguir mesmo assim.
                            </div>
                        </div>
                    )}

                    {check && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="bg-zinc-950/50 border border-zinc-800 rounded-lg p-3">
                                <div className="text-zinc-500 uppercase tracking-wide mb-1 flex items-center gap-1">
                                    <Clock size={11} /> Uptime
                                </div>
                                <div className="text-zinc-200 font-mono">{formatUptime(check.uptime_minutes)}</div>
                            </div>
                            <div className="bg-zinc-950/50 border border-zinc-800 rounded-lg p-3">
                                <div className="text-zinc-500 uppercase tracking-wide mb-1 flex items-center gap-1">
                                    <Users size={11} /> Sessões
                                </div>
                                <div className="text-zinc-200 font-mono">
                                    {check.sessions.length === 0
                                        ? 'Nenhuma'
                                        : `${check.sessions.length} (${check.sessions.filter(s => /(active|ativo)/i.test(s.state)).length} ativa(s))`}
                                </div>
                            </div>
                        </div>
                    )}

                    {warnings.map((w, i) => (
                        <div
                            key={i}
                            className={clsx(
                                'flex items-start gap-2 p-3 rounded-lg text-sm',
                                w.severity === 'high'
                                    ? 'bg-red-500/5 border border-red-500/20 text-zinc-200'
                                    : 'bg-yellow-500/5 border border-yellow-500/20 text-zinc-300'
                            )}
                        >
                            <span className={clsx('mt-0.5 shrink-0', w.severity === 'high' ? 'text-red-400' : 'text-yellow-400')}>
                                {w.icon}
                            </span>
                            <div>{w.text}</div>
                        </div>
                    ))}

                    {noProblems && (
                        <div className="text-sm text-zinc-400 py-2">
                            Tudo certo — nenhum aviso. {actionLabel.toLowerCase()} este host?
                        </div>
                    )}
                </div>

                <div className="flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm text-zinc-300 hover:text-white transition-colors"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={onProceed}
                        disabled={isLoading}
                        className={clsx(
                            'px-4 py-2 rounded-lg font-medium text-sm transition-colors flex items-center gap-2',
                            isLoading && 'opacity-50 cursor-not-allowed',
                            warnings.some(w => w.severity === 'high')
                                ? 'bg-red-600 hover:bg-red-500 text-white'
                                : 'bg-blue-600 hover:bg-blue-500 text-white'
                        )}
                    >
                        <Power size={14} />
                        {actionLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
