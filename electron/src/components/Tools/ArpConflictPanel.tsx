import { useState, useEffect } from 'react';
import { ShieldAlert, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface ARPEntry {
    interface: string;
    ip: string;
    mac: string;
    type: string;
}

interface ARPConflict {
    type: string;
    ip: string;
    macs: string[];
    severity: string;
    description: string;
}

export function ArpConflictPanel({ defaultSourceIp }: { defaultSourceIp?: string }) {
    const { showToast } = useToast();
    const [loading, setLoading] = useState(false);
    const [entries, setEntries] = useState<ARPEntry[]>([]);
    const [conflicts, setConflicts] = useState<ARPConflict[]>([]);
    const [lastChecked, setLastChecked] = useState<string | null>(null);

    const checkArp = async () => {
        setLoading(true);
        try {
            const url = defaultSourceIp ? `${API_BASE}/l2/arp-conflicts?interface_ip=${defaultSourceIp}` : `${API_BASE}/l2/arp-conflicts`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setEntries(data.entries || []);
            setConflicts(data.conflicts || []);
            setLastChecked(new Date().toLocaleTimeString());
            
            if (data.conflicts && data.conflicts.length > 0) {
                showToast(`Alerta: ${data.conflicts.length} conflito(s) de IP detectado(s)!`, 'error');
            } else {
                showToast('Tabela ARP auditada. Nenhum conflito encontrado.', 'success');
            }
        } catch (err: any) {
            showToast(`Erro na auditoria ARP: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        checkArp();
    }, [defaultSourceIp]);

    return (
        <div className="bg-zinc-900/60 rounded-xl p-5 border border-zinc-800 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                    <ShieldAlert className="text-blue-400" size={20} />
                    <div>
                        <h3 className="text-base font-semibold text-zinc-100">Auditoria de Tabela ARP & Conflitos de IP</h3>
                        <p className="text-xs text-zinc-400">Detecta IPs duplicados respondendo por múltiplos MAC addresses (ARP Spoof / Rogue Gateway)</p>
                    </div>
                </div>
                <button
                    onClick={checkArp}
                    disabled={loading}
                    className="flex items-center gap-2 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg shadow transition-colors"
                >
                    <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                    {loading ? 'Verificando...' : 'Reescanear ARP'}
                </button>
            </div>

            {conflicts.length > 0 ? (
                <div className="p-4 bg-rose-950/40 border border-rose-800/80 rounded-xl space-y-3">
                    <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
                        <AlertTriangle size={18} />
                        <span>Conflito Crítico de IP Detectado!</span>
                    </div>
                    {conflicts.map((c, idx) => (
                        <div key={idx} className="bg-rose-950/60 p-3 rounded-lg border border-rose-900/80 text-xs text-rose-200 space-y-1">
                            <div className="font-semibold text-rose-300">IP em Conflito: {c.ip}</div>
                            <div>{c.description}</div>
                            <div className="text-[11px] font-mono text-rose-400">MACs Detectados: {c.macs.join(', ')}</div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="p-4 bg-emerald-950/30 border border-emerald-800/50 rounded-xl flex items-center gap-3 text-emerald-400 text-xs">
                    <CheckCircle size={18} className="shrink-0" />
                    <span>Nenhum conflito de IP detectado na sub-rede ativa. ({entries.length} entradas válidas no cache ARP)</span>
                </div>
            )}

            {entries.length > 0 && (
                <div className="space-y-2">
                    <div className="text-xs text-zinc-400 flex justify-between">
                        <span>Entradas no Cache ARP: <strong className="text-zinc-200">{entries.length}</strong></span>
                        {lastChecked && <span>Última atualização: {lastChecked}</span>}
                    </div>
                    <div className="max-h-[260px] overflow-y-auto border border-zinc-800 rounded-lg">
                        <table className="w-full text-left text-xs">
                            <thead className="bg-zinc-950 text-zinc-400 sticky top-0 border-b border-zinc-800">
                                <tr>
                                    <th className="p-2.5">Endereço IP</th>
                                    <th className="p-2.5">Endereço MAC</th>
                                    <th className="p-2.5">Tipo</th>
                                    <th className="p-2.5">Interface</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800/60 bg-zinc-900/40 font-mono text-[11px]">
                                {entries.map((entry, idx) => (
                                    <tr key={idx} className="hover:bg-zinc-800/40">
                                        <td className="p-2 text-zinc-200">{entry.ip}</td>
                                        <td className="p-2 text-zinc-400">{entry.mac}</td>
                                        <td className="p-2 text-zinc-500">{entry.type}</td>
                                        <td className="p-2 text-zinc-500">{entry.interface}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
