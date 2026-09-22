import { useState, useMemo, type ReactNode } from 'react';
import {
    Router,
    Search,
    Layers,
    ListTree,
    Activity,
    AlertTriangle,
    ShieldAlert,
    ShieldCheck,
    Lock,
    Copy,
    Check,
    Terminal,
    ChevronDown,
    ChevronUp,
    CheckCircle2
} from 'lucide-react';
import { clsx } from 'clsx';
import { API_BASE } from '../../config/api';
import { useToast } from '../../contexts/ToastContext';
import { usePersistedState } from '../../hooks/usePersistedState';
import { LastExecutionBadge } from './LastExecutionBadge';

interface SnmpSystemResult {
    ok: boolean;
    error?: string;
    host?: string;
    community?: string;
    version?: string;
    sysDescr?: string;
    sysName?: string;
    sysUpTime?: string;
    sysContact?: string;
    sysLocation?: string;
    sysObjectID?: string;
    ifNumber?: number;
}

interface SnmpInterfaceItem {
    index: number;
    descr: string;
    type: string;
    speed: string;
    admin_status: string;
    oper_status: string;
    in_discards: number;
    in_errors: number;
    out_discards: number;
    out_errors: number;
    has_errors: boolean;
}

interface SnmpInterfacesResult {
    ok: boolean;
    error?: string;
    host?: string;
    total_interfaces: number;
    up_count: number;
    down_count: number;
    error_count: number;
    interfaces: SnmpInterfaceItem[];
}

interface SnmpWalkNode {
    oid: string;
    value: string;
    type: string;
}

interface SnmpWalkResult {
    ok: boolean;
    error?: string;
    host?: string;
    root_oid?: string;
    total_nodes: number;
    nodes: SnmpWalkNode[];
}

interface SnmpFinding {
    severity: string;
    title: string;
    desc: string;
}

interface SnmpSecurityAuditResult {
    ok: boolean;
    error?: string;
    host?: string;
    port?: number;
    version?: string;
    risk_score: number;
    risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'SECURE';
    risk_label: string;
    network?: {
        target: string;
        ip?: string;
        is_ip: boolean;
        network_type: string;
        is_private: boolean;
        description: string;
        warning?: string | null;
    };
    credentials?: {
        version: string;
        community?: string;
        is_weak: boolean;
        severity?: string;
        warning?: string | null;
        recommendation?: string | null;
    };
    protocol?: {
        version: string;
        is_encrypted: boolean;
        is_authenticated: boolean;
        cleartext_warning: boolean;
    };
    write_audit?: {
        ok: boolean;
        write_enabled: boolean;
        status: string;
        message: string;
        severity?: string;
    };
    snmpv3_probe?: {
        supported: boolean;
        details: string;
    };
    findings?: SnmpFinding[];
    recommendations?: string[];
}

const WEAK_COMMUNITIES = new Set([
    'public', 'private', 'cisco', 'switch', 'router', 'admin',
    'default', 'snmp', 'manager', 'community', 'monitor', 'test',
    'guest', 'root', 'read', 'write', 'secret'
]);

function isLikelyPublicWan(target: string): boolean {
    const t = target.trim();
    if (!t) return false;
    if (t === 'localhost' || t.startsWith('127.') || t === '::1') return false;
    if (t.endsWith('.local') || t.endsWith('.lan') || t.endsWith('.internal') || t.endsWith('.corp')) return false;

    // Suporte a IPv6 (Loopback ::1, Link-Local fe80::, ULA fd00:: vs Global Unicast WAN)
    if (t.includes(':')) {
        const lower = t.toLowerCase();
        if (lower === '::1' || lower.startsWith('fe80:') || lower.startsWith('fc00:') || lower.startsWith('fd')) {
            return false;
        }
        return true;
    }

    const m = t.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if (m) {
        const o1 = parseInt(m[1], 10);
        const o2 = parseInt(m[2], 10);
        if (o1 === 10) return false;
        if (o1 === 172 && o2 >= 16 && o2 <= 31) return false;
        if (o1 === 192 && o2 === 168) return false;
        if (o1 === 169 && o2 === 254) return false;
        if (o1 === 127) return false;
        return true;
    }
    return t.includes('.');
}

