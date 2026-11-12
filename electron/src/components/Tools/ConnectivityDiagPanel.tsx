import { useState, useEffect, useRef, useMemo } from 'react';
import {
    Wifi,
    WifiOff,
    Cable,
    ShieldCheck,
    Play,
    Square,
    Copy,
    RotateCcw,
    Search,
    FileText,
    Award,
    CheckCircle2,
    AlertTriangle,
    XCircle,
    Server,
    Lock,
    KeyRound,
    X,
    Eye,
    ChevronDown,
    ChevronUp,
    Laptop
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { useVault } from '../../contexts/VaultContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

export type TileState = 'Green' | 'Blue' | 'Amber' | 'Red' | 'Neutral';

export interface DiagTile {
    title: string;
    main: string;
    sub: string;
    state: TileState;
}

export interface LanAdapterInfo {
    Name: string;
    Description: string;
    Status: string;
    MAC: string;
    SpeedMbps: number;
    SpeedText: string;
    IPv4: string;
    Gateway: string;
    GwStatus: string;
    DNS: string;
}

export interface WifiProfile8021xDetail {
    ProfileName: string;
    AuthMode: string;
    EapType: string;
    EapTypeName: string;
    InnerEapType: string;
    InnerEapTypeName: string;
    ValidateServer: boolean;
    ServerNames: string;
    DisableUserPrompt: boolean;
    FastReconnect: boolean;
    UseWinLogon: boolean;
    TrustedRootCount: number;
    TrustedRootThumbs: string[];
}

export interface Cert8021xInfo {
    Subject: string;
    Issuer: string;
    Thumbprint: string;
    NotBefore?: string;
    NotAfter: string;
    DaysLeft: number;
    HasPrivateKey: boolean;
    Template: string;
    FriendlyName?: string;
    Store: string;
    SerialNumber?: string;
    IsEapTrustedRoot?: boolean;
    EapProfileName?: string;
    EapConfigSummary?: string;
    EapAuthMode?: string;
    EapFastReconnect?: boolean;
    EapDisablePrompt?: boolean;
    EapServerNames?: string;
    IsMissingFromStore?: boolean;
}

export interface HostDiagResult {
    host_input: string;
    stage: 'Initial' | 'PingStage' | 'Final';
    mode: string;
    timestamp: string;
    dns_ok: boolean;
    ip_resolved: string;
    fqdn_resolved: string;
    ping_ok: boolean;
    ping_ms: number | null;
    ping_ttl: number | null;
    winrm_ok: boolean;
    winrm_error: string;
    winrm_detail: string;
    hostname: string;
    domain: string;
    os_caption: string;
    lan_connected: boolean;
    lan_adapters: LanAdapterInfo[];
    wifi_present: boolean;
    wifi_connected: boolean;
    wifi_state: string;
    wifi_ssid: string;
    wifi_bssid: string;
    wifi_signal: string;
    wifi_signal_num: number;
    wifi_radio: string;
    wifi_channel: string;
    wifi_auth: string;
    wifi_cipher: string;
    wifi_ip: string;
    wifi_desc: string;
    wifi_profiles_8021x: string[];
    wifi_profiles_8021x_detail?: WifiProfile8021xDetail[];
    wifi_all_profiles: string[];
    certs_8021x: Cert8021xInfo[];
    cert_status: 'OK' | 'Expiring' | 'Problem' | 'Missing' | 'Unknown';
    cert_summary: string;
    overall_badge: string;
    overall_state: TileState;
    synthesis: string;
    tiles: {
        tile1: DiagTile;
        tile2: DiagTile;
        tile3: DiagTile;
        tile4: DiagTile;
        tile5: DiagTile;
        tile6: DiagTile;
    };
    raw_report?: string;
}

function createInitialHostItem(hostInput: string): HostDiagResult {
    const nowStr = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    return {
        host_input: hostInput,
        stage: 'Initial',
        mode: 'Full',
        timestamp: nowStr,
        dns_ok: false,
        ip_resolved: '',
        fqdn_resolved: hostInput,
        ping_ok: false,
        ping_ms: null,
        ping_ttl: null,
        winrm_ok: false,
        winrm_error: '',
        winrm_detail: '',
        hostname: hostInput,
        domain: '',
        os_caption: '',
        lan_connected: false,
        lan_adapters: [],
        wifi_present: false,
        wifi_connected: false,
        wifi_state: 'Aguardando',
        wifi_ssid: '',
        wifi_bssid: '',
        wifi_signal: '',
        wifi_signal_num: 0,
        wifi_radio: '',
        wifi_channel: '',
        wifi_auth: '',
        wifi_cipher: '',
        wifi_ip: '',
        wifi_desc: '',
        wifi_profiles_8021x: [],
        wifi_profiles_8021x_detail: [],
        wifi_all_profiles: [],
        certs_8021x: [],
        cert_status: 'Unknown',
        cert_summary: '',
        overall_badge: 'SONDANDO...',
        overall_state: 'Blue',
        synthesis: 'Verificando resolução e conectividade remota via WinRM...',
        tiles: {
            tile1: { title: 'RESOLUÇÃO DNS & IP', main: 'Consultando...', sub: 'Resolvendo nome/IP', state: 'Neutral' },
            tile2: { title: 'ALCANCE (PING ICMP)', main: 'Verificando...', sub: 'Pré-checagem de rede', state: 'Neutral' },
            tile3: { title: 'GERÊNCIA (WINRM)', main: 'Na fila...', sub: 'Aguardando sessão', state: 'Neutral' },
            tile4: { title: 'ENLACE CABEADO (LAN)', main: 'Aguardando...', sub: 'Placas Ethernet físicas', state: 'Neutral' },
            tile5: { title: 'ENLACE WI-FI (WLAN)', main: 'Aguardando...', sub: 'Estado SSID / Sinal', state: 'Neutral' },
            tile6: { title: 'CONTROLE 802.1X', main: 'Aguardando...', sub: 'Certificados LocalMachine', state: 'Neutral' },
        },
        raw_report: ''
    };
}

function parseTargetListClient(raw: string): string[] {
    const parts = raw.split(/[,;\r\n\s]+/);
    const seen = new Set<string>();
    const out: string[] = [];
    for (const p of parts) {
        const v = p.trim();
        if (!v) continue;
        const key = v.toUpperCase();
        if (!seen.has(key)) {
            seen.add(key);
            const isIp = /^(?:\d{1,3}\.){3}\d{1,3}$/.test(v);
            out.push(isIp ? v : key);
        }
    }
    return out;
}

const BADGE_STYLES: Record<TileState, string> = {
    Green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
    Blue: 'bg-blue-500/15 text-blue-300 border-blue-500/40',
    Amber: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
    Red: 'bg-red-500/15 text-red-300 border-red-500/40',
    Neutral: 'bg-zinc-800 text-zinc-300 border-zinc-700'
};

const DOT_STYLES: Record<TileState, string> = {
    Green: 'bg-emerald-400 shadow-emerald-400/50',
    Blue: 'bg-blue-400 shadow-blue-400/50',
    Amber: 'bg-amber-400 shadow-amber-400/50',
    Red: 'bg-red-400 shadow-red-400/50',
    Neutral: 'bg-zinc-500'
};

type FilterKey = 'ALL' | 'WIFI' | 'LAN' | 'HYBRID' | 'ALERTS';

export function ConnectivityDiagPanel() {
    const { showToast } = useToast();

    // Persistência obrigatória (parâmetros + último resultado + timestamp)
    const [targetsInput, setTargetsInput] = usePersistedState<string>('wifi_diag_targets_v2', '');
    const [credMode, setCredMode] = usePersistedState<string>('wifi_diag_cred_mode_v3', 'manual');
    const [manualUsername, setManualUsername] = usePersistedState<string>('wifi_diag_manual_user_v2', '');
    const [manualPassword, setManualPassword] = useState<string>('');
    const [results, setResults, clearResultsState] = usePersistedState<HostDiagResult[]>('wifi_diag_results_v2', []);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('wifi_diag_last_run_v2', null);
    const [lastTargetsSummary, setLastTargetsSummary] = usePersistedState<string | null>('wifi_diag_last_targets_v2', null);
    const [viewFilter, setViewFilter] = usePersistedState<FilterKey>('wifi_diag_view_filter_v2', 'ALL');

    // Estado de execução e UI
    const [isRunning, setIsRunning] = useState<boolean>(false);
    const [progressText, setProgressText] = useState<string>('Pronto para auditar');
    const [searchQuery, setSearchQuery] = useState<string>('');
    const { isUnlocked: vaultUnlocked, vaultCredentials, isLoading: vaultLoading } = useVault();
    const hasVaultCreds = vaultUnlocked && vaultCredentials.length > 0;

    // Modais focados (apenas o host selecionado ou auditoria 802.1x)
    const [selectedHostModal, setSelectedHostModal] = useState<HostDiagResult | null>(null);
    const [showRawLogInModal, setShowRawLogInModal] = useState<boolean>(false);
    const [showCertsModal, setShowCertsModal] = useState<boolean>(false);
    const [certModalHostFilter, setCertModalHostFilter] = useState<string>('ALL');
    const [selectedCertDetail, setSelectedCertDetail] = useState<{
        cert: Cert8021xInfo;
        hostInput: string;
        ip?: string;
        domain?: string;
    } | null>(null);

    const copyCertFullText = (c: Cert8021xInfo, hostInput?: string) => {
        const lines = [
            `=== AUDITORIA DE CERTIFICADO 802.1X ===`,
            hostInput ? `Host Alvo: ${hostInput}` : '',
            `Repositório: ${c.Store}`,
            `Titular (Subject): ${c.Subject}`,
            `Emissor (Issuer): ${c.Issuer}`,
            c.NotBefore
                ? `Vigência: ${c.NotBefore} até ${c.NotAfter} (${c.DaysLeft} dias restantes)`
                : `Validade: até ${c.NotAfter} (${c.DaysLeft} dias restantes)`,
            `Status: ${c.IsMissingFromStore ? 'NÃO INSTALADA NO COMPUTADOR!' : c.DaysLeft <= 0 ? 'Expirado' : c.DaysLeft <= 30 ? 'Expirando' : 'Válido'}`,
            c.IsEapTrustedRoot ? `★ Marcada na Política 802.1X: Sim (Perfil ${c.EapProfileName} • ${c.EapConfigSummary || ''})` : '',
            c.EapAuthMode ? `Modo 802.1X: ${c.EapAuthMode === 'machine' ? 'Credencial da Máquina (Computador)' : c.EapAuthMode}` : '',
            c.EapFastReconnect !== undefined ? `Reconexão Rápida: ${c.EapFastReconnect ? 'Ativada (Sim)' : 'Não'}` : '',
            `Chave Privada: ${c.HasPrivateKey ? 'Sim (Presente)' : c.Store === 'LocalMachine\\My' ? 'Ausente!' : 'N/A (Autoridade Certificadora)'}`,
            c.Template ? `Template: ${c.Template}` : '',
            c.FriendlyName ? `Nome Amigável: ${c.FriendlyName}` : '',
            c.SerialNumber ? `Número de Série: ${c.SerialNumber}` : '',
            `Thumbprint (SHA1): ${c.Thumbprint}`
        ].filter(Boolean);
        navigator.clipboard.writeText(lines.join('\n'));
        showToast('Dados completos do certificado copiados!', 'success');
    };

    const abortControllerRef = useRef<AbortController | null>(null);

    // Verifica automaticamente se existe credencial disponível no Cofre;
    // caso contrário, seleciona automaticamente o preenchimento manual.
    useEffect(() => {
        if (vaultLoading) return;
        if (!hasVaultCreds) {
            if (credMode !== 'manual') {
                setCredMode('manual');
            }
        } else {
            if (credMode === 'manual' && !manualUsername.trim()) {
                setCredMode('auto');
            } else if (
                credMode !== 'manual' &&
                credMode !== 'auto' &&
                !vaultCredentials.some(c => c.id === credMode)
            ) {
                setCredMode('auto');
            }
        }
    }, [vaultLoading, hasVaultCreds, vaultCredentials]);

    // Mantém o modal aberto sincronizado se o streaming atualizar o host selecionado
    useEffect(() => {
        if (selectedHostModal) {
            const updated = results.find(r => r.host_input === selectedHostModal.host_input);
            if (updated) setSelectedHostModal(updated);
        }
    }, [results]);

    const stopDiagnostic = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsRunning(false);
        setProgressText('Auditoria interrompida pelo operador.');
        showToast('Execução interrompida.', 'warning');
    };

    const handleClear = () => {
        if (isRunning) stopDiagnostic();
        clearResultsState();
        setLastRunAt(null);
        setLastTargetsSummary(null);
        setViewFilter('ALL');
        setSearchQuery('');
        setProgressText('Resultados limpos.');
    };

    const runDiagnostic = async () => {
        const parsedTargets = parseTargetListClient(targetsInput);
        if (parsedTargets.length === 0) {
            showToast('Informe ao menos um Hostname ou IP (ex: host01.example.com, 1.1.1.1).', 'warning');
            return;
        }

        const useManual = !hasVaultCreds || credMode === 'manual';
        if (useManual && (!manualUsername.trim() || !manualPassword)) {
            showToast('Informe o usuário e senha administrativos para auditar os hosts.', 'warning');
            return;
        }

        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        const controller = new AbortController();
        abortControllerRef.current = controller;

        setIsRunning(true);
        setResults(parsedTargets.map(t => createInitialHostItem(t)));
        setLastRunAt(new Date().toISOString());
        setLastTargetsSummary(`${parsedTargets.length} host(s)`);
        setProgressText(`Auditando ${parsedTargets.length} host(s)...`);

        try {
            const payload: Record<string, any> = { targets: parsedTargets };
            if (useManual) {
                payload.username = manualUsername.trim();
                payload.password = manualPassword;
            } else {
                payload.credential_id = credMode;
            }

            const response = await fetch(`${API_BASE}/system/connectivity-diag`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            if (!response.ok) {
                let errDetail = `Erro HTTP ${response.status}`;
                try {
                    const errJson = await response.json();
                    if (errJson?.detail) errDetail = errJson.detail;
                } catch {}
                throw new Error(errDetail);
            }

            if (!response.body) {
                throw new Error('Stream de resposta indisponível.');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';
            let completedFinals = 0;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed) continue;
                    try {
                        const msg = JSON.parse(trimmed);
                        if (msg.type === 'host_update' && msg.data) {
                            const hostData: HostDiagResult = msg.data;
                            if (hostData.stage === 'Final') {
                                completedFinals++;
                            }
                            setResults(prev =>
                                prev.map(item =>
                                    item.host_input.toUpperCase() === hostData.host_input.toUpperCase()
                                        ? hostData
                                        : item
                                )
                            );
                            setProgressText(
                                hostData.stage === 'PingStage'
                                    ? `Coletando placas e Wi-Fi via WinRM (${hostData.host_input})...`
                                    : `Concluído ${completedFinals} de ${parsedTargets.length} host(s)`
                            );
                        } else if (msg.type === 'done') {
                            setProgressText(`Auditoria concluída (${parsedTargets.length} host(s)).`);
                        }
                    } catch {}
                }
            }

            setLastRunAt(new Date().toISOString());
            showToast(`Auditoria concluída para ${parsedTargets.length} host(s)!`, 'success');
        } catch (err: any) {
            if (err?.name === 'AbortError') return;
            setProgressText(`Falha: ${err.message}`);
            showToast(err.message || 'Erro ao executar auditoria.', 'error');
        } finally {
            setIsRunning(false);
            abortControllerRef.current = null;
        }
    };

    const stats = useMemo(() => {
        const total = results.length;
        const wifiExclusive = results.filter(r => r.winrm_ok && r.wifi_connected && !r.lan_connected).length;
        const lanExclusive = results.filter(r => r.winrm_ok && r.lan_connected && !r.wifi_connected).length;
        const hybrid = results.filter(r => r.winrm_ok && r.lan_connected && r.wifi_connected).length;
        const alerts = results.filter(r => r.stage === 'Final' && (r.overall_state === 'Red' || r.overall_state === 'Amber')).length;
        const totalCerts = results.reduce((acc, r) => acc + (r.certs_8021x?.length || 0), 0);

        return { total, wifiExclusive, lanExclusive, hybrid, alerts, totalCerts };
    }, [results]);

    const filteredResults = useMemo(() => {
        return results.filter(r => {
            if (viewFilter === 'WIFI' && !(r.winrm_ok && r.wifi_connected)) return false;
            if (viewFilter === 'LAN' && !(r.winrm_ok && r.lan_connected)) return false;
            if (viewFilter === 'HYBRID' && !(r.winrm_ok && r.lan_connected && r.wifi_connected)) return false;
            if (viewFilter === 'ALERTS' && r.overall_state !== 'Red' && r.overall_state !== 'Amber') return false;

            if (searchQuery.trim()) {
                const q = searchQuery.trim().toLowerCase();
                const hay = [
                    r.host_input,
                    r.ip_resolved,
                    r.fqdn_resolved,
                    r.domain,
                    r.wifi_ssid,
                    r.wifi_ip,
                    r.overall_badge,
                    ...(r.lan_adapters || []).map(a => `${a.Name} ${a.Description} ${a.IPv4} ${a.MAC}`)
                ]
                    .join(' ')
                    .toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        });
    }, [results, viewFilter, searchQuery]);

    const handleCopySummary = () => {
        if (results.length === 0) {
            showToast('Execute uma auditoria primeiro para copiar o relatório.', 'warning');
            return;
        }
        const fullText = results
            .map(r => r.raw_report || `[${r.host_input}] ${r.overall_badge} - ${r.synthesis}`)
            .join('\n\n');
        navigator.clipboard.writeText(fullText);
        showToast('Resumo técnico copiado para a área de transferência!', 'success');
    };

    const activeLanOf = (h: HostDiagResult) =>
        (h.lan_adapters || []).find(a => a.Status === 'Conectado');

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0 overflow-y-auto custom-scrollbar pr-1">
            {/* Barra de Entrada & Credenciais */}
            <div className="bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 space-y-3 shrink-0">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 pb-2.5">
                    <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
                            <Cable size={18} />
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-white tracking-tight">
                                Auditoria de Interfaces e Conexões Ativas
                            </h3>
                            <p className="text-xs text-zinc-400">
                                Identifica em tempo real quais conexões estão em funcionamento nos hosts (Cabo, Wi-Fi, Híbrido) e certificados 802.1x
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-zinc-400">
                        <span className={clsx('w-2 h-2 rounded-full', isRunning ? 'bg-blue-400 animate-ping' : 'bg-emerald-500')} />
                        <span className="font-medium text-zinc-300">{progressText}</span>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-end">
                    <div className="lg:col-span-6 space-y-1">
                        <label className="block text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                            Hosts ou IPs Alvo (vírgula, espaço ou ponto e vírgula)
                        </label>
                        <input
                            type="text"
                            value={targetsInput}
                            onChange={e => setTargetsInput(e.target.value)}
                            onKeyDown={e => {
                                if (e.key === 'Enter' && !isRunning) runDiagnostic();
                            }}
                            placeholder="Ex: host01.example.com, 1.1.1.1"
                            className="w-full bg-zinc-950 border border-zinc-800 focus:border-blue-500 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono focus:outline-none transition-colors"
                        />
                    </div>

                    <div className="lg:col-span-4 space-y-1">
                        <label className="block text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                            Credencial Administrativa (WinRM)
                        </label>
                        <select
                            value={hasVaultCreds ? credMode : 'manual'}
                            onChange={e => setCredMode(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-800 focus:border-blue-500 rounded-lg px-2.5 py-2 text-xs text-zinc-200 focus:outline-none"
                        >
                            {hasVaultCreds ? (
                                <>
                                    <option value="auto">
                                        Cofre Automático ({vaultCredentials[0].name} - {vaultCredentials[0].username})
                                    </option>
                                    {vaultCredentials.map(c => (
                                        <option key={c.id} value={c.id}>
                                            Cofre: {c.name} ({c.username})
                                        </option>
                                    ))}
                                </>
                            ) : (
                                <option value="" disabled>
                                    Nenhuma credencial disponível no Cofre
                                </option>
                            )}
                            <option value="manual">Informar Usuário / Senha Manualmente...</option>
                        </select>
                    </div>

                    <div className="lg:col-span-2 flex items-center gap-2">
                        {!isRunning ? (
                            <button
                                type="button"
                                onClick={runDiagnostic}
                                className="w-full flex items-center justify-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg shadow transition-colors whitespace-nowrap"
                            >
                                <Play size={14} />
                                <span>Auditar Hosts</span>
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={stopDiagnostic}
                                className="w-full flex items-center justify-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-semibold rounded-lg shadow transition-colors whitespace-nowrap"
                            >
                                <Square size={13} />
                                <span>Parar</span>
                            </button>
                        )}
                    </div>
                </div>

                {(credMode === 'manual' || !hasVaultCreds) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-zinc-800/60">
                        <div>
                            <label className="block text-[11px] text-zinc-400 mb-1">
                                Usuário Administrativo (ex: DOMINIO\admin ou admin)
                            </label>
                            <div className="relative">
                                <KeyRound size={14} className="absolute left-3 top-2.5 text-zinc-500" />
                                <input
                                    type="text"
                                    value={manualUsername}
                                    onChange={e => setManualUsername(e.target.value)}
                                    placeholder="DOMINIO\usuario"
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                                />
                            </div>
                        </div>
                        <div>
                            <label className="block text-[11px] text-zinc-400 mb-1">
                                Senha Administrativa
                            </label>
                            <div className="relative">
                                <Lock size={14} className="absolute left-3 top-2.5 text-zinc-500" />
                                <input
                                    type="password"
                                    value={manualPassword}
                                    onChange={e => setManualPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                                />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Badge de Última Execução + Botão Limpar */}
            {results.length > 0 && lastRunAt && (
                <div className="shrink-0">
                    <LastExecutionBadge
                        timestamp={lastRunAt}
                        target={lastTargetsSummary}
                        onClear={handleClear}
                    />
                </div>
            )}

            {/* Barra Executiva Única: Filtros Rápidos + Certificados 802.1x + Busca */}
            {results.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-2 bg-zinc-900/60 border border-zinc-800 rounded-xl px-3.5 py-2.5 shrink-0">
                    {/* Pílulas Clicáveis de Filtro & Métrica */}
                    <div className="flex flex-wrap items-center gap-1.5">
                        {(
                            [
                                { id: 'ALL', label: 'Todos', count: stats.total, activeCls: 'bg-zinc-700 text-white border-zinc-500' },
                                { id: 'WIFI', label: 'Exclusivo Wi-Fi', count: stats.wifiExclusive, activeCls: 'bg-blue-600/25 text-blue-300 border-blue-500/50' },
                                { id: 'LAN', label: 'Exclusivo Cabo', count: stats.lanExclusive, activeCls: 'bg-emerald-600/25 text-emerald-300 border-emerald-500/50' },
                                { id: 'HYBRID', label: 'Híbrido (Cabo + Wi-Fi)', count: stats.hybrid, activeCls: 'bg-amber-600/25 text-amber-300 border-amber-500/50' },
                                { id: 'ALERTS', label: 'Alertas / Falhas', count: stats.alerts, activeCls: 'bg-red-600/25 text-red-300 border-red-500/50' }
                            ] as const
                        ).map(pill => {
                            const active = viewFilter === pill.id;
                            return (
                                <button
                                    key={pill.id}
                                    type="button"
                                    onClick={() => setViewFilter(pill.id)}
                                    className={clsx(
                                        'px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors flex items-center gap-1.5',
                                        active
                                            ? pill.activeCls
                                            : 'bg-zinc-950/70 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-700'
                                    )}
                                >
                                    <span>{pill.label}</span>
                                    <span className="px-1.5 py-0.2 rounded bg-black/30 text-[10px] font-mono">
                                        {pill.count}
                                    </span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Busca + Certificados 802.1x + Exportar */}
                    <div className="flex flex-wrap items-center gap-2">
                        <div className="relative w-48">
                            <Search size={13} className="absolute left-2.5 top-2 text-zinc-500" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                placeholder="Buscar host, IP, SSID..."
                                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-2.5 py-1 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                            />
                        </div>

                        <button
                            type="button"
                            onClick={() => {
                                setCertModalHostFilter('ALL');
                                setShowCertsModal(true);
                            }}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 transition-colors"
                            title="Abrir auditoria consolidada de certificados 802.1x"
                        >
                            <Award size={13} />
                            <span>Certificados ({stats.totalCerts})</span>
                        </button>

                        <button
                            type="button"
                            onClick={handleCopySummary}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors"
                        >
                            <Copy size={13} />
                            <span>Copiar</span>
                        </button>

                        <button
                            type="button"
                            onClick={handleClear}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-900 hover:bg-red-950/50 text-zinc-400 hover:text-red-300 border border-zinc-800 hover:border-red-800/50 transition-colors"
                        >
                            <RotateCcw size={13} />
                            <span>Limpar</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Lista Limpa e Enxuta de Hosts (Foco nas Conexões Atualmente em Uso + Botão por Host) */}
            {results.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center p-10 bg-zinc-900/30 border border-dashed border-zinc-800 rounded-xl text-center">
                    <div className="p-3.5 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-blue-400 mb-3">
                        <Cable size={28} />
                    </div>
                    <h4 className="text-sm font-bold text-zinc-200">
                        Auditoria de Interfaces e Conexões em Uso
                    </h4>
                    <p className="text-xs text-zinc-400 max-w-md mt-1 leading-relaxed">
                        Informe um ou mais hostnames ou endereços IP acima e clique em{' '}
                        <strong className="text-zinc-200">Auditar Hosts</strong> para verificar quais conexões (Cabo, Wi-Fi ou Híbrido) estão ativas em cada estação.
                    </p>
                </div>
            ) : filteredResults.length === 0 ? (
                <div className="p-8 text-center text-xs text-zinc-400 bg-zinc-900/40 border border-zinc-800 rounded-xl">
                    Nenhum host corresponde ao filtro ou termo de busca selecionado.
                </div>
            ) : (
                <div className="space-y-2 pb-4">
                    {filteredResults.map(host => {
                        const activeLan = activeLanOf(host);
                        return (
                            <div
                                key={host.host_input}
                                className="bg-zinc-900/80 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700/90 rounded-xl px-4 py-3 transition-colors flex flex-col lg:flex-row lg:items-center justify-between gap-3"
                            >
                                {/* Esquerda: Identificação do Host */}
                                <div className="flex items-center gap-3 min-w-0 lg:w-[28%]">
                                    <span
                                        className={clsx(
                                            'w-2.5 h-2.5 rounded-full shrink-0 shadow-sm',
                                            DOT_STYLES[host.overall_state] || DOT_STYLES.Neutral
                                        )}
                                    />
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-sm font-bold text-white font-mono truncate">
                                                {host.host_input}
                                            </span>
                                            {host.ip_resolved && host.ip_resolved !== host.host_input && (
                                                <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-zinc-950 text-zinc-300 border border-zinc-800">
                                                    {host.ip_resolved}
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-[11px] text-zinc-500 truncate mt-0.5">
                                            {host.winrm_ok
                                                ? `${host.domain || 'Local'} • Coletado às ${host.timestamp}`
                                                : host.stage === 'Final'
                                                ? host.synthesis
                                                : `Consultando interfaces via WinRM...`}
                                        </div>
                                    </div>
                                </div>

                                {/* Centro: Resumo Visual Rápido das Conexões em Uso */}
                                <div className="flex flex-wrap items-center gap-2 flex-1">
                                    {host.stage !== 'Final' ? (
                                        <span className="text-xs text-blue-300/90 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-950/30 border border-blue-900/40">
                                            <Server size={12} className="animate-pulse" />
                                            <span>{host.overall_badge}</span>
                                        </span>
                                    ) : !host.winrm_ok ? (
                                        <span className="text-xs text-amber-300/90 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-950/25 border border-amber-800/40">
                                            <AlertTriangle size={12} />
                                            <span>
                                                {host.ping_ok
                                                    ? `Ping ${host.ping_ms} ms • WinRM: ${host.tiles.tile3.main}`
                                                    : host.tiles.tile1.main}
                                            </span>
                                        </span>
                                    ) : (
                                        <>
                                            {/* Chip Cabo (Ethernet) */}
                                            <div
                                                className={clsx(
                                                    'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border',
                                                    host.lan_connected
                                                        ? 'bg-emerald-950/30 text-emerald-300 border-emerald-800/50 font-medium'
                                                        : 'bg-zinc-950/70 text-zinc-500 border-zinc-800/80'
                                                )}
                                            >
                                                <Cable size={13} />
                                                <span>
                                                    {host.lan_connected
                                                        ? `Cabo Ativo${activeLan?.SpeedText ? ` (${activeLan.SpeedText})` : ''}`
                                                        : 'Cabo Desconectado'}
                                                </span>
                                            </div>

                                            {/* Chip Wi-Fi (WLAN) */}
                                            <div
                                                className={clsx(
                                                    'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border',
                                                    host.wifi_connected
                                                        ? 'bg-blue-950/35 text-blue-300 border-blue-800/50 font-medium'
                                                        : 'bg-zinc-950/70 text-zinc-500 border-zinc-800/80'
                                                )}
                                            >
                                                {host.wifi_connected ? <Wifi size={13} /> : <WifiOff size={13} />}
                                                <span>
                                                    {host.wifi_connected
                                                        ? `Wi-Fi: ${host.wifi_ssid || 'Conectado'} (${host.wifi_signal || '?%'})`
                                                        : host.wifi_present
                                                        ? 'Wi-Fi Desconectado'
                                                        : 'Sem Placa Wi-Fi'}
                                                </span>
                                            </div>

                                            {/* Chip Certificado 802.1x (apenas se relevante) */}
                                            {(host.wifi_present || host.certs_8021x.length > 0) && (
                                                <div
                                                    className={clsx(
                                                        'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border',
                                                        host.cert_status === 'OK'
                                                            ? 'bg-emerald-950/20 text-emerald-300 border-emerald-800/40'
                                                            : host.cert_status === 'Expiring' || host.cert_status === 'Missing'
                                                            ? 'bg-amber-950/25 text-amber-300 border-amber-800/40'
                                                            : 'bg-red-950/25 text-red-300 border-red-800/40'
                                                    )}
                                                >
                                                    <ShieldCheck size={13} />
                                                    <span>
                                                        {host.cert_status === 'OK'
                                                            ? 'Cert. 802.1x OK'
                                                            : host.cert_status === 'Expiring'
                                                            ? 'Cert. Expirando'
                                                            : host.cert_status === 'Problem'
                                                            ? 'Cert. Inválido'
                                                            : 'Sem Cert. 802.1x'}
                                                    </span>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>

                                {/* Direita: Badge Consolidado + Botão Focado "Resumo das Conexões" */}
                                <div className="flex items-center justify-end gap-2 shrink-0">
                                    <span
                                        className={clsx(
                                            'px-2.5 py-1 rounded-lg text-[11px] font-bold tracking-wide border whitespace-nowrap',
                                            BADGE_STYLES[host.overall_state] || BADGE_STYLES.Neutral
                                        )}
                                    >
                                        {host.overall_badge}
                                    </span>

                                    {host.stage === 'Final' && (
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setShowRawLogInModal(false);
                                                setSelectedHostModal(host);
                                            }}
                                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600/15 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/40 transition-colors whitespace-nowrap"
                                        >
                                            <Eye size={13} />
                                            <span>Resumo das Conexões</span>
                                        </button>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* MODAL FOCADO POR HOST: Resumo Completo das Conexões Utilizadas */}
            {selectedHostModal && (
                <div
                    className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in"
                    onClick={() => setSelectedHostModal(null)}
                >
                    <div
                        className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden"
                        onClick={e => e.stopPropagation()}
                    >
                        {/* Header do Modal */}
                        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/70">
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="p-2 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
                                    <Laptop size={20} />
                                </div>
                                <div className="min-w-0">
                                    <div className="flex items-center gap-2.5 flex-wrap">
                                        <h3 className="text-base font-bold text-white font-mono">
                                            Resumo das Conexões — {selectedHostModal.host_input}
                                        </h3>
                                        <span
                                            className={clsx(
                                                'px-2 py-0.5 rounded text-[11px] font-bold border',
                                                BADGE_STYLES[selectedHostModal.overall_state]
                                            )}
                                        >
                                            {selectedHostModal.overall_badge}
                                        </span>
                                    </div>
                                    <p className="text-xs text-zinc-400 mt-0.5 truncate">
                                        IP: {selectedHostModal.ip_resolved || 'N/D'} • Domínio: {selectedHostModal.domain || 'Local'} • {selectedHostModal.os_caption || 'Windows'} • Coleta: {selectedHostModal.timestamp}
                                    </p>
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setSelectedHostModal(null)}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Corpo Focado em Somente Este Host */}
                        <div className="p-5 overflow-y-auto space-y-4 custom-scrollbar text-xs">
                            {/* Síntese Executiva */}
                            <div
                                className={clsx(
                                    'p-3.5 rounded-xl border flex items-start gap-2.5',
                                    selectedHostModal.overall_state === 'Green'
                                        ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-200'
                                        : selectedHostModal.overall_state === 'Amber'
                                        ? 'bg-amber-950/20 border-amber-800/40 text-amber-200'
                                        : selectedHostModal.overall_state === 'Red'
                                        ? 'bg-red-950/20 border-red-800/40 text-red-200'
                                        : 'bg-zinc-950 border-zinc-800 text-zinc-200'
                                )}
                            >
                                <Server size={16} className="shrink-0 mt-0.5" />
                                <div className="space-y-0.5">
                                    <div className="font-bold uppercase text-[10px] tracking-wider opacity-80">
                                        Diagnóstico de Enlaces Atualmente em Uso
                                    </div>
                                    <div className="text-xs leading-relaxed">{selectedHostModal.synthesis}</div>
                                </div>
                            </div>

                            {selectedHostModal.winrm_ok && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {/* Bloco 1: Wi-Fi (WLAN) */}
                                    <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                                            <span className="font-bold text-zinc-200 flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                                                <Wifi size={14} className="text-blue-400" />
                                                <span>Conexão Sem Fio (Wi-Fi)</span>
                                            </span>
                                            <span
                                                className={clsx(
                                                    'px-2 py-0.5 rounded text-[10px] font-bold',
                                                    selectedHostModal.wifi_connected
                                                        ? 'bg-blue-950 text-blue-300 border border-blue-800'
                                                        : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
                                                )}
                                            >
                                                {selectedHostModal.wifi_state}
                                            </span>
                                        </div>

                                        {!selectedHostModal.wifi_present ? (
                                            <p className="text-zinc-500">
                                                Nenhum adaptador Wi-Fi ativo ou serviço WLAN AutoConfig parado neste host.
                                            </p>
                                        ) : selectedHostModal.wifi_connected ? (
                                            <div className="space-y-2 text-[11px]">
                                                <div className="grid grid-cols-2 gap-2">
                                                    <div className="p-2 rounded-lg bg-zinc-900/70 border border-zinc-800/60">
                                                        <div className="text-zinc-500 text-[10px]">REDE (SSID)</div>
                                                        <div className="font-bold text-blue-300 text-xs truncate">{selectedHostModal.wifi_ssid}</div>
                                                    </div>
                                                    <div className="p-2 rounded-lg bg-zinc-900/70 border border-zinc-800/60">
                                                        <div className="text-zinc-500 text-[10px]">QUALIDADE DO SINAL</div>
                                                        <div className="font-bold text-emerald-300 text-xs">{selectedHostModal.wifi_signal}</div>
                                                    </div>
                                                </div>
                                                <div className="space-y-1 font-mono text-zinc-300 pt-1">
                                                    <div><span className="text-zinc-500">Adaptador:</span> {selectedHostModal.wifi_desc}</div>
                                                    <div><span className="text-zinc-500">IPv4 Wi-Fi:</span> {selectedHostModal.wifi_ip || 'N/D'}</div>
                                                    <div><span className="text-zinc-500">BSSID (AP):</span> {selectedHostModal.wifi_bssid || 'N/D'}</div>
                                                    <div><span className="text-zinc-500">Rádio / Canal:</span> {selectedHostModal.wifi_radio} • Canal {selectedHostModal.wifi_channel}</div>
                                                    <div><span className="text-zinc-500">Autenticação:</span> {selectedHostModal.wifi_auth} ({selectedHostModal.wifi_cipher})</div>
                                                </div>
                                                {selectedHostModal.wifi_all_profiles.length > 0 && (
                                                    <div className="pt-2 border-t border-zinc-800/80 text-zinc-400">
                                                        <strong className="text-zinc-300">Perfis Salvos:</strong> {selectedHostModal.wifi_all_profiles.join(', ')}
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="space-y-2 text-zinc-400">
                                                <div>Adaptador presente ({selectedHostModal.wifi_desc || 'WLAN'}), porém desconectado.</div>
                                                {selectedHostModal.wifi_all_profiles.length > 0 && (
                                                    <div className="pt-2 border-t border-zinc-800/80">
                                                        <strong className="text-zinc-300">Perfis Salvos:</strong> {selectedHostModal.wifi_all_profiles.join(', ')}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* Bloco 2: Conexão Cabeada (Ethernet) */}
                                    <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                                            <span className="font-bold text-zinc-200 flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                                                <Cable size={14} className="text-emerald-400" />
                                                <span>Interfaces Cabeadas ({selectedHostModal.lan_adapters.length})</span>
                                            </span>
                                            <span
                                                className={clsx(
                                                    'px-2 py-0.5 rounded text-[10px] font-bold',
                                                    selectedHostModal.lan_connected
                                                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                                        : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
                                                )}
                                            >
                                                {selectedHostModal.lan_connected ? 'Link Ativo' : 'Sem Link'}
                                            </span>
                                        </div>

                                        {selectedHostModal.lan_adapters.length === 0 ? (
                                            <p className="text-zinc-500">Nenhuma placa Ethernet física detectada.</p>
                                        ) : (
                                            <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1 custom-scrollbar">
                                                {selectedHostModal.lan_adapters.map((nic, i) => (
                                                    <div key={i} className="p-2.5 rounded-lg bg-zinc-900/70 border border-zinc-800/70 space-y-1">
                                                        <div className="flex items-center justify-between">
                                                            <span className="font-bold text-zinc-200">{nic.Name || 'Ethernet'}</span>
                                                            <span
                                                                className={clsx(
                                                                    'px-1.5 py-0.5 rounded text-[10px] font-bold',
                                                                    nic.Status === 'Conectado'
                                                                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                                                        : 'bg-zinc-950 text-zinc-500 border border-zinc-800'
                                                                )}
                                                            >
                                                                {nic.Status} • {nic.SpeedText}
                                                            </span>
                                                        </div>
                                                        <div className="text-zinc-400 text-[11px] truncate">{nic.Description}</div>
                                                        <div className="grid grid-cols-2 gap-1 text-[11px] font-mono text-zinc-300 pt-1">
                                                            <div>IPv4: {nic.IPv4 || 'N/D'}</div>
                                                            <div>MAC: {nic.MAC || 'N/D'}</div>
                                                            <div>{nic.GwStatus}</div>
                                                            <div className="truncate" title={nic.DNS}>DNS: {nic.DNS || 'N/D'}</div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Bloco 3: Certificados 802.1x e Políticas RSOP do Host */}
                            {selectedHostModal.winrm_ok && (
                                <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <span className="font-bold text-zinc-200 flex items-center gap-1.5 uppercase tracking-wider text-[11px]">
                                            <ShieldCheck size={14} className="text-amber-400" />
                                            <span>Controle 802.1x / Certificados de Rede ({selectedHostModal.certs_8021x.length})</span>
                                        </span>
                                        <div className="flex items-center gap-2">
                                            <span
                                                className={clsx(
                                                    'px-2 py-0.5 rounded text-[10px] font-bold border',
                                                    selectedHostModal.cert_status === 'OK'
                                                        ? BADGE_STYLES.Green
                                                        : selectedHostModal.cert_status === 'Expiring'
                                                        ? BADGE_STYLES.Amber
                                                        : selectedHostModal.cert_status === 'Problem'
                                                        ? BADGE_STYLES.Red
                                                        : BADGE_STYLES.Neutral
                                                )}
                                            >
                                                {selectedHostModal.cert_summary}
                                            </span>
                                            {selectedHostModal.certs_8021x.length > 0 && (
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        setCertModalHostFilter(selectedHostModal.host_input);
                                                        setShowCertsModal(true);
                                                    }}
                                                    className="text-[11px] text-amber-400 hover:text-amber-300 hover:underline flex items-center gap-1 font-semibold ml-1.5"
                                                >
                                                    <Award size={12} />
                                                    <span>Auditar Completo</span>
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* Sub-bloco RSOP: Políticas 802.1X Configuradas */}
                                    {selectedHostModal.wifi_profiles_8021x_detail && selectedHostModal.wifi_profiles_8021x_detail.length > 0 && (
                                        <div className="p-3 bg-zinc-900/90 border border-zinc-800 rounded-xl space-y-2">
                                            <div className="flex items-center justify-between text-[11px] font-bold text-amber-300">
                                                <span className="flex items-center gap-1.5">
                                                    <Wifi size={13} className="text-amber-400" />
                                                    <span>Políticas de Rede Sem Fio 802.1X / RSOP ({selectedHostModal.wifi_profiles_8021x_detail.length})</span>
                                                </span>
                                                <span className="text-[10px] text-zinc-400 font-normal">GPO / Perfil WLAN</span>
                                            </div>
                                            <div className="grid grid-cols-1 gap-2">
                                                {selectedHostModal.wifi_profiles_8021x_detail.map((p, pIdx) => (
                                                    <div key={pIdx} className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-2.5 text-[11px] space-y-1.5">
                                                        <div className="flex flex-wrap items-center justify-between gap-1">
                                                            <span className="font-bold text-white font-mono">{p.ProfileName}</span>
                                                            <div className="flex items-center gap-1.5">
                                                                <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/15 text-blue-300 border border-blue-500/30 font-semibold">
                                                                    {p.EapTypeName}
                                                                </span>
                                                                {p.InnerEapTypeName && (
                                                                    <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                                                                        {p.InnerEapTypeName}
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-2 gap-y-1 text-zinc-400 text-[10px]">
                                                            <div>Modo de Autenticação: <strong className="text-zinc-200">{p.AuthMode === 'machine' ? 'Credencial da Máquina (Computador)' : p.AuthMode === 'user' ? 'Credencial do Usuário' : p.AuthMode}</strong></div>
                                                            <div>Reconexão Rápida: <strong className={p.FastReconnect ? 'text-emerald-400' : 'text-zinc-400'}>{p.FastReconnect ? 'Ativada (Sim)' : 'Não'}</strong></div>
                                                            <div>Validar Servidor: <strong className={p.ValidateServer ? 'text-emerald-400' : 'text-zinc-400'}>{p.ValidateServer ? 'Sim (Valida Certificado)' : 'Não'}</strong></div>
                                                            <div>CAs Raiz Confiáveis Marcadas: <strong className="text-amber-400">{p.TrustedRootCount} autoridade(s)</strong></div>
                                                            {p.ServerNames && <div className="sm:col-span-2">Servidores Permitidos: <span className="font-mono text-zinc-300">{p.ServerNames}</span></div>}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Grade de Certificados Auditados */}
                                    {selectedHostModal.certs_8021x.length > 0 && (
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                            {selectedHostModal.certs_8021x.map((c, idx) => {
                                                const isPersonal = c.Store === 'LocalMachine\\My';
                                                const isValid = c.DaysLeft > 0 && (!isPersonal || c.HasPrivateKey);
                                                const isExpiring = isValid && c.DaysLeft <= 30;
                                                return (
                                                    <div
                                                        key={idx}
                                                        className="p-3 rounded-xl bg-zinc-900/70 border border-zinc-800/80 space-y-2 text-[11px] hover:border-zinc-700 transition-colors"
                                                    >
                                                        {c.IsEapTrustedRoot && (
                                                            <div className={clsx(
                                                                'px-2 py-0.5 rounded text-[10px] flex items-center justify-between gap-1.5 border font-semibold',
                                                                c.IsMissingFromStore
                                                                    ? 'bg-red-950/40 border-red-500/50 text-red-300'
                                                                    : c.DaysLeft <= 0
                                                                    ? 'bg-red-950/30 border-red-500/40 text-red-300'
                                                                    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                                                            )}>
                                                                <span className="flex items-center gap-1 truncate">
                                                                    <ShieldCheck size={12} className="shrink-0 text-emerald-400" />
                                                                    <span className="truncate">CA Marcada na Política ({c.EapProfileName})</span>
                                                                </span>
                                                                {c.IsMissingFromStore ? (
                                                                    <span className="text-red-400 font-bold uppercase shrink-0">NÃO INSTALADA!</span>
                                                                ) : (
                                                                    <span className="text-emerald-400 font-bold shrink-0">Marcada [✓]</span>
                                                                )}
                                                            </div>
                                                        )}

                                                        <div className="flex items-center justify-between gap-1 pb-1 border-b border-zinc-800/50">
                                                            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-zinc-950 text-zinc-400 border border-zinc-800">{c.Store}</span>
                                                            <div className="flex items-center gap-1.5">
                                                                <span className={clsx(
                                                                    'text-[10px] font-semibold flex items-center gap-1',
                                                                    !isValid ? 'text-red-400' : isExpiring ? 'text-amber-400' : 'text-emerald-400'
                                                                )}>
                                                                    {!isValid ? <XCircle size={11} /> : isExpiring ? <AlertTriangle size={11} /> : <CheckCircle2 size={11} />}
                                                                    <span>{c.IsMissingFromStore ? 'Ausente' : c.DaysLeft <= 0 ? `Expirado (${c.NotAfter})` : `${c.NotAfter} (${c.DaysLeft}d)`}</span>
                                                                </span>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => setSelectedCertDetail({
                                                                        cert: c,
                                                                        hostInput: selectedHostModal.host_input,
                                                                        ip: selectedHostModal.ip_resolved,
                                                                        domain: selectedHostModal.domain
                                                                    })}
                                                                    className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-zinc-800 hover:bg-zinc-700 text-blue-400 hover:text-blue-300 border border-zinc-700 transition-colors"
                                                                    title="Ver detalhes completos em janela dedicada"
                                                                >
                                                                    <Eye size={11} />
                                                                    <span>Detalhes</span>
                                                                </button>
                                                            </div>
                                                        </div>

                                                        <div className="text-zinc-200 font-medium truncate" title={c.Subject}>
                                                            <span className="text-zinc-500">Titular: </span>{c.Subject}
                                                        </div>
                                                        <div className="text-zinc-400 truncate text-[10px]" title={c.Issuer}>
                                                            <span className="text-zinc-500">Emissor: </span>{c.Issuer}
                                                        </div>
                                                        <div className="flex items-center justify-between text-[10px] text-zinc-500 pt-1 border-t border-zinc-800/50">
                                                            <span>Chave Privada: <strong className={c.HasPrivateKey ? 'text-emerald-400' : 'text-zinc-400'}>{c.HasPrivateKey ? 'Sim' : isPersonal ? 'Ausente' : 'N/A'}</strong></span>
                                                            <span className="font-mono">SHA1: {c.Thumbprint.slice(0, 10)}...</span>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Toggle Opcional de Log Bruto */}
                            <div className="border border-zinc-800 rounded-xl overflow-hidden">
                                <button
                                    type="button"
                                    onClick={() => setShowRawLogInModal(v => !v)}
                                    className="w-full flex items-center justify-between px-4 py-2.5 bg-zinc-950/60 hover:bg-zinc-900 text-xs font-semibold text-zinc-300 transition-colors"
                                >
                                    <span className="flex items-center gap-2">
                                        <FileText size={14} className="text-zinc-400" />
                                        <span>Relatório Técnico Completo (Texto)</span>
                                    </span>
                                    {showRawLogInModal ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                                </button>
                                {showRawLogInModal && (
                                    <pre className="p-3.5 bg-zinc-950 text-zinc-300 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap leading-relaxed border-t border-zinc-800">
                                        {selectedHostModal.raw_report || selectedHostModal.synthesis}
                                    </pre>
                                )}
                            </div>
                        </div>

                        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-zinc-800 bg-zinc-950/70">
                            <button
                                type="button"
                                onClick={() => {
                                    navigator.clipboard.writeText(
                                        selectedHostModal.raw_report || selectedHostModal.synthesis
                                    );
                                    showToast('Relatório do host copiado!', 'success');
                                }}
                                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors"
                            >
                                <Copy size={13} />
                                <span>Copiar Relatório</span>
                            </button>
                            <button
                                type="button"
                                onClick={() => setSelectedHostModal(null)}
                                className="px-4 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                            >
                                Fechar
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL 2: Auditoria Estrita de Certificados 802.1x e Controle de Rede */}
            {showCertsModal && (
                <div
                    className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in"
                    onClick={() => setShowCertsModal(false)}
                >
                    <div
                        className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-5xl max-h-[88vh] flex flex-col shadow-2xl overflow-hidden"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-zinc-800 bg-zinc-950/70">
                            <div className="flex items-center gap-2.5">
                                <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                                    <Award size={20} />
                                </div>
                                <div>
                                    <h3 className="text-base font-bold text-white">
                                        Auditoria de Certificados 802.1x e Controle de Rede
                                    </h3>
                                    <p className="text-xs text-zinc-400">
                                        Inspeção estrita em Cert:\LocalMachine\My, CA e Root (excluindo certificados de terceiros/ruído)
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <select
                                    value={certModalHostFilter}
                                    onChange={e => setCertModalHostFilter(e.target.value)}
                                    className="bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none"
                                >
                                    <option value="ALL">[Todos os Hosts Auditados]</option>
                                    {results
                                        .filter(r => r.winrm_ok)
                                        .map(r => (
                                            <option key={r.host_input} value={r.host_input}>
                                                {r.host_input} ({r.certs_8021x?.length || 0} cert)
                                            </option>
                                        ))}
                                </select>
                                <button
                                    type="button"
                                    onClick={() => setShowCertsModal(false)}
                                    className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        <div className="p-5 overflow-y-auto space-y-4 custom-scrollbar text-xs">
                            {results.filter(r => r.winrm_ok).length === 0 ? (
                                <div className="p-6 text-center text-zinc-400 bg-zinc-950 border border-zinc-800 rounded-xl">
                                    Nenhum host com sessão WinRM ativa nesta execução. Execute a auditoria com credenciais administrativas para inspecionar os repositórios de certificados.
                                </div>
                            ) : (
                                results
                                    .filter(
                                        r =>
                                            r.winrm_ok &&
                                            (certModalHostFilter === 'ALL' ||
                                                r.host_input.toUpperCase() === certModalHostFilter.toUpperCase())
                                    )
                                    .map(h => (
                                        <div
                                            key={h.host_input}
                                            className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3"
                                        >
                                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2">
                                                <div>
                                                    <span className="font-bold text-white font-mono text-sm">
                                                        {h.host_input}
                                                    </span>
                                                    <span className="text-zinc-400 ml-2">
                                                        ({h.ip_resolved}) • Domínio: {h.domain || 'Local'}
                                                    </span>
                                                </div>
                                                <span
                                                    className={clsx(
                                                        'px-2.5 py-0.5 rounded text-[11px] font-bold border',
                                                        h.cert_status === 'OK'
                                                            ? BADGE_STYLES.Green
                                                            : h.cert_status === 'Expiring'
                                                            ? BADGE_STYLES.Amber
                                                            : h.cert_status === 'Problem'
                                                            ? BADGE_STYLES.Red
                                                            : BADGE_STYLES.Neutral
                                                    )}
                                                >
                                                    802.1x: {h.cert_summary}
                                                </span>
                                            </div>

                                            <div className="text-zinc-400">
                                                <strong className="text-zinc-300">Perfis WLAN 802.1x:</strong>{' '}
                                                {h.wifi_profiles_8021x?.length > 0
                                                    ? h.wifi_profiles_8021x.join(', ')
                                                    : 'Nenhum perfil WLAN 802.1x detectado'}
                                            </div>

                                            {/* Sub-bloco RSOP: Políticas 802.1X Configuradas */}
                                            {h.wifi_profiles_8021x_detail && h.wifi_profiles_8021x_detail.length > 0 && (
                                                <div className="p-3 bg-zinc-900/90 border border-zinc-800 rounded-xl space-y-2">
                                                    <div className="flex items-center justify-between text-[11px] font-bold text-amber-300">
                                                        <span className="flex items-center gap-1.5">
                                                            <Wifi size={13} className="text-amber-400" />
                                                            <span>Configurações EAP na Política / RSOP ({h.wifi_profiles_8021x_detail.length} perfil)</span>
                                                        </span>
                                                        <span className="text-[10px] text-zinc-400 font-normal">Propriedades EAP Protegidas</span>
                                                    </div>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                                        {h.wifi_profiles_8021x_detail.map((p, pIdx) => (
                                                            <div key={pIdx} className="bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-2.5 text-[11px] space-y-1.5">
                                                                <div className="flex flex-wrap items-center justify-between gap-1">
                                                                    <span className="font-bold text-white font-mono">{p.ProfileName}</span>
                                                                    <div className="flex items-center gap-1.5">
                                                                        <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/15 text-blue-300 border border-blue-500/30 font-semibold">
                                                                            {p.EapTypeName}
                                                                        </span>
                                                                        {p.InnerEapTypeName && (
                                                                            <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                                                                                {p.InnerEapTypeName}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-2 gap-y-1 text-zinc-400 text-[10px]">
                                                                    <div>Modo de Autenticação: <strong className="text-zinc-200">{p.AuthMode === 'machine' ? 'Credencial da Máquina' : p.AuthMode === 'user' ? 'Credencial do Usuário' : p.AuthMode}</strong></div>
                                                                    <div>Reconexão Rápida: <strong className={p.FastReconnect ? 'text-emerald-400' : 'text-zinc-400'}>{p.FastReconnect ? 'Ativada (Sim)' : 'Não'}</strong></div>
                                                                    <div>Validar Servidor: <strong className={p.ValidateServer ? 'text-emerald-400' : 'text-zinc-400'}>{p.ValidateServer ? 'Sim' : 'Não'}</strong></div>
                                                                    <div>CAs Raiz Confiáveis Marcadas: <strong className="text-amber-400">{p.TrustedRootCount} autoridade(s)</strong></div>
                                                                    {p.ServerNames && <div className="sm:col-span-2">Servidores Permitidos: <span className="font-mono text-zinc-300">{p.ServerNames}</span></div>}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {(!h.certs_8021x || h.certs_8021x.length === 0) ? (
                                                <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 text-amber-300/90 flex items-center gap-2">
                                                    <AlertTriangle size={15} className="shrink-0" />
                                                    <span>
                                                        Nenhum certificado de autenticação 802.1x localizado em Cert:\LocalMachine neste host.
                                                    </span>
                                                </div>
                                            ) : (
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    {h.certs_8021x.map((c, idx) => {
                                                        const isPersonal = c.Store === 'LocalMachine\\My';
                                                        const isValid = c.DaysLeft > 0 && (!isPersonal || c.HasPrivateKey);
                                                        const isExpiring = isValid && c.DaysLeft <= 30;

                                                        return (
                                                            <div
                                                                key={idx}
                                                                className={clsx(
                                                                    'p-3.5 rounded-xl border space-y-2 transition-all',
                                                                    !isValid
                                                                        ? 'bg-red-950/20 border-red-800/50'
                                                                        : isExpiring
                                                                        ? 'bg-amber-950/20 border-amber-800/50'
                                                                        : 'bg-emerald-950/15 border-emerald-800/40'
                                                                )}
                                                            >
                                                                {/* Top Bar: Repositório, Validade e Botão Detalhes */}
                                                                <div className="flex flex-wrap items-center justify-between gap-2 pb-1 border-b border-zinc-800/60">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
                                                                            {c.Store}
                                                                        </span>
                                                                        {c.FriendlyName && (
                                                                            <span className="text-[10px] text-zinc-400 font-mono hidden sm:inline truncate max-w-[200px]" title={c.FriendlyName}>
                                                                                {c.FriendlyName}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <div className="flex items-center gap-2">
                                                                        <span
                                                                            className={clsx(
                                                                                'text-[11px] font-bold flex items-center gap-1',
                                                                                !isValid
                                                                                    ? 'text-red-400'
                                                                                    : isExpiring
                                                                                    ? 'text-amber-400'
                                                                                    : 'text-emerald-400'
                                                                            )}
                                                                        >
                                                                            {!isValid ? (
                                                                                <XCircle size={13} />
                                                                            ) : isExpiring ? (
                                                                                <AlertTriangle size={13} />
                                                                            ) : (
                                                                                <CheckCircle2 size={13} />
                                                                            )}
                                                                            <span>
                                                                                {c.IsMissingFromStore
                                                                                    ? 'Não Instalada!'
                                                                                    : c.DaysLeft <= 0
                                                                                    ? `Expirado (${c.NotAfter})`
                                                                                    : `Válido até ${c.NotAfter} (${c.DaysLeft}d)`}
                                                                            </span>
                                                                        </span>
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => setSelectedCertDetail({
                                                                                cert: c,
                                                                                hostInput: h.host_input,
                                                                                ip: h.ip_resolved,
                                                                                domain: h.domain
                                                                            })}
                                                                            className="flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-semibold bg-zinc-900 hover:bg-zinc-800 text-blue-400 hover:text-blue-300 border border-zinc-800 hover:border-zinc-700 transition-colors"
                                                                            title="Abrir inspetor completo em janela dedicada"
                                                                        >
                                                                            <Eye size={12} />
                                                                            <span>Detalhes</span>
                                                                        </button>
                                                                    </div>
                                                                </div>

                                                                {/* Indicador de Autoridade Raiz Marcada na Política 802.1X */}
                                                                {c.IsEapTrustedRoot && (
                                                                    <div className={clsx(
                                                                        'px-2.5 py-1 rounded-lg border text-[10px] flex items-center justify-between gap-1.5 font-semibold',
                                                                        c.IsMissingFromStore
                                                                            ? 'bg-red-950/40 border-red-500/50 text-red-300'
                                                                            : c.DaysLeft <= 0
                                                                            ? 'bg-red-950/30 border-red-500/40 text-red-300'
                                                                            : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                                                                    )}>
                                                                        <span className="flex items-center gap-1.5 truncate">
                                                                            <ShieldCheck size={12} className="shrink-0 text-emerald-400" />
                                                                            <span className="truncate">Autoridade Raiz Confiável Marcada na Política 802.1X ({c.EapProfileName})</span>
                                                                        </span>
                                                                        {c.IsMissingFromStore ? (
                                                                            <span className="text-red-400 font-bold uppercase shrink-0">NÃO INSTALADA!</span>
                                                                        ) : (
                                                                            <span className="text-emerald-400 font-bold shrink-0">Marcada [✓]</span>
                                                                        )}
                                                                    </div>
                                                                )}

                                                                {/* Informações Resumidas e Limpas */}
                                                                <div className="text-zinc-200 font-semibold truncate" title={c.Subject}>
                                                                    <span className="text-zinc-400 font-normal">Titular: </span>{c.Subject}
                                                                </div>
                                                                <div className="text-zinc-400 truncate text-[11px]" title={c.Issuer}>
                                                                    <span className="text-zinc-500">Emissor: </span>{c.Issuer}
                                                                </div>

                                                                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400 pt-1 border-t border-zinc-800/70">
                                                                    <span>
                                                                        Chave Privada:{' '}
                                                                        <strong className={c.HasPrivateKey ? 'text-emerald-400' : 'text-zinc-400'}>
                                                                            {c.HasPrivateKey ? 'Sim (Presente)' : isPersonal ? 'Ausente!' : 'N/A (CA)'}
                                                                        </strong>
                                                                    </span>
                                                                    {c.Template && (
                                                                        <span className="truncate">Template: {c.Template}</span>
                                                                    )}
                                                                </div>

                                                                <div className="flex items-center justify-between gap-2 text-[10px] font-mono text-zinc-500">
                                                                    <span className="truncate">SHA1: {c.Thumbprint}</span>
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => {
                                                                            navigator.clipboard.writeText(c.Thumbprint);
                                                                            showToast('Thumbprint copiado!', 'info');
                                                                        }}
                                                                        className="text-blue-400 hover:underline shrink-0"
                                                                    >
                                                                        Copiar Hash
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                    ))
                            )}
                        </div>

                        <div className="flex justify-end px-5 py-3 border-t border-zinc-800 bg-zinc-950/70">
                            <button
                                type="button"
                                onClick={() => setShowCertsModal(false)}
                                className="px-4 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                            >
                                Fechar
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL 3: Inspetor Dedicado de Certificado 802.1X (Layered Popup Modal z-[120]) */}
            {selectedCertDetail && (
                <div
                    className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in"
                    onClick={() => setSelectedCertDetail(null)}
                >
                    <div
                        className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden"
                        onClick={e => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950/80">
                            <div className="flex items-center gap-3">
                                <div className={clsx(
                                    'p-2.5 rounded-xl border',
                                    selectedCertDetail.cert.DaysLeft <= 0 || (selectedCertDetail.cert.Store === 'LocalMachine\\My' && !selectedCertDetail.cert.HasPrivateKey)
                                        ? 'bg-red-500/15 border-red-500/30 text-red-400'
                                        : selectedCertDetail.cert.DaysLeft <= 30
                                        ? 'bg-amber-500/15 border-amber-500/30 text-amber-400'
                                        : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                                )}>
                                    <Award size={22} />
                                </div>
                                <div>
                                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                                        <span>Inspetor de Certificado Digital</span>
                                        {selectedCertDetail.cert.IsEapTrustedRoot && (
                                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">
                                                802.1X PEAP
                                            </span>
                                        )}
                                    </h3>
                                    <p className="text-xs text-zinc-400">
                                        Host: <span className="font-mono text-zinc-200">{selectedCertDetail.hostInput}</span>
                                        {selectedCertDetail.ip && <span> ({selectedCertDetail.ip})</span>}
                                        {selectedCertDetail.domain && <span> • Domínio: {selectedCertDetail.domain}</span>}
                                    </p>
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={() => setSelectedCertDetail(null)}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Body */}
                        <div className="p-5 overflow-y-auto space-y-4 custom-scrollbar text-xs">
                            {/* Banner de Validade e Política EAP */}
                            <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-xs px-2.5 py-1 rounded bg-zinc-900 text-zinc-300 border border-zinc-700">
                                        Repositório: {selectedCertDetail.cert.Store}
                                    </span>
                                    {selectedCertDetail.cert.Template && (
                                        <span className="text-xs text-zinc-400">
                                            Template: <strong className="text-zinc-200">{selectedCertDetail.cert.Template}</strong>
                                        </span>
                                    )}
                                </div>
                                <div className={clsx(
                                    'px-3 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 border',
                                    selectedCertDetail.cert.DaysLeft <= 0
                                        ? 'bg-red-950/40 border-red-500/50 text-red-400'
                                        : selectedCertDetail.cert.DaysLeft <= 30
                                        ? 'bg-amber-950/40 border-amber-500/50 text-amber-400'
                                        : 'bg-emerald-950/40 border-emerald-500/50 text-emerald-400'
                                )}>
                                    {selectedCertDetail.cert.DaysLeft <= 0 ? (
                                        <XCircle size={14} />
                                    ) : selectedCertDetail.cert.DaysLeft <= 30 ? (
                                        <AlertTriangle size={14} />
                                    ) : (
                                        <CheckCircle2 size={14} />
                                    )}
                                    <span>
                                        {selectedCertDetail.cert.DaysLeft <= 0
                                            ? `Expirado em ${selectedCertDetail.cert.NotAfter}`
                                            : `Válido até ${selectedCertDetail.cert.NotAfter} (${selectedCertDetail.cert.DaysLeft} dias restantes)`}
                                    </span>
                                </div>
                            </div>

                            {/* Bloco RSOP / Propriedades EAP quando marcado */}
                            {selectedCertDetail.cert.IsEapTrustedRoot && (
                                <div className={clsx(
                                    'p-3.5 rounded-xl border space-y-2',
                                    selectedCertDetail.cert.IsMissingFromStore
                                        ? 'bg-red-950/30 border-red-500/50'
                                        : 'bg-emerald-950/20 border-emerald-500/30'
                                )}>
                                    <div className="flex items-center justify-between">
                                        <span className="flex items-center gap-2 font-bold text-sm text-emerald-300">
                                            <ShieldCheck size={16} className="text-emerald-400" />
                                            <span>Autoridade Raiz Confiável Marcada na Política 802.1X</span>
                                        </span>
                                        {selectedCertDetail.cert.IsMissingFromStore ? (
                                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 border border-red-500/40 text-red-300 uppercase">
                                                NÃO INSTALADA NO HOST!
                                            </span>
                                        ) : (
                                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">
                                                Marcada no Perfil [✓]
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-xs text-zinc-300 space-y-1 pl-6">
                                        <div>• Perfil WLAN: <strong className="text-white font-mono">{selectedCertDetail.cert.EapProfileName}</strong></div>
                                        {selectedCertDetail.cert.EapConfigSummary && (
                                            <div>• Resumo da Política EAP: <strong className="text-zinc-200">{selectedCertDetail.cert.EapConfigSummary}</strong></div>
                                        )}
                                        {selectedCertDetail.cert.EapAuthMode && (
                                            <div>• Modo de Autenticação: <span className="font-mono text-amber-300">{selectedCertDetail.cert.EapAuthMode === 'machine' ? 'Credencial do Computador (Máquina)' : selectedCertDetail.cert.EapAuthMode}</span></div>
                                        )}
                                        {selectedCertDetail.cert.EapFastReconnect !== undefined && (
                                            <div>• Reconexão Rápida (Fast Reconnect): <strong className={selectedCertDetail.cert.EapFastReconnect ? 'text-emerald-400' : 'text-zinc-400'}>{selectedCertDetail.cert.EapFastReconnect ? 'Ativada (Sim)' : 'Desativada'}</strong></div>
                                        )}
                                        {selectedCertDetail.cert.EapDisablePrompt !== undefined && (
                                            <div>• Notificações de Autorização: <span className="text-zinc-300">{selectedCertDetail.cert.EapDisablePrompt ? 'Silencioso (Não pedir para autorizar novos servidores)' : 'Avisar usuário'}</span></div>
                                        )}
                                        {selectedCertDetail.cert.EapServerNames && (
                                            <div>• Validação de Servidor: <span className="font-mono text-zinc-300">{selectedCertDetail.cert.EapServerNames}</span></div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Titular (Subject DN Completo) */}
                            <div className="space-y-1.5">
                                <div className="flex items-center justify-between">
                                    <span className="font-semibold text-zinc-300">Titular Completo (Subject DN):</span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            navigator.clipboard.writeText(selectedCertDetail.cert.Subject);
                                            showToast('Titular copiado!', 'info');
                                        }}
                                        className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
                                    >
                                        <Copy size={12} />
                                        <span>Copiar</span>
                                    </button>
                                </div>
                                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-zinc-100 font-mono text-[11px] leading-relaxed break-words select-text">
                                    {selectedCertDetail.cert.Subject}
                                </div>
                            </div>

                            {/* Emissor (Issuer DN Completo) */}
                            <div className="space-y-1.5">
                                <div className="flex items-center justify-between">
                                    <span className="font-semibold text-zinc-300">Emissor Completo (Issuer DN):</span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            navigator.clipboard.writeText(selectedCertDetail.cert.Issuer);
                                            showToast('Emissor copiado!', 'info');
                                        }}
                                        className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
                                    >
                                        <Copy size={12} />
                                        <span>Copiar</span>
                                    </button>
                                </div>
                                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-zinc-300 font-mono text-[11px] leading-relaxed break-words select-text">
                                    {selectedCertDetail.cert.Issuer}
                                </div>
                            </div>

                            {/* Grid de Metadados e Criptografia */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 bg-zinc-950 p-3.5 rounded-xl border border-zinc-800">
                                <div>
                                    <span className="text-zinc-500 text-[11px]">Válido De: </span>
                                    <span className="text-zinc-200 font-mono text-[11px] block sm:inline">{selectedCertDetail.cert.NotBefore || 'N/A'}</span>
                                </div>
                                <div>
                                    <span className="text-zinc-500 text-[11px]">Válido Até: </span>
                                    <span className="text-zinc-200 font-mono text-[11px] block sm:inline">{selectedCertDetail.cert.NotAfter}</span>
                                </div>
                                <div>
                                    <span className="text-zinc-500 text-[11px]">Chave Privada: </span>
                                    <strong className={selectedCertDetail.cert.HasPrivateKey ? 'text-emerald-400' : 'text-zinc-400'}>
                                        {selectedCertDetail.cert.HasPrivateKey
                                            ? 'Sim (Chave Privada Presente)'
                                            : selectedCertDetail.cert.Store === 'LocalMachine\\My'
                                            ? 'Ausente (Falha de Autenticação)'
                                            : 'N/A (Autoridade Certificadora)'}
                                    </strong>
                                </div>
                                {selectedCertDetail.cert.FriendlyName && (
                                    <div>
                                        <span className="text-zinc-500 text-[11px]">Nome Amigável: </span>
                                        <span className="text-zinc-200 font-mono text-[11px]">{selectedCertDetail.cert.FriendlyName}</span>
                                    </div>
                                )}
                                {selectedCertDetail.cert.SerialNumber && (
                                    <div className="sm:col-span-2 flex items-center justify-between gap-1">
                                        <div>
                                            <span className="text-zinc-500 text-[11px]">Número de Série: </span>
                                            <span className="text-zinc-200 font-mono text-[11px] select-text">{selectedCertDetail.cert.SerialNumber}</span>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => {
                                                navigator.clipboard.writeText(selectedCertDetail.cert.SerialNumber || '');
                                                showToast('Serial copiado!', 'info');
                                            }}
                                            className="text-[11px] text-blue-400 hover:text-blue-300 shrink-0"
                                        >
                                            Copiar
                                        </button>
                                    </div>
                                )}
                            </div>

                            {/* Thumbprint / SHA-1 */}
                            <div className="space-y-1.5">
                                <div className="flex items-center justify-between">
                                    <span className="font-semibold text-zinc-400">Impressão Digital (Thumbprint SHA-1):</span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            navigator.clipboard.writeText(selectedCertDetail.cert.Thumbprint);
                                            showToast('Thumbprint copiado!', 'info');
                                        }}
                                        className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
                                    >
                                        <Copy size={12} />
                                        <span>Copiar Hash</span>
                                    </button>
                                </div>
                                <div className="bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-300 font-mono text-xs break-all select-text tracking-wider">
                                    {selectedCertDetail.cert.Thumbprint}
                                </div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between px-5 py-3 border-t border-zinc-800 bg-zinc-950/80">
                            <button
                                type="button"
                                onClick={() => copyCertFullText(selectedCertDetail.cert, selectedCertDetail.hostInput)}
                                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors"
                            >
                                <Copy size={13} />
                                <span>Copiar Todos os Dados</span>
                            </button>
                            <button
                                type="button"
                                onClick={() => setSelectedCertDetail(null)}
                                className="px-4 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
                            >
                                Fechar
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}