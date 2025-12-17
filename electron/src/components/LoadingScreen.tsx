import React, { useEffect, useState } from 'react';
import { Terminal, Cpu, Shield, Wifi, HardDrive, Battery, Zap, CheckCircle2 } from 'lucide-react';

interface LoadingScreenProps {
    onComplete: () => void;
}

export const LoadingScreen: React.FC<LoadingScreenProps> = ({ onComplete }) => {
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState<string[]>([]);
    const [, setCurrentStep] = useState(0);

    const bootSteps = [
        { message: 'Inicializando kernel...', icon: <Cpu size={14} className="text-blue-400" /> },
        { message: 'Carregando módulos do sistema...', icon: <HardDrive size={14} className="text-purple-400" /> },
        { message: 'Verificando interfaces de rede...', icon: <Wifi size={14} className="text-cyan-400" /> },
        { message: 'Verificando protocolos de segurança...', icon: <Shield size={14} className="text-green-400" /> },
        { message: 'Calibrando gerenciamento de energia...', icon: <Battery size={14} className="text-yellow-400" /> },
        { message: 'Iniciando serviços em segundo plano...', icon: <Zap size={14} className="text-orange-400" /> },
        { message: 'Sistema pronto.', icon: <CheckCircle2 size={14} className="text-emerald-400" /> }
    ];

    useEffect(() => {
        const totalDuration = 4000; // Increased slightly for better effect
        const stepDuration = totalDuration / bootSteps.length;

        const progressInterval = setInterval(() => {
            setProgress(prev => {
                if (prev >= 100) {
                    clearInterval(progressInterval);
                    return 100;
                }
                return prev + 1;
            });
        }, totalDuration / 100);

        const stepInterval = setInterval(() => {
            setCurrentStep(prev => {
                if (prev < bootSteps.length - 1) {
                    setLogs(currentLogs => [...currentLogs, bootSteps[prev].message]);
                    return prev + 1;
                } else {
                    clearInterval(stepInterval);
                    setLogs(currentLogs => [...currentLogs, bootSteps[bootSteps.length - 1].message]);
                    setTimeout(onComplete, 1000); // Wait a bit after completion
                    return prev;
                }
            });
        }, stepDuration);

        return () => {
            clearInterval(progressInterval);
            clearInterval(stepInterval);
        };
    }, [onComplete]);

    return (
        <div className="fixed inset-0 bg-zinc-950 flex flex-col items-center justify-center z-50 font-mono text-sm overflow-hidden perspective-1000">
            {/* Animated Perspective Grid Background */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute inset-0 bg-[linear-gradient(rgba(0,123,255,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(0,123,255,0.1)_1px,transparent_1px)] bg-[size:40px_40px] [transform:perspective(500px)_rotateX(60deg)] origin-top animate-grid-flow opacity-30" />
                <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-zinc-950" />
            </div>

            {/* Vignette & Scanline Overlay */}
            <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_center,transparent_0%,rgba(0,0,0,0.8)_100%)]" />
            <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] z-20 bg-[size:100%_2px,3px_100%] opacity-20" />
            <div className="absolute inset-0 pointer-events-none h-1 bg-white/5 opacity-30 animate-scanline z-30 blur-[1px]" />

            <div className="relative z-40 w-full max-w-md p-8 flex flex-col gap-8">
                {/* Logo / Header */}
                <div className="flex flex-col items-center justify-center relative group">
                    <div className="absolute inset-0 bg-blue-500/30 blur-[60px] rounded-full opacity-20 animate-pulse" />
                    <div className="relative bg-zinc-900/40 border border-zinc-700/50 p-6 rounded-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] backdrop-blur-md ring-1 ring-white/10 overflow-hidden">
                        {/* Scanning light effect over logo */}
                        <div className="absolute top-0 left-[-100%] w-[50%] h-full bg-gradient-to-r from-transparent via-white/10 to-transparent skew-x-[-25deg] animate-[shimmer_3s_infinite]" />

                        <img src="/logo.png?v=4" alt="Logo" className="w-16 h-16 object-contain drop-shadow-[0_0_15px_rgba(0,123,255,0.8)]" />
                    </div>
                    <div className="mt-4 flex flex-col items-center">
                        <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300 tracking-widest uppercase drop-shadow-sm">
                            Ferramentas de Rede
                        </h1>
                        <span className="text-[10px] text-zinc-500 tracking-[0.3em] uppercase mt-1">Inicialização do Sistema</span>
                    </div>
                </div>

                {/* Progress Bar */}
                <div className="space-y-2">
                    <div className="flex justify-between text-xs text-blue-400/80 mb-1 uppercase tracking-wider font-bold">
                        <span className="flex items-center gap-2">
                            <Terminal size={12} />
                            Carregando Núcleo...
                        </span>
                        <span className="font-mono">{progress.toString().padStart(3, '0')}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-zinc-900/80 rounded-sm overflow-hidden border border-zinc-800 shadow-[0_0_10px_rgba(0,0,0,0.5)_inset]">
                        <div
                            className="h-full bg-gradient-to-r from-blue-600 via-cyan-400 to-blue-500 transition-all duration-100 ease-linear relative shadow-[0_0_10px_rgba(56,189,248,0.5)]"
                            style={{ width: `${progress}%` }}
                        >
                            <div className="absolute inset-0 bg-white/30 animate-[shimmer_1s_infinite]" />
                        </div>
                    </div>
                </div>

                {/* Boot Logs */}
                <div className="bg-black/40 border border-zinc-800/60 rounded-lg p-4 h-48 overflow-hidden relative backdrop-blur-sm shadow-inner font-mono text-xs">
                    <div className="absolute top-0 left-0 w-full h-full pointer-events-none bg-gradient-to-b from-transparent via-transparent to-black/40" />
                    <div className="space-y-1.5 flex flex-col justify-end h-full relative z-10">
                        {logs.map((log, index) => (
                            <div key={index} className="flex items-center gap-3 animate-in slide-in-from-left-2 fade-in duration-200">
                                <span className="opacity-80 shrink-0">{bootSteps.find(s => s.message === log)?.icon}</span>
                                <span className="text-zinc-300 tracking-wide truncate">
                                    <span className="text-zinc-600 mr-2">[{new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>
                                    {log}
                                </span>
                            </div>
                        ))}
                        <div className="flex items-center gap-2 text-blue-400 animate-pulse opacity-70">
                            <span className="text-blue-500">{'>'}</span>
                            <span className="w-2 h-4 bg-blue-500/50 block animate-blink" />
                        </div>
                    </div>
                </div>

                {/* Footer Status */}
                <div className="flex justify-between items-center text-[10px] text-zinc-600 uppercase tracking-widest border-t border-zinc-800/30 pt-4">
                    <span>Conexão Segura</span>
                    <span className="flex items-center gap-2">
                        <span className={`w-1.5 h-1.5 rounded-full shadow-[0_0_5px_currentColor] ${progress === 100 ? 'bg-emerald-500 text-emerald-500' : 'bg-amber-500 text-amber-500 animate-pulse'}`} />
                        {progress === 100 ? 'Sistema Pronto' : 'Inicializando...'}
                    </span>
                </div>
            </div>
        </div>
    );
};
