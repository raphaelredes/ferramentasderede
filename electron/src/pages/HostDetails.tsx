import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
    ArrowLeft, RefreshCw, Copy, Check, Terminal,
    Monitor, Power, Lock, MessageSquare, X, AlertCircle
} from 'lucide-react';
import { HostInfoTab } from '../components/HostDetails/HostInfoTab';
import { HostHistoryTab } from '../components/HostDetails/HostHistoryTab';
import { ServicesTab } from '../components/HostDetails/ServicesTab';
import { PrintServiceTab } from '../components/HostDetails/PrintServiceTab';
import { LogsTab } from '../components/HostDetails/LogsTab';
import { SessionsTab } from '../components/HostDetails/SessionsTab';
import { CredentialModal } from '../components/CredentialModal';
import { DisconnectUserModal } from '../components/HostDetails/DisconnectUserModal';
import TrustedHostsModal from '../components/TrustedHostsModal';
import { TestConnectionModal } from '../components/HostDetails/TestConnectionModal';
import { RemoteAccessModal } from '../components/Dashboard/RemoteAccessModal';
import { useHostData } from '../hooks/useHostData';
import { useToast } from '../contexts/ToastContext';
import { useTrustedHostsSession } from '../contexts/TrustedHostsSessionContext';
import { Host } from '../types';
import { HelpButton } from '../components/HelpButton';
import { API_BASE } from '../config/api';

interface Session {
    UserName: string;
    ID: string;
    State: string;
    SessionName: string;
    LogonTime?: string;
    Duration?: string;
}

