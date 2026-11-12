import React, { useState } from 'react';
import { Monitor, RefreshCw, AlertCircle, KeyRound, DownloadCloud } from 'lucide-react';

export type HtdFetchState =
    | { kind: 'idle' }
    | { kind: 'loading'; status?: string }
    | { kind: 'success'; id: string }
    | { kind: 'needs_credentials'; reason: string }
    | { kind: 'failed'; message: string };

interface HopToDeskCardProps {
    state: HtdFetchState;
    initialDomain?: string;
    onConnect: (id: string) => void;
    onDeploy: () => void;
    onManualSubmit: (username: string, password: string) => void;
}

export function HopToDeskCard({ state, initialDomain, onConnect, onDeploy, onManualSubmit }: HopToDeskCardProps) {
    const baseCls = 'relative group p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden md:col-span-2';

    if (state.kind === 'success') {
        return (
            <button
                onClick={() => onConnect(state.id)}
                className={`${baseCls} hover:bg-zinc-800 hover:border-emerald-500/50`}
            >
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-zinc-800 group-hover:bg-emerald-500/20 w-fit rounded-lg transition-colors">
                        <Monitor size={24} className="text-zinc-400 group-hover:text-emerald-400 transition-colors" />
                    </div>
                    <div>
                        <div className="font-medium text-white group-hover:text-emerald-400 transition-colors">HopToDesk</div>
                        <div className="text-sm text-zinc-500 flex items-center gap-2">
                            ID: <span className="font-mono text-emerald-300 font-semibold">{state.id}</span>
                            <span className="text-xs bg-emerald-950/80 border border-emerald-800/60 text-emerald-400 px-2 py-0.5 rounded">Conectar Automaticamente</span>
                        </div>
                    </div>
                </div>
            </button>
        );
    }

    if (state.kind === 'loading') {
        return (
            <div className={baseCls}>
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-zinc-800 w-fit rounded-lg">
                        <RefreshCw size={24} className="text-emerald-400 animate-spin" />
                    </div>
                    <div>
                        <div className="font-medium text-white">HopToDesk</div>
                        <div className="text-sm text-zinc-400">{state.status || 'Implantando HopToDesk no host remoto…'}</div>
                    </div>
                </div>
            </div>
        );
    }

    if (state.kind === 'needs_credentials') {
        return (
            <ManualCredentialsForm
                reason={state.reason}
                initialDomain={initialDomain}
                onSubmit={onManualSubmit}
                onCancel={onDeploy}
            />
        );
    }

    if (state.kind === 'failed') {
        return (
            <div className={baseCls}>
                <div className="flex items-start gap-4">
                    <div className="p-3 bg-zinc-800 w-fit rounded-lg">
                        <AlertCircle size={24} className="text-red-400" />
                    </div>
                    <div className="flex-1">
                        <div className="font-medium text-white">HopToDesk: Falha na Implantação</div>
                        <div className="text-sm text-zinc-500 mt-1">{state.message}</div>
                        <button
                            onClick={onDeploy}
                            className="mt-3 inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300"
                        >
                            <RefreshCw size={12} /> Tentar novamente
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Estado 'idle': Oferece botão para implantar e obter ID
    return (
        <button
            onClick={onDeploy}
            className={`${baseCls} hover:bg-zinc-800 hover:border-emerald-500/50 cursor-pointer`}
        >
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-4">
                <div className="p-3 bg-zinc-800 group-hover:bg-emerald-500/20 w-fit rounded-lg transition-colors">
                    <DownloadCloud size={24} className="text-zinc-400 group-hover:text-emerald-400 transition-colors" />
                </div>
                <div>
                    <div className="font-medium text-white group-hover:text-emerald-400 transition-colors">HopToDesk</div>
                    <div className="text-sm text-zinc-500">
                        Clique para baixar, copiar para a Área de Trabalho Pública e capturar o ID automaticamente
                    </div>
                </div>
            </div>
        </button>
    );
}

function ManualCredentialsForm({
    reason,
    initialDomain,
    onSubmit,
    onCancel,
}: {
    reason: string;
    initialDomain?: string;
    onSubmit: (user: string, pass: string) => void;
    onCancel: () => void;
}) {
    const [user, setUser] = useState('');
    const [pass, setPass] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!user.trim() || !pass) return;
        const finalUser = user.includes('\\') || user.includes('@') || !initialDomain
            ? user.trim()
            : `${initialDomain}\\${user.trim()}`;
        onSubmit(finalUser, pass);
    };

    return (
        <form onSubmit={handleSubmit} className="p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl flex flex-col gap-3 md:col-span-2">
            <div className="flex items-center gap-2 text-amber-400 text-xs">
                <KeyRound size={14} />
                <span>Credenciais Administrativas para Implantar HopToDesk: {reason}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <input
                    type="text"
                    placeholder={initialDomain ? `usuario ou ${initialDomain}\\usuario` : 'usuario'}
                    value={user}
                    onChange={(e) => setUser(e.target.value)}
                    className="px-3 py-1.5 bg-zinc-800/80 border border-zinc-700 rounded text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                    autoFocus
                />
                <input
                    type="password"
                    placeholder="Senha administrativa"
                    value={pass}
                    onChange={(e) => setPass(e.target.value)}
                    className="px-3 py-1.5 bg-zinc-800/80 border border-zinc-700 rounded text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                />
            </div>
            <div className="flex justify-end gap-2 mt-1">
                <button
                    type="button"
                    onClick={onCancel}
                    className="px-3 py-1 text-xs text-zinc-400 hover:text-white"
                >
                    Cancelar
                </button>
                <button
                    type="submit"
                    disabled={!user.trim() || !pass}
                    className="px-3 py-1 text-xs bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded font-medium transition-colors"
                >
                    Implantar & Conectar
                </button>
            </div>
        </form>
    );
}
