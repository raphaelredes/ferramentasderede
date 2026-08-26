export interface ToolHelpInfo {
    id: string;
    title: string;
    category: string;
    categoryLabel: string;
    summary: string;
    howItWorks: string[];
    useCases: string[];
    tips: string[];
    protocolsOrPorts?: string;
}

export const TOOLS_HELP_DATA: Record<string, ToolHelpInfo> = {
    ping: {
        id: 'ping',
        title: 'Ping (ICMP Echo)',
        category: 'diag',
        categoryLabel: 'Diagnóstico',
        summary: 'Mede a conectividade e a latência de ida e volta (RTT) entre este computador e um host de destino através do protocolo ICMP.',
        howItWorks: [
            'Envia pacotes ICMP Echo Request para o endereço IP ou Hostname informado.',
            'Aguarda a resposta ICMP Echo Reply do destino e calcula o tempo de resposta em milissegundos (ms).',
            'Computa em tempo real a taxa de perda de pacotes (Packet Loss %) e a estabilidade da linha.',
        ],
        useCases: [
            'Verificar rapidamente se um servidor, gateway, impressora ou roteador está ligado e acessível na rede.',
            'Detectar oscilações, jitter e perdas intermitentes de pacotes em links de rede local ou internet.',
            'Testar a estabilidade contínua de um host durante manutenções e reinicializações de serviços.',
        ],
        tips: [
            'Use o seletor "Sair pela rede" em ambientes multi-VLAN para forçar o teste a sair pela placa de rede correta.',
            'Se um servidor Windows não responder ao Ping, ele pode estar apenas com a regra de firewall ICMP desativada. Nesses casos, utilize a ferramenta "TCP Ping".',
        ],
        protocolsOrPorts: 'Protocolo ICMP (Tipo 8 / Código 0)'
    },
    traceroute: {
        id: 'traceroute',
        title: 'Traceroute (Rastreamento de Rota)',
        category: 'diag',
        categoryLabel: 'Diagnóstico',
        summary: 'Mapeia e exibe cada roteador intermediário (salto/hop) pelo qual os pacotes trafegam até chegar ao destino.',
        howItWorks: [
            'Envia pacotes IP com o campo TTL (Time to Live) iniciando em 1 e incrementando a cada salto.',
            'Cada roteador no caminho decrementa o TTL; ao chegar a zero, o roteador descarta o pacote e retorna uma mensagem ICMP Time Exceeded com seu próprio IP.',
            'Permite visualizar o caminho físico e lógico completo percorrido pelo tráfego de rede.',
        ],
        useCases: [
            'Identificar em qual roteador, operadora ou firewall o tráfego está sendo bloqueado ou descartado.',
            'Descobrir rotas assimétricas ou caminhos indesejados (ex: tráfego saindo por um link de backup incorreto).',
            'Diagnosticar loops de roteamento em redes internas e ambientes de VPN.',
        ],
        tips: [
            'Linhas com asteriscos (* * *) indicam que o roteador intermediário está configurado para não responder a ICMP Time Exceeded (comum por segurança), o que não significa necessariamente que a rota esteja quebrada.',
        ],
        protocolsOrPorts: 'ICMP / UDP (TTL Progressivo)'
    },
    mtr: {
        id: 'mtr',
        title: 'MTR (Path Monitor Salto a Salto)',
        category: 'diag',
        categoryLabel: 'Diagnóstico',
        summary: 'Combina a funcionalidade do Traceroute com a amostragem contínua do Ping em uma tabela dinâmica ao vivo.',
        howItWorks: [
            'Identifica todos os saltos da rota até o destino e dispara pings contínuos para cada um deles em paralelo.',
            'Calcula métricas estatísticas atualizadas a cada ciclo: Perda (Loss %), Última Latência, Média, Mínima, Máxima e Jitter (variação de latência).',
            'Utiliza os utilitários nativos do sistema operacional, sem necessidade de drivers ou bibliotecas adicionais.',
        ],
        useCases: [
            'Provar para operadoras e provedores de link onde exatamente a perda de pacotes está ocorrendo.',
            'Diagnosticar problemas de voz sobre IP (VoIP) e videoconferência causados por Jitter elevado em saltos específicos.',
            'Monitorar a qualidade contínua de um túnel ou link dedicado durante transferências de grande volume.',
        ],
        tips: [
            'Deixe o MTR rodar por pelo menos 30 a 50 ciclos para obter médias estatísticas confiáveis.',
            'Se a perda de pacotes aparece em apenas um salto intermediário mas NÃO persiste nos saltos seguintes, trata-se apenas de limitação de taxa (ICMP rate-limiting) daquele roteador, e não de um problema real.',
        ],
        protocolsOrPorts: 'ICMP / Tracert Nativo'
    },
    'tcp-ping': {
        id: 'tcp-ping',
        title: 'TCP Ping (Teste de Conexão por Porta)',
        category: 'diag',
        categoryLabel: 'Diagnóstico',
        summary: 'Verifica a disponibilidade e mede o tempo de resposta de um host abrindo uma conexão TCP real em uma porta específica.',
        howItWorks: [
            'Inicia o handshake TCP de 3 vias (SYN) na porta de destino especificada.',
            'Ao receber o pacote SYN-ACK (porta aberta) ou RST (porta fechada mas host ativo), calcula o tempo de resposta em ms e fecha a conexão de forma limpa.',
        ],
        useCases: [
            'Testar a conectividade em estações e servidores Windows que bloqueiam ICMP Ping por padrão no firewall.',
            'Verificar se uma porta de serviço específica (ex: RDP 3389, Web 80/443, Banco 1433/3306) está respondendo à rede.',
            'Medir a latência real da camada de transporte para serviços corporativos.',
        ],
        tips: [
            'Ideal para testar servidores em DMZ e computadores em domínio Active Directory sem precisar liberar regras ICMP no firewall.',
        ],
        protocolsOrPorts: 'Conexão TCP (Handshake SYN/ACK)'
    },
    pmtu: {
        id: 'pmtu',
        title: 'Path MTU (Descoberta de MTU do Caminho)',
        category: 'diag',
        categoryLabel: 'Diagnóstico',
        summary: 'Descobre o tamanho máximo de unidade de transmissão (MTU) que pode atravessar toda a rota sem sofrer fragmentação.',
        howItWorks: [
            'Envia pacotes de tamanhos decrescentes (iniciando no padrão Ethernet 1500 bytes) com a flag DF (Don\'t Fragment / Não Fragmentar) ativada.',
            'Se um roteador intermediário não suportar o tamanho do pacote, ele descarta e o teste tenta um tamanho menor até obter resposta bem-sucedida.',
        ],
        useCases: [
            'Diagnosticar o clássico problema de "Black Hole de MTU", onde a conexão funciona para comandos leves (Ping/SSH) mas trava ao transferir arquivos grandes ou abrir páginas pesadas.',
            'Ajustar o MTU de túneis VPN (IPsec, OpenVPN, WireGuard), GRE e interfaces PPPoE.',
        ],
        tips: [
            'Em conexões de internet padrão com túneis VPN, é comum que o Path MTU ideal seja entre 1400 e 1420 bytes devido aos cabeçalhos de encapsulamento criptográfico.',
        ],
        protocolsOrPorts: 'ICMP com flag Don\'t Fragment (DF)'
    },
    ad: {
        id: 'ad',
        title: 'Diagnóstico de Active Directory (AD DS)',
        category: 'ad',
        categoryLabel: 'Active Directory',
        summary: 'Executa uma auditoria completa de conectividade do Domain Controller, registros DNS SRV e sincronismo de tempo Kerberos.',
        howItWorks: [
            'Matriz de Portas do DC: Testa simultaneamente as portas vitais do DC (DNS 53, Kerberos 88/464, RPC 135, LDAP 389/636, SMB 445, Global Catalog 3268/3269).',
            'Validador SRV: Consulta registros DNS SRV essenciais (_ldap._tcp, _kerberos._tcp, _kpasswd._tcp, _gc._msdcs).',
            'Time Skew (Kerberos): Consulta o relógio do PDC Emulator e calcula a diferença de horário em relação a esta máquina.',
        ],
        useCases: [
            'Diagnosticar falhas de logon de usuários, mensagens de "Nenhum servidor de logon disponível" ou erros ao ingressar máquinas no domínio.',
            'Validar se as réplicas de catálogo global e serviços LDAP estão acessíveis em ambientes multi-site ou através de firewalls.',
            'Identificar desvios de relógio acima de 5 minutos, que causam a quebra imediata da autenticação Kerberos.',
        ],
        tips: [
            'Informe o IP de um Domain Controller específico ou o FQDN completo do domínio (ex: empresa.local).',
            'O Kerberos permite uma tolerância máxima de 5 minutos de desvio. Qualquer valor superior causará falhas de logon.',
        ],
        protocolsOrPorts: 'Portas: 53, 88, 135, 389, 445, 464, 636, 3268, 3269 / UDP 123 (NTP)'
    },
    scanner: {
        id: 'scanner',
        title: 'Scanner de Rede Local & Multi-VLAN',
        category: 'disco',
        categoryLabel: 'Descoberta & L2',
        summary: 'Varre blocos inteiros de IP para descobrir hosts ativos, resolver nomes e identificar fabricantes e tipos de equipamentos.',
        howItWorks: [
            'Dispara varredura multithread de alta performance através da faixa CIDR informada.',
            'Executa resolução de DNS reverso e consulta a tabela ARP para obter o endereço MAC físico.',
            'Cruza o prefixo OUI do MAC com a base oficial IEEE para identificar o fabricante do hardware e infere o tipo provável de dispositivo (impressora, câmera, switch, workstation).',
        ],
        useCases: [
            'Inventariar todos os computadores, servidores, impressoras e appliances conectados a uma sub-rede.',
            'Localizar equipamentos recém-instalados que pegaram IP via DHCP.',
            'Adicionar hosts descobertos diretamente ao Painel de Monitoramento com 1 clique.',
        ],
        tips: [
            'Abas de scan podem ser fixadas (Pin) ou renomeadas com duplo clique no título.',
            'Para identificar o fabricante via MAC Address, o host precisa estar na mesma sub-rede/VLAN local (limitação da Camada 2).',
        ],
        protocolsOrPorts: 'ARP / ICMP / Probes TCP Rápidos'
    },
    lldp: {
        id: 'lldp',
        title: 'Switch / Camada 2 (LLDP & CDP)',
        category: 'disco',
        categoryLabel: 'Descoberta & L2',
        summary: 'Descobre passivamente o nome do switch físico, modelo e porta exata em que o cabo de rede está conectado.',
        howItWorks: [
            'Captura pacotes multicast de camada de enlace dos protocolos IEEE 802.1AB (LLDP) e Cisco Discovery Protocol (CDP).',
            'Decodifica os campos TLV (Type-Length-Value) contendo o nome do switch, modelo do chassi, porta física (ex: GigabitEthernet1/0/24) e VLAN nativa.',
        ],
        useCases: [
            'Descobrir em qual porta física do switch de borda o computador do operador está conectado sem ir até o rack.',
            'Identificar a VLAN configurada na porta do switch durante a instalação de novos pontos de rede.',
            'Verificar a marca e o modelo do switch conectado sem precisar de credenciais de gerência SSH/Telnet.',
        ],
        tips: [
            'Switches enviam anúncios LLDP/CDP a cada 30 a 60 segundos. Aguarde o tempo de escuta para capturar os pacotes.',
            'Certifique-se de que o switch esteja com o protocolo LLDP ou CDP habilitado em suas portas.',
        ],
        protocolsOrPorts: 'LLDP (Ethertype 0x88CC) / CDP (SNAP 0x2000)'
    },
    smb: {
        id: 'smb',
        title: 'Pastas Compartilhadas (SMB / CIFS)',
        category: 'disco',
        categoryLabel: 'Descoberta & L2',
        summary: 'Enumera e audita pastas compartilhadas públicas e compartilhamentos administrativos ocultos em servidores de arquivos e NAS.',
        howItWorks: [
            'Conecta à porta TCP 445 do host alvo e utiliza as APIs de rede do Windows (NetShareEnum) para listar os compartilhamentos.',
            'Identifica o tipo de pasta (Disco, Impressora, IPC) e testa o nível de acessibilidade.',
        ],
        useCases: [
            'Auditar quais pastas estão expostas na rede por um servidor ou workstation.',
            'Verificar se compartilhamentos administrativos padrão (C$, ADMIN$) estão acessíveis.',
            'Mapear caminhos de rede corporativos para configuração de backups e rotinas de TI.',
        ],
        tips: [
            'Pastas terminadas em $ (como C$, D$, ADMIN$) são compartilhamentos administrativos ocultos que exigem credenciais com privilégios de administrador no host.',
        ],
        protocolsOrPorts: 'Porta TCP 445 (SMB) / TCP 139 (NetBIOS)'
    },
    arp: {
        id: 'arp',
        title: 'Detector de Conflitos ARP',
        category: 'disco',
        categoryLabel: 'Descoberta & L2',
        summary: 'Inspeciona a tabela ARP local para identificar colisões de endereços IP estáticos duplicados ou tentativas de ARP Spoofing.',
        howItWorks: [
            'Analisa as entradas da tabela de cache ARP do sistema operacional e mapeia cada endereço IP ao seu respectivo MAC Address.',
            'Detecta anomalias onde múltiplos endereços MAC respondem pelo mesmo IP ou onde o mesmo MAC assume múltiplos IPs de gateways.',
        ],
        useCases: [
            'Diagnosticar instabilidades graves na rede causadas por dois dispositivos configurados acidentalmente com o mesmo IP estático.',
            'Identificar máquinas que estão clonando o MAC ou praticando ataques de envenenamento ARP (Man-in-the-Middle).',
        ],
        tips: [
            'Se um conflito for detectado, consulte o fabricante dos MACs na ferramenta para saber quais aparelhos físicos estão em disputa pelo mesmo IP.',
        ],
        protocolsOrPorts: 'Camada 2 (ARP / RFC 826)'
    },
    ports: {
        id: 'ports',
        title: 'Scanner de Portas TCP',
        category: 'disco',
        categoryLabel: 'Descoberta & L2',
        summary: 'Varredura ultrarrápida de portas TCP abertas com streaming em tempo real e concorrência adaptativa.',
        howItWorks: [
            'Executa conexões TCP assíncronas utilizando um pool paralelo de alto rendimento.',
            'Capaz de verificar portas comuns pré-configuradas, intervalos personalizados (ex: 8000-8100) ou todas as 65.535 portas.',
            'Exibe as portas abertas imediatamente conforme são descobertas.',
        ],
        useCases: [
            'Auditar a segurança de um servidor para garantir que apenas as portas necessárias estejam expostas.',
            'Verificar se serviços recém-instalados (Web, SSH, RDP, Banco de Dados) estão escutando na porta esperada.',
            'Testar se firewalls de borda estão bloqueando portas críticas.',
        ],
        tips: [
            'O modo "Portas Comuns" verifica rapidamente as ~30 portas mais utilizadas em ambientes corporativos em menos de 1 segundo.',
        ],
        protocolsOrPorts: 'TCP Ports (1 a 65535)'
    },
    'ptr-sweep': {
        id: 'ptr-sweep',
        title: 'PTR Sweep (DNS Reverso em Lote)',
        category: 'disco',
        categoryLabel: 'Descoberta & L2',
        summary: 'Consulta o DNS reverso (PTR) de todos os endereços IP de uma sub-rede inteira de forma simultânea.',
        howItWorks: [
            'Gera todos os IPs do bloco CIDR fornecido e envia consultas DNS PTR concorrentes para o servidor DNS configurado.',
            'Converte endereços IP no formato in-addr.arpa para descobrir os nomes de host registrados no servidor DNS.',
        ],
        useCases: [
            'Mapear e documentar os nomes de todas as máquinas de uma VLAN rapidamente.',
            'Auditar as zonas reversas do servidor DNS corporativo em busca de registros órfãos ou desatualizados.',
            'Descobrir quais IPs de uma faixa possuem servidores ativos mesmo quando o ping está desativado.',
        ],
        tips: [
            'Permite especificar um servidor DNS corporativo dedicado para resolver domínios internos do Active Directory.',
        ],
        protocolsOrPorts: 'DNS UDP/TCP 53 (Registros PTR)'
    },
    dns: {
        id: 'dns',
        title: 'Consulta DNS (Direta & Reversa)',
        category: 'dns',
        categoryLabel: 'DNS & Nomes',
        summary: 'Executa consultas detalhadas no servidor DNS com suporte a múltiplos tipos de registros e servidores por VLAN.',
        howItWorks: [
            'Envia consultas DNS RFC 1035 para o servidor especificado ou para o resolver padrão da máquina.',
            'Detecta automaticamente se a entrada é um nome (resolução direta: A, AAAA, CNAME, MX, TXT) ou um IP (resolução reversa: PTR).',
        ],
        useCases: [
            'Testar se um nome de máquina interna está resolvendo para o IP correto.',
            'Verificar apontamentos de domínios públicos e registros de e-mail (MX, SPF, TXT).',
            'Diagnosticar falhas de resolução em ambientes corporativos multi-domínio.',
        ],
        tips: [
            'Informe o servidor DNS de uma rede específica para simular a resolução a partir de outra VLAN ou filial.',
        ],
        protocolsOrPorts: 'DNS UDP/TCP 53'
    },
    tls: {
        id: 'tls',
        title: 'Certificado TLS / SSL',
        category: 'dns',
        categoryLabel: 'DNS & Nomes',
        summary: 'Inspeciona a estrutura, emissor, SANs e data de validade de certificados digitais em portas seguras (HTTPS).',
        howItWorks: [
            'Abre uma sessão TLS raw na porta indicada (ex: 443, 8443) e obtém o certificado X.509 servido pelo host.',
            'Decodifica os campos ASN.1 extraindo o Subject, Emissor (CA), Nomes Alternativos (SANs), Suíte de Cifras e Versão do TLS.',
            'Calcula a contagem de dias restantes até o vencimento com alertas visuais coloridos.',
        ],
        useCases: [
            'Evitar quedas de serviços e portais web por expiração inesperada de certificados SSL.',
            'Auditar quais subdomínios estão protegidos por um certificado Wildcard (*.empresa.com).',
            'Inspecionar certificados de equipamentos de rede e appliances que utilizam portas não padrão (ex: 8443, 9443).',
        ],
        tips: [
            'Você pode colar a URL completa (ex: https://site.com.br:8443/login) que a ferramenta extrairá automaticamente o host e a porta corretos.',
            'Esta ferramenta inspeciona o certificado mesmo que ele seja autoassinado ou emitido por uma CA interna.',
        ],
        protocolsOrPorts: 'TLS / SSL (Porta 443 / 8443 / etc)'
    },
    iperf: {
        id: 'iperf',
        title: 'Banda & Vazão (iPerf2 Nativo)',
        category: 'banda',
        categoryLabel: 'Banda & Web',
        summary: 'Mede a capacidade real de transmissão de dados (Mbits/s), vazão e qualidade do link entre dois pontos da rede.',
        howItWorks: [
            'Modo Servidor: Coloca esta máquina em modo de escuta aguardando testes disparados por outros computadores.',
            'Modo Cliente: Conecta a um servidor iPerf existente na rede e transfere blocos de dados contínuos medindo a taxa média de transferência.',
            'Suporta fluxos TCP (vazão pura) e UDP (com medição de perda e jitter).',
        ],
        useCases: [
            'Medir a velocidade real de cabos de rede, links de rádio, fibra óptica e túneis VPN.',
            'Identificar gargalos em switches e placas de rede operando erroneamente em 100 Mbps em vez de 1 Gbps.',
            'Testar a taxa de transferência real sem a interferência de lentidão de disco ou antivírus.',
        ],
        tips: [
            'No modo Servidor, a ferramenta exibe o comando exato que deve ser executado no computador da outra ponta para iniciar o teste.',
            'Suporta "Sair pela rede" para testar interfaces específicas em computadores conectados a múltiplas VLANs.',
        ],
        protocolsOrPorts: 'Porta TCP/UDP 5201 (iPerf2)'
    },
    traffic: {
        id: 'traffic',
        title: 'Tráfego por Interface de Rede',
        category: 'banda',
        categoryLabel: 'Banda & Web',
        summary: 'Monitora em tempo real a taxa de download e upload individualizada para cada placa de rede física ou virtual.',
        howItWorks: [
            'Lê periodicamente os contadores acumulados de bytes e pacotes do sistema operacional via psutil.',
            'Calcula a derivada temporal a cada segundo para exibir a vazão instantânea em KB/s e MB/s.',
        ],
        useCases: [
            'Identificar qual placa de rede está saturada durante lentidões.',
            'Acompanhar o tráfego de rotinas de backup, clonagem de discos e transferências pesadas em tempo real.',
            'Monitorar placas virtuais de hipervisores (Hyper-V, VMware) e interfaces de VPN.',
        ],
        tips: [
            'Permite visualizar simultaneamente todas as interfaces de rede ativas da máquina em um único painel.',
        ],
        protocolsOrPorts: 'Contadores do Sistema Operacional'
    },
    http: {
        id: 'http',
        title: 'HTTP & Performance Web',
        category: 'banda',
        categoryLabel: 'Banda & Web',
        summary: 'Testa a disponibilidade, código de status e tempo de resposta (TTFB) de aplicações e portais web.',
        howItWorks: [
            'Envia requisições HTTP/HTTPS reais (GET, POST, HEAD) para o endpoint especificado.',
            'Mede com precisão os tempos de DNS, conexão TCP, handshake TLS e tempo até o primeiro byte (TTFB).',
            'Exibe o código HTTP retornado (ex: 200 OK, 301 Redirect, 500 Erro) e os cabeçalhos de resposta do servidor.',
        ],
        useCases: [
            'Verificar se uma aplicação ou serviço web de intranet está online e respondendo rapidamente.',
            'Identificar se uma lentidão ao abrir um portal é causada pelo DNS, pela rede ou pelo processamento interno do servidor (TTFB alto).',
            'Inspecionar cabeçalhos de segurança, tipo de servidor web (Nginx, IIS, Apache) e cookies retornados.',
        ],
        tips: [
            'Desmarque a opção "Verificar certificado TLS" caso esteja testando sistemas internos com certificados autoassinados.',
        ],
        protocolsOrPorts: 'HTTP (Porta 80) / HTTPS (Porta 443)'
    },
    snmp: {
        id: 'snmp',
        title: 'SNMP (Gerência de Dispositivos)',
        category: 'infra',
        categoryLabel: 'Infra & Cálculo',
        summary: 'Consulta informações gerenciais de switches, roteadores, nobreaks, firewalls e impressoras via protocolo SNMP.',
        howItWorks: [
            'Envia requisições SNMP GET (v1 ou v2c) utilizando a community de leitura informada (padrão "public").',
            'Lê as OIDs padrão da MIB-II: Nome do Dispositivo (sysName), Descrição do Sistema (sysDescr), Uptime e Quantidade de Interfaces.',
        ],
        useCases: [
            'Coletar o tempo de atividade (Uptime) de switches e roteadores para saber se houve reinicialização recente.',
            'Identificar a versão de firmware e o modelo exato de equipamentos de rede sem precisar de acesso via SSH.',
            'Verificar a conectividade de gerência SNMP antes de cadastrar o host em sistemas como Zabbix ou Grafana.',
        ],
        tips: [
            'A porta padrão do protocolo SNMP é a UDP 161.',
            'A community de leitura precisa corresponder exatamente à configurada no equipamento alvo.',
        ],
        protocolsOrPorts: 'UDP 161 (SNMP v1/v2c)'
    },
    ntp: {
        id: 'ntp',
        title: 'NTP (Sincronismo de Horário)',
        category: 'infra',
        categoryLabel: 'Infra & Cálculo',
        summary: 'Consulta servidores de tempo NTP para verificar o stratum, a precisão e o desvio temporal (clock offset).',
        howItWorks: [
            'Envia um pacote NTP na porta UDP 123 para o servidor alvo e calcula o atraso de ida e volta e a diferença entre o relógio local e o servidor de referência.',
            'Exibe o Stratum (distância até o relógio atômico) e a data/hora exata fornecida pelo servidor.',
        ],
        useCases: [
            'Verificar se os servidores NTP corporativos ou Domain Controllers estão sincronizados.',
            'Auditar a precisão do relógio em servidores de banco de dados e sistemas financeiros.',
            'Prevenir falhas em logs e auditorias causadas por servidores com horários divergentes.',
        ],
        tips: [
            'Servidores NTP públicos confiáveis no Brasil incluem a.ntp.br, b.ntp.br e c.ntp.br.',
        ],
        protocolsOrPorts: 'UDP 123 (NTP)'
    },
    subnet: {
        id: 'subnet',
        title: 'Calculadora de Sub-redes IPv4 / CIDR',
        category: 'infra',
        categoryLabel: 'Infra & Cálculo',
        summary: 'Calcula instantaneamente parâmetros de endereçamento IPv4, faixas usáveis, máscara, broadcast e divisão em sub-redes.',
        howItWorks: [
            'Processa a notação CIDR (ex: 192.168.1.0/24) através de cálculos binários de máscara de rede.',
            'Exibe o Endereço de Rede, Primeiro IP Usável, Último IP Usável, Endereço de Broadcast, Máscara Decimal, Máscara Wildcard e Total de Hosts.',
            'Permite dividir a rede em sub-redes menores com listagem detalhada de cada bloco.',
        ],
        useCases: [
            'Planejar a divisão de sub-redes e VLANs para novos departamentos ou filiais.',
            'Configurar escopos de DHCP e tabelas de roteamento com as faixas de IP corretas.',
            'Criar regras de firewall com máscaras wildcard (inversas) utilizadas em roteadores Cisco.',
        ],
        tips: [
            'Você pode digitar tanto no formato CIDR (ex: 10.0.0.0/22) quanto com a máscara tradicional (ex: 10.0.0.0 255.255.252.0).',
        ],
        protocolsOrPorts: 'Cálculo IPv4 / RFC 4632'
    },
    connections: {
        id: 'connections',
        title: 'Conexões Ativas (Netstat com Processos)',
        category: 'infra',
        categoryLabel: 'Infra & Cálculo',
        summary: 'Lista todas as portas TCP/UDP em escuta e conexões ativas nesta máquina com o nome do processo e PID associados.',
        howItWorks: [
            'Examina a tabela de sockets do sistema operacional em tempo real.',
            'Cruza cada porta e conexão aberta com a lista de processos ativos do Windows, exibindo o nome do executável proprietário.',
            'Oferece filtros instantâneos por número de porta, endereço IP e nome do processo.',
        ],
        useCases: [
            'Descobrir qual programa está ocupando uma porta específica (ex: porta 80 ocupada pelo IIS ou Skype).',
            'Auditar conexões de rede ativas em busca de softwares suspeitos ou comunicações indesejadas.',
            'Verificar se serviços recém-iniciados estão realmente em estado de escuta (LISTENING).',
        ],
        tips: [
            'Use a caixa de busca para filtrar rapidamente por portas (ex: 443, 3389) ou por processos (ex: chrome.exe, java.exe).',
        ],
        protocolsOrPorts: 'Sockets TCP / UDP do Windows'
    }
};
