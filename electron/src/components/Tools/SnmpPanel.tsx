import { useState } from 'react';
import { Router, Search } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface SnmpResult {
    ok: boolean; error?: string;
    host?: string; sysDescr?: string; sysName?: string; sysUpTime?: string;
    sysContact?: string; sysLocation?: string; sysObjectID?: string; ifNumber?: number;
}

/** SNMP system query for switches/routers (sysDescr/sysName/uptime/ifNumber). */
export function SnmpPanel() {
    const { showToast } = useToast();
    const [host, setHost] = useState('');
    const [community, setCommunity] = useState('public');
    const [version, setVersion] = useState('2c');
    const [result, setResult] = useState<SnmpResult | null>(null);
    const [busy, setBusy] = useState(false);

    const query = async () => {
        const h = host.trim();
        if (!h) { showToast('Informe o host SNMP.', 'error'); return; }
        setBusy(true); setResult(null);
        try {
            const res = await fetch(`${API_BASE}/tools/snmp`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host: h, community, version }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setResult(data);
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        } finally { setBusy(false); }
    };

    const Row = ({ label, value }: { label: string; value?: React.ReactNode }) => (
        <div className="flex gap-3 py-1.5 border-b border-zinc-900 text-sm">
            <span className="text-zinc-500 w-32 shrink-0">{label}</span>
            <span className="text-zinc-200 font-mono break-all">{value ?? '—'}</span>
        </div>
    );

    return (
        <div className="flex-1 flex flex-col space-y-4 min-h-0">
            <div className="flex gap-4 items-end bg-zinc-900 p-4 rounded-xl border border-zinc-800 flex-wrap">
                <div className="flex-1 min-w-48 space-y-2">
                    <label className="text-sm font-medium text-zinc-400">Host (switch/roteador)</label>
                    <input type="text" value={host} onChange={e => setHost(e.target.value)} placeholder="10.0.0.1"
                        onKeyDown={e => { if (e.key === 'Enter' && !busy) query(); }}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 font-mono placeholder:text-zinc-500" />
                </div>
                <div className="space-y-2 w-44">
                    <label className="text-sm font-medium text-zinc-400">Community (read-only)</label>
                    <input type="text" value={community} onChange={e => setCommunity(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 font-mono" />
                </div>
                <div className="space-y-2 w-24">
                    <label className="text-sm font-medium text-zinc-400">Versão</label>
                    <select value={version} onChange={e => setVersion(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                        <option value="2c">v2c</option>
                        <option value="1">v1</option>
                    </select>
                </div>
                <button onClick={query} disabled={busy} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 transition-colors disabled:opacity-60">
                    <Search size={18} /> Consultar
                </button>
            </div>

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 p-5 overflow-auto custom-scrollbar">
                {!result ? (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                        <Router size={48} className="mb-4 opacity-20" />
                        <p>Lê dados de um equipamento de rede via SNMP (nome, descrição, uptime, nº de portas).</p>
                    </div>
                ) : result.ok ? (
                    <div>
                        <Row label="Nome (sysName)" value={result.sysName} />
                        <Row label="Descrição" value={result.sysDescr} />
                        <Row label="Uptime" value={result.sysUpTime} />
                        <Row label="Localização" value={result.sysLocation} />
                        <Row label="Contato" value={result.sysContact} />
                        <Row label="Interfaces" value={result.ifNumber} />
                        <Row label="Object ID" value={result.sysObjectID} />
                    </div>
                ) : (
                    <div className="text-red-400 text-sm">{result.error}</div>
                )}
            </div>
        </div>
    );
}
