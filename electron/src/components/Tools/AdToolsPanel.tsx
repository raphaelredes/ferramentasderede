import { useState } from 'react';
import {
    Clock,
    Server,
    Play,
    Crown,
    RefreshCw,
    Activity,
    Layers
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface ADPortResult {
    port: number;
    proto: string;
    service: string;
    desc: string;
    open: boolean;
    latency_ms?: number;
    error?: string;
}

interface ADSRVTarget {
    target: string;
    port: number;
    priority: number;
    weight: number;
    ips: string[];
}

interface ADSRVResult {
    record: string;
    desc: string;
    found: boolean;
    targets: ADSRVTarget[];
    error?: string;
}

interface FSMORoleItem {
    role: string;
    desc: string;
    holder: string | null;
}

interface FSMOResult {
    ok: boolean;
    domain?: string;
    roles?: Record<string, string | null>;
    role_list?: FSMORoleItem[];
    raw_output?: string;
    error?: string;
}

interface ReplicationPartner {
    dsa: string;
    largest_delta: string;
    fails: number;
    total: number;
    percent_fails: number;
    status: 'HEALTHY' | 'FAILING';
}

interface ReplicationResult {
    ok: boolean;
    dc_target?: string;
    total_fails: number;
    status: 'HEALTHY' | 'WARNING';
    sources: ReplicationPartner[];
    destinations: ReplicationPartner[];
    raw_output?: string;
    error?: string;
}

export function AdToolsPanel({ defaultSourceIp }: { defaultSourceIp?: string }) {
    const { showToast } = useToast();
    const [subTab, setSubTab] = usePersistedState<'ports' | 'srv' | 'skew' | 'fsmo'>('ad_tool_subtab_v2', 'ports');
    const [loading, setLoading] = useState(false);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('ad_tool_last_run_v2', null);

    // Port Matrix State
    const [dcTarget, setDcTarget] = usePersistedState('ad_tool_dc_target', 'dc01.corp.local');
    const [portResults, setPortResults, clearPortResults] = usePersistedState<ADPortResult[]>('ad_tool_port_results', []);
    const [portSummary, setPortSummary] = usePersistedState<{ total: number; open: number; status: string } | null>('ad_tool_port_summary', null);

    // SRV Records State
    const [domainTarget, setDomainTarget] = usePersistedState('ad_tool_domain_target', 'corp.local');
    const [customDns, setCustomDns] = usePersistedState('ad_tool_custom_dns', '');
    const [srvResults, setSrvResults, clearSrvResults] = usePersistedState<ADSRVResult[]>('ad_tool_srv_results', []);

    // Time Skew State
    const [skewTarget, setSkewTarget] = usePersistedState('ad_tool_skew_target', 'dc01.corp.local');
    const [skewResult, setSkewResult, clearSkewResult] = usePersistedState<any>('ad_tool_skew_result', null);

    // FSMO & Replication State
    const [fsmoDomain, setFsmoDomain] = usePersistedState('ad_tool_fsmo_domain', '');
    const [fsmoResult, setFsmoResult, clearFsmoResult] = usePersistedState<FSMOResult | null>('ad_tool_fsmo_res', null);
    const [replResult, setReplResult, clearReplResult] = usePersistedState<ReplicationResult | null>('ad_tool_repl_res', null);

    const runPortTest = async () => {
        if (!dcTarget.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/ad/test-ports`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: dcTarget.trim(), source_ip: defaultSourceIp || null, timeout: 2.0 })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setPortResults(data.results || []);
            setPortSummary({ total: data.total_ports, open: data.open_ports, status: data.status });
            setLastRunAt(new Date().toISOString());
            showToast('Matriz de portas AD concluída!', 'success');
        } catch (err: any) {
            showToast(`Erro ao testar portas AD: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const runSrvTest = async () => {
        if (!domainTarget.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/ad/test-srv`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain: domainTarget.trim(), dns_server: customDns.trim() || null })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setSrvResults(data.results || []);
            setLastRunAt(new Date().toISOString());
            showToast(`Consulta SRV concluída: ${data.found_count}/${data.total_queries} resolvidos`, 'success');
        } catch (err: any) {
            showToast(`Erro ao consultar registros SRV: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const runSkewTest = async () => {
        if (!skewTarget.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/ad/check-skew`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: skewTarget.trim(), source_ip: defaultSourceIp || null })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setSkewResult(data);
            setLastRunAt(new Date().toISOString());
            if (data.status === 'HEALTHY') {
                showToast(`Desvio de tempo aceitável (${data.offset_ms}ms)`, 'success');
            } else {
                showToast(`Atenção: desvio de relógio detectado (${data.offset_ms}ms)`, 'error');
            }
        } catch (err: any) {
            showToast(`Erro ao checar time skew: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const runFsmoDiscovery = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/ad/fsmo`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain: fsmoDomain.trim() || null })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setFsmoResult(data);
            setLastRunAt(new Date().toISOString());
            showToast('Funções FSMO descobertas com sucesso!', 'success');
        } catch (err: any) {
            showToast(`Erro ao consultar FSMO: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const runReplicationCheck = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/ad/replication`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dc_target: fsmoDomain.trim() || null })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setReplResult(data);
            setLastRunAt(new Date().toISOString());
            if (data.status === 'HEALTHY') {
                showToast('Replicação do Active Directory 100% íntegra!', 'success');
            } else {
                showToast(`Atenção: ${data.total_fails} falhas de replicação detectadas`, 'error');
            }
        } catch (err: any) {
            showToast(`Erro ao checar replicação: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Navegação entre Sub-abas */}
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-2 shrink-0">
                <button
                    onClick={() => setSubTab('ports')}
                    className={clsx(
                        "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5",
                        subTab === 'ports'
                            ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                            : "text-zinc-400 hover:text-zinc-200"
                    )}
                >
                    <Server size={14} />
                    <span>Matriz de Portas DC</span>
                </button>
                <button
                    onClick={() => setSubTab('srv')}
                    className={clsx(
                        "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5",
                        subTab === 'srv'
                            ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                            : "text-zinc-400 hover:text-zinc-200"
                    )}
                >
                    <Layers size={14} />
                    <span>Registros DNS SRV</span>
                </button>
                <button
                    onClick={() => setSubTab('skew')}
                    className={clsx(
                        "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5",
                        subTab === 'skew'
                            ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                            : "text-zinc-400 hover:text-zinc-200"
                    )}
                >
                    <Clock size={14} />
                    <span>Desvio Kerberos (Skew)</span>
                </button>
                <button
                    onClick={() => setSubTab('fsmo')}
                    className={clsx(
                        "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5",
                        subTab === 'fsmo'
                            ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                            : "text-zinc-400 hover:text-zinc-200"
                    )}
                >
                    <Crown size={14} />
                    <span>FSMO & Replicação</span>
                </button>
            </div>

            {/* Badge de Última Execução */}
            {lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={subTab === 'ports' ? dcTarget : subTab === 'srv' ? domainTarget : subTab === 'skew' ? skewTarget : fsmoDomain || 'Domínio Atual'}
                    onClear={() => {
                        clearPortResults();
                        clearSrvResults();
                        clearSkewResult();
                        clearFsmoResult();
                        clearReplResult();
                        setLastRunAt(null);
                    }}
                />
            )}

            {/* Conteúdo da Sub-aba: Portas */}
            {subTab === 'ports' && (
                <div className="flex-1 flex flex-col space-y-3 min-h-0">
                    <div className="flex flex-wrap items-center gap-3 bg-zinc-900 p-3.5 rounded-xl border border-zinc-800 shrink-0">
                        <input
                            type="text"
                            placeholder="IP ou FQDN do DC (ex: dc01.corp.local)"
                            value={dcTarget}
                            onChange={e => setDcTarget(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter' && !loading) runPortTest(); }}
                            className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[220px] focus:outline-none focus:border-blue-500 font-mono"
                        />
                        <button
                            onClick={runPortTest}
                            disabled={loading}
                            className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-md transition-all"
                        >
                            {loading ? <Activity size={15} className="animate-spin" /> : <Play size={15} />}
                            {loading ? 'Testando...' : 'Testar Matriz de Portas'}
                        </button>
                    </div>

                    {portSummary && (
                        <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900 border border-zinc-800 rounded-xl text-xs shrink-0">
                            <span className="text-zinc-400 font-mono">
                                Portas Abertas: <strong className="text-emerald-400">{portSummary.open}</strong> de {portSummary.total}
                            </span>
                            <span className={clsx(
                                "px-2 py-0.5 rounded font-bold uppercase",
                                portSummary.status === 'HEALTHY' ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            )}>
                                {portSummary.status}
                            </span>
                        </div>
                    )}

                    <div className="flex-1 overflow-auto custom-scrollbar bg-black rounded-xl border border-zinc-800">
                        {portResults.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8">
                                <Server size={48} className="mb-3 opacity-20 text-blue-400" />
                                <p className="text-sm font-medium text-zinc-400">Matriz de 9 Portas Essenciais do Active Directory</p>
                                <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                    Verifica DNS (53), Kerberos (88), RPC (135), LDAP (389), SMB/SYSVOL (445), Kpasswd (464), LDAPS (636) e Global Catalog (3268/3269).
                                </p>
                            </div>
                        ) : (
                            <table className="w-full text-xs font-mono">
                                <thead className="sticky top-0 bg-zinc-950 text-zinc-400 border-b border-zinc-800 z-10">
                                    <tr>
                                        <th className="text-left px-3 py-2 font-semibold w-16">Porta</th>
                                        <th className="text-left px-3 py-2 font-semibold w-28">Serviço</th>
                                        <th className="text-left px-3 py-2 font-semibold">Função no Active Directory</th>
                                        <th className="text-right px-3 py-2 font-semibold w-24">Latência</th>
                                        <th className="text-center px-3 py-2 font-semibold w-24">Estado</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-900">
                                    {portResults.map((p) => (
                                        <tr key={p.port} className="hover:bg-zinc-900/50">
                                            <td className="px-3 py-2 text-zinc-300 font-bold">{p.port}</td>
                                            <td className="px-3 py-2 text-blue-300 font-semibold">{p.service}</td>
                                            <td className="px-3 py-2 text-zinc-400">{p.desc}</td>
                                            <td className="px-3 py-2 text-right text-zinc-300">{p.latency_ms !== null && p.latency_ms !== undefined ? `${p.latency_ms} ms` : '—'}</td>
                                            <td className="px-3 py-2 text-center">
                                                {p.open ? (
                                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                                        ABERTA
                                                    </span>
                                                ) : (
                                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                                        FECHADA
                                                    </span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            )}

            {/* Conteúdo da Sub-aba: SRV */}
            {subTab === 'srv' && (
                <div className="flex-1 flex flex-col space-y-3 min-h-0">
                    <div className="flex flex-wrap items-center gap-3 bg-zinc-900 p-3.5 rounded-xl border border-zinc-800 shrink-0">
                        <input
                            type="text"
                            placeholder="Domínio AD (ex: corp.local)"
                            value={domainTarget}
                            onChange={e => setDomainTarget(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter' && !loading) runSrvTest(); }}
                            className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[200px] focus:outline-none focus:border-blue-500 font-mono"
                        />
                        <input
                            type="text"
                            placeholder="DNS Server opcional (ex: 10.0.0.1)"
                            value={customDns}
                            onChange={e => setCustomDns(e.target.value)}
                            className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 w-48 focus:outline-none focus:border-blue-500 font-mono"
                        />
                        <button
                            onClick={runSrvTest}
                            disabled={loading}
                            className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-md transition-all"
                        >
                            {loading ? <Activity size={15} className="animate-spin" /> : <Play size={15} />}
                            {loading ? 'Consultando...' : 'Validar Registros SRV'}
                        </button>
                    </div>

                    <div className="flex-1 overflow-auto custom-scrollbar space-y-2.5">
                        {srvResults.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8 border border-zinc-800 rounded-xl bg-black">
                                <Layers size={48} className="mb-3 opacity-20 text-blue-400" />
                                <p className="text-sm font-medium text-zinc-400">Validação de Registros DNS SRV do Active Directory</p>
                                <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                    Localiza os controladores de domínio consultando os registros _ldap._tcp.dc._msdcs, _kerberos._tcp, _kpasswd._tcp e _gc._tcp.
                                </p>
                            </div>
                        ) : (
                            srvResults.map((srv, idx) => (
                                <div key={idx} className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-xl text-xs space-y-2">
                                    <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
                                        <div className="font-mono text-blue-300 font-semibold">{srv.record}</div>
                                        <span className={clsx(
                                            "px-2 py-0.5 rounded text-[10px] font-bold",
                                            srv.found ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                        )}>
                                            {srv.found ? 'ENCONTRADO' : 'NÃO RESOLVIDO'}
                                        </span>
                                    </div>
                                    <div className="text-zinc-400">{srv.desc}</div>
                                    {srv.targets && srv.targets.length > 0 && (
                                        <div className="space-y-1 pl-2 border-l-2 border-blue-500/40">
                                            {srv.targets.map((t, tidx) => (
                                                <div key={tidx} className="text-zinc-300 font-mono text-[11px] flex justify-between">
                                                    <span>{t.target}:{t.port} (Prioridade: {t.priority}, Peso: {t.weight})</span>
                                                    <span className="text-zinc-500">{t.ips?.join(', ') || 'Sem IP'}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}

            {/* Conteúdo da Sub-aba: Skew */}
            {subTab === 'skew' && (
                <div className="flex-1 flex flex-col space-y-3 min-h-0">
                    <div className="flex flex-wrap items-center gap-3 bg-zinc-900 p-3.5 rounded-xl border border-zinc-800 shrink-0">
                        <input
                            type="text"
                            placeholder="PDC Emulator ou DC (ex: dc01.corp.local)"
                            value={skewTarget}
                            onChange={e => setSkewTarget(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter' && !loading) runSkewTest(); }}
                            className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[220px] focus:outline-none focus:border-blue-500 font-mono"
                        />
                        <button
                            onClick={runSkewTest}
                            disabled={loading}
                            className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-md transition-all"
                        >
                            {loading ? <Activity size={15} className="animate-spin" /> : <Clock size={15} />}
                            {loading ? 'Medindo...' : 'Checar Desvio Kerberos'}
                        </button>
                    </div>

                    <div className="flex-1 overflow-auto custom-scrollbar">
                        {!skewResult ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8 border border-zinc-800 rounded-xl bg-black">
                                <Clock size={48} className="mb-3 opacity-20 text-blue-400" />
                                <p className="text-sm font-medium text-zinc-400">Verificação de Desvio de Relógio (Kerberos Time Skew)</p>
                                <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                    O protocolo Kerberos v5 rejeita autenticações quando a diferença entre o relógio da estação e do Controlador de Domínio ultrapassa 300 segundos (5 minutos).
                                </p>
                            </div>
                        ) : (
                            <div className="p-5 bg-zinc-900/80 border border-zinc-800 rounded-xl space-y-4 text-xs">
                                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                                    <span className="font-semibold text-zinc-200 flex items-center gap-2 text-sm">
                                        <Server size={18} className="text-blue-400" /> Servidor Alvo: {skewResult.target}
                                    </span>
                                    <span className={clsx(
                                        "px-2.5 py-0.5 rounded-full font-bold",
                                        skewResult.status === 'HEALTHY' ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                    )}>
                                        {skewResult.status}
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                    <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                                        <div className="text-zinc-500 text-[11px]">Desvio (Offset)</div>
                                        <div className="text-base font-bold text-zinc-100 font-mono">{skewResult.offset_ms ?? '-'} ms</div>
                                    </div>
                                    <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                                        <div className="text-zinc-500 text-[11px]">RTT / Delay de Rede</div>
                                        <div className="text-base font-bold text-zinc-100 font-mono">{skewResult.delay_ms ?? '-'} ms</div>
                                    </div>
                                    <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                                        <div className="text-zinc-500 text-[11px]">NTP Stratum</div>
                                        <div className="text-base font-bold text-zinc-100 font-mono">{skewResult.stratum ?? '-'}</div>
                                    </div>
                                    <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                                        <div className="text-zinc-500 text-[11px]">Tolerância Kerberos</div>
                                        <div className="text-base font-bold text-emerald-400 font-mono">&lt; 300 segundos</div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Conteúdo da Sub-aba: FSMO & Replicação */}
            {subTab === 'fsmo' && (
                <div className="flex-1 flex flex-col space-y-3 min-h-0">
                    <div className="flex flex-wrap items-center gap-3 bg-zinc-900 p-3.5 rounded-xl border border-zinc-800 shrink-0">
                        <input
                            type="text"
                            placeholder="Domínio AD opcional (deixe em branco para o domínio da máquina atual)"
                            value={fsmoDomain}
                            onChange={e => setFsmoDomain(e.target.value)}
                            className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[240px] focus:outline-none focus:border-blue-500 font-mono"
                        />
                        <button
                            onClick={runFsmoDiscovery}
                            disabled={loading}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-md transition-all"
                        >
                            {loading ? <Activity size={15} className="animate-spin" /> : <Crown size={15} />}
                            Descobrir FSMO Roles
                        </button>
                        <button
                            onClick={runReplicationCheck}
                            disabled={loading}
                            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-md transition-all"
                        >
                            {loading ? <Activity size={15} className="animate-spin" /> : <RefreshCw size={15} />}
                            Auditar Replicação
                        </button>
                    </div>

                    <div className="flex-1 overflow-auto custom-scrollbar space-y-3">
                        {!fsmoResult && !replResult ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8 border border-zinc-800 rounded-xl bg-black">
                                <Crown size={48} className="mb-3 opacity-20 text-blue-400" />
                                <p className="text-sm font-medium text-zinc-400">Descoberta de FSMO Roles e Integridade de Replicação</p>
                                <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                    Identifica os 5 detentores de funções FSMO (Schema, Domain Naming, PDC, RID, Infrastructure) e verifica o estado de sincronismo de diretório entre todos os controladores da floresta.
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {/* Cards FSMO */}
                                {fsmoResult && fsmoResult.ok && fsmoResult.role_list && (
                                    <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                        <div className="flex items-center justify-between">
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                                <Crown size={15} className="text-amber-400" />
                                                Detentores das Funções FSMO (Active Directory)
                                            </h3>
                                            <span className="text-xs text-zinc-400 font-mono">
                                                Domínio: <strong>{fsmoResult.domain}</strong>
                                            </span>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                                            {fsmoResult.role_list.map((r, idx) => (
                                                <div key={idx} className="bg-zinc-950 border border-zinc-800 p-3 rounded-lg text-xs space-y-1">
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-bold text-amber-300 font-mono">{r.role}</span>
                                                        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-500/15 text-blue-300 border border-blue-500/30">
                                                            {r.holder || 'Não identificado'}
                                                        </span>
                                                    </div>
                                                    <p className="text-[11px] text-zinc-500">{r.desc}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Tabela de Replicação */}
                                {replResult && replResult.ok && (
                                    <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                        <div className="flex items-center justify-between">
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                                <RefreshCw size={15} className="text-indigo-400" />
                                                Status de Replicação de Diretório (repadmin)
                                            </h3>
                                            <span className={clsx(
                                                "px-2.5 py-0.5 rounded-full text-xs font-bold",
                                                replResult.status === 'HEALTHY' ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                            )}>
                                                {replResult.status === 'HEALTHY' ? '100% Sincronizado' : `${replResult.total_fails} Falhas`}
                                            </span>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            {/* Origens */}
                                            <div className="space-y-2">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                                                    DSA Origem (Source DCs)
                                                </span>
                                                <div className="space-y-1.5">
                                                    {replResult.sources.map((s, idx) => (
                                                        <div key={idx} className="bg-zinc-950 border border-zinc-800 p-2.5 rounded-lg text-xs font-mono flex items-center justify-between">
                                                            <div>
                                                                <span className="font-bold text-zinc-200">{s.dsa}</span>
                                                                <span className="text-[11px] text-zinc-500 block">Delta: {s.largest_delta}</span>
                                                            </div>
                                                            <div className="text-right">
                                                                <span className={clsx(
                                                                    "px-2 py-0.5 rounded text-[10px] font-bold",
                                                                    s.fails === 0 ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                                                                )}>
                                                                    {s.fails} / {s.total} falhas
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>

                                            {/* Destinos */}
                                            <div className="space-y-2">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                                                    DSA Destino (Destination DCs)
                                                </span>
                                                <div className="space-y-1.5">
                                                    {replResult.destinations.map((d, idx) => (
                                                        <div key={idx} className="bg-zinc-950 border border-zinc-800 p-2.5 rounded-lg text-xs font-mono flex items-center justify-between">
                                                            <div>
                                                                <span className="font-bold text-zinc-200">{d.dsa}</span>
                                                                <span className="text-[11px] text-zinc-500 block">Delta: {d.largest_delta}</span>
                                                            </div>
                                                            <div className="text-right">
                                                                <span className={clsx(
                                                                    "px-2 py-0.5 rounded text-[10px] font-bold",
                                                                    d.fails === 0 ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                                                                )}>
                                                                    {d.fails} / {d.total} falhas
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
