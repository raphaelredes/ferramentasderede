import React from 'react';
import { Clock, RotateCcw } from 'lucide-react';

interface LastExecutionBadgeProps {
    timestamp?: string | number | null;
    target?: string | null;
    onClear?: () => void;
    label?: string;
}

export function LastExecutionBadge({ timestamp, target, onClear, label }: LastExecutionBadgeProps) {
    if (!timestamp) return null;

    let formatted = '';
    try {
        const d = typeof timestamp === 'number' ? new Date(timestamp) : new Date(timestamp);
        if (!isNaN(d.getTime())) {
            const dateStr = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            const timeStr = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            formatted = `${dateStr} às ${timeStr}`;
        } else {
            formatted = String(timestamp);
        }
    } catch {
        formatted = String(timestamp);
    }

    return (
        <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-400">
            <div className="flex items-center gap-1.5 flex-wrap">
                <Clock size={13} className="text-blue-400 shrink-0" />
                <span>{label || 'Última execução'}:</span>
                <span className="text-zinc-200 font-medium">{formatted}</span>
                {target && (
                    <span className="text-zinc-500 font-mono">({target})</span>
                )}
            </div>
            {onClear && (
                <button
                    onClick={onClear}
                    type="button"
                    className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-red-400 transition-colors p-0.5 rounded shrink-0 ml-auto"
                    title="Limpar resultado salvo"
                >
                    <RotateCcw size={11} />
                    <span>Limpar</span>
                </button>
            )}
        </div>
    );
}

