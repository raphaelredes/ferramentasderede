import React from 'react';
import { X, Monitor, Users, ArrowUpDown } from 'lucide-react';
import { Host } from '../../types';
import { useToast } from '../../contexts/ToastContext';

interface RemoteAccessModalProps {
    isOpen: boolean;
    onClose: () => void;
    host: Host;
}

export const RemoteAccessModal: React.FC<RemoteAccessModalProps> = ({ isOpen, onClose, host }) => {
    const { showToast } = useToast();
    const [localDomain, setLocalDomain] = React.useState<string>('');

    React.useEffect(() => {
        if (isOpen) {
            window.electron.getLocalDomain().then(setLocalDomain).catch(console.error);
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleLaunchRdp = async () => {
        try {
            await window.electron.launchRdp(host.ip || host.address);
            onClose();
        } catch (error) {
            console.error('Failed to launch RDP:', error);
            showToast('Falha ao iniciar RDP', 'error');
        }
    };

    const handleLaunchMsra = async (forceOtherUser = false) => {
        try {
            let asOtherUser = forceOtherUser;

            // Auto-detect domain mismatch if not forced
            if (!asOtherUser && host.domain && localDomain) {
                const hostDomain = host.domain.toLowerCase();
                const myDomain = localDomain.toLowerCase();

                // Compare domains (handling FQDN vs NetBIOS if possible, but simple string check for now)
                // If host domain is not part of my domain and vice versa
                if (!hostDomain.includes(myDomain) && !myDomain.includes(hostDomain)) {
                    console.log(`Domain mismatch detected: Host=${hostDomain}, Local=${myDomain}. Switching to 'Run as other user'.`);
                    asOtherUser = true;
                    showToast('Domínio diferente detectado. Solicitando credenciais...', 'info');
                }
            }

            await window.electron.launchMsra(host.ip || host.address, asOtherUser);
            onClose();
        } catch (error) {
            console.error('Failed to launch MSRA:', error);
            showToast('Falha ao iniciar Assistência Remota', 'error');
        }
    };

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-zinc-800 bg-zinc-900/30">
                    <div>
                        <h2 className="text-xl font-semibold text-white flex items-center gap-3">
                            <div className="p-2 bg-blue-500/10 rounded-lg">
                                <Monitor size={24} className="text-blue-400" />
                            </div>
                            Acesso Remoto
                        </h2>
                        <p className="text-zinc-400 text-sm mt-1 ml-12">Escolha uma ferramenta para conectar</p>
                    </div>
                    <button onClick={onClose} className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-all">
                        <X size={20} />
                    </button>
                </div>

                {/* Host Info */}
                <div className="px-6 py-4 bg-zinc-900/50 border-b border-zinc-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]"></div>
                        <div>
                            <div className="text-white font-medium">{host.name || host.hostname || host.address}</div>
                            <div className="text-zinc-500 text-xs font-mono">{host.ip || host.address}</div>
                        </div>
                    </div>
                    <div className="px-3 py-1 rounded-full bg-zinc-800 text-zinc-400 text-xs border border-zinc-700">
                        {host.vendor || "Genérico"}
                    </div>
                </div>

                {/* Tools Grid */}
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* RDP Card */}
                    <button
                        onClick={handleLaunchRdp}
                        className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-blue-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                        <div className="p-3 bg-zinc-800 group-hover:bg-blue-500/20 w-fit rounded-lg transition-colors">
                            <Monitor size={24} className="text-zinc-400 group-hover:text-blue-400 transition-colors" />
                        </div>
                        <div>
                            <div className="font-medium text-white group-hover:text-blue-400 transition-colors">RDP</div>
                            <div className="text-sm text-zinc-500">Conexão de Área de Trabalho Remota</div>
                        </div>
                    </button>

                    {/* MSRA Card */}
                    <div className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-purple-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

                        <div className="flex items-start justify-between relative z-10">
                            <div className="p-3 bg-zinc-800 group-hover:bg-purple-500/20 w-fit rounded-lg transition-colors">
                                <Users size={24} className="text-zinc-400 group-hover:text-purple-400 transition-colors" />
                            </div>

                            {/* Secondary Action Menu / Button */}
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleLaunchMsra(true);
                                }}
                                className="p-2 text-zinc-500 hover:text-purple-400 hover:bg-purple-500/10 rounded-lg transition-all"
                                title="Executar como outro usuário"
                            >
                                <Users size={16} />
                            </button>
                        </div>

                        <div className="cursor-pointer relative z-10" onClick={() => handleLaunchMsra(false)}>
                            <div className="font-medium text-white group-hover:text-purple-400 transition-colors">Assistência Remota</div>
                            <div className="text-sm text-zinc-500">Solicitar controle via MSRA</div>
                        </div>
                    </div>

                    {/* TeamViewer Card */}
                    {host.teamviewer_id && (
                        <button
                            onClick={() => {
                                if (host.teamviewer_id) {
                                    // Copy to clipboard as backup/convenience
                                    navigator.clipboard.writeText(host.teamviewer_id);

                                    showToast('Abrindo TeamViewer em 3s... ID copiado para a área de transferência!', 'info');

                                    setTimeout(() => {
                                        // Launch with ID
                                        window.electron.launchTeamViewer(host.teamviewer_id);
                                        onClose();
                                    }, 3000);
                                }
                            }}
                            className="relative group p-4 bg-zinc-900/50 hover:bg-zinc-800 border border-zinc-800 hover:border-cyan-500/50 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden md:col-span-2"
                        >
                            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="flex items-center gap-4">
                                <div className="p-3 bg-zinc-800 group-hover:bg-cyan-500/20 w-fit rounded-lg transition-colors">
                                    <ArrowUpDown size={24} className="text-zinc-400 group-hover:text-cyan-400 transition-colors rotate-45" />
                                </div>
                                <div>
                                    <div className="font-medium text-white group-hover:text-cyan-400 transition-colors">TeamViewer</div>
                                    <div className="text-sm text-zinc-500 flex items-center gap-2">
                                        ID: <span className="font-mono text-zinc-400">{host.teamviewer_id}</span>
                                        <span className="text-xs bg-zinc-800 px-2 py-0.5 rounded text-zinc-500">Conectar Automaticamente</span>
                                    </div>
                                </div>
                            </div>
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};
