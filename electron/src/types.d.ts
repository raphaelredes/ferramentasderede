export { };

// Renderer-side type declarations. The `electron` bridge surface itself is
// declared in `electron/electron-env.d.ts` (ElectronBridge); here we only add
// the optional pywebview fallback the renderer still probes for some legacy
// flows.
declare global {
    interface Window {
        pywebview?: {
            api: {
                open_url: (url: string) => void;
                get_local_domain: () => Promise<string>;
                showItemInFolder: (path: string) => Promise<boolean>;
                saveFileAs: (filename: string, content: string) => Promise<string | null>;
            };
        };
    }
}

export interface HostStatistics {
    online: boolean;
    latency: number | null;
    average_latency: number | null;
    packet_loss: number;
    packet_loss_pct: number;
    total_packets: number;
    calibration_done: boolean;
    ip?: string;
    history?: { timestamp: number; latency: number; packet_loss: number }[];
    ports_status?: Record<number, boolean>;
    hostname?: string;
    domain?: string;
    vendor?: string;
    ports?: number[];
    stats?: HostStatistics;
    current_user?: string;
    is_smart_offline?: boolean;
    has_ever_been_online?: boolean;
    // ISO timestamp set the moment the host transitioned from online to
    // offline. Cleared (null/undefined) when it comes back up. The UI shows
    // "Offline desde X" in the host details popup.
    offline_since?: string | null;
}

export interface Host {
    name: string;
    address: string;
    mac?: string;
    type: string;
    hostname?: string;
    domain?: string;
    ip?: string;
    last_status?: boolean;
    last_checked?: string;
    group?: string;
    monitoring?: boolean;
    teamviewer_id?: string;
    vendor?: string;
    ports?: number[];
    stats?: HostStatistics;
    current_user?: string;
    // Opportunistic host-probe data, collected when the operator authenticates
    // against this host for any reason (Power Action, Terminal Remoto,
    // TestConnection, HostDetails). All optional — only set after a successful probe.
    last_boot?: string;
    system_disk_free_gb?: number;
    // Inferred by backend from settings.networks (multi-VLAN/multi-domain)
    network_id?: string;
    network_name?: string;
}

export interface HostUpdate extends Partial<Host> {
    reset_stats?: boolean;
    group?: string;
    mac?: string;
}

export interface Session {
    UserName: string;
    ID: string;
    State: string;
    SessionName: string;
    LogonTime?: string;
    Duration?: string;
}

export interface SystemInfo {
    os_name: string;
    os_version: string;
    os_arch: string;
    hostname: string;
    domain: string;
    manufacturer: string;
    model: string;
    processor: string;
    ram_total: string;
    ram_available: string;
    uptime: string;
    last_boot: string;
    bios_version: string;
    serial_number: string;
    CurrentUser?: string;
    SubnetMask?: string;
    Gateway?: string;
    DNSServers?: string;
    DHCPServer?: string;
    Interface?: string;
    LinkSpeed?: string;
    MACAddress?: string;
}

export interface Service {
    Name: string;
    DisplayName: string;
    Status: string;
    StartType: string;
}

export interface LogEntry {
    TimeCreated: string;
    Id: number;
    LevelDisplayName: string;
    ProviderName: string;
    Message: string;
}

export interface VaultCredential {
    id: string;
    name: string;
    username: string;
    description?: string;
}
