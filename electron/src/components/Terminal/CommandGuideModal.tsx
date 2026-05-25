import { useMemo, useState } from 'react';
import { X, Copy, Check, Search, AlertTriangle, BookOpen } from 'lucide-react';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';
import { PS_COMMAND_GUIDE } from '../../data/powershellCommands';

interface CommandGuideModalProps {
    isOpen: boolean;
    onClose: () => void;
}

/**
 * Quick-reference modal for PowerShell commands. Operators open this from the
 * Terminal Remoto page and copy snippets straight into the remote PSSession.
 *
 * Design notes
 * - Single-column, scrollable list of sections. The PDF source already groups
 *   the commands logically; we mirror that grouping.
 * - Each card has its own copy button with a 2s "copiado" confirmation.
 * - Search filter narrows on title, description, and command text — operators
 *   often remember a keyword like "porta", "disco", "logoff".
 * - Destructive commands get a yellow warning row so an operator doesn't
 *   paste `Restart-Computer -Force` thinking it'll prompt.
 */
export function CommandGuideModal({ isOpen, onClose }: CommandGuideModalProps) {
    const [search, setSearch] = useState('');
    const [copiedKey, setCopiedKey] = useState<string | null>(null);

    useEscapeToClose(isOpen, onClose);

    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        if (!q) return PS_COMMAND_GUIDE;
        return PS_COMMAND_GUIDE
            .map(section => ({
                ...section,
                commands: section.commands.filter(c =>
                    c.title.toLowerCase().includes(q)
                    || c.description.toLowerCase().includes(q)
                    || c.command.toLowerCase().includes(q),
                ),
            }))
            .filter(section => section.commands.length > 0);
    }, [search]);

    const handleCopy = async (command: string, key: string) => {
        try {
            await navigator.clipboard.writeText(command);
            setCopiedKey(key);
            setTimeout(() => setCopiedKey(prev => (prev === key ? null : prev)), 2000);
        } catch (err) {
            console.error('Falha ao copiar comando:', err);
        }
    };

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4"
            onClick={onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-3xl max-h-[85vh] shadow-2xl overflow-hidden flex flex-col"
                onClick={e => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="cmdguide-title"
            >
                {/* Header */}
                <div className="p-5 border-b border-zinc-800 flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400 flex-shrink-0">
                            <BookOpen size={20} />
                        </div>
                        <div className="min-w-0">
                            <h2 id="cmdguide-title" className="text-lg font-bold text-white">
                                Guia de Comandos PowerShell
                            </h2>
                            <p className="text-xs text-zinc-400 mt-0.5">
                                Selecione e copie o comando para colar diretamente no terminal remoto.
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white flex-shrink-0"
                        aria-label="Fechar"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Search */}
                <div className="px-5 py-3 border-b border-zinc-800/50 bg-zinc-950/30">
                    <div className="relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                        <input
                            type="text"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Buscar por palavra-chave (ex: porta, disco, logoff)..."
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
                            autoFocus
                        />
                    </div>
                </div>

                {/* Sections */}
                <div className="flex-1 overflow-y-auto p-5 space-y-6">
                    {filtered.length === 0 && (
                        <p className="text-center text-zinc-500 text-sm py-8">
                            Nenhum comando encontrado para "{search}".
                        </p>
                    )}
                    {filtered.map(section => (
                        <section key={section.title} className="space-y-3">
                            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                                {section.title}
                            </h3>
                            <div className="space-y-3">
                                {section.commands.map((cmd, idx) => {
                                    const key = `${section.title}::${idx}`;
                                    const copied = copiedKey === key;
                                    return (
                                        <article
                                            key={key}
                                            className="bg-zinc-950/50 border border-zinc-800/70 rounded-lg overflow-hidden"
                                        >
                                            <div className="p-3 border-b border-zinc-800/50">
                                                <h4 className="text-sm font-medium text-zinc-200">
                                                    {cmd.title}
                                                </h4>
                                                <p className="text-xs text-zinc-500 mt-1">{cmd.description}</p>
                                            </div>
                                            {cmd.warning && (
                                                <div className="px-3 py-2 bg-yellow-500/5 border-b border-yellow-900/30 flex items-start gap-2">
                                                    <AlertTriangle size={12} className="text-yellow-500 mt-0.5 flex-shrink-0" />
                                                    <p className="text-[11px] text-yellow-200/90">{cmd.warning}</p>
                                                </div>
                                            )}
                                            <div className="p-3 bg-blue-950/20 flex items-start gap-2">
                                                <pre className="flex-1 text-xs font-mono text-blue-200 whitespace-pre-wrap break-all m-0 leading-relaxed">
                                                    {cmd.command}
                                                </pre>
                                                <button
                                                    onClick={() => handleCopy(cmd.command, key)}
                                                    className="p-1.5 rounded hover:bg-blue-500/10 text-zinc-400 hover:text-blue-400 transition-colors flex-shrink-0"
                                                    title="Copiar comando"
                                                    aria-label={`Copiar comando: ${cmd.title}`}
                                                >
                                                    {copied
                                                        ? <Check size={14} className="text-green-500" />
                                                        : <Copy size={14} />}
                                                </button>
                                            </div>
                                        </article>
                                    );
                                })}
                            </div>
                        </section>
                    ))}
                </div>

                {/* Footer */}
                <div className="px-5 py-3 border-t border-zinc-800 bg-zinc-950/30 text-xs text-zinc-500">
                    Dica: rode <code className="text-blue-400 font-mono">quser</code> antes de
                    {' '}<code className="text-blue-400 font-mono">logoff &lt;id&gt;</code> para
                    confirmar o ID da sessão.
                </div>
            </div>
        </div>
    );
}
