import React, { useEffect } from 'react';
import { X, HelpCircle, CheckCircle2, Lightbulb, Cog, Shield, ArrowRight } from 'lucide-react';
import { TOOLS_HELP_DATA } from '../../data/toolsHelpData';

interface ToolHelpModalProps {
    toolId: string | null;
    onClose: () => void;
}

export function ToolHelpModal({ toolId, onClose }: ToolHelpModalProps) {
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onClose]);

    if (!toolId) return null;
    const info = TOOLS_HELP_DATA[toolId];
    if (!info) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
            <div
                className="bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-scale-up"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-zinc-800 bg-zinc-950/60">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
                            <HelpCircle size={22} />
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 rounded text-[11px] font-bold tracking-wide uppercase bg-zinc-800 text-zinc-400 border border-zinc-700">
                                    {info.categoryLabel}
                                </span>
                                {info.protocolsOrPorts && (
                                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-blue-950/80 text-blue-300 border border-blue-800/50">
                                        {info.protocolsOrPorts}
                                    </span>
                                )}
                            </div>
                            <h2 className="text-lg font-bold text-white mt-1">{info.title}</h2>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-zinc-400 hover:text-white p-2 rounded-lg hover:bg-zinc-800 transition-colors"
                        title="Fechar (Esc)"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Body Content */}
                <div className="p-6 overflow-y-auto space-y-5 custom-scrollbar text-sm">
                    {/* Resumo */}
                    <div className="p-4 rounded-xl bg-gradient-to-r from-blue-950/40 to-cyan-950/20 border border-blue-900/30 text-zinc-200 leading-relaxed font-medium">
                        {info.summary}
                    </div>

                    {/* Como Funciona */}
                    <div className="space-y-2.5">
                        <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs uppercase tracking-wider">
                            <Cog size={15} className="text-blue-400" />
                            <span>Como Funciona</span>
                        </div>
                        <div className="space-y-2 bg-zinc-950/50 p-3.5 rounded-xl border border-zinc-800/80">
                            {info.howItWorks.map((item, idx) => (
                                <div key={idx} className="flex items-start gap-2.5 text-zinc-300 text-xs sm:text-sm">
                                    <ArrowRight size={14} className="text-blue-400 mt-1 shrink-0" />
                                    <span>{item}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Casos de Uso */}
                    <div className="space-y-2.5">
                        <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs uppercase tracking-wider">
                            <Shield size={15} className="text-emerald-400" />
                            <span>Casos de Uso no Dia a Dia</span>
                        </div>
                        <div className="space-y-2 bg-zinc-950/50 p-3.5 rounded-xl border border-zinc-800/80">
                            {info.useCases.map((item, idx) => (
                                <div key={idx} className="flex items-start gap-2.5 text-zinc-300 text-xs sm:text-sm">
                                    <CheckCircle2 size={15} className="text-emerald-400 mt-0.5 shrink-0" />
                                    <span>{item}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Dicas e Boas Práticas */}
                    {info.tips && info.tips.length > 0 && (
                        <div className="space-y-2.5">
                            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs uppercase tracking-wider">
                                <Lightbulb size={15} className="text-amber-400" />
                                <span>Dicas & Boas Práticas</span>
                            </div>
                            <div className="space-y-2 bg-amber-950/20 p-3.5 rounded-xl border border-amber-900/30">
                                {info.tips.map((item, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-amber-200/90 text-xs sm:text-sm">
                                        <span className="text-amber-400 font-bold">•</span>
                                        <span>{item}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex justify-end p-4 border-t border-zinc-800 bg-zinc-950/60">
                    <button
                        onClick={onClose}
                        className="px-5 py-2 rounded-xl text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors shadow-lg shadow-blue-900/20"
                    >
                        Entendi
                    </button>
                </div>
            </div>
        </div>
    );
}
