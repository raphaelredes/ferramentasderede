import { useState, useEffect } from 'react';
import { X, FolderPlus, Check } from 'lucide-react';

interface SetGroupModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (group: string) => void;
    currentGroup: string;
    existingGroups: string[];
}

export function SetGroupModal({ isOpen, onClose, onConfirm, currentGroup, existingGroups }: SetGroupModalProps) {
    const [group, setGroup] = useState(currentGroup);
    const [isCustom, setIsCustom] = useState(false);

    useEffect(() => {
        setGroup(currentGroup);
        setIsCustom(false);
    }, [currentGroup, isOpen]);

    if (!isOpen) return null;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onConfirm(group);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
                        <FolderPlus size={20} className="text-blue-400" />
                        Definir Grupo
                    </h2>
                    <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-2">
                            Selecione um grupo existente ou crie um novo
                        </label>

                        <div className="flex flex-wrap gap-2 mb-4 max-h-40 overflow-y-auto custom-scrollbar">
                            <button
                                type="button"
                                onClick={() => { setGroup(''); setIsCustom(false); }}
                                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${group === '' && !isCustom ? 'bg-blue-500/20 border-blue-500/50 text-blue-400' : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'}`}
                            >
                                Sem Grupo
                            </button>
                            {existingGroups.map(g => (
                                <button
                                    key={g}
                                    type="button"
                                    onClick={() => { setGroup(g); setIsCustom(false); }}
                                    className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${group === g && !isCustom ? 'bg-blue-500/20 border-blue-500/50 text-blue-400' : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'}`}
                                >
                                    {g}
                                </button>
                            ))}
                            <button
                                type="button"
                                onClick={() => { setGroup(''); setIsCustom(true); }}
                                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${isCustom ? 'bg-blue-500/20 border-blue-500/50 text-blue-400' : 'bg-zinc-800/50 border-zinc-700/50 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'}`}
                            >
                                + Novo Grupo
                            </button>
                        </div>

                        {isCustom && (
                            <div className="animate-in fade-in slide-in-from-top-2 duration-200">
                                <input
                                    type="text"
                                    value={group}
                                    onChange={(e) => setGroup(e.target.value)}
                                    placeholder="Nome do novo grupo"
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-zinc-200 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
                                    autoFocus
                                />
                            </div>
                        )}
                    </div>

                    <div className="flex justify-end gap-3 pt-4 border-t border-zinc-800/50">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                        >
                            <Check size={16} />
                            Salvar
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
