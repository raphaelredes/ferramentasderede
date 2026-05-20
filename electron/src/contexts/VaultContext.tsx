import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { VaultCredential } from '../types';
import { API_BASE } from '../config/api';

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
            const res = await fetch(`${API_BASE}/security/status`);
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
            const res = await fetch(`${API_BASE}/security/credentials`);
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
            const res = await fetch(`${API_BASE}/security/unlock`, {
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
            await fetch(`${API_BASE}/security/lock`, { method: 'POST' });
            setIsUnlocked(false);
            setVaultCredentials([]);
        } catch (error) {
            console.error("Erro ao bloquear cofre:", error);
        }
    };

    useEffect(() => {
        // Recursive setTimeout with exponential backoff on failure — same
        // pattern as MonitoringContext. Vault state changes are rare so the
        // happy path polls every 30s; if /security/status fails (backend
        // restart, network blip) we back off up to 2 min instead of hammering.
        let timeoutId: number | null = null;
        let cancelled = false;
        let failureCount = 0;
        const BASE_DELAY_MS = 30_000;
        const MAX_DELAY_MS = 120_000;

        const tick = async () => {
            if (cancelled) return;
            try {
                const res = await fetch(`${API_BASE}/security/status`);
                if (res.ok) {
                    const data = await res.json();
                    setHasVault(data.has_vault);
                    setIsUnlocked(data.is_unlocked);
                    if (data.is_unlocked) {
                        refreshCredentials();
                    } else {
                        setVaultCredentials([]);
                    }
                    failureCount = 0;
                } else {
                    failureCount += 1;
                }
            } catch (error) {
                failureCount += 1;
                console.debug('VaultContext poll failed:', error);
            } finally {
                setIsLoading(false);
            }

            if (cancelled) return;
            const delay = Math.min(BASE_DELAY_MS * Math.max(1, failureCount), MAX_DELAY_MS);
            timeoutId = window.setTimeout(tick, delay);
        };

        tick();
        return () => {
            cancelled = true;
            if (timeoutId !== null) window.clearTimeout(timeoutId);
        };
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
