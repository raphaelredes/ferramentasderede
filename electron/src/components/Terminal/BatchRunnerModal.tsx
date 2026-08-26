import { useState, useEffect } from 'react';
import { X, Play, CheckCircle, XCircle, Terminal as TerminalIcon } from 'lucide-react';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { Host } from '../../types';

interface BatchRunnerModalProps {
    isOpen: boolean;
    onClose: () => void;
    hosts: Host[];
}

interface BatchResult {
    host: string;
    name: string;
    success: boolean;
    status_code: number;
    stdout: string;
    stderr: string;
    elapsed_ms: number;
}

export function BatchRunnerModal({ isOpen, onClose, hosts }: BatchRunnerModalProps) {
    const { showToast } = useToast();
    const [selectedIps, setSelectedIps] = useState<string[]>([]);
    const [command, setCommand] = useState('Get-Service -Name Spooler');
    const [running, setRunning] = useState(false);
    const [results, setResults] = useState<BatchResult[]>([]);
    const [activeResultTab, setActiveResultTab] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && hosts.length > 0 && selectedIps.length === 0) {
            setSelectedIps(hosts.slice(0, 5).map(h => h.address));
        }
    }, [isOpen, hosts]);

    if (!isOpen) return null;

    const toggleSelectAll = () => {
        if (selectedIps.length === hosts.length) {
            setSelectedIps([]);
        } else {
            setSelectedIps(hosts.map(h => h.address));
        }
    };

    const toggleSelectIp = (ip: string) => {
        if (selectedIps.includes(ip)) {
            setSelectedIps(selectedIps.filter(i => i !== ip));
        } else {
            setSelectedIps([...selectedIps, ip]);
        }
    };

    const handleRunBatch = async () => {
        if (!command.trim() || selectedIps.length === 0) {
            showToast('Selecione pelo menos um host e informe o comando.', 'warning');
            return;
        }

        setRunning(true);
        setResults([]);
        setActiveResultTab(null);

        const targets = hosts
            .filter(h => selectedIps.includes(h.address))
            .map(h => ({
                id: (h as any).id ?? null,
                ip: h.address,
                name: h.name
            }));

        try {
            const res = await fetch(`${API_BASE}/batch/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    command: command.trim(),
                    targets,
                    max_workers: 10,
                    timeout: 30
                })
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setResults(data.results || []);
            if (data.results && data.results.length > 0) {
                setActiveResultTab(data.results[0].host);
            }
            showToast(`Execução em lote concluída: ${data.success_count} sucesso(s), ${data.failed_count} falha(s).`, 'info');
        } catch (err: any) {
            showToast(`Erro na execução em lote: ${err.message}`, 'error');
        } finally {
            setRunning(false);
        }
    };

    const activeResult = results.find(r => r.host === activeResultTab);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-5xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950/50">
                    <div className="flex items-center gap-3">
                        <TerminalIcon className="text-blue-400" size={22} />
                        <div>
                            <h2 className="text-base font-semibold text-zinc-100">Multi-Host Action Runner (WinRM em Lote)</h2>
                            <p className="text-xs text-zinc-400">Executa scripts concorrentes em múltiplos servidores utilizando credenciais seguras</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800">
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6 overflow-y-auto">
                    {/* Left: Target Selection */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-zinc-300">Hosts Alvo ({selectedIps.length}/{hosts.length})</span>
                            <button onClick={toggleSelectAll} className="text-blue-400 hover:underline">
                                {selectedIps.length === hosts.length ? 'Desmarcar Todos' : 'Selecionar Todos'}
                            </button>
                        </div>
                        <div className="max-h-[220px] overflow-y-auto border border-zinc-800 rounded-lg p-2 bg-zinc-950 space-y-1">
                            {hosts.map(h => (
                                <label key={h.address} className="flex items-center gap-2 p-1.5 hover:bg-zinc-900 rounded text-xs cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={selectedIps.includes(h.address)}
                                        onChange={() => toggleSelectIp(h.address)}
                                        className="rounded border-zinc-700 text-blue-600 focus:ring-0"
                                    />
                                    <span className="font-medium text-zinc-200 truncate">{h.name || h.address}</span>
                                    <span className="text-zinc-500 font-mono text-[11px] ml-auto">{h.address}</span>
                                </label>
                            ))}
                        </div>

                        {/* Command Editor */}
                        <div className="space-y-1">
                            <label className="text-xs font-semibold text-zinc-300">Script / Comando PowerShell</label>
                            <textarea
                                value={command}
                                onChange={e => setCommand(e.target.value)}
                                rows={4}
                                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none focus:border-blue-500 resize-none"
                                placeholder="Digite o script PowerShell a executar em lote..."
                            />
                        </div>

                        <button
                            onClick={handleRunBatch}
                            disabled={running || selectedIps.length === 0}
                            className="w-full flex items-center justify-center gap-2 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow transition-colors"
                        >
                            <Play size={14} />
                            {running ? 'Executando em Paralelo...' : `Executar em ${selectedIps.length} Host(s)`}
                        </button>
                    </div>

                    {/* Right: Results & Console Output */}
                    <div className="md:col-span-2 flex flex-col space-y-3">
                        <div className="text-xs font-semibold text-zinc-300">Resultados da Execução</div>
                        {results.length > 0 ? (
                            <div className="flex-1 flex flex-col border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950">
                                {/* Result Host Tabs */}
                                <div className="flex border-b border-zinc-800 overflow-x-auto bg-zinc-900/60 p-1 gap-1 text-xs">
                                    {results.map(r => (
                                        <button
                                            key={r.host}
                                            onClick={() => setActiveResultTab(r.host)}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono transition-colors ${activeResultTab === r.host ? 'bg-zinc-800 text-white font-semibold' : 'text-zinc-400 hover:text-zinc-200'}`}
                                        >
                                            {r.success ? (
                                                <CheckCircle size={14} className="text-emerald-400" />
                                            ) : (
                                                <XCircle size={14} className="text-rose-400" />
                                            )}
                                            <span>{r.name || r.host}</span>
                                            <span className="text-[10px] text-zinc-500">({r.elapsed_ms}ms)</span>
                                        </button>
                                    ))}
                                </div>

                                {/* Active Tab Console Output */}
                                <div className="p-4 flex-1 font-mono text-xs overflow-y-auto max-h-[340px] text-zinc-300 whitespace-pre-wrap select-text">
                                    {activeResult ? (
                                        activeResult.stdout || activeResult.stderr || '(Nenhum retorno recebido)'
                                    ) : (
                                        'Selecione um host acima para visualizar a saída.'
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className="flex-1 flex items-center justify-center border border-zinc-800 border-dashed rounded-xl p-8 text-xs text-zinc-500">
                                Nenhum lote executado ainda. Selecione os alvos e clique em Executar.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
