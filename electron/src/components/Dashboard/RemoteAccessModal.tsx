import React from 'react';
import { X, Monitor, Users } from 'lucide-react';
import { Host } from '../../types';
import { useToast } from '../../contexts/ToastContext';
import { resolveTeamViewerId, getDefaultCredentialIdIfAvailable } from '../../utils/teamviewer';
import { probeHost } from '../../utils/hostProbe';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';
import { ipForHost } from '../../utils/ipForHost';
import { TeamViewerCard, type TvFetchState } from './TeamViewerCard';

interface RemoteAccessModalProps {
    isOpen: boolean;
    onClose: () => void;
    host: Host;
}

export const RemoteAccessModal: React.FC<RemoteAccessModalProps> = ({ isOpen, onClose, host }) => {
    useEscapeToClose(isOpen, onClose);
    const { showToast } = useToast();
    const [localDomain, setLocalDomain] = React.useState<string>('');
    const [tvState, setTvState] = React.useState<TvFetchState>(() =>
        host.teamviewer_id ? { kind: 'success', id: host.teamviewer_id } : { kind: 'idle' }
    );

    React.useEffect(() => {
        if (host.teamviewer_id) {
            setTvState({ kind: 'success', id: host.teamviewer_id });
        } else {
            setTvState({ kind: 'idle' });
        }
    }, [host.teamviewer_id, isOpen]);

    React.useEffect(() => {
        if (isOpen) {
            window.electron.getLocalDomain().then(setLocalDomain).catch(console.error);
        }
    }, [isOpen]);

    const fetchSilently = React.useCallback(async () => {
        if (!host.address) return;
        setTvState({ kind: 'loading' });

        const credentialId = await getDefaultCredentialIdIfAvailable();
        if (!credentialId) {
            setTvState({
                kind: 'needs_credentials',
                reason: 'Cofre bloqueado ou credencial padrão não configurada.',
            });
            return;
        }

        const result = await resolveTeamViewerId({
            targetIp: host.ip || host.address,
            credentialId,
            persistOnHost: host.address,
        });

        probeHost({
            targetIp: host.ip || host.address,
            credentialId,
        }).catch(() => undefined);

        if (result.ok) {
            setTvState({ kind: 'success', id: result.id });
            showToast('TeamViewer ID encontrado e salvo!', 'success');
            return;
        }
        if (result.code === 'CREDENTIALS_UNAVAILABLE') {
            setTvState({ kind: 'needs_credentials', reason: result.message });
        } else if (result.code === 'NOT_FOUND') {
            setTvState({ kind: 'failed', message: result.message });
        } else {
            setTvState({ kind: 'needs_credentials', reason: result.message });
        }
    }, [host.address, host.ip, showToast]);

    const fetchWithInlineCredentials = React.useCallback(async (username: string, password: string) => {
        setTvState({ kind: 'loading' });
        const result = await resolveTeamViewerId({
            targetIp: host.ip || host.address,
            username,
            password,
            persistOnHost: host.address,
        });
        if (result.ok) {
            setTvState({ kind: 'success', id: result.id });
            showToast('TeamViewer ID encontrado e salvo!', 'success');
        } else if (result.code === 'NOT_FOUND') {
            setTvState({ kind: 'failed', message: result.message });
            showToast('TeamViewer não encontrado neste host.', 'warning');
        } else {
            setTvState({ kind: 'needs_credentials', reason: result.message });
            showToast(result.message, 'error');
        }
    }, [host.address, host.ip, showToast]);

    React.useEffect(() => {
        if (!isOpen) return;
        if (host.teamviewer_id) return;
        fetchSilently();
    }, [isOpen, host.address, host.teamviewer_id, fetchSilently]);

    if (!isOpen) return null;

    const handleLaunchRdp = () => {
        const target = host.ip || host.address;
        window.electron.launchRdp(target);
        showToast(`Iniciando RDP para ${target}...`, 'info');
        onClose();
    };

    const handleLaunchMsra = (askCredentials = false) => {
        const target = host.ip || host.address;
        window.electron.launchMsra(target, askCredentials);
        showToast(`Iniciando Assistência Remota para ${target}...`, 'info');
        onClose();
    };

    const handleLaunchTeamViewer = (id: string) => {
        const cleanId = id.replace(/\s+/g, '');
        window.electron.launchTeamViewer(cleanId);
        showToast(`Iniciando TeamViewer para ID ${cleanId}...`, 'info');

        setTimeout(() => {
            if (host.domain && host.domain === localDomain) {
                handleLaunchMsra(false);
            }
            onClose();
        }, 3000);
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose} role="presentation">
            <div
                className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl max-h-[85vh] sm:max-h-[90vh] overflow-y-auto custom-scrollbar shadow-2xl animate-in fade-in zoom-in duration-200 my-auto flex flex-col"
                onClick={e => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="remoteaccess-title"
            >
                {/* Header */}
                <div className="flex items-center justify-between p-5 sm:p-6 border-b border-zinc-800 bg-zinc-900/30 shrink-0">
                    <div>
                        <h2 id="remoteaccess-title" className="text-xl font-semibold text-white flex items-center gap-3">
                            <div className="p-2 bg-blue-500/10 rounded-lg">
                                <Monitor size={22} className="text-blue-400" aria-hidden="true" />
                            </div>
                            Acesso Remoto
                        </h2>
                        <p className="text-zinc-400 text-xs sm:text-sm mt-1 ml-11">Escolha uma ferramenta para conectar</p>
                    </div>
                    <button onClick={onClose} className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-all" aria-label="Fechar">
                        <X size={20} />
                    </button>
                </div>

                {/* Host Info */}
                <div className="px-5 sm:px-6 py-3.5 bg-zinc-900/50 border-b border-zinc-800 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]"></div>
                        <div>
                            <div className="text-white font-medium text-sm">{host.name || host.hostname || host.address}</div>
                            <div className="text-zinc-500 text-xs font-mono">{ipForHost(host) ?? 'Resolvendo...'}</div>
                        </div>
                    </div>
                    <div className="px-2.5 py-0.5 rounded-full bg-zinc-800 text-zinc-400 text-xs border border-zinc-700">
                        {host.vendor || "Genérico"}
                    </div>
                </div>

                {/* Tools Grid */}
                <div className="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
                    {/* RDP Card */}
                    <button
                        onClick={handleLaunchRdp}
                        className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-blue-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                        <div className="p-3 bg-zinc-800 group-hover:bg-blue-500/20 w-fit rounded-lg transition-colors">
                            <Monitor size={22} className="text-zinc-400 group-hover:text-blue-400 transition-colors" />
                        </div>
                        <div>
                            <div className="font-medium text-white group-hover:text-blue-400 transition-colors text-sm">RDP</div>
                            <div className="text-xs text-zinc-500">Conexão de Área de Trabalho Remota</div>
                        </div>
                    </button>

                    {/* MSRA Card */}
                    <div className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-purple-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                        <div className="flex items-start justify-between relative z-10">
                            <div className="p-3 bg-zinc-800 group-hover:bg-purple-500/20 w-fit rounded-lg transition-colors">
                                <Users size={22} className="text-zinc-400 group-hover:text-purple-400 transition-colors" />
                            </div>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleLaunchMsra(true);
                                }}
                                className="p-1.5 text-zinc-500 hover:text-purple-400 hover:bg-purple-500/10 rounded-lg transition-all text-xs"
                                title="Executar como outro usuário"
                                aria-label="Executar Assistência Remota como outro usuário"
                            >
                                <Users size={15} />
                            </button>
                        </div>
                        <div className="cursor-pointer relative z-10" onClick={() => handleLaunchMsra(false)}>
                            <div className="font-medium text-white group-hover:text-purple-400 transition-colors text-sm">Assistência Remota</div>
                            <div className="text-xs text-zinc-500">Solicitar controle via MSRA</div>
                        </div>
                    </div>

                    {/* TeamViewer Card */}
                    <TeamViewerCard
                        state={tvState}
                        initialDomain={host.domain}
                        onConnect={handleLaunchTeamViewer}
                        onSilentRetry={fetchSilently}
                        onManualSubmit={fetchWithInlineCredentials}
                    />
                </div>
            </div>
        </div>
    );
};
