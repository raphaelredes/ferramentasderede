import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Monitor } from 'lucide-react';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
    DragOverlay
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    rectSortingStrategy
} from '@dnd-kit/sortable';
import { DashboardHeader } from '../components/Dashboard/DashboardHeader';
import { FilterBar } from '../components/Dashboard/FilterBar';
import { HostCard } from '../components/Dashboard/HostCard';
import { SortableHostCard } from '../components/Dashboard/SortableHostCard';
import { AddHostModal } from '../components/Dashboard/AddHostModal';
import { DeleteHostModal } from '../components/Dashboard/DeleteHostModal';
import { TrashDroppable } from '../components/Dashboard/TrashDroppable';
import { SetGroupModal } from '../components/Dashboard/SetGroupModal';
import { Host } from '../types';
import { useMonitoring } from '../contexts/MonitoringContext';
import { useHostActions } from '../hooks/useHostActions';
import { useToast } from '../contexts/ToastContext';
import { HelpButton } from '../components/HelpButton';
import { HostListSkeleton } from '../components/Dashboard/HostListSkeleton';

export default function Dashboard() {
    const {
        hosts,
        isLoading: loading,
        refreshHosts: fetchHosts,
        uniqueGroups,
        stats: globalStats
    } = useMonitoring();

    const { showToast } = useToast();
    const {
        isAddingHost,
        isDeleting,
        addHost,
        deleteHost,
        updateHost
    } = useHostActions();

    const navigate = useNavigate();

    // Modal State
    const [isAddHostModalOpen, setIsAddHostModalOpen] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [hostToDelete, setHostToDelete] = useState<Host | null>(null);
    const [isSetGroupModalOpen, setIsSetGroupModalOpen] = useState(false);
    const [hostToSetGroup, setHostToSetGroup] = useState<Host | null>(null);

    // Context Menu State
    const [activeContextMenu, setActiveContextMenu] = useState<string | null>(null);

    // Search, Filter, Sort State
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState<'all' | 'monitored' | 'unmonitored'>('all');
    const [sortBy, setSortBy] = useState<'name' | 'status' | 'ip' | 'manual'>('manual');
    const [hostOrder, setHostOrder] = useState<string[]>(() => {
        const saved = localStorage.getItem('hostOrder');
        return saved ? JSON.parse(saved) : [];
    });

    const [activeGroupTab, setActiveGroupTab] = useState('all');

    // Handlers
    const onAddHost = async (name: string, address: string, mac: string, ports: number[], group: string) => {
        const success = await addHost(name, address, mac, ports, group);
        if (success) {
            await fetchHosts();
            setIsAddHostModalOpen(false);
        }
    };

    const handleDeleteClick = (host: Host) => {
        setHostToDelete(host);
        setIsDeleteModalOpen(true);
    };

    const onConfirmDeleteHost = async () => {
        if (!hostToDelete) return;
        const success = await deleteHost(hostToDelete.address);
        if (success) {
            await fetchHosts();
            setIsDeleteModalOpen(false);
            setHostToDelete(null);
            showToast('Host removido com sucesso', 'success');
        } else {
            showToast('Erro ao remover host', 'error');
        }
    };

    const handleSetGroupClick = (host: Host) => {
        setHostToSetGroup(host);
        setIsSetGroupModalOpen(true);
    };

    const onConfirmSetGroup = async (group: string) => {
        if (!hostToSetGroup) return;
        const success = await updateHost(hostToSetGroup.address, { group });
        if (success) {
            await fetchHosts();
            showToast('Grupo atualizado com sucesso', 'success');
        } else {
            showToast('Erro ao atualizar grupo', 'error');
        }
    };

    const handleToggleMonitoring = useCallback((e: React.MouseEvent, host: Host) => {
        e.stopPropagation();
        const newStatus = host.monitoring === false;

        fetch(`http://127.0.0.1:8000/hosts/${host.address}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monitoring: newStatus })
        }).then(() => {
            fetchHosts();
        }).catch(err => {
            console.error("Failed to toggle monitoring:", err);
            showToast('Erro ao atualizar monitoramento', 'error');
        });
    }, [fetchHosts, showToast]);

    const setDetailsHostCallback = useCallback((_host: Host) => {
        // No-op, kept for prop compatibility if needed, but we navigate now
    }, []);

    const setIsDetailsModalOpenCallback = useCallback((_isOpen: boolean) => {
        // No-op
    }, []);

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const [activeId, setActiveId] = useState<string | null>(null);

    const handleDragEndDnd = (event: DragEndEvent) => {
        const { active, over } = event;

        setActiveId(null);

        if (!over) return;

        // Handle drop on trash
        if (over.id === 'trash-droppable') {
            const host = hosts.find(h => h.address === active.id);
            if (host) {
                handleDeleteClick(host);
            }
            return;
        }

        if (active.id !== over.id) {
            const oldIndex = hosts.findIndex((host) => host.address === active.id);
            const newIndex = hosts.findIndex((host) => host.address === over.id);

            const newHosts = arrayMove(hosts, oldIndex, newIndex);

            const newOrder = newHosts.map(h => h.address);
            setHostOrder(newOrder);
            localStorage.setItem('hostOrder', JSON.stringify(newOrder));

            if (sortBy !== 'manual') {
                setSortBy('manual');
            }
        }
    };

    // Filter and Sort Logic
    const filteredHosts = hosts.filter(host => {
        const matchesSearch =
            (host.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
            host.address.includes(searchTerm) ||
            (host.hostname && host.hostname.toLowerCase().includes(searchTerm.toLowerCase()));

        const matchesStatus =
            filterStatus === 'all' ? true :
                filterStatus === 'monitored' ? host.monitoring :
                    !host.monitoring;

        const matchesGroup =
            activeGroupTab === 'all' ? true :
                activeGroupTab === 'ungrouped' ? !host.group :
                    host.group === activeGroupTab;

        return matchesSearch && matchesStatus && matchesGroup;
    }).sort((a, b) => {
        if (sortBy === 'manual') {
            const indexA = hostOrder.indexOf(a.address);
            const indexB = hostOrder.indexOf(b.address);
            if (indexA === -1 && indexB === -1) return 0;
            if (indexA === -1) return 1;
            if (indexB === -1) return -1;
            return indexA - indexB;
        }

        if (sortBy === 'name') return a.name.localeCompare(b.name);
        if (sortBy === 'ip') {
            const ipA = a.address.split('.').map(Number);
            const ipB = b.address.split('.').map(Number);
            for (let i = 0; i < 4; i++) {
                if (ipA[i] < ipB[i]) return -1;
                if (ipA[i] > ipB[i]) return 1;
            }
            return 0;
        }
        if (sortBy === 'status') {
            // Online first
            const isOnlineA = a.stats?.online ?? a.last_status ?? false;
            const isOnlineB = b.stats?.online ?? b.last_status ?? false;
            if (isOnlineA && !isOnlineB) return -1;
            if (!isOnlineA && isOnlineB) return 1;
            return 0;
        }
        return 0;
    });

    return (
        <div className="p-8 max-w-[1600px] mx-auto">
            <DashboardHeader
                onAddHost={() => setIsAddHostModalOpen(true)}
                totalHosts={hosts.length}
                onlineHosts={globalStats.online}
            />

            <div className="flex gap-2 border-b border-zinc-800 mb-4 overflow-x-auto custom-scrollbar pb-2">
                <button
                    onClick={() => setActiveGroupTab('all')}
                    className={`px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap ${activeGroupTab === 'all' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-zinc-400 hover:text-white'}`}
                >
                    Todos
                </button>
                <button
                    onClick={() => setActiveGroupTab('ungrouped')}
                    className={`px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap ${activeGroupTab === 'ungrouped' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-zinc-400 hover:text-white'}`}
                >
                    Sem Grupo
                </button>
                {uniqueGroups.map(group => (
                    <button
                        key={group}
                        onClick={() => setActiveGroupTab(group)}
                        className={`px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap ${activeGroupTab === group ? 'text-blue-400 border-b-2 border-blue-400' : 'text-zinc-400 hover:text-white'}`}
                    >
                        {group}
                    </button>
                ))}
                <div className="ml-auto flex items-center">
                    <HelpButton title="Grupos e Filtros" description="Use as abas para filtrar hosts por grupo. 'Sem Grupo' mostra hosts que ainda não foram categorizados." />
                </div>
            </div>

            <FilterBar
                searchTerm={searchTerm}
                setSearchTerm={setSearchTerm}
                filterStatus={filterStatus}
                setFilterStatus={setFilterStatus}
                sortBy={sortBy}
                setSortBy={setSortBy}
            />

            {
                loading && hosts.length === 0 ? (
                    <HostListSkeleton />
                ) : filteredHosts.length === 0 ? (
                    <div className="text-center py-12 text-zinc-500 bg-zinc-900/30 rounded-xl border border-zinc-800/50 border-dashed">
                        <Monitor size={48} className="mx-auto mb-4 opacity-50" />
                        <p className="text-lg font-medium mb-1">Nenhum host encontrado</p>
                        <p className="text-sm">
                            {searchTerm || filterStatus !== 'all'
                                ? 'Tente ajustar seus filtros de busca'
                                : 'Adicione seu primeiro host para começar o monitoramento'}
                        </p>
                    </div>
                ) : (
                    <DndContext
                        sensors={sensors}
                        collisionDetection={closestCenter}
                        onDragStart={(event) => setActiveId(event.active.id as string)}
                        onDragEnd={handleDragEndDnd}
                        onDragCancel={() => setActiveId(null)}
                    >
                        <div className="space-y-8">
                            <SortableContext
                                items={filteredHosts.map(h => h.address)}
                                strategy={rectSortingStrategy}
                            >
                                <div className="flex flex-wrap gap-4">
                                    {filteredHosts.map((host, index) => {
                                        const isOnline = host.stats?.online ?? host.last_status ?? false;
                                        const stats = host.stats || {
                                            online: isOnline,
                                            latency: null,
                                            average_latency: null,
                                            packet_loss: 0,
                                            packet_loss_pct: 0,
                                            total_packets: 0,
                                            calibration_done: false
                                        };

                                        const isReorderEnabled = sortBy === 'manual' && filterStatus === 'all' && searchTerm === '';

                                        return (
                                            <SortableHostCard
                                                key={host.address}
                                                host={host}
                                                index={index}
                                                isOnline={isOnline}
                                                stats={stats}

                                                handleToggleMonitoring={handleToggleMonitoring}
                                                setDetailsHost={setDetailsHostCallback}
                                                setIsDetailsModalOpen={setIsDetailsModalOpenCallback}
                                                isDragDisabled={!isReorderEnabled}
                                                onPing={(host) => navigate('/tools', { state: { target: host.ip || host.address, tool: 'ping', autoRun: true } })}
                                                onTraceroute={(host) => navigate('/tools', { state: { target: host.ip || host.address, tool: 'traceroute', autoRun: false } })}
                                                onDelete={handleDeleteClick}
                                                onUpdateHost={updateHost}
                                                activeContextMenu={activeContextMenu}
                                                onContextMenuOpen={setActiveContextMenu}
                                                onViewDetails={(host) => navigate(`/host/${host.address}`, { state: { host } })}
                                                onSetGroup={handleSetGroupClick}
                                            />
                                        );
                                    })}
                                </div>
                            </SortableContext>
                        </div>
                        <DragOverlay adjustScale={true}>
                            {activeId ? (
                                (() => {
                                    const host = hosts.find(h => h.address === activeId);
                                    if (!host) return null;
                                    const isOnline = host.stats?.online ?? host.last_status ?? false;
                                    const stats = host.stats || {
                                        online: isOnline,
                                        latency: null,
                                        average_latency: null,
                                        packet_loss: 0,
                                        packet_loss_pct: 0,
                                        total_packets: 0,
                                        calibration_done: false
                                    };
                                    return (
                                        <HostCard
                                            host={host}
                                            index={0}
                                            isOnline={isOnline}
                                            stats={stats}

                                            handleToggleMonitoring={handleToggleMonitoring}
                                            setDetailsHost={setDetailsHostCallback}
                                            setIsDetailsModalOpen={setIsDetailsModalOpenCallback}
                                            isDragDisabled={false}
                                            isDragging={true}
                                            isOverlay={true}
                                            onPing={() => { }}
                                            onTraceroute={() => { }}
                                            onDelete={() => { }}
                                        />
                                    );
                                })()
                            ) : null}
                        </DragOverlay>

                        {activeId && (
                            <div className="sticky bottom-8 left-0 w-full flex justify-center z-50 pointer-events-none">
                                <div className="pointer-events-auto">
                                    <TrashDroppable />
                                </div>
                            </div>
                        )}
                    </DndContext>
                )
            }

            <AddHostModal
                isOpen={isAddHostModalOpen}
                onClose={() => setIsAddHostModalOpen(false)}
                onAdd={onAddHost}
                isAdding={isAddingHost}
                existingHosts={hosts}
            />

            <DeleteHostModal
                isOpen={isDeleteModalOpen}
                onClose={() => setIsDeleteModalOpen(false)}
                onConfirm={onConfirmDeleteHost}
                host={hostToDelete}
                isDeleting={isDeleting}
            />

            <SetGroupModal
                isOpen={isSetGroupModalOpen}
                onClose={() => setIsSetGroupModalOpen(false)}
                onConfirm={onConfirmSetGroup}
                currentGroup={hostToSetGroup?.group || ''}
                existingGroups={uniqueGroups}
            />

        </div >
    );
}
