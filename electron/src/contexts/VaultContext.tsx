import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { VaultCredential } from '../types';

interface VaultContextType {
    hasVault: boolean;
    isUnlocked: boolean;
    vaultCredentials: VaultCredential[];
    isLoading: boolean;
    unlock: (password: string, hint?: string) => Promise<boolean>;
    lock: () => Promise<void>;
    refreshStatus: () => Promise<void>;
    refreshCredentials: () => Promise<void>;
    autoLockTimeout: number;
    setAutoLockTimeout: (minutes: number) => void;
}

const VaultContext = createContext<VaultContextType | undefined>(undefined);

export function VaultProvider({ children }: { children: ReactNode }) {
    const [hasVault, setHasVault] = useState(false);
    const [isUnlocked, setIsUnlocked] = useState(false);
    const [vaultCredentials, setVaultCredentials] = useState<VaultCredential[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Auto-lock state (default 5 minutes)
    const [autoLockTimeout, setAutoLockTimeoutState] = useState<number>(() => {
        const saved = localStorage.getItem('vault_auto_lock_timeout');
        return saved ? parseInt(saved, 10) : 5;
    });

    const setAutoLockTimeout = (minutes: number) => {
        setAutoLockTimeoutState(minutes);
        localStorage.setItem('vault_auto_lock_timeout', minutes.toString());
    };

    const refreshStatus = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8000/security/status');
            if (res.ok) {
                const data = await res.json();
                setHasVault(data.has_vault);
                setIsUnlocked(data.is_unlocked);
                if (data.is_unlocked) {
                    refreshCredentials();
                } else {
                    setVaultCredentials([]);
                }
            }
        } catch (error) {
            console.error("Erro ao verificar status do cofre:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const refreshCredentials = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8000/security/credentials');
            if (res.ok) {
                const data = await res.json();
                setVaultCredentials(data);
            }
        } catch (error) {
            console.error("Erro ao buscar credenciais:", error);
        }
    };

    const unlock = async (password: string, hint?: string): Promise<boolean> => {
        try {
            const res = await fetch('http://127.0.0.1:8000/security/unlock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password, hint })
            });

            if (res.ok) {
                setIsUnlocked(true);
                refreshCredentials();
                return true;
            }
            return false;
        } catch (error) {
            console.error("Erro ao desbloquear cofre:", error);
            return false;
        }
    };

    const lock = async () => {
        try {
            await fetch('http://127.0.0.1:8000/security/lock', { method: 'POST' });
            setIsUnlocked(false);
            setVaultCredentials([]);
        } catch (error) {
            console.error("Erro ao bloquear cofre:", error);
        }
    };

    useEffect(() => {
        refreshStatus();
        // Poll status every 5 seconds to check for auto-lock or external changes
        const interval = setInterval(refreshStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    // Auto-lock logic
    useEffect(() => {
        if (!isUnlocked || autoLockTimeout === 0) return;

        let timeoutId: NodeJS.Timeout;

        const resetTimer = () => {
            if (timeoutId) clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                console.log("Auto-locking vault due to inactivity");
                lock();
            }, autoLockTimeout * 60 * 1000);
        };

        // Initial set
        resetTimer();

        // Event listeners for activity
        const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart'];
        const handleActivity = () => resetTimer();

        events.forEach(event => {
            window.addEventListener(event, handleActivity);
        });

        return () => {
            if (timeoutId) clearTimeout(timeoutId);
            events.forEach(event => {
                window.removeEventListener(event, handleActivity);
            });
        };
    }, [isUnlocked, autoLockTimeout]);

    return (
        <VaultContext.Provider value={{
            hasVault,
            isUnlocked,
            vaultCredentials,
            isLoading,
            unlock,
            lock,
            refreshStatus,
            refreshCredentials,
            autoLockTimeout,
            setAutoLockTimeout
        }}>
            {children}
        </VaultContext.Provider>
    );
}

export function useVault() {
    const context = useContext(VaultContext);
    if (context === undefined) {
        throw new Error('useVault must be used within a VaultProvider');
    }
    return context;
}
