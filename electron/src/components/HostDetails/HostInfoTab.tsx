import React, { useState } from 'react';
import { Monitor, Cpu, HardDrive, Network, User, Shield, Copy, Check, ExternalLink, Activity } from 'lucide-react';
import { useToast } from '../../contexts/ToastContext';

interface HostInfoTabProps {
    systemInfo: any;
    teamViewerId: string | null;
    formatDate: (date: string) => string;
}

export const HostInfoTab: React.FC<HostInfoTabProps> = ({ systemInfo, teamViewerId, formatDate }) => {
    const { showToast } = useToast();
    const [copiedField, setCopiedField] = useState<string | null>(null);

    if (!systemInfo) return <div className="p-8 text-center text-zinc-400">Carregando informações do sistema...</div>;
    if (systemInfo.error) {
        return (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-red-400">
                <p className="font-semibold mb-1">Falha na Coleta de Informações</p>
                <p className="text-sm opacity-90">{systemInfo.error}</p>
            </div>
        );
    }

    const handleCopy = (text: string, fieldName: string, label: string) => {
        if (!text || text === 'N/A') return;
        navigator.clipboard.writeText(text);
        setCopiedField(fieldName);
        showToast(`${label} copiado!`, 'success');
        setTimeout(() => setCopiedField(null), 2000);
    };

    const effectiveTvId = (teamViewerId && teamViewerId !== 'N/A' && teamViewerId !== 'Unknown')
        ? teamViewerId
        : (systemInfo.TeamViewerID && systemInfo.TeamViewerID !== 'N/A' && systemInfo.TeamViewerID !== 'Unknown')
            ? systemInfo.TeamViewerID
            : null;

    const handleLaunchTv = (id: string) => {
        const clean = id.replace(/\s+/g, '');
        if (window.electron?.launchTeamViewer) {
            window.electron.launchTeamViewer(clean);
            showToast(`Iniciando TeamViewer para ID ${clean}...`, 'info');
        } else {
            handleCopy(clean, 'tvid', 'ID TeamViewer');
        }
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Usuário Ativo & Suporte Remoto */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50 md:col-span-2 flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
                <div className="flex items-center gap-3.5">
                    <div className="p-3 bg-blue-500/10 text-blue-400 rounded-xl border border-blue-500/20">
                        <User size={24} />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Usuário Conectado</span>
                            {systemInfo.CurrentUser && systemInfo.CurrentUser !== 'N/A' && (
                                <button
                                    onClick={() => handleCopy(systemInfo.CurrentUser, 'user', 'Usuário')}
                                    className="p-1 hover:bg-zinc-700/50 rounded text-zinc-400 hover:text-white transition-colors"
                                    title="Copiar usuário"
                                >
                                    {copiedField === 'user' ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
                                </button>
                            )}
                        </div>
                        <p className="text-lg font-bold text-white mt-0.5">
                            {systemInfo.CurrentUser && systemInfo.CurrentUser !== 'N/A' ? systemInfo.CurrentUser : 'Nenhum usuário em console'}
                        </p>
                        {systemInfo.Domain && systemInfo.Domain !== 'N/A' && (
                            <p className="text-xs text-zinc-400 flex items-center gap-1.5 mt-0.5">
                                <Shield size={12} className="text-purple-400" />
                                Domínio: <span className="text-zinc-300 font-medium">{systemInfo.Domain}</span>
                            </p>
                        )}
                    </div>
                </div>

                {/* TeamViewer ID Badge / Shortcut */}
                {effectiveTvId && (
                    <div className="bg-zinc-900/80 border border-blue-900/50 rounded-xl p-3.5 flex items-center gap-3.5 w-full sm:w-auto">
                        <div className="p-2 bg-blue-600/20 text-blue-400 rounded-lg">
                            <Activity size={18} />
                        </div>
                        <div>
                            <span className="text-[11px] uppercase tracking-wider font-semibold text-zinc-400">TeamViewer ID</span>
                            <div className="flex items-center gap-2">
                                <span className="font-mono text-base font-bold text-blue-300 tracking-wider">
                                    {effectiveTvId}
                                </span>
                                <button
                                    onClick={() => handleCopy(effectiveTvId, 'tvid', 'ID TeamViewer')}
                                    className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-white transition-colors"
                                    title="Copiar TeamViewer ID"
                                >
                                    {copiedField === 'tvid' ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                                </button>
                            </div>
                        </div>
                        <button
                            onClick={() => handleLaunchTv(effectiveTvId)}
                            className="ml-auto sm:ml-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-blue-900/30 transition-all hover:-translate-y-0.5"
                            title="Conectar via TeamViewer"
                        >
                            <ExternalLink size={13} />
                            Conectar
                        </button>
                    </div>
                )}
            </div>

            {/* Sistema Operacional */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <Monitor size={18} className="text-blue-400" />
                        Sistema Operacional
                    </h3>
                    {systemInfo.OS && (
                        <button
                            onClick={() => handleCopy(`${systemInfo.OS} (${systemInfo.OS_Version})`, 'os', 'Dados do SO')}
                            className="p-1 text-zinc-400 hover:text-white rounded hover:bg-zinc-700/50 transition-colors"
                            title="Copiar SO"
                        >
                            {copiedField === 'os' ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                        </button>
                    )}
                </div>
                <div className="space-y-3 text-sm">
                    <div className="flex justify-between py-1 border-b border-zinc-700/30">
                        <span className="text-zinc-400">Sistema</span>
                        <span className="text-white font-medium text-right">{systemInfo.OS || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-zinc-700/30">
                        <span className="text-zinc-400">Build / Versão</span>
                        <span className="text-white font-mono">{systemInfo.OS_Version || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-zinc-700/30">
                        <span className="text-zinc-400">Data de Instalação</span>
                        <span className="text-zinc-300">{formatDate(systemInfo.InstallDate)}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-zinc-700/30">
                        <span className="text-zinc-400">Última Inicialização</span>
                        <span className="text-zinc-300">{formatDate(systemInfo.LastBootUpTime)}</span>
                    </div>
                    <div className="flex justify-between py-1">
                        <span className="text-zinc-400">Tempo de Atividade (Uptime)</span>
                        <span className="text-emerald-400 font-medium">
                            {systemInfo.Uptime
                                ? `${systemInfo.Uptime.uptime_days}d ${systemInfo.Uptime.uptime_hours}h`
                                : 'N/A'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Hardware & Processador */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <Cpu size={18} className="text-purple-400" />
                        Hardware & Capacidade
                    </h3>
                    {systemInfo.CPU && (
                        <button
                            onClick={() => handleCopy(`${systemInfo.CPU} - ${systemInfo.RAM_GB} GB RAM`, 'hw', 'Hardware')}
                            className="p-1 text-zinc-400 hover:text-white rounded hover:bg-zinc-700/50 transition-colors"
                            title="Copiar Hardware"
                        >
                            {copiedField === 'hw' ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
                        </button>
                    )}
                </div>
                <div className="space-y-3 text-sm">
                    <div className="flex justify-between py-1 border-b border-zinc-700/30 items-start">
                        <span className="text-zinc-400 shrink-0">Processador</span>
                        <span className="text-white font-medium text-right max-w-[240px] truncate" title={systemInfo.CPU}>
                            {systemInfo.CPU || 'N/A'}
                        </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-zinc-700/30">
                        <span className="text-zinc-400">Memória RAM</span>
                        <span className="text-white font-semibold">{systemInfo.RAM_GB} GB</span>
                    </div>
                    <div className="flex justify-between py-1">
                        <span className="text-zinc-400">Arquitetura</span>
                        <span className="text-zinc-300 font-medium">
                            {systemInfo.OS?.includes('64') ? 'x64 (64-bit)' : 'x86 (32-bit)'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Armazenamento */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50 md:col-span-2">
                <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
                    <HardDrive size={18} className="text-green-400" />
                    Armazenamento & Discos
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {(Array.isArray(systemInfo.Disks) ? systemInfo.Disks : (systemInfo.Disks ? [systemInfo.Disks] : [])).map((disk: any) => {
                        const freeRatio = disk.Total_GB > 0 ? (disk.Free_GB / disk.Total_GB) : 1;
                        const isCritical = freeRatio < 0.10;
                        const isWarning = freeRatio < 0.20 && !isCritical;
                        const usedPct = disk.Total_GB > 0 ? Math.round(((disk.Total_GB - disk.Free_GB) / disk.Total_GB) * 100) : 0;

                        return (
                            <div key={disk.DeviceID} className="bg-zinc-900/60 p-4 rounded-xl border border-zinc-700/60 space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-white font-bold font-mono text-base">
                                        {disk.DeviceID} <span className="text-xs font-normal text-zinc-400 font-sans">({disk.VolumeName || 'Disco Local'})</span>
                                    </span>
                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                        isCritical ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                                        isWarning ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                                        'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                    }`}>
                                        {disk.Free_GB} GB livres
                                    </span>
                                </div>
                                <div className="w-full bg-zinc-800 h-2.5 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all ${
                                            isCritical ? 'bg-red-500' :
                                            isWarning ? 'bg-amber-500' :
                                            'bg-blue-500'
                                        }`}
                                        style={{ width: `${usedPct}%` }}
                                    />
                                </div>
                                <div className="flex justify-between items-center text-xs text-zinc-400 font-mono">
                                    <span>{usedPct}% usado</span>
                                    <span>Total: {disk.Total_GB} GB</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Configuração de Rede */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50 md:col-span-2">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <Network size={18} className="text-orange-400" />
                        Configuração de Rede & Adaptador
                    </h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                    <div className="bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-700/40 space-y-1">
                        <span className="text-xs text-zinc-400">Interface Ativa</span>
                        <p className="text-white font-medium truncate" title={systemInfo.Interface}>
                            {systemInfo.Interface || 'N/A'}
                        </p>
                    </div>

                    <div className="bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-700/40 space-y-1">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-zinc-400">Endereço MAC</span>
                            {systemInfo.MACAddress && systemInfo.MACAddress !== 'N/A' && (
                                <button
                                    onClick={() => handleCopy(systemInfo.MACAddress, 'mac', 'MAC Address')}
                                    className="text-zinc-500 hover:text-white transition-colors"
                                    title="Copiar MAC"
                                >
                                    {copiedField === 'mac' ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                                </button>
                            )}
                        </div>
                        <p className="text-zinc-200 font-mono font-medium truncate">
                            {systemInfo.MACAddress || 'N/A'}
                        </p>
                    </div>

                    <div className="bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-700/40 space-y-1">
                        <span className="text-xs text-zinc-400">Velocidade do Link</span>
                        <p className="text-emerald-400 font-semibold">
                            {systemInfo.LinkSpeed || 'N/A'}
                        </p>
                    </div>

                    <div className="bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-700/40 space-y-1">
                        <span className="text-xs text-zinc-400">Máscara de Subrede</span>
                        <p className="text-zinc-200 font-mono">
                            {systemInfo.SubnetMask || 'N/A'}
                        </p>
                    </div>

                    <div className="bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-700/40 space-y-1">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-zinc-400">Gateway Padrão</span>
                            {systemInfo.Gateway && systemInfo.Gateway !== 'N/A' && (
                                <button
                                    onClick={() => handleCopy(systemInfo.Gateway, 'gw', 'Gateway')}
                                    className="text-zinc-500 hover:text-white transition-colors"
                                    title="Copiar Gateway"
                                >
                                    {copiedField === 'gw' ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                                </button>
                            )}
                        </div>
                        <p className="text-zinc-200 font-mono">
                            {systemInfo.Gateway || 'N/A'}
                        </p>
                    </div>

                    <div className="bg-zinc-900/40 p-3.5 rounded-lg border border-zinc-700/40 space-y-1">
                        <span className="text-xs text-zinc-400">Servidores DNS</span>
                        <p className="text-zinc-200 font-mono truncate" title={systemInfo.DNSServers}>
                            {systemInfo.DNSServers || 'N/A'}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};
