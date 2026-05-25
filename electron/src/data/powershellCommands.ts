// Quick-reference catalog of PowerShell snippets shown in the "Guia de
// Comandos" modal opened from the Terminal Remoto page. Each command is
// designed to be copied as-is and pasted into the remote PSSession the
// operator just opened.
//
// Source: docs/guia_comandos_powershell.pdf (internal support guide).
// Keep the data here (not in the modal component) so future additions are a
// pure-data edit without touching JSX.

export interface PSCommand {
    /** Short title shown above the code block. */
    title: string;
    /** One-line explanation in PT-BR — what does this do, why would I run it. */
    description: string;
    /** The literal command to copy. Preserves line breaks for multi-line snippets. */
    command: string;
    /** Optional warning tag. Used for destructive commands (logoff, restart, etc). */
    warning?: string;
}

export interface PSSection {
    title: string;
    commands: PSCommand[];
}

export const PS_COMMAND_GUIDE: PSSection[] = [
    {
        title: 'Gerenciamento de Rede e Adaptadores',
        commands: [
            {
                title: 'Listar todos os adaptadores de rede físico/virtual',
                description: 'Exibe o status, nome da interface, velocidade e endereço MAC.',
                command: 'Get-NetAdapter | Format-Table Name, InterfaceDescription, Status, LinkSpeed',
            },
            {
                title: 'Desativar o adaptador Wi-Fi remotamente',
                description: 'Desliga a interface sem pedir confirmação manual. Substitua "Wi-Fi" pelo nome real se necessário.',
                command: 'Disable-NetAdapter -Name "Wi-Fi" -Confirm:$false',
                warning: 'Pode derrubar a conexão remota se for a NIC ativa.',
            },
            {
                title: 'Ativar o adaptador Wi-Fi remotamente',
                description: 'Reativa a interface de rede sem fio previamente desativada.',
                command: 'Enable-NetAdapter -Name "Wi-Fi" -Confirm:$false',
            },
            {
                title: 'Verificar endereços IP da máquina',
                description: 'Lista apenas as interfaces ativas com seus respectivos IPs IPv4.',
                command: 'Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress',
            },
        ],
    },
    {
        title: 'Diagnósticos e Testes de Rede',
        commands: [
            {
                title: 'Testar conectividade básica (Ping)',
                description: 'Realiza um teste de eco para validar se um servidor ou IP está online.',
                command: 'Test-NetConnection -ComputerName google.com',
            },
            {
                title: 'Testar se uma porta TCP específica está aberta',
                description: 'Excelente para validar serviços como RDP (3389), SSH (22) ou WinRM (5985).',
                command: 'Test-NetConnection -ComputerName 192.168.1.50 -Port 3389',
            },
            {
                title: 'Rastrear a rota de rede (Traceroute)',
                description: 'Mostra o caminho dos pacotes até o destino, útil para achar falhas de salto.',
                command: 'Test-NetConnection -ComputerName 8.8.8.8 -TraceRoute',
            },
        ],
    },
    {
        title: 'Armazenamento e Disco',
        commands: [
            {
                title: 'Verificar espaço livre e total em disco (simplificado)',
                description: 'Exibe as partições, tipo de sistema de arquivos e o espaço livre de forma direta.',
                command: 'Get-Volume | Format-Table DriveLetter, FileSystemLabel, SizeRemaining, Size',
            },
            {
                title: 'Verificar espaço em discos locais em Gigabytes (GB)',
                description: 'Formata os tamanhos de bytes para GB legíveis com duas casas decimais.',
                command:
                    `Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, ` +
                    `@{n="Total(GB)";e={[math]::round($_.Size/1GB,2)}}, ` +
                    `@{n="Livre(GB)";e={[math]::round($_.FreeSpace/1GB,2)}}`,
            },
        ],
    },
    {
        title: 'Usuários e Sessões',
        commands: [
            {
                title: 'Verificar usuários conectados no momento',
                description: 'Exibe o nome do usuário, ID da sessão RDP/Local e o estado (Ativo/Inativo).',
                command: 'quser',
            },
            {
                title: 'Fazer logout da própria sessão terminal atual',
                description: 'Encerra imediatamente a sua sessão atual no servidor/máquina.',
                command: 'logoff',
                warning: 'Encerra a sessão da qual você está executando — pode te desconectar.',
            },
            {
                title: 'Desconectar/Deslogar outro usuário pelo ID de sessão',
                description: "Força o encerramento da sessão de outro usuário. Obtenha o ID rodando 'quser'.",
                command: 'logoff 2',
                warning: 'Substitua "2" pelo ID real. Encerra trabalho não salvo do usuário.',
            },
            {
                title: 'Derrubar uma sessão RDP específica (resetar)',
                description: 'Útil quando o usuário travou no ambiente de Área de Trabalho Remota.',
                command: 'rwinsta 2',
                warning: 'Substitua "2" pelo ID real da sessão travada.',
            },
        ],
    },
    {
        title: 'Sistema e Processos',
        commands: [
            {
                title: 'Listar os 10 processos que mais consomem memória RAM',
                description: 'Identifica rapidamente gargalos de desempenho na máquina.',
                command:
                    `Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 Name, Id, ` +
                    `@{n="RAM(MB)";e={[math]::round($_.WorkingSet/1MB,2)}}`,
            },
            {
                title: 'Forçar o encerramento de um processo travado',
                description: 'Finaliza o processo pelo nome (ex: instâncias travadas do Chrome).',
                command: 'Stop-Process -Name "chrome" -Force',
                warning: 'Encerra todas as instâncias do processo nomeado, sem salvar.',
            },
            {
                title: 'Reiniciar o computador imediatamente',
                description: 'Força a reinicialização imediata do sistema operacional.',
                command: 'Restart-Computer -Force',
                warning: 'Reinicia agora — perde trabalho não salvo de todos os usuários conectados.',
            },
        ],
    },
];
