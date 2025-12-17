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

    React.useEffect(() => {
        const handleFocusChange = (_event: any, focused: boolean) => {
            setIsWindowFocused(focused);
            if (focused && toastQueue.current.length > 0) {
                // Flush queue
                toastQueue.current.forEach(t => {
                    addToast(t.message, t.type);
                });
                toastQueue.current = [];
            }
        };

        // @ts-ignore
        window.electron?.ipcRenderer?.on('window-focus-change', handleFocusChange);

        return () => {
            // Cleanup if needed, though usually not necessary for main app component
        };
    }, []);

    const addToast = useCallback((message: string, type: ToastType) => {
        const id = Math.random().toString(36).substring(2, 9);
        setToasts(prev => [...prev, { id, message, type }]);
    }, []);

    const showToast = useCallback((message: string, type: ToastType) => {
        if (isWindowFocused) {
            addToast(message, type);
        } else {
            toastQueue.current.push({ message, type });
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
