import { X, Sparkles, Bug, Zap, ShieldCheck, Wand2, Wrench, FileText } from 'lucide-react';
import { createPortal } from 'react-dom';
import { CHANGELOG, type ChangeKind } from '../../data/changelog';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';

interface ChangelogModalProps {
    isOpen: boolean;
    onClose: () => void;
}

const KIND_META: Record<ChangeKind, { label: string; color: string; bg: string; border: string; Icon: typeof Sparkles }> = {
    feat:     { label: 'Novo',       color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', Icon: Sparkles },
    fix:      { label: 'Correção',   color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/20',   Icon: Bug },
    perf:     { label: 'Performance', color: 'text-violet-400', bg: 'bg-violet-500/10',  border: 'border-violet-500/20',  Icon: Zap },
    security: { label: 'Segurança',  color: 'text-red-400',     bg: 'bg-red-500/10',     border: 'border-red-500/20',     Icon: ShieldCheck },
    ui:       { label: 'Interface',  color: 'text-blue-400',    bg: 'bg-blue-500/10',    border: 'border-blue-500/20',    Icon: Wand2 },
    refactor: { label: 'Refatoração', color: 'text-zinc-400',   bg: 'bg-zinc-500/10',    border: 'border-zinc-500/20',    Icon: Wrench },
    docs:     { label: 'Docs',       color: 'text-cyan-400',    bg: 'bg-cyan-500/10',    border: 'border-cyan-500/20',    Icon: FileText },
};

export function ChangelogModal({ isOpen, onClose }: ChangelogModalProps) {
    useEscapeToClose(isOpen, onClose);
    if (!isOpen) return null;

    return createPortal(
        <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-[10000] p-4 animate-in fade-in duration-200"
            onClick={onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl scale-100 animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="changelog-title"
            >
                <div className="flex items-center justify-between p-5 border-b border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20">
                            <Sparkles size={18} className="text-blue-400" aria-hidden="true" />
                        </div>
                        <div>
                            <h2 id="changelog-title" className="text-lg font-bold text-white">Novidades e melhorias</h2>
                            <p className="text-xs text-zinc-500">Histórico de versões da aplicação</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Fechar"
                        className="p-2 text-zinc-500 hover:text-white hover:bg-zinc-800/50 rounded-lg transition-colors"
                    >
                        <X size={20} aria-hidden="true" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-8">
                    {CHANGELOG.map((entry, idx) => (
                        <section key={entry.version}>
                            <header className="flex items-baseline gap-3 mb-3 pb-2 border-b border-zinc-800/50">
                                <h3 className="text-base font-bold text-white">v{entry.version}</h3>
                                <span className="text-xs text-zinc-500 font-mono">{entry.date}</span>
                                {idx === 0 && (
                                    <span className="ml-auto text-[10px] uppercase font-semibold tracking-wider text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                                        Atual
                                    </span>
                                )}
                            </header>
                            {entry.title && (
                                <p className="text-sm text-zinc-300 mb-3 italic">{entry.title}</p>
                            )}
                            <ul className="space-y-2">
                                {entry.changes.map((change, i) => {
                                    const meta = KIND_META[change.kind];
                                    const Icon = meta.Icon;
                                    return (
                                        <li key={i} className="flex gap-3 items-start">
                                            <span
                                                className={`shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded ${meta.bg} ${meta.color} ${meta.border} border text-[10px] font-semibold uppercase tracking-wider`}
                                                title={meta.label}
                                            >
                                                <Icon size={11} />
                                                {meta.label}
                                            </span>
                                            <p className="text-sm text-zinc-300 leading-relaxed flex-1">{change.text}</p>
                                        </li>
                                    );
                                })}
                            </ul>
                        </section>
                    ))}
                </div>

                <div className="p-4 border-t border-zinc-800 bg-zinc-950/30 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                        Fechar
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
}
