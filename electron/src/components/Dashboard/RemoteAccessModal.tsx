import React from 'react';
import { X, Monitor, Users, ArrowUpDown, RefreshCw, AlertCircle, KeyRound } from 'lucide-react';
import { Host } from '../../types';
import { useToast } from '../../contexts/ToastContext';
import { resolveTeamViewerId, getDefaultCredentialIdIfAvailable } from '../../utils/teamviewer';
import { probeHost } from '../../utils/hostProbe';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';

interface RemoteAccessModalProps {
    isOpen: boolean;
    onClose: () => void;
    host: Host;
}

type TvFetchState =
    | { kind: 'idle' }
    | { kind: 'loading' }
    | { kind: 'success'; id: string }
    | { kind: 'needs_credentials'; reason: string } // ask inline (vault not usable or last attempt failed with bad creds)
    | { kind: 'failed'; message: string };          // technical failure (TrustedHosts, TV not installed, etc.) — offer retry

export const RemoteAccessModal: React.FC<RemoteAccessModalProps> = ({ isOpen, onClose, host }) => {
    useEscapeToClose(isOpen, onClose);
    const { showToast } = useToast();
    const [localDomain, setLocalDomain] = React.useState<string>('');
    const [tvState, setTvState] = React.useState<TvFetchState>(() =>
        host.teamviewer_id ? { kind: 'success', id: host.teamviewer_id } : { kind: 'idle' }
    );

    // Reseed when the host changes or modal reopens.
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

    /** Try first via vault default credential. If unavailable, fall to the
     *  inline credential form (kind = 'needs_credentials'). */
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
        // Silent probe with same vault credential — collects MAC/Domain/etc.
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
            // No TV installed / not detected: this is technical, not credentials.
            setTvState({ kind: 'failed', message: result.message });
        } else {
            // ERROR / TRUSTED_HOSTS_REQUIRED — let the user retry with inline creds
            // since those often mean the configured default cred lacks permission.
            setTvState({ kind: 'needs_credentials', reason: result.message });
        }
    }, [host.address, host.ip, showToast]);

    /** Called by the inline credential form. */
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
        } else {
            setTvState({ kind: 'needs_credentials', reason: result.message });
        }
        // Always fire a probe with these credentials — if the user just typed
        // valid admin creds we might as well harvest MAC/Domain/CurrentUser/
        // LastBoot/DiskFree on the side. Backend persists; we don't await.
        probeHost({
            targetIp: host.ip || host.address,
            username,
            password,
        }).catch(() => undefined);
    }, [host.address, host.ip, showToast]);

    // Auto-fetch on open if no ID yet.
    React.useEffect(() => {
        if (!isOpen) return;
        if (!host.teamviewer_id) {
            fetchSilently();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, host.address]);

    if (!isOpen) return null;

    const handleLaunchRdp = async () => {
        try {
            await window.electron.launchRdp(host.ip || host.address);
            onClose();
        } catch (error) {
            console.error('Failed to launch RDP:', error);
            showToast('Falha ao iniciar RDP', 'error');
        }
    };

    const handleLaunchMsra = async (forceOtherUser = false) => {
        try {
            let asOtherUser = forceOtherUser;
            if (!asOtherUser && host.domain && localDomain) {
                const hostDomain = host.domain.toLowerCase();
                const myDomain = localDomain.toLowerCase();
                if (!hostDomain.includes(myDomain) && !myDomain.includes(hostDomain)) {
                    asOtherUser = true;
                    showToast('Domínio diferente detectado. Solicitando credenciais...', 'info');
                }
            }
            await window.electron.launchMsra(host.ip || host.address, asOtherUser);
            onClose();
        } catch (error) {
            console.error('Failed to launch MSRA:', error);
            showToast('Falha ao iniciar Assistência Remota', 'error');
        }
    };

    const handleLaunchTeamViewer = (id: string) => {
        navigator.clipboard.writeText(id);
        showToast('Abrindo TeamViewer em 3s... ID copiado para a área de transferência!', 'info');
        setTimeout(() => {
            window.electron.launchTeamViewer(id);
            onClose();
        }, 3000);
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose} role="presentation">
            <div
                className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200"
                onClick={e => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="remoteaccess-title"
            >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-zinc-800 bg-zinc-900/30">
                    <div>
                        <h2 id="remoteaccess-title" className="text-xl font-semibold text-white flex items-center gap-3">
                            <div className="p-2 bg-blue-500/10 rounded-lg">
                                <Monitor size={24} className="text-blue-400" aria-hidden="true" />
                            </div>
                            Acesso Remoto
                        </h2>
                        <p className="text-zinc-400 text-sm mt-1 ml-12">Escolha uma ferramenta para conectar</p>
                    </div>
                    <button onClick={onClose} className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-all" aria-label="Fechar">
                        <X size={20} />
                    </button>
                </div>

                {/* Host Info */}
                <div className="px-6 py-4 bg-zinc-900/50 border-b border-zinc-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]"></div>
                        <div>
                            <div className="text-white font-medium">{host.name || host.hostname || host.address}</div>
                            <div className="text-zinc-500 text-xs font-mono">{host.ip || host.address}</div>
                        </div>
                    </div>
                    <div className="px-3 py-1 rounded-full bg-zinc-800 text-zinc-400 text-xs border border-zinc-700">
                        {host.vendor || "Genérico"}
                    </div>
                </div>

                {/* Tools Grid */}
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* RDP Card */}
                    <button
                        onClick={handleLaunchRdp}
                        className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-blue-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                        <div className="p-3 bg-zinc-800 group-hover:bg-blue-500/20 w-fit rounded-lg transition-colors">
                            <Monitor size={24} className="text-zinc-400 group-hover:text-blue-400 transition-colors" />
                        </div>
                        <div>
                            <div className="font-medium text-white group-hover:text-blue-400 transition-colors">RDP</div>
                            <div className="text-sm text-zinc-500">Conexão de Área de Trabalho Remota</div>
                        </div>
                    </button>

                    {/* MSRA Card */}
                    <div className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-purple-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                        <div className="flex items-start justify-between relative z-10">
                            <div className="p-3 bg-zinc-800 group-hover:bg-purple-500/20 w-fit rounded-lg transition-colors">
                                <Users size={24} className="text-zinc-400 group-hover:text-purple-400 transition-colors" />
                            </div>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleLaunchMsra(true);
                                }}
                                className="p-2 text-zinc-500 hover:text-purple-400 hover:bg-purple-500/10 rounded-lg transition-all"
                                title="Executar como outro usuário"
                                aria-label="Executar Assistência Remota como outro usuário"
                            >
                                <Users size={16} />
                            </button>
                        </div>
                        <div className="cursor-pointer relative z-10" onClick={() => handleLaunchMsra(false)}>
                            <div className="font-medium text-white group-hover:text-purple-400 transition-colors">Assistência Remota</div>
                            <div className="text-sm text-zinc-500">Solicitar controle via MSRA</div>
                        </div>
                    </div>

                    {/* TeamViewer Card — sempre visível, 4 estados */}
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

