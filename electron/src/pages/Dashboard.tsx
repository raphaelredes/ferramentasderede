import { useState, useCallback, useEffect, useRef } from 'react';
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
    DragOverlay,
    CollisionDetection,
    pointerWithin
} from '@dnd-kit/core';



import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    rectSortingStrategy
} from '@dnd-kit/sortable';
import { CredentialModal } from '../components/CredentialModal';
import TrustedHostsModal from '../components/TrustedHostsModal';

import { DashboardHeader } from '../components/Dashboard/DashboardHeader';
import { FilterBar } from '../components/Dashboard/FilterBar';
import { HostCard } from '../components/Dashboard/HostCard';
import { SortableHostCard } from '../components/Dashboard/SortableHostCard';
import { AddHostModal } from '../components/Dashboard/AddHostModal';
import { DeleteHostModal } from '../components/Dashboard/DeleteHostModal';
import { TrashDroppable } from '../components/Dashboard/TrashDroppable';
import { SetGroupModal } from '../components/Dashboard/SetGroupModal';
import { HostDetailsModal } from '../components/Dashboard/HostDetailsModal';
import { PrePowerActionModal } from '../components/Dashboard/PrePowerActionModal';
import { preCheckPowerAction, shouldWarn, PrePowerCheckData } from '../utils/prePowerCheck';
import { Host } from '../types';
import { useMonitoring } from '../contexts/MonitoringContext';
import { useHostActions } from '../hooks/useHostActions';
import { useToast } from '../contexts/ToastContext';
import { useTools } from '../contexts/ToolsContext';
import { useTrustedHostsSession } from '../contexts/TrustedHostsSessionContext';
import { HostListSkeleton } from '../components/Dashboard/HostListSkeleton';
import { GroupNetworkTabs } from '../components/Dashboard/GroupNetworkTabs';
import { API_BASE } from '../config/api';
import { useNetworks } from '../hooks/useNetworks';
import { useFilteredHosts } from '../hooks/useFilteredHosts';
import { resolveTeamViewerId } from '../utils/teamviewer';
import { probeHost } from '../utils/hostProbe';

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

    const { setPendingAction } = useTools();
    const { isApproved: isTrustedSessionApproved } = useTrustedHostsSession();

    const navigate = useNavigate();

    const customCollisionDetection: CollisionDetection = useCallback((args) => {
        const pointerCollisions = pointerWithin(args);

        // First, check if the pointer is over the trash (strict)
        const trashCollision = pointerCollisions.find(c => c.id === 'trash-droppable');
        if (trashCollision) {
            return [trashCollision];
        }

        // Otherwise, use closestCenter for the sortable list, BUT EXCLUDE THE TRASH
        // This ensures the trash only activates on strict pointer overlap
        return closestCenter({
            ...args,
            droppableContainers: args.droppableContainers.filter(container => container.id !== 'trash-droppable')
        });
    }, []);

    // Modal State
    const [isAddHostModalOpen, setIsAddHostModalOpen] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [hostToDelete, setHostToDelete] = useState<Host | null>(null);
    const [isSetGroupModalOpen, setIsSetGroupModalOpen] = useState(false);
    const [hostToSetGroup, setHostToSetGroup] = useState<Host | null>(null);

    // Details Modal State
    const [detailsHost, setDetailsHost] = useState<Host | null>(null);
    const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
    const [isEditingName, setIsEditingName] = useState(false);
    const [editedName, setEditedName] = useState('');
    const [modalStatus, setModalStatus] = useState<{ type: 'success' | 'error' | 'info', message: string } | null>(null);
    const [copiedIp, setCopiedIp] = useState(false);
    const [copiedHostname, setCopiedHostname] = useState(false);

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
    const [activeNetworkTab, setActiveNetworkTab] = useState('all'); // 'all' | 'unassigned' | network.id

    const { networks } = useNetworks();

    // Handlers
    const onAddHost = async (name: string, address: string, mac: string, ports: number[], group: string) => {
        const success = await addHost(name, address, mac, ports, group);
        if (success) {
            await fetchHosts(true);
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
            // Also close the details modal if the deleted host is the one being
            // shown there — otherwise the user is left staring at a card for a
            // host that no longer exists.
            setIsDetailsModalOpen(false);
            setDetailsHost(null);
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

    const handleToggleMonitoring = useCallback(async (e: React.MouseEvent, host: Host) => {
        e.stopPropagation();
        const newStatus = host.monitoring === false;

        // Use the centralized updateHost helper — same code path as nickname /
        // ports / reset_stats. Inline fetch was missing two things: URL-encode
        // and a `response.ok` check (a 404 from the backend was being treated
        // as success here, while the .catch only fired on a network error).
        const ok = await updateHost(host.address, { monitoring: newStatus });
        if (ok) {
            fetchHosts();
        } else {
            showToast('Erro ao atualizar monitoramento', 'error');
        }
    }, [fetchHosts, showToast, updateHost]);

    // Details Modal Handlers
    const handleModalCopy = (text: string, type: 'ip' | 'hostname') => {
        navigator.clipboard.writeText(text);
        if (type === 'ip') {
            setCopiedIp(true);
            setTimeout(() => setCopiedIp(false), 2000);
        } else {
            setCopiedHostname(true);
            setTimeout(() => setCopiedHostname(false), 2000);
        }
    };

    const handleRefreshDetails = async () => {
        if (!detailsHost) return;
        await fetchHosts();
        const freshHost = hosts.find(h => h.address === detailsHost.address);
        if (freshHost) {
            setDetailsHost(freshHost);
        }
    };

    // Sync detailsHost with hosts list to reflect background updates
    useEffect(() => {
        if (isDetailsModalOpen && detailsHost) {
            const freshHost = hosts.find(h => h.address === detailsHost.address);
            if (freshHost && freshHost !== detailsHost) {
                setDetailsHost(freshHost);
            }
        }
    }, [hosts, isDetailsModalOpen, detailsHost]);

    // Auth & Action State
    const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
    const [isTrustedHostsModalOpen, setIsTrustedHostsModalOpen] = useState(false);
    const [pendingPowerAction, setPendingPowerAction] = useState<{
        host: Host;
        type: 'shutdown' | 'restart' | 'wol' | 'message' | 'cancel';
        message?: string;
        delay?: number;
        auth?: { user: string; pass: string };
    } | null>(null);
    const [pendingTrustedAction, setPendingTrustedAction] = useState<(() => Promise<void>) | null>(null);

    // Pre-power confirmation state — shown only for shutdown/restart after the
    // user has provided creds. Holds the in-flight check + the auth pair so we
    // can dispatch executePowerAction immediately on confirm.
    const [prePowerState, setPrePowerState] = useState<{
        host: Host;
        type: 'shutdown' | 'restart';
        message?: string;
        delay?: number;
        user: string;
        pass: string;
        check: PrePowerCheckData | null;
        error: string | null;
    } | null>(null);

    const executePowerAction = async (
        host: Host,
        type: 'shutdown' | 'restart' | 'wol' | 'message' | 'cancel',
        message: string = '',
        delay: number = 0,
        user: string,
        pass: string,
        tempAuth: boolean = false
    ) => {
        // Auto-elevate when this host was approved earlier in the same session.
        // The actual TrustedHosts mutation still happens server-side, scoped to
        // this single request via the X-Temp-Auth header.
        const effectiveTempAuth = tempAuth || isTrustedSessionApproved(host.address);

        const headers: HeadersInit = {
            'Content-Type': 'application/json'
        };
        if (effectiveTempAuth) {
            headers['X-Temp-Auth'] = 'true';
        }

        try {
            const body = {
                target_ip: host.address, // Use address as IP might be resolving
                username: user,
                password: pass,
                action: type,
                message: message,
                timeout: delay,
                force: true
            };

            const res = await fetch(`${API_BASE}/system/power`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(body)
            });

            if (res.ok) {
                const reader = res.body?.getReader();
                const decoder = new TextDecoder();
                let hasError = false;

                if (reader) {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const chunk = decoder.decode(value);
                        const lines = chunk.split('\n');

                        for (const line of lines) {
                            if (!line.trim()) continue;
                            try {
                                const data = JSON.parse(line);
                                if (data.status === 'error') {
                                    hasError = true;
                                    if (data.code === "TRUSTED_HOSTS_REQUIRED") {
                                        setPendingTrustedAction(() => async () => executePowerAction(host, type, message, delay, user, pass, true));
                                        setIsTrustedHostsModalOpen(true);
                                        return;
                                    }
                                    showToast(`Erro: ${data.message}`, 'error');
                                    return;
                                }
                            } catch (e) {
                                console.error('Error parsing power action response:', e);
                            }
                        }
                    }
                }

                if (!hasError) {
                    showToast(`Ação ${type} enviada com sucesso`, 'success');
                    // Opportunistic background probes: we just proved these
                    // credentials work for this host. Free signals — fire-and-
                    // forget, backend persists, then we silent-refresh once.
                    const followUps: Promise<unknown>[] = [];
                    if (!host.teamviewer_id) {
                        followUps.push(resolveTeamViewerId({
                            targetIp: host.address,
                            username: user,
                            password: pass,
                            persistOnHost: host.address,
                            tempAuth: effectiveTempAuth,
                        }));
                    }
                    followUps.push(probeHost({
                        targetIp: host.address,
                        username: user,
                        password: pass,
                        tempAuth: effectiveTempAuth,
                    }));
                    Promise.allSettled(followUps).then(() => {
                        fetchHosts(true).catch(() => undefined);
                    });
                }
            } else {
                const err = await res.json().catch(() => ({}));
                if (res.status === 403 && err.detail === "TRUSTED_HOSTS_REQUIRED") {
                    setPendingTrustedAction(() => async () => executePowerAction(host, type, message, delay, user, pass, true));
                    setIsTrustedHostsModalOpen(true);
                    return;
                }
                showToast('Erro ao executar ação', 'error');
            }
        } catch (e) {
            console.error(e);
            showToast('Erro ao executar ação', 'error');
        }
    };

    const handleAction = async (host: Host, type: 'shutdown' | 'restart' | 'wol' | 'message' | 'cancel', message?: string, delay?: number) => {
        setPendingPowerAction({ host, type, message, delay });
        setIsAuthModalOpen(true);
    };

    const handleConfirmTrustedHosts = async () => {
        if (pendingTrustedAction) {
            setIsTrustedHostsModalOpen(false);
            await pendingTrustedAction();
            setPendingTrustedAction(null);
        }
    };

    const handleSaveName = async () => {
        if (!detailsHost) return;
        const success = await updateHost(detailsHost.address, { name: editedName });
        if (success) {
            setModalStatus({ type: 'success', message: 'Nome atualizado com sucesso!' });
            setTimeout(() => setModalStatus(null), 3000);
            setIsEditingName(false);
            handleRefreshDetails();
        } else {
            setModalStatus({ type: 'error', message: 'Erro ao atualizar nome.' });
            setTimeout(() => setModalStatus(null), 3000);
        }
    };

    const setDetailsHostCallback = useCallback((host: Host) => {
        setDetailsHost(host);
    }, []);

    const setIsDetailsModalOpenCallback = useCallback((isOpen: boolean) => {
        setIsDetailsModalOpen(isOpen);
    }, []);

    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const [activeId, setActiveId] = useState<string | null>(null);

    const filteredHosts = useFilteredHosts({
        hosts,
        searchTerm,
        filterStatus,
        activeGroupTab,
        activeNetworkTab,
        sortBy,
        hostOrder,
    });

    // Stable reference cache for the `stats` prop fed to each HostCard.
    // Without this, every poll (2s) creates a new `host.stats` object reference
    // even when the underlying values didn't change — defeating React.memo on
    // HostCard and causing O(N) re-renders per tick. We compare shallow on the
    // fields that actually drive the card UI and reuse the previous reference
    // when nothing relevant moved.
    const statsCacheRef = useRef<Map<string, { hash: string; stats: any; isOnline: boolean }>>(new Map());
    const getStableStats = useCallback((host: Host) => {
        const raw = host.stats;
        const isOnline = raw?.online ?? host.last_status ?? false;
        // Hash captures every field HostCard actually reads. history is summarized
        // by length + last latency since recharts rerenders are cheap and full
        // deep compare would be wasted work.
        const hash = raw
            ? [
                  raw.online,
                  raw.latency,
                  raw.average_latency,
                  raw.packet_loss_pct?.toFixed?.(1),
                  raw.total_packets,
                  raw.calibration_done,
                  raw.is_smart_offline,
                  raw.has_ever_been_online,
                  raw.history?.length ?? 0,
                  raw.history?.[raw.history.length - 1]?.latency ?? 0,
                  Object.keys(raw.ports_status ?? {}).length,
                  raw.ip,
              ].join('|')
            : `__empty__|${isOnline}`;

        const cached = statsCacheRef.current.get(host.address);
        if (cached && cached.hash === hash) {
            return { stats: cached.stats, isOnline: cached.isOnline };
        }
        const stats = raw ?? {
            online: isOnline,
            latency: null,
            average_latency: null,
            packet_loss: 0,
            packet_loss_pct: 0,
            total_packets: 0,
            calibration_done: false,
        };
        statsCacheRef.current.set(host.address, { hash, stats, isOnline });
        return { stats, isOnline };
    }, []);

    // GC do cache: remover entradas de hosts que não existem mais (host deletado).
    useEffect(() => {
        const live = new Set(hosts.map(h => h.address));
        for (const key of statsCacheRef.current.keys()) {
            if (!live.has(key)) statsCacheRef.current.delete(key);
        }
    }, [hosts]);

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
            const oldIndex = filteredHosts.findIndex((host) => host.address === active.id);
            const newIndex = filteredHosts.findIndex((host) => host.address === over.id);

            const newHosts = arrayMove(filteredHosts, oldIndex, newIndex);

            const newOrder = newHosts.map(h => h.address);
            setHostOrder(newOrder);
            localStorage.setItem('hostOrder', JSON.stringify(newOrder));

            if (sortBy !== 'manual') {
                setSortBy('manual');
            }
        }
    };

    return (
        <div className="p-8 max-w-[1600px] mx-auto">
            <DashboardHeader
                onAddHost={() => setIsAddHostModalOpen(true)}
                totalHosts={hosts.length}
                onlineHosts={globalStats.online}
            />

            <GroupNetworkTabs
                uniqueGroups={uniqueGroups}
                activeGroupTab={activeGroupTab}
                onGroupTabChange={setActiveGroupTab}
                networks={networks}
                activeNetworkTab={activeNetworkTab}
                onNetworkTabChange={setActiveNetworkTab}
            />

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
                        collisionDetection={customCollisionDetection}
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
                                        const { stats, isOnline } = getStableStats(host);

                                        const isReorderEnabled = sortBy === 'manual' && filterStatus === 'all' && searchTerm === '' && activeGroupTab === 'all';

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
                                                onPing={(host) => {
                                                    // Carrega o source_ip da rede do host se cadastrada — assim
                                                    // ações rápidas no card já saem pela NIC certa em multi-VLAN.
                                                    const net = host.network_id ? networks.find(n => n.id === host.network_id) : undefined;
                                                    setPendingAction({
                                                        type: 'ping',
                                                        target: host.ip || host.address,
                                                        id: crypto.randomUUID(),
                                                        sourceIp: net?.source_ip,
                                                    });
                                                    navigate('/tools');
                                                }}
                                                onTraceroute={(host) => {
                                                    const net = host.network_id ? networks.find(n => n.id === host.network_id) : undefined;
                                                    setPendingAction({
                                                        type: 'traceroute',
                                                        target: host.ip || host.address,
                                                        id: crypto.randomUUID(),
                                                        sourceIp: net?.source_ip,
                                                    });
                                                    navigate('/tools');
                                                }}
                                                onDelete={handleDeleteClick}
                                                onUpdateHost={updateHost}
                                                activeContextMenu={activeContextMenu}
                                                onContextMenuOpen={setActiveContextMenu}
                                                onViewDetails={undefined}
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
                                    const { stats, isOnline } = getStableStats(host);
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
                            <div className="fixed bottom-8 left-0 w-full flex justify-center z-[100] pointer-events-none">
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
                existingGroups={uniqueGroups}
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

            <HostDetailsModal
                isOpen={isDetailsModalOpen}
                onClose={() => setIsDetailsModalOpen(false)}
                host={detailsHost}
                hostStatus={{}}
                onRefresh={handleRefreshDetails}
                onAction={handleAction}
                onDelete={handleDeleteClick}
                onSaveName={handleSaveName}
                isEditingName={isEditingName}
                setIsEditingName={setIsEditingName}
                editedName={editedName}
                setEditedName={setEditedName}
                modalStatus={modalStatus}
                handleModalCopy={handleModalCopy}
                copiedIp={copiedIp}
                copiedHostname={copiedHostname}
                onUpdateHost={updateHost}
            />

            <CredentialModal
                isOpen={isAuthModalOpen}
                onClose={() => {
                    setIsAuthModalOpen(false);
                    setPendingPowerAction(null);
                }}
                title="Autenticação Necessária"
                initialDomain={pendingPowerAction?.host.domain || ''}
                onConfirm={(username, password) => {
                    if (!pendingPowerAction) return;
                    setIsAuthModalOpen(false);
                    const { host, type, message, delay } = pendingPowerAction;

                    // Destructive actions go through a pre-check first so the
                    // operator sees uptime/sessions/pending-reboot warnings before
                    // we ship the shutdown. Other action types (wol/message/
                    // cancel) just execute as before.
                    if (type === 'shutdown' || type === 'restart') {
                        setPrePowerState({
                            host,
                            type,
                            message,
                            delay,
                            user: username,
                            pass: password,
                            check: null,
                            error: null,
                        });
                        preCheckPowerAction({
                            targetIp: host.address,
                            username,
                            password,
                            tempAuth: isTrustedSessionApproved(host.address),
                        }).then(r => {
                            setPrePowerState(prev => {
                                if (!prev || prev.host.address !== host.address) return prev;
                                if (r.ok) {
                                    // Auto-skip the dialog when there's nothing to warn about.
                                    if (!shouldWarn(r.data, type)) {
                                        executePowerAction(host, type, message ?? '', delay ?? 0, username, password);
                                        return null;
                                    }
                                    return { ...prev, check: r.data, error: null };
                                }
                                return { ...prev, check: null, error: r.message };
                            });
                        }).catch(e => {
                            setPrePowerState(prev => prev && { ...prev, error: String(e) });
                        });
                        setPendingPowerAction(null);
                    } else {
                        executePowerAction(host, type, message, delay, username, password);
                        setPendingPowerAction(null);
                    }
                }}
            />

            <PrePowerActionModal
                isOpen={!!prePowerState}
                host={prePowerState?.host ?? null}
                type={prePowerState?.type ?? 'shutdown'}
                check={prePowerState?.check ?? null}
                error={prePowerState?.error ?? null}
                onClose={() => setPrePowerState(null)}
                onProceed={() => {
                    if (!prePowerState) return;
                    const { host, type, message, delay, user, pass } = prePowerState;
                    executePowerAction(host, type, message ?? '', delay ?? 0, user, pass);
                    setPrePowerState(null);
                }}
            />

            <TrustedHostsModal
                isOpen={isTrustedHostsModalOpen}
                onClose={() => setIsTrustedHostsModalOpen(false)}
                onConfirm={handleConfirmTrustedHosts}
                targetIp={pendingPowerAction?.host.address}
            />

        </div>
    );
}
