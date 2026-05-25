// `package.json` is the single source of truth for the app version. The
// changelog entries below remain manual — only the bare version string is
// resolved from package.json so a release bump only requires editing
// package.json + appending one entry here.
import pkg from '../../package.json';

export const APP_VERSION: string = pkg.version;

export type ChangeKind = 'feat' | 'fix' | 'perf' | 'security' | 'ui' | 'refactor' | 'docs';

export interface ChangelogEntry {
    version: string;
    date: string;       // ISO date (YYYY-MM-DD)
    title?: string;     // optional one-line theme for the release
    changes: { kind: ChangeKind; text: string }[];
}

export const CHANGELOG: ChangelogEntry[] = [
    {
        version: '1.2.4',
        date: '2026-05-11',
        title: 'Coleta oportunista de informações + UX refinada',
        changes: [
            { kind: 'feat', text: 'Botão "Guia de Comandos" no Terminal Remoto abre modal de consulta rápida com snippets PowerShell organizados por seção (rede, diagnósticos, disco, usuários/sessões, sistema/processos). Cada bloco tem botão de copiar e os destrutivos têm aviso amarelo (logoff, Restart-Computer -Force, Disable-NetAdapter etc.). Busca por palavra-chave.' },
            { kind: 'feat', text: 'Popup de detalhes do host agora mostra "Offline desde X" quando o monitor detectou uma transição online→offline, com wall-clock e label relativo "há X" que tica enquanto o popup está aberto. Limpado automaticamente quando o host volta a responder.' },
            { kind: 'fix', text: 'Campo "Endereço IP" do popup de detalhes mostrava o hostname quando o host era cadastrado pelo nome (e o monitor ainda não tinha resolvido). Agora um helper ipForHost(host) prefere stats.ip → host.ip → host.address (todos validados como literal IPv4). Quando nada bate, exibe "Não disponível" em vez do hostname.' },
            { kind: 'fix', text: 'PATCH /hosts/{address} agora aceita lookup case-insensitive e cai para match por host.ip quando o caller envia o IP resolvido em vez da PK. Frontend URL-encoda o address e surfaca o detail do backend no console em caso de erro (não mais "Erro ao atualizar" genérico).' },
            { kind: 'feat', text: 'Quando o operador autentica em um host para qualquer ação (Terminal Remoto, TestConnection, Power Action, abrir Detalhes Avançados, buscar TeamViewer ID), agora coletamos em background MAC, domínio AD real, usuário atual, último boot e disco livre — tudo persistido sem o operador precisar fazer nada extra. Novo endpoint /system/host-probe + script PowerShell enxuto.' },
            { kind: 'feat', text: 'Confirmação pré-shutdown/restart: novo diálogo mostra uptime, sessões ativas e reinício pendente antes de mandar a ação. Auto-skip quando não há nada para avisar. Endpoint /system/pre-power-check + heurística shouldWarn.' },
            { kind: 'feat', text: 'Terminal Remoto agora tem picker de hosts do painel com busca, indicador online/offline e opção "Digitar manualmente". Selecionar um host preenche o IP e o prefixo de domínio (DOMINIO\\) automaticamente; trocar de host troca o domínio preservando a parte do usuário.' },
            { kind: 'feat', text: 'Card TeamViewer no Acesso Remoto agora tem 4 estados (sucesso/loading/needs_credentials/failed) com form inline de credenciais quando o vault não pode atender — sem mais instruções manuais.' },
            { kind: 'feat', text: 'Apelido do host (campo "Apelido" do AddHost) agora é separado do hostname resolvido por DNS — antes o reverse DNS sobrescrevia o apelido. Card mostra apelido se houver, senão hostname; HostDetails/RDP continuam usando o hostname real.' },
            { kind: 'fix', text: 'Assistência Remota (msra) com path absoluto + arguments via array PS — corrige caso em que o MSRA abria sem efetivar o /offerRA. "Executar como outro usuário" também ajustado.' },
            { kind: 'fix', text: 'Remover host a partir do popup de detalhes agora fecha o popup automaticamente (antes ficava exibindo um host removido).' },
            { kind: 'fix', text: 'DeleteHost e ConfirmationModal agora em z-[110], ficam acima do HostDetailsModal (z-[100]) — antes a confirmação renderizava atrás do popup pai.' },
            { kind: 'fix', text: 'Esconder "% de perda" no card quando o host está offline (já redundante com "HOST OFFLINE"); critério de online agora consolidado (não pisca verde em pingue isolado dentro de 96% de perda).' },
            { kind: 'perf', text: 'Persistência granular: atualizações de status do monitor agora usam UPDATE de coluna em vez de DELETE+INSERT da tabela inteira (era o gargalo principal em 100+ hosts). PATCH /hosts/{address} também tem caminho rápido.' },
            { kind: 'perf', text: 'Monitor migrado de 1 thread/host para ThreadPoolExecutor(64) com scheduler único — escala para 500+ hosts sem esgotar handles do Windows.' },
            { kind: 'perf', text: 'Code splitting: Tools, Settings, HostDetails, Security e Terminal viraram chunks lazy. Bundle inicial de 1067KB → 666KB.' },
            { kind: 'security', text: 'launchMsra/launchRdp do pywebview validam IP e passam via env var (não interpolam em string PowerShell). 25 except: bare removidos. sandbox: true + CSP no Electron. Preload restrito (sem ipcRenderer genérico).' },
            { kind: 'refactor', text: 'Versão unificada: agora vem só de electron/package.json (settings.py lê em runtime, build_webview.spec lê no build, changelog.ts importa). server.py / não tem mais hardcode "2.0.0".' },
        ],
    },
    {
        version: '1.2.3',
        date: '2026-05-06',
        title: 'Build portátil + fluxo de TrustedHosts mais inteligente',
        changes: [
            { kind: 'fix', text: 'Reiniciar/Desligar/Logoff/Mensagem em hosts cross-domain agora abre a modal de TrustedHosts em vez de mostrar um toast vermelho críptico. O backend perdia o code estruturado ao transmitir o erro pelo streaming NDJSON; consertado em _stream_winrm_command.' },
            { kind: 'feat', text: 'Modal de TrustedHosts agora detecta automaticamente quando o alvo está em um domínio diferente do seu (USERDNSDOMAIN vs networks[].domain) e sugere o formato usuario@dominio para evitar o gate.' },
            { kind: 'feat', text: 'Checkbox "Não perguntar de novo nesta sessão" na modal — aprovação fica em memória do app e expira ao fechar. TrustedHosts continua sendo adicionado e removido a cada operação no servidor.' },
            { kind: 'feat', text: 'Endpoint /system/diagnose-target retorna o domínio do alvo (via Settings) e o domínio local do operador para alimentar a modal contextual.' },
            { kind: 'fix', text: 'Build portátil v1.2.2 quebrava no boot por três deps que setuptools 80 desbundled (jaraco.text, platformdirs) e por um import legado (customtkinter). Spec PyInstaller agora coleta jaraco.*/platformdirs/importlib_*/pkg_resources via collect_all e src.system.AdvancedPerformanceOptimizer virou lazy import.' },
            { kind: 'fix', text: 'Frontend portátil falhava ao carregar configurações/interfaces porque o WebView servia a UI numa porta aleatória fora da whitelist de CORS. Agora a porta é fixa (NT_WEBVIEW_PORT, default 5174) e está na whitelist por padrão.' },
        ],
    },
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
