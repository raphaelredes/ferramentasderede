import { Trash2 } from 'lucide-react';
import { Host } from '../../types';

interface DeleteHostModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    host: Host | null;
    isDeleting: boolean;
}

export function DeleteHostModal({ isOpen, onClose, onConfirm, host, isDeleting }: DeleteHostModalProps) {
    if (!isOpen || !host) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 text-red-500 mb-4">
                    <div className="p-3 bg-red-500/10 rounded-full">
                        <Trash2 size={24} />
                    </div>
                    <h3 className="text-xl font-bold text-white">Remover Host</h3>
                </div>

                <p className="text-zinc-400 mb-6">
                    Tem certeza que deseja remover o host <span className="text-white font-bold">{host.name}</span> ({host.address})?
                    <br /><br />
                    Esta ação não pode ser desfeita.
                </p>

                <div className="flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-zinc-400 hover:text-white transition-colors"
                        disabled={isDeleting}
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={isDeleting}
                        className="bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed text-red-400 border border-red-900/30 hover:border-red-500/50 px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                    >
                        {isDeleting ? (
                            <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-400" />
                                Removendo...
                            </>
                        ) : (
                            'Confirmar Remoção'
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
