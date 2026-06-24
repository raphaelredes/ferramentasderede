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
        version: '1.2.7',
        date: '2026-06-24',
        title: 'Scanner identifica fabricante e tipo + abas fixas/persistentes',
        changes: [
            { kind: 'feat', text: 'Scanner de Rede agora identifica o FABRICANTE de cada dispositivo pelo MAC address (via OUI/IEEE). Funciona para hosts na mesma sub-rede do operador — em VLAN roteada o MAC não é visível através do roteador (limitação do ARP/L2), então fica vazio nesses casos. O MAC só carrega o fabricante: não existe (em nenhuma base do mundo) como descobrir o MODELO do dispositivo a partir do MAC.' },
            { kind: 'feat', text: 'Cards do scan ganham um rótulo de TIPO provável (Impressora, Câmera IP, Workstation Windows, Equipamento de rede, Máquina virtual, etc.) inferido combinando portas abertas + fabricante + hostname. Quando o tipo é incerto (só fabricante/hostname), aparece um ícone "?" com aviso no hover. Tipos por porta forte (9100=impressora, 554=câmera, 3389=RDP) são tratados como certos e não mostram o "?".' },
            { kind: 'feat', text: 'Abas do Scanner de Rede agora podem ser RENOMEADAS (duplo-clique no título) e FIXADAS (pin — aba fixada não fecha por acidente). As abas, com nomes e pins, sobrevivem ao fechar/reabrir o app (persistidas em localStorage), igual aos cards de host. Resultados de scan antigos não voltam — cada aba reabre "Pronta" para re-escanear.' },
            { kind: 'feat', text: 'Configurações → Scanner: novo toggle "Identificar fabricante no scan" (liga/desliga a etapa) e bloco "Base de fabricantes (IEEE OUI)" com contagem de registros, data de atualização e botão "Atualizar base". A atualização baixa a lista oficial da IEEE só sob demanda — o scan nunca baixa nada automaticamente (evita falso-negativo com proxy corporativo e alerta de IDS).' },
            { kind: 'fix', text: 'Lookup de fabricante é thread-safe: o dicionário de prefixos OUI é carregado UMA vez antes do pool de threads do scan e lido em memória — evita o crash de event-loop concorrente da biblioteca mac-vendor-lookup quando chamada dos N workers do discovery.' },
            { kind: 'fix', text: 'Cache da base de fabricantes movido para %APPDATA%\\FerramentasDeRede\\mac-vendors.txt (antes ficava em ~/.cache, que some no portátil PyInstaller). Atualização com escrita atômica (temp + rename) e validação por contagem de registros — um download interrompido não corrompe mais a base existente.' },
            { kind: 'perf', text: 'MAC resolvido com UMA leitura de "arp -a" ao fim do scan, cruzada por IP — em vez de um subprocesso arp por host (que com 50-256 workers spawava centenas de processos). Port-probe leve (connect_ex, sem subprocess) só nos hosts online.' },
            { kind: 'fix', text: 'closeScanSession (fechar aba do scanner) reescrito: a escolha da próxima aba ativa agora acontece dentro da própria função (a lógica antiga era admitidamente frágil e dependia de um efeito downstream). Abas fixadas não podem ser fechadas. Renomear inline resolve o conflito clique-vs-duplo-clique.' },
            { kind: 'fix', text: 'Export CSV do scanner passa a escapar aspas internas (RFC-4180) — antes um nome de fabricante com vírgula/aspas quebrava o CSV. Nova coluna "Tipo" no export.' },
        ],
    },
    {
        version: '1.2.6',
        date: '2026-06-10',
        title: 'Revisão profunda: replace_all_hosts não apaga mais campos novos',
        changes: [
            { kind: 'ui', text: 'Versão agora aparece no título da janela ("Ferramentas de Rede v1.2.6") tanto no portátil (pywebview) quanto no Electron dev — facilita identificar qual build está rodando.' },
            { kind: 'fix', text: 'Complemento crítico do fix do replace_all_hosts: o caller save_hosts_list (network.py) nunca POPULAVA resolved_ip/current_user/last_boot/system_disk_free_gb no dict enviado ao update_hosts — então mesmo com o INSERT corrigido, todo PATCH de nome/grupo/portas/monitoramento continuava zerando essas colunas. Verificado ao vivo: PATCH de nome/toggle agora preserva o IP resolvido na coluna do DB.' },
            { kind: 'fix', text: 'RemoteAccessModal e PrePowerActionModal mostravam host.ip || host.address no campo de IP — vazava o hostname para hosts cadastrados pelo nome. Agora usam o helper ipForHost (mesma disciplina do card/popup). Chamadas IPC de acesso remoto continuam aceitando hostname.' },
            { kind: 'fix', text: 'Forward-DNS do monitor agora tenta o dns_server/domínio de cada rede cadastrada antes de cair no resolver do sistema (multi-domínio determinístico). Antes resolvia cego pelo DNS primário da máquina.' },
            { kind: 'fix', text: 'Traceroute no Windows com NIC de origem selecionada agora emite um aviso visível no terminal ("o Windows tracert não suporta IP de origem; rota traçada pela interface padrão") em vez de só logar — o operador não é mais enganado achando que saiu pela VLAN escolhida.' },
            { kind: 'security', text: '/ws/terminal valida o IP de destino com _is_safe_remote_target antes de abrir a sessão WinRM (consistente com /tools/terminal/external). check_powershell_ping (dead code que interpolava IP em string PowerShell) removido. showItemInFolder do pywebview ganhou guard de path (null/traversal/UNC) espelhando o handler Electron.' },
            { kind: 'ui', text: 'Acessibilidade: modal "Adicionar/Editar Credencial" da tela de Segurança ganhou role=dialog + aria-modal + aria-labelledby + fechar com Escape e clique no backdrop, como os demais modais.' },
            { kind: 'fix', text: 'replace_all_hosts (DELETE+INSERT da tabela inteira, usado em todo PATCH de nome/grupo/portas/monitoramento) listava só 14 colunas no INSERT — não incluía resolved_ip, current_user, last_boot, system_disk_free_gb. Resultado: cada PATCH zerava o IP resolvido e os dados de host-probe (usuário atual, último boot, disco livre). O monitor reescrevia o IP em ~5s mas os campos do probe ficavam perdidos até a próxima autenticação. Agora o SQL é construído a partir da constante _WRITE_COLUMNS — adicionar uma coluna nova passa a ser único ponto de edição.' },
            { kind: 'fix', text: 'update_host_details(ip, mac=...) chamado pelo monitor disparava TypeError engolido pelo except — a assinatura só aceitava hostname e domain. MAC só chegava ao DB via outro caminho (callback do tick), escondendo o silent-fail. Agora aceita mac= também.' },
            { kind: 'fix', text: 'HostCard mostrava host.ip || host.address na coluna do IP, e o botão "Copiar IP" copiava host.address — para hosts cadastrados pelo nome isso vazava o hostname. Agora usa o helper ipForHost compartilhado com o popup (movido para utils/ipForHost.ts) com validação IPv4 estrita. Botão de copiar fica desabilitado enquanto resolução não termina.' },
            { kind: 'fix', text: 'Sort por IP em useFilteredHosts.ts virava NaN-compare quando o host era cadastrado pelo nome (hostname.split(".") = [NaN, NaN, ...]). Agora prefere host.ip resolvido e cai em 0.0.0.0 quando ambos são hostnames — sort estável.' },
            { kind: 'perf', text: '_dns_loop do monitor recriava um ThreadPoolExecutor(16) a cada ciclo de 5s — sob 100+ hosts isso era ~16 thread spawn/s gratuito. Agora o pool é persistente, criado uma vez e shutdown no fim do loop.' },
            { kind: 'refactor', text: 'Hook useHosts.ts (legado, não-importado) removido — 110 linhas de polling sem AbortController/backoff/null-safety que confundiam future-readers. MonitoringContext é o único caminho.' },
            { kind: 'refactor', text: 'electron-builder removido das devDependencies. O script "build" do package.json já estava neutralizado (aborta com mensagem apontando build_system.bat) — o pacote era dead weight cobrindo ~70% das 27 vulnerabilidades do npm audit.' },
        ],
    },
    {
        version: '1.2.5',
        date: '2026-05-27',
        title: 'Ações do card funcionando + IP real + Guia de Comandos',
        changes: [
            { kind: 'fix', text: 'CORS allow_methods agora inclui PATCH. Sem isso, o preflight OPTIONS respondia "GET, POST, PUT, DELETE, OPTIONS" e o WebView2 bloqueava toda PATCH cross-origin com TypeError "Failed to fetch" — os 4 botões do card (renomear apelido, adicionar porta, reiniciar métricas, alternar monitoramento) caíam silenciosamente. curl não dispara preflight, então o bug escapou de testes manuais.' },
            { kind: 'feat', text: 'host.ip agora é SEMPRE o IPv4 real, nunca o hostname. Nova coluna resolved_ip no DB persiste o forward-DNS resolvido (sobrevive restart). add_host faz resolução síncrona ao cadastrar pelo nome; refresh_host (botão do popup) força nova resolução com o dns_server da rede do host. _match_network passa a usar o IP resolvido para detectar VLAN.' },
            { kind: 'feat', text: 'Botão "Guia de Comandos" no Terminal Remoto abre modal de consulta rápida com snippets PowerShell organizados por seção (rede, diagnósticos, disco, usuários/sessões, sistema/processos). Cada bloco tem botão de copiar e os destrutivos têm aviso amarelo (logoff, Restart-Computer -Force, Disable-NetAdapter etc.). Busca por palavra-chave.' },
            { kind: 'feat', text: 'Popup de detalhes do host agora mostra "Offline desde X" quando o monitor detectou uma transição online→offline, com wall-clock e label relativo "há X" que tica enquanto o popup está aberto. Limpado automaticamente quando o host volta a responder.' },
            { kind: 'fix', text: 'Campo "Endereço IP" do popup de detalhes mostrava o hostname quando o host era cadastrado pelo nome. Agora um helper ipForHost(host) prefere stats.ip → host.ip → host.address (todos validados como literal IPv4). Quando nada bate, exibe "Não disponível" em vez do hostname.' },
            { kind: 'fix', text: 'PATCH /hosts/{address} agora aceita lookup em 4 níveis: exato → case-insensitive → host.ip → monitor.stats.ip. Cobre o caso em que o frontend envia o IP resolvido em vez da PK. Frontend URL-encoda o address e expõe o detail do backend no console em vez do genérico "Erro ao atualizar".' },
            { kind: 'fix', text: 'Ações do card foram unificadas no helper updateHost (URL-encode + response.ok check + erro real surfaceado). Toggle monitoramento agora retorna toast de erro quando falha (antes ignorava response.ok). Reiniciar Métricas aguarda a Promise antes de exibir "sucesso" — não mais mensagens enganosas.' },
            { kind: 'fix', text: 'Backend reset_host_stats agora faz lookup case-insensitive da key do monitor — quando o address sofreu drift de case (DNS reverse retornando lowercase), o reset deixava de funcionar silenciosamente.' },
            { kind: 'security', text: 'Hardening do portátil: NT_API_HOST/NT_API_PORT respeitados no main_webview.py (antes hardcoded 127.0.0.1:8000); /network/status com validação shape; saveFileAs do pywebview com validação de filename igual ao Electron handler; resolver do sistema substituído por dns_resolver no monitor + check_status; VaultContext com backoff exponencial em vez de setInterval fixo; electron-builder.yml removido e script "build" do package.json neutralizado.' },
            { kind: 'docs', text: 'Regra de release: a partir desta versão, toda atualização do .exe deve bumpar a versão (1.2.4 → 1.2.5 → …) e ter as correções listadas no AboutModal (CHANGELOG em changelog.ts). Aplicado no CLAUDE.md como regra obrigatória.' },
        ],
    },
    {
        version: '1.2.4',
        date: '2026-05-11',
        title: 'Coleta oportunista de informações + UX refinada',
        changes: [
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
