import { useState } from 'react';
import { Search, ShieldCheck, ShieldAlert, ShieldX, Lock } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface CertResult {
    ok: boolean;
    error?: string;
    host?: string; port?: number;
    subject?: string; issuer?: string; serial?: string;
    sans?: string[];
    not_before?: string; not_after?: string;
    days_to_expiry?: number; is_expired?: boolean; not_yet_valid?: boolean;
    tls_version?: string; cipher?: string; signature_algorithm?: string;
}

/** Helper para sanitizar URLs e hosts: remove http://, https://, ssl://, caminhos, barras finais e detecta porta */
function parseSmartTarget(raw: string, defaultPort = 443): { host: string; port: number } {
    let s = raw.trim().replace(/^['"]|['"]$/g, '');
    if (!s) return { host: '', port: defaultPort };

    // Remove esquema (http://, https://, ssl://, tls://)
    s = s.replace(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, '');

    // Remove caminhos, query strings e fragmentos
    s = s.split('/')[0].split('?')[0].split('#')[0];

    // Detecta se a porta veio junto no host (host:porta ou [ipv6]:porta)
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

    // Remove pontos finais e espaços residuais
    s = s.replace(/\.+$/, '').trim();

    return { host: s, port };
}

/** TLS certificate inspector for host:port (validity / SAN / expiry). */
export function TlsPanel() {
    const { showToast } = useToast();
    const [host, setHost] = useState('');
    const [port, setPort] = useState('443');
    const [result, setResult] = useState<CertResult | null>(null);
    const [busy, setBusy] = useState(false);

    const check = async () => {
        const parsed = parseSmartTarget(host, parseInt(port, 10) || 443);
        if (!parsed.host) { showToast('Informe o host.', 'error'); return; }

        setHost(parsed.host);
        setPort(parsed.port.toString());
        setBusy(true); setResult(null);
        try {
            const res = await fetch(`${API_BASE}/tools/tls`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host: parsed.host, port: parsed.port }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setResult(data);
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        } finally { setBusy(false); }
    };

    const expiryBadge = () => {
        if (!result?.ok) return null;
        if (result.is_expired) return { cls: 'text-red-400 bg-red-500/10 border-red-900/40', icon: <ShieldX size={16} />, txt: 'EXPIRADO' };
        if (result.not_yet_valid) return { cls: 'text-amber-400 bg-amber-500/10 border-amber-900/40', icon: <ShieldAlert size={16} />, txt: 'AINDA NÃO VÁLIDO' };
        const d = result.days_to_expiry ?? 0;
        if (d <= 14) return { cls: 'text-red-400 bg-red-500/10 border-red-900/40', icon: <ShieldAlert size={16} />, txt: `EXPIRA EM ${d} DIAS` };
        if (d <= 30) return { cls: 'text-amber-400 bg-amber-500/10 border-amber-900/40', icon: <ShieldAlert size={16} />, txt: `EXPIRA EM ${d} DIAS` };
        return { cls: 'text-green-400 bg-green-500/10 border-green-900/40', icon: <ShieldCheck size={16} />, txt: `VÁLIDO · ${d} DIAS` };
    };
    const badge = expiryBadge();

    const Row = ({ label, value }: { label: string; value?: React.ReactNode }) => (
        <div className="flex gap-3 py-1.5 border-b border-zinc-900 text-sm">
            <span className="text-zinc-500 w-32 shrink-0">{label}</span>
            <span className="text-zinc-200 font-mono break-all">{value ?? '—'}</span>
        </div>
    );

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Host</label>
                    <input type="text" value={host}
                        onChange={e => setHost(e.target.value)}
                        onBlur={() => {
                            if (host) {
                                const p = parseSmartTarget(host, parseInt(port, 10) || 443);
                                if (p.host && p.host !== host) {
                                    setHost(p.host);
                                    if (p.port !== 443 || port === '443') {
                                        setPort(p.port.toString());
                                    }
                                }
                            }
                        }}
                        placeholder="echamados.betim.mg.gov.br ou https://site.com.br"
                        onKeyDown={e => { if (e.key === 'Enter' && !busy) check(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500" />
                </div>
                <div className="space-y-2 w-28">
                    <label className="text-sm font-medium text-zinc-400">Porta</label>
                    <input type="text" value={port} onChange={e => setPort(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 font-mono" />
                </div>
                <button onClick={check} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-violet-400 border border-violet-900/30 hover:border-violet-500/50 transition-colors disabled:opacity-60">
                    <Search size={18} /> Verificar
                </button>
            </div>


            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-5 overflow-auto custom-scrollbar">
                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <Lock size={48} className="mb-4 opacity-20" />
                        <p>Inspeciona o certificado TLS de um host (validade, SAN, emissor).</p>
                    </div>
                ) : !result.ok ? (
                    <div className="text-red-400 text-sm">{result.error}</div>
                ) : (
                    <div className="space-y-3">
                        {badge && (
                            <div className={clsx('inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-semibold', badge.cls)}>
                                {badge.icon}{badge.txt}
                            </div>
                        )}
                        <div className="mt-2">
                            <Row label="Host" value={`${result.host}:${result.port}`} />
                            <Row label="Subject" value={result.subject} />
                            <Row label="Emissor" value={result.issuer} />
                            <Row label="Válido de" value={result.not_before ? new Date(result.not_before).toLocaleString('pt-BR') : '—'} />
                            <Row label="Válido até" value={result.not_after ? new Date(result.not_after).toLocaleString('pt-BR') : '—'} />
                            <Row label="SANs" value={result.sans && result.sans.length ? result.sans.join(', ') : '—'} />
                            <Row label="TLS" value={`${result.tls_version ?? '—'} · ${result.cipher ?? '—'}`} />
                            <Row label="Assinatura" value={result.signature_algorithm} />
                            <Row label="Serial" value={result.serial} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
