import React from 'react';
import { X, Copy, Check } from 'lucide-react';

interface PixModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const PixModal: React.FC<PixModalProps> = ({ isOpen, onClose }) => {
    const [copied, setCopied] = React.useState(false);
    const pixKey = "pixferramentasderede@gmail.com";

    if (!isOpen) return null;

    const handleCopy = () => {
        navigator.clipboard.writeText(pixKey);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between p-4 border-b border-zinc-800">
                    <h2 className="text-lg font-semibold text-white">Faça um PIX</h2>
                    <button onClick={onClose} className="text-zinc-400 hover:text-white transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 flex flex-col items-center text-center">
                    <p className="text-zinc-300 mb-6">
                        Ajude a manter o projeto ativo e recebendo atualizações constantes!
                    </p>

                    <div className="w-full bg-zinc-950/50 rounded-xl border border-zinc-800 p-4 mb-6">
                        <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-2">Chave PIX (E-mail)</p>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 text-sm text-blue-400 font-mono bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20 truncate">
                                {pixKey}
                            </code>
                            <button
                                onClick={handleCopy}
                                className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors"
                                title="Copiar chave"
                            >
                                {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
                            </button>
                        </div>
                    </div>

                    <div className="bg-white p-2 rounded-xl mb-4">
                        <img
                            src="/qrcode-pix.png"
                            alt="QR Code PIX"
                            className="w-48 h-48 object-contain"
                        />
                    </div>
                    <p className="text-xs text-zinc-500">Escaneie o QR Code com seu app de banco</p>
                </div>
            </div>
        </div>
    );
};
