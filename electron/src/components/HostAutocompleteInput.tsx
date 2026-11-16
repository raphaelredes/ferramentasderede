import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { clsx } from 'clsx';
import { ChevronRight } from 'lucide-react';
import { useMonitoring } from '../contexts/MonitoringContext';
import { Host } from '../types';
import { ipForHost } from '../utils/ipForHost';

export interface HostAutocompleteInputProps {
    value: string;
    onChange: (value: string) => void;
    onSelectHost?: (host: Host, selectedValue: string) => void;
    placeholder?: string;
    className?: string;
    disabled?: boolean;
    autoFocus?: boolean;
    id?: string;
    name?: string;
    required?: boolean;
    title?: string;
    'aria-label'?: string;
    onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
    onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
    onFocus?: (e: React.FocusEvent<HTMLInputElement>) => void;
    /**
     * When true, supports comma/space-separated multi-host targets
     * (e.g. for ConnectivityDiagPanel: "host1, 10.200.5.113").
     */
    multi?: boolean;
    /**
     * Preferred value to insert on row selection ('auto' | 'ip' | 'hostname' | 'address' | 'url')
     */
    preferredFill?: 'auto' | 'ip' | 'hostname' | 'address' | 'url';
    /**
     * Optional wrapper class name
     */
    wrapperClassName?: string;
    /**
     * Optional custom hosts list override
     */
    customHosts?: Host[];
}

const IPV4_SHAPE = /^\d{1,3}(\.\d{0,3}){0,3}$/;

