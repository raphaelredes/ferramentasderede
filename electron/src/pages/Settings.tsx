import { useState, useEffect, useRef } from 'react';
import { Settings as SettingsIcon, Save, RotateCcw, Shield, Network, Database, Trash2, Download, Upload } from 'lucide-react';
import { clsx } from 'clsx';
import { useToast } from '../contexts/ToastContext';
import { HelpButton } from '../components/HelpButton';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { RemoteSettings } from '../components/Settings/RemoteSettings';
import { NetworksSettings } from '../components/Settings/NetworksSettings';
import { useVault } from '../contexts/VaultContext';
import { API_BASE } from '../config/api';

interface ScannerSettings {
    default_cidr: string;
    ping_timeout: number;
    concurrency: number;
    /** Resolve manufacturer (MAC→vendor) during scans. Default on. */
    online_vendor_lookup: boolean;
}

interface RemoteSettingsData {
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

export interface NetworkConfig {
    id: string;
    name: string;
    cidr: string;
    source_ip?: string;
    dns_server?: string;
    domain?: string;
    enabled: boolean;
}

interface SettingsData {
    general: GeneralSettings;
    scanner: ScannerSettings;
    remote: RemoteSettingsData;
    dashboard: DashboardSettings;
    networks: NetworkConfig[];
}

interface Backup {
    filename: string;
    path: string;
    size: number;
    created: string;
}

const DEFAULT_SETTINGS: SettingsData = {
    general: { appearance_mode: 'System', ask_initial_info: true },
    scanner: { default_cidr: '', ping_timeout: 200, concurrency: 50, online_vendor_lookup: true },
    remote: { auto_add_trusted_hosts: false, default_credential_id: undefined, auto_login: false },
    dashboard: { status_update_interval: 60, ping_monitor_interval: 5, notify_offline: false, notify_online: false },
    networks: []
};

export function Settings() {
    const [settings, setSettings] = useState<SettingsData>(DEFAULT_SETTINGS);
    const [initialSettings, setInitialSettings] = useState<SettingsData | null>(null);
    const [status, setStatus] = useState('');
    const [activeTab, setActiveTab] = useState<'scanner' | 'remote' | 'dashboard' | 'networks' | 'data'>('scanner');

    // Backups State
    const [backups, setBackups] = useState<Backup[]>([]);
    const [backupStatus, setBackupStatus] = useState('');

    // Vendor (OUI) database State
    const [vendorInfo, setVendorInfo] = useState<{
        present: boolean; complete: boolean; last_updated: string | null; count: number;
    } | null>(null);
    const [vendorUpdating, setVendorUpdating] = useState(false);

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

    // Create Vault Modal State (Shared/Parent managed)
    const [createVaultModal, setCreateVaultModal] = useState({
        isOpen: false,
        password: '',
        confirmPassword: '',
        hint: ''
    });

    const { showToast } = useToast();
    const { refreshStatus: refreshVaultStatus } = useVault();

    // Load vendor-DB status when the scanner tab is shown.
    useEffect(() => {
        if (activeTab !== 'scanner') return;
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API_BASE}/network/vendors/info`);
                const data = await res.json();
                if (!cancelled) setVendorInfo(data);
            } catch (e) {
                console.warn('vendors/info fetch failed', e);
            }
        })();
        return () => { cancelled = true; };
    }, [activeTab]);

    const handleUpdateVendors = async () => {
        setVendorUpdating(true);
        try {
            const res = await fetch(`${API_BASE}/network/vendors/update`, { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message || 'Base de fabricantes atualizada.', 'success');
                if (data.info) setVendorInfo(data.info);
            } else {
                showToast(data.detail || 'Falha ao atualizar base de fabricantes.', 'error');
            }
        } catch (e: any) {
            showToast(`Erro: ${e?.message || 'falha de rede'}`, 'error');
        } finally {
            setVendorUpdating(false);
        }
    };

    const handleCreateVault = async () => {
        if (createVaultModal.password !== createVaultModal.confirmPassword) {
            showToast('As senhas não coincidem.', 'error');
            return;
        }
        if (!createVaultModal.password) {
            showToast('A senha não pode ser vazia.', 'error');
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/security/unlock`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    password: createVaultModal.password,
                    hint: createVaultModal.hint
                })
            });

            if (res.ok) {
                showToast('Cofre criado com sucesso!', 'success');
                setCreateVaultModal({ isOpen: false, password: '', confirmPassword: '', hint: '' });
                // Refresh vault state — was a full page reload, which lost
                // the open settings tab and any unsaved changes elsewhere.
                await refreshVaultStatus();
            } else {
                showToast('Erro ao criar cofre.', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Erro de conexão.', 'error');
        }
    };

    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetchSettings();
        if (activeTab === 'data') {
            fetchBackups();
        }
    }, [activeTab]);

    const fetchSettings = () => {
        fetch(`${API_BASE}/settings`)
            .then(res => res.json())
            .then(data => {
                const merged = {
                    general: { ...DEFAULT_SETTINGS.general, ...data.general },
                    scanner: { ...DEFAULT_SETTINGS.scanner, ...data.scanner },
                    remote: { ...DEFAULT_SETTINGS.remote, ...data.remote },
                    dashboard: { ...DEFAULT_SETTINGS.dashboard, ...data.dashboard },
                    networks: Array.isArray(data.networks) ? data.networks : [],
                };
                setSettings(merged);
                setInitialSettings(merged);
            })
            .catch(() => setStatus('Erro ao carregar configurações.'));
    };

    // --- Backup Functions ---
    const fetchBackups = () => {
        fetch(`${API_BASE}/settings/backups`)
            .then(res => res.json())
            .then(data => setBackups(data))
            .catch(err => console.error("Failed to fetch backups", err));
    };

    const handleCreateBackup = async () => {
        setBackupStatus('Criando backup...');
        try {
            const res = await fetch(`${API_BASE}/settings/backups/create`, { method: 'POST' });
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
                    const res = await fetch(`${API_BASE}/settings/backups/${filename}/restore`, { method: 'POST' });
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
                    const response = await fetch(`${API_BASE}/settings/backups/${filename}`, {
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
            const res = await fetch(`${API_BASE}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            if (res.ok) {
                setStatus('Configurações salvas com sucesso!');
                setInitialSettings(settings);
                setTimeout(() => setStatus(''), 3000);
            } else if (res.status === 422) {
                // FastAPI request-body validation failed. The body looks like
                // {"detail": [{"loc": [...], "msg": "...", "type": "..."}, ...]}.
                // Surface the first field-level error so the operator knows
                // which value (e.g. a malformed dns_server) was rejected.
                try {
                    const body = await res.json();
                    const first = Array.isArray(body?.detail) ? body.detail[0] : null;
                    const loc = first?.loc?.slice(1).join('.') ?? '';
                    const msg = first?.msg ?? 'campo inválido';
                    setStatus(`Erro de validação${loc ? ` em ${loc}` : ''}: ${msg}`);
                } catch {
                    setStatus('Erro de validação ao salvar.');
                }
            } else {
                setStatus('Erro ao salvar.');
            }
        } catch (err) {
            setStatus('Erro de conexão ao salvar.');
        }
    };

    const handleExport = async () => {
        try {
            const response = await fetch(`${API_BASE}/settings/export`);
            if (!response.ok) throw new Error('Falha no download');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

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
            const res = await fetch(`${API_BASE}/settings/import`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                showToast('Importação concluída com sucesso!', 'success');
            } else {
                showToast('Erro na importação.', 'error');
            }
        } catch (err) {
            showToast('Erro ao enviar arquivo.', 'error');
        }
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const [showResetModal, setShowResetModal] = useState(false);

    const handleFactoryReset = async () => {
        setShowResetModal(true);
    };

    const confirmFactoryReset = async () => {
        setShowResetModal(false);
        try {
            const res = await fetch(`${API_BASE}/settings/reset`, { method: 'POST' });
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
                <button onClick={() => setActiveTab('networks')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'networks' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <Network size={16} /> Redes / VLANs
                </button>
                <button onClick={() => setActiveTab('remote')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'remote' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <Shield size={16} /> Acesso Remoto
                </button>
                <button onClick={() => setActiveTab('data')} className={clsx("pb-2 px-2 text-sm font-medium transition-colors flex items-center gap-2", activeTab === 'data' ? "text-blue-400 border-b-2 border-blue-400" : "text-zinc-400 hover:text-zinc-200")}>
                    <Database size={16} /> Dados
                </button>
            </div>

            <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800 flex-1 overflow-y-auto">

                {activeTab === 'scanner' && (
                    <div className="space-y-6 animate-fadeIn">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                CIDR Padrão
                                <HelpButton title="CIDR Padrão" description="Define a rede padrão que será preenchida automaticamente ao abrir o scanner (ex: 192.168.1.0/24)." />
                            </label>
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

                        {/* Manufacturer (MAC vendor) identification */}
                        <div className="space-y-3 pt-2 border-t border-zinc-800/60">
                            <label className="flex items-center justify-between gap-3 cursor-pointer">
                                <span className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-zinc-300">Identificar fabricante no scan</span>
                                    <HelpButton
                                        title="Identificação de fabricante"
                                        description="Resolve o fabricante de cada dispositivo pelo MAC address (via tabela ARP). Só funciona para hosts na MESMA sub-rede — em VLANs roteadas o MAC não é visível. Não identifica o modelo do dispositivo: o MAC só carrega o fabricante."
                                    />
                                </span>
                                <input
                                    type="checkbox"
                                    checked={settings.scanner.online_vendor_lookup}
                                    onChange={(e) => setSettings({ ...settings, scanner: { ...settings.scanner, online_vendor_lookup: e.target.checked } })}
                                    className="w-4 h-4 accent-blue-500"
                                />
                            </label>

                            <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 space-y-3">
                                <div className="flex items-center justify-between gap-4">
                                    <div className="text-xs text-zinc-400 space-y-0.5">
                                        <p className="text-zinc-300 font-medium">Base de fabricantes (IEEE OUI)</p>
                                        {vendorInfo ? (
                                            <>
                                                <p>{vendorInfo.count.toLocaleString('pt-BR')} registros{vendorInfo.complete ? '' : ' (incompleta)'}</p>
                                                <p>Atualizada em: {vendorInfo.last_updated ? new Date(vendorInfo.last_updated).toLocaleDateString('pt-BR') : '—'}</p>
                                            </>
                                        ) : (
                                            <p>Carregando status…</p>
                                        )}
                                    </div>
                                    <button
                                        onClick={handleUpdateVendors}
                                        disabled={vendorUpdating}
                                        className={clsx(
                                            "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors border whitespace-nowrap",
                                            vendorUpdating
                                                ? "bg-zinc-800 text-zinc-500 border-zinc-700 cursor-wait"
                                                : "bg-zinc-800 hover:bg-blue-600 text-zinc-200 hover:text-white border-zinc-700 hover:border-blue-500"
                                        )}
                                    >
                                        <Download size={15} />
                                        {vendorUpdating ? 'Atualizando…' : 'Atualizar base'}
                                    </button>
                                </div>
                                <p className="text-[11px] text-zinc-500 leading-relaxed">
                                    A atualização baixa a lista oficial da IEEE (requer internet). Em rede corporativa com proxy, pode ser necessário configurar o proxy do sistema. O scan usa a base local — não baixa nada automaticamente.
                                </p>
                            </div>
                        </div>

                    </div>
                )}

                {activeTab === 'networks' && (
                    <NetworksSettings
                        networks={settings.networks}
                        onChange={(newNetworks) => setSettings({ ...settings, networks: newNetworks })}
                    />
                )}

                {activeTab === 'remote' && (
                    <RemoteSettings
                        settings={settings.remote}
                        onUpdateSettings={(newRemote) => setSettings({ ...settings, remote: newRemote })}
                        isChanged={(key, val) => isChanged('remote', key, val)}
                        setConfirmationModal={setConfirmationModal}
                        setCreateVaultModal={setCreateVaultModal}
                    />
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
                                                    <td
                                                        className="px-4 py-3 text-zinc-300 font-mono text-xs cursor-pointer hover:text-blue-400 hover:underline transition-colors"
                                                        onClick={() => window.electron.showItemInFolder(backup.path)}
                                                        title="Abrir local do arquivo"
                                                    >
                                                        {backup.filename}
                                                    </td>
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
            {createVaultModal.isOpen && (
                <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 rounded-xl">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-6 animate-fadeIn">
                        <div className="flex items-center gap-3 text-blue-400">
                            <div className="p-3 bg-blue-500/10 rounded-full">
                                <Shield size={24} />
                            </div>
                            <h3 className="text-xl font-bold">Criar Cofre Seguro</h3>
                        </div>

                        <div className="space-y-4">
                            <p className="text-zinc-400 text-sm">
                                Defina uma senha mestra forte para proteger suas credenciais.
                                <br />
                                <span className="text-red-400">Atenção: Se você perder esta senha, não será possível recuperar seus dados.</span>
                            </p>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-300">Senha Mestra</label>
                                <input
                                    type="password"
                                    value={createVaultModal.password}
                                    onChange={(e) => setCreateVaultModal({ ...createVaultModal, password: e.target.value })}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
                                    placeholder="********"
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-300">Confirmar Senha</label>
                                <input
                                    type="password"
                                    value={createVaultModal.confirmPassword}
                                    onChange={(e) => setCreateVaultModal({ ...createVaultModal, confirmPassword: e.target.value })}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
                                    placeholder="********"
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-300">Dica de Senha (Opcional)</label>
                                <input
                                    type="text"
                                    value={createVaultModal.hint}
                                    onChange={(e) => setCreateVaultModal({ ...createVaultModal, hint: e.target.value })}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2 text-white placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
                                    placeholder="Ex: Nome do meu primeiro cachorro"
                                />
                            </div>
                        </div>

                        <div className="flex gap-3 pt-2">
                            <button
                                onClick={() => setCreateVaultModal({ ...createVaultModal, isOpen: false })}
                                className="flex-1 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg font-medium transition-colors"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleCreateVault}
                                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors shadow-lg shadow-blue-900/20"
                            >
                                Criar Cofre
                            </button>
                        </div>
                    </div>
                </div>
            )}
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
