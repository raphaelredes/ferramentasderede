import React, { createContext, useContext, useState, useCallback } from 'react';
import { Toast, ToastType } from '../components/Toast/Toast';

interface ToastContextType {
    showToast: (message: string, type: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [toasts, setToasts] = useState<Array<{ id: string; message: string; type: ToastType }>>([]);
    const [isWindowFocused, setIsWindowFocused] = useState(true);
    const toastQueue = React.useRef<Array<{ message: string; type: ToastType }>>([]);

    const addToast = useCallback((message: string, type: ToastType) => {
        const id = Math.random().toString(36).substring(2, 9);
        setToasts(prev => [...prev, { id, message, type }]);
    }, []);

    React.useEffect(() => {
        const handleFocusChange = (focused: boolean) => {
            setIsWindowFocused(focused);
            if (focused && toastQueue.current.length > 0) {
                toastQueue.current.forEach(t => addToast(t.message, t.type));
                toastQueue.current = [];
            }
        };

        // Returns its own unsubscribe so StrictMode remounts don't stack listeners.
        const unsubscribe = window.electron?.onWindowFocusChange?.(handleFocusChange);
        return () => unsubscribe?.();
    }, [addToast]);

    // Cap on the queue so a long monitoring session with the window
    // minimized doesn't accumulate hundreds of "host online"/"offline" toasts
    // that all fire at once on refocus. 20 entries is enough to communicate
    // "something happened while you were away" without spam.
    const TOAST_QUEUE_CAP = 20;

    const showToast = useCallback((message: string, type: ToastType) => {
        if (isWindowFocused) {
            addToast(message, type);
        } else {
            // Collapse consecutive identical toasts so e.g. 50 ping flaps
            // collapse to a single entry.
            const last = toastQueue.current[toastQueue.current.length - 1];
            if (last && last.message === message && last.type === type) return;
            toastQueue.current.push({ message, type });
            if (toastQueue.current.length > TOAST_QUEUE_CAP) {
                // Drop oldest — newest entries are more relevant on refocus.
                toastQueue.current.splice(0, toastQueue.current.length - TOAST_QUEUE_CAP);
            }
        }
    }, [isWindowFocused, addToast]);

    const removeToast = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <div className="fixed bottom-8 right-8 z-[100] flex flex-col gap-3 pointer-events-none">
                {toasts.map(toast => (
                    <div key={toast.id} className="pointer-events-auto">
                        <Toast
                            id={toast.id}
                            message={toast.message}
                            type={toast.type}
                            onClose={removeToast}
                        />
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};

export const useToast = () => {
    const context = useContext(ToastContext);
    if (context === undefined) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};
