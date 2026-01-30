import { memo } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { HostCard } from './HostCard';
import { Host, HostStatistics, HostUpdate } from '../../types';

interface SortableHostCardProps {
    host: Host;
    index: number;
    isOnline: boolean;
    stats: HostStatistics;
    handleToggleMonitoring: (e: React.MouseEvent, host: Host) => void;
    setDetailsHost: (host: Host) => void;
    setIsDetailsModalOpen: (isOpen: boolean) => void;
    isDragDisabled: boolean;
    onPing: (host: Host) => void;
    onTraceroute: (host: Host) => void;
    onDelete: (host: Host) => void;
    onUpdateHost?: (address: string, updates: HostUpdate) => Promise<boolean>;
    activeContextMenu?: string | null;
    onContextMenuOpen?: (id: string | null) => void;
    onViewDetails?: (host: Host) => void;
    onSetGroup?: (host: Host) => void;
}

export const SortableHostCard = memo(function SortableHostCard(props: SortableHostCardProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: props.host.address, disabled: props.isDragDisabled });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 100 : 'auto',
        opacity: isDragging ? 0.5 : 1,
    };

    return (
        <HostCard
            {...props}
            setNodeRef={setNodeRef}
            style={style}
            attributes={attributes}
            listeners={listeners}
            isDragging={isDragging}
            onPing={props.onPing}
            onTraceroute={props.onTraceroute}
            onDelete={props.onDelete}
            onUpdateHost={props.onUpdateHost}
            activeContextMenu={props.activeContextMenu}
            onContextMenuOpen={props.onContextMenuOpen}
            onViewDetails={props.onViewDetails}
            onSetGroup={props.onSetGroup}
        />
    );
});
