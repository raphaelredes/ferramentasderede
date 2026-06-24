import { useEffect, useRef } from 'react';
import { Host } from '../types';
import { useToast } from '../contexts/ToastContext';
import { API_BASE } from '../config/api';

/**
 * Fires a toast + native desktop notification when a monitored host transitions
 * online→offline or offline→online, gated by the operator's
 * settings.dashboard.notify_offline / notify_online flags.
 *
 * Design notes:
 * - Frontend-only. MonitoringContext already polls every host's status every
 *   ~2s; we just diff the previous snapshot against the current one. No backend
 *   change, no new socket.
 * - The native Notification API works in both the pywebview portable (WebView2)
 *   and the Electron build (Chromium), so it surfaces even when the window is in
 *   the background. Toast is the in-app fallback when permission is denied.
 * - The FIRST batch of hosts is recorded as the baseline WITHOUT notifying —
 *   otherwise every host would "notify" its initial state on app start.
 * - A host's effective status treats `is_smart_offline` as offline, matching the
 *   consolidated criterion the cards already use (no notification on an isolated
 *   ping blip within an otherwise-up host).
 */

type NotifyPrefs = { notify_offline: boolean; notify_online: boolean };

/** Effective up/down for a host, or null when status is not yet known. */
function effectiveOnline(host: Host): boolean | null {
    const s = host.stats;
    if (s) {
        if (s.is_smart_offline) return false;
        if (typeof s.online === 'boolean') return s.online;
    }
    if (typeof host.last_status === 'boolean') return host.last_status;
    return null;
}

function hostLabel(host: Host): string {
    return host.name || host.hostname || host.ip || host.address;
}

export function useHostNotifications(hosts: Host[]) {
    const { showToast } = useToast();

    // address -> last known effective online state. Seeded on first non-empty
    // batch so we never alert on the initial snapshot.
    const prevStatusRef = useRef<Map<string, boolean>>(new Map());
    const baselineSetRef = useRef(false);
    const prefsRef = useRef<NotifyPrefs>({ notify_offline: false, notify_online: false });
    const permissionAskedRef = useRef(false);

    // Keep notification prefs fresh. Cheap poll (30s) — settings change rarely
    // and this avoids threading a prefs prop through every caller.
    useEffect(() => {
        let cancelled = false;
        const loadPrefs = async () => {
            try {
                const res = await fetch(`${API_BASE}/settings`);
                const data = await res.json();
                if (cancelled) return;
                prefsRef.current = {
                    notify_offline: !!data?.dashboard?.notify_offline,
                    notify_online: !!data?.dashboard?.notify_online,
                };
                // Only prompt for OS notification permission once, and only if the
                // operator actually wants notifications — no unsolicited prompt.
                const wantsAny = prefsRef.current.notify_offline || prefsRef.current.notify_online;
                if (wantsAny && !permissionAskedRef.current && typeof Notification !== 'undefined') {
                    permissionAskedRef.current = true;
                    if (Notification.permission === 'default') {
                        try { Notification.requestPermission(); } catch { /* noop */ }
                    }
                }
            } catch {
                /* settings unavailable — keep last known prefs */
            }
        };
        loadPrefs();
        const id = setInterval(loadPrefs, 30_000);
        return () => { cancelled = true; clearInterval(id); };
    }, []);

    useEffect(() => {
        if (hosts.length === 0) return;

        const prev = prevStatusRef.current;

        // First non-empty batch: record baseline silently.
        if (!baselineSetRef.current) {
            for (const h of hosts) {
                const st = effectiveOnline(h);
                if (st !== null) prev.set(h.address, st);
            }
            baselineSetRef.current = true;
            return;
        }

        const { notify_offline, notify_online } = prefsRef.current;

        for (const h of hosts) {
            const current = effectiveOnline(h);
            if (current === null) continue; // status unknown this round — skip

            const previous = prev.get(h.address);
            prev.set(h.address, current);

            if (previous === undefined || previous === current) continue; // no transition

            const label = hostLabel(h);
            if (previous === true && current === false && notify_offline) {
                emit(`${label} ficou OFFLINE`, `O host ${label} parou de responder.`, 'error', showToast);
            } else if (previous === false && current === true && notify_online) {
                emit(`${label} voltou ONLINE`, `O host ${label} está respondendo novamente.`, 'success', showToast);
            }
        }

        // Drop addresses that left the host list so the map doesn't grow forever.
        const liveAddrs = new Set(hosts.map(h => h.address));
        for (const addr of prev.keys()) {
            if (!liveAddrs.has(addr)) prev.delete(addr);
        }
    }, [hosts, showToast]);
}

function emit(
    title: string,
    body: string,
    toastType: 'success' | 'error',
    showToast: (m: string, t: 'success' | 'error') => void,
) {
    // In-app toast always.
    showToast(title, toastType);
    // Native desktop notification when granted (visible with window in background).
    try {
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification(title, { body });
        }
    } catch {
        /* some webviews throw on construction — toast already covered it */
    }
}
