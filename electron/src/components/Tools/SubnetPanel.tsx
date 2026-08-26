import { Calculator, Binary } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface SubnetResult {
    ok: boolean; error?: string;
    network?: string; prefix?: number; netmask?: string; broadcast?: string;
    hostmask?: string; num_addresses?: number; num_usable?: number;
    first_host?: string; last_host?: string; is_private?: boolean; cidr?: string;
    split_count?: number; subnets?: string[]; split_truncated?: boolean; split_error?: string;
}

/** Subnet/CIDR calculator (pure stdlib ipaddress on the backend). */
export function SubnetPanel() {
    const { showToast } = useToast();
    const [cidr, setCidr] = usePersistedState('subnet_tool_cidr', '');
    const [splitPrefix, setSplitPrefix] = usePersistedState('subnet_tool_split_prefix', '');
    const [result, setResult, clearResult] = usePersistedState<SubnetResult | null>('subnet_tool_result', null);
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('subnet_tool_last_run', null);

    const calc = async () => {
        const c = cidr.trim();
        if (!c) { showToast('Informe um CIDR (ex.: 10.0.0.0/24).', 'error'); return; }
        try {
            const body: Record<string, unknown> = { cidr: c };
            const sp = parseInt(splitPrefix, 10);
            if (sp) body.split_prefix = sp;
            const res = await fetch(`${API_BASE}/tools/subnet`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setResult(data);
            setLastRunAt(new Date().toISOString());
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        }
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
                    <label className="text-sm font-medium text-zinc-400">CIDR ou IP/máscara</label>
                    <input type="text" value={cidr} onChange={e => setCidr(e.target.value)} placeholder="10.20.30.0/24"
                        onKeyDown={e => { if (e.key === 'Enter') calc(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500" />
                </div>
                <div className="space-y-2 w-40">
                    <label className="text-sm font-medium text-zinc-400">Dividir em /</label>
                    <input type="text" value={splitPrefix} onChange={e => setSplitPrefix(e.target.value)} placeholder="opcional (ex.: 26)"
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500" />
                </div>
                <button onClick={calc} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-orange-400 border border-orange-900/30 hover:border-orange-500/50 transition-colors">
                    <Calculator size={18} /> Calcular
                </button>
            </div>

            {result && lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={cidr || null}
                    onClear={() => { clearResult(); setLastRunAt(null); }}
                />
            )}

            <div className="flex-1 overflow-auto custom-scrollbar">

                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <Binary size={48} className="mb-4 opacity-20" />
                        <p>Calcula rede, broadcast, faixa usável, máscara e wildcard de um CIDR.</p>
                    </div>
                ) : result.ok ? (
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <Cell label="Rede" value={`${result.network}/${result.prefix}`} />
                            <Cell label="Máscara" value={result.netmask} />
                            <Cell label="Broadcast" value={result.broadcast} />
                            <Cell label="Wildcard" value={result.hostmask} />
                            <Cell label="1º host usável" value={result.first_host} />
                            <Cell label="Último host usável" value={result.last_host} />
                            <Cell label="Total de endereços" value={result.num_addresses?.toLocaleString('pt-BR')} />
                            <Cell label="Hosts usáveis" value={result.num_usable?.toLocaleString('pt-BR')} />
                            <Cell label="Tipo" value={result.is_private ? 'Privada (RFC1918)' : 'Pública'} />
                        </div>
                        {result.subnets && result.subnets.length > 0 && (
                            <div>
                                <p className="text-sm text-zinc-400 mb-2">Sub-redes ({result.split_count}{result.split_truncated ? ', mostrando as primeiras 1024' : ''}):</p>
                                <div className="bg-black rounded-lg border border-zinc-800 p-3 max-h-64 overflow-auto custom-scrollbar grid grid-cols-2 md:grid-cols-3 gap-1 font-mono text-sm text-zinc-300">
                                    {result.subnets.map((s, i) => <div key={i}>{s}</div>)}
                                </div>
                            </div>
                        )}
                        {result.split_error && <p className="text-sm text-amber-400">{result.split_error}</p>}
                    </div>
                ) : (
                    <div className="text-red-400 text-sm">{result.error}</div>
                )}
            </div>
        </div>
    );
}
