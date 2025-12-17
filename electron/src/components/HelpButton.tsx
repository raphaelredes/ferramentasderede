import { useState } from 'react';
import { createPortal } from 'react-dom';
import { HelpCircle, X } from 'lucide-react';

interface HelpButtonProps {
    title: string;
    description: React.ReactNode;
    className?: string;
}

export function HelpButton({ title, description, className = "" }: HelpButtonProps) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <>
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setIsOpen(true);
                }}
                className={`text-zinc-500 hover:text-blue-400 transition-colors ${className}`}
                title="Ajuda"
            >
                <HelpCircle size={16} />
            </button>

            {isOpen && createPortal(
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] backdrop-blur-sm" onClick={() => setIsOpen(false)}>
                    <div
                        className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl animate-in fade-in zoom-in duration-200"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                <HelpCircle className="text-blue-500" size={20} />
                                {title}
                            </h3>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-zinc-400 hover:text-white transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <div className="text-zinc-300 text-sm leading-relaxed space-y-2">
                            {description}
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </>
    );
}
