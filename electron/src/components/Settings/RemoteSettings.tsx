
import React, { useState, useEffect } from 'react';
import { Trash2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useToast } from '../../contexts/ToastContext';
import { HelpButton } from '../HelpButton';
import { API_BASE } from '../../config/api';

// Interfaces (duplicated for self-containment, or could be shared)
interface RemoteSettingsData {
    auto_add_trusted_hosts: boolean;
    default_credential_id?: string;
    auto_login: boolean;
}

interface Credential {
    id: string;
    name: string;
    username: string;
    description?: string;
}

interface RemoteSettingsProps {
    settings: RemoteSettingsData;
    onUpdateSettings: (newSettings: RemoteSettingsData) => void;
    isChanged: (key: string, val: any) => boolean;
    setConfirmationModal: React.Dispatch<React.SetStateAction<any>>;
    setCreateVaultModal: React.Dispatch<React.SetStateAction<any>>;
}

export function RemoteSettings({ settings, onUpdateSettings, isChanged, setConfirmationModal, setCreateVaultModal }: RemoteSettingsProps) {
    const { showToast } = useToast();

    // Trusted Hosts State
    const [trustedHosts, setTrustedHosts] = useState<string[]>([]);
    const [newTrustedHost, setNewTrustedHost] = useState('');
    const [trustedHostStatus, setTrustedHostStatus] = useState('');

    // Vault & Credentials State
    const [vaultStatus, setVaultStatus] = useState({ is_unlocked: false, has_vault: false });
    const [vaultPassword, setVaultPassword] = useState('');
    const [credentials, setCredentials] = useState<Credential[]>([]);
    const [newCred, setNewCred] = useState({ name: '', username: '', password: '', description: '' });
    const [isAddingCred, setIsAddingCred] = useState(false);

    useEffect(() => {
        fetchTrustedHosts();
        fetchVaultStatus();
    }, []);

    useEffect(() => {
        if (vaultStatus.is_unlocked) {
            fetchCredentials();
        }
    }, [vaultStatus.is_unlocked]);

    // --- Trusted Hosts Logic ---

    const fetchTrustedHosts = () => {
        fetch(`${API_BASE}/settings/trusted-hosts`)
            .then(res => res.json())
            .then(data => setTrustedHosts(data))
            .catch(err => console.error("Failed to fetch trusted hosts", err));
    };

    const handleAddTrustedHost = async (hostToAdd?: string) => {
        const host = hostToAdd || newTrustedHost;
        if (!host) return;

        setTrustedHostStatus('Adicionando...');
        try {
            const res = await fetch(`${API_BASE}/settings/trusted-hosts?host=${encodeURIComponent(host)}`, {
                method: 'POST'
            });
            if (res.ok) {
                if (!hostToAdd) setNewTrustedHost('');
                fetchTrustedHosts();
                setTrustedHostStatus('Host adicionado.');
                setTimeout(() => setTrustedHostStatus(''), 2000);
            } else {
                setTrustedHostStatus('Erro ao adicionar.');
            }
        } catch (e) {
            setTrustedHostStatus('Erro de conexão.');
        }
    };

    const handleRemoveTrustedHost = (host: string) => {
        setConfirmationModal({
            isOpen: true,
            title: 'Remover Host Confiável',
            message: `Tem certeza que deseja remover "${host}" dos Hosts Confiáveis?`,
            confirmText: 'Remover',
            type: 'danger',
            onConfirm: async () => {
                try {
                    const res = await fetch(`${API_BASE}/settings/trusted-hosts?host=${encodeURIComponent(host)}`, { method: 'DELETE' });
                    if (res.ok) {
                        fetchTrustedHosts();
                        showToast('Host removido.', 'success');
                    } else {
                        showToast('Erro ao remover host.', 'error');
                    }
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao remover host.', 'error');
                }
                setConfirmationModal((prev: any) => ({ ...prev, isOpen: false }));
            }
        });
    };

    const handleClearTrustedHosts = () => {
        setConfirmationModal({
            isOpen: true,
            title: 'Limpar Hosts Confiáveis',
            message: 'Tem certeza que deseja limpar todos os Hosts Confiáveis? Isso pode afetar o acesso remoto.',
            confirmText: 'Limpar',
            type: 'warning',
            onConfirm: async () => {
                try {
                    const res = await fetch(`${API_BASE}/settings/trusted-hosts`, { method: 'DELETE' });
                    if (res.ok) {
                        fetchTrustedHosts();
                        showToast('Hosts confiáveis limpos.', 'success');
                    }
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao limpar hosts.', 'error');
                }
                setConfirmationModal((prev: any) => ({ ...prev, isOpen: false }));
            }
        });
    };

    // --- Vault & Credentials Logic ---

    const fetchVaultStatus = () => {
        fetch(`${API_BASE}/security/status`)
            .then(res => res.json())
            .then(data => setVaultStatus(data))
            .catch(err => console.error("Failed to fetch vault status", err));
    };

    const fetchCredentials = () => {
        fetch(`${API_BASE}/security/credentials`)
            .then(res => res.json())
            .then(data => setCredentials(data))
            .catch(err => console.error("Failed to fetch credentials", err));
    };

    const handleUnlockVault = async () => {
        try {
            const res = await fetch(`${API_BASE}/security/unlock`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: vaultPassword })
            });
            if (res.ok) {
                setVaultStatus({ ...vaultStatus, is_unlocked: true });
                setVaultPassword('');
                showToast('Cofre desbloqueado!', 'success');
            } else {
                showToast('Senha incorreta.', 'error');
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleAddCredential = async () => {
        try {
            const res = await fetch(`${API_BASE}/security/credentials`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newCred)
            });
            if (res.ok) {
                fetchCredentials();
                setIsAddingCred(false);
                setNewCred({ name: '', username: '', password: '', description: '' });
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleDeleteCredential = (id: string) => {
        setConfirmationModal({
            isOpen: true,
            title: 'Remover Credencial',
            message: 'Tem certeza que deseja remover esta credencial?',
            confirmText: 'Remover',
            type: 'danger',
            onConfirm: async () => {
                try {
                    const res = await fetch(`${API_BASE}/security/credentials/${id}`, { method: 'DELETE' });
                    if (res.ok) {
                        fetchCredentials();
                        if (settings.default_credential_id === id) {
                            onUpdateSettings({ ...settings, default_credential_id: undefined });
                        }
                        showToast('Credencial removida com sucesso!', 'success');
                    }
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao remover credencial.', 'error');
                }
                setConfirmationModal((prev: any) => ({ ...prev, isOpen: false }));
            }
        });
    };

    // --- Computed ---
    const trustedDomains = trustedHosts.filter(h => h.includes('*'));
    const trustedSpecifics = trustedHosts.filter(h => !h.includes('*'));

    return (
        <div className="space-y-6 animate-fadeIn">
            <div className="space-y-4">
                <h3 className="text-white font-medium">Configurações Gerais</h3>
                <div className="flex items-center justify-between">
                    <span className="text-zinc-400 text-sm">Adicionar hosts automaticamente aos confiáveis</span>
                    <button
                        onClick={() => onUpdateSettings({ ...settings, auto_add_trusted_hosts: !settings.auto_add_trusted_hosts })}
                        className={clsx("w-10 h-5 rounded-full transition-colors relative", settings.auto_add_trusted_hosts ? "bg-blue-600" : "bg-zinc-700")}
                    >
                        <div className={clsx("absolute top-1 w-3 h-3 rounded-full bg-white transition-all", settings.auto_add_trusted_hosts ? "left-6" : "left-1")} />
                    </button>
                </div>
                <div className="flex items-center justify-between">
                    <span className="text-zinc-400 text-sm">Login automático se credencial corresponder</span>
                    <button
                        onClick={() => onUpdateSettings({ ...settings, auto_login: !settings.auto_login })}
                        className={clsx("w-10 h-5 rounded-full transition-colors relative", settings.auto_login ? "bg-blue-600" : "bg-zinc-700")}
                    >
                        <div className={clsx("absolute top-1 w-3 h-3 rounded-full bg-white transition-all", settings.auto_login ? "left-6" : "left-1")} />
                    </button>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-zinc-300">Credencial Padrão para Acesso Remoto</label>
                    <select
                        value={settings.default_credential_id || ''}
                        onChange={(e) => onUpdateSettings({ ...settings, default_credential_id: e.target.value || undefined })}
                        className={clsx("w-full bg-zinc-950 border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors", isChanged('default_credential_id', settings.default_credential_id) ? "border-blue-500/50 text-white" : "border-zinc-700 text-zinc-500")}
                    >
                        <option value="">Nenhuma</option>
                        {credentials.map(cred => (
                            <option key={cred.id} value={cred.id}>{cred.name}</option>
                        ))}
                    </select>
                    <p className="text-xs text-zinc-500">Credencial usada por padrão ao tentar acesso remoto.</p>
                </div>
            </div>

            <div className="space-y-4 pt-4 border-t border-zinc-800">
                <h3 className="text-white font-medium flex items-center gap-2">
                    Cofre de Credenciais
                    <HelpButton title="Cofre de Credenciais" description="Armazena suas credenciais de forma segura e criptografada. Permite login automático em hosts e serviços." />
                </h3>
                {!vaultStatus.has_vault && (
                    <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 space-y-2">
                        <p className="text-zinc-400 text-sm">Crie um cofre para armazenar suas credenciais de forma segura.</p>
                        <button onClick={() => setCreateVaultModal({ isOpen: true, password: '', confirmPassword: '', hint: '' })} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
                            Criar Cofre
                        </button>
                    </div>
                )}
                {vaultStatus.has_vault && !vaultStatus.is_unlocked && (
                    <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 space-y-2">
                        <p className="text-zinc-400 text-sm">O cofre está bloqueado. Insira a senha para desbloquear.</p>
                        <input
                            type="password"
                            value={vaultPassword}
                            onChange={(e) => setVaultPassword(e.target.value)}
                            placeholder="Senha do Cofre"
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                        />
                        <button onClick={handleUnlockVault} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
                            Desbloquear
                        </button>
                    </div>
                )}
                {vaultStatus.is_unlocked && (
                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <h4 className="text-zinc-300 font-medium">Credenciais Salvas</h4>
                            <button onClick={() => setIsAddingCred(true)} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium transition-colors">
                                Adicionar Nova
                            </button>
                        </div>
                        {isAddingCred && (
                            <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 space-y-2">
                                <input
                                    type="text"
                                    value={newCred.name}
                                    onChange={(e) => setNewCred({ ...newCred, name: e.target.value })}
                                    placeholder="Nome (ex: Admin SSH)"
                                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                />
                                <input
                                    type="text"
                                    value={newCred.username}
                                    onChange={(e) => setNewCred({ ...newCred, username: e.target.value })}
                                    placeholder="Usuário"
                                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                />
                                <input
                                    type="password"
                                    value={newCred.password}
                                    onChange={(e) => setNewCred({ ...newCred, password: e.target.value })}
                                    placeholder="Senha"
                                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                />
                                <textarea
                                    value={newCred.description}
                                    onChange={(e) => setNewCred({ ...newCred, description: e.target.value })}
                                    placeholder="Descrição (opcional)"
                                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                />
                                <div className="flex justify-end gap-2">
                                    <button onClick={() => setIsAddingCred(false)} className="px-3 py-1 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-xs font-medium transition-colors">
                                        Cancelar
                                    </button>
                                    <button onClick={handleAddCredential} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium transition-colors">
                                        Salvar Credencial
                                    </button>
                                </div>
                            </div>
                        )}
                        {credentials.length === 0 ? (
                            <p className="text-zinc-500 text-sm">Nenhuma credencial salva.</p>
                        ) : (
                            <div className="space-y-2">
                                {credentials.map(cred => (
                                    <div key={cred.id} className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg p-3">
                                        <div>
                                            <p className="text-white font-medium">{cred.name}</p>
                                            <p className="text-zinc-400 text-xs">{cred.username} {cred.description && `(${cred.description})`}</p>
                                        </div>
                                        <button onClick={() => handleDeleteCredential(cred.id)} className="text-red-400 hover:text-red-300 text-xs">
                                            Remover
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="space-y-4 pt-4 border-t border-zinc-800">
                <h3 className="text-white font-medium flex items-center gap-2">
                    Hosts Confiáveis
                    <HelpButton title="Hosts Confiáveis" description="Lista de IPs ou domínios (com *) que o Windows permite gerenciar remotamente." />
                </h3>

                <div className="flex gap-2">
                    <input
                        type="text"
                        value={newTrustedHost}
                        onChange={(e) => setNewTrustedHost(e.target.value)}
                        placeholder="Adicionar IP ou Domínio (ex: *.empresa.local)"
                        className="flex-1 bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    />
                    <button onClick={() => handleAddTrustedHost()} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
                        Adicionar
                    </button>
                </div>
                {trustedHostStatus && <p className={clsx("text-xs", trustedHostStatus.includes('Erro') ? 'text-red-400' : 'text-green-400')}>{trustedHostStatus}</p>}

                {/* Trusted Domains Section */}
                <div className="space-y-2">
                    <h4 className="text-sm font-medium text-zinc-400">Domínios Confiáveis</h4>
                    {trustedDomains.length === 0 ? (
                        <p className="text-zinc-600 text-xs italic">Nenhum domínio confiável.</p>
                    ) : (
                        <div className="space-y-2 max-h-32 overflow-y-auto custom-scrollbar pr-2">
                            {trustedDomains.map((host, index) => (
                                <div key={index} className="flex items-center justify-between bg-zinc-950/50 border border-zinc-800 rounded-lg p-2">
                                    <span className="text-blue-200 text-sm font-mono">{host}</span>
                                    <button onClick={() => handleRemoveTrustedHost(host)} className="text-zinc-500 hover:text-red-400 transition-colors p-1 rounded hover:bg-zinc-900">
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Specific Hosts Section */}
                <div className="space-y-2">
                    <h4 className="text-sm font-medium text-zinc-400">Hosts Específicos</h4>
                    {trustedSpecifics.length === 0 ? (
                        <p className="text-zinc-600 text-xs italic">Nenhum host específico.</p>
                    ) : (
                        <div className="space-y-2 max-h-40 overflow-y-auto custom-scrollbar pr-2">
                            {trustedSpecifics.map((host, index) => (
                                <div key={index} className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg p-3">
                                    <span className="text-zinc-300 text-sm font-mono">{host}</span>
                                    <button onClick={() => handleRemoveTrustedHost(host)} className="text-zinc-500 hover:text-red-400 transition-colors p-1 rounded hover:bg-zinc-900">
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {trustedHosts.length > 0 && (
                    <div className="flex justify-end pt-2 border-t border-zinc-800/50">
                        <button onClick={handleClearTrustedHosts} className="text-red-400 hover:text-red-300 text-xs flex items-center gap-1">
                            <Trash2 size={12} /> Limpar Tudo
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
