import { useState } from 'react';
import { Lock, Unlock, Eye, EyeOff, Trash2, Plus, Copy, Check, Shield, Key, Settings, Clock, Pencil } from 'lucide-react';
import { useVault } from '../contexts/VaultContext';
import { useToast } from '../contexts/ToastContext';
import { ConfirmationModal } from '../components/ConfirmationModal';

export function Security() {
    const {
        hasVault,
        isUnlocked,
        vaultCredentials,
        isLoading,
        unlock,
        lock,
        refreshCredentials,
        autoLockTimeout,
        setAutoLockTimeout
    } = useVault();

    const { showToast } = useToast();

    // Modals
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [isResetModalOpen, setIsResetModalOpen] = useState(false);
    const [credentialToDelete, setCredentialToDelete] = useState<string | null>(null);
    const [editingCredential, setEditingCredential] = useState<string | null>(null);

    // Form State
    const [masterPassword, setMasterPassword] = useState('');
    const [newName, setNewName] = useState('');
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [error, setError] = useState('');

    // Reveal State
    const [revealedId, setRevealedId] = useState<string | null>(null);
    const [revealedPassword, setRevealedPassword] = useState<string>('');
    const [copiedId, setCopiedId] = useState<string | null>(null);

    // Recovery State
    const [passwordHint, setPasswordHint] = useState('');
    const [showHint, setShowHint] = useState(false);
    const [retrievedHint, setRetrievedHint] = useState('');
    const [isResetting, setIsResetting] = useState(false);

    const handleUnlock = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        // Pass hint only when creating a new vault
        const success = await unlock(masterPassword, !hasVault ? passwordHint : undefined);
        if (success) {
            setMasterPassword('');
            setPasswordHint('');
        } else {
            setError('Senha incorreta.');
        }
    };

    const handleForgotPassword = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8000/security/hint');
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
            const res = await fetch('http://127.0.0.1:8000/security/reset', { method: 'POST' });
            if (res.ok) {
                showToast('Cofre resetado com sucesso.', 'success');
                window.location.reload(); // Reload to refresh vault state completely
            } else {
                showToast('Erro ao resetar cofre.', 'error');
            }
        } catch (e) {
            showToast('Erro de conexão.', 'error');
        }
        setIsResetting(false);
        setIsResetModalOpen(false);
    };

    const handleAddCredential = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const payload: any = {
                name: newName,
                username: newUsername,
                password: newPassword,
                description: newDescription
            };

            if (editingCredential) {
                payload.id = editingCredential;
            }

            const res = await fetch('http://127.0.0.1:8000/security/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                setIsAddModalOpen(false);
                setNewName('');
                setNewUsername('');
                setNewPassword('');
                setNewDescription('');
                setEditingCredential(null);
                refreshCredentials();
                showToast(editingCredential ? 'Credencial atualizada!' : 'Credencial adicionada!', 'success');
            }
        } catch (error) {
            console.error("Erro ao adicionar/editar credencial:", error);
            showToast('Erro ao salvar credencial.', 'error');
        }
    };

    const handleEditClick = async (cred: any) => {
        setEditingCredential(cred.id);
        setNewName(cred.name);
        setNewUsername(cred.username);
        setNewDescription(cred.description || '');

        // Fetch password
        try {
            const res = await fetch('http://127.0.0.1:8000/security/credentials/decrypt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: cred.id })
            });

            if (res.ok) {
                const data = await res.json();
                setNewPassword(data.password);
                setIsAddModalOpen(true);
            }
        } catch (error) {
            console.error("Erro ao buscar senha para edição:", error);
            showToast('Erro ao carregar dados da credencial.', 'error');
        }
    };

    const openAddModal = () => {
        setEditingCredential(null);
        setNewName('');
        setNewUsername('');
        setNewPassword('');
        setNewDescription('');
        setIsAddModalOpen(true);
    };

    const handleDeleteClick = (id: string) => {
        setCredentialToDelete(id);
    };

    const confirmDeleteCredential = async () => {
        if (!credentialToDelete) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/security/credentials/${credentialToDelete}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                refreshCredentials();
                showToast('Credencial removida.', 'success');
            }
        } catch (error) {
            console.error("Erro ao remover credencial:", error);
            showToast('Erro ao remover credencial.', 'error');
        }
        setCredentialToDelete(null);
    };

    const handleReveal = async (id: string) => {
        if (revealedId === id) {
            setRevealedId(null);
            setRevealedPassword('');
            return;
        }

        try {
            const res = await fetch('http://127.0.0.1:8000/security/credentials/decrypt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id })
            });

            if (res.ok) {
                const data = await res.json();
                setRevealedPassword(data.password);
                setRevealedId(id);
            }
        } catch (error) {
            console.error("Erro ao decriptar:", error);
        }
    };

    const handleCopy = (text: string, id: string) => {
        navigator.clipboard.writeText(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
        showToast('Senha copiada!', 'success');
    };

    if (isLoading && !isUnlocked) {
        return (
            <div className="flex justify-center items-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
        );
    }

    if (!isUnlocked) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-6">
                <div className="bg-zinc-800/50 p-6 rounded-full">
                    <Lock size={64} className="text-blue-500" />
                </div>
                <div className="space-y-2">
                    <h2 className="text-3xl font-bold text-white">Cofre Bloqueado</h2>
                    <p className="text-zinc-400 max-w-md mx-auto">
                        {hasVault
                            ? "Suas credenciais estão protegidas. Digite sua senha mestra para acessar."
                            : "Configure uma senha mestra para criar seu cofre seguro."}
                    </p>
                </div>

                <form onSubmit={handleUnlock} className="w-full max-w-sm space-y-4">
                    <div className="relative">
                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={20} />
                        <input
                            type="password"
                            value={masterPassword}
                            onChange={(e) => setMasterPassword(e.target.value)}
                            placeholder={hasVault ? "Senha Mestra" : "Crie uma Senha Mestra"}
                            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-10 pr-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                            autoFocus
                        />
                    </div>

                    {!hasVault && (
                        <div className="relative">
                            <input
                                type="text"
                                value={passwordHint}
                                onChange={(e) => setPasswordHint(e.target.value)}
                                placeholder="Dica de senha (Opcional)"
                                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                            />
                        </div>
                    )}

                    {error && <p className="text-red-500 text-sm">{error}</p>}

                    <button
                        type="submit"
                        className="w-full bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                        {hasVault ? <Unlock size={20} /> : <Shield size={20} />}
                        {hasVault ? "Desbloquear Cofre" : "Criar Cofre"}
                    </button>

                    {hasVault && (
                        <div className="flex justify-between items-center pt-2">
                            <button
                                type="button"
                                onClick={handleForgotPassword}
                                className="text-sm text-zinc-500 hover:text-blue-400 transition-colors flex items-center gap-1"
                            >
                                <Eye size={14} /> Esqueci a senha
                            </button>
                            <button
                                type="button"
                                onClick={() => setIsResetModalOpen(true)}
                                className="text-sm text-red-500/70 hover:text-red-400 transition-colors flex items-center gap-1"
                            >
                                <Trash2 size={14} /> Resetar Cofre
                            </button>
                        </div>
                    )}

                    {showHint && (
                        <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-sm text-blue-300 mt-4">
                            <strong>Dica:</strong> {retrievedHint}
                        </div>
                    )}
                </form>

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
            </div>
        );
    }

    return (
        <div className="space-y-6 h-full flex flex-col p-8">
            <header className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Shield className="text-blue-500" />
                        Cofre de Senhas
                    </h2>
                    <p className="text-zinc-400">Gerenciamento seguro de credenciais locais.</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                        className={`p-2 rounded-lg transition-colors border ${isSettingsOpen ? 'bg-zinc-800 text-blue-400 border-blue-900/50' : 'bg-zinc-900 hover:bg-zinc-800 text-zinc-400 border-zinc-800'}`}
                        title="Configurações do Cofre"
                    >
                        <Settings size={18} />
                    </button>
                    <button
                        onClick={lock}
                        className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/50 px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        <Lock size={18} />
                        Bloquear
                    </button>
                    <button
                        onClick={openAddModal}
                        className="bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        <Plus size={18} />
                        Nova Credencial
                    </button>
                </div>
            </header>

            {/* Settings Panel */}
            {isSettingsOpen && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 mb-4 animate-in slide-in-from-top-2">
                    <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                        <Settings size={20} className="text-blue-500" />
                        Configurações
                    </h3>

                    <div className="flex items-center justify-between p-3 bg-zinc-950 rounded-lg border border-zinc-800">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-zinc-900 rounded-lg text-zinc-400">
                                <Clock size={20} />
                            </div>
                            <div>
                                <p className="text-white font-medium">Bloqueio Automático</p>
                                <p className="text-sm text-zinc-500">Bloquear após inatividade</p>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            {[1, 5, 15, 30, 0].map((time) => (
                                <button
                                    key={time}
                                    onClick={() => setAutoLockTimeout(time)}
                                    className={`px-3 py-1.5 rounded text-sm font-medium transition-colors border ${autoLockTimeout === time
                                        ? 'bg-zinc-800 text-blue-400 border-blue-900/50'
                                        : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:bg-zinc-800 hover:text-zinc-200'
                                        }`}
                                >
                                    {time === 0 ? 'Nunca' : `${time} min`}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            <div className="flex-1 overflow-auto">
                {vaultCredentials.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 text-zinc-600 border border-dashed border-zinc-800 rounded-xl">
                        <Lock size={48} className="mb-4 opacity-20" />
                        <p>Nenhuma credencial salva.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {vaultCredentials.map((cred) => (
                            <div key={cred.id} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-zinc-700 transition-colors group">
                                <div className="flex justify-between items-start mb-3">
                                    <div className="p-2 bg-zinc-800 rounded-lg">
                                        <Lock className="text-zinc-400" size={20} />
                                    </div>
                                    <div className="flex gap-1">
                                        <button
                                            onClick={() => handleEditClick(cred)}
                                            className="text-zinc-600 hover:text-blue-400 transition-colors p-1"
                                            title="Editar"
                                        >
                                            <Pencil size={16} />
                                        </button>
                                        <button
                                            onClick={() => handleDeleteClick(cred.id)}
                                            className="text-zinc-600 hover:text-red-500 transition-colors p-1"
                                            title="Remover"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>

                                <h3 className="font-semibold text-white mb-1">{cred.name}</h3>
                                <p className="text-sm text-zinc-400 mb-4">{cred.username}</p>

                                {cred.description && (
                                    <p className="text-xs text-zinc-500 mb-4 line-clamp-2">{cred.description}</p>
                                )}

                                <div className="flex items-center gap-2 mt-auto pt-4 border-t border-zinc-800">
                                    <div className="flex-1 bg-zinc-950 rounded px-3 py-1.5 text-sm font-mono text-zinc-300 truncate h-8 flex items-center">
                                        {revealedId === cred.id ? revealedPassword : '••••••••••••'}
                                    </div>

                                    <button
                                        onClick={() => handleReveal(cred.id)}
                                        className="p-1.5 text-zinc-400 hover:text-white transition-colors"
                                        title={revealedId === cred.id ? "Ocultar" : "Mostrar"}
                                    >
                                        {revealedId === cred.id ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>

                                    {revealedId === cred.id && (
                                        <button
                                            onClick={() => handleCopy(revealedPassword, cred.id)}
                                            className="p-1.5 text-zinc-400 hover:text-green-400 transition-colors"
                                            title="Copiar"
                                        >
                                            {copiedId === cred.id ? <Check size={16} /> : <Copy size={16} />}
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Add Modal */}
            {isAddModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl">
                        <h3 className="text-xl font-bold text-white mb-4">{editingCredential ? 'Editar Credencial' : 'Adicionar Credencial'}</h3>
                        <form onSubmit={handleAddCredential} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Nome (Identificador)</label>
                                <input
                                    type="text"
                                    required
                                    value={newName}
                                    onChange={e => setNewName(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                                    placeholder="ex: Servidor AD Principal"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Usuário</label>
                                <input
                                    type="text"
                                    required
                                    value={newUsername}
                                    onChange={e => setNewUsername(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                                    placeholder="ex: admin@dominio.local"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Senha</label>
                                <input
                                    type="password"
                                    required
                                    value={newPassword}
                                    onChange={e => setNewPassword(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Descrição (Opcional)</label>
                                <textarea
                                    value={newDescription}
                                    onChange={e => setNewDescription(e.target.value)}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 h-20 resize-none"
                                />
                            </div>

                            <div className="flex justify-end gap-2 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setIsAddModalOpen(false)}
                                    className="px-4 py-2 text-zinc-400 hover:text-white transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    type="submit"
                                    className="bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 px-4 py-2 rounded-lg font-medium transition-colors"
                                >
                                    Salvar
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            <ConfirmationModal
                isOpen={!!credentialToDelete}
                onClose={() => setCredentialToDelete(null)}
                onConfirm={confirmDeleteCredential}
                title="Remover Credencial"
                message="Tem certeza que deseja remover esta credencial? Esta ação não pode ser desfeita."
                confirmText="Remover"
                type="danger"
            />
        </div>
    );
}
