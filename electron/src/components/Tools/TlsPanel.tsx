import { useState } from 'react';
import {
    Search,
    ShieldCheck,
    ShieldAlert,
    ShieldX,
    Lock,
    GitBranch,
    Layers,
    Activity
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface CertChainItem {
    cn?: string | null;
    subject?: string;
    issuer?: string;
    issuer_org?: string | null;
    serial?: string;
    sans?: string[];
    not_before?: string;
    not_after?: string;
    days_to_expiry?: number;
    is_expired?: boolean;
    not_yet_valid?: boolean;
    signature_algorithm?: string;
}

interface CipherEval {
    name: string;
    grade: 'strong' | 'moderate' | 'weak' | 'unknown';
    pfs: boolean;
    aead: boolean;
    rating: string;
}

interface CertResult {
    ok: boolean;
    error?: string;
    host?: string;
    port?: number;
    subject?: string;
    issuer?: string;
    cn?: string | null;
    serial?: string;
    sans?: string[];
    not_before?: string;
    not_after?: string;
    days_to_expiry?: number;
    is_expired?: boolean;
    not_yet_valid?: boolean;
    tls_version?: string;
    cipher?: string;
    cipher_eval?: CipherEval;
    signature_algorithm?: string;
    alpn?: string;
    chain?: CertChainItem[];
    chain_length?: number;
    protocols?: Record<string, boolean>;
    has_deprecated_protocols?: boolean;
}

/** Helper para sanitizar URLs e hosts: remove http://, https://, ssl://, caminhos, barras finais e detecta porta */
function parseSmartTarget(raw: string, defaultPort = 443): { host: string; port: number } {
    let s = raw.trim().replace(/^['"]|['"]$/g, '');
    if (!s) return { host: '', port: defaultPort };

    s = s.replace(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, '');
    s = s.split('/')[0].split('?')[0].split('#')[0];

    let port = defaultPort;
    if (s.includes(':') && !s.startsWith('[')) {
        const parts = s.split(':');
        s = parts[0];
        const parsedPort = parseInt(parts[1], 10);
        if (!isNaN(parsedPort) && parsedPort >= 1 && parsedPort <= 65535) {
            port = parsedPort;
        }
    } else if (s.startsWith('[') && s.includes(']:')) {
        const match = s.match(/^\[(.*?)\]:(\d+)$/);
        if (match) {
            s = match[1];
            const parsedPort = parseInt(match[2], 10);
            if (!isNaN(parsedPort) && parsedPort >= 1 && parsedPort <= 65535) {
                port = parsedPort;
            }
        }
    }

    s = s.replace(/\.+$/, '').trim();
    return { host: s, port };
}

export function TlsPanel() {
    const { showToast } = useToast();
    const [host, setHost] = usePersistedState('tls_tool_host', 'www.google.com');
    const [port, setPort] = usePersistedState('tls_tool_port', '443');
    const [result, setResult, clearResult] = usePersistedState<CertResult | null>('tls_tool_result_v2', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('tls_tool_last_run_v2', null);
    const [busy, setBusy] = useState(false);

    const check = async () => {
        const parsed = parseSmartTarget(host, parseInt(port, 10) || 443);
        if (!parsed.host) {
            showToast('Informe o host.', 'error');
            return;
        }

        setHost(parsed.host);
        setPort(parsed.port.toString());
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/tls`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host: parsed.host, port: parsed.port }),
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

    const expiryBadge = () => {
        if (!result?.ok) return null;
        if (result.is_expired) return { cls: 'text-red-400 bg-red-500/10 border-red-900/40', icon: <ShieldX size={16} />, txt: 'EXPIRADO' };
        if (result.not_yet_valid) return { cls: 'text-amber-400 bg-amber-500/10 border-amber-900/40', icon: <ShieldAlert size={16} />, txt: 'AINDA NÃO VÁLIDO' };
        const d = result.days_to_expiry ?? 0;
        if (d <= 14) return { cls: 'text-red-400 bg-red-500/10 border-red-900/40', icon: <ShieldAlert size={16} />, txt: `EXPIRA EM ${d} DIAS` };
        if (d <= 30) return { cls: 'text-amber-400 bg-amber-500/10 border-amber-900/40', icon: <ShieldAlert size={16} />, txt: `EXPIRA EM ${d} DIAS` };
        return { cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-900/40', icon: <ShieldCheck size={16} />, txt: `VÁLIDO · ${d} DIAS RESTANTES` };
    };
    const badge = expiryBadge();

    const Row = ({ label, value }: { label: string; value?: React.ReactNode }) => (
        <div className="flex gap-3 py-1.5 border-b border-zinc-900 text-xs">
            <span className="text-zinc-500 w-36 shrink-0">{label}</span>
            <span className="text-zinc-200 font-mono break-all">{value ?? '—'}</span>
        </div>
    );

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Controles de Entrada */}
            <div className="flex flex-wrap gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800 shrink-0">
                <div className="flex-1 min-w-[240px] space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Host ou FQDN
                    </label>
                    <input
                        type="text"
                        value={host}
                        onChange={e => setHost(e.target.value)}
                        onFocus={() => { if (host === 'www.google.com') setHost(''); }}
                        onBlur={() => {
                            if (host) {
                                const p = parseSmartTarget(host, parseInt(port, 10) || 443);
                                if (p.host && p.host !== host) {
                                    setHost(p.host);
                                    if (p.port !== 443 || port === '443') setPort(p.port.toString());
                                }
                            }
                        }}
                        placeholder="ex: www.google.com ou 10.0.0.1"
                        onKeyDown={e => { if (e.key === 'Enter' && !busy) check(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-emerald-500 font-mono placeholder:text-zinc-500 text-sm"
                    />
                </div>
                <div className="space-y-1.5 w-24">
                    <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Porta
                    </label>
                    <input
                        type="text"
                        value={port}
                        onChange={e => setPort(e.target.value)}
                        placeholder="443"
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 font-mono"
                    />
                </div>
                <button
                    onClick={check}
                    disabled={busy}
                    className="flex items-center gap-2 px-5 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 transition-all text-sm disabled:opacity-60"
                >
                    {busy ? <Activity size={16} className="animate-spin" /> : <Search size={16} />}
                    Inspecionar TLS
                </button>
            </div>

            {/* Badge de Última Execução */}
            {result && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={host ? `${host}:${port}` : null}
                    onClear={() => { clearResult(); setLastRunAt(null); }}
                />
            )}

            {/* Conteúdo Principal */}
            <div className="flex-1 overflow-auto custom-scrollbar space-y-3">
                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8 border border-zinc-900 rounded-xl bg-black">
                        <Lock size={48} className="mb-4 opacity-20 text-emerald-400" />
                        <p className="text-sm font-medium text-zinc-400">Inspeção Completa de Certificados e Criptografia TLS</p>
                        <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                            Valida a expiração do certificado folha, inspeciona a cadeia de confiança (Chain of Trust), verifica o suporte a ALPN (HTTP/2) e audita o descarte de protocolos TLS 1.0 e 1.1 obsoletos.
                        </p>
                    </div>
                ) : result.ok ? (
                    <div className="space-y-3">
                        {/* Status Geral e Badges de Criptografia */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                            {badge && (
                                <div className={clsx("p-3.5 rounded-xl border flex items-center gap-3", badge.cls)}>
                                    <div className="p-2 rounded-lg bg-black/30 shrink-0">{badge.icon}</div>
                                    <div>
                                        <span className="text-[10px] uppercase font-bold tracking-wider opacity-80 block">Status de Validade</span>
                                        <span className="text-sm font-bold font-mono">{badge.txt}</span>
                                    </div>
                                </div>
                            )}

                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3.5 flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-zinc-950 text-indigo-400 shrink-0">
                                    <Layers size={18} />
                                </div>
                                <div>
                                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Protocolo & ALPN</span>
                                    <span className="text-sm font-bold font-mono text-zinc-100">
                                        {result.tls_version || 'TLS'} · {result.alpn || 'HTTP/1.1'}
                                    </span>
                                </div>
                            </div>

                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3.5 flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-zinc-950 text-emerald-400 shrink-0">
                                    <ShieldCheck size={18} />
                                </div>
                                <div>
                                    <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Robustez da Cifra</span>
                                    <span className={clsx(
                                        "text-sm font-bold font-mono",
                                        result.cipher_eval?.grade === 'strong' ? "text-emerald-400" :
                                        result.cipher_eval?.grade === 'weak' ? "text-rose-400" : "text-amber-400"
                                    )}>
                                        {result.cipher_eval?.rating || 'Padrão'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Auditoria de Protocolos Depreciados */}
                        {result.protocols && (
                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-2.5">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                        <GitBranch size={15} className="text-emerald-400" />
                                        Auditoria de Protocolos TLS Aceitos
                                    </h3>
                                    {result.has_deprecated_protocols ? (
                                        <span className="text-xs font-semibold text-rose-400 flex items-center gap-1">
                                            <ShieldAlert size={13} /> Servidor aceita protocolos inseguros (PCI-DSS Reprovado)
                                        </span>
                                    ) : (
                                        <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                                            <ShieldCheck size={13} /> Protocolos legados desativados (PCI-DSS Aprovado)
                                        </span>
                                    )}
                                </div>

                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                    {Object.entries(result.protocols).map(([pName, supported]) => {
                                        const isLegacy = pName === 'TLSv1.0' || pName === 'TLSv1.1';
                                        return (
                                            <div
                                                key={pName}
                                                className={clsx(
                                                    "p-2.5 rounded-lg border text-xs font-mono flex items-center justify-between",
                                                    supported
                                                        ? isLegacy
                                                            ? "bg-rose-950/20 border-rose-900/40 text-rose-300"
                                                            : "bg-emerald-950/20 border-emerald-900/40 text-emerald-300"
                                                        : "bg-zinc-950/60 border-zinc-800 text-zinc-500"
                                                )}
                                            >
                                                <span className="font-bold">{pName.replace('v', ' ')}</span>
                                                {supported ? (
                                                    <span className={clsx("text-[10px] px-1.5 py-0.5 rounded font-bold", isLegacy ? "bg-rose-500/20 text-rose-300" : "bg-emerald-500/20 text-emerald-300")}>
                                                        {isLegacy ? 'Habilitado (Inseguro)' : 'Habilitado (Seguro)'}
                                                    </span>
                                                ) : (
                                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-semibold">
                                                        Negado
                                                    </span>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* Cadeia de Confiança (Chain of Trust) */}
                        {result.chain && result.chain.length > 0 && (
                            <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4 space-y-3">
                                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                                    <Layers size={15} className="text-indigo-400" />
                                    Cadeia Completa de Certificados (Chain of Trust - {result.chain.length} níveis)
                                </h3>

                                <div className="space-y-2">
                                    {result.chain.map((cert, idx) => (
                                        <div key={idx} className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs font-mono space-y-1">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <span className={clsx(
                                                        "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                                                        idx === 0 ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" :
                                                        idx === (result.chain?.length ?? 1) - 1 ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30" :
                                                        "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                                                    )}>
                                                        {idx === 0 ? 'Certificado Folha (Servidor)' : idx === (result.chain?.length ?? 1) - 1 ? 'CA Raiz (Root CA)' : `CA Intermediária #${idx}`}
                                                    </span>
                                                    <span className="text-zinc-200 font-bold truncate max-w-md">{cert.cn || cert.subject}</span>
                                                </div>
                                                <span className={clsx(
                                                    "text-[11px]",
                                                    cert.is_expired ? "text-rose-400 font-bold" : "text-zinc-400"
                                                )}>
                                                    {cert.is_expired ? 'Expirado' : `${cert.days_to_expiry} dias restantes`}
                                                </span>
                                            </div>
                                            <div className="text-[11px] text-zinc-500 truncate">
                                                Emissor: <span className="text-zinc-400">{cert.issuer_org || cert.issuer}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Metadados Técnicos do Certificado */}
                        <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-4">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 mb-2">
                                Metadados Criptográficos
                            </h3>
                            <Row label="Sujeito (Subject)" value={result.subject} />
                            <Row label="Emissor (Issuer)" value={result.issuer} />
                            <Row label="Número de Série" value={result.serial} />
                            <Row label="Algoritmo de Assinatura" value={result.signature_algorithm} />
                            <Row label="Cifra Negociada" value={result.cipher} />
                            <Row label="Válido de" value={result.not_before} />
                            <Row label="Válido até" value={result.not_after} />
                            <Row label="Porta / Serviço" value={`${result.port}`} />

                            {result.sans && result.sans.length > 0 && (
                                <div className="pt-2 text-xs">
                                    <span className="text-zinc-500 block mb-1">Nomes Alternativos (SANs - {result.sans.length} domínios):</span>
                                    <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto custom-scrollbar bg-zinc-950 p-2 rounded-lg border border-zinc-800">
                                        {result.sans.map((s, i) => (
                                            <span key={i} className="text-[10px] bg-zinc-900 text-zinc-300 px-2 py-0.5 rounded font-mono border border-zinc-800/80">
                                                {s}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="p-4 bg-rose-500/10 border border-rose-900/40 rounded-xl text-rose-400 text-sm flex items-center gap-2">
                        <ShieldAlert size={16} className="shrink-0" />
                        <span>{result.error}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
