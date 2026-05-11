import { API_BASE } from '../config/api';

/**
 * Result of an opportunistic host probe. Always resolves (never rejects) so
 * callers can be true fire-and-forget. Failure modes are signalled by `ok:false`.
 */
export type HostProbeResult =
    | {
          ok: true;
          data: {
              MACAddress?: string;
              Domain?: string;
              CurrentUser?: string;
              LastBootUpTime?: string;
              SystemDiskFreeGB?: number | null;
          };
      }
    | {
          ok: false;
          code: 'CREDENTIALS_UNAVAILABLE' | 'TRUSTED_HOSTS_REQUIRED' | 'PROBE_FAILED' | 'NETWORK';
          message: string;
      };

interface ProbeOptions {
    targetIp: string;
    username?: string;
    password?: string;
    credentialId?: string;
    tempAuth?: boolean;
}

/**
 * Calls /system/host-probe. The endpoint already persists the discovered
 * fields on the host record — callers don't need to PATCH. Use the returned
 * data only when you want to update UI immediately (e.g., show "MAC detected")
 * or decide on a follow-up (e.g., "uptime is 3 min — confirm restart?").
 *
 * Never throws. Designed to be called as:
 *   probeHost({...}).then(() => fetchHosts(true));   // silent refresh
 *   probeHost({...}).catch(() => undefined);          // also fine
 */
export async function probeHost(opts: ProbeOptions): Promise<HostProbeResult> {
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

        const res = await fetch(`${API_BASE}/system/host-probe`, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            return { ok: false, code: 'PROBE_FAILED', message: `HTTP ${res.status}` };
        }
        const parsed = await res.json().catch(() => null);
        if (!parsed || typeof parsed !== 'object') {
            return { ok: false, code: 'PROBE_FAILED', message: 'Resposta vazia.' };
        }

        if (parsed.status === 'success' && parsed.data) {
            return { ok: true, data: parsed.data };
        }
        const code = (parsed.code as HostProbeResult extends { ok: false; code: infer C } ? C : never) ?? 'PROBE_FAILED';
        return { ok: false, code, message: parsed.message || 'Falha desconhecida.' };
    } catch (e: unknown) {
        return { ok: false, code: 'NETWORK', message: e instanceof Error ? e.message : String(e) };
    }
}
