import { useEffect, useMemo, useRef, useState } from 'react';
import { Terminal as TerminalIcon, ExternalLink, ChevronDown, Search } from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../config/api';
import { useMonitoring } from '../contexts/MonitoringContext';
import { Host } from '../types';
import { probeHost } from '../utils/hostProbe';
import { resolveTeamViewerId } from '../utils/teamviewer';

type LogEntry = { ts: number; level: 'info' | 'warn' | 'error'; text: string };

const MANUAL_OPTION_VALUE = '__manual__';

export function Terminal() {
    const { hosts, refreshHosts } = useMonitoring();
    const [connection, setConnection] = useState({ ip: '', username: '', password: '' });
    const [status, setStatus] = useState('Pronto');
    const [busy, setBusy] = useState(false);
    const [log, setLog] = useState<LogEntry[]>([]);
    const [defaultCredName, setDefaultCredName] = useState<string | null>(null);

    // Selected entry in the host picker. Empty = no host chosen yet, MANUAL_OPTION_VALUE
    // = user picked "digitar manualmente" so the IP field becomes a free text input.
    const [selectedAddress, setSelectedAddress] = useState<string>('');
    const [isPickerOpen, setIsPickerOpen] = useState(false);
    const [search, setSearch] = useState('');
    const pickerRef = useRef<HTMLDivElement>(null);

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

    // Close dropdown on outside click.
    useEffect(() => {
        if (!isPickerOpen) return;
        const onDown = (e: MouseEvent) => {
            if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
                setIsPickerOpen(false);
            }
        };
        document.addEventListener('mousedown', onDown);
        return () => document.removeEventListener('mousedown', onDown);
    }, [isPickerOpen]);

    // Sort hosts: monitored first, then alphabetical by display name. We coalesce
    // null name/hostname to '' because some discovered hosts ship with null and
    // localeCompare on null blows up.
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

    const isManualMode = selectedAddress === MANUAL_OPTION_VALUE;

    const pickHost = (host: Host) => {
        setSelectedAddress(host.address);
        setConnection(prev => {
            const next = { ...prev, ip: host.ip || host.address };

            // Auto-set the DOMINIO\ prefix from the picked host's known AD
            // domain. We use the NetBIOS short name (CONTOSO from
            // contoso.local) since that's what WinRM expects in DOMINIO\user.
            //
            // Replacement strategy — preserves the operator's intent:
            //   ""             → "NEWDOMAIN\"
            //   "user"         → "NEWDOMAIN\user"     (came from default cred)
            //   "OLDDOM\"      → "NEWDOMAIN\"         (empty user from prior pick)
            //   "OLDDOM\user"  → "NEWDOMAIN\user"     (switching domains)
            //   "user@foo.com" → unchanged            (operator chose UPN — respect)
            if (host.domain) {
                const shortDomain = host.domain.split('.')[0].toUpperCase();
                const current = (prev.username || '').trim();
                const isUpn = current.includes('@');
                if (!isUpn) {
                    const idx = current.indexOf('\\');
                    const userPart = idx >= 0 ? current.slice(idx + 1) : current;
                    next.username = userPart
                        ? `${shortDomain}\\${userPart}`
                        : `${shortDomain}\\`;
                }
            }
            return next;
        });
        setIsPickerOpen(false);
        setSearch('');
    };

    const pickManual = () => {
        setSelectedAddress(MANUAL_OPTION_VALUE);
        setConnection(prev => ({ ...prev, ip: '' }));
        setIsPickerOpen(false);
        setSearch('');
    };

    const openExternal = () => {
        if (!connection.ip || !connection.username || !connection.password) {
            append('Preencha host, usuário e senha antes de abrir o terminal.', 'error');
            return;
        }

        setBusy(true);
        setStatus('Abrindo terminal externo...');
        append(`Iniciando PowerShell remoto para ${connection.username}@${connection.ip}…`, 'info');

        fetch(`${API_BASE}/tools/terminal/external`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(connection),
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    setStatus('Terminal externo aberto');
                    append('Janela do PowerShell aberta — interaja por lá.', 'info');
                    // Opportunistic background probe: we have admin creds the user
                    // just confirmed work for this host. Fetch MAC/Domain/CurrentUser/
                    // LastBoot/DiskFree (cheap WinRM round-trip) and TV ID (if missing)
                    // and let the backend persist them. Only fires when the operator
                    // picked a known host from the panel — in manual mode we have no
                    // host record to attach the data to.
                    if (selectedHost) {
                        probeHost({
                            targetIp: selectedHost.ip || selectedHost.address,
                            username: connection.username,
                            password: connection.password,
                        }).then((r) => {
                            if (r.ok) {
                                refreshHosts(true).catch(() => undefined);
                            }
                        }).catch(() => undefined);

                        if (!selectedHost.teamviewer_id) {
                            resolveTeamViewerId({
                                targetIp: selectedHost.ip || selectedHost.address,
                                username: connection.username,
                                password: connection.password,
                                persistOnHost: selectedHost.address,
                            }).then((r) => {
                                if (r.ok) refreshHosts(true).catch(() => undefined);
                            }).catch(() => undefined);
                        }
                    }
                } else {
                    setStatus('Erro');
                    append(data.detail || data.message || 'Erro desconhecido.', 'error');
                }
            })
            .catch(err => {
                console.error('Failed to open external terminal', err);
                setStatus('Erro de conexão');
                append('Falha ao contatar o backend.', 'error');
            })
            .finally(() => setBusy(false));
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !busy) openExternal();
    };

    // Label rendered inside the picker button — host name + ip, or hint.
    const pickerLabel = (() => {
        if (isManualMode) return 'Digitar IP/Hostname manualmente';
        if (selectedHost) {
            const name = selectedHost.name || selectedHost.hostname || selectedHost.address;
            return `${name} — ${selectedHost.ip || selectedHost.address}`;
        }
        return 'Selecione um host do painel…';
    })();

    return (
        <div className="h-full flex flex-col space-y-4 min-h-0 p-8">
            <header>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <TerminalIcon /> Terminal Remoto
                </h2>
                <p className="text-zinc-400">
                    Abre uma janela PowerShell nativa autenticada via WinRM. A sessão acontece fora desta janela.
                </p>
            </header>

            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 flex gap-4 items-end">
                <div className="flex-1 grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-4">
                    {/* Host picker */}
                    <div className="space-y-1 relative" ref={pickerRef}>
                        <label className="text-xs text-white">Host</label>
                        <button
                            type="button"
                            onClick={() => setIsPickerOpen(v => !v)}
                            disabled={busy}
                            className={clsx(
                                'w-full bg-zinc-950 border rounded px-3 py-2 text-sm flex items-center justify-between gap-2 transition-colors',
                                isPickerOpen ? 'border-blue-500' : 'border-zinc-700 hover:border-zinc-600',
                                busy && 'opacity-50 cursor-not-allowed'
                            )}
                            aria-haspopup="listbox"
                            aria-expanded={isPickerOpen}
                        >
                            <span className={clsx('truncate text-left', !selectedAddress && 'text-zinc-500')}>
                                {pickerLabel}
                            </span>
                            <ChevronDown size={16} className={clsx('text-zinc-500 shrink-0 transition-transform', isPickerOpen && 'rotate-180')} />
                        </button>
                        {isManualMode && (
                            <input
                                type="text"
                                value={connection.ip}
                                onChange={e => setConnection(prev => ({ ...prev, ip: e.target.value }))}
                                className="mt-2 w-full bg-zinc-950 border border-zinc-700 focus:border-blue-500 focus:outline-none rounded px-3 py-2 text-sm text-zinc-300 placeholder:text-zinc-500"
                                placeholder="192.168.1.10 ou hostname"
                                disabled={busy}
                                onKeyDown={handleKeyDown}
                                autoFocus
                            />
                        )}
                        {isPickerOpen && (
                            <div
                                className="absolute z-20 mt-1 w-full bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl overflow-hidden flex flex-col max-h-80"
                                role="listbox"
                            >
                                <div className="p-2 border-b border-zinc-800 flex items-center gap-2">
                                    <Search size={14} className="text-zinc-500 shrink-0" />
                                    <input
                                        type="text"
                                        value={search}
                                        onChange={e => setSearch(e.target.value)}
                                        placeholder="Buscar por nome, IP ou grupo…"
                                        className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none"
                                        autoFocus
                                    />
                                </div>
                                <button
                                    type="button"
                                    onClick={pickManual}
                                    className="w-full px-3 py-2 text-left text-sm text-blue-400 hover:bg-zinc-800 border-b border-zinc-800 flex items-center gap-2"
                                    role="option"
                                    aria-selected={isManualMode}
                                >
                                    <span className="font-medium">+ Digitar manualmente</span>
                                    <span className="text-zinc-500 text-xs">IP ou hostname não cadastrado</span>
                                </button>
                                <div className="flex-1 overflow-y-auto">
                                    {filteredHosts.length === 0 ? (
                                        <div className="px-3 py-4 text-sm text-zinc-500 text-center">
                                            {hosts.length === 0
                                                ? 'Nenhum host no painel ainda.'
                                                : 'Nenhum host bate com a busca.'}
                                        </div>
                                    ) : (
                                        filteredHosts.map(h => {
                                            const displayName = h.name || h.hostname || h.address;
                                            const ipText = h.ip || h.address;
                                            const isSelected = h.address === selectedAddress;
                                            const online = h.stats?.online ?? h.last_status ?? false;
                                            return (
                                                <button
                                                    key={h.address}
                                                    type="button"
                                                    onClick={() => pickHost(h)}
                                                    className={clsx(
                                                        'w-full px-3 py-2 text-left text-sm flex items-center gap-3 transition-colors',
                                                        isSelected ? 'bg-zinc-800' : 'hover:bg-zinc-800/60'
                                                    )}
                                                    role="option"
                                                    aria-selected={isSelected}
                                                >
                                                    <span
                                                        className={clsx(
                                                            'w-1.5 h-1.5 rounded-full shrink-0',
                                                            h.monitoring === false ? 'bg-zinc-700' : (online ? 'bg-green-500' : 'bg-red-500')
                                                        )}
                                                        aria-hidden="true"
                                                    />
                                                    <div className="min-w-0 flex-1">
                                                        <div className="text-zinc-200 truncate">{displayName}</div>
                                                        <div className="text-xs text-zinc-500 font-mono truncate">
                                                            {ipText}
                                                            {h.group && <span className="ml-2 text-zinc-600">· {h.group}</span>}
                                                        </div>
                                                    </div>
                                                </button>
                                            );
                                        })
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

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
