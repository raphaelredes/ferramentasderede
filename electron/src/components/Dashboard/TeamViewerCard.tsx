import React from 'react';
import { ArrowUpDown, RefreshCw, AlertCircle, KeyRound } from 'lucide-react';

export type TvFetchState =
    | { kind: 'idle' }
    | { kind: 'loading' }
    | { kind: 'success'; id: string }
    | { kind: 'needs_credentials'; reason: string }
    | { kind: 'failed'; message: string };

interface TeamViewerCardProps {
    state: TvFetchState;
    initialDomain?: string;
    onConnect: (id: string) => void;
    onSilentRetry: () => void;
    onManualSubmit: (username: string, password: string) => void;
}

export function TeamViewerCard({ state, initialDomain, onConnect, onSilentRetry, onManualSubmit }: TeamViewerCardProps) {
    const baseCls = 'relative group p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl transition-all text-left flex flex-col gap-3 overflow-hidden md:col-span-2';

    if (state.kind === 'success') {
        return (
            <button
                onClick={() => onConnect(state.id)}
                className={`${baseCls} hover:bg-zinc-800 hover:border-cyan-500/50`}
            >
                <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-zinc-800 group-hover:bg-cyan-500/20 w-fit rounded-lg transition-colors">
                        <ArrowUpDown size={24} className="text-zinc-400 group-hover:text-cyan-400 transition-colors rotate-45" />
                    </div>
                    <div>
                        <div className="font-medium text-white group-hover:text-cyan-400 transition-colors">TeamViewer</div>
                        <div className="text-sm text-zinc-500 flex items-center gap-2">
                            ID: <span className="font-mono text-zinc-400">{state.id}</span>
                            <span className="text-xs bg-zinc-800 px-2 py-0.5 rounded text-zinc-500">Conectar Automaticamente</span>
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
                        <RefreshCw size={24} className="text-cyan-400 animate-spin" />
                    </div>
                    <div>
                        <div className="font-medium text-white">TeamViewer</div>
                        <div className="text-sm text-zinc-500">Buscando ID no host via WinRM…</div>
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
                onCancel={onSilentRetry}
            />
        );
    }

    const failMessage = state.kind === 'failed' ? state.message : 'Aguardando…';
    return (
        <div className={baseCls}>
            <div className="flex items-start gap-4">
                <div className="p-3 bg-zinc-800 w-fit rounded-lg">
                    <AlertCircle size={24} className="text-red-400" />
                </div>
                <div className="flex-1">
                    <div className="font-medium text-white">TeamViewer ID não detectado</div>
                    <div className="text-sm text-zinc-500 mt-1">{failMessage}</div>
                    <button
                        onClick={onSilentRetry}
                        className="mt-3 inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300"
                    >
                        <RefreshCw size={12} /> Tentar novamente
                    </button>
                </div>
            </div>
        </div>
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
    onSubmit: (username: string, password: string) => void;
    onCancel: () => void;
}) {
    const [domain, setDomain] = React.useState(initialDomain || '');
    const [user, setUser] = React.useState('');
    const [password, setPassword] = React.useState('');

    const handleFormSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const trimmedUser = user.trim();
        if (!trimmedUser || !password) return;
        const fullUsername = domain.trim()
            ? (trimmedUser.includes('\\') ? trimmedUser : `${domain.trim()}\\${trimmedUser}`)
            : trimmedUser;
        onSubmit(fullUsername, password);
    };

    return (
        <div className="relative p-4 bg-zinc-900/80 border border-zinc-800 rounded-xl md:col-span-2">
            <div className="flex items-start gap-3 mb-3">
                <KeyRound size={18} className="text-cyan-400 mt-0.5 shrink-0" />
                <div>
                    <div className="font-medium text-white text-sm">Credenciais para detectar TeamViewer</div>
                    <div className="text-xs text-zinc-400">{reason}</div>
                </div>
            </div>

            <form onSubmit={handleFormSubmit} className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <input
                        type="text"
                        value={domain}
                        onChange={e => setDomain(e.target.value)}
                        placeholder="Domínio (opcional)"
                        className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
                    />
                    <input
                        type="text"
                        value={user}
                        onChange={e => setUser(e.target.value)}
                        placeholder="Usuário"
                        className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
                    />
                    <input
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="Senha"
                        className="bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
                    />
                </div>
                <div className="flex justify-end gap-2">
                    <button
                        type="button"
                        onClick={onCancel}
                        className="px-3 py-1 text-xs text-zinc-400 hover:text-white"
                    >
                        Cancelar
                    </button>
                    <button
                        type="submit"
                        disabled={!user.trim() || !password}
                        className="px-3 py-1 text-xs bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg font-medium"
                    >
                        Detectar ID
                    </button>
                </div>
            </form>
        </div>
    );
}
