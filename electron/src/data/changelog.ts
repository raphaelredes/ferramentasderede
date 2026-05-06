// Single source of truth for app version and release history.
// AboutModal renders the version as a clickable element that opens a popup
// with this list. LoadingScreen also reads APP_VERSION from here.

export const APP_VERSION = '1.2.2';

export type ChangeKind = 'feat' | 'fix' | 'perf' | 'security' | 'ui' | 'refactor' | 'docs';

export interface ChangelogEntry {
    version: string;
    date: string;       // ISO date (YYYY-MM-DD)
    title?: string;     // optional one-line theme for the release
    changes: { kind: ChangeKind; text: string }[];
}

export const CHANGELOG: ChangelogEntry[] = [
    {
        version: '1.2.2',
        date: '2026-05-06',
        title: 'Suporte multi-domínio / multi-VLAN e endurecimento técnico',
        changes: [
            { kind: 'feat', text: 'Aba "Redes / VLANs" em Configurações com detecção automática de NICs locais (psutil) e CRUD de redes gerenciadas (CIDR, source IP, DNS server, domínio AD).' },
            { kind: 'feat', text: 'Ping, Traceroute e Scanner aceitam um source IP — o pacote sai pela NIC certa em ambientes com múltiplas VLANs (ping -S no Windows, ping -I no Linux).' },
            { kind: 'feat', text: 'Resolução DNS pode usar um servidor específico por rede (dnspython). Quando um host pertence a uma rede com DNS cadastrado, o "Atualizar host" usa esse DNS antes do resolver do sistema.' },
            { kind: 'feat', text: 'Dashboard mostra um badge azul com o nome da rede em cada card e tem uma linha extra de filtros para filtrar hosts por rede.' },
            { kind: 'feat', text: 'Quick-action de Ping/Traceroute no card pré-seleciona automaticamente o source IP da rede do host.' },
            { kind: 'feat', text: 'WinRM tenta variantes de username automaticamente em ambiente cross-domain (DOMINIO\\user, user@dominio) quando a rede do host-alvo tem o domínio cadastrado.' },
            { kind: 'feat', text: 'WinRM agora classifica falhas em códigos acionáveis: AUTH_FAILED, CROSS_DOMAIN_AUTH, NETWORK_UNREACHABLE, WINRM_DISABLED, TRUSTED_HOSTS_REQUIRED — com mensagem específica em português.' },
            { kind: 'security', text: 'Backend bind em 127.0.0.1 por padrão (era 0.0.0.0). CORS travado em localhost:5173. Override via NT_API_HOST e NT_CORS_ORIGINS quando precisar.' },
            { kind: 'security', text: 'Terminal externo (PowerShell remoto) recebe IP/usuário/senha via env vars que o script remove na entrada. Senha não aparece mais em Get-History nem na linha de comando do processo.' },
            { kind: 'security', text: 'Validação rigorosa em todos os IPC do Electron (RDP, MSRA, TeamViewer, openExternal, showItemInFolder, saveFileAs) — argumentos maliciosos são rejeitados.' },
            { kind: 'perf', text: 'SQLite com busy_timeout, retry exponencial nos writes e lock de processo. Sem mais "database is locked" sob carga de monitoramento.' },
            { kind: 'perf', text: 'Resolução de DNS / MAC no monitor agora roda em ThreadPoolExecutor (16 workers). Ciclo completo de 100+ hosts cai de minutos para segundos.' },
            { kind: 'perf', text: 'Vendor lookup não bloqueia mais o startup tentando baixar a base OUI. Fallback embutido cobre Dell, HP, Lenovo, Cisco, Ubiquiti, VMware, Hyper-V, QEMU e impressoras.' },
            { kind: 'ui', text: 'Polling com backoff exponencial (2s → 30s) quando o backend cai, com toast de "desconectado" e "conexão restaurada".' },
            { kind: 'ui', text: 'Reset/criação do cofre não recarrega mais a app inteira — preserva aba aberta, scroll e estado.' },
            { kind: 'ui', text: 'URLs do backend centralizadas em src/config/api.ts — configurável via VITE_API_HOST / VITE_API_PORT.' },
            { kind: 'fix', text: 'Dashboard tolera hosts com name/address null sem quebrar (eram bugs de "Cannot read properties of null").' },
            { kind: 'fix', text: 'Logs (errors.log, terminal_debug.log, debug_sessions.txt) agora vão para %APPDATA%\\FerramentasDeRede\\ — antes ficavam no Desktop ou no diretório de execução.' },
            { kind: 'fix', text: 'Removidas duplicações de rotas (refresh_host, update_host) que o FastAPI estava silenciosamente mascarando.' },
            { kind: 'refactor', text: 'Dashboard.tsx 105 linhas mais leve — extraído GroupNetworkTabs e hook useFilteredHosts memoizado.' },
            { kind: 'docs', text: 'Plano de testes offline em TESTES.html com 27 testes organizados em 9 seções, abertura em qualquer navegador.' },
        ],
    },
    {
        version: '1.2.1',
        date: '2025-12-XX',
        title: 'Strict trash collision e atomic DB updates',
        changes: [
            { kind: 'feat', text: 'Sistema de exclusão estrito por colisão de cursor com lixeira.' },
            { kind: 'feat', text: 'Atualizações atômicas no banco de dados.' },
            { kind: 'ui', text: 'Multi-Row Tab System.' },
            { kind: 'ui', text: 'Sistema completo de shutdown da aplicação.' },
        ],
    },
    {
        version: '1.1',
        date: '2025-11-14',
        changes: [
            { kind: 'fix', text: 'Status das abas atualiza corretamente após adicionar hosts via Scanner de Rede.' },
            { kind: 'fix', text: 'Ícone na barra de tarefas em alta qualidade (PNG 256x256, interpolação LANCZOS).' },
            { kind: 'fix', text: 'UPX desabilitado para evitar erro "ordinal 380" em DLLs do Tcl/Tk.' },
            { kind: 'perf', text: 'Thread-safety na atualização de status de hosts.' },
            { kind: 'feat', text: 'Nome do executável inclui versão.' },
        ],
    },
    {
        version: '1.0',
        date: '2025-10-XX',
        title: 'Primeira versão',
        changes: [
            { kind: 'feat', text: 'Sistema de gerenciamento de hosts.' },
            { kind: 'feat', text: 'Scanner de rede local e remoto.' },
            { kind: 'feat', text: 'Ferramentas (ping, traceroute).' },
            { kind: 'feat', text: 'Comandos remotos via WinRM.' },
            { kind: 'feat', text: 'Sistema de credenciais seguras.' },
            { kind: 'feat', text: 'Interface multi-abas responsiva.' },
            { kind: 'feat', text: 'Suporte a múltiplos idiomas (PT-BR, EN-US, ES-ES).' },
        ],
    },
];
