import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Copy, Check, Terminal } from 'lucide-react';
import { HostInfoTab } from '../components/HostDetails/HostInfoTab';
import { ServicesTab } from '../components/HostDetails/ServicesTab';
import { PrintServiceTab } from '../components/HostDetails/PrintServiceTab';
import { LogsTab } from '../components/HostDetails/LogsTab';
import { SessionsTab } from '../components/HostDetails/SessionsTab';
import { CredentialModal } from '../components/CredentialModal';
import { DisconnectUserModal } from '../components/HostDetails/DisconnectUserModal';
import TrustedHostsModal from '../components/TrustedHostsModal';
import { TestConnectionModal } from '../components/HostDetails/TestConnectionModal';
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
    const [authContext, setAuthContext] = useState<'main' | 'test' | 'service'>('main');
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
    const [isTestConnectionModalOpen, setIsTestConnectionModalOpen] = useState(false);
    const [pendingServiceAction, setPendingServiceAction] = useState<{ name: string, action: string, startupType?: string } | null>(null);

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
            if (!hasData) {
                setAuthContext('main');
                setIsAuthModalOpen(true);
            }
        }
    }, [ip, loadFromCache]);

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
        // Auto-elevate when this host was already approved earlier in the same
        // app session (operator ticked "remember for this session" in the modal).
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

    // Re-fetch whenever the tab or credentials change. `credentials` is set
    // once after the CredentialModal closes and doesn't churn between fetches,
    // so adding it to the deps doesn't trigger spurious requests — it just
    // closes the stale-closure window where switching tabs after a credential
    // update would have refetched with old creds.
    useEffect(() => {
        if (credentials) {
            handleFetchData(credentials.username, credentials.password);
        }
        // handleFetchData isn't memoized but closes only over stable router
        // params and setters, so leaving it out of deps is intentional.
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
        setPendingServiceAction({ name, action, startupType });
        setAuthContext('service');
        setIsAuthModalOpen(true);
    };

    const handleServiceAction = async (serviceName: string, action: string, startupType?: string, authCreds?: { user: string, pass: string }, tempAuth: boolean = false) => {
        // Handle overload where authCreds is passed as 3rd arg (legacy calls)
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

                // Auto-refresh after 5 and 10 seconds
                setTimeout(() => handleFetchData(user, pass), 5000);
                setTimeout(() => handleFetchData(user, pass), 10000);
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

        if (!user || !pass || !ip) return;

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

    return (
        <div className="space-y-6 h-full flex flex-col min-h-0 p-8">
            <header className="flex items-center gap-4">
                <button onClick={() => navigate('/')} className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white">
                    <ArrowLeft size={20} />
                </button>
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        {currentHost?.name || currentHost?.hostname || ip}
                        <button
                            onClick={() => handleCopy(currentHost?.name || currentHost?.hostname || ip, 'hostname')}
                            className="p-1.5 hover:bg-zinc-800 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors"
                            title="Copiar Nome"
                        >
                            {copiedHostname ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
                        </button>
                    </h1>
                    <div className="flex items-center gap-2 text-zinc-400">
                        <span>{currentHost?.ip || (/\d+\.\d+\.\d+\.\d+/.test(ip || '') ? ip : 'Resolvendo...')}</span>
                        <button
                            onClick={() => handleCopy(ip || '', 'ip')}
                            className="p-1 hover:bg-zinc-800 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors"
                            title="Copiar IP"
                        >
                            {copiedIp ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                        </button>
                    </div>
                </div>
                <div className="ml-auto flex items-center gap-4">
                    {lastUpdated && (
                        <span className="text-xs text-zinc-500">
                            Atualizado: {lastUpdated.toLocaleString()}
                        </span>
                    )}
                    <button
                        onClick={() => {
                            setAuthContext('test');
                            setIsAuthModalOpen(true);
                        }}
                        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white"
                        title="Testar Conexão WinRM"
                    >
                        <Terminal size={20} />
                    </button>
                    <button
                        onClick={handleRefresh}
                        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white"
                        title="Atualizar dados"
                    >
                        <RefreshCw size={20} className={loading ? "animate-spin" : ""} />
                    </button>
                    <HelpButton title="Detalhes do Host" description="Aqui você pode ver informações detalhadas, gerenciar serviços, ver logs de eventos e sessões de usuários ativos." />
                </div>
            </header>

            <div className="flex gap-2 border-b border-zinc-800">
                {[
                    { id: 'info', label: 'Informações', help: 'Exibe detalhes gerais do hardware e sistema operacional do host.' },
                    { id: 'services', label: 'Serviços', help: 'Gerencie serviços do Windows (Iniciar, Parar, Reiniciar). Requer privilégios administrativos.' },
                    { id: 'print', label: 'Impressão', help: 'Controle o Spooler de Impressão e visualize impressoras instaladas.' },
                    { id: 'logs', label: 'Logs de Eventos', help: 'Visualize os últimos eventos do sistema (Event Viewer) para diagnóstico.' },
                    { id: 'sessions', label: 'Sessões', help: 'Veja usuários conectados atualmente e gerencie suas sessões (Desconectar).' }
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-4 py-2 text-sm font-medium transition-colors relative ${activeTab === tab.id ? 'text-blue-400' : 'text-zinc-400 hover:text-white'
                            }`}
                    >
                        <div className="flex items-center gap-2">
                            {tab.label}
                            <HelpButton title={tab.label} description={tab.help} />
                        </div>
                        {activeTab === tab.id && (
                            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400" />
                        )}
                    </button>
                ))}
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto pr-2 custom-scrollbar">
                {loading && !systemInfo && !services.length && !logs.length && !sessions.length ? (
                    <div className="flex items-center justify-center h-full text-zinc-500">
                        <RefreshCw className="animate-spin mr-2" /> Carregando...
                    </div>
                ) : error ? (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-red-400">
                        {error}
                    </div>
                ) : (
                    <>
                        {activeTab === 'info' && (
                            <HostInfoTab
                                systemInfo={systemInfo}
                                teamViewerId={teamViewerId}
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

            <CredentialModal
                isOpen={isAuthModalOpen}
                onClose={() => setIsAuthModalOpen(false)}
                title={authContext === 'test' ? "Autenticação para Teste" : authContext === 'service' ? "Autenticação para Serviço" : "Autenticação Necessária"}
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
                    } else {
                        setCredentials({ username, password });
                        setIsAuthModalOpen(false);
                        handleFetchData(username, password, false, ['info', 'services', 'logs', 'sessions']);
                    }
                }}
            />

            <DisconnectUserModal
                isOpen={isDisconnectModalOpen}
                onClose={() => setIsDisconnectModalOpen(false)}
                onConfirm={() => confirmDisconnect()}
                username={sessionToDisconnect?.UserName || ''}
                sessionName={sessionToDisconnect?.SessionName || ''}
                isLoading={isDisconnecting}
            />

            <TrustedHostsModal
                isOpen={isTrustedHostsModalOpen}
                onClose={() => setIsTrustedHostsModalOpen(false)}
                onConfirm={handleConfirmTrustedHosts}
                targetIp={ip}
            />

            <TestConnectionModal
                isOpen={isTestConnectionModalOpen}
                onClose={() => setIsTestConnectionModalOpen(false)}
                ip={ip || ''}
                credentials={testCredentials}
            />
        </div >
    );
};
