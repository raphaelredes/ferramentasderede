import { useState } from 'react';
import { Search, Globe, ArrowRight, Server } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { useNetworks } from '../../hooks/useNetworks';

interface DnsResult {
    kind: 'forward' | 'reverse';
    query: string;
    answer: string | null;
    dnsServer: string | null;
}

/**
 * DNS lookup tool. Forward (name → IP) and reverse (IP → FQDN), with the
 * ability to target a specific DNS server — essential in multi-AD setups where
 * the same shortname resolves differently per domain. Backed by the existing
 * /network/dns/resolve endpoint.
 */
export function DnsPanel() {
    const { showToast } = useToast();
    const { networks } = useNetworks();

    const [query, setQuery] = useState('');
    const [dnsServer, setDnsServer] = useState('');     // '' = system resolver
    const [results, setResults] = useState<DnsResult[]>([]);
    const [busy, setBusy] = useState(false);

    // Networks that actually have a DNS server configured (offer them as quick picks).
    const dnsNetworks = networks.filter(n => n.dns_server);

    // IPv4 (dotted quad) OR IPv6 (contains a colon and only hex/colon chars) →
    // reverse lookup. Anything else is treated as a hostname (forward). The
    // backend does a strict ip_address() check; this is just routing.
    const looksLikeIp = (s: string) => {
        const v = s.trim();
        if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(v)) return true;
        return v.includes(':') && /^[0-9a-fA-F:]+$/.test(v);
    };

    const resolve = async () => {
        const q = query.trim();
        if (!q) { showToast('Informe um hostname ou IP.', 'error'); return; }
        setBusy(true);
        try {
            const isIp = looksLikeIp(q);
            const body = isIp
                ? { ip: q, dns_server: dnsServer || undefined }
                : { name: q, dns_server: dnsServer || undefined };
            const res = await fetch(`${API_BASE}/network/dns/resolve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
            const data = await res.json();
            const result: DnsResult = isIp
                ? { kind: 'reverse', query: q, answer: data.fqdn ?? null, dnsServer: dnsServer || null }
                : { kind: 'forward', query: q, answer: data.ip ?? null, dnsServer: dnsServer || null };
            setResults(prev => [result, ...prev].slice(0, 20));
            if (!result.answer) showToast('Sem resposta (NXDOMAIN ou sem registro).', 'info');
        } catch (e: any) {
            showToast('Erro na consulta: ' + e.message, 'error');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-4">
                <div className="flex gap-4 items-end">
                    <div className="flex-1 space-y-2">
                        <label className="text-sm font-medium text-zinc-400">Hostname ou IP</label>
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="servidor.dominio.local  ou  10.0.0.5"
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-zinc-500"
                            onKeyDown={(e) => { if (e.key === 'Enter' && !busy) resolve(); }}
                        />
                    </div>
                    <div className="space-y-2 w-72">
                        <label className="text-sm font-medium text-zinc-400">Servidor DNS</label>
                        <select
                            value={dnsServer}
                            onChange={(e) => setDnsServer(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                        >
                            <option value="">Resolver do sistema (padrão)</option>
                            {dnsNetworks.map(net => (
                                <option key={net.id} value={net.dns_server ?? ''}>
                                    {net.name || net.cidr} — {net.dns_server}
                                </option>
                            ))}
                        </select>
                    </div>
                    <button
                        onClick={resolve}
                        disabled={busy}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-sky-400 border border-sky-900/30 hover:border-sky-500/50 transition-colors disabled:opacity-60"
                    >
                        <Search size={18} />
                        Resolver
                    </button>
                </div>
                <p className="text-xs text-zinc-600">
                    Detecta automaticamente: valor com formato de IP faz <strong>reverso</strong> (IP → nome), caso contrário <strong>direto</strong> (nome → IP). Escolher um servidor DNS específico resolve no domínio certo em ambientes multi-AD.
                </p>
            </div>

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col">
                {results.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-zinc-600">
                        <Globe size={48} className="mb-4 opacity-20" />
                        <p>As consultas DNS aparecem aqui.</p>
                    </div>
                ) : (
                    <div className="flex-1 overflow-auto custom-scrollbar p-3 space-y-2">
                        {results.map((r, i) => (
                            <div key={i} className="flex items-center gap-3 bg-zinc-950/60 border border-zinc-800 rounded-lg px-4 py-2.5 font-mono text-sm">
                                <span className="text-xs uppercase tracking-wide text-zinc-600 w-16 shrink-0">{r.kind === 'forward' ? 'Direto' : 'Reverso'}</span>
                                <span className="text-zinc-300">{r.query}</span>
                                <ArrowRight size={14} className="text-zinc-600 shrink-0" />
                                <span className={r.answer ? 'text-sky-400 font-medium' : 'text-zinc-600'}>
                                    {r.answer ?? 'sem resposta'}
                                </span>
                                {r.dnsServer && (
                                    <span className="ml-auto flex items-center gap-1 text-xs text-zinc-600 shrink-0">
                                        <Server size={11} /> {r.dnsServer}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