export const HostDetails: React.FC = () => {
    const { ip } = useParams<{ ip: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { showToast } = useToast();
    const { isApproved: isTrustedSessionApproved } = useTrustedHostsSession();

    const [activeTab, setActiveTab] = useState('info');
    const [credentials, setCredentials] = useState<{ username: string, password: string } | null>(null);
    const [testCredentials, setTestCredentials] = useState<{ username: string, password: string } | null>(null);
    const [authContext, setAuthContext] = useState<'main' | 'test' | 'service' | 'power'>('main');
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
    const [isTestConnectionModalOpen, setIsTestConnectionModalOpen] = useState(false);
    const [pendingServiceAction, setPendingServiceAction] = useState<{ name: string, action: string, startupType?: string } | null>(null);

    // Remote Access Modal State
    const [isRemoteModalOpen, setIsRemoteModalOpen] = useState(false);

    // Power & Message Modal State
    const [isPowerModalOpen, setIsPowerModalOpen] = useState(false);
    const [powerAction, setPowerAction] = useState<'restart' | 'shutdown' | 'message'>('restart');
    const [powerMessage, setPowerMessage] = useState('');
    const [powerDelay, setPowerDelay] = useState(10);
    const [isPowerExecuting, setIsPowerExecuting] = useState(false);

    // Disconnect Modal State
    const [isDisconnectModalOpen, setIsDisconnectModalOpen] = useState(false);
    const [sessionToDisconnect, setSessionToDisconnect] = useState<Session | null>(null);
    const [isDisconnecting, setIsDisconnecting] = useState(false);

    // TrustedHosts Modal State
    const [isTrustedHostsModalOpen, setIsTrustedHostsModalOpen] = useState(false);
    const [pendingAction, setPendingAction] = useState<(() => Promise<void>) | null>(null);

    // Copy feedback states
    const [copiedIp, setCopiedIp] = useState(false);
    const [copiedHostname, setCopiedHostname] = useState(false);

    const [currentHost, setCurrentHost] = useState<any>(null);
    const [localDomain, setLocalDomain] = useState('');

    useEffect(() => {
        const fetchDomain = async () => {
            try {
                if (window.electron) {
                    const domain = await window.electron.getLocalDomain();
                    setLocalDomain(domain);
                } else if (window.pywebview?.api) {
                    const domain = await window.pywebview.api.get_local_domain();
                    setLocalDomain(domain);
                }
            } catch (error) {
                console.error("Failed to get local domain:", error);
            }
        };
        fetchDomain();
    }, []);

    const {
        systemInfo,
        services,
        logs,
        sessions,
        teamViewerId,
        lastUpdated,
        loading,
        error,
        fetchData,
        loadFromCache,
    } = useHostData(ip);

    useEffect(() => {
        if (location.state?.host) {
            setCurrentHost(location.state.host);
        } else {
            // Fallback: fetch hosts and find the current one
            fetch(`${API_BASE}/hosts`)
                .then(res => res.json())
                .then(hosts => {
                    const found = hosts.find((h: Host) => h.address === ip);
                    if (found) setCurrentHost(found);
                })
                .catch(err => console.error('Failed to fetch host info:', err));
        }
    }, [ip, location.state]);

    // Load from cache on mount
    useEffect(() => {
        if (ip) {
            const hasData = loadFromCache();
            if (!hasData && activeTab === 'info') {
                setAuthContext('main');
                setIsAuthModalOpen(true);
            }
        }
    }, [ip, loadFromCache, activeTab]);

    const handleCopy = (text: string, type: 'ip' | 'hostname') => {
        navigator.clipboard.writeText(text);
        if (type === 'ip') {
            setCopiedIp(true);
            setTimeout(() => setCopiedIp(false), 2000);
            showToast('Endereço IP copiado!', 'success');
        } else {
            setCopiedHostname(true);
            setTimeout(() => setCopiedHostname(false), 2000);
            showToast('Nome do host copiado!', 'success');
        }
    };

    const handleRefresh = () => {
        if (credentials) {
            const tabsToFetch = activeTab === 'logs' ? ['logs'] : [activeTab, 'logs'];
            handleFetchData(credentials.username, credentials.password, false, tabsToFetch);
        } else {
            setAuthContext('main');
            setIsAuthModalOpen(true);
        }
    };

    const handleConfirmTrustedHosts = async () => {
        if (pendingAction) {
            setIsTrustedHostsModalOpen(false);
            await pendingAction();
            setPendingAction(null);
        }
    };

    const handleFetchData = async (user: string, pass: string, tempAuth: boolean = false, targetTab: string | string[] = activeTab) => {
        const effectiveTempAuth = tempAuth || (ip ? isTrustedSessionApproved(ip) : false);
        try {
            await fetchData(targetTab, user, pass, effectiveTempAuth);
        } catch (err: unknown) {
            if (err instanceof Error && err.message === "TRUSTED_HOSTS_REQUIRED") {
                setPendingAction(() => async () => handleFetchData(user, pass, true, targetTab));
                setIsTrustedHostsModalOpen(true);
            }
        }
    };

    useEffect(() => {
        if (credentials) {
            handleFetchData(credentials.username, credentials.password);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab, credentials]);

    const formatDate = (dateStr: string) => {
        if (!dateStr || dateStr === 'N/A') return 'N/A';
        try {
            const d = new Date(dateStr);
            return isNaN(d.getTime()) ? 'Data inválida' : d.toLocaleString('pt-BR');
        } catch {
            return 'Erro na data';
        }
    };

    const initiateServiceAction = (name: string, action: string, startupType?: string) => {
        if (!credentials) {
            setPendingServiceAction({ name, action, startupType });
            setAuthContext('service');
            setIsAuthModalOpen(true);
        } else {
            handleServiceAction(name, action, startupType);
        }
    };

    const handleServiceAction = async (serviceName: string, action: string, startupType?: string, authCreds?: { user: string, pass: string }, tempAuth: boolean = false) => {
        if (typeof startupType === 'object' && startupType !== null) {
            authCreds = startupType;
            startupType = undefined;
        }

        const user = authCreds ? authCreds.user : credentials?.username;
        const pass = authCreds ? authCreds.pass : credentials?.password;

        if (!user || !pass || !ip) return;

        const effectiveTempAuth = tempAuth || isTrustedSessionApproved(ip);
        const headers: HeadersInit = {
            'Content-Type': 'application/json'
        };
        if (effectiveTempAuth) {
            headers['X-Temp-Auth'] = 'true';
        }

        try {
            const body: any = {
                target_ip: ip,
                username: user,
                password: pass,
                service_name: serviceName,
                action: action
            };

            if (startupType) {
                body.startup_type = startupType;
            }

            const res = await fetch(`${API_BASE}/system/services/manage`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });

            if (res.ok) {
                const reader = res.body?.getReader();
                const decoder = new TextDecoder();

                if (reader) {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const chunk = decoder.decode(value);
                        const lines = chunk.split('\n');

                        for (const line of lines) {
                            if (!line.trim()) continue;
                            try {
                                const data = JSON.parse(line);
                                if (data.status === 'error') {
                                    if (data.code === "TRUSTED_HOSTS_REQUIRED") {
                                        setPendingAction(() => async () => handleServiceAction(serviceName, action, startupType, { user, pass }, true));
                                        setIsTrustedHostsModalOpen(true);
                                        return;
                                    }
                                    showToast(`Erro: ${data.message}`, 'error');
                                    return;
                                }
                            } catch (e) {
                                console.error('Error parsing service action response:', e);
                            }
                        }
                    }
                }

                handleFetchData(user, pass);
                showToast(`Serviço ${serviceName} ${action === 'start' ? 'iniciado' : action === 'stop' ? 'parado' : 'reiniciado'} com sucesso`, 'success');

                setTimeout(() => handleFetchData(user, pass), 5000);
            } else {
                const err = await res.json().catch(() => ({}));
                if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                    setPendingAction(() => async () => handleServiceAction(serviceName, action, startupType, { user, pass }, true));
                    setIsTrustedHostsModalOpen(true);
                    return;
                }
                showToast('Erro ao executar ação no serviço', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Erro ao executar ação no serviço', 'error');
        }
    };

    const [isSpoolerLoading, setIsSpoolerLoading] = useState(false);

    const handleSpoolerAction = async (action: string, authCreds?: { user: string, pass: string }, tempAuth: boolean = false) => {
        const user = authCreds ? authCreds.user : credentials?.username;
        const pass = authCreds ? authCreds.pass : credentials?.password;

        if (!user || !pass || !ip) {
            setAuthContext('main');
            setIsAuthModalOpen(true);
            return;
        }

        setIsSpoolerLoading(true);

        const effectiveTempAuth = tempAuth || isTrustedSessionApproved(ip);
        const headers: HeadersInit = {
            'Content-Type': 'application/json'
        };
        if (effectiveTempAuth) {
            headers['X-Temp-Auth'] = 'true';
        }

        try {
            const res = await fetch(`${API_BASE}/system/spooler/manage`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    target_ip: ip,
                    username: user,
                    password: pass,
                    action: action
                })
            });

            if (res.ok) {
                const reader = res.body?.getReader();
                const decoder = new TextDecoder();

                if (reader) {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const chunk = decoder.decode(value);
                        const lines = chunk.split('\n');

                        for (const line of lines) {
                            if (!line.trim()) continue;
                            try {
                                const data = JSON.parse(line);
                                if (data.status === 'error') {
                                    if (data.code === "TRUSTED_HOSTS_REQUIRED") {
                                        setPendingAction(() => async () => handleSpoolerAction(action, { user, pass }, true));
                                        setIsTrustedHostsModalOpen(true);
                                        setIsSpoolerLoading(false);
                                        return;
                                    }
                                    showToast(`Erro: ${data.message}`, 'error');
                                    setIsSpoolerLoading(false);
                                    return;
                                }
                            } catch (e) {
                                console.error('Error parsing spooler action response:', e);
                            }
                        }
                    }
                }

                showToast(`Ação de spooler (${action}) concluída com sucesso`, 'success');
                handleFetchData(user, pass);
            } else {
                const err = await res.json().catch(() => ({}));
                if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                    setPendingAction(() => async () => handleSpoolerAction(action, { user, pass }, true));
                    setIsTrustedHostsModalOpen(true);
                    setIsSpoolerLoading(false);
                    return;
                }
                showToast('Erro ao executar ação no spooler', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Erro ao executar ação no spooler', 'error');
        } finally {
            setIsSpoolerLoading(false);
        }
    };

    const handleExecutePowerAction = async (tempAuth = false) => {
        const user = credentials?.username;
        const pass = credentials?.password;

        if (!user || !pass) {
            setAuthContext('power');
            setIsAuthModalOpen(true);
            return;
        }

        setIsPowerExecuting(true);
        const effectiveTempAuth = tempAuth || (ip ? isTrustedSessionApproved(ip) : false);
        const headers: HeadersInit = { 'Content-Type': 'application/json' };
        if (effectiveTempAuth) headers['X-Temp-Auth'] = 'true';

        try {
            const body = {
                target_ip: ip,
                username: user,
                password: pass,
                action: powerAction,
                message: powerMessage || (powerAction === 'message' ? 'Aviso do Suporte de TI' : 'Manutenção Programada de TI'),
                timeout: powerDelay,
                force: true
            };

            const res = await fetch(`${API_BASE}/system/power`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });

            if (res.ok) {
                showToast(`Comando (${powerAction}) enviado com sucesso para ${ip}!`, 'success');
                setIsPowerModalOpen(false);
            } else {
                const errData = await res.json().catch(() => ({}));
                if (res.status === 403 && errData.detail === 'TRUSTED_HOSTS_REQUIRED') {
                    setPendingAction(() => async () => handleExecutePowerAction(true));
                    setIsTrustedHostsModalOpen(true);
                    return;
                }
                showToast(`Falha ao executar ação: ${errData.detail || res.statusText}`, 'error');
            }
        } catch (e: any) {
            showToast(`Erro na comunicação: ${e.message || e}`, 'error');
        } finally {
            setIsPowerExecuting(false);
        }
    };

    const handleDisconnectClick = (sessionId: string) => {
        const session = sessions.find(s => s.ID === sessionId);
        if (session) {
            setSessionToDisconnect(session);
            setIsDisconnectModalOpen(true);
        }
    };

    const confirmDisconnect = async (tempAuth: boolean = false) => {
        if (!sessionToDisconnect || !credentials || !ip) return;

        setIsDisconnecting(true);

        const effectiveTempAuth = tempAuth || isTrustedSessionApproved(ip);
        const headers: HeadersInit = {
            'Content-Type': 'application/json'
        };
        if (effectiveTempAuth) {
            headers['X-Temp-Auth'] = 'true';
        }

        try {
            const res = await fetch(`${API_BASE}/system/disconnect`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    target_ip: ip,
                    username: credentials.username,
                    password: credentials.password,
                    session_id: sessionToDisconnect.ID
                })
            });

            if (res.ok) {
                handleFetchData(credentials.username, credentials.password);
                setIsDisconnectModalOpen(false);
                setSessionToDisconnect(null);
                showToast('Usuário desconectado com sucesso', 'success');
            } else {
                const err = await res.json().catch(() => ({}));
                if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                    setPendingAction(() => async () => confirmDisconnect(true));
                    setIsTrustedHostsModalOpen(true);
                    setIsDisconnecting(false);
                    return;
                }
                showToast('Erro ao desconectar usuário', 'error');
            }
        } catch (e) {
            showToast('Erro ao desconectar usuário', 'error');
        } finally {
            setIsDisconnecting(false);
        }
    };

    const isHostOnline = currentHost?.stats?.online;
    const hostLatency = currentHost?.stats?.latency;

    return (
        <div className="space-y-6 h-full flex flex-col min-h-0 p-8">
            {/* Header com Informações do Host e Ações Rápidas */}
            <header className="flex flex-wrap items-center gap-4 justify-between">
                <div className="flex items-center gap-3.5">
                    <button
                        onClick={() => navigate('/')}
                        className="p-2 hover:bg-zinc-800 rounded-xl transition-colors text-zinc-400 hover:text-white border border-zinc-800"
                        title="Voltar ao Painel"
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <div>
                        <div className="flex items-center gap-2.5">
                            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                                {currentHost?.name || currentHost?.hostname || ip}
                            </h1>
                            <button
                                onClick={() => handleCopy(currentHost?.name || currentHost?.hostname || ip, 'hostname')}
                                className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-zinc-300 transition-colors"
                                title="Copiar Nome"
                            >
                                {copiedHostname ? <Check size={15} className="text-emerald-400" /> : <Copy size={15} />}
                            </button>

                            {/* Badge Online/Offline */}
                            {isHostOnline !== undefined && (
                                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                                    isHostOnline
                                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                        : 'bg-red-500/15 text-red-400 border border-red-500/30'
                                }`}>
                                    <span className={`w-1.5 h-1.5 rounded-full ${isHostOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                                    {isHostOnline
                                        ? `Online${hostLatency ? ` • ${Math.round(hostLatency)}ms` : ''}`
                                        : 'Offline'}
                                </span>
                            )}
                        </div>

                        <div className="flex items-center gap-2 text-zinc-400 text-xs mt-0.5 font-mono">
                            <span>{currentHost?.ip || (/\d+\.\d+\.\d+\.\d+/.test(ip || '') ? ip : 'Resolvendo...')}</span>
                            <button
                                onClick={() => handleCopy(ip || '', 'ip')}
                                className="p-0.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-zinc-300 transition-colors"
                                title="Copiar IP"
                            >
                                {copiedIp ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                            </button>
                            {lastUpdated && (
                                <span className="text-zinc-500 ml-2 font-sans">
                                    • Atualizado às {lastUpdated.toLocaleTimeString('pt-BR')}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Toolbar de Ações Rápidas */}
                <div className="flex items-center gap-2.5 ml-auto">
                    {/* Botão Acesso Remoto */}
                    <button
                        onClick={() => setIsRemoteModalOpen(true)}
                        className="px-3 py-2 bg-blue-600/15 hover:bg-blue-600/25 text-blue-400 hover:text-blue-300 rounded-xl border border-blue-500/30 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
                        title="Conectar via RDP, MSRA ou TeamViewer"
                    >
                        <Monitor size={15} />
                        <span>Acesso Remoto</span>
                    </button>

                    {/* Botão Energia & Mensagem */}
                    <button
                        onClick={() => setIsPowerModalOpen(true)}
                        className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white rounded-xl border border-zinc-700 text-xs font-semibold flex items-center gap-1.5 transition-all"
                        title="Reiniciar, Desligar ou Enviar Mensagem remota"
                    >
                        <Power size={15} className="text-orange-400" />
                        <span>Energia & Msg</span>
                    </button>

                    {/* Teste WinRM */}
                    <button
                        onClick={() => {
                            setAuthContext('test');
                            setIsAuthModalOpen(true);
                        }}
                        className="p-2 hover:bg-zinc-800 rounded-xl transition-colors text-zinc-400 hover:text-white border border-zinc-800"
                        title="Testar Conexão WinRM / PowerShell"
                    >
                        <Terminal size={18} />
                    </button>

                    {/* Atualizar */}
                    <button
                        onClick={handleRefresh}
                        className="p-2 hover:bg-zinc-800 rounded-xl transition-colors text-zinc-400 hover:text-white border border-zinc-800"
                        title="Atualizar dados do host"
                    >
                        <RefreshCw size={18} className={loading ? "animate-spin text-blue-400" : ""} />
                    </button>

                    {/* Ajuda Geral */}
                    <HelpButton
                        title="Painel Avançado do Host"
                        description={
                            <div className="space-y-3">
                                <p>
                                    Este módulo oferece diagnóstico e gestão técnica centralizada do computador através dos protocolos WinRM (Windows Remote Management) e WMI.
                                </p>
                                <p>
                                    <strong>Acesso Remoto:</strong> Permite disparar clientes RDP (Área de Trabalho Remota), MSRA (Assistência Remota) ou TeamViewer sem sair da tela.
                                </p>
                                <p>
                                    <strong>Energia & Mensagem:</strong> Envia alertas na área de trabalho dos usuários conectados e programa reinícios ou desligamentos controlados.
                                </p>
                                <p>
                                    <strong>Independência do Histórico:</strong> A aba <em>Histórico</em> é alimentada pelo monitor contínuo e funciona mesmo sem nenhuma senha ou privilégio administrativo.
                                </p>
                            </div>
                        }
                    />
                </div>
            </header>

            {/* Abas de Navegação com Ajuda Integrada */}
            <div className="flex gap-2 border-b border-zinc-800 overflow-x-auto">
                {[
                    {
                        id: 'info',
                        label: 'Informações',
                        help: 'Exibe o inventário detalhado de hardware, processador, discos com alerta visual de espaço livre, usuário ativo no momento e identificação remota (TeamViewer). Requer autenticação WinRM.'
                    },
                    {
                        id: 'history',
                        label: 'Histórico',
                        help: 'Histórico contínuo de latência (ms) e disponibilidade (uptime) gravado minuto a minuto pelo monitor de rede (24h e 7 dias). Totalmente independente de autenticação WinRM.'
                    },
                    {
                        id: 'services',
                        label: 'Serviços',
                        help: 'Gerenciador de serviços do Windows em tempo real. Permite iniciar, parar ou reiniciar serviços remotos e alterar o tipo de inicialização (Automático, Manual, Desabilitado) via WinRM.'
                    },
                    {
                        id: 'print',
                        label: 'Impressão',
                        help: 'Diagnóstico e recuperação do serviço Spooler de Impressão. Exibe o status ao vivo do serviço, reinicia suavemente ou limpa arquivos presos na pasta spool/PRINTERS com um clique.'
                    },
                    {
                        id: 'logs',
                        label: 'Logs de Eventos',
                        help: 'Visualizador de Eventos do Windows (Event Viewer - Application e System). Filtre instantaneamente por nível de severidade (Erros, Avisos e Informações).'
                    },
                    {
                        id: 'sessions',
                        label: 'Sessões',
                        help: 'Lista os usuários conectados atualmente, identificando se estão no terminal físico (Console) ou em sessão remota (RDP), permitindo desconexão assistida.'
                    }
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-4 py-2.5 text-sm font-medium transition-colors relative whitespace-nowrap ${
                            activeTab === tab.id ? 'text-blue-400' : 'text-zinc-400 hover:text-white'
                        }`}
                    >
                        <div className="flex items-center gap-2">
                            <span>{tab.label}</span>
                            <HelpButton title={tab.label} description={tab.help} />
                        </div>
                        {activeTab === tab.id && (
                            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500" />
                        )}
                    </button>
                ))}
            </div>

            {/* Conteúdo da Aba Selecionada */}
            <div className="flex-1 min-h-0 overflow-y-auto pr-2 custom-scrollbar">
                {activeTab === 'history' ? (
                    <HostHistoryTab address={ip || ''} />
                ) : loading && !systemInfo && !services.length && !logs.length && !sessions.length ? (
                    <div className="flex flex-col items-center justify-center h-64 text-zinc-500 gap-3">
                        <RefreshCw className="animate-spin text-blue-500" size={28} />
                        <span className="text-sm">Consultando host remoto via WinRM...</span>
                    </div>
                ) : error ? (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-6 text-red-400 space-y-3">
                        <div className="flex items-center gap-2 font-bold text-base">
                            <AlertCircle size={20} className="text-red-400" />
                            <span>Falha na Conexão com o Host</span>
                        </div>
                        <div className="text-sm opacity-90 leading-relaxed space-y-2">
                            {error.includes(' • ') ? (
                                <>
                                    <p className="font-medium text-red-300">{error.split(' • ')[0]}</p>
                                    <div className="text-xs bg-red-950/40 rounded-xl p-3 border border-red-900/30 space-y-1 font-mono text-red-200/90">
                                        <div className="font-semibold text-red-300 font-sans mb-1">Diagnóstico técnico das tentativas:</div>
                                        {error.split(' • ').slice(1).map((detail, idx) => (
                                            <div key={idx} className="flex items-start gap-1.5">
                                                <span className="text-red-400">•</span>
                                                <span>{detail}</span>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <p>{error}</p>
                            )}
                        </div>
                        <div className="pt-2 flex items-center gap-3">
                            <button
                                onClick={() => {
                                    setAuthContext('main');
                                    setIsAuthModalOpen(true);
                                }}
                                className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-xl text-xs font-semibold transition-colors border border-red-500/30"
                            >
                                Informar Novas Credenciais
                            </button>
                            {activeTab !== 'history' && (
                                <button
                                    onClick={() => setActiveTab('history')}
                                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors border border-zinc-700"
                                >
                                    Ver Histórico (Sem Senha)
                                </button>
                            )}
                        </div>
                    </div>
                ) : !credentials && !systemInfo && services.length === 0 ? (
                    /* Banner Não-Bloqueante de Autenticação */
                    <div className="p-8 text-center bg-zinc-800/30 rounded-2xl border border-zinc-700/50 max-w-lg mx-auto my-12 space-y-4 shadow-xl">
                        <div className="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto border border-blue-500/20">
                            <Lock size={22} />
                        </div>
                        <div className="space-y-1">
                            <h3 className="text-base font-bold text-white">Autenticação Administrativa Necessária</h3>
                            <p className="text-xs text-zinc-400 leading-relaxed">
                                As informações de hardware, discos, serviços e eventos deste host são consultadas remotamente via WinRM/WMI e exigem credenciais com privilégios de administrador.
                            </p>
                        </div>
                        <button
                            onClick={() => {
                                setAuthContext('main');
                                setIsAuthModalOpen(true);
                            }}
                            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-900/30 transition-all hover:-translate-y-0.5"
                        >
                            Conectar com Credenciais
                        </button>
                    </div>
                ) : (
                    <>
                        {activeTab === 'info' && (
                            <HostInfoTab
                                systemInfo={systemInfo}
                                teamViewerId={teamViewerId || currentHost?.teamviewer_id || null}
                                formatDate={formatDate}
                            />
                        )}
                        {activeTab === 'services' && (
                            <ServicesTab
                                services={services}
                                handleServiceAction={(name, action, startupType) => initiateServiceAction(name, action, startupType)}
                            />
                        )}
                        {activeTab === 'print' && (
                            <PrintServiceTab
                                handleSpoolerAction={handleSpoolerAction}
                                isLoading={isSpoolerLoading}
                                spoolerService={services.find((s: any) => (s.Name || '').toLowerCase() === 'spooler')}
                            />
                        )}
                        {activeTab === 'logs' && (
                            <LogsTab
                                logs={logs}
                                formatDate={formatDate}
                            />
                        )}
                        {activeTab === 'sessions' && (
                            <SessionsTab
                                sessions={sessions}
                                handleDisconnect={handleDisconnectClick}
                                formatDate={formatDate}
                            />
                        )}
                    </>
                )}
            </div>

            {/* Modal de Autenticação */}
            <CredentialModal
                isOpen={isAuthModalOpen}
                onClose={() => setIsAuthModalOpen(false)}
                title={
                    authContext === 'test' ? "Autenticação para Teste WinRM" :
                    authContext === 'service' ? "Autenticação para Serviço" :
                    authContext === 'power' ? "Autenticação para Ação de Energia" :
                    "Autenticação Necessária"
                }
                initialDomain={currentHost?.domain || localDomain || ''}
                onConfirm={(username, password) => {
                    if (authContext === 'test') {
                        setTestCredentials({ username, password });
                        setIsAuthModalOpen(false);
                        setIsTestConnectionModalOpen(true);
                    } else if (authContext === 'service' && pendingServiceAction) {
                        handleServiceAction(pendingServiceAction.name, pendingServiceAction.action, pendingServiceAction.startupType, { user: username, pass: password });
                        setIsAuthModalOpen(false);
                        setPendingServiceAction(null);
                    } else if (authContext === 'power') {
                        setCredentials({ username, password });
                        setIsAuthModalOpen(false);
                        handleExecutePowerAction();
                    } else {
                        setCredentials({ username, password });
                        setIsAuthModalOpen(false);
                        handleFetchData(username, password, false, ['info', 'services', 'logs', 'sessions']);
                    }
                }}
            />

            {/* Modal de Desconexão de Usuário */}
            <DisconnectUserModal
                isOpen={isDisconnectModalOpen}
                onClose={() => setIsDisconnectModalOpen(false)}
                onConfirm={() => confirmDisconnect()}
                username={sessionToDisconnect?.UserName || ''}
                sessionName={sessionToDisconnect?.SessionName || ''}
                isLoading={isDisconnecting}
            />

            {/* Modal de TrustedHosts */}
            <TrustedHostsModal
                isOpen={isTrustedHostsModalOpen}
                onClose={() => setIsTrustedHostsModalOpen(false)}
                onConfirm={handleConfirmTrustedHosts}
                targetIp={ip}
            />

            {/* Modal de Teste de Conexão */}
            <TestConnectionModal
                isOpen={isTestConnectionModalOpen}
                onClose={() => setIsTestConnectionModalOpen(false)}
                ip={ip || ''}
                credentials={testCredentials}
            />

            {/* Modal de Acesso Remoto */}
            {isRemoteModalOpen && (
                <RemoteAccessModal
                    isOpen={isRemoteModalOpen}
                    onClose={() => setIsRemoteModalOpen(false)}
                    host={currentHost || ({ address: ip || '', name: currentHost?.name || ip } as any)}
                />
            )}

            {/* Modal de Ações de Energia & Mensagem */}
            {isPowerModalOpen && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150"
                    onClick={() => setIsPowerModalOpen(false)}
                >
                    <div
                        className="bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-5 animate-in zoom-in-95 duration-150"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                            <h3 className="text-base font-bold text-white flex items-center gap-2">
                                <Power size={18} className="text-orange-400" />
                                Ações de Energia & Mensagem
                            </h3>
                            <button
                                onClick={() => setIsPowerModalOpen(false)}
                                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5">
                                    Ação Desejada
                                </label>
                                <div className="grid grid-cols-3 gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setPowerAction('restart')}
                                        className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all flex flex-col items-center gap-1.5 ${
                                            powerAction === 'restart'
                                                ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                                                : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:text-white'
                                        }`}
                                    >
                                        <RefreshCw size={16} />
                                        Reiniciar
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setPowerAction('shutdown')}
                                        className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all flex flex-col items-center gap-1.5 ${
                                            powerAction === 'shutdown'
                                                ? 'bg-red-500/20 text-red-400 border-red-500/40'
                                                : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:text-white'
                                        }`}
                                    >
                                        <Power size={16} />
                                        Desligar
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setPowerAction('message')}
                                        className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all flex flex-col items-center gap-1.5 ${
                                            powerAction === 'message'
                                                ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
                                                : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:text-white'
                                        }`}
                                    >
                                        <MessageSquare size={16} />
                                        Mensagem
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5">
                                    Mensagem para o Usuário Remoto
                                </label>
                                <input
                                    type="text"
                                    value={powerMessage}
                                    onChange={(e) => setPowerMessage(e.target.value)}
                                    placeholder="Ex: Manutenção de TI programada..."
                                    className="w-full bg-zinc-950 border border-zinc-700/80 rounded-xl px-3.5 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                                />
                            </div>

                            {powerAction !== 'message' && (
                                <div>
                                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5">
                                        Tempo de Espera (Delay em segundos)
                                    </label>
                                    <input
                                        type="number"
                                        min="0"
                                        value={powerDelay}
                                        onChange={(e) => setPowerDelay(Math.max(0, parseInt(e.target.value) || 0))}
                                        className="w-full bg-zinc-950 border border-zinc-700/80 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
                                    />
                                    <p className="text-[11px] text-zinc-500 mt-1">
                                        Contagem regressiva que o Windows exibirá antes de reiniciar ou desligar.
                                    </p>
                                </div>
                            )}

                            <div className="pt-2 flex gap-3">
                                <button
                                    type="button"
                                    onClick={() => setIsPowerModalOpen(false)}
                                    className="flex-1 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleExecutePowerAction()}
                                    disabled={isPowerExecuting}
                                    className={`flex-1 py-2.5 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                                        powerAction === 'shutdown' ? 'bg-red-600 hover:bg-red-500 text-white' :
                                        powerAction === 'restart' ? 'bg-amber-600 hover:bg-amber-500 text-white' :
                                        'bg-blue-600 hover:bg-blue-500 text-white'
                                    }`}
                                >
                                    {isPowerExecuting ? <RefreshCw size={14} className="animate-spin" /> : null}
                                    Confirmar {powerAction === 'message' ? 'Envio' : 'Execução'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
