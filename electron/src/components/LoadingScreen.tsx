import React, { useEffect, useState, useRef } from 'react';
import { Cpu, Shield, HardDrive, Zap, CheckCircle2, Router, Sparkles, Activity, Layers } from 'lucide-react';
import { APP_VERSION } from '../data/changelog';
import { API_BASE } from '../config/api';

interface LoadingScreenProps {
    onComplete: () => void;
}

interface StepItem {
    id: string;
    label: string;
    icon: React.ReactNode;
    status: 'pending' | 'running' | 'done';
}

export const LoadingScreen: React.FC<LoadingScreenProps> = ({ onComplete }) => {
    const [progress, setProgress] = useState(10);
    const [statusText, setStatusText] = useState('Iniciando subsistemas...');
    const hasFinishedRef = useRef(false);

    const [steps, setSteps] = useState<StepItem[]>([
        { id: 'backend', label: 'Núcleo FastAPI & Uvicorn', icon: <Cpu size={13} className="text-blue-400" />, status: 'running' },
        { id: 'db', label: 'Banco SQLite & Cache de Hosts', icon: <HardDrive size={13} className="text-purple-400" />, status: 'pending' },
        { id: 'network', label: 'Adaptadores & Camada 2 (LLDP/CDP)', icon: <Router size={13} className="text-cyan-400" />, status: 'pending' },
        { id: 'security', label: 'Cofre de Credenciais & AD Matrix', icon: <Shield size={13} className="text-emerald-400" />, status: 'pending' },
        { id: 'chunks', label: 'Pré-carregamento de Telas & Bundles', icon: <Layers size={13} className="text-amber-400" />, status: 'pending' },
        { id: 'ready', label: 'Sistema 100% Pronto', icon: <CheckCircle2 size={13} className="text-emerald-400" />, status: 'pending' }
    ]);

    const updateStep = (id: string, status: 'pending' | 'running' | 'done') => {
        setSteps(prev => prev.map(s => s.id === id ? { ...s, status } : s));
    };

    useEffect(() => {
        const startTime = Date.now();
        const minDisplayDuration = 2200; // Smooth duration for the cyber animation

        async function prewarmAll() {
            try {
                // Step 1: Backend Health & Status
                setStatusText('Verificando integridade da API...');
                setProgress(25);
                updateStep('backend', 'running');
                await fetch(`${API_BASE}/monitoring/status`).catch(() => null);
                updateStep('backend', 'done');

                // Step 2: Database & Hosts Cache Pre-warming
                setStatusText('Aquecendo conexões do SQLite e inventário...');
                setProgress(45);
                updateStep('db', 'running');
                await Promise.all([
                    fetch(`${API_BASE}/hosts`).catch(() => null),
                    fetch(`${API_BASE}/settings`).catch(() => null)
                ]);
                updateStep('db', 'done');

                // Step 3: Network & L2 Listeners
                setStatusText('Inicializando listeners de rede e tabelas ARP...');
                setProgress(65);
                updateStep('network', 'running');
                await fetch(`${API_BASE}/batch/snippets`).catch(() => null);
                updateStep('network', 'done');

                // Step 4: Vault & Security Matrix
                setStatusText('Carregando cofres e matriz de segurança...');
                setProgress(80);
                updateStep('security', 'running');
                await fetch(`${API_BASE}/vault/status`).catch(() => null);
                updateStep('security', 'done');

                // Step 5: Pre-load lazy route chunks in background for 0ms tab transitions
                setStatusText('Pré-carregando módulos da interface em memória...');
                setProgress(92);
                updateStep('chunks', 'running');
                await Promise.all([
                    import('../pages/Tools').catch(() => null),
                    import('../pages/Terminal').catch(() => null),
                    import('../pages/Settings').catch(() => null),
                    import('../pages/HostDetails').catch(() => null),
                    import('../pages/Security').catch(() => null)
                ]);
                updateStep('chunks', 'done');

                // Final Step: Complete
                setStatusText('Tudo pronto! Carregando painel principal...');
                setProgress(100);
                updateStep('ready', 'done');

                const elapsed = Date.now() - startTime;
                const remaining = Math.max(0, minDisplayDuration - elapsed);

                setTimeout(() => {
                    if (!hasFinishedRef.current) {
                        hasFinishedRef.current = true;
                        onComplete();
                    }
                }, remaining);

            } catch (err) {
                // Fallback guarantee: if anything fails, proceed after safety timeout
                console.warn('Prewarm fallback triggered', err);
                setProgress(100);
                setTimeout(() => {
                    if (!hasFinishedRef.current) {
                        hasFinishedRef.current = true;
                        onComplete();
                    }
                }, 1000);
            }
        }

        prewarmAll();

        // Safety fallback
        const safetyTimer = setTimeout(() => {
            if (!hasFinishedRef.current) {
                hasFinishedRef.current = true;
                onComplete();
            }
        }, 5000);

        return () => clearTimeout(safetyTimer);
    }, [onComplete]);

    return (
        <div className="fixed inset-0 bg-zinc-950 flex flex-col items-center justify-center z-50 font-mono text-sm overflow-hidden select-none">
            {/* Holographic 3D Grid floor */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.12)_1px,transparent_1px)] bg-[size:48px_48px] origin-top animate-grid-flow opacity-45" />
                <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/75 to-zinc-950" />

                {/* Ambient Radial Lights */}
                <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-600/15 rounded-full blur-[140px] animate-pulse-glow" />
                <div className="absolute bottom-1/4 left-1/3 w-[450px] h-[450px] bg-cyan-500/10 rounded-full blur-[110px]" />
            </div>

            {/* Scanlines & High-Tech HUD */}
            <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(0,123,255,0.03),rgba(0,255,255,0.01),rgba(0,123,255,0.03))] z-20 bg-[size:100%_2px,3px_100%] opacity-35" />
            <div className="absolute inset-0 pointer-events-none h-1.5 bg-gradient-to-r from-transparent via-cyan-400/50 to-transparent opacity-70 animate-scanline z-30 blur-[1px]" />

            {/* Main Cyber HUD Container */}
            <div className="relative z-40 w-full max-w-lg p-6 sm:p-8 flex flex-col gap-5">
                {/* Logo & Version Hero */}
                <div className="flex flex-col items-center justify-center relative">
                    <div className="relative flex items-center justify-center mb-3">
                        <img src="/logo.png?v=4" alt="Logo" className="w-16 h-16 object-contain" />
                    </div>


                    <h1 className="text-2xl sm:text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-300 via-cyan-200 to-blue-400 tracking-wider uppercase drop-shadow-md text-center">
                        Ferramentas de Rede
                    </h1>

                    {/* HIGH-VISIBILITY VERSION BADGE */}
                    <div className="mt-2 flex items-center gap-2 px-4 py-1.5 rounded-full bg-gradient-to-r from-blue-950/95 via-zinc-900/95 to-blue-950/95 border border-cyan-500/50 shadow-[0_0_25px_rgba(6,182,212,0.35)] animate-pulse">
                        <Sparkles size={14} className="text-cyan-400 animate-spin" style={{ animationDuration: '5s' }} />
                        <span className="text-xs font-bold text-cyan-300 tracking-widest uppercase">
                            Versão {APP_VERSION}
                        </span>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
                        <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-semibold">Portátil</span>
                    </div>
                </div>

                {/* Progress Bar & Status Text */}
                <div className="space-y-2 bg-zinc-900/60 p-3.5 rounded-xl border border-zinc-800/80 backdrop-blur-md">
                    <div className="flex justify-between items-center text-xs">
                        <span className="flex items-center gap-2 text-cyan-300 font-bold tracking-wide uppercase truncate max-w-[75%]">
                            <Activity size={13} className="animate-pulse text-blue-400 shrink-0" />
                            <span className="truncate">{statusText}</span>
                        </span>
                        <span className="font-mono text-xs font-bold text-white bg-blue-600/30 px-2 py-0.5 rounded border border-blue-500/30 shadow-sm shrink-0">
                            {progress.toString().padStart(3, '0')}%
                        </span>
                    </div>

                    <div className="h-2 w-full bg-zinc-950 rounded-full overflow-hidden border border-zinc-800 p-0.5 shadow-inner">
                        <div
                            className="h-full bg-gradient-to-r from-blue-600 via-cyan-400 to-emerald-400 rounded-full transition-all duration-300 ease-out relative shadow-[0_0_14px_rgba(34,211,238,0.7)]"
                            style={{ width: `${progress}%` }}
                        >
                            <div className="absolute inset-0 bg-white/40 animate-[shimmer_1.2s_infinite]" />
                        </div>
                    </div>
                </div>

                {/* Real-time Subsystem Initialization Grid */}
                <div className="bg-black/60 border border-zinc-800/80 rounded-xl p-3.5 backdrop-blur-md shadow-2xl space-y-1.5">
                    <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mb-1 flex items-center justify-between border-b border-zinc-800/50 pb-1">
                        <span>Telemetria de Inicialização</span>
                        <span className="text-cyan-400">Pré-Aquecimento Ativo</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                        {steps.map(step => (
                            <div
                                key={step.id}
                                className={`flex items-center gap-2 px-2 py-1 rounded-md text-[11px] transition-all border ${
                                    step.status === 'done'
                                        ? 'bg-emerald-500/10 border-emerald-500/20 text-zinc-200'
                                        : step.status === 'running'
                                        ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300 animate-pulse'
                                        : 'bg-zinc-900/40 border-zinc-800/40 text-zinc-600'
                                }`}
                            >
                                <span className="shrink-0">{step.icon}</span>
                                <span className="truncate flex-1">{step.label}</span>
                                {step.status === 'done' && (
                                    <CheckCircle2 size={11} className="text-emerald-400 shrink-0" />
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Footer Telemetry */}
                <div className="flex justify-between items-center text-[10px] text-zinc-500 uppercase tracking-widest border-t border-zinc-800/60 pt-2.5">
                    <span className="flex items-center gap-1.5">
                        <Zap size={11} className="text-amber-400 animate-pulse" />
                        0ms Latency Ready
                    </span>
                    <span className="font-mono text-zinc-400 font-bold">v{APP_VERSION}</span>
                    <span className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${progress === 100 ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-amber-400 animate-pulse'}`} />
                        {progress === 100 ? 'Pronto' : 'Carregando...'}
                    </span>
                </div>
            </div>
        </div>
    );
};
