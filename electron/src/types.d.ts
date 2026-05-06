export { };

declare global {
    interface Window {
        electron: {
            ipcRenderer: {
                invoke(channel: string, ...args: any[]): Promise<any>;
                send(channel: string, ...args: any[]): void;
                on(channel: string, func: (...args: any[]) => void): void;
                removeAllListeners(channel: string): void;
            };
            launchRdp(ip: string): Promise<void>;
            launchMsra(ip: string, askCredentials?: boolean): Promise<void>;
            launchTeamViewer(id?: string): Promise<void>;
            openExternal(url: string): Promise<void>;
            getLocalDomain(): Promise<string>;
            showItemInFolder(path: string): Promise<void>;
            saveFileAs(filename: string, content: string): Promise<string | null>;
        };
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
