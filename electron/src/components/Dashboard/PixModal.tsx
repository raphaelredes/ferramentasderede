import React from 'react';
import { X, Copy, Check, QrCode } from 'lucide-react';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';

interface PixModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const PixModal: React.FC<PixModalProps> = ({ isOpen, onClose }) => {
    const [copied, setCopied] = React.useState(false);
    const pixKey = "pixferramentasderede@gmail.com";

    useEscapeToClose(isOpen, onClose);
    if (!isOpen) return null;

    const handleCopy = () => {
        navigator.clipboard.writeText(pixKey);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 sm:p-6 animate-in fade-in duration-200"
            onClick={onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-md max-h-[85vh] sm:max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200 relative my-auto"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="pix-title"
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-950/50 shrink-0">
                    <div className="flex items-center gap-2">
                        <QrCode size={18} className="text-blue-400" />
                        <h2 id="pix-title" className="text-base font-semibold text-white">Faça um PIX</h2>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Fechar"
                        className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition-colors"
                    >
                        <X size={18} aria-hidden="true" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-5 sm:p-6 overflow-y-auto custom-scrollbar flex flex-col items-center text-center space-y-4 flex-1">
                    <p className="text-xs sm:text-sm text-zinc-300">
                        Ajude a manter o projeto ativo e recebendo atualizações constantes!
                    </p>

                    <div className="w-full bg-zinc-950/60 rounded-xl border border-zinc-800/80 p-3.5 text-left">
                        <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-1.5">Chave PIX (E-mail)</p>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 text-xs text-blue-400 font-mono bg-blue-500/10 px-2.5 py-1.5 rounded-lg border border-blue-500/20 truncate">
                                {pixKey}
                            </code>
                            <button
                                onClick={handleCopy}
                                className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-300 hover:text-white transition-colors shrink-0"
                                title="Copiar chave"
                            >
                                {copied ? <Check size={15} className="text-emerald-400" /> : <Copy size={15} />}
                            </button>
                        </div>
                    </div>

                    <div className="bg-white p-3 rounded-2xl shadow-lg">
                        <img
                            src="/qrcode-pix.png"
                            alt="QR Code PIX"
                            className="w-40 h-40 object-contain"
                        />
                    </div>
                    <p className="text-[11px] text-zinc-500">Escaneie o QR Code com seu aplicativo de banco</p>
                </div>
            </div>
        </div>
    );
};
