import React, { createContext, useContext, useState, useCallback } from 'react';

interface LoadingContextType {
    isLoading: (id: string) => boolean;
    setLoading: (id: string, isLoading: boolean) => void;
}

const LoadingContext = createContext<LoadingContextType | undefined>(undefined);

export const LoadingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [loadingStates, setLoadingStates] = useState<Record<string, boolean>>({});

    const setLoading = useCallback((id: string, isLoading: boolean) => {
        setLoadingStates(prev => {
            if (prev[id] === isLoading) return prev;
            return { ...prev, [id]: isLoading };
        });
    }, []);

    const isLoading = useCallback((id: string) => {
        return !!loadingStates[id];
    }, [loadingStates]);

    return (
        <LoadingContext.Provider value={{ isLoading, setLoading }}>
            {children}
        </LoadingContext.Provider>
    );
};

export const useLoading = () => {
    const context = useContext(LoadingContext);
    if (context === undefined) {
        throw new Error('useLoading must be used within a LoadingProvider');
    }
    return context;
};
