# Ferramentas de Rede - Documentação do Sistema

## Visão Geral
O **Ferramentas de Rede** é uma aplicação profissional desenvolvida para auxiliar administradores de rede e técnicos no diagnóstico, monitoramento e gerenciamento de redes locais e remotas.

## Funcionalidades Principais

### 1. Monitoramento de Hosts (Ping)
- **Descrição**: Monitora o status (Online/Offline) de múltiplos hosts simultaneamente.
- **Como usar**:
    - Adicione hosts na lista principal.
    - O sistema enviará pings periodicamente.
    - O status é atualizado em tempo real com indicadores visuais (Verde = Online, Vermelho = Offline).

### 2. Scanner de Portas
- **Descrição**: Verifica quais portas TCP estão abertas em um host específico.
- **Como usar**:
    - Selecione um host ou digite um IP.
    - Escolha o intervalo de portas (Top 60, Todas, ou Personalizado).
    - Inicie o scan para ver os serviços disponíveis.

### 3. Descoberta de Rede (Network Discovery)
- **Descrição**: Varre a rede local para encontrar dispositivos conectados.
- **Como usar**:
    - Acesse a aba de descoberta.
    - Clique em "Iniciar Scan".
    - O sistema listará IPs, nomes de host e fabricantes (MAC) encontrados.

### 4. Teste de Velocidade (Speedtest)
- **Descrição**: Mede a velocidade da conexão com a internet (Download, Upload e Ping).
- **Como usar**:
    - Acesse a ferramenta de velocidade.
    - Clique em "Iniciar Teste".

### 5. Calculadora IP
- **Descrição**: Realiza cálculos de sub-rede (CIDR, Máscara, Broadcast, etc.).
- **Como usar**:
    - Insira um IP e a máscara (ex: 192.168.1.1/24).
    - O sistema calculará automaticamente os detalhes da rede.

## Configuração e Arquivos

### Localização dos Arquivos
Para garantir a segurança e integridade dos dados, o sistema armazena suas configurações e dados no diretório de dados do usuário:

- **Windows**: `%LOCALAPPDATA%\FerramentasDeRede`
    - Geralmente: `C:\Users\SeuUsuario\AppData\Local\FerramentasDeRede`

### Arquivos Importantes
- `hosts.json`: Lista de hosts salvos (Favoritos).
- `ui_preferences.json`: Preferências de interface (Tema, Tamanho da fonte).
- `discovery_cache.json`: Cache da última varredura de rede.
- `logs/`: Diretório contendo logs de execução para diagnóstico de problemas.

## Solução de Problemas

### A janela abre muito pequena
- O sistema tenta detectar automaticamente a resolução da tela. Se falhar, ele usará um tamanho padrão seguro. Você pode redimensionar a janela manualmente e o sistema tentará lembrar da posição (se configurado).

### Ícones não aparecem
- Verifique se os arquivos de imagem (`.png`, `.ico`) estão presentes na pasta `assets/` ou na raiz do executável. O sistema tenta carregar `network_topology.png` como ícone principal.

### "Erro de Permissão" ao salvar hosts
- O sistema agora salva em `%LOCALAPPDATA%`, que não requer permissões de administrador. Se o erro persistir, verifique se o antivírus não está bloqueando a escrita na pasta.

## Suporte
Para reportar bugs ou solicitar novas funcionalidades, entre em contato com o desenvolvedor responsável.
