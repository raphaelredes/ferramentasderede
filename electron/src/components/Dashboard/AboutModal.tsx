import { X, Globe, Send } from 'lucide-react';
import { createPortal } from 'react-dom';

interface AboutModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function AboutModal({ isOpen, onClose }: AboutModalProps) {
    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[9999] p-4 animate-in fade-in duration-200" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden scale-100 animate-in zoom-in-95 duration-200 relative" onClick={(e) => e.stopPropagation()}>

                {/* Decorative Background Elements */}
                <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-blue-500/10 to-transparent pointer-events-none" />
                <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 text-zinc-500 hover:text-white hover:bg-zinc-800/50 rounded-full transition-colors z-10"
                >
                    <X size={20} />
                </button>

                <div className="p-8 text-center relative z-0">
                    <div className="mb-6 flex items-center justify-center">
                        <img src="/logo.png?v=4" alt="Logo" className="w-24 h-24 object-contain drop-shadow-[0_0_15px_rgba(0,123,255,0.5)]" />
                    </div>

                    <h2 className="text-2xl font-bold text-white mb-2">Ferramentas de Rede</h2>
                    <p className="text-zinc-400 mb-8">Versão 1.2.0</p>

                    <div className="space-y-4 mb-8">
                        <div className="p-4 bg-zinc-950/50 rounded-xl border border-zinc-800/50">
                            <p className="text-sm text-zinc-500 mb-1 uppercase tracking-wider font-semibold">Desenvolvido por</p>
                            <p className="text-lg text-white font-medium">Raphael Oliveira Rêgo</p>
                        </div>

                        <div className="p-4 bg-zinc-950/50 rounded-xl border border-zinc-800/50">
                            <p className="text-sm text-zinc-500 mb-2 uppercase tracking-wider font-semibold">Tecnologias Utilizadas</p>
                            <div className="flex flex-wrap justify-center gap-2">
                                {['Python', 'React', 'TypeScript', 'Electron', 'Tailwind CSS'].map((tech) => (
                                    <span key={tech} className="px-2 py-1 bg-zinc-800 rounded text-xs text-zinc-300 border border-zinc-700">
                                        {tech}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <button
                            onClick={() => {
                                const url = "https://t.me/raphaelrego";
                                if (window.electron) window.electron.openExternal(url);
                                else if (window.pywebview?.api) window.pywebview.api.open_url(url);
                                else window.open(url, '_blank');
                            }}
                            className="flex items-center justify-center gap-2 p-3 bg-[#0088cc]/10 hover:bg-[#0088cc]/20 text-[#0088cc] rounded-xl transition-colors border border-[#0088cc]/20 hover:border-[#0088cc]/40 group"
                        >
                            <Send size={18} className="group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                            <span className="font-medium">Telegram</span>
                        </button>
                        <button
                            onClick={() => {
                                const url = "https://www.ferramentasderede.com.br/";
                                if (window.electron) window.electron.openExternal(url);
                                else if (window.pywebview?.api) window.pywebview.api.open_url(url);
                                else window.open(url, '_blank');
                            }}
                            className="flex items-center justify-center gap-2 p-3 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-xl transition-colors border border-blue-500/20 hover:border-blue-500/40 group"
                        >
                            <Globe size={18} className="group-hover:rotate-12 transition-transform" />
                            <span className="font-medium">Website</span>
                        </button>
                    </div>
                </div>

                <div className="p-4 bg-zinc-950/30 border-t border-zinc-800/50 text-center">
                    <p className="text-xs text-zinc-600">
                        © {new Date().getFullYear()} Todos os direitos reservados.
                    </p>
                </div>
            </div>
        </div>,
        document.body
    );
}