export function HostAutocompleteInput({
    value,
    onChange,
    onSelectHost,
    placeholder,
    className,
    disabled = false,
    autoFocus = false,
    id,
    name,
    required,
    title,
    'aria-label': ariaLabel,
    onKeyDown,
    onBlur,
    onFocus,
    multi = false,
    preferredFill = 'auto',
    wrapperClassName,
    customHosts,
}: HostAutocompleteInputProps) {
    const monitoringContext = useMonitoring();
    const hosts = customHosts || monitoringContext?.hosts || [];

    const [isOpen, setIsOpen] = useState(false);
    const [highlightedIndex, setHighlightedIndex] = useState(-1);
    const wrapperRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Splits multi-target input to find active query token
    const getActiveToken = useCallback((val: string): { prefix: string; query: string } => {
        if (!multi) {
            return { prefix: '', query: val.trim() };
        }
        const lastDelim = Math.max(val.lastIndexOf(','), val.lastIndexOf(';'));
        if (lastDelim === -1) {
            return { prefix: '', query: val.trim() };
        }
        const prefix = val.slice(0, lastDelim + 1) + ' ';
        const query = val.slice(lastDelim + 1).trim();
        return { prefix, query };
    }, [multi]);

    const { query: activeQuery } = useMemo(() => getActiveToken(value), [getActiveToken, value]);

    // Filter hosts responsively
    const filteredHosts = useMemo(() => {
        if (!hosts || hosts.length === 0) return [];
        const q = activeQuery.toLowerCase();

        if (!q) {
            // When query is empty, show up to 6 configured hosts, online first
            return [...hosts]
                .sort((a, b) => {
                    const aOnline = a.stats?.online ?? a.last_status ?? false;
                    const bOnline = b.stats?.online ?? b.last_status ?? false;
                    if (aOnline && !bOnline) return -1;
                    if (!aOnline && bOnline) return 1;
                    return (a.name || a.address).localeCompare(b.name || b.address);
                })
                .slice(0, 6);
        }

        const matches: { host: Host; score: number }[] = [];
        for (const h of hosts) {
            const hName = (h.name || '').toLowerCase();
            const hHostname = (h.hostname || '').toLowerCase();
            const hAddress = (h.address || '').toLowerCase();
            const hIp = (ipForHost(h) || h.ip || '').toLowerCase();
            const hGroup = (h.group || '').toLowerCase();

            let score = 0;
            if (hName === q || hHostname === q || hAddress === q || hIp === q) score += 100;
            else if (hName.startsWith(q) || hHostname.startsWith(q) || hAddress.startsWith(q) || hIp.startsWith(q)) score += 50;
            else if (hName.includes(q) || hHostname.includes(q) || hAddress.includes(q) || hIp.includes(q)) score += 20;
            else if (hGroup.includes(q)) score += 10;

            if (score > 0) {
                matches.push({ host: h, score });
            }
        }

        return matches
            .sort((a, b) => b.score - a.score)
            .slice(0, 8)
            .map(m => m.host);
    }, [hosts, activeQuery]);

    // Outside click listener
    useEffect(() => {
        const handleOutsideClick = (e: MouseEvent) => {
            if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleOutsideClick);
        return () => document.removeEventListener('mousedown', handleOutsideClick);
    }, []);

    // Resolves best string to insert
    const resolveValueForHost = useCallback((host: Host, forceType?: 'ip' | 'hostname' | 'address'): string => {
        const resolvedIp = ipForHost(host) || host.ip || (host.address && /^\d{1,3}(\.\d{1,3}){3}$/.test(host.address) ? host.address : null);
        const resolvedHostname = host.hostname || (host.address && !/^\d{1,3}(\.\d{1,3}){3}$/.test(host.address) ? host.address : host.name);

        if (forceType === 'ip') return resolvedIp || host.address;
        if (forceType === 'hostname') return resolvedHostname || host.address;
        if (forceType === 'address') return host.address;

        if (preferredFill === 'ip') return resolvedIp || host.address;
        if (preferredFill === 'hostname') return resolvedHostname || host.address;
        if (preferredFill === 'address') return host.address;
        if (preferredFill === 'url') {
            const hostPart = resolvedHostname || resolvedIp || host.address;
            if (value.startsWith('https://')) return `https://${hostPart}`;
            if (value.startsWith('http://')) return `http://${hostPart}`;
            return `http://${hostPart}`;
        }

        // Auto mode: if user query looks like numbers/dots, prefer IP; otherwise prefer Hostname/Address
        if (IPV4_SHAPE.test(activeQuery) && resolvedIp) {
            return resolvedIp;
        }
        return resolvedHostname || resolvedIp || host.address;
    }, [activeQuery, preferredFill, value]);

    // Inserts the selected host value into the input
    const selectHost = useCallback((host: Host, forceType?: 'ip' | 'hostname' | 'address') => {
        const chosenVal = resolveValueForHost(host, forceType);

        if (!multi) {
            onChange(chosenVal);
        } else {
            const { prefix } = getActiveToken(value);
            const newValue = `${prefix}${chosenVal}, `;
            onChange(newValue);
        }

        onSelectHost?.(host, chosenVal);
        setIsOpen(false);
        setHighlightedIndex(-1);
        inputRef.current?.focus();
    }, [getActiveToken, multi, onChange, onSelectHost, resolveValueForHost, value]);

    const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (isOpen && filteredHosts.length > 0) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setHighlightedIndex(prev => (prev < filteredHosts.length - 1 ? prev + 1 : 0));
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setHighlightedIndex(prev => (prev > 0 ? prev - 1 : filteredHosts.length - 1));
                return;
            }
            if (e.key === 'Enter') {
                if (highlightedIndex >= 0 && highlightedIndex < filteredHosts.length) {
                    e.preventDefault();
                    selectHost(filteredHosts[highlightedIndex]);
                    return;
                }
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                setIsOpen(false);
                setHighlightedIndex(-1);
                return;
            }
        }
        onKeyDown?.(e);
    };

    return (
        <div ref={wrapperRef} className={clsx('relative w-full', wrapperClassName)}>
            <input
                ref={inputRef}
                id={id}
                name={name}
                type="text"
                value={value}
                required={required}
                title={title}
                aria-label={ariaLabel}
                onChange={e => {
                    onChange(e.target.value);
                    if (!isOpen) setIsOpen(true);
                }}
                onFocus={e => {
                    setIsOpen(true);
                    onFocus?.(e);
                }}
                onBlur={e => {
                    onBlur?.(e);
                }}
                onKeyDown={handleInputKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                autoFocus={autoFocus}
                className={className}
                autoComplete="off"
                spellCheck={false}
            />

            {isOpen && !disabled && filteredHosts.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-64 animate-in fade-in slide-in-from-top-1 duration-150">
                    <div className="px-3 py-1.5 bg-zinc-950/80 border-b border-zinc-800 text-[10px] font-semibold uppercase tracking-wider text-zinc-400 flex items-center justify-between">
                        <span>Hosts do Painel ({filteredHosts.length})</span>
                        <span className="text-zinc-500 font-normal">Enter ou clique para preencher</span>
                    </div>

                    <div className="overflow-y-auto custom-scrollbar divide-y divide-zinc-800/40">
                        {filteredHosts.map((h, idx) => {
                                const isHighlighted = idx === highlightedIndex;
                                const isOnline = h.stats?.online ?? h.last_status ?? false;
                                const hostIp = ipForHost(h) || h.ip || (h.address && /^\d{1,3}(\.\d{1,3}){3}$/.test(h.address) ? h.address : null);
                                const hostname = h.hostname || (h.address && !/^\d{1,3}(\.\d{1,3}){3}$/.test(h.address) ? h.address : null);

                                return (
                                    <div
                                        key={h.address || idx}
                                        onMouseDown={e => {
                                            // onMouseDown instead of onClick prevents input blur from closing before selection
                                            e.preventDefault();
                                            selectHost(h);
                                        }}
                                        onMouseEnter={() => setHighlightedIndex(idx)}
                                        className={clsx(
                                            'px-3 py-2 flex items-center justify-between gap-2 cursor-pointer transition-colors text-xs select-none',
                                            isHighlighted ? 'bg-zinc-800 text-white' : 'hover:bg-zinc-800/60 text-zinc-200'
                                        )}
                                    >
                                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                                            <span
                                                className={clsx(
                                                    'w-2 h-2 rounded-full shrink-0',
                                                    h.monitoring === false
                                                        ? 'bg-zinc-600'
                                                        : isOnline
                                                        ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50'
                                                        : 'bg-rose-500'
                                                )}
                                                title={isOnline ? 'Online' : 'Offline'}
                                            />
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-semibold text-zinc-100 truncate">
                                                        {h.name || hostname || h.address}
                                                    </span>
                                                    {h.group && (
                                                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400 border border-zinc-700 shrink-0">
                                                            {h.group}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-2 text-[11px] text-zinc-400 font-mono truncate">
                                                    {hostIp && <span>IP: {hostIp}</span>}
                                                    {hostname && hostname !== h.name && (
                                                        <span className="text-zinc-500 truncate">({hostname})</span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Quick Insert Actions */}
                                        <div className="flex items-center gap-1.5 shrink-0" onClick={e => e.stopPropagation()}>
                                            {hostIp && (
                                                <button
                                                    type="button"
                                                    onMouseDown={e => {
                                                        e.preventDefault();
                                                        selectHost(h, 'ip');
                                                    }}
                                                    className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-950/80 hover:bg-blue-600/30 text-blue-300 hover:text-white border border-zinc-700/80 hover:border-blue-500/50 transition-colors"
                                                    title={`Inserir endereço IP: ${hostIp}`}
                                                >
                                                    IP
                                                </button>
                                            )}
                                            {hostname && (
                                                <button
                                                    type="button"
                                                    onMouseDown={e => {
                                                        e.preventDefault();
                                                        selectHost(h, 'hostname');
                                                    }}
                                                    className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-950/80 hover:bg-emerald-600/30 text-emerald-300 hover:text-white border border-zinc-700/80 hover:border-emerald-500/50 transition-colors"
                                                    title={`Inserir Hostname: ${hostname}`}
                                                >
                                                    Nome
                                                </button>
                                            )}
                                            <ChevronRight size={13} className="text-zinc-500" />
                                        </div>
                                    </div>
                                );
                            })
                        }
                    </div>
                </div>
            )}
        </div>
    );
}
