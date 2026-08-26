import { X, Globe, Send, Sparkles, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { APP_VERSION } from '../../data/changelog';
import { ChangelogModal } from './ChangelogModal';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';

interface AboutModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function AboutModal({ isOpen, onClose }: AboutModalProps) {
    const [isChangelogOpen, setIsChangelogOpen] = useState(false);
    useEscapeToClose(isOpen, onClose);
    if (!isOpen) return null;

    return createPortal(
        <>
            <ChangelogModal isOpen={isChangelogOpen} onClose={() => setIsChangelogOpen(false)} />
            <div
                className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-[9999] p-4 sm:p-6 animate-in fade-in duration-200"
                onClick={onClose}
                role="presentation"
            >
                <div
                    className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md max-h-[85vh] sm:max-h-[90vh] flex flex-col shadow-2xl overflow-hidden scale-100 animate-in zoom-in-95 duration-200 relative my-auto"
                    onClick={(e) => e.stopPropagation()}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="about-title"
                >
                    {/* Decorative Background Elements */}
                    <div className="absolute top-0 left-0 w-full h-28 bg-gradient-to-b from-blue-500/15 via-blue-500/5 to-transparent pointer-events-none" />
                    <div className="absolute -top-16 -right-16 w-36 h-36 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

                    {/* Close Button */}
                    <button
                        onClick={onClose}
                        aria-label="Fechar"
                        className="absolute top-3.5 right-3.5 p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800/60 rounded-full transition-colors z-20"
                    >
                        <X size={18} aria-hidden="true" />
                    </button>

                    {/* Scrollable Modal Content */}
                    <div className="p-5 sm:p-6 overflow-y-auto custom-scrollbar space-y-4 text-center relative z-10 flex-1">
                        {/* Logo & Header */}
                        <div className="flex flex-col items-center justify-center pt-1">
                            <div className="relative mb-3 group">
                                <div className="absolute inset-0 bg-blue-500/25 blur-xl rounded-full" />
                                <img
                                    src="/logo.png?v=4"
                                    alt="Logo"
                                    className="w-16 h-16 sm:w-18 sm:h-18 object-contain relative z-10 drop-shadow-[0_0_15px_rgba(0,123,255,0.6)]"
                                />
                            </div>

                            <h2 id="about-title" className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                                Ferramentas de Rede
                            </h2>

                            <button
                                onClick={() => setIsChangelogOpen(true)}
                                title="Clique para ver o histórico completo de novidades e melhorias"
                                className="group inline-flex items-center gap-1.5 mt-1 px-3 py-1 rounded-full text-xs font-semibold text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/25 hover:border-blue-500/40 transition-all shadow-sm"
                            >
                                <Sparkles size={13} className="text-blue-400 group-hover:scale-110 transition-transform" />
                                <span>Versão {APP_VERSION}</span>
                                <span className="text-[10px] text-blue-300/80 font-normal ml-0.5">(Ver Novidades)</span>
                            </button>
                            <p className="text-[11px] text-zinc-500 mt-1">Build portátil · Windows · Multi-VLAN & AD</p>
                        </div>

                        {/* Author Card */}
                        <div className="p-3.5 bg-zinc-950/60 rounded-xl border border-zinc-800/70 text-left">
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-0.5">Desenvolvido por</p>
                            <p className="text-sm font-semibold text-zinc-100">Raphael Oliveira Rêgo</p>
                        </div>

                        {/* Technologies */}
                        <div className="p-3.5 bg-zinc-950/60 rounded-xl border border-zinc-800/70 text-left">
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-2">Tecnologias & Arquitetura</p>
                            <div className="flex flex-wrap gap-1.5">
                                {[
                                    'Python 3', 'FastAPI', 'SQLite (WAL)',
                                    'React 18', 'TypeScript', 'Tailwind CSS',
                                    'PyWebView', 'WinRM', 'PowerShell', 'iPerf'
                                ].map((tech) => (
                                    <span key={tech} className="px-2 py-0.5 bg-zinc-900 rounded-md text-[11px] font-medium text-zinc-300 border border-zinc-800">
                                        {tech}
                                    </span>
                                ))}
                            </div>
                        </div>

                        {/* Attributions */}
                        <div className="p-3.5 bg-zinc-950/60 rounded-xl border border-zinc-800/70 text-left space-y-1.5">
                            <div className="flex items-center gap-1.5 text-zinc-400 font-semibold text-[10px] uppercase tracking-wider">
                                <ShieldCheck size={13} className="text-emerald-400" />
                                <span>Licenças & Terceiros</span>
                            </div>
                            <p className="text-[11px] text-zinc-400 leading-relaxed">
                                Os testes de banda utilizam o <strong className="text-zinc-200">iPerf2</strong> (NCSA/BSD). As ferramentas utilizam <strong className="text-zinc-200">pysnmp</strong> (BSD), <strong className="text-zinc-200">ntplib</strong> (MIT), <strong className="text-zinc-200">dnspython</strong> (ISC), <strong className="text-zinc-200">psutil</strong> (BSD) e <strong className="text-zinc-200">cryptography</strong> (Apache/BSD). 100% licenças permissivas.
                            </p>
                        </div>

                        {/* Action Links */}
                        <div className="grid grid-cols-2 gap-3 pt-1">
                            <button
                                onClick={() => {
                                    const url = "https://t.me/raphaelrego";
                                    if (window.electron) window.electron.openExternal(url);
                                    else if (window.pywebview?.api) window.pywebview.api.open_url(url);
                                    else window.open(url, '_blank');
                                }}
                                className="flex items-center justify-center gap-2 py-2.5 px-3 bg-[#0088cc]/10 hover:bg-[#0088cc]/20 text-[#0088cc] rounded-xl transition-colors border border-[#0088cc]/20 hover:border-[#0088cc]/40 text-xs font-semibold group"
                            >
                                <Send size={15} className="group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                                <span>Telegram</span>
                            </button>
                            <button
                                onClick={() => {
                                    const url = "https://www.ferramentasderede.com.br/";
                                    if (window.electron) window.electron.openExternal(url);
                                    else if (window.pywebview?.api) window.pywebview.api.open_url(url);
                                    else window.open(url, '_blank');
                                }}
                                className="flex items-center justify-center gap-2 py-2.5 px-3 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-xl transition-colors border border-blue-500/20 hover:border-blue-500/40 text-xs font-semibold group"
                            >
                                <Globe size={15} className="group-hover:rotate-12 transition-transform" />
                                <span>Website</span>
                            </button>
                        </div>
                    </div>

                    {/* Footer */}
                    <div className="py-2.5 px-4 bg-zinc-950/80 border-t border-zinc-800/60 text-center shrink-0">
                        <p className="text-[11px] text-zinc-500">
                            © {new Date().getFullYear()} Raphael Oliveira Rêgo · Todos os direitos reservados.
                        </p>
                    </div>
                </div>
            </div>
        </>,
        document.body
    );
}
