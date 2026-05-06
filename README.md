Resumo das Funcionalidades
1. Painel Principal (Dashboard)
Visão Geral: Exibe status do sistema, total de hosts monitorados, alertas recentes e métricas de rede.

Monitoramento em Tempo Real:

Latência Média: Exibição da latência média baseada no histórico recente.

Perda de Pacotes: Cálculo de perda com lógica "Smart Offline" (considera offline apenas com >60% de perda e >50 pacotes ou sem responder desde a inicialização).

Gráficos Sparkline: Histórico visual de latência no fundo dos cards dos hosts.

Status de Serviços: Monitoramento de portas TCP específicas (HTTP, SSH, RDP, etc.) com indicadores visuais.

Organização:

Grupos: Categorização de hosts por grupos (ex: Servidores, Impressoras).

Filtros e Busca: Filtragem por status, nome, IP ou grupo.

Ordenação Manual: Reordenação de cards via Drag & Drop com persistência.

2. Ferramentas de Diagnóstico
Ping: Ferramenta ICMP rápida (icmplib) com fallback automático.

Traceroute: Rastreamento de rota visual.

Scanner de Rede:

Varredura de faixas CIDR (ex: 192.168.1.0/24).

Identificação de Fabricante (Vendor) via MAC Address.

Resolução de Hostname (DNS Reverso/NetBIOS).

IPs Disponíveis: Listagem de endereços livres na rede.

Exportação de resultados para CSV.

3. Gerenciamento Remoto
Acesso Remoto:

Integração nativa com RDP (Remote Desktop Protocol).

Integração com TeamViewer (via ID).

Integração com MSRA (Assistência Remota do Windows).

Ações de Energia:

Desligar e Reiniciar remoto (via RPC/WMI).

Wake-on-LAN (WoL).

Envio de mensagens (msg.exe) para usuários conectados.

Agendamento e cancelamento de desligamento.

Terminal Remoto (WinRM):

Execução de comandos PowerShell/CMD remotos.

Listagem de processos e serviços.

Gerenciamento de sessões de usuário (listar, desconectar).

4. Segurança e Configuração
Cofre de Senhas:

Armazenamento criptografado (AES-256) de credenciais.

Senha Mestra para proteção do cofre.

Uso automático de credenciais salvas para autenticação remota.

Hosts Confiáveis: Interface para configurar 

TrustedHosts do WinRM.

Backup:

Backup automático diário do banco de dados SQLite.

Exportação/Importação manual de hosts (JSON).

5. Arquitetura e Performance
Backend Otimizado:

Threads Dedicadas: Uma thread por host para garantir precisão de 1 ping/segundo.

Resolução Assíncrona: DNS e MAC Address resolvidos em background para não bloquear o monitoramento.

Fast Mode: Otimização de timeouts para redes locais e WAN.

Portabilidade:

Executável Único: Compilação portátil (

.exe) sem instalador.

Banco de Dados SQLite: Persistência robusta de dados em arquivo local.
