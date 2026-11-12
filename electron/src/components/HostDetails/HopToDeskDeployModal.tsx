import React, { useState, useEffect } from 'react';
import {
    Monitor,
    X,
    User,
    LogOut,
    Check,
    RefreshCw,
    Shield,
    ShieldAlert,
    ExternalLink,
    HardDrive,
    Lock,
    Users,
    Trash2,
    Search
} from 'lucide-react';
import { Session } from '../../types';
import { API_BASE } from '../../config/api';
import { deployAndResolveHopToDeskId, launchLocalHopToDesk } from '../../utils/hoptodesk';

export interface UserProfileFolder {
    Username: string;
    Path: string;
    DesktopPath: string;
}

interface HopToDeskDeployModalProps {
    isOpen: boolean;
    onClose: () => void;
    targetIp: string;
    hostname?: string;
    initialDomain?: string;
    credentials?: { username: string; password?: string } | null;
    sessions?: Session[];
    userProfiles?: UserProfileFolder[];
    onFetchSessions?: () => Promise<void> | void;
    onHoptodeskResolved: (id: string, running?: boolean) => void;
    showToast: (message: string, type: 'success' | 'error' | 'info' | 'warning') => void;
    formatDate?: (dateStr: string) => string;
}

export const HopToDeskDeployModal: React.FC<HopToDeskDeployModalProps> = ({
    isOpen,
    onClose,
    targetIp,
    hostname,
    initialDomain = '',
    credentials,
    sessions: initialSessions = [],
    userProfiles: initialUserProfiles = [],
    onFetchSessions,
    onHoptodeskResolved,
    showToast,
    formatDate = (d) => d
}) => {
    // Modo de instalação: 'public' (Área de Trabalho Pública) ou 'user' (Área de Trabalho do Usuário)
    const [targetLocation, setTargetLocation] = useState<'public' | 'user'>('public');
    const [selectedUser, setSelectedUser] = useState<string>('');

    // Pastas de usuários em C:\Users
    const [userProfiles, setUserProfiles] = useState<UserProfileFolder[]>(initialUserProfiles);
    const [isLoadingProfiles, setIsLoadingProfiles] = useState<boolean>(false);
    const [userSearchTerm, setUserSearchTerm] = useState<string>('');

    // Credenciais (usa do pai se disponível, senão formulário local)
    const [username, setUsername] = useState<string>(credentials?.username || '');
    const [password, setPassword] = useState<string>(credentials?.password || '');
    const [domain, setDomain] = useState<string>(initialDomain);

    // Lista de sessões ativas locais (com atualização em tempo real ao deslogar)
    const [activeSessions, setActiveSessions] = useState<Session[]>(initialSessions);
    const [disconnectingSessionId, setDisconnectingSessionId] = useState<string | null>(null);

    // Estado do deployment
    const [isDeploying, setIsDeploying] = useState<boolean>(false);
    const [deployStatus, setDeployStatus] = useState<string | null>(null);
    const [resolvedId, setResolvedId] = useState<string | null>(null);
    const [isRemoving, setIsRemoving] = useState<boolean>(false);
    const [isLoadingSessions, setIsLoadingSessions] = useState<boolean>(false);

    // Sincronizar credenciais do pai se mudarem
    useEffect(() => {
        if (credentials?.username) {
            setUsername(credentials.username);
        }
        if (credentials?.password) {
            setPassword(credentials.password);
        }
    }, [credentials]);

    // Sincronizar perfis de usuário iniciais
    useEffect(() => {
        if (initialUserProfiles && initialUserProfiles.length > 0) {
            setUserProfiles(initialUserProfiles);
            if (!selectedUser) {
                setSelectedUser(initialUserProfiles[0].Username);
            }
        }
    }, [initialUserProfiles]);

    // Sincronizar sessões iniciais
    useEffect(() => {
        setActiveSessions(initialSessions);
        if (initialSessions.length > 0 && !selectedUser) {
            // Seleciona por padrão o primeiro usuário ativo
            const active = initialSessions.find(s => s.State === 'Active') || initialSessions[0];
            const clean = active.UserName.split('\\').pop() || active.UserName;
            setSelectedUser(clean);
        }
    }, [initialSessions]);

    const fetchSessionsDirect = async () => {
        const effectiveUser = username || credentials?.username;
        const effectivePass = password || credentials?.password;
        if (!targetIp || !effectiveUser || !effectivePass) return;

        setIsLoadingSessions(true);
        try {
            const res = await fetch(`${API_BASE}/system/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_ip: targetIp,
                    username: effectiveUser,
                    password: effectivePass
                })
            });
            if (res.ok && res.body) {
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                const list: Session[] = [];
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() ?? '';
                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const parsed = JSON.parse(line);
                            if (parsed.status === 'success' && parsed.data) {
                                if (Array.isArray(parsed.data)) {
                                    list.push(...parsed.data);
                                } else {
                                    list.push(parsed.data);
                                }
                            }
                        } catch {}
                    }
                }
                if (list.length > 0) {
                    setActiveSessions(list);
                    if (!selectedUser) {
                        const clean = list[0].UserName.split('\\').pop() || list[0].UserName;
                        setSelectedUser(clean);
                    }
                }
            }
        } catch {} finally {
            setIsLoadingSessions(false);
        }
    };

    const fetchUserProfilesDirect = async () => {
        const effectiveUser = username || credentials?.username;
        const effectivePass = password || credentials?.password;
        if (!targetIp || !effectiveUser || !effectivePass) return;

        setIsLoadingProfiles(true);
        try {
            const res = await fetch(`${API_BASE}/system/user-profiles`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_ip: targetIp,
                    username: effectiveUser,
                    password: effectivePass
                })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.status === 'success' && Array.isArray(data.profiles)) {
                setUserProfiles(data.profiles);
                if (!selectedUser && data.profiles.length > 0) {
                    setSelectedUser(data.profiles[0].Username);
                }
            }
        } catch {} finally {
            setIsLoadingProfiles(false);
        }
    };

    const handleRefreshAll = async () => {
        const promises: Promise<any>[] = [];
        if (onFetchSessions && credentials?.username) {
            setIsLoadingSessions(true);
            promises.push(Promise.resolve(onFetchSessions()).finally(() => setIsLoadingSessions(false)));
        } else {
            promises.push(fetchSessionsDirect());
        }
        promises.push(fetchUserProfilesDirect());
        await Promise.all(promises);
    };

    // Disparar imediatamente o carregamento de sessões e pastas ao abrir o modal
    useEffect(() => {
        if (isOpen) {
            handleRefreshAll();
        }
    }, [isOpen]);

    if (!isOpen) return null;

    // Desconectar / Deslogar usuário
    const handleDisconnectUser = async (sessionId: string, userName: string) => {
        const effectiveUser = username || credentials?.username;
        const effectivePass = password || credentials?.password;

        if (!effectiveUser || !effectivePass) {
            showToast('Informe as credenciais de administrador para deslogar o usuário.', 'warning');
            return;
        }

        setDisconnectingSessionId(sessionId);
        try {
            const res = await fetch(`${API_BASE}/system/disconnect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_ip: targetIp,
                    username: effectiveUser,
                    password: effectivePass,
                    session_id: sessionId
                })
            });

            if (res.ok) {
                showToast(`Sessão de ${userName} desconectada com sucesso!`, 'success');
                setActiveSessions(prev => prev.filter(s => s.ID !== sessionId));
            } else {
                const err = await res.json().catch(() => ({}));
                showToast(err.message || 'Falha ao desconectar usuário remoto.', 'error');
            }
        } catch (e: any) {
            showToast(`Erro ao desconectar: ${e.message}`, 'error');
        } finally {
            setDisconnectingSessionId(null);
        }
    };

    // Submissão do deployment
    const handleDeploy = async () => {
        const effectiveUser = username || credentials?.username;
        const effectivePass = password || credentials?.password;

        if (!effectiveUser || !effectivePass) {
            showToast('Credenciais de administrador são obrigatórias para implantar.', 'warning');
            return;
        }

        const targetUser = targetLocation === 'user' ? selectedUser.trim() : undefined;
        if (targetLocation === 'user' && !targetUser) {
            showToast('Selecione a pasta do usuário de destino.', 'warning');
            return;
        }

        setIsDeploying(true);
        setDeployStatus('Iniciando implantação e inicialização...');
        setResolvedId(null);

        try {
            const res = await deployAndResolveHopToDeskId({
                targetIp,
                username: effectiveUser,
                password: effectivePass,
                targetLocation,
                targetUser,
                persistOnHost: targetIp,
                onProgress: (msg) => setDeployStatus(msg)
            });

            if (res.ok) {
                setResolvedId(res.id);
                if (res.running) {
                    showToast(`HopToDesk implantado e em execução! ID: ${res.id}`, 'success');
                } else {
                    showToast(`HopToDesk copiado (ID: ${res.id}), mas a janela gráfica ainda não abriu.`, 'warning');
                }
                onHoptodeskResolved(res.id, res.running ?? true);
                onClose();
            } else {
                showToast(res.message, 'error');
            }
        } catch (e: any) {
            showToast(`Falha: ${e.message}`, 'error');
        } finally {
            setIsDeploying(false);
            setDeployStatus(null);
        }
    };

    const handleRemoveFromHost = async () => {
        const effectiveUser = username || credentials?.username;
        const effectivePass = password || credentials?.password;
        if (!effectiveUser || !effectivePass) {
            showToast('Credenciais de administrador são obrigatórias para remover.', 'warning');
            return;
        }
        if (!window.confirm('Deseja realmente parar o serviço e remover todos os arquivos do HopToDesk deste host remoto?')) {
            return;
        }
        setIsRemoving(true);
        try {
            const res = await fetch(`${API_BASE}/system/hoptodesk/remove`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_ip: targetIp,
                    username: effectiveUser,
                    password: effectivePass
                })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.status === 'success') {
                showToast(data.message || 'HopToDesk removido com sucesso!', 'success');
                setResolvedId(null);
                onHoptodeskResolved('');
                onClose();
            } else {
                showToast(data.message || 'Falha ao remover HopToDesk.', 'error');
            }
        } catch (e: any) {
            showToast(`Erro ao remover: ${e.message}`, 'error');
        } finally {
            setIsRemoving(false);
        }
    };

    const handleConnectNow = async () => {
        if (!resolvedId) return;
        showToast(`Iniciando HopToDesk para ID ${resolvedId}...`, 'info');
        await launchLocalHopToDesk(resolvedId);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200 overflow-y-auto">
            <div className="bg-zinc-900 border border-zinc-700/80 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden flex flex-col my-8">
                {/* Header */}
                <div className="p-5 bg-zinc-800/60 border-b border-zinc-700/60 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
                            <Monitor size={22} />
                        </div>
                        <div>
                            <h2 className="text-base font-bold text-white flex items-center gap-2">
                                Configuração e Implantação do HopToDesk
                            </h2>
                            <p className="text-xs text-zinc-400 mt-0.5 font-mono">
                                Alvo: <span className="text-emerald-400 font-semibold">{hostname || targetIp}</span> ({targetIp})
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        disabled={isDeploying}
                        className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors disabled:opacity-50"
                        title="Fechar"
                    >
                        <X size={18} />
                    </button>
                </div>

                <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(85vh-140px)] custom-scrollbar">
                    {/* ID Resolvido com Sucesso */}
                    {resolvedId && (
                        <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-4 flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg">
                                    <Check size={20} />
                                </div>
                                <div>
                                    <span className="text-xs text-emerald-300 font-semibold uppercase tracking-wider">
                                        HopToDesk Configurado e Ativo
                                    </span>
                                    <div className="text-lg font-mono font-bold text-white tracking-widest mt-0.5">
                                        {resolvedId}
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={handleConnectNow}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-emerald-900/30 transition-all hover:-translate-y-0.5"
                            >
                                <ExternalLink size={14} />
                                Conectar Agora
                            </button>
                        </div>
                    )}

                    {/* Escolha do Destino de Instalação */}
                    <div className="space-y-3">
                        <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                            <HardDrive size={15} className="text-blue-400" />
                            Onde deseja implantar o HopToDesk no host remoto?
                        </label>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                            {/* Opção 1: Área de Trabalho Pública */}
                            <div
                                onClick={() => setTargetLocation('public')}
                                className={`cursor-pointer rounded-xl p-4 border transition-all flex flex-col justify-between ${
                                    targetLocation === 'public'
                                        ? 'bg-emerald-500/10 border-emerald-500/50 ring-1 ring-emerald-500/30'
                                        : 'bg-zinc-800/40 border-zinc-700/60 hover:border-zinc-600'
                                }`}
                            >
                                <div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm font-bold text-white">
                                            Área de Trabalho Pública
                                        </span>
                                        <span className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                                            targetLocation === 'public' ? 'border-emerald-500 bg-emerald-500' : 'border-zinc-600'
                                        }`}>
                                            {targetLocation === 'public' && <Check size={11} className="text-black stroke-[3]" />}
                                        </span>
                                    </div>
                                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                                        Disponível para <strong className="text-zinc-200">todos os usuários</strong> do computador em <span className="font-mono text-[11px] text-zinc-300">C:\Users\Public\Desktop</span>.
                                    </p>
                                </div>

                                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded-lg">
                                    <ShieldAlert size={13} className="shrink-0" />
                                    <span>Requer credenciais de administrador da rede</span>
                                </div>
                            </div>

                            {/* Opção 2: Área de Trabalho do Usuário */}
                            <div
                                onClick={() => setTargetLocation('user')}
                                className={`cursor-pointer rounded-xl p-4 border transition-all flex flex-col justify-between ${
                                    targetLocation === 'user'
                                        ? 'bg-emerald-500/10 border-emerald-500/50 ring-1 ring-emerald-500/30'
                                        : 'bg-zinc-800/40 border-zinc-700/60 hover:border-zinc-600'
                                }`}
                            >
                                <div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm font-bold text-white">
                                            Área de Trabalho do Usuário
                                        </span>
                                        <span className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                                            targetLocation === 'user' ? 'border-emerald-500 bg-emerald-500' : 'border-zinc-600'
                                        }`}>
                                            {targetLocation === 'user' && <Check size={11} className="text-black stroke-[3]" />}
                                        </span>
                                    </div>
                                    <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                                        Copia diretamente para o perfil específico do usuário em <span className="font-mono text-[11px] text-zinc-300">C:\Users\&lt;usuario&gt;\Desktop</span>.
                                    </p>
                                </div>

                                <div className="mt-3 flex items-center gap-1.5 text-[11px] text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-1 rounded-lg">
                                    <User size={13} className="shrink-0" />
                                    <span>Inicia na tela da sessão ativa do usuário</span>
                                </div>
                            </div>
                        </div>

                        {/* Seleção do Usuário se opção 'user' ativa */}
                        {targetLocation === 'user' && (() => {
                            const term = userSearchTerm.toLowerCase().trim();
                            const filteredProfiles = userProfiles.filter(prof => {
                                if (!term) return true;
                                return prof.Username.toLowerCase().includes(term) || (prof.DesktopPath && prof.DesktopPath.toLowerCase().includes(term));
                            });
                            const filteredSessions = activeSessions.filter(s => {
                                if (!term) return true;
                                return s.UserName.toLowerCase().includes(term);
                            });

                            return (
                                <div className="bg-zinc-800/60 border border-zinc-700/60 rounded-xl p-4 space-y-3 animate-in fade-in">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs font-semibold text-zinc-300 flex items-center gap-2">
                                            <Users size={14} className="text-emerald-400" />
                                            <span>Selecione a pasta do usuário em C:\Users:</span>
                                            {userProfiles.length > 0 && (
                                                <span className="text-[11px] text-zinc-400 font-normal">
                                                    ({filteredProfiles.length}{filteredProfiles.length !== userProfiles.length ? ` de ${userProfiles.length}` : ''})
                                                </span>
                                            )}
                                        </label>
                                        <button
                                            type="button"
                                            onClick={fetchUserProfilesDirect}
                                            disabled={isLoadingProfiles}
                                            className="p-1 hover:bg-zinc-700/60 rounded text-zinc-400 hover:text-white transition-colors text-[11px] flex items-center gap-1"
                                            title="Recarregar lista de pastas em C:\Users"
                                        >
                                            <RefreshCw size={12} className={isLoadingProfiles ? "animate-spin text-emerald-400" : ""} />
                                            <span>Atualizar pastas</span>
                                        </button>
                                    </div>

                                    {/* Campo de Busca / Filtro de Usuários */}
                                    <div className="relative">
                                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                                        <input
                                            type="text"
                                            value={userSearchTerm}
                                            onChange={(e) => setUserSearchTerm(e.target.value)}
                                            placeholder="Pesquisar usuário... (ex: diego, leonidas)"
                                            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-9 pr-8 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-all"
                                        />
                                        {userSearchTerm && (
                                            <button
                                                type="button"
                                                onClick={() => setUserSearchTerm('')}
                                                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-zinc-400 hover:text-white rounded"
                                                title="Limpar filtro"
                                            >
                                                <X size={12} />
                                            </button>
                                        )}
                                    </div>

                                    {isLoadingProfiles && userProfiles.length === 0 ? (
                                        <div className="p-4 bg-zinc-900/60 border border-zinc-700/40 rounded-xl text-center text-xs text-zinc-400 flex items-center justify-center gap-2">
                                            <RefreshCw size={14} className="animate-spin text-emerald-400" />
                                            <span>Localizando pastas de usuários em C:\Users no host remoto...</span>
                                        </div>
                                    ) : userProfiles.length > 0 ? (
                                        filteredProfiles.length > 0 ? (
                                            <div className="space-y-2 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                                                {filteredProfiles.map((prof) => {
                                                    const isSelected = selectedUser.toLowerCase() === prof.Username.toLowerCase();
                                                    const sessionMatch = activeSessions.find(
                                                        s => (s.UserName.split('\\').pop() || s.UserName).toLowerCase() === prof.Username.toLowerCase()
                                                    );
                                                    return (
                                                        <div
                                                            key={prof.Username}
                                                            onClick={() => setSelectedUser(prof.Username)}
                                                            className={`cursor-pointer p-3 rounded-xl border text-xs flex items-center justify-between transition-all ${
                                                                isSelected
                                                                    ? 'bg-emerald-500/15 border-emerald-500/60 ring-1 ring-emerald-500/30 text-white shadow-sm'
                                                                    : 'bg-zinc-900/60 border-zinc-700/50 text-zinc-300 hover:bg-zinc-800/60 hover:border-zinc-600'
                                                            }`}
                                                        >
                                                            <div className="flex items-center gap-2.5">
                                                                <User size={15} className={isSelected ? 'text-emerald-400' : 'text-zinc-400'} />
                                                                <div>
                                                                    <div className="font-semibold flex items-center gap-2">
                                                                        <span>{prof.Username}</span>
                                                                        {sessionMatch ? (
                                                                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                                                                Sessão {sessionMatch.ID} • {sessionMatch.State === 'Active' ? 'Ativo' : sessionMatch.State}
                                                                            </span>
                                                                        ) : (
                                                                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/60">
                                                                                Perfil Local
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <div className="text-[11px] font-mono text-zinc-400 mt-0.5">
                                                                        {prof.DesktopPath || `C:\\Users\\${prof.Username}\\Desktop`}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <span className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                                                                isSelected ? 'border-emerald-500 bg-emerald-500' : 'border-zinc-600'
                                                            }`}>
                                                                {isSelected && <Check size={11} className="text-black stroke-[3]" />}
                                                            </span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        ) : (
                                            <div className="p-4 bg-zinc-900/40 border border-zinc-700/40 rounded-xl text-center text-xs text-zinc-400 space-y-1">
                                                <div>Nenhum usuário corresponde a "<strong>{userSearchTerm}</strong>".</div>
                                                <button
                                                    type="button"
                                                    onClick={() => setUserSearchTerm('')}
                                                    className="text-emerald-400 hover:underline text-[11px]"
                                                >
                                                    Limpar filtro
                                                </button>
                                            </div>
                                        )
                                    ) : activeSessions.length > 0 ? (
                                        filteredSessions.length > 0 ? (
                                            <div className="space-y-2 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                                                {filteredSessions.map((s) => {
                                                    const cleanName = s.UserName.split('\\').pop() || s.UserName;
                                                    const isSelected = selectedUser.toLowerCase() === cleanName.toLowerCase();
                                                    return (
                                                        <div
                                                            key={s.ID}
                                                            onClick={() => setSelectedUser(cleanName)}
                                                            className={`cursor-pointer p-3 rounded-xl border text-xs flex items-center justify-between transition-all ${
                                                                isSelected
                                                                    ? 'bg-emerald-500/15 border-emerald-500/60 ring-1 ring-emerald-500/30 text-white'
                                                                    : 'bg-zinc-900/60 border-zinc-700/50 text-zinc-300 hover:bg-zinc-800/60 hover:border-zinc-600'
                                                            }`}
                                                        >
                                                            <div className="flex items-center gap-2.5">
                                                                <User size={15} className={isSelected ? 'text-emerald-400' : 'text-zinc-400'} />
                                                                <div>
                                                                    <div className="font-semibold flex items-center gap-2">
                                                                        <span>{cleanName}</span>
                                                                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                                                            Sessão {s.ID} • {s.State === 'Active' ? 'Ativo' : s.State}
                                                                        </span>
                                                                    </div>
                                                                    <div className="text-[11px] font-mono text-zinc-400 mt-0.5">
                                                                        C:\Users\{cleanName}\Desktop
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <span className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                                                                isSelected ? 'border-emerald-500 bg-emerald-500' : 'border-zinc-600'
                                                            }`}>
                                                                {isSelected && <Check size={11} className="text-black stroke-[3]" />}
                                                            </span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        ) : (
                                            <div className="p-4 bg-zinc-900/40 border border-zinc-700/40 rounded-xl text-center text-xs text-zinc-400 space-y-1">
                                                <div>Nenhuma sessão corresponde a "<strong>{userSearchTerm}</strong>".</div>
                                                <button
                                                    type="button"
                                                    onClick={() => setUserSearchTerm('')}
                                                    className="text-emerald-400 hover:underline text-[11px]"
                                                >
                                                    Limpar filtro
                                                </button>
                                            </div>
                                        )
                                    ) : (
                                        <div className="p-4 bg-zinc-900/40 border border-zinc-700/40 rounded-xl text-center text-xs text-zinc-400">
                                            Nenhum perfil de usuário encontrado em C:\Users no host remoto.
                                        </div>
                                    )}
                                </div>
                            );
                        })()}
                    </div>

                    {/* Sessões Ativas & Botão de Deslogar */}
                    <div className="space-y-3 pt-2 border-t border-zinc-800">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="flex items-center gap-2">
                                    <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                        <Users size={15} className="text-purple-400" />
                                        Sessões Conectadas no Host ({activeSessions.length})
                                    </h3>
                                    <button
                                        onClick={handleRefreshAll}
                                        disabled={isLoadingSessions || isLoadingProfiles}
                                        className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors"
                                        title="Atualizar sessões ativas e perfis do host"
                                    >
                                        <RefreshCw size={12} className={(isLoadingSessions || isLoadingProfiles) ? "animate-spin text-purple-400" : ""} />
                                    </button>
                                </div>
                                <p className="text-[11px] text-zinc-400 mt-0.5">
                                    Gerencie os usuários ativos. Você pode desconectar sessões indesejadas antes ou após a implantação.
                                </p>
                            </div>
                        </div>

                        {isLoadingSessions && activeSessions.length === 0 ? (
                            <div className="bg-zinc-800/30 border border-zinc-700/40 rounded-xl p-4 text-center text-xs text-zinc-400 flex items-center justify-center gap-2">
                                <RefreshCw size={14} className="animate-spin text-purple-400" />
                                <span>Consultando sessões ativas no host...</span>
                            </div>
                        ) : activeSessions.length === 0 ? (
                            <div className="bg-zinc-800/30 border border-zinc-700/40 rounded-xl p-4 text-center text-xs text-zinc-400 space-y-1">
                                <div className="font-medium text-zinc-300">Nenhum usuário logado no momento (computador na tela de logon/bloqueio)</div>
                                <div className="text-[11px] text-emerald-400">
                                    ✓ O HopToDesk será instalado como Serviço do Windows e aceitará conexão mesmo sem usuário logado.
                                </div>
                            </div>
                        ) : (
                            <div className="border border-zinc-700/50 rounded-xl overflow-hidden divide-y divide-zinc-700/40 bg-zinc-900/40">
                                {activeSessions.map((s) => {
                                    const isDisconnecting = disconnectingSessionId === s.ID;
                                    const isActive = s.State === 'Active';
                                    return (
                                        <div key={s.ID} className="p-3 flex items-center justify-between gap-3 text-xs">
                                            <div className="flex items-center gap-2.5">
                                                <div className="p-1.5 rounded-lg bg-zinc-800 text-zinc-300 border border-zinc-700 shrink-0">
                                                    <User size={14} />
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-white flex items-center gap-2">
                                                        <span>{s.UserName}</span>
                                                        <span className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${
                                                            isActive
                                                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                                                : 'bg-zinc-700/40 text-zinc-400 border border-zinc-700/50'
                                                        }`}>
                                                            {isActive ? 'Ativo' : s.State}
                                                        </span>
                                                    </div>
                                                    <div className="text-[11px] text-zinc-400 font-mono mt-0.5">
                                                        ID Sessão: {s.ID} • {s.SessionName || 'Remoto'} {s.LogonTime ? `• Logon: ${formatDate(s.LogonTime)}` : ''}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Botão Deslogar Usuário */}
                                            <button
                                                onClick={() => handleDisconnectUser(s.ID, s.UserName)}
                                                disabled={isDisconnecting || isDeploying}
                                                className="px-2.5 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/20 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50"
                                                title={`Desconectar a sessão de ${s.UserName} remotamente`}
                                            >
                                                {isDisconnecting ? (
                                                    <RefreshCw size={13} className="animate-spin text-red-400" />
                                                ) : (
                                                    <LogOut size={13} />
                                                )}
                                                <span>{isDisconnecting ? 'Deslogando...' : 'Deslogar'}</span>
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        <div className="text-[11px] text-zinc-400 flex items-start gap-1.5 bg-zinc-800/40 p-2.5 rounded-lg border border-zinc-700/40">
                            <Shield size={14} className="text-zinc-400 shrink-0 mt-0.5" />
                            <span>
                                <strong>Nota técnica de segurança:</strong> Deslogar usuários remotamente no Windows requer estritamente privilégios de Administrador da rede (execução do comando nativo <code className="text-zinc-300 font-mono">logoff</code> via WinRM ou RPC).
                            </span>
                        </div>
                    </div>

                    {/* Formulário de Credenciais se não herdadas */}
                    {(!credentials?.username || !credentials?.password) && (
                        <div className="space-y-3 pt-2 border-t border-zinc-800">
                            <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                <Lock size={15} className="text-amber-400" />
                                Credenciais Administrativas Necessárias
                            </label>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                                <input
                                    type="text"
                                    value={domain}
                                    onChange={(e) => setDomain(e.target.value)}
                                    placeholder="Domínio (opcional)"
                                    className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                                />
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    placeholder="Usuário Administrador"
                                    className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                                />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="Senha"
                                    className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                                />
                            </div>
                        </div>
                    )}

                    {/* Status de Implantação em Progresso */}
                    {isDeploying && (
                        <div className="bg-zinc-800/80 border border-emerald-500/30 rounded-xl p-3.5 flex items-center gap-3 animate-pulse">
                            <RefreshCw size={18} className="animate-spin text-emerald-400 shrink-0" />
                            <div className="text-xs text-zinc-200">
                                {deployStatus || 'Implantando HopToDesk no host remoto...'}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer de Ações */}
                <div className="p-4 bg-zinc-800/60 border-t border-zinc-700/60 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={onClose}
                            disabled={isDeploying || isRemoving}
                            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors disabled:opacity-50"
                        >
                            Fechar
                        </button>
                        <button
                            type="button"
                            onClick={handleRemoveFromHost}
                            disabled={isDeploying || isRemoving}
                            className="px-3 py-2 text-xs font-semibold text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20 rounded-xl transition-all disabled:opacity-50 flex items-center gap-1.5"
                            title="Remover arquivos do HopToDesk e parar o serviço no host remoto"
                        >
                            {isRemoving ? <RefreshCw size={13} className="animate-spin" /> : <Trash2 size={13} />}
                            <span>{isRemoving ? 'Removendo...' : 'Remover do Host'}</span>
                        </button>
                    </div>

                    <div className="flex items-center gap-3">
                        {resolvedId && (
                            <button
                                onClick={handleConnectNow}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-emerald-900/30 transition-all hover:-translate-y-0.5"
                            >
                                <ExternalLink size={14} />
                                Conectar
                            </button>
                        )}

                        <button
                            onClick={handleDeploy}
                            disabled={isDeploying}
                            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-emerald-900/30 transition-all hover:-translate-y-0.5 disabled:opacity-50"
                        >
                            {isDeploying ? (
                                <>
                                    <RefreshCw size={14} className="animate-spin" />
                                    <span>Implantando...</span>
                                </>
                            ) : (
                                <>
                                    <Monitor size={14} />
                                    <span>Implantar & Iniciar HopToDesk</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};
