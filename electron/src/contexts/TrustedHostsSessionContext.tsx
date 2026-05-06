import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

/**
 * Tracks which target IPs the operator has approved for TrustedHosts elevation
 * during the current app session. Approval here means "skip the modal next
 * time" — the actual TrustedHosts mutation still happens per-request via the
 * X-Temp-Auth header, so the registry change is still added/removed atomically
 * around each individual call.
 *
 * Scope is intentionally process-wide and ephemeral: closing the app drops the
 * set. We do not persist this to disk because (a) it would outlive the
 * operator's intent and (b) it would make a privileged change easy to forget.
 */
interface TrustedHostsSessionContextType {
    isApproved: (ip: string) => boolean;
    approve: (ip: string) => void;
    revoke: (ip: string) => void;
    clearAll: () => void;
}

const TrustedHostsSessionContext = createContext<TrustedHostsSessionContextType | undefined>(undefined);

export const TrustedHostsSessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // useState rather than useRef so consumers re-render when the set changes.
    const [, forceRender] = useState(0);
    const setRef = useRef<Set<string>>(new Set());

    const isApproved = useCallback((ip: string) => setRef.current.has(ip), []);

    const approve = useCallback((ip: string) => {
        if (!setRef.current.has(ip)) {
            setRef.current.add(ip);
            forceRender(n => n + 1);
        }
    }, []);

    const revoke = useCallback((ip: string) => {
        if (setRef.current.delete(ip)) {
            forceRender(n => n + 1);
        }
    }, []);

    const clearAll = useCallback(() => {
        if (setRef.current.size > 0) {
            setRef.current.clear();
            forceRender(n => n + 1);
        }
    }, []);

    const value = useMemo<TrustedHostsSessionContextType>(() => ({
        isApproved,
        approve,
        revoke,
        clearAll,
    }), [isApproved, approve, revoke, clearAll]);

    return (
        <TrustedHostsSessionContext.Provider value={value}>
            {children}
        </TrustedHostsSessionContext.Provider>
    );
};

export const useTrustedHostsSession = (): TrustedHostsSessionContextType => {
    const ctx = useContext(TrustedHostsSessionContext);
    if (!ctx) {
        throw new Error('useTrustedHostsSession must be used inside TrustedHostsSessionProvider');
    }
    return ctx;
};
