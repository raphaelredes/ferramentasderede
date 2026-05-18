import { X, LogOut, User, Monitor } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';

interface DisconnectUserModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    username: string;
    sessionName: string;
    isLoading?: boolean;
}

export function DisconnectUserModal({
    isOpen,
    onClose,
    onConfirm,
    username,
    sessionName,
    isLoading = false
}: DisconnectUserModalProps) {
    useEscapeToClose(isOpen, isLoading ? () => {} : onClose);
    if (!isOpen) return null;

    return createPortal(
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[9999] p-4 animate-in fade-in duration-200"
            onClick={isLoading ? undefined : onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl overflow-hidden scale-100 animate-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="disconnect-title"
            >
                <div className="p-6">
                    <div className="flex items-start gap-4">
                        <div className="p-3 bg-red-500/10 text-red-500 rounded-xl shrink-0">
                            <LogOut size={24} aria-hidden="true" />
                        </div>
                        <div className="flex-1">
                            <h3 id="disconnect-title" className="text-lg font-bold text-white mb-1">Desconectar Usuário</h3>
                            <p className="text-zinc-400 text-sm leading-relaxed">
                                Tem certeza que deseja encerrar esta sessão? O usuário perderá qualquer trabalho não salvo.
                            </p>
                        </div>
                        <button
                            onClick={onClose}
                            aria-label="Fechar"
                            className="text-zinc-500 hover:text-white transition-colors"
                            disabled={isLoading}
                        >
                            <X size={20} aria-hidden="true" />
                        </button>
                    </div>

                    <div className="mt-6 bg-zinc-950/50 border border-zinc-800/50 rounded-lg p-4 space-y-3">
                        <div className="flex items-center gap-3 text-sm">
                            <User size={16} className="text-zinc-500" />
                            <span className="text-zinc-400">Usuário:</span>
                            <span className="text-white font-medium ml-auto">{username}</span>
                        </div>
                        <div className="flex items-center gap-3 text-sm">
                            <Monitor size={16} className="text-zinc-500" />
                            <span className="text-zinc-400">Sessão:</span>
                            <span className="text-white font-medium ml-auto">{sessionName}</span>
                        </div>
                    </div>

                    <div className="flex justify-end gap-3 mt-6">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-zinc-400 hover:text-white transition-colors text-sm font-medium hover:bg-zinc-800 rounded-lg"
                            disabled={isLoading}
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={onConfirm}
                            className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors text-sm font-medium flex items-center gap-2"
                            disabled={isLoading}
                        >
                            {isLoading ? 'Desconectando...' : 'Desconectar'}
                        </button>
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
}
