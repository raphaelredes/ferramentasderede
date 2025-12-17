import React from 'react';
import { Sidebar } from '../components/Sidebar';

interface MainLayoutProps {
    children: React.ReactNode;
}

export function MainLayout({ children }: Omit<MainLayoutProps, 'activeTab' | 'onTabChange'>) {
    return (
        <div className="flex w-screen h-screen bg-zinc-950 text-white overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-x-hidden overflow-y-auto bg-zinc-950">
                <div className="h-full">
                    {children}
                </div>
            </main>
        </div>
    );
}
