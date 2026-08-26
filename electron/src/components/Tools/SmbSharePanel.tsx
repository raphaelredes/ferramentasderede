import { useState } from 'react';
import { FolderGit2, Play, AlertCircle, HardDrive } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface SMBShare {
    name: string;
    path: string;
    description: string;
    is_hidden: boolean;
    type: string;
}

export function SmbSharePanel() {
    const { showToast } = useToast();
    const [target, setTarget] = useState('192.168.1.1');
    const [loading, setLoading] = useState(false);
    const [shares, setShares] = useState<SMBShare[]>([]);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const scanShares = async () => {
        if (!target.trim()) return;
        setLoading(true);
        setErrorMsg(null);
        setShares([]);

        try {
            const res = await fetch(`${API_BASE}/l2/smb-shares`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: target.trim() })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (data.shares && data.shares.length > 0) {
                setShares(data.shares);
                showToast(`${data.shares.length} compartilhamentos encontrados!`, 'success');
            } else {
                setErrorMsg(data.error || 'Nenhum compartilhamento detectado.');
                showToast('Nenhum compartilhamento listado.', 'warning');
            }
        } catch (err: any) {
            setErrorMsg(`Erro ao escanear SMB: ${err.message}`);
            showToast(`Falha no scan SMB: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-zinc-900/60 rounded-xl p-5 border border-zinc-800 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                    <FolderGit2 className="text-blue-400" size={20} />
                    <div>
                        <h3 className="text-base font-semibold text-zinc-100">Enumeração de Compartilhamentos SMB / CIFS</h3>
                        <p className="text-xs text-zinc-400">Descobre pastas públicas e administrativas (C$, ADMIN$) no host</p>
                    </div>
                </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
                <input
                    type="text"
                    placeholder="IP ou Hostname do alvo (ex: 192.168.1.100)"
                    value={target}
                    onChange={e => setTarget(e.target.value)}
                    className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 flex-1 min-w-[220px] focus:outline-none focus:border-blue-500"
                />
                <button
                    onClick={scanShares}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg shadow transition-colors"
                >
                    <Play size={15} />
                    {loading ? 'Escaneando...' : 'Listar Compartilhamentos'}
                </button>
            </div>

            {errorMsg && (
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl flex items-center gap-3 text-amber-400 text-xs">
                    <AlertCircle size={18} className="shrink-0" />
                    <span>{errorMsg}</span>
                </div>
            )}

            {shares.length > 0 && (
                <div className="space-y-3">
                    <div className="text-xs text-zinc-400">
                        Total de Compartilhamentos: <strong className="text-zinc-200">{shares.length}</strong>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {shares.map((share, idx) => (
                            <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs space-y-2">
                                <div className="flex items-center justify-between">
                                    <div className="font-semibold text-zinc-200 flex items-center gap-2">
                                        <HardDrive size={16} className={share.is_hidden ? 'text-amber-400' : 'text-blue-400'} />
                                        <span>{share.name}</span>
                                    </div>
                                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${share.is_hidden ? 'bg-amber-950 text-amber-300 border border-amber-800' : 'bg-blue-950 text-blue-300 border border-blue-800'}`}>
                                        {share.type}
                                    </span>
                                </div>
                                <div className="text-zinc-400 font-mono text-[11px] truncate">
                                    {share.path || `\\\\${target}\\${share.name}`}
                                </div>
                                {share.description && (
                                    <div className="text-zinc-500 text-[11px]">{share.description}</div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
