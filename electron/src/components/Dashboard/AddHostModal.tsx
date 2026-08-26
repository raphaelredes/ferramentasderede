import { X, AlertCircle } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { Host } from '../../types';

interface AddHostModalProps {
    isOpen: boolean;
    onClose: () => void;
    onAdd: (name: string, address: string, mac: string, ports: number[], group: string) => Promise<void>;
    isAdding: boolean;
    existingHosts: Host[];
    existingGroups: string[];
}

export function AddHostModal({ isOpen, onClose, onAdd, isAdding, existingHosts, existingGroups }: AddHostModalProps) {
    const [name, setName] = useState('');
    const [address, setAddress] = useState('');
    const [group, setGroup] = useState('');
    const [mac, setMac] = useState('');
    const [portsStr, setPortsStr] = useState('');
    // Field-level errors so screen readers (and sighted users) can tell which
    // input was rejected. `generalError` is for the duplicate-host banner.
    const [addressError, setAddressError] = useState<string | null>(null);
    const [macError, setMacError] = useState<string | null>(null);
    const [generalError, setGeneralError] = useState<string | null>(null);

    const [showSuggestions, setShowSuggestions] = useState(false);
    const wrapperRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setShowSuggestions(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [wrapperRef]);

    // IPv4 strict: 4 octets each 0..255. Hostname: letters/digits/dot/hyphen,
    // first char alphanumeric, max 253 chars. Same shape backend uses.
    const isValidAddress = (v: string): boolean => {
        const trimmed = v.trim();
        if (!trimmed || trimmed.length > 253) return false;
        const ipMatch = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(trimmed);
        if (ipMatch) {
            return ipMatch.slice(1, 5).every(o => {
                const n = parseInt(o, 10);
                return n >= 0 && n <= 255;
            });
        }
        return /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(trimmed);
    };

    // MAC: optional. If provided, must be 6 hex pairs with `:` or `-` or
    // none. Reject anything that wouldn't survive WoL's wakeonlan.
    const isValidMac = (v: string): boolean => {
        const t = v.trim();
        if (!t) return true;
        return /^([0-9A-Fa-f]{2}([:-])?){5}[0-9A-Fa-f]{2}$/.test(t);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        // Block re-entry: a fast double-Enter could fire before the parent
        // sets isAdding=true, so guard locally too.
        if (isAdding) return;
        setAddressError(null);
        setMacError(null);
        setGeneralError(null);

        const cleanAddress = address.trim();
        if (!isValidAddress(cleanAddress)) {
            setAddressError('Endereço inválido. Use IPv4 ou hostname (letras, dígitos, ponto, hífen).');
            return;
        }
        if (!isValidMac(mac)) {
            setMacError('MAC inválido. Use o formato 00:11:22:33:44:55 (ou deixe vazio).');
            return;
        }

        // Check for duplicates
        const isDuplicate = existingHosts.some(h =>
            h.address?.toLowerCase() === cleanAddress.toLowerCase() ||
            (h.hostname && h.hostname.toLowerCase() === cleanAddress.toLowerCase()) ||
            (h.ip && h.ip === cleanAddress)
        );

        if (isDuplicate) {
            setGeneralError('Este host já existe no painel (IP ou Hostname duplicado).');
            return;
        }

        const ports = portsStr.split(',')
            .map(p => parseInt(p.trim()))
            .filter(p => !isNaN(p) && p > 0 && p <= 65535);

        await onAdd(name.trim(), cleanAddress, mac.trim(), ports, group.trim());
        setName('');
        setAddress('');
        setGroup('');
        setMac('');
        setPortsStr('');
        setAddressError(null);
        setMacError(null);
        setGeneralError(null);
    };

    const filteredGroups = existingGroups.filter(g =>
        g.toLowerCase().includes(group.toLowerCase())
    );

    // ESC closes — basic accessibility hygiene for any modal.
    useEffect(() => {
        if (!isOpen) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={onClose}
            role="presentation"
        >
            <div
                className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md max-h-[85vh] sm:max-h-[90vh] overflow-y-auto custom-scrollbar p-6 shadow-2xl my-auto animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="addhost-title"
            >
                <div className="flex justify-between items-center mb-4">
                    <h3 id="addhost-title" className="text-xl font-bold text-white">Adicionar Novo Host</h3>
                    <button
                        onClick={onClose}
                        className="text-zinc-400 hover:text-white"
                        aria-label="Fechar"
                    >
                        <X size={20} />
                    </button>
                </div>

                {generalError && (
                    <div role="alert" className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                        <AlertCircle size={16} aria-hidden="true" />
                        {generalError}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                    <div>
                        <label htmlFor="addhost-name" className="block text-sm font-medium text-zinc-400 mb-1">Apelido</label>
                        <input
                            id="addhost-name"
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${name ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="Opcional (será resolvido se vazio)"
                        />
                    </div>
                    <div>
                        <label htmlFor="addhost-address" className="block text-sm font-medium text-zinc-400 mb-1">Endereço IP / Hostname</label>
                        <input
                            id="addhost-address"
                            type="text"
                            required
                            value={address}
                            onChange={e => {
                                setAddress(e.target.value);
                                setAddressError(null);
                                setGeneralError(null);
                            }}
                            aria-invalid={!!addressError}
                            aria-describedby={addressError ? 'addhost-address-error' : 'addhost-address-hint'}
                            className={`w-full bg-zinc-950 border rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${address ? 'text-white' : 'text-zinc-500'} ${addressError ? 'border-red-500/60' : 'border-zinc-700'}`}
                            placeholder="ex: 192.168.1.10"
                        />
                        {addressError ? (
                            <p id="addhost-address-error" role="alert" className="mt-1 text-xs text-red-400">{addressError}</p>
                        ) : (
                            <p id="addhost-address-hint" className="mt-1 text-xs text-zinc-600">IPv4 ou hostname (letras, dígitos, ponto, hífen).</p>
                        )}
                    </div>
                    <div>
                        <label htmlFor="addhost-mac" className="block text-sm font-medium text-zinc-400 mb-1">Endereço MAC (Para WoL)</label>
                        <input
                            id="addhost-mac"
                            type="text"
                            value={mac}
                            onChange={e => {
                                setMac(e.target.value);
                                setMacError(null);
                            }}
                            aria-invalid={!!macError}
                            aria-describedby={macError ? 'addhost-mac-error' : 'addhost-mac-hint'}
                            className={`w-full bg-zinc-950 border rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${mac ? 'text-white' : 'text-zinc-500'} ${macError ? 'border-red-500/60' : 'border-zinc-700'}`}
                            placeholder="ex: 00:11:22:33:44:55"
                        />
                        {macError ? (
                            <p id="addhost-mac-error" role="alert" className="mt-1 text-xs text-red-400">{macError}</p>
                        ) : (
                            <p id="addhost-mac-hint" className="mt-1 text-xs text-zinc-600">Opcional. Formato 6 hex pares (`:` ou `-`).</p>
                        )}
                    </div>
                    <div className="relative" ref={wrapperRef}>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Grupo (Opcional)</label>
                        <input
                            type="text"
                            value={group}
                            onChange={e => {
                                setGroup(e.target.value);
                                setShowSuggestions(true);
                            }}
                            onFocus={() => setShowSuggestions(true)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${group ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="ex: Servidores, Impressoras"
                        />
                        {showSuggestions && filteredGroups.length > 0 && (
                            <div className="absolute z-10 w-full mt-1 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl max-h-40 overflow-y-auto">
                                {filteredGroups.map(g => (
                                    <div
                                        key={g}
                                        className="px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 cursor-pointer"
                                        onClick={() => {
                                            setGroup(g);
                                            setShowSuggestions(false);
                                        }}
                                    >
                                        {g}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-1">Monitorar Portas (Opcional)</label>
                        <input
                            type="text"
                            value={portsStr}
                            onChange={e => setPortsStr(e.target.value)}
                            className={`w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder:text-zinc-500 ${portsStr ? 'text-white' : 'text-zinc-500'}`}
                            placeholder="ex: 80, 443, 3389"
                        />
                    </div>
                    <div className="flex justify-end gap-2 mt-6">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-zinc-400 hover:text-white transition-colors"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            disabled={isAdding}
                            className="bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed text-blue-400 border border-blue-900/30 hover:border-blue-500/50 px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                        >
                            {isAdding && <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400" />}
                            Adicionar
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
