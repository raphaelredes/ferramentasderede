import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Lock, User, Key, Loader2, AlertCircle, Shield, Unlock, ChevronDown, Save, Plus, HelpCircle, RefreshCw } from 'lucide-react';
import { useVault } from '../contexts/VaultContext';
import { ConfirmationModal } from './ConfirmationModal';
import { API_BASE } from '../config/api';

interface CredentialModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (username: string, password: string) => void;
    title: string;
    message?: string;
    isLoading?: boolean;
    error?: string | null;
    initialDomain?: string;
}

export function CredentialModal({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    initialDomain = '',
    isLoading = false,
    error = null
}: CredentialModalProps) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [domain, setDomain] = useState(initialDomain);
    const [saveToVault, setSaveToVault] = useState(false);

    // Vault Context
    const {
        hasVault,
        isUnlocked,
        vaultCredentials,
        unlock,
        refreshCredentials
    } = useVault();

    const [masterPassword, setMasterPassword] = useState('');
    const [passwordHint, setPasswordHint] = useState('');
    const [isUnlocking, setIsUnlocking] = useState(false);
    const [vaultError, setVaultError] = useState('');
    const [showVault, setShowVault] = useState(false);

    // Recovery State
    const [showHint, setShowHint] = useState(false);
    const [retrievedHint, setRetrievedHint] = useState('');
    const [isResetting, setIsResetting] = useState(false);
    const [isResetModalOpen, setIsResetModalOpen] = useState(false);

    // Atualiza o domínio se a prop mudar
    useEffect(() => {
        setDomain(initialDomain);
    }, [initialDomain]);

    // Limpa estados quando o modal fecha ou abre
    useEffect(() => {
        if (isOpen) {
            setPassword('');
            // Auto-expand if unlocked to show credentials immediately
            setShowVault(isUnlocked);
            setMasterPassword('');
            setPasswordHint('');
            setVaultError('');
            setSaveToVault(false);
            setShowHint(false);
            setRetrievedHint('');
            setIsResetting(false);
            setIsResetModalOpen(false);
        }
    }, [isOpen, isUnlocked]);

    const handleUnlockVault = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsUnlocking(true);
        setVaultError('');

        // Pass hint only when creating a new vault (not when unlocking)
        // But here we are unlocking or creating. 
        // If !hasVault, we are creating.

        const success = await unlock(masterPassword, !hasVault ? passwordHint : undefined);
        if (success) {
            setMasterPassword('');
            setPasswordHint('');
        } else {
            setVaultError('Senha incorreta.');
        }
        setIsUnlocking(false);
    };

    const handleSelectCredential = async (credId: string) => {
        if (!credId) return;
        try {
            const res = await fetch(`${API_BASE}/security/credentials/decrypt`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: credId })
            });

            if (res.ok) {
                const data = await res.json();
                const cred = vaultCredentials.find(c => c.id === credId);
                if (cred) {
                    // Parse username to separate domain if present
                    if (cred.username.includes('\\')) {
                        const [dom, user] = cred.username.split('\\');
                        setDomain(dom);
                        setUsername(user);
                    } else if (cred.username.includes('@')) {
                        setDomain('');
                        setUsername(cred.username);
                    } else {
                        setUsername(cred.username);
                    }
                    setPassword(data.password);
                }
            }
        } catch (error) {
            console.error("Erro ao obter senha da credencial:", error);
        }
    };

    const saveCredentialToVault = async (finalUsername: string) => {
        try {
            await fetch(`${API_BASE}/security/credentials`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: finalUsername,
                    username: finalUsername,
                    password: password,
                    description: `Salvo automaticamente via Autenticação em ${new Date().toLocaleString()}`
                })
            });
            refreshCredentials();
        } catch (error) {
            console.error("Erro ao salvar no cofre:", error);
        }
    };

    const handleForgotPassword = async () => {
        try {
            const res = await fetch(`${API_BASE}/security/hint`);
            if (res.ok) {
                const data = await res.json();
                setRetrievedHint(data.hint || 'Nenhuma dica cadastrada.');
                setShowHint(true);
            }
        } catch (e) {
            setRetrievedHint('Erro ao buscar dica.');
            setShowHint(true);
        }
    };

    const confirmResetVault = async () => {
        setIsResetting(true);
        try {
            const res = await fetch(`${API_BASE}/security/reset`, { method: 'POST' });
            if (res.ok) {
                alert('Cofre resetado com sucesso. Você pode criar uma nova senha agora.');
                window.location.reload(); // Reload to refresh vault state completely
            } else {
                alert('Erro ao resetar cofre.');
            }
        } catch (e) {
            alert('Erro de conexão.');
        }
        setIsResetting(false);
        setIsResetModalOpen(false);
    };

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (isLoading) return;

        const userToUse = username || "Administrador";
        const finalUsername = domain ? `${domain}\\${userToUse}` : userToUse;

        if (saveToVault && isUnlocked) {
            await saveCredentialToVault(finalUsername);
        }

        onConfirm(finalUsername, password);
    };

    return createPortal(
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] backdrop-blur-sm" onClick={onClose}>
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl animate-in fade-in zoom-in duration-200 flex flex-col max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-6 shrink-0">
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                        <Lock className="text-blue-500" size={20} />
                        {title}
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-zinc-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={isLoading}
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="overflow-y-auto custom-scrollbar pr-2 -mr-2">
                    {message && (
                        <p className="text-zinc-400 mb-6 text-sm">{message}</p>
                    )}

                    {error && (
                        <div className="mb-6 bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-start gap-3">
                            <AlertCircle className="text-red-500 shrink-0 mt-0.5" size={16} />
                            <p className="text-sm text-red-400">{error}</p>
                        </div>
                    )}

                    {/* Vault Section */}
                    <div className="mb-6 bg-zinc-950/50 border border-zinc-800 rounded-lg p-4">
                        <button
                            onClick={() => setShowVault(!showVault)}
                            className="flex items-center justify-between w-full text-left mb-2"
                        >
                            <div className="flex items-center gap-2 text-sm font-medium text-blue-400">
                                <Shield size={16} />
                                {hasVault ? 'Cofre de Senhas' : 'Criar Cofre de Senhas'}
                            </div>
                            <ChevronDown size={16} className={`text-zinc-500 transition-transform ${showVault ? 'rotate-180' : ''}`} />
                        </button>

                        {showVault && (
                            <div className="mt-3 pt-3 border-t border-zinc-800 space-y-3">
                                {!isUnlocked ? (
                                    <div className="space-y-3">
                                        <p className="text-xs text-zinc-500">
                                            {hasVault
                                                ? "Desbloqueie para usar uma credencial salva."
                                                : "Crie uma senha mestra para proteger suas credenciais."}
                                        </p>
                                        <div className="flex flex-col gap-2">
                                            <div className="flex gap-2">
                                                <input
                                                    type="password"
                                                    value={masterPassword}
                                                    onChange={(e) => setMasterPassword(e.target.value)}
                                                    placeholder={hasVault ? "Senha Mestra" : "Crie uma Senha Mestra"}
                                                    className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
                                                    onKeyDown={(e) => e.key === 'Enter' && handleUnlockVault(e)}
                                                />
                                                <button
                                                    onClick={handleUnlockVault}
                                                    disabled={isUnlocking}
                                                    className="bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50"
                                                >
                                                    {isUnlocking ? <Loader2 className="animate-spin" size={16} /> : (hasVault ? <Unlock size={16} /> : <Plus size={16} />)}
                                                </button>
                                            </div>

                                            {!hasVault && (
                                                <input
                                                    type="text"
                                                    value={passwordHint}
                                                    onChange={(e) => setPasswordHint(e.target.value)}
                                                    placeholder="Dica de senha (Opcional)"
                                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
                                                />
                                            )}
                                        </div>

                                        {hasVault && (
                                            <div className="flex justify-between items-center">
                                                <button
                                                    type="button"
                                                    onClick={handleForgotPassword}
                                                    className="text-xs text-zinc-500 hover:text-blue-400 transition-colors flex items-center gap-1"
                                                >
                                                    <HelpCircle size={12} /> Esqueci a senha
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setIsResetModalOpen(true)}
                                                    disabled={isResetting}
                                                    className="text-xs text-red-500/70 hover:text-red-400 transition-colors flex items-center gap-1"
                                                >
                                                    <RefreshCw size={12} className={isResetting ? "animate-spin" : ""} /> Resetar Cofre
                                                </button>
                                            </div>
                                        )}

                                        {showHint && (
                                            <div className="bg-blue-500/10 border border-blue-500/20 rounded p-2 text-xs text-blue-300">
                                                <strong>Dica:</strong> {retrievedHint}
                                            </div>
                                        )}

                                        {vaultError && <p className="text-xs text-red-400">{vaultError}</p>}
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium text-zinc-400">Selecionar Credencial</label>
                                        <select
                                            onChange={(e) => handleSelectCredential(e.target.value)}
                                            className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                            defaultValue=""
                                        >
                                            <option value="" disabled>Escolha uma credencial...</option>
                                            {vaultCredentials.map(cred => (
                                                <option key={cred.id} value={cred.id}>
                                                    {cred.name} ({cred.username})
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300">Domínio (Opcional)</label>
                            <div className="relative">
                                {/* 
                                    PROTECTED: UI RULE ENFORCEMENT
                                    1. Pre-filled/System values (like Domain) MUST be gray (text-zinc-500).
                                    2. User-typed values MUST be white (text-white).
                                    3. DO NOT CHANGE THIS COLOR SCHEME WITHOUT EXPLICIT USER APPROVAL.
                                */}
                                <input
                                    type="text"
                                    value={domain}
                                    onChange={(e) => setDomain(e.target.value)}
                                    onFocus={(e) => e.target.select()}
                                    className={`w-full bg-zinc-950 border border-zinc-800 rounded-lg py-2 px-4 focus:outline-none focus:border-blue-500 transition-colors placeholder:text-zinc-500 ${domain === initialDomain ? 'text-zinc-500' : 'text-white'} disabled:opacity-50 disabled:cursor-not-allowed`}
                                    placeholder="ex: EMPRESA"
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300">Usuário</label>
                            <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className={`w-full bg-zinc-950 border border-zinc-800 rounded-lg py-2 pl-10 pr-4 focus:outline-none focus:border-blue-500 transition-colors placeholder-zinc-500 placeholder:text-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed ${!username || username === 'Administrador' ? 'text-zinc-500' : 'text-white'}`}
                                    placeholder="Administrador"
                                    autoFocus={!isUnlocked}
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300">Senha</label>
                            <div className="relative">
                                <Key className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg py-2 pl-10 pr-4 text-white placeholder-zinc-500 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    placeholder=""
                                    required
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        {/* Save to Vault Checkbox */}
                        {isUnlocked && (
                            <div className="flex items-center gap-2 pt-2">
                                <input
                                    type="checkbox"
                                    id="saveToVault"
                                    checked={saveToVault}
                                    onChange={(e) => setSaveToVault(e.target.checked)}
                                    className="rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500"
                                />
                                <label htmlFor="saveToVault" className="text-sm text-zinc-400 select-none cursor-pointer flex items-center gap-1.5">
                                    <Save size={14} />
                                    Salvar credencial no cofre
                                </label>
                            </div>
                        )}

                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                type="button"
                                onClick={onClose}
                                className="px-4 py-2 text-zinc-400 hover:text-white transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={isLoading}
                            >
                                Cancelar
                            </button>
                            <button
                                type="submit"
                                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 rounded-lg transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                disabled={isLoading}
                            >
                                {isLoading && <Loader2 className="animate-spin" size={16} />}
                                {isLoading ? 'Confirmando...' : 'Confirmar'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <ConfirmationModal
                isOpen={isResetModalOpen}
                onClose={() => setIsResetModalOpen(false)}
                onConfirm={confirmResetVault}
                title="Resetar Cofre de Senhas"
                message="ATENÇÃO: Esta ação apagará PERMANENTEMENTE todas as credenciais salvas no cofre. Você perderá o acesso a elas para sempre. Deseja realmente continuar?"
                confirmText="Sim, Resetar Tudo"
                type="danger"
                isLoading={isResetting}
            />
        </div>,
        document.body
    );
}
