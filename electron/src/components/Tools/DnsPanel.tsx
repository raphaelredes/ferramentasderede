import { useState, useMemo } from 'react';
import {
    Search, Globe, Server, CheckCircle2, AlertTriangle, XCircle,
    Copy, Check, Zap, BarChart3, Terminal, ShieldCheck,
    ArrowRight, Info, ShieldAlert, Layers, Clock
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

// Tipos suportados na interface
type DnsRecordType = 'AUTO' | 'ALL' | 'A' | 'AAAA' | 'CNAME' | 'MX' | 'TXT' | 'NS' | 'SOA' | 'PTR' | 'SRV' | 'CAA';

interface DnsRecordItem {
    name: string;
    type: string;
    ttl: number;
    ttl_formatted: string;
    raw_data: string;
    address?: string;
    target?: string;
    priority?: number;
    weight?: number;
    port?: number;
    text?: string;
    nameserver?: string;
    ptr_name?: string;
    mname?: string;
    serial?: number;
}

interface DnsInsight {
    type: 'success' | 'info' | 'warning' | 'error_critical';
    title: string;
    message: string;
}

interface DnsQueryResult {
    ok: boolean;
    target: string;
    record_type: string;
    server_used: string;
    server_ip: string;
    is_system_resolver: boolean;
    rcode: string;
    rcode_description: string;
    flags: string[];
    query_time_ms: number;
    answer_count: number;
    answers: DnsRecordItem[];
    authorities?: Array<{ name: string; type: string; ttl_formatted: string; data: string }>;
    raw_dig?: string;
    error?: string;
    // Campos caso venha de /diagnose
    mode?: 'domain_complete' | 'ip_reverse';
    records?: DnsRecordItem[];
    insights?: DnsInsight[];
    primary_result?: any;
    public_comparison?: any;
}

interface BenchmarkItem {
    id: string;
    name: string;
    ip: string;
    type: 'local' | 'public' | 'corporate';
    ok: boolean;
    rcode: string;
    rcode_description?: string;
    query_time_ms: number;
    flags: string[];
    answer_count: number;
    answers_summary: string[];
    error?: string;
}

interface BenchmarkResult {
    ok: boolean;
    target: string;
    record_type: string;
    benchmarks: BenchmarkItem[];
    divergence_detected: boolean;
    status_distribution: Record<string, number>;
}

const PUBLIC_PRESETS = [
    { label: 'Google DNS (8.8.8.8)', ip: '8.8.8.8' },
    { label: 'Cloudflare DNS (1.1.1.1)', ip: '1.1.1.1' },
    { label: 'Quad9 DNS (9.9.9.9)', ip: '9.9.9.9' },
    { label: 'OpenDNS (208.67.222.222)', ip: '208.67.222.222' },
];

export function DnsPanel() {
    const { showToast } = useToast();
    const { networks } = useNetworks();

    // Estados persistidos
    const [query, setQuery] = usePersistedState('dns_tool_query_v2', '');
    const [recordType, setRecordType] = usePersistedState<DnsRecordType>('dns_tool_record_type', 'AUTO');
    const [dnsServer, setDnsServer] = usePersistedState('dns_tool_server_v2', ''); // '' = system resolver
    const [customServerIp, setCustomServerIp] = usePersistedState('dns_tool_custom_ip', '');
    const [activeTab, setActiveTab] = usePersistedState<'records' | 'benchmark' | 'raw'>('dns_tool_view_tab', 'records');

    const [lastResult, setLastResult] = usePersistedState<DnsQueryResult | null>('dns_tool_last_res_v2', null);
    const [benchmarkResult, setBenchmarkResult] = usePersistedState<BenchmarkResult | null>('dns_tool_bench_res', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('dns_tool_last_run_v2', null);

    // Estados locais da sessão
    const [busy, setBusy] = useState(false);
    const [busyAction, setBusyAction] = useState<'query' | 'benchmark' | null>(null);
    const [copiedRaw, setCopiedRaw] = useState(false);
    const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

    // Redes corporativas cadastradas que possuem DNS configurado
    const dnsNetworks = networks.filter(n => n.dns_server);

    // Servidor DNS efetivo a ser enviado
    const effectiveDnsServer = useMemo(() => {
        if (dnsServer === '__custom__') return customServerIp.trim();
        return dnsServer.trim() || undefined;
    }, [dnsServer, customServerIp]);

    // Detecção se o alvo aparenta ser IP (para dicas e roteamento)
    const looksLikeIp = (s: string) => {
        const v = s.trim();
        if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(v)) return true;
        return v.includes(':') && /^[0-9a-fA-F:]+$/.test(v);
    };

    // Executa a consulta DNS (Simples ou Diagnóstico Completo)
    const handleResolve = async () => {
        const q = query.trim();
        if (!q) {
            showToast('Informe um hostname ou endereço IP.', 'error');
            return;
        }

        if (dnsServer === '__custom__' && !customServerIp.trim()) {
            showToast('Informe o endereço IP do servidor DNS personalizado.', 'error');
            return;
        }

        setBusy(true);
        setBusyAction('query');

        try {
            const isAllMode = recordType === 'ALL';
            const endpoint = isAllMode ? `${API_BASE}/network/dns/diagnose` : `${API_BASE}/network/dns/query`;
            const payload: any = {
                target: q,
                dns_server: effectiveDnsServer,
            };
            if (!isAllMode) {
                payload.record_type = recordType;
            }

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || `HTTP ${res.status}`);
            }

            setLastResult(data);
            setLastRunAt(new Date().toISOString());

            // Notificação situacional baseada no RCODE
            const rcode = data.rcode || (data.primary_result && data.primary_result.rcode);
            if (rcode === 'NOERROR') {
                showToast(`DNS: Resposta NOERROR recebida em ${data.query_time_ms || data.primary_result?.query_time_ms || 0}ms`, 'success');
            } else if (rcode === 'NXDOMAIN') {
                showToast('DNS: Domínio ou registro inexistente (NXDOMAIN).', 'info');
            } else if (rcode === 'SERVFAIL') {
                showToast('DNS: Servidor retornou SERVFAIL (falha de forwarder ou DNSSEC).', 'error');
            } else if (rcode === 'TIMEOUT') {
                showToast('DNS: Tempo limite esgotado ao consultar o servidor.', 'error');
            } else if (rcode) {
                showToast(`DNS: Status ${rcode}`, 'info');
            }
        } catch (e: any) {
            showToast('Erro na consulta DNS: ' + e.message, 'error');
        } finally {
            setBusy(false);
            setBusyAction(null);
        }
    };

    // Executa o benchmark multi-provedor
    const handleBenchmark = async () => {
        const q = query.trim();
        if (!q) {
            showToast('Informe um hostname ou IP para o benchmark.', 'error');
            return;
        }

        setBusy(true);
        setBusyAction('benchmark');

        try {
            // Repassa servidores de redes AD como extras
            const extraServers = dnsNetworks.map(n => ({
                ip: n.dns_server,
                name: n.name || n.cidr,
            }));

            const targetRecord = recordType === 'ALL' || recordType === 'AUTO' ? 'A' : recordType;

            const res = await fetch(`${API_BASE}/network/dns/benchmark`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target: q,
                    record_type: targetRecord,
                    extra_servers: extraServers,
                }),
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || `HTTP ${res.status}`);
            }

            setBenchmarkResult(data);
            setActiveTab('benchmark');
            setLastRunAt(new Date().toISOString());

            if (data.divergence_detected) {
                showToast('Benchmark concluído: Divergências detectadas entre provedores!', 'info');
            } else {
                showToast('Benchmark concluído: Todos os provedores retornaram respostas consistentes.', 'success');
            }
        } catch (e: any) {
            showToast('Erro no benchmark: ' + e.message, 'error');
        } finally {
            setBusy(false);
            setBusyAction(null);
        }
    };

    const handleCopy = (text: string, index?: number) => {
        navigator.clipboard.writeText(text);
        if (index !== undefined) {
            setCopiedIndex(index);
            setTimeout(() => setCopiedIndex(null), 2000);
        } else {
            setCopiedRaw(true);
            setTimeout(() => setCopiedRaw(false), 2000);
        }
        showToast('Copiado para a área de transferência!', 'success');
    };

    const handleClearAll = () => {
        setLastResult(null);
        setBenchmarkResult(null);
        setLastRunAt(null);
        showToast('Resultados de DNS limpos com sucesso.', 'info');
    };

    // Badges de Status RCODE
    const renderRcodeBadge = (rcode: string) => {
        switch (rcode) {
            case 'NOERROR':
                return (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        <CheckCircle2 size={13} /> NOERROR
                    </span>
                );
            case 'NXDOMAIN':
                return (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        <AlertTriangle size={13} /> NXDOMAIN (Inexistente)
                    </span>
                );
            case 'SERVFAIL':
                return (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/40">
                        <XCircle size={13} /> SERVFAIL (Falha Servidor)
                    </span>
                );
            case 'TIMEOUT':
                return (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/40">
                        <Clock size={13} /> TIMEOUT (Sem Resposta)
                    </span>
                );
            case 'REFUSED':
                return (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/30">
                        <XCircle size={13} /> REFUSED (Recusado)
                    </span>
                );
            default:
                return (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
                        {rcode || 'UNKNOWN'}
                    </span>
                );
        }
    };

    // Cores de badge por tipo de registro DNS
    const getRecordTypeBadge = (type: string) => {
        switch (type) {
            case 'A': return 'bg-sky-500/10 text-sky-400 border-sky-500/30';
            case 'AAAA': return 'bg-purple-500/10 text-purple-400 border-purple-500/30';
            case 'MX': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
            case 'TXT': return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
            case 'NS': return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30';
            case 'SOA': return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
            case 'CNAME': return 'bg-teal-500/10 text-teal-400 border-teal-500/30';
            case 'PTR': return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
            case 'SRV': return 'bg-pink-500/10 text-pink-400 border-pink-500/30';
            default: return 'bg-zinc-800 text-zinc-300 border-zinc-700';
        }
    };

    // Indicador de velocidade de latência (ms)
    const getLatencyColor = (ms: number) => {
        if (ms <= 50) return 'text-emerald-400';
        if (ms <= 150) return 'text-amber-400';
        return 'text-rose-400';
    };

    // Registros consolidados para exibição
    const recordsToDisplay: DnsRecordItem[] = useMemo(() => {
        if (!lastResult) return [];
        if (lastResult.records && lastResult.records.length > 0) {
            return lastResult.records;
        }
        return lastResult.answers || [];
    }, [lastResult]);

    // Resultado principal para o cabeçalho
    const primaryInfo = useMemo(() => {
        if (!lastResult) return null;
        if (lastResult.primary_result) {
            return {
                rcode: lastResult.primary_result.rcode || lastResult.rcode || 'NOERROR',
                rcode_desc: lastResult.primary_result.rcode_description || lastResult.rcode_description,
                server: lastResult.primary_result.server_used || lastResult.server_used,
                query_time_ms: lastResult.primary_result.query_time_ms ?? lastResult.query_time_ms ?? 0,
                flags: lastResult.primary_result.flags || lastResult.flags || [],
                raw_dig: lastResult.primary_result.raw_dig || lastResult.raw_dig,
            };
        }
        return {
            rcode: lastResult.rcode || 'NOERROR',
            rcode_desc: lastResult.rcode_description,
            server: lastResult.server_used,
            query_time_ms: lastResult.query_time_ms ?? 0,
            flags: lastResult.flags || [],
            raw_dig: lastResult.raw_dig,
        };
    }, [lastResult]);

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Bloco de Controles e Configuração de Consulta */}
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-3 shrink-0">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                    {/* Alvo: Hostname ou IP */}
                    <div className="md:col-span-5 space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center justify-between">
                            <span>Hostname ou IP</span>
                            {query && looksLikeIp(query) && (
                                <span className="text-[10px] text-blue-400 font-mono font-normal">Detectado: Endereço IP</span>
                            )}
                        </label>
                        <div className="relative">
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder="ex: google.com, cloudflare.com ou 1.1.1.1"
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500"
                                onKeyDown={(e) => { if (e.key === 'Enter' && !busy) handleResolve(); }}
                            />
                        </div>
                    </div>

                    {/* Tipo de Registro */}
                    <div className="md:col-span-3 space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Tipo de Registro
                        </label>
                        <select
                            value={recordType}
                            onChange={(e) => setRecordType(e.target.value as DnsRecordType)}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                        >
                            <option value="AUTO">AUTO (Inteligente: Direto/PTR)</option>
                            <option value="ALL">TODOS (Diagnóstico Completo)</option>
                            <option value="A">A (Endereço IPv4)</option>
                            <option value="AAAA">AAAA (Endereço IPv6)</option>
                            <option value="CNAME">CNAME (Alias Canônico)</option>
                            <option value="MX">MX (Servidores de Correio)</option>
                            <option value="TXT">TXT (SPF, DMARC, Validações)</option>
                            <option value="NS">NS (Servidores de Nome)</option>
                            <option value="SOA">SOA (Zona & Autoridade)</option>
                            <option value="PTR">PTR (Resolução Reversa)</option>
                            <option value="SRV">SRV (Localização de Serviços)</option>
                            <option value="CAA">CAA (Certificados TLS)</option>
                        </select>
                    </div>

                    {/* Servidor DNS */}
                    <div className="md:col-span-4 space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Servidor DNS Resolver
                        </label>
                        <select
                            value={dnsServer}
                            onChange={(e) => setDnsServer(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                        >
                            <option value="">Resolver do Sistema (Padrão Local)</option>
                            <optgroup label="Provedores Públicos Globais">
                                {PUBLIC_PRESETS.map(p => (
                                    <option key={p.ip} value={p.ip}>{p.label}</option>
                                ))}
                            </optgroup>
                            {dnsNetworks.length > 0 && (
                                <optgroup label="Redes / VLANs Corporativas">
                                    {dnsNetworks.map(net => (
                                        <option key={net.id} value={net.dns_server ?? ''}>
                                            {net.name || net.cidr} — {net.dns_server}
                                        </option>
                                    ))}
                                </optgroup>
                            )}
                            <option value="__custom__">Outro Servidor (IP Personalizado)...</option>
                        </select>
                    </div>
                </div>

                {/* Campo adicional caso escolha IP customizado */}
                {dnsServer === '__custom__' && (
                    <div className="flex items-center gap-3 bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800">
                        <Server size={15} className="text-blue-400 shrink-0" />
                        <label className="text-xs text-zinc-400 whitespace-nowrap">IP do Servidor DNS:</label>
                        <input
                            type="text"
                            value={customServerIp}
                            onChange={(e) => setCustomServerIp(e.target.value)}
                            placeholder="ex: 10.0.0.1 ou 1.1.1.1"
                            className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
                        />
                    </div>
                )}

                {/* Botões de Ação */}
                <div className="flex items-center justify-between pt-1 border-t border-zinc-800/80">
                    <p className="text-xs text-zinc-500">
                        Padrão RFC 1035/8499 com fallback TCP automático e diagnóstico de falha de forwarder.
                    </p>

                    <div className="flex items-center gap-2.5">
                        <button
                            onClick={handleBenchmark}
                            disabled={busy}
                            title="Compara o tempo de resposta e resolução entre o resolvedor local e provedores mundiais (Google, Cloudflare, Quad9)"
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-zinc-800 hover:bg-zinc-700 text-sky-300 border border-sky-900/40 hover:border-sky-500/50 transition-all disabled:opacity-50"
                        >
                            <BarChart3 size={15} className={busyAction === 'benchmark' ? 'animate-pulse' : ''} />
                            <span>{busyAction === 'benchmark' ? 'Comparando Provedores...' : 'Comparar Provedores (Benchmark)'}</span>
                        </button>

                        <button
                            onClick={handleResolve}
                            disabled={busy}
                            className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20 hover:shadow-blue-600/30 transition-all disabled:opacity-50"
                        >
                            <Search size={16} className={busyAction === 'query' ? 'animate-spin' : ''} />
                            <span>{busyAction === 'query' ? 'Resolvendo DNS...' : (recordType === 'ALL' ? 'Diagnosticar Domínio' : 'Consultar DNS')}</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Badge de Última Execução e Botão Limpar */}
            {(lastResult || benchmarkResult) && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={lastResult?.target || benchmarkResult?.target}
                    onClear={handleClearAll}
                />
            )}

            {/* Painel Principal de Resultados */}
            <div className="flex-1 bg-zinc-950 rounded-xl border border-zinc-800 overflow-hidden flex flex-col min-h-0">
                {/* Cabeçalho de Execução: Badges de Métricas (quando há resultado) */}
                {primaryInfo && (
                    <div className="bg-zinc-900/90 border-b border-zinc-800 px-4 py-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
                        <div className="flex items-center gap-3 flex-wrap">
                            {renderRcodeBadge(primaryInfo.rcode)}

                            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-zinc-900 border border-zinc-800">
                                <Zap size={13} className={getLatencyColor(primaryInfo.query_time_ms)} />
                                <span className="text-zinc-400">Tempo:</span>
                                <span className={clsx('font-mono font-semibold', getLatencyColor(primaryInfo.query_time_ms))}>
                                    {primaryInfo.query_time_ms} ms
                                </span>
                            </div>

                            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-zinc-900 border border-zinc-800">
                                <Server size={13} className="text-blue-400" />
                                <span className="text-zinc-400">Servidor:</span>
                                <span className="text-zinc-200 font-mono font-medium">{primaryInfo.server || 'Padrão'}</span>
                            </div>

                            {/* Flags DNS */}
                            {primaryInfo.flags.length > 0 && (
                                <div className="flex items-center gap-1">
                                    {primaryInfo.flags.map((flag: string) => (
                                        <span
                                            key={flag}
                                            title={
                                                flag === 'AA' ? 'Authoritative Answer (Resposta Autoritativa)' :
                                                flag === 'RD' ? 'Recursion Desired (Recursão Solicitada)' :
                                                flag === 'RA' ? 'Recursion Available (Recursão Disponível no Servidor)' :
                                                flag === 'AD' ? 'Authentic Data (DNSSEC Validado)' : flag
                                            }
                                            className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-zinc-800 text-zinc-300 border border-zinc-700"
                                        >
                                            {flag}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Seletor de Abas de Visualização */}
                        <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800 text-xs">
                            <button
                                onClick={() => setActiveTab('records')}
                                className={clsx(
                                    'flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-colors',
                                    activeTab === 'records' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-white'
                                )}
                            >
                                <Layers size={13} />
                                <span>Registros & Diagnóstico</span>
                                {recordsToDisplay.length > 0 && (
                                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-black/40 font-mono">
                                        {recordsToDisplay.length}
                                    </span>
                                )}
                            </button>

                            <button
                                onClick={() => setActiveTab('benchmark')}
                                className={clsx(
                                    'flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-colors',
                                    activeTab === 'benchmark' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-white'
                                )}
                            >
                                <BarChart3 size={13} />
                                <span>Comparativo Multi-DNS</span>
                                {benchmarkResult && (
                                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                                )}
                            </button>

                            <button
                                onClick={() => setActiveTab('raw')}
                                className={clsx(
                                    'flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-colors',
                                    activeTab === 'raw' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-white'
                                )}
                            >
                                <Terminal size={13} />
                                <span>Saída Raw (DiG)</span>
                            </button>
                        </div>
                    </div>
                )}

                {/* Conteúdo da Área de Visualização */}
                <div className="flex-1 overflow-auto custom-scrollbar p-4">
                    {busy ? (
                        <div className="h-full flex flex-col items-center justify-center space-y-4 text-zinc-400">
                            <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                            <div className="text-center space-y-1">
                                <p className="text-sm font-medium text-white">
                                    {busyAction === 'benchmark' ? 'Executando benchmark cruzado em múltiplos resolvedores...' : 'Consultando registros DNS nos servidores...'}
                                </p>
                                <p className="text-xs text-zinc-500 font-mono">
                                    Alvo: {query} · Servidor: {effectiveDnsServer || 'Resolvedor Local do Sistema'}
                                </p>
                            </div>
                        </div>
                    ) : !lastResult && !benchmarkResult ? (
                        <div className="h-full flex flex-col items-center justify-center text-zinc-600 space-y-3">
                            <Globe size={48} className="opacity-20 animate-pulse" />
                            <div className="text-center max-w-sm space-y-1">
                                <p className="text-sm font-medium text-zinc-400">Nenhuma consulta realizada</p>
                                <p className="text-xs text-zinc-600">
                                    Digite um hostname ou IP acima para inspecionar registros DNS, verificar a integridade de domínios ou comparar provedores mundiais.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <>
                            {/* ABA 1: REGISTROS & DIAGNÓSTICO */}
                            {activeTab === 'records' && (
                                <div className="space-y-4">
                                    {/* Alertas e Insights de Diagnóstico Inteligente */}
                                    {lastResult?.insights && lastResult.insights.length > 0 && (
                                        <div className="space-y-2">
                                            {lastResult.insights.map((insight, idx) => (
                                                <div
                                                    key={idx}
                                                    className={clsx(
                                                        'p-3 rounded-lg border flex gap-3 text-xs leading-relaxed',
                                                        insight.type === 'error_critical' && 'bg-rose-500/10 border-rose-500/30 text-rose-300',
                                                        insight.type === 'warning' && 'bg-amber-500/10 border-amber-500/30 text-amber-300',
                                                        insight.type === 'success' && 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
                                                        insight.type === 'info' && 'bg-blue-500/10 border-blue-500/30 text-blue-300'
                                                    )}
                                                >
                                                    <div className="shrink-0 mt-0.5">
                                                        {insight.type === 'error_critical' && <ShieldAlert size={16} className="text-rose-400" />}
                                                        {insight.type === 'warning' && <AlertTriangle size={16} className="text-amber-400" />}
                                                        {insight.type === 'success' && <ShieldCheck size={16} className="text-emerald-400" />}
                                                        {insight.type === 'info' && <Info size={16} className="text-blue-400" />}
                                                    </div>
                                                    <div>
                                                        <strong className="font-semibold block mb-0.5 text-white">{insight.title}</strong>
                                                        {insight.message}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {/* Aviso explicativo se o RCODE for diferente de NOERROR */}
                                    {primaryInfo && primaryInfo.rcode !== 'NOERROR' && (
                                        <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-300 flex items-start gap-2.5">
                                            <Info size={16} className="text-amber-400 shrink-0 mt-0.5" />
                                            <div>
                                                <span className="font-semibold text-white mr-1.5">{primaryInfo.rcode}:</span>
                                                {primaryInfo.rcode_desc}
                                            </div>
                                        </div>
                                    )}

                                    {/* Tabela Estruturada de Registros DNS */}
                                    {recordsToDisplay.length > 0 ? (
                                        <div className="border border-zinc-800 rounded-lg overflow-hidden">
                                            <div className="bg-zinc-900/60 px-4 py-2 border-b border-zinc-800 flex items-center justify-between text-xs text-zinc-400 font-medium">
                                                <span>Registros Retornados na Resposta ({recordsToDisplay.length})</span>
                                                <span>TTL & Prioridade</span>
                                            </div>

                                            <div className="divide-y divide-zinc-900">
                                                {recordsToDisplay.map((rec, i) => (
                                                    <div
                                                        key={i}
                                                        className="px-4 py-2.5 hover:bg-zinc-900/40 transition-colors flex items-center gap-3 font-mono text-xs"
                                                    >
                                                        {/* Badge do Tipo */}
                                                        <span className={clsx(
                                                            'px-2 py-0.5 rounded text-[11px] font-bold border shrink-0 text-center min-w-16',
                                                            getRecordTypeBadge(rec.type)
                                                        )}>
                                                            {rec.type}
                                                        </span>

                                                        {/* Nome da Zona */}
                                                        <span className="text-zinc-400 max-w-48 truncate shrink-0" title={rec.name}>
                                                            {rec.name}
                                                        </span>

                                                        <ArrowRight size={13} className="text-zinc-700 shrink-0" />

                                                        {/* Valor / Dados do Registro */}
                                                        <div className="flex-1 truncate text-zinc-200">
                                                            {rec.address ? (
                                                                <span className="text-sky-400 font-semibold">{rec.address}</span>
                                                            ) : rec.target ? (
                                                                <span>
                                                                    {rec.priority !== undefined && (
                                                                        <span className="text-amber-400 mr-2 font-bold">[Pref: {rec.priority}]</span>
                                                                    )}
                                                                    <span className="text-emerald-400">{rec.target}</span>
                                                                </span>
                                                            ) : rec.text ? (
                                                                <span className="text-amber-200/90 break-all">{rec.text}</span>
                                                            ) : rec.ptr_name ? (
                                                                <span className="text-blue-300 font-semibold">{rec.ptr_name}</span>
                                                            ) : rec.nameserver ? (
                                                                <span className="text-indigo-300">{rec.nameserver}</span>
                                                            ) : (
                                                                <span className="text-zinc-300">{rec.raw_data}</span>
                                                            )}
                                                        </div>

                                                        {/* TTL */}
                                                        <div className="text-right shrink-0 text-zinc-500 text-[11px] ml-2">
                                                            <span title={`TTL: ${rec.ttl} segundos`}>{rec.ttl_formatted}</span>
                                                        </div>

                                                        {/* Botão Copiar Linha */}
                                                        <button
                                                            onClick={() => handleCopy(rec.address || rec.target || rec.text || rec.raw_data, i)}
                                                            className="p-1 rounded text-zinc-600 hover:text-zinc-200 transition-colors shrink-0 ml-1"
                                                            title="Copiar valor"
                                                        >
                                                            {copiedIndex === i ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-center py-8 text-zinc-500 text-xs border border-dashed border-zinc-800 rounded-lg">
                                            Nenhum registro retornado na seção ANSWER para a consulta solicitada.
                                        </div>
                                    )}

                                    {/* Seção Authority (Nameservers da Zona) se disponível */}
                                    {lastResult?.authorities && lastResult.authorities.length > 0 && (
                                        <div className="border border-zinc-800/80 rounded-lg overflow-hidden mt-3">
                                            <div className="bg-zinc-900/40 px-4 py-2 border-b border-zinc-800/80 text-xs text-zinc-500 font-medium">
                                                Autoridade / Nameservers da Zona (AUTHORITY SECTION)
                                            </div>
                                            <div className="divide-y divide-zinc-900">
                                                {lastResult.authorities.map((auth, idx) => (
                                                    <div key={idx} className="px-4 py-2 text-xs font-mono flex items-center justify-between text-zinc-400">
                                                        <span>{auth.name}</span>
                                                        <span className="text-indigo-400">{auth.data}</span>
                                                        <span className="text-zinc-600 text-[11px]">{auth.ttl_formatted}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ABA 2: COMPARATIVO MULTI-DNS (BENCHMARK) */}
                            {activeTab === 'benchmark' && (
                                <div className="space-y-4">
                                    {benchmarkResult ? (
                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                                    <span>Comparação de Resolução e Latência</span>
                                                    {benchmarkResult.divergence_detected ? (
                                                        <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                                            Divergências Detectadas
                                                        </span>
                                                    ) : (
                                                        <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                                            Consenso entre Provedores
                                                        </span>
                                                    )}
                                                </h4>
                                                <span className="text-xs text-zinc-500 font-mono">
                                                    Alvo: {benchmarkResult.target} ({benchmarkResult.record_type})
                                                </span>
                                            </div>

                                            <div className="border border-zinc-800 rounded-lg overflow-hidden">
                                                <table className="w-full text-left text-xs">
                                                    <thead className="bg-zinc-900/80 border-b border-zinc-800 text-zinc-400">
                                                        <tr>
                                                            <th className="px-4 py-2.5 font-semibold">Provedor DNS</th>
                                                            <th className="px-3 py-2.5 font-semibold">Status</th>
                                                            <th className="px-3 py-2.5 font-semibold">Latência</th>
                                                            <th className="px-4 py-2.5 font-semibold">Resposta Obtida</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-zinc-900 font-mono">
                                                        {benchmarkResult.benchmarks.map((bench) => {
                                                            const isSystem = bench.id === 'system';
                                                            return (
                                                                <tr
                                                                    key={bench.id}
                                                                    className={clsx(
                                                                        'hover:bg-zinc-900/30 transition-colors',
                                                                        isSystem && 'bg-blue-950/20'
                                                                    )}
                                                                >
                                                                    <td className="px-4 py-2.5 font-sans">
                                                                        <div className="font-medium text-white flex items-center gap-1.5">
                                                                            {bench.name}
                                                                            {isSystem && (
                                                                                <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                                                                    LOCAL
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                        <div className="text-[11px] text-zinc-500 font-mono">{bench.ip}</div>
                                                                    </td>
                                                                    <td className="px-3 py-2.5">
                                                                        {renderRcodeBadge(bench.rcode)}
                                                                    </td>
                                                                    <td className="px-3 py-2.5">
                                                                        <span className={clsx('font-bold', getLatencyColor(bench.query_time_ms))}>
                                                                            {bench.query_time_ms} ms
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-4 py-2.5 text-zinc-300">
                                                                        {bench.answers_summary.length > 0 ? (
                                                                            <span className="text-sky-400 font-semibold">
                                                                                {bench.answers_summary.join(', ')}
                                                                            </span>
                                                                        ) : (
                                                                            <span className="text-zinc-600 italic">Nenhum registro retornado</span>
                                                                        )}
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-center py-10 space-y-3">
                                            <BarChart3 size={36} className="mx-auto text-zinc-600 opacity-40" />
                                            <p className="text-xs text-zinc-400">
                                                Clique no botão <strong>"Comparar Provedores (Benchmark)"</strong> acima para realizar a análise simultânea entre seu resolvedor e os maiores provedores globais.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ABA 3: SAÍDA RAW NO PADRÃO ISC BIND DIG */}
                            {activeTab === 'raw' && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs font-medium text-zinc-400">
                                            Saída Canônica RFC (ISC BIND DiG format)
                                        </span>
                                        <button
                                            onClick={() => handleCopy(primaryInfo?.raw_dig || '')}
                                            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 text-xs transition-colors"
                                        >
                                            {copiedRaw ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                                            <span>{copiedRaw ? 'Copiado!' : 'Copiar Saída Raw'}</span>
                                        </button>
                                    </div>

                                    <pre className="p-4 bg-black rounded-lg border border-zinc-800 text-zinc-300 font-mono text-xs overflow-x-auto custom-scrollbar leading-relaxed">
                                        {primaryInfo?.raw_dig || ';; Nenhuma saída de comando dig gerada.'}
                                    </pre>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
