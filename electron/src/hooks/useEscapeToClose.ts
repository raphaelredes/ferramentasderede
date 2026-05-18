import { useEffect } from 'react';

/**
 * Install a document-level Escape key handler that fires `onClose` while the
 * modal is open. Cleans up on close / unmount so multiple modals don't stack
 * listeners.
 *
 * Most modals in the app already implemented this manually with the same
 * 6-line `useEffect` (AddHostModal, DeleteHostModal, PrePowerActionModal,
 * ConfirmationModal). Centralising avoids drift and lets new modals get
 * Escape-to-close in one line.
 */
export function useEscapeToClose(isOpen: boolean, onClose: () => void): void {
    useEffect(() => {
        if (!isOpen) return;
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handler);
        return () => document.removeEventListener('keydown', handler);
    }, [isOpen, onClose]);
}
