import { useEffect, useMemo, useState } from 'react';
import { Terminal as TerminalIcon, ExternalLink, BookOpen, Layers, Code2 } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../config/api';
import { useMonitoring } from '../contexts/MonitoringContext';
import { Host } from '../types';
import { probeHost } from '../utils/hostProbe';
import { resolveTeamViewerId } from '../utils/teamviewer';
import { CommandGuideModal } from '../components/Terminal/CommandGuideModal';
import { BatchRunnerModal } from '../components/Terminal/BatchRunnerModal';
import { SnippetsDrawer } from '../components/Terminal/SnippetsDrawer';
import { HostPicker, MANUAL_OPTION_VALUE } from '../components/Terminal/HostPicker';

type LogEntry = { ts: number; level: 'info' | 'warn' | 'error'; text: string };

export function Terminal() {
    const { hosts, refreshHosts } = useMonitoring();
    const [connection, setConnection] = useState({ ip: '', username: '', password: '' });
    const [status, setStatus] = useState('Pronto');
    const [busy, setBusy] = useState(false);
    const [log, setLog] = useState<LogEntry[]>([]);
    const [defaultCredName, setDefaultCredName] = useState<string | null>(null);

    const [selectedAddress, setSelectedAddress] = useState<string>('');
    const [isPickerOpen, setIsPickerOpen] = useState(false);
    const [search, setSearch] = useState('');
    
    // Modals
    const [isGuideOpen, setIsGuideOpen] = useState(false);
    const [isBatchOpen, setIsBatchOpen] = useState(false);
    const [isSnippetsOpen, setIsSnippetsOpen] = useState(false);

    const append = (text: string, level: LogEntry['level'] = 'info') =>
        setLog(prev => [...prev.slice(-200), { ts: Date.now(), level, text }]);

    useEffect(() => {
        fetch(`${API_BASE}/settings`)
            .then(res => res.json())
            .then(data => {
                if (data.remote?.auto_login && data.remote?.default_credential_id) {
                    return fetch(`${API_BASE}/security/credentials`)
                        .then(res => res.json())
                        .then(creds => {
                            const cred = creds.find((c: any) => c.id === data.remote.default_credential_id);
                            if (cred) {
                                setDefaultCredName(cred.name);
                                setConnection(prev => ({ ...prev, username: cred.username }));
                                append(`Credencial padrão '${cred.name}' carregada.`, 'info');
                            }
                        })
                        .catch(() => append('Cofre bloqueado — credencial padrão indisponível.', 'warn'));
                }
            })
            .catch(err => console.error('Failed to fetch settings', err));
    }, []);

    const sortedHosts = useMemo(() => {
        return [...hosts]
            .filter(h => !!h.address)
            .sort((a, b) => {
                const am = a.monitoring !== false ? 0 : 1;
                const bm = b.monitoring !== false ? 0 : 1;
                if (am !== bm) return am - bm;
                const an = (a.name || a.hostname || a.address || '').toLowerCase();
                const bn = (b.name || b.hostname || b.address || '').toLowerCase();
                return an.localeCompare(bn);
            });
    }, [hosts]);

    const filteredHosts = useMemo(() => {
        if (!search.trim()) return sortedHosts;
        const q = search.toLowerCase();
        return sortedHosts.filter(h => {
            const name = (h.name || h.hostname || '').toLowerCase();
            const ip = (h.ip || h.address || '').toLowerCase();
            const group = (h.group || '').toLowerCase();
            return name.includes(q) || ip.includes(q) || group.includes(q);
        });
    }, [sortedHosts, search]);

    const selectedHost: Host | null = useMemo(
        () => sortedHosts.find(h => h.address === selectedAddress) || null,
        [sortedHosts, selectedAddress]
    );

    const pickHost = (host: Host) => {
        setSelectedAddress(host.address);
        setIsPickerOpen(false);
        setSearch('');
        const ip = host.ip || host.address;
        setConnection(prev => ({ ...prev, ip }));
        const displayName = host.name || host.hostname || host.address;
        append(`Alvo selecionado: ${displayName} (${ip})`, 'info');
    };

    const pickManual = () => {
        setSelectedAddress(MANUAL_OPTION_VALUE);
        setIsPickerOpen(false);
        setSearch('');
        setConnection(prev => ({ ...prev, ip: '' }));
        append('Modo manual ativado. Digite o IP ou hostname.', 'info');
    };

    const openExternal = () => {
        const target = connection.ip.trim();
        if (!target) {
            append('Erro: Informe o IP ou hostname do alvo.', 'error');
            return;
        }

        setBusy(true);
        setStatus(`Abrindo terminal para ${target}…`);
        append(`Iniciando PowerShell remoto em ${target}…`, 'info');

        fetch(`${API_BASE}/terminal/open-external`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ip: target,
                username: connection.username || null,
                password: connection.password || null,
            }),
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    append(`✓ Janela aberta com sucesso (PID ${data.pid ?? '—'}).`, 'info');
                    setStatus('Sessão iniciada');
                    if (selectedHost && !selectedHost.teamviewer_id) {
                        resolveTeamViewerId({
                            targetIp: selectedHost.ip || selectedHost.address,
                            persistOnHost: selectedHost.address,
                        }).then(res => {
                            if (res.ok) refreshHosts();
                        });
                    }
                    if (selectedHost) {
                        probeHost({
                            targetIp: selectedHost.ip || selectedHost.address,
                        }).then(res => {
                            if (res.ok) refreshHosts();
                        });
                    }
                } else {
                    append(`✗ Falha: ${data.message || 'Erro desconhecido'}`, 'error');
                    setStatus('Erro ao abrir');
                }
            })
            .catch(err => {
                append(`✗ Erro na requisição: ${err.message}`, 'error');
                setStatus('Erro');
            })
            .finally(() => setBusy(false));
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !busy) openExternal();
    };

    return (
        <div className="h-full flex flex-col space-y-4 min-h-0 p-8">
            <header className="flex items-start justify-between gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                        <TerminalIcon /> Terminal Remoto
                    </h2>
                    <p className="text-zinc-400">
                        Abre uma janela PowerShell nativa autenticada via WinRM. A sessão acontece fora desta janela.
                    </p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <button
                        type="button"
                        onClick={() => setIsBatchOpen(true)}
                        className="flex items-center gap-2 px-3 py-2 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/40 rounded-lg text-sm font-medium transition-colors"
                        title="Execução paralela em múltiplos hosts"
                    >
                        <Layers size={16} />
                        <span>WinRM em Lote</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => setIsSnippetsOpen(true)}
                        className="flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-blue-400 border border-zinc-700/60 rounded-lg text-sm font-medium transition-colors"
                        title="Biblioteca de Snippets"
                    >
                        <Code2 size={16} />
                        <span>Snippets</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => setIsGuideOpen(true)}
                        className="flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-blue-400 border border-zinc-700/60 rounded-lg text-sm font-medium transition-colors"
                        title="Abrir guia de comandos PowerShell"
                    >
                        <BookOpen size={16} />
                        <span>Guia</span>
                    </button>
                </div>
            </header>

            <CommandGuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />
            <BatchRunnerModal isOpen={isBatchOpen} onClose={() => setIsBatchOpen(false)} hosts={hosts} />
            <SnippetsDrawer 
                isOpen={isSnippetsOpen} 
                onClose={() => setIsSnippetsOpen(false)} 
                onSelectSnippet={(cmd) => {
                    append(`Snippet inserido: ${cmd}`, 'info');
                }} 
            />

            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 flex gap-4 items-end">
                <div className="flex-1 grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-4">
                    <HostPicker
                        hosts={hosts}
                        filteredHosts={filteredHosts}
                        selectedAddress={selectedAddress}
                        selectedHost={selectedHost}
                        isPickerOpen={isPickerOpen}
                        setIsPickerOpen={setIsPickerOpen}
                        search={search}
                        setSearch={setSearch}
                        busy={busy}
                        pickHost={pickHost}
                        pickManual={pickManual}
                    />

                    {/* Username */}
                    <div className="space-y-1">
                        <label className="text-xs text-white">
                            Usuário {defaultCredName && <span className="text-blue-400">({defaultCredName})</span>}
                        </label>
                        <input
                            type="text"
                            value={connection.username}
                            onChange={e => setConnection(prev => ({ ...prev, username: e.target.value }))}
                            className="w-full bg-zinc-950 border border-zinc-700 focus:border-blue-500 focus:outline-none rounded px-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-500"
                            placeholder="DOMINIO\\usuario"
                            disabled={busy}
                            onKeyDown={handleKeyDown}
                        />
                    </div>

                    {/* Password */}
                    <div className="space-y-1">
                        <label className="text-xs text-white">Senha</label>
                        <input
                            type="password"
                            value={connection.password}
                            onChange={e => setConnection(prev => ({ ...prev, password: e.target.value }))}
                            className="w-full bg-zinc-950 border border-zinc-700 focus:border-blue-500 focus:outline-none rounded px-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-500"
                            placeholder="••••••"
                            disabled={busy}
                            onKeyDown={handleKeyDown}
                        />
                    </div>
                </div>

                <button
                    onClick={openExternal}
                    disabled={busy}
                    className={clsx(
                        'flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-colors h-[38px] border',
                        busy
                            ? 'bg-zinc-800 text-zinc-500 border-zinc-800 cursor-not-allowed'
                            : 'bg-zinc-800 hover:bg-zinc-700 text-green-400 border-green-900/30 hover:border-green-500/50'
                    )}
                >
                    <ExternalLink size={18} />
                    Abrir Terminal
                </button>
            </div>

            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden p-4 font-mono text-sm">
                {log.length === 0 ? (
                    <p className="text-zinc-600">Aguardando ação. As credenciais são enviadas via variáveis de ambiente, não pela linha de comando do PowerShell.</p>
                ) : (
                    <ul className="space-y-1">
                        {log.map((entry, i) => (
                            <li
                                key={i}
                                className={clsx(
                                    entry.level === 'error' && 'text-red-400',
                                    entry.level === 'warn' && 'text-yellow-400',
                                    entry.level === 'info' && 'text-zinc-300'
                                )}
                            >
                                <span className="text-zinc-600 mr-2">
                                    {new Date(entry.ts).toLocaleTimeString()}
                                </span>
                                {entry.text}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="text-xs text-zinc-600 flex justify-between px-2">
                <span>Status: {status}</span>
                <span>Protocolo: WinRM (HTTP Negotiate)</span>
            </div>
        </div>
    );
}