interface TeamViewerCardProps {
    state: TvFetchState;
    initialDomain?: string;
    onConnect: (id: string) => void;
    onSilentRetry: () => void;
    onManualSubmit: (username: string, password: string) => void;
}

function TeamViewerCard({ state, initialDomain, onConnect, onSilentRetry, onManualSubmit }: TeamViewerCardProps) {
    const baseCls = 'relative group p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden md:col-span-2';

    if (state.kind === 'success') {
        return (
            <button
                onClick={() => onConnect(state.id)}
                className={`${baseCls} hover:bg-zinc-800 hover:border-cyan-500/50`}
            >
                <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-zinc-800 group-hover:bg-cyan-500/20 w-fit rounded-lg transition-colors">
                        <ArrowUpDown size={24} className="text-zinc-400 group-hover:text-cyan-400 transition-colors rotate-45" />
                    </div>
                    <div>
                        <div className="font-medium text-white group-hover:text-cyan-400 transition-colors">TeamViewer</div>
                        <div className="text-sm text-zinc-500 flex items-center gap-2">
                            ID: <span className="font-mono text-zinc-400">{state.id}</span>
                            <span className="text-xs bg-zinc-800 px-2 py-0.5 rounded text-zinc-500">Conectar Automaticamente</span>
                        </div>
                    </div>
                </div>
            </button>
        );
    }

    if (state.kind === 'loading') {
        return (
            <div className={baseCls}>
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-zinc-800 w-fit rounded-lg">
                        <RefreshCw size={24} className="text-cyan-400 animate-spin" />
                    </div>
                    <div>
                        <div className="font-medium text-white">TeamViewer</div>
                        <div className="text-sm text-zinc-500">Buscando ID no host via WinRM…</div>
                    </div>
                </div>
            </div>
        );
    }

    if (state.kind === 'needs_credentials') {
        return (
            <ManualCredentialsForm
                reason={state.reason}
                initialDomain={initialDomain}
                onSubmit={onManualSubmit}
                onCancel={onSilentRetry}
            />
        );
    }

    // idle (auto-fetch should move us out of it) or failed.
    const failMessage = state.kind === 'failed' ? state.message : 'Aguardando…';
    return (
        <div className={baseCls}>
            <div className="flex items-start gap-4">
                <div className="p-3 bg-zinc-800 w-fit rounded-lg">
                    <AlertCircle size={24} className="text-red-400" />
                </div>
                <div className="flex-1">
                    <div className="font-medium text-white">TeamViewer ID não detectado</div>
                    <div className="text-sm text-zinc-500 mt-1">{failMessage}</div>
                    <button
                        onClick={onSilentRetry}
                        className="mt-3 inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300"
                    >
                        <RefreshCw size={12} /> Tentar novamente
                    </button>
                </div>
            </div>
        </div>
    );
}

