import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastProps {
    id: string;
    type: ToastType;
    message: string;
    onClose: (id: string) => void;
    duration?: number;
}

export const Toast: React.FC<ToastProps> = ({ id, type, message, onClose, duration = 5000 }) => {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose(id);
        }, duration);

        return () => clearTimeout(timer);
    }, [id, duration, onClose]);

    const icons = {
        success: <CheckCircle size={20} className="text-green-400" />,
        error: <AlertCircle size={20} className="text-red-400" />,
        info: <Info size={20} className="text-blue-400" />,
        warning: <AlertTriangle size={20} className="text-yellow-400" />
    };

    const styles = {
        success: 'bg-zinc-900 border-green-500/20 shadow-green-900/10',
        error: 'bg-zinc-900 border-red-500/20 shadow-red-900/10',
        info: 'bg-zinc-900 border-blue-500/20 shadow-blue-900/10',
        warning: 'bg-zinc-900 border-yellow-500/20 shadow-yellow-900/10'
    };

    return (
        <div className={`
            flex items-center gap-3 p-4 rounded-xl border shadow-lg 
            animate-in slide-in-from-right-full fade-in duration-300
            min-w-[300px] max-w-md
            ${styles[type]}
        `}>
            <div className="shrink-0">
                {icons[type]}
            </div>
            <p className="text-sm text-zinc-200 font-medium flex-1">{message}</p>
            <button
                onClick={() => onClose(id)}
                className="p-1 hover:bg-white/10 rounded-lg text-zinc-500 hover:text-white transition-colors"
            >
                <X size={16} />
            </button>
        </div>
    );
};
