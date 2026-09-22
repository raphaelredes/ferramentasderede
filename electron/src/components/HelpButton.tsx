import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { HelpCircle, X } from 'lucide-react';

interface HelpButtonProps {
    title: string;
    description: React.ReactNode;
    className?: string;
}

export function HelpButton({ title, description, className = "" }: HelpButtonProps) {
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.stopPropagation();
                setIsOpen(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

    return (
        <>
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setIsOpen(true);
                }}
                className={`text-zinc-500 hover:text-blue-400 transition-colors inline-flex items-center justify-center ${className}`}
                title={`Ajuda: ${title}`}
                aria-label={`Ajuda: ${title}`}
            >
                <HelpCircle size={16} />
            </button>

            {isOpen && createPortal(
                <div
                    className="fixed inset-0 bg-black/60 flex items-center justify-center z-[9999] backdrop-blur-sm p-4 animate-in fade-in duration-150"
                    onClick={() => setIsOpen(false)}
                    role="presentation"
                >
                    <div
                        className="bg-zinc-900 border border-zinc-700/80 rounded-2xl w-full max-w-lg p-6 shadow-2xl animate-in zoom-in-95 duration-150 flex flex-col max-h-[85vh]"
                        onClick={e => e.stopPropagation()}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="help-modal-title"
                    >
                        <div className="flex items-center justify-between pb-3 border-b border-zinc-800 mb-4">
                            <h3 id="help-modal-title" className="text-base font-bold text-white flex items-center gap-2.5">
                                <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                    <HelpCircle size={18} />
                                </div>
                                {title}
                            </h3>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-zinc-400 hover:text-white p-1.5 rounded-lg hover:bg-zinc-800 transition-colors"
                                title="Fechar (Esc)"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="text-zinc-300 text-sm leading-relaxed space-y-2.5 overflow-y-auto pr-1 custom-scrollbar">
                            {description}
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </>
    );
}
