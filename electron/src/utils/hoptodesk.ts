import { API_BASE } from '../config/api';

export type HtdResolveResult =
    | { ok: true; id: string; running: boolean }
    | { ok: false; code: 'CREDENTIALS_UNAVAILABLE' | 'TRUSTED_HOSTS_REQUIRED' | 'NOT_FOUND' | 'ERROR'; message: string };

interface FetchOptions {
    targetIp: string;
    username?: string;
    password?: string;
    credentialId?: string;
    targetLocation?: 'public' | 'user';
    targetUser?: string;
    persistOnHost?: string; // host address to PATCH
    tempAuth?: boolean;
    onProgress?: (message: string) => void;
}

/**
 * Implanta o HopToDesk no host remoto (se necessário) e obtém seu ID de conexão.
 * Persiste o resultado no banco via PATCH /hosts/{address}.
 */
export async function deployAndResolveHopToDeskId(opts: FetchOptions): Promise<HtdResolveResult> {
    try {
        const headers: HeadersInit = { 'Content-Type': 'application/json' };
        if (opts.tempAuth) headers['X-Temp-Auth'] = 'true';

        const body: Record<string, unknown> = {
            target_ip: opts.targetIp,
            target_location: opts.targetLocation || 'public',
            target_user: opts.targetUser || null,
        };
        if (opts.credentialId) {
            body.credential_id = opts.credentialId;
        } else {
            body.username = opts.username ?? '';
            body.password = opts.password ?? '';
        }

        const res = await fetch(`${API_BASE}/system/hoptodesk/deploy`, {
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
        let isRunning: boolean = true;
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
                    if (parsed.message && opts.onProgress) {
                        opts.onProgress(parsed.message);
                    }
                    if (parsed.code === 'CREDENTIALS_UNAVAILABLE') {
                        errorCode = 'CREDENTIALS_UNAVAILABLE';
                        errorMsg = parsed.message || 'Cofre indisponível.';
                    } else if (parsed.code === 'TRUSTED_HOSTS_REQUIRED') {
                        errorCode = 'TRUSTED_HOSTS_REQUIRED';
                        errorMsg = 'TrustedHosts não configurado para esse alvo.';
                    } else if (parsed.status === 'error') {
                        errorMsg = parsed.message || 'Falha ao implantar HopToDesk.';
                    } else if (parsed.status === 'success' && parsed.data) {
                        foundId = String(parsed.data);
                        if (parsed.running !== undefined) {
                            isRunning = Boolean(parsed.running);
                        }
                    }
                } catch {
                    /* skip malformed lines */
                }
            }
        }

        if (foundId) {
            if (opts.persistOnHost) {
                fetch(`${API_BASE}/hosts/${opts.persistOnHost}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ hoptodesk_id: foundId }),
                }).catch(() => undefined);
            }
            return { ok: true, id: foundId, running: isRunning };
        }

        if (errorCode === 'CREDENTIALS_UNAVAILABLE') {
            return { ok: false, code: 'CREDENTIALS_UNAVAILABLE', message: errorMsg || 'Cofre bloqueado ou credencial padrão não configurada.' };
        }
        if (errorCode === 'TRUSTED_HOSTS_REQUIRED') {
            return { ok: false, code: 'TRUSTED_HOSTS_REQUIRED', message: errorMsg || 'TrustedHosts não configurado.' };
        }
        return { ok: false, code: 'NOT_FOUND', message: errorMsg || 'HopToDesk ID não detectado no host.' };
    } catch (e: unknown) {
        return { ok: false, code: 'ERROR', message: e instanceof Error ? e.message : String(e) };
    }
}

/** Inicia o HopToDesk local conectando ao ID alvo. */
export async function launchLocalHopToDesk(targetId: string): Promise<boolean> {
    const clean = targetId.replace(/\s+/g, '');
    if (window.electron?.launchHopToDesk) {
        return await window.electron.launchHopToDesk(clean);
    }
    try {
        const res = await fetch(`${API_BASE}/system/hoptodesk/launch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_id: clean }),
        });
        const data = await res.json();
        return data.status === 'success';
    } catch {
        return false;
    }
}