export function SnmpPanel() {
    const { showToast } = useToast();
    const [subTab, setSubTab] = usePersistedState<'system' | 'interfaces' | 'walk' | 'security'>('snmp_tool_subtab', 'system');
    const [host, setHost] = usePersistedState('snmp_tool_host', '10.0.0.1');
    const [community, setCommunity] = usePersistedState('snmp_tool_community', 'public');
    const [version, setVersion] = usePersistedState('snmp_tool_version', '2c');
    const [port, setPort] = usePersistedState('snmp_tool_port', '161');

    // Credenciais SNMPv3 USM
    const [v3User, setV3User] = usePersistedState('snmp_tool_v3_user', 'snmpadmin');
    const [v3AuthKey, setV3AuthKey] = usePersistedState('snmp_tool_v3_auth_key', '');
    const [v3PrivKey, setV3PrivKey] = usePersistedState('snmp_tool_v3_priv_key', '');
    const [v3AuthProto, setV3AuthProto] = usePersistedState('snmp_tool_v3_auth_proto', 'SHA256');
    const [v3PrivProto, setV3PrivProto] = usePersistedState('snmp_tool_v3_priv_proto', 'AES');
    const [v3SecLevel, setV3SecLevel] = usePersistedState('snmp_tool_v3_sec_level', 'authPriv');
    const [showV3Config, setShowV3Config] = useState(false);

    // Resultados por aba
    const [systemResult, setSystemResult, clearSystemResult] = usePersistedState<SnmpSystemResult | null>('snmp_tool_sys_res', null);
    const [ifResult, setIfResult, clearIfResult] = usePersistedState<SnmpInterfacesResult | null>('snmp_tool_if_res', null);
    const [walkResult, setWalkResult, clearWalkResult] = usePersistedState<SnmpWalkResult | null>('snmp_tool_walk_res', null);
    const [securityResult, setSecurityResult, clearSecurityResult] = usePersistedState<SnmpSecurityAuditResult | null>('snmp_tool_sec_res', null);

    const [walkOid, setWalkOid] = usePersistedState('snmp_tool_walk_oid', '1.3.6.1.2.1.1');
    const [lastRunAt, setLastRunAt] = usePersistedState<string | null>('snmp_tool_last_run', null);

    const [busy, setBusy] = useState(false);
    const [filterQuery, setFilterQuery] = useState('');
    const [hardeningVendor, setHardeningVendor] = useState<'cisco' | 'linux' | 'mikrotik'>('cisco');
    const [copiedSnippet, setCopiedSnippet] = useState(false);

    // Validação de integridade e requisitos RFC 3414
    const validateInputs = (): boolean => {
        const h = host.trim();
        if (!h) {
            showToast('Informe o host SNMP.', 'error');
            return false;
        }
        if (version === '3') {
            if (v3SecLevel !== 'noAuthNoPriv' && (!v3AuthKey || v3AuthKey.length < 8)) {
                showToast('A senha de autenticação SNMPv3 (AuthKey) deve conter no mínimo 8 caracteres (RFC 3414).', 'error');
                return false;
            }
            if (v3SecLevel === 'authPriv' && (!v3PrivKey || v3PrivKey.length < 8)) {
                showToast('A chave de privacidade SNMPv3 (PrivKey) deve conter no mínimo 8 caracteres (RFC 3414).', 'error');
                return false;
            }
        }
        return true;
    };

    // Build common payload
    const getPayload = (extra: Record<string, any> = {}) => ({
        host: host.trim(),
        community: community.trim(),
        port: parseInt(port, 10) || 161,
        version,
        v3_user: version === '3' ? (v3User.trim() || undefined) : undefined,
        v3_auth_key: version === '3' ? (v3AuthKey || undefined) : undefined,
        v3_priv_key: version === '3' ? (v3PrivKey || undefined) : undefined,
        v3_auth_proto: version === '3' ? v3AuthProto : undefined,
        v3_priv_proto: version === '3' ? v3PrivProto : undefined,
        v3_sec_level: version === '3' ? v3SecLevel : undefined,
        ...extra
    });

    const isWanTarget = useMemo(() => isLikelyPublicWan(host), [host]);
    const isWeakCommunity = useMemo(() => version !== '3' && WEAK_COMMUNITIES.has(community.trim().toLowerCase()), [version, community]);

    const querySystem = async () => {
        if (!validateInputs()) return;
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/snmp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getPayload({ timeout: 4.0 })),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setSystemResult(data);
            setLastRunAt(new Date().toISOString());
        } catch (e: any) {
            showToast('Erro: ' + e.message, 'error');
        } finally {
            setBusy(false);
        }
    };

    const queryInterfaces = async () => {
        if (!validateInputs()) return;
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/snmp/interfaces`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getPayload({ timeout: 4.0 })),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setIfResult(data);
            setLastRunAt(new Date().toISOString());
            showToast(`Mapeamento concluído: ${data.total_interfaces} interfaces encontradas.`, 'success');
        } catch (e: any) {
            showToast('Erro ao varrer interfaces: ' + e.message, 'error');
        } finally {
            setBusy(false);
        }
    };

    const runWalk = async () => {
        if (!validateInputs()) return;
        if (!walkOid.trim()) { showToast('Informe o OID inicial.', 'error'); return; }
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/snmp/walk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getPayload({ root_oid: walkOid.trim(), max_rows: 100, timeout: 3.5 })),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setWalkResult(data);
            setLastRunAt(new Date().toISOString());
            showToast(`Walk finalizado: ${data.total_nodes} nós coletados.`, 'success');
        } catch (e: any) {
            showToast('Erro no SNMP Walk: ' + e.message, 'error');
        } finally {
            setBusy(false);
        }
    };

    const querySecurityAudit = async () => {
        if (!validateInputs()) return;
        setBusy(true);
        try {
            const res = await fetch(`${API_BASE}/tools/snmp/security-audit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getPayload({ timeout: 3.5 })),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            setSecurityResult(data);
            setLastRunAt(new Date().toISOString());
            if (data.risk_score >= 70) {
                showToast(`Auditoria finalizada: Risco Crítico identificado (Score: ${data.risk_score}/100)`, 'warning');
            } else if (data.risk_score === 0) {
                showToast('Auditoria finalizada: Postura Fortalecida (Score: 0/100).', 'success');
            } else {
                showToast(`Auditoria finalizada: ${data.risk_label} (Score: ${data.risk_score}/100)`, 'info');
            }
        } catch (e: any) {
            showToast('Erro na auditoria de segurança SNMP: ' + e.message, 'error');
        } finally {
            setBusy(false);
        }
    };

    const handleCopyHardening = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopiedSnippet(true);
        showToast('Comandos de hardening copiados para a área de transferência!', 'success');
        setTimeout(() => setCopiedSnippet(false), 2500);
    };

    // Filtro de portas
    const filteredInterfaces = useMemo(() => {
        if (!ifResult?.interfaces) return [];
        if (!filterQuery.trim()) return ifResult.interfaces;
        const q = filterQuery.toLowerCase();
        return ifResult.interfaces.filter(i =>
            i.descr.toLowerCase().includes(q) ||
            i.type.toLowerCase().includes(q) ||
            i.oper_status.toLowerCase().includes(q)
        );
    }, [ifResult, filterQuery]);

    const Row = ({ label, value }: { label: string; value?: ReactNode }) => (
        <div className="flex gap-3 py-1.5 border-b border-zinc-900 text-xs">
            <span className="text-zinc-500 w-36 shrink-0">{label}</span>
            <span className="text-zinc-200 font-mono break-all">{value ?? '—'}</span>
        </div>
    );

    // Hardening Code Snippets
    const hardeningGuides = {
        cisco: `! ========================================================
! CISCO IOS / XE - HARDENING SNMP (NIST SP 800-123 & CISA)
! ========================================================

! 1. Desativar comunidades fracas e não criptografadas v1/v2c
no snmp-server community public
no snmp-server community private

! 2. Criar Visão MIB Restrita (Limita acesso a OIDs de risco)
snmp-server view V3VIEW iso included

! 3. Criar Grupo SNMPv3 com criptografia (authPriv)
snmp-server group SECGROUP v3 priv read V3VIEW write V3VIEW

! 4. Criar Usuário USM com SHA-256 e AES-128
snmp-server user ${v3User || 'snmpadmin'} SECGROUP v3 auth sha256 SenhaForteAuth123! priv aes 128 SenhaFortePriv123!

! 5. Restringir acesso exclusivamente por ACL à estação NOC
ip access-list standard ACL-SNMP-MGMT
 permit 192.168.1.50
 deny any
snmp-server group SECGROUP v3 priv access ACL-SNMP-MGMT`,

        linux: `# ========================================================
# LINUX / NET-SNMP (/etc/snmp/snmpd.conf)
# ========================================================

# 1. Parar o serviço snmpd antes de registrar usuário
# sudo systemctl stop snmpd

# 2. Criar usuário seguro SNMPv3 com SHA-256 e AES
# sudo net-snmp-create-v3-user -ro -A SenhaForteAuth123! -a SHA-256 -X SenhaFortePriv123! -x AES ${v3User || 'snmpadmin'}

# 3. Em /etc/snmp/snmpd.conf, garanta acesso apenas com authPriv:
rouser ${v3User || 'snmpadmin'} priv

# 4. Vincular somente à interface de gerência (OOBM) ou loopback:
agentaddress 127.0.0.1:161,192.168.10.1:161

# 5. Reiniciar o serviço
# sudo systemctl restart snmpd`,

        mikrotik: `# ========================================================
# MIKROTIK ROUTEROS (CLI)
# ========================================================

# 1. Desabilitar comunidade padrão 'public'
/snmp community set [find name=public] disabled=yes

# 2. Adicionar comunidade SNMPv3 com SHA-256 e AES
/snmp community add name=${v3User || 'snmpadmin'} security=private \\
  authentication-protocol=SHA256 authentication-password="SenhaForteAuth123!" \\
  encryption-protocol=AES encryption-password="SenhaFortePriv123!" \\
  read-access=yes write-access=no addresses=192.168.1.50/32

# 3. Forçar uso de SNMPv3 no RouterOS
/snmp set enabled=yes trap-version=3`
    };

    return (
        <div className="flex-1 flex flex-col space-y-3 min-h-0">
            {/* Controles de Conexão SNMP */}
            <div className="bg-zinc-900 p-4 rounded-xl border border-zinc-800 space-y-3 shrink-0">
                <div className="flex flex-wrap gap-3 items-end">
                    <div className="flex-1 min-w-[200px] space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Host (Switch / Roteador)
                        </label>
                        <input
                            type="text"
                            value={host}
                            onChange={e => setHost(e.target.value)}
                            onFocus={() => { if (host === '10.0.0.1') setHost(''); }}
                            placeholder="10.0.0.1 ou switch-core.local"
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3.5 py-2 text-white focus:outline-none focus:border-blue-500 font-mono text-sm"
                        />
                    </div>

                    {version !== '3' && (
                        <div className="w-40 space-y-1.5">
                            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center justify-between">
                                <span>Community</span>
                                {isWeakCommunity && (
                                    <span className="text-[10px] text-rose-400 font-bold">Fraca</span>
                                )}
                            </label>
                            <input
                                type="text"
                                value={community}
                                onChange={e => setCommunity(e.target.value)}
                                className={clsx(
                                    "w-full bg-zinc-950 border rounded-lg px-3 py-2 text-white focus:outline-none font-mono text-sm",
                                    isWeakCommunity ? "border-amber-500/70 focus:border-amber-400" : "border-zinc-700 focus:border-blue-500"
                                )}
                            />
                        </div>
                    )}

                    <div className="w-28 space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Versão
                        </label>
                        <select
                            value={version}
                            onChange={e => {
                                setVersion(e.target.value);
                                if (e.target.value === '3') setShowV3Config(true);
                            }}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-2.5 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="2c">v2c</option>
                            <option value="3">v3 (USM)</option>
                            <option value="1">v1</option>
                        </select>
                    </div>

                    <div className="w-20 space-y-1.5">
                        <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Porta
                        </label>
                        <input
                            type="text"
                            value={port}
                            onChange={e => setPort(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-2.5 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono text-center"
                        />
                    </div>

                    <button
                        onClick={
                            subTab === 'system' ? querySystem :
                            subTab === 'interfaces' ? queryInterfaces :
                            subTab === 'walk' ? runWalk : querySecurityAudit
                        }
                        disabled={busy}
                        className={clsx(
                            "flex items-center gap-2 px-5 py-2 rounded-lg font-semibold text-white shadow-md transition-all text-sm disabled:opacity-60",
                            subTab === 'security'
                                ? "bg-amber-600 hover:bg-amber-500 shadow-amber-600/20"
                                : "bg-blue-600 hover:bg-blue-500 shadow-blue-600/20"
                        )}
                    >
                        {busy ? <Activity size={16} className="animate-spin" /> : (
                            subTab === 'security' ? <ShieldAlert size={16} /> : <Search size={16} />
                        )}
                        {subTab === 'system' ? 'Consultar Sistema' :
                         subTab === 'interfaces' ? 'Mapear Interfaces' :
                         subTab === 'walk' ? 'Iniciar Walk' : 'Auditar Postura'}
                    </button>
                </div>

                {/* Pre-Flight Warning Banner: WAN Pública + v1/v2c */}
                {version !== '3' && isWanTarget && (
                    <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-2.5 flex items-start gap-2.5 text-xs text-rose-300">
                        <AlertTriangle size={16} className="text-rose-400 shrink-0 mt-0.5" />
                        <div>
                            <strong className="text-rose-200">Alerta de Risco (Exposição WAN / Texto Claro):</strong>
                            <p className="text-rose-300/90 mt-0.5">
                                O host <code>{host}</code> aparenta ser um IP ou domínio público na Internet. O tráfego de SNMPv{version} trafega sem cifragem sobre UDP 161, permitindo interceptação da community <code>'{community}'</code> por nós de trânsito. Migre para <strong>SNMPv3 (authPriv com AES)</strong> ou utilize VPN dedicada.
                            </p>
                        </div>
                    </div>
                )}

                {/* Sub-painel SNMPv3 USM Credentials */}
                {version === '3' && (
                    <div className="bg-zinc-950 p-3 rounded-lg border border-blue-900/40 space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-blue-400 flex items-center gap-1.5">
                                <Lock size={14} />
                                Credenciais USM (SNMPv3 Criptografado - RFC 3414)
                            </span>
                            <button
                                type="button"
                                onClick={() => setShowV3Config(!showV3Config)}
                                className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
                            >
                                {showV3Config ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                <span>{showV3Config ? 'Recolher Parâmetros' : 'Expandir Parâmetros'}</span>
                            </button>
                        </div>

                        {showV3Config && (
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1 border-t border-zinc-900">
                                <div className="space-y-1">
                                    <label className="text-[11px] font-semibold text-zinc-400">Usuário USM (SecurityName)</label>
                                    <input
                                        type="text"
                                        value={v3User}
                                        onChange={e => setV3User(e.target.value)}
                                        placeholder="snmpadmin"
                                        className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-semibold text-zinc-400">Nível de Segurança</label>
                                    <select
                                        value={v3SecLevel}
                                        onChange={e => setV3SecLevel(e.target.value)}
                                        className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                                    >
                                        <option value="authPriv">authPriv (Autenticação + Cifragem AES)</option>
                                        <option value="authNoPriv">authNoPriv (Apenas Autenticação)</option>
                                        <option value="noAuthNoPriv">noAuthNoPriv (Sem Auth / Sem Cifra)</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-semibold text-zinc-400">Algoritmo de Autenticação</label>
                                    <select
                                        value={v3AuthProto}
                                        disabled={v3SecLevel === 'noAuthNoPriv'}
                                        onChange={e => setV3AuthProto(e.target.value)}
                                        className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono disabled:opacity-40"
                                    >
                                        <option value="SHA256">HMAC-SHA-256 (Recomendado)</option>
                                        <option value="SHA">HMAC-SHA-1</option>
                                        <option value="MD5">HMAC-MD5 (Legado)</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-semibold text-zinc-400">Senha de Autenticação (AuthKey)</label>
                                    <input
                                        type="password"
                                        value={v3AuthKey}
                                        disabled={v3SecLevel === 'noAuthNoPriv'}
                                        onChange={e => setV3AuthKey(e.target.value)}
                                        placeholder="Chave mínima de 8 caracteres"
                                        className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono disabled:opacity-40"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-semibold text-zinc-400">Algoritmo de Cifra (PrivProto)</label>
                                    <select
                                        value={v3PrivProto}
                                        disabled={v3SecLevel !== 'authPriv'}
                                        onChange={e => setV3PrivProto(e.target.value)}
                                        className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono disabled:opacity-40"
                                    >
                                        <option value="AES">AES-128 (Padrão RFC 3826)</option>
                                        <option value="AES256">AES-256 (Alta Segurança)</option>
                                        <option value="DES">DES (Inseguro / Legado)</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[11px] font-semibold text-zinc-400">Chave de Privacidade (PrivKey)</label>
                                    <input
                                        type="password"
                                        value={v3PrivKey}
                                        disabled={v3SecLevel !== 'authPriv'}
                                        onChange={e => setV3PrivKey(e.target.value)}
                                        placeholder="Chave mínima de 8 caracteres"
                                        className="w-full bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono disabled:opacity-40"
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Sub-abas do SNMP */}
                <div className="flex items-center gap-2 pt-1 border-t border-zinc-800/80">
                    <button
                        type="button"
                        onClick={() => setSubTab('system')}
                        className={clsx(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                            subTab === 'system'
                                ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                                : "text-zinc-400 hover:text-zinc-200"
                        )}
                    >
                        <Router size={14} />
                        <span>Sistema & Métricas</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => setSubTab('interfaces')}
                        className={clsx(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                            subTab === 'interfaces'
                                ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                                : "text-zinc-400 hover:text-zinc-200"
                        )}
                    >
                        <Layers size={14} />
                        <span>Portas & Interfaces (ifTable)</span>
                        {ifResult?.interfaces && (
                            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-blue-500/30 text-blue-200">
                                {ifResult.interfaces.length}
                            </span>
                        )}
                    </button>
                    <button
                        type="button"
                        onClick={() => setSubTab('walk')}
                        className={clsx(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                            subTab === 'walk'
                                ? "bg-blue-600/20 text-blue-300 border border-blue-500/40"
                                : "text-zinc-400 hover:text-zinc-200"
                        )}
                    >
                        <ListTree size={14} />
                        <span>SNMP Walk Livre</span>
                    </button>
                    <button
                        type="button"
                        onClick={() => setSubTab('security')}
                        className={clsx(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                            subTab === 'security'
                                ? "bg-amber-600/20 text-amber-300 border border-amber-500/40"
                                : "text-zinc-400 hover:text-zinc-200"
                        )}
                    >
                        <ShieldAlert size={14} />
                        <span>Segurança & Riscos</span>
                        {securityResult?.risk_level && (
                            <span className={clsx(
                                "ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold",
                                securityResult.risk_level === 'CRITICAL' ? "bg-rose-500/30 text-rose-300" :
                                securityResult.risk_level === 'HIGH' ? "bg-orange-500/30 text-orange-300" :
                                securityResult.risk_level === 'MEDIUM' ? "bg-amber-500/30 text-amber-300" :
                                "bg-emerald-500/30 text-emerald-300"
                            )}>
                                {securityResult.risk_score}
                            </span>
                        )}
                    </button>
                </div>
            </div>

            {/* Badge de Última Execução */}
            {lastRunAt && (
                <LastExecutionBadge
                    timestamp={lastRunAt}
                    target={host || null}
                    onClear={() => {
                        clearSystemResult();
                        clearIfResult();
                        clearWalkResult();
                        clearSecurityResult();
                        setLastRunAt(null);
                    }}
                />
            )}

            {/* Conteúdo das Sub-abas */}
            <div className="flex-1 bg-black rounded-xl border border-zinc-800 overflow-hidden flex flex-col min-h-0">
                {subTab === 'system' && (
                    <div className="flex-1 p-5 overflow-auto custom-scrollbar">
                        {!systemResult ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8">
                                <Router size={48} className="mb-4 opacity-20 text-blue-400" />
                                <p className="text-sm font-medium text-zinc-400">Leitura Básica do Grupo System SNMP</p>
                                <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                    Identifica nome do switch (sysName), descrição de firmware (sysDescr), tempo de atividade (sysUpTime) e total de portas.
                                </p>
                            </div>
                        ) : systemResult.ok ? (
                            <div className="space-y-4">
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                                        <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Nome do Ativo</span>
                                        <span className="text-base font-bold font-mono text-zinc-100">{systemResult.sysName || '—'}</span>
                                    </div>
                                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                                        <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Uptime do Equipamento</span>
                                        <span className="text-base font-bold font-mono text-emerald-400">{systemResult.sysUpTime || '—'}</span>
                                    </div>
                                    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                                        <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">Total de Interfaces</span>
                                        <span className="text-base font-bold font-mono text-indigo-400">{systemResult.ifNumber ?? '—'}</span>
                                    </div>
                                </div>
                                <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4">
                                    <Row label="Descrição de Firmware" value={systemResult.sysDescr} />
                                    <Row label="Localização" value={systemResult.sysLocation} />
                                    <Row label="Contato" value={systemResult.sysContact} />
                                    <Row label="SysObjectID" value={systemResult.sysObjectID} />
                                    <Row label="Host / IP" value={systemResult.host} />
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-rose-500/10 border border-rose-900/40 rounded-xl text-rose-400 text-sm flex items-center gap-2">
                                <AlertTriangle size={16} />
                                <span>{systemResult.error}</span>
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'interfaces' && (
                    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                        {!ifResult ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8">
                                <Layers size={48} className="mb-4 opacity-20 text-blue-400" />
                                <p className="text-sm font-medium text-zinc-400">Tabela de Interfaces em Tempo Real (RFC 2863 ifTable)</p>
                                <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                    Mapeia todas as portas físicas do switch, reportando velocidade de negociação, estado UP/DOWN e contadores de erros de CRC/descarte de pacotes.
                                </p>
                            </div>
                        ) : ifResult.ok ? (
                            <div className="flex-1 flex flex-col min-h-0">
                                {/* Resumo de Portas e Campo de Filtro */}
                                <div className="p-3 bg-zinc-950 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-3 shrink-0">
                                    <div className="flex items-center gap-3">
                                        <span className="text-xs font-mono text-zinc-300">
                                            Total: <strong>{ifResult.total_interfaces}</strong>
                                        </span>
                                        <span className="text-xs font-mono text-emerald-400">
                                            UP: <strong>{ifResult.up_count}</strong>
                                        </span>
                                        <span className="text-xs font-mono text-zinc-500">
                                            DOWN: <strong>{ifResult.down_count}</strong>
                                        </span>
                                        {ifResult.error_count > 0 && (
                                            <span className="text-xs font-mono text-rose-400 font-bold bg-rose-500/15 px-2 py-0.5 rounded border border-rose-500/30">
                                                Com Erros: {ifResult.error_count}
                                            </span>
                                        )}
                                    </div>
                                    <div className="w-56">
                                        <input
                                            type="text"
                                            value={filterQuery}
                                            onChange={e => setFilterQuery(e.target.value)}
                                            placeholder="Filtrar por nome ou tipo..."
                                            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                                        />
                                    </div>
                                </div>

                                {/* Tabela de Portas */}
                                <div className="flex-1 overflow-auto custom-scrollbar">
                                    <table className="w-full text-xs font-mono">
                                        <thead className="sticky top-0 bg-zinc-950 text-zinc-400 border-b border-zinc-800 z-10">
                                            <tr>
                                                <th className="text-left px-3 py-2 font-semibold w-12">#</th>
                                                <th className="text-left px-3 py-2 font-semibold min-w-[160px]">Porta / Descrição</th>
                                                <th className="text-left px-3 py-2 font-semibold w-28">Tipo</th>
                                                <th className="text-center px-3 py-2 font-semibold w-20">Oper</th>
                                                <th className="text-center px-3 py-2 font-semibold w-20">Admin</th>
                                                <th className="text-right px-3 py-2 font-semibold w-24">Velocidade</th>
                                                <th className="text-right px-3 py-2 font-semibold w-28">Erros (In / Out)</th>
                                                <th className="text-right px-3 py-2 font-semibold w-28">Descartes</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-zinc-900">
                                            {filteredInterfaces.map(i => (
                                                <tr key={i.index} className="hover:bg-zinc-900/50 transition-colors">
                                                    <td className="px-3 py-2 text-zinc-500 font-bold">{i.index}</td>
                                                    <td className="px-3 py-2 text-zinc-200 font-semibold">{i.descr}</td>
                                                    <td className="px-3 py-2 text-zinc-400 text-[11px]">{i.type}</td>
                                                    <td className="px-3 py-2 text-center">
                                                        <span className={clsx(
                                                            "px-2 py-0.5 rounded text-[10px] font-bold",
                                                            i.oper_status === 'UP' ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-zinc-800 text-zinc-500"
                                                        )}>
                                                            {i.oper_status}
                                                        </span>
                                                    </td>
                                                    <td className="px-3 py-2 text-center text-zinc-400 text-[11px]">{i.admin_status}</td>
                                                    <td className="px-3 py-2 text-right text-indigo-300">{i.speed}</td>
                                                    <td className="px-3 py-2 text-right">
                                                        {i.has_errors ? (
                                                            <span className="text-rose-400 font-bold bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/30">
                                                                {i.in_errors} / {i.out_errors}
                                                            </span>
                                                        ) : (
                                                            <span className="text-zinc-600">0 / 0</span>
                                                        )}
                                                    </td>
                                                    <td className="px-3 py-2 text-right text-zinc-500">
                                                        {i.in_discards || i.out_discards ? `${i.in_discards} / ${i.out_discards}` : '0'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-rose-500/10 border border-rose-900/40 rounded-xl text-rose-400 text-sm flex items-center gap-2 m-4">
                                <AlertTriangle size={16} />
                                <span>{ifResult.error}</span>
                            </div>
                        )}
                    </div>
                )}

                {subTab === 'walk' && (
                    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                        <div className="p-3 bg-zinc-950 border-b border-zinc-800 flex items-center gap-3 shrink-0">
                            <span className="text-xs text-zinc-400 uppercase font-semibold">OID Raiz:</span>
                            <input
                                type="text"
                                value={walkOid}
                                onChange={e => setWalkOid(e.target.value)}
                                placeholder="1.3.6.1.2.1.1"
                                className="w-64 bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                            />
                            <button
                                onClick={runWalk}
                                disabled={busy}
                                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold"
                            >
                                Executar Walk
                            </button>
                        </div>
                        <div className="flex-1 overflow-auto custom-scrollbar p-3">
                            {!walkResult ? (
                                <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8">
                                    <ListTree size={48} className="mb-4 opacity-20 text-blue-400" />
                                    <p className="text-sm font-medium text-zinc-400">Varredura Livre de MIB SNMP</p>
                                    <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
                                        Percorre recursivamente a subárvore a partir do OID informado (limite de 100 registros por consulta).
                                    </p>
                                </div>
                            ) : walkResult.ok ? (
                                <div className="space-y-1">
                                    <div className="text-xs text-zinc-400 pb-2 border-b border-zinc-800">
                                        Nós retornados: <strong className="text-white">{walkResult.total_nodes}</strong>
                                    </div>
                                    <table className="w-full text-xs font-mono">
                                        <thead>
                                            <tr className="text-zinc-500 border-b border-zinc-900 text-left">
                                                <th className="py-1 px-2">OID</th>
                                                <th className="py-1 px-2">Tipo</th>
                                                <th className="py-1 px-2">Valor</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-zinc-900">
                                            {walkResult.nodes.map((n, idx) => (
                                                <tr key={idx} className="hover:bg-zinc-900/40">
                                                    <td className="py-1 px-2 text-blue-300 font-semibold select-all">{n.oid}</td>
                                                    <td className="py-1 px-2 text-zinc-500 text-[11px]">{n.type}</td>
                                                    <td className="py-1 px-2 text-zinc-200 break-all select-all">{n.value}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="p-4 bg-rose-500/10 border border-rose-900/40 rounded-xl text-rose-400 text-sm">
                                    {walkResult.error}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Sub-aba 4: Segurança & Riscos (NIST / CISA) */}
                {subTab === 'security' && (
                    <div className="flex-1 overflow-auto custom-scrollbar p-4 space-y-4">
                        {!securityResult ? (
                            <div className="h-full flex flex-col items-center justify-center text-zinc-600 p-8">
                                <ShieldAlert size={52} className="mb-4 opacity-25 text-amber-500" />
                                <p className="text-base font-semibold text-zinc-300">Auditoria Completa de Postura e Riscos SNMP</p>
                                <p className="text-xs text-zinc-500 mt-2 max-w-lg text-center leading-relaxed">
                                    Examina riscos em redes não-monitoradas / WAN, auditoria de communities fracas, teste não-destrutivo de privilégio de escrita (SET sysLocation) e sonda RFC 3414 para compatibilidade com SNMPv3.
                                </p>
                                <button
                                    onClick={querySecurityAudit}
                                    disabled={busy}
                                    className="mt-5 flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-amber-600/20 transition-all disabled:opacity-50"
                                >
                                    {busy ? <Activity size={16} className="animate-spin" /> : <ShieldAlert size={16} />}
                                    <span>Iniciar Auditoria de Segurança</span>
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {/* Banner de Score e Risco Global */}
                                <div className={clsx(
                                    "p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4",
                                    securityResult.risk_level === 'CRITICAL' ? "bg-rose-950/30 border-rose-800/60 text-rose-200" :
                                    securityResult.risk_level === 'HIGH' ? "bg-orange-950/30 border-orange-800/60 text-orange-200" :
                                    securityResult.risk_level === 'MEDIUM' ? "bg-amber-950/30 border-amber-800/60 text-amber-200" :
                                    "bg-emerald-950/30 border-emerald-800/60 text-emerald-200"
                                )}>
                                    <div className="flex items-center gap-3.5">
                                        {securityResult.risk_level === 'SECURE' || securityResult.risk_level === 'LOW' ? (
                                            <ShieldCheck size={36} className="text-emerald-400 shrink-0" />
                                        ) : (
                                            <ShieldAlert size={36} className={clsx(
                                                "shrink-0",
                                                securityResult.risk_level === 'CRITICAL' ? "text-rose-400" :
                                                securityResult.risk_level === 'HIGH' ? "text-orange-400" : "text-amber-400"
                                            )} />
                                        )}
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-lg font-bold">{securityResult.risk_label}</span>
                                                <span className={clsx(
                                                    "px-2 py-0.5 rounded text-xs font-mono font-bold uppercase",
                                                    securityResult.risk_level === 'CRITICAL' ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" :
                                                    securityResult.risk_level === 'HIGH' ? "bg-orange-500/20 text-orange-300 border border-orange-500/40" :
                                                    securityResult.risk_level === 'MEDIUM' ? "bg-amber-500/20 text-amber-300 border border-amber-500/40" :
                                                    "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                                                )}>
                                                    Nível {securityResult.risk_level}
                                                </span>
                                            </div>
                                            <p className="text-xs opacity-80 mt-1">
                                                Alvo: <span className="font-mono">{securityResult.host}</span> | Porta: <span className="font-mono">{securityResult.port}</span> | Versão testada: <span className="font-mono">{securityResult.version}</span>
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4 self-end sm:self-center">
                                        <div className="text-right">
                                            <span className="text-[10px] uppercase font-bold tracking-wider opacity-70 block">Score de Risco</span>
                                            <span className="text-2xl font-black font-mono">{securityResult.risk_score} <span className="text-xs font-normal opacity-60">/ 100</span></span>
                                        </div>
                                        <button
                                            onClick={querySecurityAudit}
                                            disabled={busy}
                                            className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded-lg text-xs font-semibold text-zinc-200 transition-colors"
                                        >
                                            Reauditar
                                        </button>
                                    </div>
                                </div>

                                {/* Grid de 4 Cards de Auditoria */}
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                                    {/* Card 1: Enlace de Rede */}
                                    <div className="bg-zinc-900/80 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Enlace de Rede</span>
                                            <span className={clsx(
                                                "px-2 py-0.5 rounded text-[10px] font-bold font-mono",
                                                securityResult.network?.is_private ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"
                                            )}>
                                                {securityResult.network?.network_type || 'DESCONHECIDO'}
                                            </span>
                                        </div>
                                        <p className="text-xs text-zinc-300 font-mono">
                                            {securityResult.network?.ip || securityResult.host}
                                        </p>
                                        <p className="text-[11px] text-zinc-500 leading-snug">
                                            {securityResult.network?.description}
                                        </p>
                                    </div>

                                    {/* Card 2: Community / Credencial */}
                                    <div className="bg-zinc-900/80 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Community</span>
                                            <span className={clsx(
                                                "px-2 py-0.5 rounded text-[10px] font-bold font-mono",
                                                securityResult.credentials?.is_weak ? "bg-rose-500/20 text-rose-300" : "bg-emerald-500/20 text-emerald-300"
                                            )}>
                                                {securityResult.credentials?.is_weak ? 'FRACA / DEFAULT' : 'CUSTOMIZADA'}
                                            </span>
                                        </div>
                                        <p className="text-xs text-zinc-300 font-mono">
                                            {securityResult.credentials?.community ? `"${securityResult.credentials.community}"` : 'USM Mode'}
                                        </p>
                                        <p className="text-[11px] text-zinc-500 leading-snug">
                                            {securityResult.credentials?.warning || 'Credencial não utiliza palavras padrão de fábrica conhecidas.'}
                                        </p>
                                    </div>

                                    {/* Card 3: Auditoria de Escrita RW */}
                                    <div className="bg-zinc-900/80 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Permissão SET (RW)</span>
                                            <span className={clsx(
                                                "px-2 py-0.5 rounded text-[10px] font-bold font-mono",
                                                securityResult.write_audit?.write_enabled ? "bg-rose-500/20 text-rose-300" : "bg-emerald-500/20 text-emerald-300"
                                            )}>
                                                {securityResult.write_audit?.write_enabled ? 'READ-WRITE (CRÍTICO)' : 'READ-ONLY (SEGURO)'}
                                            </span>
                                        </div>
                                        <p className="text-xs text-zinc-300 font-mono">
                                            Status: {securityResult.write_audit?.status || 'N/A'}
                                        </p>
                                        <p className="text-[11px] text-zinc-500 leading-snug">
                                            {securityResult.write_audit?.message || 'Teste não-destrutivo sobre sysLocation (1.3.6.1.2.1.1.6.0).'}
                                        </p>
                                    </div>

                                    {/* Card 4: Sonda SNMPv3 (RFC 3414) */}
                                    <div className="bg-zinc-900/80 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Suporte SNMPv3</span>
                                            <span className={clsx(
                                                "px-2 py-0.5 rounded text-[10px] font-bold font-mono",
                                                securityResult.snmpv3_probe?.supported ? "bg-blue-500/20 text-blue-300" : "bg-zinc-800 text-zinc-400"
                                            )}>
                                                {securityResult.snmpv3_probe?.supported ? 'DETECTADO' : 'INATIVO / SEM RESPOSTA'}
                                            </span>
                                        </div>
                                        <p className="text-xs text-zinc-300 font-mono truncate">
                                            {securityResult.snmpv3_probe?.supported ? 'RFC 3414 EngineID OK' : 'Sem descoberta USM'}
                                        </p>
                                        <p className="text-[11px] text-zinc-500 leading-snug">
                                            {securityResult.snmpv3_probe?.details}
                                        </p>
                                    </div>
                                </div>

                                {/* Apontamentos e Riscos Detectados */}
                                {securityResult.findings && securityResult.findings.length > 0 && (
                                    <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                                        <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                            <AlertTriangle size={15} className="text-amber-400" />
                                            Apontamentos & Vulnerabilidades Identificadas ({securityResult.findings.length})
                                        </span>
                                        <div className="space-y-2">
                                            {securityResult.findings.map((f, idx) => (
                                                <div key={idx} className="bg-zinc-950/70 border border-zinc-800/80 rounded-lg p-3 flex items-start gap-3">
                                                    <span className={clsx(
                                                        "px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase shrink-0 mt-0.5",
                                                        f.severity === 'CRITICAL' ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" :
                                                        f.severity === 'HIGH' ? "bg-orange-500/20 text-orange-300 border border-orange-500/40" :
                                                        f.severity === 'MEDIUM' ? "bg-amber-500/20 text-amber-300 border border-amber-500/40" :
                                                        "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                                                    )}>
                                                        {f.severity}
                                                    </span>
                                                    <div className="space-y-0.5">
                                                        <strong className="text-xs text-zinc-200 block">{f.title}</strong>
                                                        <p className="text-xs text-zinc-400 leading-relaxed">{f.desc}</p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Recomendações Práticas (NIST & CISA) */}
                                {securityResult.recommendations && securityResult.recommendations.length > 0 && (
                                    <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                                        <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                            <CheckCircle2 size={15} className="text-emerald-400" />
                                            Plano de Ação Recomendado (NIST SP 800-123 & CISA)
                                        </span>
                                        <ul className="space-y-1.5">
                                            {securityResult.recommendations.map((rec, idx) => (
                                                <li key={idx} className="text-xs text-zinc-300 flex items-start gap-2">
                                                    <span className="text-emerald-400 font-bold shrink-0 mt-0.5">•</span>
                                                    <span>{rec}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Guia Prático de Hardening (Cisco / Linux / MikroTik) */}
                                <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                                            <Terminal size={15} className="text-blue-400" />
                                            Guia Prático de Hardening (Comandos Prontos)
                                        </span>
                                        <div className="flex items-center gap-1.5 bg-zinc-950 p-1 rounded-lg border border-zinc-800">
                                            <button
                                                type="button"
                                                onClick={() => setHardeningVendor('cisco')}
                                                className={clsx(
                                                    "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                                                    hardeningVendor === 'cisco' ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-zinc-200"
                                                )}
                                            >
                                                Cisco IOS
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setHardeningVendor('linux')}
                                                className={clsx(
                                                    "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                                                    hardeningVendor === 'linux' ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-zinc-200"
                                                )}
                                            >
                                                Linux Net-SNMP
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setHardeningVendor('mikrotik')}
                                                className={clsx(
                                                    "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                                                    hardeningVendor === 'mikrotik' ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-zinc-200"
                                                )}
                                            >
                                                MikroTik RouterOS
                                            </button>
                                        </div>
                                    </div>

                                    <div className="relative">
                                        <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs font-mono text-zinc-300 overflow-x-auto custom-scrollbar leading-relaxed">
                                            {hardeningGuides[hardeningVendor]}
                                        </pre>
                                        <button
                                            type="button"
                                            onClick={() => handleCopyHardening(hardeningGuides[hardeningVendor])}
                                            className="absolute top-2.5 right-2.5 flex items-center gap-1.5 px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 rounded text-xs font-medium transition-colors shadow-md"
                                        >
                                            {copiedSnippet ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                                            <span>{copiedSnippet ? 'Copiado!' : 'Copiar'}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
