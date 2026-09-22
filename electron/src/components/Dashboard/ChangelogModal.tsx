import { useState, useMemo } from 'react';
import {
    X,
    Sparkles,
    Bug,
    Zap,
    ShieldCheck,
    Wand2,
    Wrench,
    FileText,
    Search,
    Calendar,
    Filter,
    Layers
} from 'lucide-react';
import { createPortal } from 'react-dom';
import { CHANGELOG, type ChangeKind, APP_VERSION } from '../../data/changelog';
import { useEscapeToClose } from '../../hooks/useEscapeToClose';
import { clsx } from 'clsx';

interface ChangelogModalProps {
    isOpen: boolean;
    onClose: () => void;
}

const KIND_META: Record<ChangeKind, { label: string; color: string; bg: string; border: string; Icon: typeof Sparkles }> = {
    feat:     { label: 'Novo',        color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', Icon: Sparkles },
    fix:      { label: 'Correção',    color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/20',   Icon: Bug },
    perf:     { label: 'Performance', color: 'text-violet-400', bg: 'bg-violet-500/10',  border: 'border-violet-500/20',  Icon: Zap },
    security: { label: 'Segurança',   color: 'text-rose-400',    bg: 'bg-rose-500/10',    border: 'border-rose-500/20',    Icon: ShieldCheck },
    ui:       { label: 'Interface',   color: 'text-blue-400',    bg: 'bg-blue-500/10',    border: 'border-blue-500/20',    Icon: Wand2 },
    refactor: { label: 'Refatoração', color: 'text-zinc-400',    bg: 'bg-zinc-500/10',    border: 'border-zinc-500/20',    Icon: Wrench },
    docs:     { label: 'Docs',        color: 'text-cyan-400',    bg: 'bg-cyan-500/10',    border: 'border-cyan-500/20',    Icon: FileText },
};

export function ChangelogModal({ isOpen, onClose }: ChangelogModalProps) {
    useEscapeToClose(isOpen, onClose);

    const [selectedVersion, setSelectedVersion] = useState<string>(APP_VERSION);
    const [selectedKind, setSelectedKind] = useState<ChangeKind | 'all'>('all');
    const [searchQuery, setSearchQuery] = useState('');

    // Lista de versões disponíveis para navegação
    const versions = useMemo(() => CHANGELOG.map(c => c.version), []);

    // Versão atualmente ativa (ou todas se for 'all')
    const currentEntry = useMemo(() => {
        if (selectedVersion === 'all') return null;
        return CHANGELOG.find(c => c.version === selectedVersion) || CHANGELOG[0];
    }, [selectedVersion]);

    // Filtragem de alterações
    const filteredEntries = useMemo(() => {
        const query = searchQuery.trim().toLowerCase();
        const baseEntries = selectedVersion === 'all'
            ? CHANGELOG
            : CHANGELOG.filter(c => c.version === selectedVersion);

        return baseEntries.map(entry => {
            const matchedChanges = entry.changes.filter(change => {
                const matchesKind = selectedKind === 'all' || change.kind === selectedKind;
                const matchesText = !query || change.text.toLowerCase().includes(query) || (entry.title && entry.title.toLowerCase().includes(query));
                return matchesKind && matchesText;
            });
            return {
                ...entry,
                changes: matchedChanges
            };
        }).filter(entry => entry.changes.length > 0);
    }, [selectedVersion, selectedKind, searchQuery]);

    // Estatísticas da versão selecionada
    const stats = useMemo(() => {
        if (!currentEntry) return null;
        const counts: Partial<Record<ChangeKind, number>> = {};
        for (const ch of currentEntry.changes) {
            counts[ch.kind] = (counts[ch.kind] || 0) + 1;
        }
        return counts;
    }, [currentEntry]);

    if (!isOpen) return null;

    return createPortal(
        <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[10000] p-3 sm:p-5 animate-in fade-in duration-200"
            onClick={onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl scale-100 animate-in zoom-in-95 duration-200 overflow-hidden"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="changelog-title"
            >
                {/* Header Principal */}
                <div className="flex items-center justify-between p-4 sm:p-5 border-b border-zinc-800 bg-zinc-950/40 shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-blue-500/10 rounded-xl border border-blue-500/25">
                            <Sparkles size={20} className="text-blue-400" aria-hidden="true" />
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h2 id="changelog-title" className="text-lg font-bold text-white tracking-tight">Histórico de Versões & Melhorias</h2>
                                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold font-mono">
                                    v{APP_VERSION} Atual
                                </span>
                            </div>
                            <p className="text-xs text-zinc-400 mt-0.5">Explore as novidades, correções e atualizações de arquitetura de cada versão.</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Fechar"
                        className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800/60 rounded-xl transition-colors"
                    >
                        <X size={20} aria-hidden="true" />
                    </button>
                </div>

                {/* Barra de Navegação de Versões (Tabs / Pills) */}
                <div className="border-b border-zinc-800 bg-zinc-950/70 p-2.5 sm:px-4 flex items-center justify-between gap-3 overflow-x-auto custom-scrollbar shrink-0">
                    <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mr-1 flex items-center gap-1">
                            <Layers size={13} />
                            Versões:
                        </span>
                        {versions.map((ver) => {
                            const isCurrent = ver === APP_VERSION;
                            const isSelected = selectedVersion === ver;
                            return (
                                <button
                                    key={ver}
                                    type="button"
                                    onClick={() => setSelectedVersion(ver)}
                                    className={clsx(
                                        "px-2.5 py-1 rounded-lg text-xs font-semibold font-mono transition-all flex items-center gap-1.5",
                                        isSelected
                                            ? "bg-blue-600 text-white shadow-md shadow-blue-600/25"
                                            : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 bg-zinc-900 border border-zinc-800"
                                    )}
                                >
                                    <span>v{ver}</span>
                                    {isCurrent && (
                                        <span className={clsx(
                                            "text-[9px] px-1.5 py-0.2 rounded-full uppercase font-bold",
                                            isSelected ? "bg-white/20 text-white" : "bg-emerald-500/20 text-emerald-400"
                                        )}>
                                            Atual
                                        </span>
                                    )}
                                </button>
                            );
                        })}
                        <button
                            type="button"
                            onClick={() => setSelectedVersion('all')}
                            className={clsx(
                                "px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ml-1",
                                selectedVersion === 'all'
                                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/25"
                                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 bg-zinc-900 border border-zinc-800"
                            )}
                        >
                            Ver Todas
                        </button>
                    </div>
                </div>

                {/* Filtros por Categoria e Busca em Tempo Real */}
                <div className="p-3 sm:px-4 bg-zinc-900/60 border-b border-zinc-800/80 flex flex-wrap items-center justify-between gap-3 shrink-0">
                    {/* Filtros de Tipo */}
                    <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mr-1 flex items-center gap-1">
                            <Filter size={12} />
                            Filtro:
                        </span>
                        <button
                            type="button"
                            onClick={() => setSelectedKind('all')}
                            className={clsx(
                                "px-2 py-0.5 rounded text-xs font-medium transition-colors",
                                selectedKind === 'all'
                                    ? "bg-zinc-200 text-zinc-900 font-semibold"
                                    : "text-zinc-400 hover:text-zinc-200 bg-zinc-950 border border-zinc-800"
                            )}
                        >
                            Todos
                        </button>
                        {(['feat', 'security', 'fix', 'perf', 'ui'] as ChangeKind[]).map((kind) => {
                            const meta = KIND_META[kind];
                            const isSelected = selectedKind === kind;
                            return (
                                <button
                                    key={kind}
                                    type="button"
                                    onClick={() => setSelectedKind(isSelected ? 'all' : kind)}
                                    className={clsx(
                                        "px-2 py-0.5 rounded text-xs font-medium transition-colors flex items-center gap-1 border",
                                        isSelected
                                            ? `${meta.bg} ${meta.color} ${meta.border} font-semibold ring-1 ring-inset ring-current`
                                            : "text-zinc-400 hover:text-zinc-200 bg-zinc-950 border-zinc-800"
                                    )}
                                >
                                    <meta.Icon size={12} />
                                    <span>{meta.label}</span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Campo de Busca Rápida */}
                    <div className="relative w-full sm:w-56">
                        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Buscar no histórico..."
                            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-7 py-1 text-xs text-white focus:outline-none focus:border-blue-500 placeholder:text-zinc-600 font-mono"
                        />
                        {searchQuery && (
                            <button
                                type="button"
                                onClick={() => setSearchQuery('')}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                            >
                                <X size={12} />
                            </button>
                        )}
                    </div>
                </div>

                {/* Conteúdo com os Itens de Mudança */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4 sm:p-5 space-y-6">
                    {/* Header Resumo da Versão Ativa (quando visualizando versão única) */}
                    {currentEntry && selectedVersion !== 'all' && (
                        <div className="bg-gradient-to-r from-blue-950/30 to-zinc-900 border border-blue-900/40 rounded-xl p-4 space-y-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <h3 className="text-base font-bold text-white font-mono">Versão {currentEntry.version}</h3>
                                    {currentEntry.version === APP_VERSION && (
                                        <span className="text-[10px] uppercase font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                                            Versão em Execução
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center gap-1.5 text-xs text-zinc-400 font-mono">
                                    <Calendar size={13} className="text-zinc-500" />
                                    <span>Lançada em {currentEntry.date}</span>
                                </div>
                            </div>

                            {currentEntry.title && (
                                <p className="text-xs sm:text-sm text-zinc-200 font-medium leading-relaxed">
                                    {currentEntry.title}
                                </p>
                            )}

                            {/* Badge Stats */}
                            {stats && (
                                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                    <span className="text-[11px] text-zinc-500">Resumo:</span>
                                    {stats.feat && (
                                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
                                            {stats.feat} Novos Recursos
                                        </span>
                                    )}
                                    {stats.security && (
                                        <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 font-medium">
                                            {stats.security} Segurança & NIST
                                        </span>
                                    )}
                                    {stats.fix && (
                                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
                                            {stats.fix} Correções
                                        </span>
                                    )}
                                    {stats.ui && (
                                        <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 font-medium">
                                            {stats.ui} Interface & Usabilidade
                                        </span>
                                    )}
                                    {stats.perf && (
                                        <span className="text-[10px] px-2 py-0.5 rounded bg-violet-500/10 text-violet-300 border border-violet-500/20 font-medium">
                                            {stats.perf} Performance
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Listagem das Entradas Filtradas */}
                    {filteredEntries.length === 0 ? (
                        <div className="py-12 flex flex-col items-center justify-center text-center text-zinc-500">
                            <Search size={36} className="opacity-30 mb-2" />
                            <p className="text-sm font-medium text-zinc-400">Nenhuma alteração encontrada</p>
                            <p className="text-xs text-zinc-600 mt-1">Tente remover o filtro de categoria ou a busca por texto.</p>
                            <button
                                type="button"
                                onClick={() => { setSelectedKind('all'); setSearchQuery(''); }}
                                className="mt-3 px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-xs text-white rounded-lg transition-colors"
                            >
                                Limpar Filtros
                            </button>
                        </div>
                    ) : (
                        filteredEntries.map((entry) => (
                            <section key={entry.version} className="space-y-3">
                                {selectedVersion === 'all' && (
                                    <div className="flex items-baseline justify-between border-b border-zinc-800/80 pb-2">
                                        <div className="flex items-center gap-2">
                                            <h3 className="text-base font-bold text-white font-mono">v{entry.version}</h3>
                                            {entry.version === APP_VERSION && (
                                                <span className="text-[10px] uppercase font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                                                    Atual
                                                </span>
                                            )}
                                        </div>
                                        <span className="text-xs text-zinc-500 font-mono">{entry.date}</span>
                                    </div>
                                )}

                                <div className="grid grid-cols-1 gap-2.5">
                                    {entry.changes.map((change, i) => {
                                        const meta = KIND_META[change.kind];
                                        const Icon = meta.Icon;
                                        return (
                                            <div
                                                key={i}
                                                className="bg-zinc-950/70 border border-zinc-800/80 hover:border-zinc-700/80 rounded-xl p-3 sm:p-3.5 transition-colors flex items-start gap-3"
                                            >
                                                <span
                                                    className={clsx(
                                                        "shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border mt-0.5",
                                                        meta.bg, meta.color, meta.border
                                                    )}
                                                    title={meta.label}
                                                >
                                                    <Icon size={12} />
                                                    <span>{meta.label}</span>
                                                </span>
                                                <div className="flex-1 text-xs sm:text-sm text-zinc-300 leading-relaxed font-sans">
                                                    {change.text}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </section>
                        ))
                    )}
                </div>

                {/* Rodapé do Modal */}
                <div className="p-3 sm:p-4 border-t border-zinc-800 bg-zinc-950/50 flex items-center justify-between shrink-0">
                    <span className="text-xs text-zinc-500">
                        Total de versões indexadas: <strong>{CHANGELOG.length} releases</strong>
                    </span>
                    <button
                        onClick={onClose}
                        className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-semibold transition-colors"
                    >
                        Fechar
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
}
