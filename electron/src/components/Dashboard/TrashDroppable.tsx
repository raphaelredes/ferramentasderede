import { useDroppable } from '@dnd-kit/core';
import { Trash2 } from 'lucide-react';

export function TrashDroppable() {
    const { isOver, setNodeRef } = useDroppable({
        id: 'trash-droppable',
    });

    return (
        <div
            ref={setNodeRef}
            className={`transition-all duration-300 ease-out ${isOver ? 'scale-110 -translate-y-2' : 'scale-100 translate-y-0'
                }`}
        >
            <div className={`
                relative flex items-center justify-center w-12 h-12 rounded-full 
                border-2 backdrop-blur-md shadow-2xl transition-all duration-300
                ${isOver
                    ? 'bg-red-500/30 border-red-500 text-red-100 shadow-[0_0_30px_rgba(239,68,68,0.5)]'
                    : 'bg-zinc-900/60 border-zinc-700/50 text-zinc-400 hover:border-red-500/50 hover:text-red-400 shadow-xl'
                }
            `}>
                <Trash2
                    size={20}
                    className={`transition-transform duration-300 ${isOver ? 'scale-110' : 'scale-100'}`}
                    strokeWidth={isOver ? 2.5 : 2}
                />

                {/* Glow effect background */}
                <div className={`absolute inset-0 rounded-full transition-opacity duration-300 ${isOver ? 'opacity-100 bg-red-500/20 blur-lg' : 'opacity-0'
                    }`} />
            </div>

            <div className={`
                absolute top-full left-1/2 -translate-x-1/2 mt-2 whitespace-nowrap
                px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase
                backdrop-blur-sm transition-all duration-300
                ${isOver
                    ? 'bg-red-500 text-white opacity-100 translate-y-0'
                    : 'bg-zinc-900/80 text-zinc-500 opacity-0 -translate-y-1'
                }
            `}>
                Remover
            </div>
        </div>
    );
}
