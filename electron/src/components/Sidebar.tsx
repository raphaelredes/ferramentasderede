import { LayoutDashboard, Network, Settings, Terminal, Shield, ChevronLeft, ChevronRight, Info, QrCode } from 'lucide-react';
import { useState, useEffect } from 'react';
import { twMerge } from 'tailwind-merge';
import { useLocation, useNavigate } from 'react-router-dom';
import { useLoading } from '../contexts/LoadingContext';
import { useTools } from '../contexts/ToolsContext';
import { useMonitoring } from '../contexts/MonitoringContext';
import { AboutModal } from './Dashboard/AboutModal';
import { PixModal } from './Dashboard/PixModal';

export function Sidebar() {
    const location = useLocation();
    const navigate = useNavigate();
    const { isLoading } = useLoading();
    const { isRunning: isToolsRunning } = useTools();
    const { isLoading: isMonitoringLoading } = useMonitoring();
    const [time, setTime] = useState(new Date());
    const [isAboutModalOpen, setIsAboutModalOpen] = useState(false);
    const [isPixModalOpen, setIsPixModalOpen] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(false);

    useEffect(() => {
        const timer = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const menuItems = [
        { id: 'dashboard', label: 'Painel', icon: LayoutDashboard, path: '/' },
        { id: 'tools', label: 'Ferramentas', icon: Network, path: '/tools' },
        { id: 'terminal', label: 'Terminal Remoto', icon: Terminal, path: '/terminal' },
        { id: 'security', label: 'Segurança', icon: Shield, path: '/security' },
        { id: 'settings', label: 'Configurações', icon: Settings, path: '/settings' },
    ];

    const currentPath = location.pathname;

    return (
        <div className={twMerge(
            "h-screen bg-zinc-900 border-r border-zinc-800 flex flex-col transition-all duration-300",
            isCollapsed ? "w-20" : "w-64"
        )}>
            <div className="p-6 flex items-center justify-center border-b border-zinc-800 relative">
                <img src="/logo.png?v=4" alt="Logo" className="w-12 h-12 object-contain drop-shadow-[0_0_10px_rgba(0,123,255,0.3)]" />
            </div>

            <nav className="flex-1 px-4 space-y-2 mt-4">
                {menuItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = item.path
                        ? (item.path === '/'
                            ? (currentPath === '/' || currentPath.startsWith('/host/'))
                            : currentPath.startsWith(item.path))
                        : false;

                    const isItemLoading = isLoading(item.id) || (item.id === 'tools' && isToolsRunning);

                    return (
                        <button
                            key={item.id}
                            onClick={() => navigate(item.path)}
                            title={isCollapsed ? item.label : undefined}
                            className={twMerge(
                                "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-sm font-medium border border-transparent relative",
                                isActive
                                    ? "bg-zinc-800 text-zinc-100 border-zinc-700/50 shadow-sm"
                                    : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200",
                                isCollapsed && "justify-center px-2"
                            )}
                        >
                            <div className="relative">
                                <Icon size={20} className="shrink-0" />
                                {isItemLoading && (
                                    <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500"></span>
                                    </span>
                                )}
                            </div>
                            {!isCollapsed && (
                                <div className="flex-1 flex items-center justify-between">
                                    <span>{item.label}</span>
                                    {isItemLoading && (
                                        <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                                    )}
                                </div>
                            )}
                        </button>
                    );
                })}
            </nav>

            <AboutModal
                isOpen={isAboutModalOpen}
                onClose={() => setIsAboutModalOpen(false)}
            />

            <PixModal
                isOpen={isPixModalOpen}
                onClose={() => setIsPixModalOpen(false)}
            />

            <div className="p-4 border-t border-zinc-800 flex flex-col gap-3">
                <div className="flex gap-2">
                    <button
                        onClick={() => setIsAboutModalOpen(true)}
                        title="Sobre"
                        className={twMerge(
                            "flex-1 flex items-center justify-center gap-2 px-2 py-3 rounded-lg transition-colors text-sm font-medium border border-transparent relative text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200",
                            isCollapsed && "w-full"
                        )}
                    >
                        <Info size={20} className="shrink-0" />
                        {!isCollapsed && <span>Sobre</span>}
                    </button>

                    <button
                        onClick={() => setIsPixModalOpen(true)}
                        title="Faça um PIX"
                        className={twMerge(
                            "flex-1 flex items-center justify-center gap-2 px-2 py-3 rounded-lg transition-colors text-sm font-medium border border-transparent relative text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200",
                            isCollapsed && "w-full"
                        )}
                    >
                        <QrCode size={20} className="shrink-0" />
                        {!isCollapsed && <span>PIX</span>}
                    </button>
                </div>

                {!isCollapsed ? (
                    <>
                        <div className="flex flex-col items-center justify-center text-zinc-300">
                            <span className="text-3xl font-light tracking-wider">
                                {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            <span className="text-xs text-zinc-500 uppercase tracking-widest">
                                {time.toLocaleDateString(undefined, { day: '2-digit', month: '2-digit', year: 'numeric' })}
                            </span>
                        </div>

                        <div className="flex items-center justify-center gap-2 pt-2 border-t border-zinc-800/50">
                            <div className={`w-1.5 h-1.5 rounded-full ${isMonitoringLoading ? 'bg-yellow-500 animate-pulse' : 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]'}`} />
                            <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-medium">
                                {isMonitoringLoading ? 'ATUALIZANDO...' : 'SISTEMA ONLINE'}
                            </span>
                        </div>
                    </>
                ) : (
                    <div className="flex flex-col items-center gap-1">
                        <div className={`w-1.5 h-1.5 rounded-full ${isMonitoringLoading ? 'bg-yellow-500 animate-pulse' : 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]'} mb-1`} title={isMonitoringLoading ? 'Atualizando...' : 'Sistema Online'} />
                        <span className="text-[10px] text-zinc-500 font-mono leading-none">
                            {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <span className="text-[9px] text-zinc-600 font-mono leading-none">
                            {time.toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })}
                        </span>
                    </div>
                )}

                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className={twMerge(
                        "flex items-center justify-center gap-2 w-full p-2 mt-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors",
                        isCollapsed && "aspect-square p-0"
                    )}
                    title={isCollapsed ? "Expandir Menu" : "Recolher Menu"}
                >
                    {isCollapsed ? <ChevronRight size={20} className="shrink-0" /> : (
                        <>
                            <ChevronLeft size={20} className="shrink-0" />
                            <span className="text-sm">Recolher</span>
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}
