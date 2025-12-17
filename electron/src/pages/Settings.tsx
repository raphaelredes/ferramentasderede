import { useState, useEffect, useRef } from 'react';
import { Settings as SettingsIcon, Save, RotateCcw, Shield, Network, LayoutDashboard, Database, Trash2, Key, Download, Upload } from 'lucide-react';
import { clsx } from 'clsx';
import { useToast } from '../contexts/ToastContext';
import { HelpButton } from '../components/HelpButton';
import { ConfirmationModal } from '../components/ConfirmationModal';

interface ScannerSettings {
    default_cidr: string;
    ping_timeout: number;
    concurrency: number;
    online_vendor_lookup: boolean;
}

interface RemoteSettings {
    auto_add_trusted_hosts: boolean;
    default_credential_id?: string;
    auto_login: boolean;
}

interface DashboardSettings {
    status_update_interval: number;
    ping_monitor_interval: number;
    notify_offline: boolean;
    notify_online: boolean;
}

interface GeneralSettings {
    appearance_mode: string;
    ask_initial_info: boolean;
}

interface SettingsData {
    general: GeneralSettings;
    scanner: ScannerSettings;
    remote: RemoteSettings;
    dashboard: DashboardSettings;
}

interface Credential {
    id: string;
    name: string;
    username: string;
    description?: string;
}

interface Backup {
    filename: string;
    path: string;
    size: number;
    created: string;
}

const DEFAULT_SETTINGS: SettingsData = {
    general: { appearance_mode: 'System', ask_initial_info: true },
    scanner: { default_cidr: '', ping_timeout: 200, concurrency: 50, online_vendor_lookup: false },
    remote: { auto_add_trusted_hosts: false, default_credential_id: undefined, auto_login: false },
    dashboard: { status_update_interval: 60, ping_monitor_interval: 5, notify_offline: false, notify_online: false }
};

