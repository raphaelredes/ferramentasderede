import { Search, Filter, ArrowUpDown } from 'lucide-react';

interface FilterBarProps {
    searchTerm: string;
    setSearchTerm: (term: string) => void;
    filterStatus: 'all' | 'monitored' | 'unmonitored';
    setFilterStatus: (status: 'all' | 'monitored' | 'unmonitored') => void;
    sortBy: 'name' | 'status' | 'ip' | 'manual';
    setSortBy: (sort: 'name' | 'status' | 'ip' | 'manual') => void;
}

export function FilterBar({
    searchTerm,
    setSearchTerm,
    filterStatus,
    setFilterStatus,
    sortBy,
    setSortBy
}: FilterBarProps) {
    return (
        <div className="flex flex-col md:flex-row gap-4 mb-6">
            <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={20} />
                <input
                    type="text"
                    placeholder="Buscar por nome, hostname ou IP..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full bg-zinc-900/50 border border-zinc-800 text-white pl-10 pr-4 py-2 rounded-lg focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 placeholder-zinc-600"
                />
            </div>
            <div className="flex gap-2">
                <div className="relative">
                    <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                    <select
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value as 'all' | 'monitored' | 'unmonitored')}
                        className="bg-zinc-900/50 border border-zinc-800 text-zinc-300 pl-9 pr-8 py-2 rounded-lg focus:outline-none focus:border-blue-500/50 appearance-none cursor-pointer hover:bg-zinc-800/50 transition-colors"
                    >
                        <option value="all">Todos os Status</option>
                        <option value="monitored">Monitorado</option>
                        <option value="unmonitored">Não monitorado</option>
                    </select>
                </div>
                <div className="relative">
                    <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value as 'name' | 'status' | 'ip' | 'manual')}
                        className="bg-zinc-900/50 border border-zinc-800 text-zinc-300 pl-9 pr-8 py-2 rounded-lg focus:outline-none focus:border-blue-500/50 appearance-none cursor-pointer hover:bg-zinc-800/50 transition-colors"
                    >
                        <option value="manual">Manual (Arrastar)</option>
                        <option value="name">Nome (A-Z)</option>
                        <option value="status">Status (Online)</option>
                        <option value="ip">Endereço IP</option>
                    </select>
                </div>
            </div>
        </div>
    );
}
