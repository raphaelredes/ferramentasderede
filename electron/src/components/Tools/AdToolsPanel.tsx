import { useState } from 'react';
import { ShieldAlert, CheckCircle, XCircle, Clock, Server, Play } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

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

export function AdToolsPanel({ defaultSourceIp }: { defaultSourceIp?: string }) {
    const { showToast } = useToast();
    const [subTab, setSubTab] = useState<'ports' | 'srv' | 'skew'>('ports');
    const [loading, setLoading] = useState(false);

    // Port Matrix State
    const [dcTarget, setDcTarget] = useState('dc01.corp.local');
    const [portResults, setPortResults] = useState<ADPortResult[]>([]);
    const [portSummary, setPortSummary] = useState<{ total: number; open: number; status: string } | null>(null);

    // SRV Records State
    const [domainTarget, setDomainTarget] = useState('corp.local');
    const [customDns, setCustomDns] = useState('');
    const [srvResults, setSrvResults] = useState<ADSRVResult[]>([]);

    // Time Skew State
    const [skewTarget, setSkewTarget] = useState('dc01.corp.local');
    const [skewResult, setSkewResult] = useState<any>(null);

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
            showToast('Registros SRV consultados!', 'success');
        } catch (err: any) {
            showToast(`Erro ao consultar SRV: ${err.message}`, 'error');
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
            showToast('Verificação de desvio concluída!', 'success');
        } catch (err: any) {
            showToast(`Erro no teste de Time Skew: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-zinc-900/60 rounded-xl p-5 border border-zinc-800 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                    <ShieldAlert className="text-blue-400" size={20} />
                    <h3 className="text-base font-semibold text-zinc-100">Diagnóstico de Active Directory & Domínio</h3>
                </div>
                <div className="flex gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-800 text-xs font-medium">
                    <button
                        onClick={() => setSubTab('ports')}
                        className={`px-3 py-1.5 rounded-md transition-colors ${subTab === 'ports' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                        Matriz de Portas
                    </button>
                    <button
                        onClick={() => setSubTab('srv')}
                        className={`px-3 py-1.5 rounded-md transition-colors ${subTab === 'srv' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                        Registros DNS SRV
                    </button>
                    <button
                        onClick={() => setSubTab('skew')}
                        className={`px-3 py-1.5 rounded-md transition-colors ${subTab === 'skew' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                        Time Skew (Kerberos)
                    </button>
                </div>
            </div>

            {subTab === 'ports' && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-3">
                        <input
                            type="text"
                            placeholder="DC FQDN ou IP (ex: dc01.corp.local)"
                            value={dcTarget}
                            onChange={e => setDcTarget(e.target.value)}
                            className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[220px] focus:outline-none focus:border-blue-500"
                        />
                        <button
                            onClick={runPortTest}
                            disabled={loading}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow transition-colors"
                        >
                            <Play size={15} />
                            {loading ? 'Testando...' : 'Testar Matriz AD'}
                        </button>
                    </div>

                    {portSummary && (
                        <div className="flex items-center gap-4 p-3 bg-zinc-950/80 border border-zinc-800 rounded-lg text-xs">
                            <span className="text-zinc-400">Portas Abertas: <strong className="text-zinc-200">{portSummary.open} / {portSummary.total}</strong></span>
                            <span className="text-zinc-400">Status Geral: 
                                <strong className={`ml-1 ${portSummary.status === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'}`}>
                                    {portSummary.status}
                                </strong>
                            </span>
                        </div>
                    )}

                    {portResults.length > 0 && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {portResults.map(p => (
                                <div key={p.port} className="p-3 bg-zinc-950 border border-zinc-800/80 rounded-lg flex items-center justify-between text-xs">
                                    <div>
                                        <div className="font-semibold text-zinc-200 flex items-center gap-1.5">
                                            {p.service} <span className="text-zinc-500 text-[11px]">({p.port}/{p.proto})</span>
                                        </div>
                                        <div className="text-zinc-400 text-[11px] mt-0.5">{p.desc}</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {p.latency_ms !== undefined && p.latency_ms !== null && (
                                            <span className="text-zinc-400 text-[11px]">{p.latency_ms} ms</span>
                                        )}
                                        {p.open ? (
                                            <CheckCircle size={16} className="text-emerald-400 shrink-0" />
                                        ) : (
                                            <XCircle size={16} className="text-rose-400 shrink-0" />
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {subTab === 'srv' && (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <input
                            type="text"
                            placeholder="Nome do Domínio AD (ex: corp.local)"
                            value={domainTarget}
                            onChange={e => setDomainTarget(e.target.value)}
                            className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-blue-500"
                        />
                        <input
                            type="text"
                            placeholder="DNS Server Opcional (ex: 192.168.1.10)"
                            value={customDns}
                            onChange={e => setCustomDns(e.target.value)}
                            className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <button
                        onClick={runSrvTest}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow transition-colors"
                    >
                        <Play size={15} />
                        {loading ? 'Consultando...' : 'Validar Registros SRV'}
                    </button>

                    {srvResults.length > 0 && (
                        <div className="space-y-3">
                            {srvResults.map((srv, idx) => (
                                <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs space-y-2">
                                    <div className="flex items-center justify-between border-b border-zinc-800/60 pb-1.5">
                                        <div className="font-mono text-blue-300 font-semibold">{srv.record}</div>
                                        <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${srv.found ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-rose-950 text-rose-300 border border-rose-800'}`}>
                                            {srv.found ? 'ENCONTRADO' : 'NÃO RESOLVIDO'}
                                        </span>
                                    </div>
                                    <div className="text-zinc-400">{srv.desc}</div>
                                    {srv.targets && srv.targets.length > 0 && (
                                        <div className="space-y-1 pl-2 border-l-2 border-zinc-700">
                                            {srv.targets.map((t, tidx) => (
                                                <div key={tidx} className="text-zinc-300 font-mono text-[11px] flex justify-between">
                                                    <span>{t.target}:{t.port} (Prioridade: {t.priority}, Peso: {t.weight})</span>
                                                    <span className="text-zinc-500">{t.ips?.join(', ') || 'Sem IP'}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {subTab === 'skew' && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-3">
                        <input
                            type="text"
                            placeholder="PDC Emulator ou DC (ex: dc01.corp.local)"
                            value={skewTarget}
                            onChange={e => setSkewTarget(e.target.value)}
                            className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[220px] focus:outline-none focus:border-blue-500"
                        />
                        <button
                            onClick={runSkewTest}
                            disabled={loading}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow transition-colors"
                        >
                            <Clock size={15} />
                            {loading ? 'Medindo...' : 'Checar Desvio Kerberos'}
                        </button>
                    </div>

                    {skewResult && (
                        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-3 text-xs">
                            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                                <span className="font-semibold text-zinc-200 flex items-center gap-2">
                                    <Server size={16} className="text-blue-400" /> Servidor: {skewResult.target}
                                </span>
                                <span className={`px-2.5 py-1 rounded-full font-bold ${skewResult.status === 'HEALTHY' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'}`}>
                                    {skewResult.status}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div>
                                    <div className="text-zinc-500">Desvio (Skew)</div>
                                    <div className="text-base font-bold text-zinc-100">{skewResult.offset_ms ?? '-'} ms</div>
                                </div>
                                <div>
                                    <div className="text-zinc-500">RTT / Delay</div>
                                    <div className="text-base font-bold text-zinc-100">{skewResult.delay_ms ?? '-'} ms</div>
                                </div>
                                <div>
                                    <div className="text-zinc-500">NTP Stratum</div>
                                    <div className="text-base font-bold text-zinc-100">{skewResult.stratum ?? '-'}</div>
                                </div>
                                <div>
                                    <div className="text-zinc-500">Tolerância Kerberos</div>
                                    <div className="text-base font-bold text-emerald-400">&lt; 300 segundos</div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
