import { useState } from 'react';
import { Globe, Search } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface HttpResult {
    ok: boolean; error?: string;
    url?: string; final_url?: string; method?: string; status?: number;
    ttfb_ms?: number; elapsed_ms?: number; redirected?: boolean;
    server?: string; content_type?: string; content_length?: number;
}

/** HTTP endpoint health/latency (TTFB/total, status) via requests. */
export function HttpPanel() {
    const { showToast } = useToast();
    const [url, setUrl] = useState('');
    const [method, setMethod] = useState('GET');
    const [verifyTls, setVerifyTls] = useState(true);
    const [result, setResult] = useState<HttpResult | null>(null);
    const [busy, setBusy] = useState(false);

    const check = async () => {
        const u = url.trim();
        if (!u) { showToast('Informe uma URL.', 'error'); return; }
        setBusy(true); setResult(null);
        try {
            const res = await fetch(`${API_BASE}/tools/http`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: u, method, verify_tls: verifyTls }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setResult(data);
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        } finally { setBusy(false); }
    };

    const statusColor = (s?: number) => {
        if (!s) return 'text-zinc-300';
        if (s < 300) return 'text-green-400';
        if (s < 400) return 'text-sky-400';
        if (s < 500) return 'text-amber-400';
        return 'text-red-400';
    };
    const Cell = ({ label, value, cls }: { label: string; value?: React.ReactNode; cls?: string }) => (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
            <div className="text-xs text-zinc-500 mb-1">{label}</div>
            <div className={clsx('font-mono', cls ?? 'text-zinc-100')}>{value ?? '—'}</div>
        </div>
    );

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-3">
                <div className="flex gap-4 items-end">
                    <div className="flex-1 space-y-2">
                        <label className="text-sm font-medium text-zinc-400">URL</label>
                        <input type="text" value={url} onChange={e => setUrl(e.target.value)} placeholder="http://intranet.dominio.local/health"
                            onKeyDown={e => { if (e.key === 'Enter' && !busy) check(); }}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500" />
                    </div>
                    <div className="space-y-2 w-28">
                        <label className="text-sm font-medium text-zinc-400">Método</label>
                        <select value={method} onChange={e => setMethod(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                            <option value="GET">GET</option>
                            <option value="HEAD">HEAD</option>
                        </select>
                    </div>
                    <button onClick={check} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-pink-400 border border-pink-900/30 hover:border-pink-500/50 transition-colors disabled:opacity-60">
                        <Search size={18} /> Testar
                    </button>
                </div>
                <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer select-none w-fit">
                    <input type="checkbox" checked={verifyTls} onChange={e => setVerifyTls(e.target.checked)} className="accent-pink-500" />
                    Verificar certificado TLS (desmarque para hosts com cert interno/inválido)
                </label>
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar">
                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <Globe size={48} className="mb-4 opacity-20" />
                        <p>Mede tempo de resposta (TTFB/total) e status de um endpoint web.</p>
                    </div>
                ) : result.ok ? (
                    <div className="space-y-3">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <Cell label="Status" value={result.status} cls={statusColor(result.status)} />
                            <Cell label="TTFB" value={`${result.ttfb_ms} ms`} />
                            <Cell label="Tempo total" value={`${result.elapsed_ms} ms`} />
                            <Cell label="Redirecionou" value={result.redirected ? 'Sim' : 'Não'} />
                            <Cell label="Servidor" value={result.server} />
                            <Cell label="Content-Type" value={result.content_type} />
                            <Cell label="Tamanho" value={result.content_length != null ? `${result.content_length} B` : '—'} />
                        </div>
                        {result.redirected && <p className="text-xs text-zinc-500 font-mono">→ {result.final_url}</p>}
                    </div>
                ) : (
                    <div className="text-red-400 text-sm">{result.error}</div>
                )}
            </div>
        </div>
    );
}
