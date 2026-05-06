import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import {
    ShieldAlert,
    Check,
    Loader2,
    User,
    Key,
    ChevronDown,
    ChevronRight,
    Network,
    Info,
} from 'lucide-react';
import { API_BASE } from '../config/api';
import { useTrustedHostsSession } from '../contexts/TrustedHostsSessionContext';

interface TrustedHostsModalProps {
    isOpen: boolean;
    onClose: () => void;
    /**
     * Called when the operator confirms. The optional credentials override
     * the ones already in scope (used to retry with a Local Administrator
     * when domain creds keep failing).
     */
    onConfirm: (username?: string, password?: string) => Promise<void>;
    /**
     * IP being trusted. Used both to render the diagnostic and to record
     * the per-session approval when the operator opts in.
     */
    targetIp?: string;
}

interface DiagnoseResponse {
    target_ip: string;
    target_domain: string | null;
    local_domain: string | null;
    network_name: string | null;
    cross_domain: boolean | null;
}

const TrustedHostsModal: React.FC<TrustedHostsModalProps> = ({ isOpen, onClose, onConfirm, targetIp }) => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showCredentials, setShowCredentials] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [rememberForSession, setRememberForSession] = useState(false);
    const [diagnose, setDiagnose] = useState<DiagnoseResponse | null>(null);

    const { approve } = useTrustedHostsSession();

    // Pull diagnostic info as soon as the modal opens so the operator sees
    // *why* TrustedHosts is being asked rather than just "Windows blocks".
    useEffect(() => {
        if (!isOpen || !targetIp) {
            setDiagnose(null);
            return;
        }
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API_BASE}/system/diagnose-target`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target_ip: targetIp }),
                });
                if (!res.ok) return;
                const data: DiagnoseResponse = await res.json();
                if (!cancelled) setDiagnose(data);
            } catch {
                /* diagnostic is best-effort; modal works without it */
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [isOpen, targetIp]);

    // Reset transient state every time the modal closes/reopens.
    useEffect(() => {
        if (!isOpen) {
            setError(null);
            setIsLoading(false);
            setShowCredentials(false);
            setUsername('');
            setPassword('');
            setRememberForSession(false);
        }
    }, [isOpen]);

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
            // Only record the session approval after the call succeeds — we
            // don't want to "remember" an approval for a host that ended up
            // failing for an unrelated reason.
            if (rememberForSession && targetIp) {
                approve(targetIp);
            }
            // Modal is closed by the parent on success.
        } catch (err: any) {
            let errorMessage = err.message || 'Falha ao configurar TrustedHosts.';

            if (errorMessage.includes('Failed to authenticate') || errorMessage.includes('Falha em todos os métodos')) {
                errorMessage =
                    'Falha na autenticação. Pode ser uma credencial incorreta ou um usuário de domínio diferente sem permissão administrativa. Por favor, verifique e tente novamente.';
                setShowCredentials(true);
            }

            setError(errorMessage);
            setIsLoading(false);
        }
    };

    // Build the contextual diagnostic block. It tries to be specific when
    // it can (cross-domain detected, target's domain known) and gracefully
    // degrades otherwise.
    const renderDiagnostic = () => {
        if (!diagnose) return null;

        const { target_domain, local_domain, network_name, cross_domain } = diagnose;

        // Cross-domain confirmed: highest-value diagnostic.
        if (cross_domain && target_domain && local_domain) {
            return (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-100 space-y-2">
                    <div className="flex items-start gap-2">
                        <Network className="w-4 h-4 mt-0.5 shrink-0" />
                        <div className="space-y-1">
                            <p>
                                <strong>Domínios diferentes detectados.</strong> Sua máquina está em
                                {' '}<code className="text-amber-200">{local_domain.toLowerCase()}</code> e o alvo em
                                {' '}<code className="text-amber-200">{target_domain.toLowerCase()}</code>.
                            </p>
                            <p className="text-amber-200/80">
                                Sem relação de confiança entre os domínios, o Windows recusa Kerberos e cai em NTLM —
                                que exige TrustedHosts.
                            </p>
                            <p className="text-amber-200/80">
                                Para evitar essa solicitação no futuro, use o usuário no formato{' '}
                                <code className="text-amber-200">usuario@{target_domain.toLowerCase()}</code>.
                            </p>
                        </div>
                    </div>
                </div>
            );
        }

        // We know the target domain even without cross-domain confirmation.
        if (target_domain) {
            return (
                <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-3 text-xs text-blue-100 space-y-1">
                    <div className="flex items-start gap-2">
                        <Info className="w-4 h-4 mt-0.5 shrink-0" />
                        <div>
                            <p>
                                Alvo está na rede{network_name ? ` "${network_name}"` : ''} (domínio
                                {' '}<code className="text-blue-200">{target_domain.toLowerCase()}</code>).
                            </p>
                            <p className="text-blue-200/80">
                                Se a credencial pertencer a esse domínio, prefira o formato{' '}
                                <code className="text-blue-200">usuario@{target_domain.toLowerCase()}</code> para usar Kerberos
                                e evitar TrustedHosts.
                            </p>
                        </div>
                    </div>
                </div>
            );
        }

        // No domain info available — suggest configuring it.
        return (
            <div className="rounded-lg border border-zinc-700/40 bg-zinc-800/50 p-3 text-xs text-zinc-300">
                <div className="flex items-start gap-2">
                    <Info className="w-4 h-4 mt-0.5 shrink-0" />
                    <p>
                        Cadastre a rede deste IP em <strong>Configurações → Redes / VLANs</strong> com o domínio AD
                        correspondente para ativar tentativas automáticas com Kerberos e reduzir essa solicitação.
                    </p>
                </div>
            </div>
        );
    };

    return createPortal(
        <div
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={onClose}
        >
            <div
                className="bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl w-full max-w-md p-6 animate-in fade-in zoom-in duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-start gap-4">
                    <div className="p-3 bg-amber-500/10 rounded-full shrink-0">
                        <ShieldAlert className="w-8 h-8 text-amber-500" />
                    </div>
                    <div className="flex-1 w-full">
                        <h3 className="text-lg font-semibold text-white mb-2">Configuração de Segurança Necessária</h3>

                        <div className="text-left space-y-3 mb-4">
                            <p className="text-zinc-300 text-sm">
                                O Windows bloqueia conexões WinRM para IPs desconhecidos por segurança.
                            </p>
                            <p className="text-zinc-300 text-sm">
                                Para prosseguir, precisamos adicionar
                                {targetIp ? <> <code className="text-zinc-100">{targetIp}</code></> : ' este IP'} aos{' '}
                                <strong>TrustedHosts</strong> temporariamente.
                            </p>
                            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-xs text-blue-200">
                                <p>
                                    Esta configuração será aplicada <strong>apenas durante esta operação</strong> e removida
                                    automaticamente em seguida.
                                </p>
                            </div>
                            {renderDiagnostic()}
                        </div>

                        {/* Remember-this-session toggle */}
                        {targetIp && (
                            <label className="flex items-start gap-2 cursor-pointer mb-4 select-none">
                                <input
                                    type="checkbox"
                                    checked={rememberForSession}
                                    onChange={(e) => setRememberForSession(e.target.checked)}
                                    className="mt-0.5 w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-1 focus:ring-blue-500 focus:ring-offset-0"
                                />
                                <span className="text-xs text-zinc-300">
                                    Não perguntar de novo para este IP nesta sessão
                                    <span className="block text-zinc-500">
                                        Reset automático ao fechar o aplicativo. TrustedHosts continua sendo adicionado e
                                        removido a cada operação.
                                    </span>
                                </span>
                            </label>
                        )}

                        {/* Credential override */}
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
                                            <User
                                                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600"
                                                size={14}
                                            />
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
                                            <Key
                                                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600"
                                                size={14}
                                            />
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
        document.body,
    );
};

export default TrustedHostsModal;
