import { Clock, AlertTriangle, Search } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface NtpResult {
    ok: boolean; error?: string;
    server?: string; offset_ms?: number; offset_seconds?: number;
    delay_ms?: number; stratum?: number; ref_id?: string;
    root_delay_ms?: number; root_dispersion_ms?: number; kerberos_risk?: boolean;
}

/** NTP query — clock offset/stratum. Skew breaks Kerberos in AD. */
export function NtpPanel() {
    const { showToast } = useToast();
    const [server, setServer] = usePersistedState('ntp_tool_server', '');
    const [result, setResult, clearResult] = usePersistedState<NtpResult | null>('ntp_tool_result', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('ntp_tool_last_run', null);
    const [busy, setBusy] = useState(false);

    const query = async () => {
        const s = server.trim();
        if (!s) { showToast('Informe um servidor NTP.', 'error'); return; }
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/ntp`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ server: s }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setResult(data);
            setLastRunAt(new Date().toISOString());
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        } finally { setBusy(false); }
    };

    const Cell = ({ label, value }: { label: string; value?: React.ReactNode }) => (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
            <div className="text-xs text-zinc-500 mb-1">{label}</div>
            <div className="font-mono text-zinc-100">{value ?? '—'}</div>
        </div>
    );

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800">
                <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Servidor NTP</label>
                    <input type="text" value={server} onChange={e => setServer(e.target.value)} placeholder="pool.ntp.org  ou  10.0.0.1 (DC)"
                        onKeyDown={e => { if (e.key === 'Enter' && !busy) query(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500" />
                </div>
                <button onClick={query} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-emerald-400 border border-emerald-900/30 hover:border-emerald-500/50 transition-colors disabled:opacity-60">
                    <Search size={18} /> Consultar
                </button>
            </div>

            {result && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={server || null}
                    onClear={() => { clearResult(); setLastRunAt(null); }}
                />
            )}

            <div className="flex-1 overflow-auto custom-scrollbar">

                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <Clock size={48} className="mb-4 opacity-20" />
                        <p>Consulta o offset do relógio e stratum de um servidor de tempo.</p>
                    </div>
                ) : result.ok ? (
                    <div className="space-y-3">
                        {result.kerberos_risk && (
                            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-semibold text-red-400 bg-red-500/10 border-red-900/40">
                                <AlertTriangle size={16} /> OFFSET &gt; 5 MIN — RISCO DE FALHA NO KERBEROS
                            </div>
                        )}
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <div className={clsx('rounded-lg p-3 border', Math.abs(result.offset_ms ?? 0) > 1000 ? 'bg-amber-500/5 border-amber-900/40' : 'bg-zinc-900 border-zinc-800')}>
                                <div className="text-xs text-zinc-500 mb-1">Offset do relógio</div>
                                <div className="font-mono text-zinc-100">{result.offset_ms} ms</div>
                            </div>
                            <Cell label="Delay (ida/volta)" value={`${result.delay_ms} ms`} />
                            <Cell label="Stratum" value={result.stratum} />
                            <Cell label="Referência" value={result.ref_id} />
                            <Cell label="Root delay" value={`${result.root_delay_ms} ms`} />
                            <Cell label="Root dispersion" value={`${result.root_dispersion_ms} ms`} />
                        </div>
                        <p className="text-xs text-zinc-600">Offset positivo = relógio local atrasado em relação ao servidor.</p>
                    </div>
                ) : (
                    <div className="text-red-400 text-sm">{result.error}</div>
                )}
            </div>
        </div>
    );
}