export function Settings() {
    const [settings, setSettings] = useState<SettingsData>(DEFAULT_SETTINGS);
    const [initialSettings, setInitialSettings] = useState<SettingsData | null>(null);
    const [status, setStatus] = useState('');
    const [activeTab, setActiveTab] = useState<'scanner' | 'remote' | 'dashboard' | 'data'>('scanner');

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

    // Backups State
    const [backups, setBackups] = useState<Backup[]>([]);
    const [backupStatus, setBackupStatus] = useState('');

    // Confirmation Modal State
    const [confirmationModal, setConfirmationModal] = useState<{
        isOpen: boolean;
        title: string;
        message: React.ReactNode;
        onConfirm: () => void;
        type?: 'danger' | 'warning' | 'info';
        confirmText?: string;
        cancelText?: string;
    }>({ isOpen: false, title: '', message: '', onConfirm: () => { } });

    const closeConfirmation = () => setConfirmationModal(prev => ({ ...prev, isOpen: false }));

    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetchSettings();
        if (activeTab === 'remote') {
            fetchTrustedHosts();
            fetchVaultStatus();
        }
        if (activeTab === 'data') {
            fetchBackups();
        }
    }, [activeTab]);

    useEffect(() => {
        if (vaultStatus.is_unlocked) {
            fetchCredentials();
        }
    }, [vaultStatus.is_unlocked]);

    const fetchSettings = () => {
        fetch('http://127.0.0.1:8000/settings')
            .then(res => res.json())
            .then(data => {
                const merged = {
                    general: { ...DEFAULT_SETTINGS.general, ...data.general },
                    scanner: { ...DEFAULT_SETTINGS.scanner, ...data.scanner },
                    remote: { ...DEFAULT_SETTINGS.remote, ...data.remote },
                    dashboard: { ...DEFAULT_SETTINGS.dashboard, ...data.dashboard },
                };
                setSettings(merged);
                setInitialSettings(merged);
            })
            .catch(() => setStatus('Erro ao carregar configurações.'));
    };

    const fetchTrustedHosts = () => {
        fetch('http://127.0.0.1:8000/settings/trusted-hosts')
            .then(res => res.json())
            .then(data => setTrustedHosts(data))
            .catch(err => console.error("Failed to fetch trusted hosts", err));
    };

    const fetchVaultStatus = () => {
        fetch('http://127.0.0.1:8000/security/status')
            .then(res => res.json())
            .then(data => setVaultStatus(data))
            .catch(err => console.error("Failed to fetch vault status", err));
    };

    const fetchCredentials = () => {
        fetch('http://127.0.0.1:8000/security/credentials')
            .then(res => res.json())
            .then(data => setCredentials(data))
            .catch(err => console.error("Failed to fetch credentials", err));
    };

    const handleUnlockVault = async () => {
        try {
            const res = await fetch('http://127.0.0.1:8000/security/unlock', {
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
            const res = await fetch('http://127.0.0.1:8000/security/credentials', {
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
                    const res = await fetch(`http://127.0.0.1:8000/security/credentials/${id}`, { method: 'DELETE' });
                    if (res.ok) {
                        fetchCredentials();
                        if (settings.remote.default_credential_id === id) {
                            setSettings({ ...settings, remote: { ...settings.remote, default_credential_id: undefined } });
                        }
                        showToast('Credencial removida com sucesso!', 'success');
                    }
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao remover credencial.', 'error');
                }
                setConfirmationModal(prev => ({ ...prev, isOpen: false }));
            }
        });
    };

    // --- Backup Functions ---
    const fetchBackups = () => {
        fetch('http://127.0.0.1:8000/settings/backups')
            .then(res => res.json())
            .then(data => setBackups(data))
            .catch(err => console.error("Failed to fetch backups", err));
    };

    const handleCreateBackup = async () => {
        setBackupStatus('Criando backup...');
        try {
            const res = await fetch('http://127.0.0.1:8000/settings/backups/create', { method: 'POST' });
            if (res.ok) {
                fetchBackups();
                setBackupStatus('Backup criado com sucesso!');
                setTimeout(() => setBackupStatus(''), 3000);
            } else {
                setBackupStatus('Erro ao criar backup.');
            }
        } catch (e) {
            setBackupStatus('Erro de conexão.');
        }
    };

    const handleRestoreBackup = (filename: string) => {
        setConfirmationModal({
            isOpen: true,
            title: 'Restaurar Backup',
            message: (
                <span>
                    Tem certeza que deseja restaurar o backup <strong className="text-white">{filename}</strong>?
                    <br /><br />
                    Isso substituirá os dados atuais e a aplicação será reiniciada.
                </span>
            ),
            confirmText: 'Restaurar',
            type: 'warning',
            onConfirm: async () => {
                setBackupStatus('Restaurando...');
                try {
                    const res = await fetch(`http://127.0.0.1:8000/settings/backups/${filename}/restore`, { method: 'POST' });
                    if (res.ok) {
                        setConfirmationModal({
                            isOpen: true,
                            title: 'Backup Restaurado',
                            message: 'Backup restaurado com sucesso! A aplicação será reiniciada.',
                            confirmText: 'OK',
                            type: 'info',
                            onConfirm: () => window.location.reload()
                        });
                    } else {
                        setBackupStatus('Erro ao restaurar.');
                        showToast('Erro ao restaurar backup.', 'error');
                    }
                } catch (e) {
                    setBackupStatus('Erro de conexão.');
                    showToast('Erro de conexão.', 'error');
                }
            }
        });
    };

    const handleDeleteBackup = async (filename: string) => {
        setConfirmationModal({
            isOpen: true,
            title: 'Excluir Backup',
            message: `Tem certeza que deseja excluir o backup "${filename}"? Esta ação não pode ser desfeita.`,
            type: 'danger',
            confirmText: 'Excluir',
            cancelText: 'Cancelar',
            onConfirm: async () => {
                try {
                    const response = await fetch(`http://127.0.0.1:8000/settings/backups/${filename}`, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    if (data.status === 'success') {
                        setBackupStatus(`Backup excluído com sucesso!`);
                        fetchBackups(); // Refresh list
                    } else {
                        setBackupStatus(`Erro ao excluir: ${data.message}`);
                    }
                } catch (error) {
                    setBackupStatus('Erro ao conectar com o servidor.');
                }
                setConfirmationModal(prev => ({ ...prev, isOpen: false }));
            }
        });
    };

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDate = (isoString: string) => {
        return new Date(isoString).toLocaleString();
    };

    const handleSave = async () => {
        setStatus('Salvando...');
        try {
            const res = await fetch('http://127.0.0.1:8000/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (res.ok) {
                setStatus('Configurações salvas com sucesso!');
                setInitialSettings(settings);
                setTimeout(() => setStatus(''), 3000);
            } else {
                setStatus('Erro ao salvar.');
            }
        } catch (err) {
            setStatus('Erro de conexão ao salvar.');
        }
    };

    const handleAddTrustedHost = async () => {
        if (!newTrustedHost) return;
        setTrustedHostStatus('Adicionando...');
        try {
            const res = await fetch(`http://127.0.0.1:8000/settings/trusted-hosts?host=${encodeURIComponent(newTrustedHost)}`, {
                method: 'POST'
            });
            if (res.ok) {
                setNewTrustedHost('');
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

    const handleClearTrustedHosts = () => {
        setConfirmationModal({
            isOpen: true,
            title: 'Limpar Hosts Confiáveis',
            message: 'Tem certeza que deseja limpar todos os Hosts Confiáveis? Isso pode afetar o acesso remoto.',
            confirmText: 'Limpar',
            type: 'warning',
            onConfirm: async () => {
                try {
                    const res = await fetch('http://127.0.0.1:8000/settings/trusted-hosts', { method: 'DELETE' });
                    if (res.ok) {
                        fetchTrustedHosts();
                        showToast('Hosts confiáveis limpos.', 'success');
                    }
                } catch (e) {
                    console.error(e);
                    showToast('Erro ao limpar hosts.', 'error');
                }
                setConfirmationModal(prev => ({ ...prev, isOpen: false }));
            }
        });
    };

    const { showToast } = useToast();

    const handleExport = async () => {
        try {
            const response = await fetch('http://127.0.0.1:8000/settings/export');
            if (!response.ok) throw new Error('Falha no download');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Tentar obter nome do arquivo do header ou usar padrão
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `hosts_backup_${new Date().toISOString().slice(0, 10)}.json`;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="?([^"]+)"?/);
                if (match && match[1]) filename = match[1];
            }

            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showToast('Exportação concluída com sucesso!', 'success');
        } catch (error) {
            console.error('Download failed:', error);
            showToast('Erro ao exportar arquivo.', 'error');
        }
    };

    const handleImportClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('http://127.0.0.1:8000/settings/import', {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                showToast('Importação concluída com sucesso!', 'success');
                // Opcional: recarregar hosts se necessário, mas eles estão no backend
            } else {
                showToast('Erro na importação.', 'error');
            }
        } catch (err) {
            showToast('Erro ao enviar arquivo.', 'error');
        }
        // Reset input
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const [showResetModal, setShowResetModal] = useState(false);

    const handleFactoryReset = async () => {
        // Trigger modal instead of confirm
        setShowResetModal(true);
    };

    const confirmFactoryReset = async () => {
        setShowResetModal(false);
        try {
            const res = await fetch('http://127.0.0.1:8000/settings/reset', { method: 'POST' });
            if (res.ok) {
                setConfirmationModal({
                    isOpen: true,
                    title: 'Reset Concluído',
                    message: 'A aplicação foi resetada com sucesso e será reiniciada.',
                    confirmText: 'OK',
                    type: 'info',
                    onConfirm: () => window.location.reload()
                });
            }
        } catch (e) {
            showToast('Erro ao resetar aplicação.', 'error');
        }
    };

    // Helper to check if a value changed
    const isChanged = (section: keyof SettingsData, key: string, val: any) => {
        if (!initialSettings) return false;
        // @ts-ignore
        return initialSettings[section][key] !== val;
    };

    return (
        <div className="h-full flex flex-col space-y-6 p-8 relative">
            {showResetModal && (
                <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 rounded-xl">
                    <div className="bg-zinc-900 border border-red-900/50 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-6 animate-fadeIn">
                        <div className="flex items-center gap-3 text-red-500">
                            <div className="p-3 bg-red-500/10 rounded-full">
                                <Shield size={24} />
                            </div>
                            <h3 className="text-xl font-bold">Atenção: Zona de Perigo</h3>
                        </div>

                        <div className="space-y-2">
                            <p className="text-zinc-300">
                                Você está prestes a realizar uma <strong className="text-red-400">Restauração de Fábrica</strong>.
                            </p>
                            <p className="text-zinc-400 text-sm">
                                Esta ação é irreversível e irá:
                            </p>
                            <ul className="list-disc list-inside text-zinc-400 text-sm space-y-1 ml-2">
                                <li>Apagar todos os hosts salvos</li>
                                <li>Remover todas as credenciais do cofre</li>
                                <li>Resetar todas as configurações para o padrão</li>
                                <li>Limpar o histórico de varreduras</li>
                                <li>Limpar lista de Hosts Confiáveis (WinRM)</li>
                            </ul>
                        </div>

                        <div className="flex gap-3 pt-2">
                            <button
                                onClick={() => setShowResetModal(false)}
                                className="flex-1 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg font-medium transition-colors"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={confirmFactoryReset}
                                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors shadow-lg shadow-red-900/20"
                            >
                                Confirmar Reset
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <header>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <SettingsIcon /> Configurações
                </h2>
                <p className="text-zinc-400">Gerencie preferências, rede e dados.</p>
            </header>

            <div className="flex gap-4 border-b border-zinc-800 pb-1">
                <button onClick={() => setActiveTab('scanner')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'scanner' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <Network size={16} /> Scanner de Rede
                </button>
                <button onClick={() => setActiveTab('remote')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'remote' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <Shield size={16} /> Acesso Remoto
                </button>
                <button onClick={() => setActiveTab('dashboard')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'dashboard' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <LayoutDashboard size={16} /> Dashboard
                </button>
                <button onClick={() => setActiveTab('data')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'data' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <Database size={16} /> Dados
                </button>
            </div>

            <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800 flex-1 overflow-y-auto">

                {activeTab === 'scanner' && (
                    <div className="space-y-6 animate-fadeIn">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300">CIDR Padrão</label>
                            <input
                                type="text"
                                value={settings.scanner.default_cidr}
                                onChange={(e) => setSettings({ ...settings, scanner: { ...settings.scanner, default_cidr: e.target.value } })}
                                placeholder="Ex: 192.168.1.0/24"
                                className={clsx("w-full bg-zinc-950 border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors", isChanged('scanner', 'default_cidr', settings.scanner.default_cidr) ? "border-blue-500/50 text-white" : "border-zinc-700 text-zinc-500")}
                            />
                            <p className="text-xs text-zinc-500">Rede padrão preenchida automaticamente ao abrir o scanner.</p>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-300">Timeout do Ping (ms)</label>
                                <input
                                    type="number"
                                    value={settings.scanner.ping_timeout}
                                    onChange={(e) => setSettings({ ...settings, scanner: { ...settings.scanner, ping_timeout: parseInt(e.target.value) || 0 } })}
                                    className={clsx("w-full bg-zinc-950 border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors", isChanged('scanner', 'ping_timeout', settings.scanner.ping_timeout) ? "border-blue-500/50 text-white" : "border-zinc-700 text-zinc-500")}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-300">Concorrência (Threads)</label>
                                <input
                                    type="number"
                                    value={settings.scanner.concurrency}
                                    onChange={(e) => setSettings({ ...settings, scanner: { ...settings.scanner, concurrency: parseInt(e.target.value) || 0 } })}
                                    className={clsx("w-full bg-zinc-950 border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors", isChanged('scanner', 'concurrency', settings.scanner.concurrency) ? "border-blue-500/50 text-white" : "border-zinc-700 text-zinc-500")}
                                />
                            </div>
                        </div>

                        <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
                            <div>
                                <h3 className="text-white font-medium flex items-center gap-2">
                                    Consulta de Fabricante Online
                                    <HelpButton title="Consulta de Fabricante" description="Utiliza uma API externa para identificar o fabricante do dispositivo pelo MAC Address. Requer conexão com a internet." />
                                </h3>
                                <p className="text-xs text-zinc-500">Consultar API online para identificar fabricantes (mais preciso, mas requer internet).</p>
                            </div>
                            <button
                                onClick={() => setSettings({ ...settings, scanner: { ...settings.scanner, online_vendor_lookup: !settings.scanner.online_vendor_lookup } })}
                                className={clsx("w-12 h-6 rounded-full transition-colors relative", settings.scanner.online_vendor_lookup ? "bg-blue-600" : "bg-zinc-700")}
                            >
                                <div className={clsx("absolute top-1 w-4 h-4 rounded-full bg-white transition-all", settings.scanner.online_vendor_lookup ? "left-7" : "left-1")} />
                            </button>
                        </div>
                    </div>
                )}

                {activeTab === 'remote' && (
                    <div className="space-y-6 animate-fadeIn">
                        <div className="space-y-4">
                            <h3 className="text-white font-medium">Configurações Gerais</h3>
                            <div className="flex items-center justify-between">
                                <span className="text-zinc-400 text-sm">Adicionar hosts automaticamente aos confiáveis</span>
                                <button
                                    onClick={() => setSettings({ ...settings, remote: { ...settings.remote, auto_add_trusted_hosts: !settings.remote.auto_add_trusted_hosts } })}
                                    className={clsx("w-10 h-5 rounded-full transition-colors relative", settings.remote.auto_add_trusted_hosts ? "bg-blue-600" : "bg-zinc-700")}
                                >
                                    <div className={clsx("absolute top-1 w-3 h-3 rounded-full bg-white transition-all", settings.remote.auto_add_trusted_hosts ? "left-6" : "left-1")} />
                                </button>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-zinc-400 text-sm">Login automático se credencial corresponder</span>
                                <button
                                    onClick={() => setSettings({ ...settings, remote: { ...settings.remote, auto_login: !settings.remote.auto_login } })}
                                    className={clsx("w-10 h-5 rounded-full transition-colors relative", settings.remote.auto_login ? "bg-blue-600" : "bg-zinc-700")}
                                >
                                    <div className={clsx("absolute top-1 w-3 h-3 rounded-full bg-white transition-all", settings.remote.auto_login ? "left-6" : "left-1")} />
                                </button>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-300">Credencial Padrão para Acesso Remoto</label>
                                <select
                                    value={settings.remote.default_credential_id || ''}
                                    onChange={(e) => setSettings({ ...settings, remote: { ...settings.remote, default_credential_id: e.target.value || undefined } })}
                                    className={clsx("w-full bg-zinc-950 border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 transition-colors", isChanged('remote', 'default_credential_id', settings.remote.default_credential_id) ? "border-blue-500/50 text-white" : "border-zinc-700 text-zinc-500")}
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
                                    <button onClick={() => alert('Implementar criação de cofre')} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
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
                                <HelpButton title="Hosts Confiáveis" description="Lista de IPs ou nomes de máquinas que o Windows permite gerenciar remotamente via WinRM. Necessário para comandos remotos." />
                            </h3>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={newTrustedHost}
                                    onChange={(e) => setNewTrustedHost(e.target.value)}
                                    placeholder="Adicionar IP ou Hostname"
                                    className="flex-1 bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                />
                                <button onClick={handleAddTrustedHost} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
                                    Adicionar
                                </button>
                            </div>
                            <div className="space-y-2 max-h-40 overflow-y-auto custom-scrollbar pr-2">
                                {trustedHosts.length === 0 ? (
                                    <p className="text-zinc-500 text-sm">Nenhum host confiável adicionado.</p>
                                ) : (
                                    trustedHosts.map((host, index) => (
                                        <div key={index} className="flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg p-3">
                                            <span className="text-zinc-300 text-sm font-mono">{host}</span>
                                        </div >
                                    ))
                                )}
                            </div >

                            <div className="flex justify-between items-center pt-2 border-t border-zinc-800">
                                <span className="text-xs text-zinc-500">{trustedHostStatus}</span>
                                <button onClick={handleClearTrustedHosts} className="text-red-400 hover:text-red-300 text-xs flex items-center gap-1">
                                    <Trash2 size={12} /> Limpar Tudo
                                </button>
                            </div>
                        </div >
                    </div>
                )}

                {activeTab === 'data' && (
                    <div className="space-y-8 animate-fadeIn">
                        <div className="space-y-4">
                            <h3 className="text-white font-medium flex items-center gap-2">
                                <Database size={16} /> Backup e Restauração
                                <HelpButton title="Backup e Restauração" description="Salve manualmente seus hosts e configurações em um arquivo JSON ou restaure de um arquivo anterior." />
                            </h3>
                            <div className="grid grid-cols-2 gap-4">
                                <button onClick={handleExport} className="flex flex-col items-center justify-center gap-2 p-6 bg-zinc-950 border border-zinc-800 rounded-lg hover:border-blue-500/50 hover:bg-zinc-900 transition-all group">
                                    <Upload size={24} className="text-zinc-500 group-hover:text-blue-400 transition-colors" />
                                    <span className="text-zinc-300 font-medium">Exportar Hosts</span>
                                    <span className="text-xs text-zinc-600">Baixar arquivo JSON</span>
                                </button>
                                <button onClick={handleImportClick} className="flex flex-col items-center justify-center gap-2 p-6 bg-zinc-950 border border-zinc-800 rounded-lg hover:border-green-500/50 hover:bg-zinc-900 transition-all group">
                                    <Download size={24} className="text-zinc-500 group-hover:text-green-400 transition-colors" />
                                    <span className="text-zinc-300 font-medium">Importar Hosts</span>
                                    <span className="text-xs text-zinc-600">Restaurar backup JSON</span>
                                </button>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileChange}
                                    accept=".json"
                                    className="hidden"
                                />
                            </div>
                        </div>

                        <div className="pt-6 border-t border-zinc-800 space-y-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-white font-medium flex items-center gap-2">
                                        <RotateCcw size={16} /> Backups Automáticos
                                        <HelpButton title="Backups Automáticos" description="O sistema cria backups diários automaticamente. Aqui você pode ver, criar ou restaurar esses backups." />
                                    </h3>
                                    <p className="text-zinc-400 text-xs">Gerencie os backups automáticos diários do sistema.</p>
                                </div>
                                <button onClick={handleCreateBackup} className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 rounded-lg text-xs font-medium transition-colors">
                                    + Criar Backup Manual
                                </button>
                            </div>

                            <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
                                {backups.length === 0 ? (
                                    <div className="p-8 text-center text-zinc-500 text-sm">
                                        Nenhum backup encontrado.
                                    </div>
                                ) : (
                                    <table className="w-full text-sm text-left">
                                        <thead className="bg-zinc-900/50 text-zinc-400 font-medium border-b border-zinc-800">
                                            <tr>
                                                <th className="px-4 py-3">Arquivo</th>
                                                <th className="px-4 py-3">Data</th>
                                                <th className="px-4 py-3">Tamanho</th>
                                                <th className="px-4 py-3 text-right">Ações</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-zinc-800">
                                            {backups.map((backup) => (
                                                <tr key={backup.filename} className="hover:bg-zinc-900/30 transition-colors">
                                                    <td className="px-4 py-3 text-zinc-300 font-mono text-xs">{backup.filename}</td>
                                                    <td className="px-4 py-3 text-zinc-400">{formatDate(backup.created)}</td>
                                                    <td className="px-4 py-3 text-zinc-500">{formatBytes(backup.size)}</td>
                                                    <td className="px-4 py-3 text-right flex items-center justify-end gap-2">
                                                        <button
                                                            onClick={() => handleRestoreBackup(backup.filename)}
                                                            className="text-blue-400 hover:text-blue-300 font-medium text-xs"
                                                            title="Restaurar Backup"
                                                        >
                                                            Restaurar
                                                        </button>
                                                        <button
                                                            onClick={() => handleDeleteBackup(backup.filename)}
                                                            className="text-red-400 hover:text-red-300 font-medium text-xs p-1 hover:bg-red-900/20 rounded"
                                                            title="Excluir Backup"
                                                        >
                                                            <Trash2 size={14} />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                            </div>
                            {backupStatus && <p className="text-xs text-blue-400">{backupStatus}</p>}
                        </div>

                        <div className="pt-6 border-t border-zinc-800">
                            <h3 className="text-red-400 font-medium flex items-center gap-2 mb-4">
                                <Shield size={16} /> Zona de Perigo
                                <HelpButton title="Zona de Perigo" description="Ações destrutivas como apagar todos os dados e resetar o aplicativo para o estado original." className="text-red-400 hover:text-red-300" />
                            </h3>
                            <div className="bg-red-950/10 border border-red-900/30 rounded-lg p-4 flex items-center justify-between">
                                <div>
                                    <h4 className="text-red-200 font-medium">Restauração de Fábrica</h4>
                                    <p className="text-red-400/60 text-xs">Apaga todos os dados, hosts e configurações.</p>
                                </div>
                                <button onClick={handleFactoryReset} className="px-4 py-2 bg-red-900/20 hover:bg-red-900/40 text-red-400 border border-red-900/50 rounded-lg text-sm font-medium transition-colors">
                                    Restaurar Padrões
                                </button>
                            </div>
                        </div>
                    </div>
                )}


                <div className="pt-4 border-t border-zinc-800 flex items-center justify-between">
                    <span className={clsx("text-sm", status.includes('Erro') ? "text-red-500" : "text-green-500")}>
                        {status}
                    </span>

                    <button
                        onClick={handleSave}
                        className="flex items-center gap-2 px-6 py-2 bg-zinc-800 hover:bg-zinc-700 text-blue-400 border border-blue-900/30 hover:border-blue-500/50 rounded-lg font-medium transition-colors"
                    >
                        <Save size={18} />
                        Salvar Alterações
                    </button>
                </div>
            </div>
            <ConfirmationModal
                isOpen={confirmationModal.isOpen}
                onClose={() => setConfirmationModal(prev => ({ ...prev, isOpen: false }))}
                onConfirm={confirmationModal.onConfirm}
                title={confirmationModal.title}
                message={confirmationModal.message}
                type={confirmationModal.type}
                confirmText={confirmationModal.confirmText}
                cancelText={confirmationModal.cancelText}
            />
        </div >
    )
}
