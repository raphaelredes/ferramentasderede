import { API_BASE } from '../config/api';

/**
 * Outcome of an attempt to resolve a host's TeamViewer ID via WinRM.
 *
 * Shared across:
 *  - RemoteAccessModal (auto-fetch on open + manual retry with inline creds)
 *  - Dashboard.executePowerAction (opportunistic background fetch after the
 *    operator supplies admin credentials for a power/message action)
 *  - useHostData (HostDetails advanced view)
 */
export type TvResolveResult =
    | { ok: true; id: string }
    | { ok: false; code: 'CREDENTIALS_UNAVAILABLE' | 'TRUSTED_HOSTS_REQUIRED' | 'NOT_FOUND' | 'ERROR'; message: string };

interface FetchOptions {
    targetIp: string;
    // Either pass plain creds OR a credential_id (vault). credential_id wins.
    username?: string;
    password?: string;
    credentialId?: string;
    /** Persist `teamviewer_id` on the host record after a successful fetch. */
    persistOnHost?: string; // host address to PATCH
    /** Allow toggling TrustedHosts for this single request (X-Temp-Auth). */
    tempAuth?: boolean;
}

/**
 * Resolve a host's TeamViewer ID by streaming /system/teamviewer. Optionally
 * persists the result with PATCH /hosts/{address} so the next render shows the
 * "Conectar Automaticamente" button without another WinRM round-trip.
 *
 * Never throws — all failure modes are returned as `{ok: false, code, message}`
 * so callers (especially opportunistic background ones) can decide whether to
 * surface a toast or stay silent.
 */
export async function resolveTeamViewerId(opts: FetchOptions): Promise<TvResolveResult> {
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

        const res = await fetch(`${API_BASE}/system/teamviewer`, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });

        if (!res.ok || !res.body) {
            return { ok: false, code: 'ERROR', message: `HTTP ${res.status}` };
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let foundId: string | null = null;
        let errorMsg: string | null = null;
        let errorCode: 'TRUSTED_HOSTS_REQUIRED' | 'CREDENTIALS_UNAVAILABLE' | null = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const parsed = JSON.parse(line);
                    if (parsed.code === 'CREDENTIALS_UNAVAILABLE') {
                        errorCode = 'CREDENTIALS_UNAVAILABLE';
                        errorMsg = parsed.message || 'Cofre indisponível.';
                    } else if (parsed.code === 'TRUSTED_HOSTS_REQUIRED') {
                        errorCode = 'TRUSTED_HOSTS_REQUIRED';
                        errorMsg = 'TrustedHosts não configurado para esse alvo.';
                    } else if (parsed.status === 'error') {
                        errorMsg = parsed.message || 'Falha ao buscar TeamViewer ID';
                    } else if (parsed.status === 'success' && parsed.data) {
                        foundId = String(parsed.data);
                    }
                } catch {
                    /* skip malformed line */
                }
            }
        }

        if (foundId) {
            if (opts.persistOnHost) {
                fetch(`${API_BASE}/hosts/${opts.persistOnHost}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ teamviewer_id: foundId }),
                }).catch(() => undefined);
            }
            return { ok: true, id: foundId };
        }

        if (errorCode === 'CREDENTIALS_UNAVAILABLE') {
            return { ok: false, code: 'CREDENTIALS_UNAVAILABLE', message: errorMsg || 'Cofre bloqueado ou credencial padrão não configurada.' };
        }
        if (errorCode === 'TRUSTED_HOSTS_REQUIRED') {
            return { ok: false, code: 'TRUSTED_HOSTS_REQUIRED', message: errorMsg || 'TrustedHosts não configurado.' };
        }
        return { ok: false, code: 'NOT_FOUND', message: errorMsg || 'TeamViewer não detectado no host.' };
    } catch (e: unknown) {
        return { ok: false, code: 'ERROR', message: e instanceof Error ? e.message : String(e) };
    }
}

/** Probe vault status + default credential. Used by callers that want to
 *  decide whether to attempt a silent fetch before falling back to an inline
 *  credential prompt. */
export async function getDefaultCredentialIdIfAvailable(): Promise<string | null> {
    try {
        const [settingsRes, vaultRes] = await Promise.all([
            fetch(`${API_BASE}/settings`),
            fetch(`${API_BASE}/security/status`),
        ]);
        if (!settingsRes.ok || !vaultRes.ok) return null;
        const settings = await settingsRes.json();
        const vaultStatus = await vaultRes.json();
        if (!vaultStatus?.is_unlocked) return null;
        return settings?.remote?.default_credential_id ?? null;
    } catch {
        return null;
    }
}
