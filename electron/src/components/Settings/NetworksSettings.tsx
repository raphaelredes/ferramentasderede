import { useEffect, useState } from 'react';
import { Plus, Trash2, RefreshCw, Network as NetworkIcon, Wifi } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { HelpButton } from '../HelpButton';
import type { NetworkConfig } from '../../pages/Settings';

interface DetectedInterface {
    name: string;
    ip: string;
    netmask: string;
    prefix: number;
    cidr: string;
    network: string;
    is_up: boolean;
    mac?: string;
}

interface Props {
    networks: NetworkConfig[];
    onChange: (networks: NetworkConfig[]) => void;
}

const emptyNetwork = (): NetworkConfig => ({
    id: crypto.randomUUID(),
    name: '',
    cidr: '',
    enabled: true,
});

export function NetworksSettings({ networks, onChange }: Props) {
    const { showToast } = useToast();
    const [interfaces, setInterfaces] = useState<DetectedInterface[]>([]);
    const [isDetecting, setIsDetecting] = useState(false);

    const detectInterfaces = async () => {
        setIsDetecting(true);
        try {
            const res = await fetch(`${API_BASE}/network/interfaces`);
            if (!res.ok) throw new Error('Falha ao listar NICs');
            const data: DetectedInterface[] = await res.json();
            setInterfaces(data);
            if (data.length === 0) showToast('Nenhuma interface IPv4 ativa detectada.', 'info');
        } catch (e) {
            console.error(e);
            showToast('Erro ao detectar interfaces.', 'error');
        } finally {
            setIsDetecting(false);
        }
    };

    useEffect(() => {
        detectInterfaces();
    }, []);

    const isImported = (cidr: string, sourceIp: string) =>
        networks.some(n => n.cidr === cidr && n.source_ip === sourceIp);

    const importInterface = (iface: DetectedInterface) => {
        if (isImported(iface.cidr, iface.ip)) {
            showToast('Esta NIC já está cadastrada.', 'info');
            return;
        }
        onChange([
            ...networks,
            {
                id: crypto.randomUUID(),
                name: iface.name,
                cidr: iface.cidr,
                source_ip: iface.ip,
                enabled: true,
            },
        ]);
    };

    const updateNetwork = (id: string, patch: Partial<NetworkConfig>) => {
        onChange(networks.map(n => (n.id === id ? { ...n, ...patch } : n)));
    };

    const removeNetwork = (id: string) => {
        onChange(networks.filter(n => n.id !== id));
    };

    const addEmpty = () => onChange([...networks, emptyNetwork()]);

    return (
        <div className="space-y-8 animate-fadeIn">
            <div>
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <Wifi size={16} className="text-zinc-400" />
                        <h3 className="text-sm font-medium text-zinc-200">Interfaces detectadas</h3>
                        <HelpButton
                            title="Interfaces detectadas"
                            description="NICs locais ativas. Clique em 'Importar' para cadastrar a sub-rede daquela NIC como uma rede gerenciada (com source IP automático)."
                        />
                    </div>
                    <button
                        onClick={detectInterfaces}
                        disabled={isDetecting}
                        className="flex items-center gap-1.5 text-xs text-zinc-300 hover:text-white px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors disabled:opacity-50"
                    >
                        <RefreshCw size={12} className={isDetecting ? 'animate-spin' : ''} />
                        Re-detectar
                    </button>
                </div>
                {interfaces.length === 0 ? (
                    <p className="text-xs text-zinc-500">Nenhuma interface ativa.</p>
                ) : (
                    <ul className="space-y-2">
                        {interfaces.map(iface => {
                            const already = isImported(iface.cidr, iface.ip);
                            return (
                                <li
                                    key={`${iface.name}-${iface.ip}`}
                                    className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5"
                                >
                                    <div className="flex flex-col">
                                        <span className="text-sm text-white">{iface.name}</span>
                                        <span className="text-xs text-zinc-500 font-mono">
                                            {iface.ip} / {iface.cidr}
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => importInterface(iface)}
                                        disabled={already}
                                        className="text-xs px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
                                    >
                                        {already ? 'Importada' : 'Importar'}
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            <div>
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <NetworkIcon size={16} className="text-zinc-400" />
                        <h3 className="text-sm font-medium text-zinc-200">
                            Redes gerenciadas ({networks.length})
                        </h3>
                        <HelpButton
                            title="Redes gerenciadas"
                            description="Sub-redes que o app conhece. Cada uma pode ter um source IP (NIC), DNS server e domínio AD próprios. Use isto quando há mais de uma VLAN/domínio na sua rede."
                        />
                    </div>
                    <button
                        onClick={addEmpty}
                        className="flex items-center gap-1.5 text-xs text-zinc-300 hover:text-white px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                    >
                        <Plus size={12} />
                        Adicionar rede
                    </button>
                </div>

                {networks.length === 0 ? (
                    <p className="text-xs text-zinc-500 bg-zinc-950/50 border border-zinc-800 border-dashed rounded-lg p-6 text-center">
                        Nenhuma rede cadastrada. Importe uma das interfaces detectadas acima ou adicione manualmente.
                    </p>
                ) : (
                    <div className="space-y-3">
                        {networks.map(net => (
                            <div
                                key={net.id}
                                className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 space-y-3"
                            >
                                <div className="flex items-center justify-between gap-4">
                                    <input
                                        type="text"
                                        placeholder="Nome (ex: Domínio A - VLAN 10)"
                                        value={net.name}
                                        onChange={e => updateNetwork(net.id, { name: e.target.value })}
                                        className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                    />
                                    <label className="flex items-center gap-2 text-xs text-zinc-400 select-none">
                                        <input
                                            type="checkbox"
                                            checked={net.enabled}
                                            onChange={e => updateNetwork(net.id, { enabled: e.target.checked })}
                                            className="accent-blue-500"
                                        />
                                        Ativa
                                    </label>
                                    <button
                                        onClick={() => removeNetwork(net.id)}
                                        className="p-2 text-zinc-500 hover:text-red-400 transition-colors"
                                        title="Remover"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="text-xs text-zinc-500 mb-1 block">CIDR</label>
                                        <input
                                            type="text"
                                            placeholder="10.10.0.0/24"
                                            value={net.cidr}
                                            onChange={e => updateNetwork(net.id, { cidr: e.target.value })}
                                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-zinc-500 mb-1 block">Source IP (NIC)</label>
                                        <input
                                            type="text"
                                            placeholder="opcional"
                                            value={net.source_ip ?? ''}
                                            onChange={e => updateNetwork(net.id, { source_ip: e.target.value || undefined })}
                                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-zinc-500 mb-1 block">DNS server</label>
                                        <input
                                            type="text"
                                            placeholder="opcional"
                                            value={net.dns_server ?? ''}
                                            onChange={e => updateNetwork(net.id, { dns_server: e.target.value || undefined })}
                                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs text-zinc-500 mb-1 block">Domínio AD</label>
                                        <input
                                            type="text"
                                            placeholder="dominio.local (opcional)"
                                            value={net.domain ?? ''}
                                            onChange={e => updateNetwork(net.id, { domain: e.target.value || undefined })}
                                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                        />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
