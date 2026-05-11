import { API_BASE } from '../config/api';

export interface SessionInfo {
    user: string;
    state: string;            // "Active", "Disc", "Ativo" etc — locale-dependent from quser
    idle_seconds: number | null;
}

export interface PrePowerCheckData {
    uptime_minutes: number | null;
    last_boot: string;          // ISO local time or "N/A"
    pending_reboot: boolean | null;
    pending_reasons: string[];
    sessions: SessionInfo[];
}

export type PrePowerCheckResult =
    | { ok: true; data: PrePowerCheckData }
    | { ok: false; code: 'CREDENTIALS_UNAVAILABLE' | 'TRUSTED_HOSTS_REQUIRED' | 'CHECK_FAILED' | 'NETWORK'; message: string };

interface PrePowerOptions {
    targetIp: string;
    username?: string;
    password?: string;
    credentialId?: string;
    tempAuth?: boolean;
}

/**
 * Fast safety check before shutdown/restart. Returns uptime, pending reboot
 * state and active sessions so the UI can confirm with the operator before
 * doing something destructive. Never throws.
 */
export async function preCheckPowerAction(opts: PrePowerOptions): Promise<PrePowerCheckResult> {
    try {
        const headers: HeadersInit = { 'Content-Type': 'application/json' };
        if (opts.tempAuth) headers['X-Temp-Auth'] = 'true';

        const body: Record<string, unknown> = { target_ip: opts.targetIp };
        if (opts.credentialId) {
            body.credential_id = opts.credentialId;
        } else {
            body.username = opts.username ?? '';
            body.password = opts.password ?? '';
        }

        const res = await fetch(`${API_BASE}/system/pre-power-check`, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            return { ok: false, code: 'CHECK_FAILED', message: `HTTP ${res.status}` };
        }
        const parsed = await res.json().catch(() => null);
        if (!parsed || typeof parsed !== 'object') {
            return { ok: false, code: 'CHECK_FAILED', message: 'Resposta vazia.' };
        }
        if (parsed.status === 'success' && parsed.data) {
            return { ok: true, data: parsed.data as PrePowerCheckData };
        }
        const code = (parsed.code as PrePowerCheckResult extends { ok: false; code: infer C } ? C : never) ?? 'CHECK_FAILED';
        return { ok: false, code, message: parsed.message || 'Falha desconhecida.' };
    } catch (e: unknown) {
        return { ok: false, code: 'NETWORK', message: e instanceof Error ? e.message : String(e) };
    }
}

/** "Heuristic" — does the operator deserve a confirmation prompt for this host? */
export function shouldWarn(data: PrePowerCheckData, type: 'shutdown' | 'restart'): boolean {
    // Active users that aren't the local viewer are always a reason to warn.
    const hasOtherUsers = data.sessions.some(s => {
        const state = (s.state || '').toLowerCase();
        // "Active" / "Ativo" or anything with "disc" still implies someone is logged in.
        return state.includes('active') || state.includes('ativo') || state.includes('disc');
    });
    if (hasOtherUsers) return true;

    // Recently rebooted (<10 min) is suspicious — operator might be clicking
    // restart twice or hitting a freshly-rebooted host.
    if (typeof data.uptime_minutes === 'number' && data.uptime_minutes < 10) return true;

    // Pending reboot + we're issuing a *shutdown* (not restart) means the pending
    // work won't apply. Worth telling the operator. For `restart`, this is fine.
    if (type === 'shutdown' && data.pending_reboot) return true;

    return false;
}
