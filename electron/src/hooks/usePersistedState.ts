import { useState, useEffect, useCallback } from 'react';

/**
 * Hook para persistir estado no localStorage com serialização automática e fallback seguro.
 */
export function usePersistedState<T>(key: string, initialValue: T): [T, (value: T | ((val: T) => T)) => void, () => void] {
    const [state, setState] = useState<T>(() => {
        try {
            const item = localStorage.getItem(key);
            if (item !== null) {
                return JSON.parse(item);
            }
        } catch (error) {
            console.warn(`Erro ao ler chave localStorage "${key}":`, error);
        }
        return initialValue;
    });

    useEffect(() => {
        try {
            if (state === undefined) {
                localStorage.removeItem(key);
            } else {
                localStorage.setItem(key, JSON.stringify(state));
            }
        } catch (error) {
            console.warn(`Erro ao salvar chave localStorage "${key}":`, error);
        }
    }, [key, state]);

    const reset = useCallback(() => {
        try {
            localStorage.removeItem(key);
            setState(initialValue);
        } catch (e) {
            console.warn(e);
        }
    }, [key, initialValue]);

    return [state, setState, reset];
}