/** Inline credential form rendered inside the TeamViewer card when the silent
 *  vault-based fetch can't run (locked vault, no default cred, or last attempt
 *  was rejected). The operator types creds *here* — no separate modal. */
function ManualCredentialsForm({
    reason,
    initialDomain,
    onSubmit,
    onCancel,
}: {
    reason: string;
    initialDomain?: string;
    onSubmit: (username: string, password: string) => void;
    onCancel: () => void;
}) {
    const [username, setUsername] = React.useState(initialDomain ? `${initialDomain}\\` : '');
    const [password, setPassword] = React.useState('');

    const submit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!username.trim() || !password) return;
        onSubmit(username.trim(), password);
    };

    return (
        <form
            onSubmit={submit}
            className="relative p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl flex flex-col gap-3 md:col-span-2"
        >
            <div className="flex items-start gap-4">
                <div className="p-3 bg-zinc-800 w-fit rounded-lg">
                    <KeyRound size={24} className="text-yellow-500" />
                </div>
                <div className="flex-1">
                    <div className="font-medium text-white">Credenciais para buscar TeamViewer ID</div>
                    <div className="text-sm text-zinc-500 mt-0.5">{reason}</div>
                </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label className="block text-xs text-zinc-400 mb-1">Usuário</label>
                    <input
                        type="text"
                        value={username}
                        onChange={e => setUsername(e.target.value)}
                        placeholder="DOMINIO\\usuario"
                        autoComplete="username"
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-cyan-500 placeholder:text-zinc-600"
                    />
                </div>
                <div>
                    <label className="block text-xs text-zinc-400 mb-1">Senha</label>
                    <input
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        autoComplete="current-password"
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-cyan-500"
                    />
                </div>
            </div>
            <div className="flex items-center gap-2">
                <button
                    type="submit"
                    disabled={!username.trim() || !password}
                    className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                    <KeyRound size={14} /> Buscar TeamViewer ID
                </button>
                <button
                    type="button"
                    onClick={onCancel}
                    className="px-3 py-2 text-xs text-zinc-400 hover:text-white"
                >
                    Tentar novamente com cofre
                </button>
            </div>
            <p className="text-[11px] text-zinc-600">
                As credenciais são usadas só para esta consulta WinRM e não ficam armazenadas no aplicativo.
                Para evitar digitá-las toda vez, configure uma credencial padrão em Configurações → Acesso Remoto.
            </p>
        </form>
    );
}
