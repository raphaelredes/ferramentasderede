import { useState } from 'react';
import {
    Globe,
    Search,
    ShieldCheck,
    Clock,
    ArrowRight,
    CheckCircle2,
    AlertTriangle,
    Activity
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface SecurityHeaderItem {
    id: string;
    name: string;
    present: boolean;
    value: string;
    status: 'pass' | 'warning' | 'info';
    desc: string;
}

interface RedirectHop {
    status: number;
    url: string;
    location?: string | null;
}

interface HttpTiming {
    dns_ms?: number | null;
    tcp_ms?: number | null;
    tls_ms?: number | null;
    server_processing_ms?: number | null;
    ttfb_ms?: number | null;
    download_ms?: number | null;
    total_ms?: number | null;
}

interface HttpResult {
    ok: boolean;
    error?: string;
    url?: string;
    final_url?: string;
    resolved_ip?: string | null;
    method?: string;
    status?: number;
    server?: string;
    content_type?: string;
    content_length?: number;
    redirected?: boolean;
    redirects?: RedirectHop[];
    timing?: HttpTiming;
    security?: {
        headers: SecurityHeaderItem[];
        passed: number;
        total: number;
        grade: string;
    };
    ttfb_ms?: number;
    elapsed_ms?: number;
}

export function HttpPanel() {
    const { showToast } = useToast();
    const [url, setUrl] = usePersistedState('http_tool_url', 'https://www.google.com');
    const [method, setMethod] = usePersistedState('http_tool_method', 'GET');
    const [verifyTls, setVerifyTls] = usePersistedState('http_tool_verify_tls', true);
    const [result, setResult, clearResult] = usePersistedState<HttpResult | null>('http_tool_result_v2', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('http_tool_last_run_v2', null);
    const [busy, setBusy] = useState(false);

    const check = async () => {
        const u = url.trim();
        if (!u) {
            showToast('Informe uma URL para teste.', 'error');
            return;
        }
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/http`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: u, method, verify_tls: verifyTls }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setResult(data);
            setLastRunAt(new Date().toISOString());
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        } finally {
            setBusy(false);
        }
    };

    const statusBadge = (s?: number) => {
        if (!s) return { text: '—', cls: 'text-zinc-400 bg-zinc-800' };
        if (s < 300) return { text: `${s} OK`, cls: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30' };
        if (s < 400) return { text: `${s} Redirect`, cls: 'text-sky-300 bg-sky-500/15 border-sky-500/30' };
        if (s < 500) return { text: `${s} Client Error`, cls: 'text-amber-300 bg-amber-500/15 border-amber-500/30' };
        return { text: `${s} Server Error`, cls: 'text-rose-300 bg-rose-500/15 border-rose-500/30' };
    };

    const timing = result?.timing;
    const totalMs = timing?.total_ms || result?.elapsed_ms || 1;

    // Calcular larguras percentuais para o Waterfall
    const calcPct = (ms?: number | null) => {
        if (!ms || ms <= 0) return 0;
        return Math.max(1, Math.min(100, Math.round((ms / totalMs) * 100)));
    };

    const dnsPct = calcPct(timing?.dns_ms);
    const tcpPct = calcPct(timing?.tcp_ms);
    const tlsPct = calcPct(timing?.tls_ms);
    const srvPct = calcPct(timing?.server_processing_ms);
    const dlPct = calcPct(timing?.download_ms);

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Controles de Entrada */}
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-3 shrink-0">
                <div className="flex flex-wrap gap-4 items-end">
                    <div className="flex-1 min-w-[240px] space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            URL do Serviço Web
                        </label>
                        <input
                            type="text"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            onFocus={() => { if (url === 'https://www.google.com') setUrl(''); }}
                            placeholder="https://www.google.com ou http://intranet.local"
                            onKeyDown={(e) => { if (e.key === 'Enter' && !busy) check(); }}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-pink-500 transition-colors font-mono placeholder:text-zinc-500 text-sm"
                        />
                    </div>
                    <div className="space-y-1.5 w-28">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Método
                        </label>
                        <select
                            value={method}
                            onChange={(e) => setMethod(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-pink-500"
                        >
                            <option value="GET">GET</option>
                            <option value="HEAD">HEAD</option>
                        </select>
                    </div>
                    <button
                        onClick={check}
                        disabled={busy}
                        className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold bg-pink-600 hover:bg-pink-500 text-white shadow-md shadow-pink-600/20 transition-all text-sm disabled:opacity-60"
                    >
                        {busy ? <Activity size={16} className="animate-spin" /> : <Search size={16} />}
                        Diagnosticar HTTP
                    </button>
                </div>
                <div className="flex items-center justify-between text-xs text-zinc-400 pt-1">
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={verifyTls}
                            onChange={(e) => setVerifyTls(e.target.checked)}
                            className="accent-pink-500 rounded"
                        />
                        <span>Validar certificado TLS estritamente (desmarque para serviços com certificado autoassinado ou corporativo interno)</span>
                    </label>
                </div>
            </div>

            {/* Badge de Última Execução */}
            {result && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={url ? `${method} ${url}` : null}
                    onClear={() => { clearResult(); setLastRunAt(null); }}
                />
            )}

            {/* Conteúdo Principal */}
            <div className="flex-1 overflow-auto custom-scrollbar space-y-3">
                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8 border border-zinc-900 rounded-xl bg-black">
                        <Globe size={48} className="mb-4 opacity-20 text-pink-400" />
                        <p className="text-sm font-medium text-zinc-400">Diagnóstico de Saúde e Desempenho HTTP / Web</p>
                        <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                            Decompõe o tempo de resposta nas 5 fases reais (DNS, TCP, TLS, TTFB, Download), analisa os cabeçalhos de segurança OWASP e mapeia redirecionamentos.
                        </p>
                    </div>
                ) : result.ok ? (
                    <div className="space-y-3">
                        {/* Cards de Resumo */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3.5">
                                <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Status HTTP</span>
                                <div className="flex items-center gap-2 mt-1">
                                    <span className={clsx("px-2.5 py-0.5 rounded-full text-xs font-bold border", statusBadge(result.status).cls)}>
                                        {statusBadge(result.status).text}
                                    </span>
                                </div>
                                <span className="text-[11px] text-zinc-500 block mt-1 font-mono">{result.method} {result.status}</span>
                            </div>

                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3.5">
                                <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Tempo Total / RTT</span>
                                <span className="text-lg font-bold font-mono text-zinc-100 block mt-0.5">
                                    {result.timing?.total_ms ?? result.elapsed_ms ?? 0} ms
                                </span>
                                <span className="text-[11px] text-zinc-500 block truncate">
                                    TTFB: {result.timing?.ttfb_ms ?? result.ttfb_ms ?? 0} ms
                                </span>
                            </div>

                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3.5">
                                <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Servidor & IP</span>
                                <span className="text-sm font-bold font-mono text-pink-300 block mt-0.5 truncate" title={result.server || 'Oculto'}>
                                    {result.server || 'Não informado'}
                                </span>
                                <span className="text-[11px] text-zinc-500 font-mono block truncate">
                                    IP: {result.resolved_ip || '—'}
                                </span>
                            </div>

                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3.5">
                                <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Segurança OWASP</span>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <span className={clsx(
                                        "px-2 py-0.5 rounded text-xs font-bold",
                                        result.security?.grade === 'A' ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" :
                                        result.security?.grade === 'B' ? "bg-blue-500/20 text-blue-300 border border-blue-500/40" :
                                        "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                                    )}>
                                        Nota {result.security?.grade || '—'}
                                    </span>
                                    <span className="text-xs text-zinc-400 font-medium">
                                        {result.security?.passed || 0}/{result.security?.total || 6} cabeçalhos
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Waterfall Visual de Tempos de Conexão */}
                        {timing && (
                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                        <Clock size={15} className="text-pink-400" />
                                        Decomposição de Conexão (Waterfall de 5 Fases)
                                    </h3>
                                    <span className="text-xs text-zinc-400 font-mono">
                                        Tempo Total: <strong className="text-white">{timing.total_ms} ms</strong>
                                    </span>
                                </div>

                                {/* Barra de Progresso Segmentada (Waterfall Bar) */}
                                <div className="w-full h-5 rounded-lg overflow-hidden bg-zinc-950 flex border border-zinc-800/80">
                                    {dnsPct > 0 && (
                                        <div
                                            style={{ width: `${dnsPct}%` }}
                                            className="bg-blue-500 hover:opacity-90 transition-all flex items-center justify-center text-[10px] font-bold text-white overflow-hidden"
                                            title={`Resolução DNS: ${timing.dns_ms} ms (${dnsPct}%)`}
                                        >
                                            {dnsPct > 6 ? `${timing.dns_ms}ms` : ''}
                                        </div>
                                    )}
                                    {tcpPct > 0 && (
                                        <div
                                            style={{ width: `${tcpPct}%` }}
                                            className="bg-indigo-500 hover:opacity-90 transition-all flex items-center justify-center text-[10px] font-bold text-white overflow-hidden"
                                            title={`TCP Handshake: ${timing.tcp_ms} ms (${tcpPct}%)`}
                                        >
                                            {tcpPct > 6 ? `${timing.tcp_ms}ms` : ''}
                                        </div>
                                    )}
                                    {tlsPct > 0 && (
                                        <div
                                            style={{ width: `${tlsPct}%` }}
                                            className="bg-purple-500 hover:opacity-90 transition-all flex items-center justify-center text-[10px] font-bold text-white overflow-hidden"
                                            title={`TLS Handshake: ${timing.tls_ms} ms (${tlsPct}%)`}
                                        >
                                            {tlsPct > 6 ? `${timing.tls_ms}ms` : ''}
                                        </div>
                                    )}
                                    {srvPct > 0 && (
                                        <div
                                            style={{ width: `${srvPct}%` }}
                                            className="bg-amber-500 hover:opacity-90 transition-all flex items-center justify-center text-[10px] font-bold text-zinc-950 overflow-hidden"
                                            title={`Processamento do Servidor (TTFB): ${timing.server_processing_ms} ms (${srvPct}%)`}
                                        >
                                            {srvPct > 6 ? `${timing.server_processing_ms}ms` : ''}
                                        </div>
                                    )}
                                    {dlPct > 0 && (
                                        <div
                                            style={{ width: `${dlPct}%` }}
                                            className="bg-emerald-500 hover:opacity-90 transition-all flex items-center justify-center text-[10px] font-bold text-zinc-950 overflow-hidden"
                                            title={`Download do Conteúdo: ${timing.download_ms} ms (${dlPct}%)`}
                                        >
                                            {dlPct > 6 ? `${timing.download_ms}ms` : ''}
                                        </div>
                                    )}
                                </div>

                                {/* Legenda e Valores das Fases */}
                                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono pt-1">
                                    <div className="flex items-center gap-1.5">
                                        <span className="w-2.5 h-2.5 rounded-sm bg-blue-500 shrink-0"></span>
                                        <span className="text-zinc-400">DNS:</span>
                                        <span className="text-zinc-200 font-semibold">{timing.dns_ms ?? '—'} ms</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 shrink-0"></span>
                                        <span className="text-zinc-400">TCP Connect:</span>
                                        <span className="text-zinc-200 font-semibold">{timing.tcp_ms ?? '—'} ms</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <span className="w-2.5 h-2.5 rounded-sm bg-purple-500 shrink-0"></span>
                                        <span className="text-zinc-400">TLS Handshake:</span>
                                        <span className="text-zinc-200 font-semibold">{timing.tls_ms ?? '—'} ms</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 shrink-0"></span>
                                        <span className="text-zinc-400">Servidor (TTFB):</span>
                                        <span className="text-zinc-200 font-semibold">{timing.server_processing_ms ?? timing.ttfb_ms} ms</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 shrink-0"></span>
                                        <span className="text-zinc-400">Download:</span>
                                        <span className="text-zinc-200 font-semibold">{timing.download_ms ?? '—'} ms</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Cadeia de Redirecionamentos (quando houver) */}
                        {result.redirects && result.redirects.length > 0 && (
                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-2">
                                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                    <ArrowRight size={15} className="text-sky-400" />
                                    Cadeia de Redirecionamentos ({result.redirects.length} saltos)
                                </h3>
                                <div className="flex flex-col space-y-2 pt-1">
                                    {result.redirects.map((hop, idx) => (
                                        <div key={idx} className="flex items-center gap-2 text-xs font-mono bg-zinc-950 p-2 rounded-lg border border-zinc-800">
                                            <span className={clsx(
                                                "px-2 py-0.5 rounded font-bold text-[11px]",
                                                hop.status < 300 ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" :
                                                hop.status < 400 ? "bg-sky-500/20 text-sky-300 border border-sky-500/30" :
                                                "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                            )}>
                                                {hop.status}
                                            </span>
                                            <span className="text-zinc-300 truncate max-w-lg">{hop.url}</span>
                                            {hop.location && (
                                                <span className="text-zinc-500 text-[11px] ml-auto truncate max-w-xs">
                                                    → {hop.location}
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Auditoria de Cabeçalhos de Segurança OWASP */}
                        {result.security?.headers && (
                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                        <ShieldCheck size={15} className="text-emerald-400" />
                                        Auditoria de Cabeçalhos de Segurança (OWASP / Mozilla)
                                    </h3>
                                    <span className="text-xs text-zinc-400">
                                        {result.security.passed} de {result.security.total} proteções ativas
                                    </span>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                                    {result.security.headers.map((h) => (
                                        <div
                                            key={h.id}
                                            className={clsx(
                                                "p-3 rounded-lg border flex flex-col justify-between space-y-1.5 transition-colors",
                                                h.present
                                                    ? "bg-zinc-950 border-emerald-900/30 text-zinc-200"
                                                    : "bg-zinc-950/60 border-zinc-800 text-zinc-400"
                                            )}
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="text-xs font-bold text-zinc-200 font-mono">{h.name}</span>
                                                {h.present ? (
                                                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 shrink-0">
                                                        <CheckCircle2 size={12} /> Presente
                                                    </span>
                                                ) : (
                                                    <span className="flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 shrink-0">
                                                        <AlertTriangle size={12} /> Ausente
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-[11px] text-zinc-500">{h.desc}</p>
                                            {h.present && (
                                                <div className="text-[11px] font-mono text-zinc-400 bg-zinc-900 px-2 py-1 rounded truncate border border-zinc-800/80">
                                                    {h.value}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="p-4 bg-rose-500/10 border border-rose-900/40 rounded-xl text-rose-400 text-sm flex items-center gap-2">
                        <AlertTriangle size={16} className="shrink-0" />
                        <span>{result.error}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
