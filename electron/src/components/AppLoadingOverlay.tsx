import React, { useEffect, useState } from 'react';
import { Server } from 'lucide-react';

interface AppLoadingOverlayProps {
    isVisible: boolean;
}

export const AppLoadingOverlay: React.FC<AppLoadingOverlayProps> = ({ isVisible }) => {
    const [shouldRender, setShouldRender] = useState(isVisible);
    const [opacityClass, setOpacityClass] = useState('opacity-100');

    useEffect(() => {
        if (!isVisible) {
            setOpacityClass('opacity-0 pointer-events-none');
            const timer = setTimeout(() => {
                setShouldRender(false);
            }, 600);
            return () => clearTimeout(timer);
        } else {
            setShouldRender(true);
            setOpacityClass('opacity-100');
        }
    }, [isVisible]);

    if (!shouldRender) return null;

    return (
        <div
            className={`fixed inset-0 z-[999999] bg-zinc-950 flex flex-col items-center justify-center select-none transition-opacity duration-500 ease-out ${opacityClass}`}
        >
            <div className="relative w-20 h-20 mb-6 flex items-center justify-center">
                <div className="absolute inset-0 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                <div
                    className="absolute inset-2 border-4 border-indigo-500/20 border-b-indigo-500 rounded-full animate-spin"
                    style={{ animationDirection: 'reverse', animationDuration: '1.6s' }}
                />
                <div className="relative flex items-center justify-center text-blue-500">
                    <Server size={32} className="animate-pulse" />
                </div>
            </div>

            <div className="text-xl font-bold tracking-tight text-white mb-2">
                Ferramentas de Rede
            </div>

            <div className="text-sm text-zinc-400 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                <span>Carregando ambiente e conectando aos hosts...</span>
            </div>

            <div className="w-48 h-1 bg-zinc-800/80 rounded-full overflow-hidden mt-6">
                <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full w-2/5 animate-[shimmer_1.5s_infinite_linear]" />
            </div>
        </div>
    );
};
