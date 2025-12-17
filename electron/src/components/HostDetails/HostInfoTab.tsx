import React from 'react';
import { Monitor, Cpu, HardDrive, Network } from 'lucide-react';

interface HostInfoTabProps {
    systemInfo: any;
    teamViewerId: string | null;
    formatDate: (date: string) => string;
}

export const HostInfoTab: React.FC<HostInfoTabProps> = ({ systemInfo, teamViewerId, formatDate }) => {
    if (!systemInfo) return <div className="text-zinc-400">Carregando informações...</div>;
    if (systemInfo.error) return <div className="text-red-400">Erro: {systemInfo.error}</div>;

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                    <Monitor size={20} className="text-blue-400" />
                    Sistema Operacional
                </h3>
                <div className="space-y-3">
                    <div className="flex justify-between">
                        <span className="text-zinc-400">OS</span>
                        <span className="text-white">{systemInfo.OS}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Versão</span>
                        <span className="text-white">{systemInfo.OS_Version}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Instalação</span>
                        <span className="text-white">{formatDate(systemInfo.InstallDate)}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Último Boot</span>
                        <span className="text-white">{formatDate(systemInfo.LastBootUpTime)}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Uptime</span>
                        <span className="text-white">
                            {systemInfo.Uptime ?
                                `${systemInfo.Uptime.uptime_days}d ${systemInfo.Uptime.uptime_hours}h` :
                                'N/A'}
                        </span>
                    </div>
                </div>
            </div>

            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                    <Cpu size={20} className="text-purple-400" />
                    Hardware
                </h3>
                <div className="space-y-3">
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Processador</span>
                        <span className="text-white text-right max-w-[200px] truncate" title={systemInfo.CPU}>
                            {systemInfo.CPU}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Memória RAM</span>
                        <span className="text-white">{systemInfo.RAM_GB} GB</span>
                    </div>
                </div>
            </div>

            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50 md:col-span-2">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                    <HardDrive size={20} className="text-green-400" />
                    Armazenamento
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {(Array.isArray(systemInfo.Disks) ? systemInfo.Disks : (systemInfo.Disks ? [systemInfo.Disks] : [])).map((disk: any) => (
                        <div key={disk.DeviceID} className="bg-zinc-900/50 p-4 rounded-lg border border-zinc-700/50">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-white font-medium">{disk.DeviceID} ({disk.VolumeName || 'Local Disk'})</span>
                                <span className="text-xs text-zinc-500">{disk.Free_GB} GB livres</span>
                            </div>
                            <div className="w-full bg-zinc-700 h-2 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${(disk.Free_GB / disk.Total_GB) < 0.1 ? 'bg-red-500' : 'bg-blue-500'
                                        }`}
                                    style={{ width: `${((disk.Total_GB - disk.Free_GB) / disk.Total_GB) * 100}%` }}
                                />
                            </div>
                            <div className="mt-2 text-xs text-zinc-400 text-right">
                                Total: {disk.Total_GB} GB
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                    <Network size={20} className="text-orange-400" />
                    Rede
                </h3>
                <div className="space-y-3">
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Interface</span>
                        <span className="text-white text-right max-w-[200px] truncate" title={systemInfo.Interface}>
                            {systemInfo.Interface || 'N/A'}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Velocidade do Link</span>
                        <span className="text-white">{systemInfo.LinkSpeed || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Máscara de Subrede</span>
                        <span className="text-white">{systemInfo.SubnetMask || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Gateway Padrão</span>
                        <span className="text-white">{systemInfo.Gateway || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Servidores DNS</span>
                        <span className="text-white text-right max-w-[200px] truncate" title={systemInfo.DNSServers}>
                            {systemInfo.DNSServers || 'N/A'}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-zinc-400">Servidor DHCP</span>
                        <span className="text-white">{systemInfo.DHCPServer || 'N/A'}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};
