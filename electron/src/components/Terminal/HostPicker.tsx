import { useRef, useEffect } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { clsx } from 'clsx';
import { Host } from '../../types';

export const MANUAL_OPTION_VALUE = '__manual__';

interface HostPickerProps {
    hosts: Host[];
    filteredHosts: Host[];
    selectedAddress: string;
    selectedHost: Host | null;
    isPickerOpen: boolean;
    setIsPickerOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
    search: string;
    setSearch: (s: string) => void;
    busy: boolean;
    pickHost: (host: Host) => void;
    pickManual: () => void;
}

export function HostPicker({
    hosts,
    filteredHosts,
    selectedAddress,
    selectedHost,
    isPickerOpen,
    setIsPickerOpen,
    search,
    setSearch,
    busy,
    pickHost,
    pickManual
}: HostPickerProps) {
    const pickerRef = useRef<HTMLDivElement>(null);
    const isManualMode = selectedAddress === MANUAL_OPTION_VALUE;

    useEffect(() => {
        if (!isPickerOpen) return;
        const onDown = (e: MouseEvent) => {
            if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
                setIsPickerOpen(false);
            }
        };
        document.addEventListener('mousedown', onDown);
        return () => document.removeEventListener('mousedown', onDown);
    }, [isPickerOpen, setIsPickerOpen]);

    const pickerLabel = (() => {
        if (isManualMode) return 'Digitar IP/Hostname manualmente';
        if (selectedHost) {
            const name = selectedHost.name || selectedHost.hostname || selectedHost.address;
            return `${name} — ${selectedHost.ip || selectedHost.address}`;
        }
        return 'Selecione um host do painel…';
    })();

    return (
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
    );
}
