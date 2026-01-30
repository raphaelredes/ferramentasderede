import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { ShieldAlert, Check, Loader2, User, Key, ChevronDown, ChevronRight } from 'lucide-react';

interface TrustedHostsModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (username?: string, password?: string) => Promise<void>;
}

const TrustedHostsModal: React.FC<TrustedHostsModalProps> = ({ isOpen, onClose, onConfirm }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showCredentials, setShowCredentials] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    if (!isOpen) return null;

    const handleConfirm = async () => {
        setIsLoading(true);
        setError(null);
        try {
            if (showCredentials && username && password) {
                await onConfirm(username, password);
            } else {
                await onConfirm();
            }
            // Modal will be closed by parent after action succeeds
        } catch (err: any) {
            let errorMessage = err.message || "Falha ao configurar TrustedHosts.";

            // Translate common auth errors
            if (errorMessage.includes("Failed to authenticate") || errorMessage.includes("Falha em todos os métodos")) {
                errorMessage = "Falha na autenticação. Pode ser uma credencial incorreta ou um usuário de domínio diferente sem permissão administrativa. Por favor, verifique e tente novamente.";
                // Auto-show credentials inputs on auth failure
                setShowCredentials(true);
            }

            setError(errorMessage);
            setIsLoading(false);
        }
    };

    return createPortal(
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl w-full max-w-md p-6 animate-in fade-in zoom-in duration-200" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-start gap-4">
                    <div className="p-3 bg-amber-500/10 rounded-full shrink-0">
                        <ShieldAlert className="w-8 h-8 text-amber-500" />
                    </div>
                    <div className="flex-1 w-full">
                        <h3 className="text-lg font-semibold text-white mb-2">
                            Configuração de Segurança Necessária
                        </h3>

                        <div className="text-left space-y-3 mb-4">
                            <p className="text-zinc-300 text-sm">
                                O Windows bloqueia conexões WinRM para IPs desconhecidos por segurança.
                            </p>
                            <p className="text-zinc-300 text-sm">
                                Para prosseguir, precisamos adicionar este IP aos <strong>TrustedHosts</strong> temporariamente.
                            </p>
                            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-xs text-blue-200">
                                <p>
                                    Esta configuração será aplicada <strong>apenas durante esta operação</strong> e removida automaticamente em seguida.
                                </p>
                            </div>
                        </div>

                        {/* Credential Override Section */}
                        <div className="mb-4">
                            <button
                                onClick={() => setShowCredentials(!showCredentials)}
                                className="flex items-center gap-2 text-xs text-zinc-400 hover:text-white transition-colors w-full"
                            >
                                {showCredentials ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                Usar credenciais diferentes (Administrador Local)
                            </button>

                            {showCredentials && (
                                <div className="mt-3 space-y-3 p-3 bg-zinc-950/50 rounded-lg border border-zinc-800 animate-in slide-in-from-top-2">
                                    <div className="space-y-1">
                                        <label className="text-xs text-zinc-500">Usuário (ex: .\Administrador)</label>
                                        <div className="relative">
                                            <User className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" size={14} />
                                            <input
                                                type="text"
                                                value={username}
                                                onChange={(e) => setUsername(e.target.value)}
                                                className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 pl-8 text-sm text-white focus:outline-none focus:border-blue-500 placeholder:text-zinc-600"
                                                placeholder="Usuário"
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs text-zinc-500">Senha</label>
                                        <div className="relative">
                                            <Key className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" size={14} />
                                            <input
                                                type="password"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 pl-8 text-sm text-white focus:outline-none focus:border-blue-500 placeholder:text-zinc-600"
                                                placeholder="Senha"
                                            />
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {error && (
                            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-sm">
                                {error}
                            </div>
                        )}

                        <div className="flex gap-3 w-full">
                            <button
                                onClick={onClose}
                                className="flex-1 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors text-sm"
                                disabled={isLoading}
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleConfirm}
                                disabled={isLoading}
                                className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors flex items-center justify-center gap-2 text-sm"
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Configurando...
                                    </>
                                ) : (
                                    <>
                                        <Check className="w-4 h-4" />
                                        Permitir Temporariamente
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
};

export default TrustedHostsModal;
