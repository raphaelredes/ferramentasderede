import { X, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { Host } from '../../types';

interface AddHostModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAdd: (name: string, address: string, mac: string, ports: number[], group: string) => Promise<void>;
    isAdding: boolean;
    existingHosts: Host[];
}

export function AddHostModal({ isOpen, onClose, onAdd, isAdding, existingHosts }: AddHostModalProps) {
    const [name, setName] = useState('');
    const [address, setAddress] = useState('');
    const [group, setGroup] = useState('');

    const [mac, setMac] = useState('');
    const [portsStr, setPortsStr] = useState('');
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        // Check for duplicates
        const isDuplicate = existingHosts.some(h =>
            h.address.toLowerCase() === address.toLowerCase() ||
            (h.hostname && h.hostname.toLowerCase() === address.toLowerCase()) ||
            (h.ip && h.ip === address)
        );

        if (isDuplicate) {
            setError('Este host já existe no painel (IP ou Hostname duplicado).');
            return;
        }

        const ports = portsStr.split(',')
            .map(p => parseInt(p.trim()))
            .filter(p => !isNaN(p) && p > 0 && p <= 65535);

        await onAdd(name, address, mac, ports, group);
        setName('');
        setAddress('');
        setGroup('');
        setMac('');
        setPortsStr('');
        setError(null);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-xl font-bold text-white">Adicionar Novo Host</h3>
                    <button onClick={onClose} className="text-zinc-400 hover:text-white">
                        <X size={20} />
                    </button>
                </div>

                {error && (
                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                        <AlertCircle size={16} />
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Apelido</label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${name ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="Opcional (será resolvido se vazio)"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Endereço IP / Hostname</label>
                        <input
                            type="text"
                            required
                            value={address}
                            onChange={e => {
                                setAddress(e.target.value);
                                setError(null);
                            }}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${address ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="ex: 192.168.1.10"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Endereço MAC (Para WoL)</label>
                        <input
                            type="text"
                            value={mac}
                            onChange={e => setMac(e.target.value)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${mac ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="ex: 00:11:22:33:44:55"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Grupo (Opcional)</label>
                        <input
                            type="text"
                            value={group}
                            onChange={e => setGroup(e.target.value)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${group ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="ex: Servidores, Impressoras"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Monitorar Portas (Opcional)</label>
                        <input
                            type="text"
                            value={portsStr}
                            onChange={e => setPortsStr(e.target.value)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${portsStr ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="ex: 80, 443, 3389"
                        />
                    </div>
                    <div className="flex justify-end gap-2 mt-6">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-zinc-400 hover:text-white transition-colors"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            disabled={isAdding}
                            className="bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed text-blue-400 border border-blue-900/30 hover:border-blue-500/50 px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                        >
                            {isAdding && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400" />}
                            Adicionar
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
