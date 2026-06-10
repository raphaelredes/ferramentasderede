import type { Host, HostStatistics } from '../types';

// IPv4 literal shape (no octet bounds — they're enforced upstream when the
// monitor / backend produce these strings).
const IPV4_RE = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;

/**
 * Returns the host's real IPv4 string, or null if nothing IP-shaped is
 * available yet. Resolution order:
 *
 *   1. `stats.ip` — monitor's freshly-resolved IP (in-memory, may be ahead
 *      of the persisted column when DNS just resolved).
 *   2. `host.ip` — backend-stored IPv4 (from the DB `resolved_ip` column or
 *      from `address` when that's already an IPv4).
 *   3. `host.address` — only when it's already an IPv4 literal.
 *
 * Each candidate is validated against the IPv4 shape so a hostname (e.g.
 * `srv01.acme.local`) never leaks into the "IP" column of the card / popup.
 *
 * When the backend can't resolve the host's IPv4 yet (newly added, DNS down),
 * this returns null and the UI should render a "Resolvendo..." / "Não
 * disponível" placeholder instead of falling back to the hostname.
 */
export function ipForHost(host: Pick<Host, 'ip' | 'address'> & { stats?: HostStatistics | undefined }): string | null {
    const statsIp = host.stats?.ip;
    if (statsIp && IPV4_RE.test(statsIp)) return statsIp;
    if (host.ip && IPV4_RE.test(host.ip)) return host.ip;
    if (host.address && IPV4_RE.test(host.address)) return host.address;
    return null;
}
