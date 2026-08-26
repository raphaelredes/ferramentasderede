import React, { useState, useEffect } from 'react';
import { BookOpen, Copy, Play, Plus, Trash2, X } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';

interface Snippet {
    id: number;
    title: string;
    description: string;
    command: string;
    category: string;
    type: string;
}

interface SnippetsDrawerProps {
    isOpen: boolean;
    onClose: () => void;
    onSelectSnippet: (command: string) => void;
}

export function SnippetsDrawer({ isOpen, onClose, onSelectSnippet }: SnippetsDrawerProps) {
    const { showToast } = useToast();
    const [snippets, setSnippets] = useState<Snippet[]>([]);
    const [selectedCategory, setSelectedCategory] = useState<string>('Todos');
    const [newTitle, setNewTitle] = useState('');
    const [newCommand, setNewCommand] = useState('');
    const [newCategory, setNewCategory] = useState('Geral');
    const [isCreating, setIsCreating] = useState(false);

    const loadSnippets = async () => {
        try {
            const res = await fetch(`${API_BASE}/batch/snippets`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setSnippets(data);
        } catch (err: any) {
            showToast(`Erro ao carregar snippets: ${err.message}`, 'error');
        }
    };

    useEffect(() => {
        if (isOpen) {
            loadSnippets();
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const categories = ['Todos', ...Array.from(new Set(snippets.map(s => s.category)))];
    const filteredSnippets = selectedCategory === 'Todos' 
        ? snippets 
        : snippets.filter(s => s.category === selectedCategory);

    const handleCreateSnippet = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newTitle.trim() || !newCommand.trim()) return;

        try {
            const res = await fetch(`${API_BASE}/batch/snippets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: newTitle.trim(),
                    command: newCommand.trim(),
                    category: newCategory.trim() || 'Geral',
                    type: 'powershell'
                })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            showToast('Snippet adicionado com sucesso!', 'success');
            setNewTitle('');
            setNewCommand('');
            setIsCreating(false);
            loadSnippets();
        } catch (err: any) {
            showToast(`Erro ao salvar snippet: ${err.message}`, 'error');
        }
    };

    const handleDeleteSnippet = async (id: number) => {
        try {
            const res = await fetch(`${API_BASE}/batch/snippets/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            showToast('Snippet excluído.', 'info');
            loadSnippets();
        } catch (err: any) {
            showToast(`Erro ao excluir: ${err.message}`, 'error');
        }
    };

    return (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-zinc-900 border-l border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800 bg-zinc-950">
                <div className="flex items-center gap-2">
                    <BookOpen size={18} className="text-blue-400" />
                    <h3 className="text-sm font-semibold text-zinc-100">Biblioteca de Snippets</h3>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setIsCreating(!isCreating)}
                        className="p-1.5 bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white rounded-lg transition-colors text-xs font-medium flex items-center gap-1"
                        title="Novo Snippet"
                    >
                        <Plus size={14} />
                    </button>
                    <button onClick={onClose} className="p-1 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800">
                        <X size={18} />
                    </button>
                </div>
            </div>

            {/* Category Tabs */}
            <div className="flex gap-1 overflow-x-auto p-2 bg-zinc-950/60 border-b border-zinc-800 text-xs">
                {categories.map(c => (
                    <button
                        key={c}
                        onClick={() => setSelectedCategory(c)}
                        className={`px-2.5 py-1 rounded-md transition-colors whitespace-nowrap ${selectedCategory === c ? 'bg-blue-600 text-white font-medium' : 'text-zinc-400 hover:text-zinc-200'}`}
                    >
                        {c}
                    </button>
                ))}
            </div>

            {/* Create Form */}
            {isCreating && (
                <form onSubmit={handleCreateSnippet} className="p-4 bg-zinc-950/90 border-b border-zinc-800 space-y-2.5 text-xs">
                    <input
                        type="text"
                        placeholder="Título do snippet..."
                        value={newTitle}
                        onChange={e => setNewTitle(e.target.value)}
                        required
                        className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-blue-500"
                    />
                    <textarea
                        placeholder="Comando PowerShell..."
                        value={newCommand}
                        onChange={e => setNewCommand(e.target.value)}
                        required
                        rows={2}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1.5 font-mono text-zinc-200 focus:outline-none focus:border-blue-500 resize-none"
                    />
                    <div className="flex gap-2">
                        <input
                            type="text"
                            placeholder="Categoria (ex: Rede, Serviços)"
                            value={newCategory}
                            onChange={e => setNewCategory(e.target.value)}
                            className="bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1.5 text-zinc-200 flex-1 focus:outline-none focus:border-blue-500"
                        />
                        <button type="submit" className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium">
                            Salvar
                        </button>
                    </div>
                </form>
            )}

            {/* List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {filteredSnippets.map(snippet => (
                    <div key={snippet.id} className="p-3 bg-zinc-950 border border-zinc-800/80 rounded-xl space-y-2 text-xs hover:border-zinc-700 transition-colors">
                        <div className="flex items-center justify-between">
                            <span className="font-semibold text-zinc-200">{snippet.title}</span>
                            <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 text-[10px]">
                                {snippet.category}
                            </span>
                        </div>
                        {snippet.description && (
                            <p className="text-zinc-400 text-[11px]">{snippet.description}</p>
                        )}
                        <pre className="p-2 bg-zinc-900 rounded font-mono text-[11px] text-blue-300 overflow-x-auto whitespace-pre-wrap">
                            {snippet.command}
                        </pre>
                        <div className="flex items-center justify-end gap-2 pt-1 border-t border-zinc-800/50">
                            <button
                                onClick={() => handleDeleteSnippet(snippet.id)}
                                className="p-1 text-zinc-500 hover:text-rose-400 transition-colors"
                                title="Excluir"
                            >
                                <Trash2 size={13} />
                            </button>
                            <button
                                onClick={() => {
                                    navigator.clipboard.writeText(snippet.command);
                                    showToast('Comando copiado!', 'info');
                                }}
                                className="p-1 text-zinc-400 hover:text-zinc-200 transition-colors"
                                title="Copiar"
                            >
                                <Copy size={13} />
                            </button>
                            <button
                                onClick={() => {
                                    onSelectSnippet(snippet.command);
                                    onClose();
                                }}
                                className="flex items-center gap-1 px-2.5 py-1 bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white rounded transition-colors text-[11px] font-medium"
                            >
                                <Play size={12} />
                                Inserir no Terminal
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
