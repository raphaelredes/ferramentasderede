import React from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { clsx } from 'clsx';

interface ConfirmationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    title: string;
    message: React.ReactNode;
    confirmText?: string;
    cancelText?: string;
    type?: 'danger' | 'warning' | 'info';
    isLoading?: boolean;
}

export function ConfirmationModal({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    confirmText = 'Confirmar',
    cancelText = 'Cancelar',
    type = 'danger',
    isLoading = false
}: ConfirmationModalProps) {
    if (!isOpen) return null;

    const colors = {
        danger: {
            icon: 'text-red-500',
            bg: 'bg-red-500/10',
            button: 'bg-red-600 hover:bg-red-700 shadow-red-900/20',
            border: 'border-red-900/50'
        },
        warning: {
            icon: 'text-yellow-500',
            bg: 'bg-yellow-500/10',
            button: 'bg-yellow-600 hover:bg-yellow-700 shadow-yellow-900/20',
            border: 'border-yellow-900/50'
        },
        info: {
            icon: 'text-blue-500',
            bg: 'bg-blue-500/10',
            button: 'bg-blue-600 hover:bg-blue-700 shadow-blue-900/20',
            border: 'border-blue-900/50'
        }
    };

    const color = colors[type];

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn">
            <div className={clsx("bg-zinc-900 border rounded-xl p-6 max-w-md w-full shadow-2xl space-y-6", color.border)}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={clsx("p-3 rounded-full", color.bg, color.icon)}>
                            <AlertTriangle size={24} />
                        </div>
                        <h3 className="text-xl font-bold text-white">{title}</h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={isLoading}
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="text-zinc-300">
                    {message}
                </div>

                <div className="flex gap-3 pt-2">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={isLoading}
                    >
                        {cancelText}
                    </button>
                    <button
                        onClick={() => {
                            onConfirm();
                            // Don't close immediately if loading, parent handles it or we wait
                            // But here onConfirm is void, so we assume it triggers something.
                            // If we want to support async onConfirm, we should change the type.
                            // For now, let's keep existing behavior but respect isLoading if passed.
                            if (!isLoading) onClose();
                        }}
                        className={clsx("flex-1 px-4 py-2 text-white rounded-lg font-medium transition-colors shadow-lg flex items-center justify-center gap-2", color.button, isLoading && "opacity-50 cursor-not-allowed")}
                        disabled={isLoading}
                    >
                        {isLoading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
}
