# Análise do Sistema "Ferramentas de Rede"

## Visão Geral da Arquitetura

O sistema é uma aplicação desktop construída com **Electron**, utilizando uma arquitetura híbrida:
- **Frontend**: React + Vite (renderizado pelo Electron).
- **Backend**: Python (FastAPI), executado como um sub-processo.
- **Comunicação**: HTTP (REST API) e WebSockets para atualizações em tempo real.

## Backend (Python)

O backend é responsável por toda a lógica de negócios, gerenciamento de rede e persistência de dados.

### Tecnologias Principais
- **Framework**: FastAPI (Alta performance, assíncrono).
- **Servidor**: Uvicorn.
- **Banco de Dados**: SQLite (gerenciado via `src.core.database`).
- **Bibliotecas de Rede**: `pywinrm`, `pypsrp` (PowerShell Remoting), `scapy` (implícito para alguns scans), `icmplib` (Ping), `wakeonlan`.

### Estrutura de Diretórios (`python/`)
- **`main.py`**: Script lançador que gerencia o ciclo de vida (limpa portas, inicia o Electron).
- **`api/`**: Definição da API REST.
    - `server.py`: Ponto de entrada da aplicação FastAPI. Configura CORS, WebSockets e Monitoramento.
    - `routes/`: Endpoints divididos por domínio (`network`, `system`, `security`, `settings`).
- **`src/`**: Núcleo da lógica.
    - `core/`: Gerenciadores principais (`HostManager`, `SettingsManager`, `Database`).
    - `network/`: Implementação das ferramentas de rede (Scanner, Ping, Port Scan).
    - `system/`: Utilitários do sistema (Backup, Logs).
    - `security/`: Criptografia e autenticação.

### Fluxo de Dados (Hosts)
1.  **Persistência**: Dados salvos em SQLite.
2.  **Gerenciamento**: `HostManager` carrega dados e converte para o formato da UI.
3.  **Monitoramento**: `HostMonitor` (em background) pinga os hosts e atualiza o status.
4.  **Atualização**: Mudanças de status são enviadas via WebSocket para o Frontend.

## Frontend (Electron/React)

A interface do usuário é moderna e reativa.

### Tecnologias Principais
- **Framework**: React 18.
- **Build Tool**: Vite.
- **Estilização**: Tailwind CSS.
- **Roteamento**: React Router.
- **Componentes**: `lucide-react` (ícones), `recharts` (gráficos), `xterm` (terminal).

### Estrutura de Diretórios (`electron/src/`)
- **`pages/`**: Telas principais.
    - `Dashboard.tsx`: Visão geral e monitoramento de hosts.
    - `HostDetails.tsx`: Detalhes e ferramentas para um host específico.
    - `Terminal.tsx`: Interface de terminal remoto.
    - `Settings.tsx`, `Security.tsx`, `Tools.tsx`: Configurações e ferramentas extras.
- **`components/`**: Componentes reutilizáveis (Cards, Modais, Inputs).
- **`contexts/`**: Gerenciamento de estado global (provavelmente Auth, Theme, Data).

## Funcionalidades Chave Identificadas

1.  **Gerenciamento de Hosts**: CRUD completo, importação/exportação CSV, organização por grupos.
2.  **Monitoramento em Tempo Real**: Ping contínuo, detecção de status (Online/Offline), latência.
3.  **Acesso Remoto**:
    - Terminal remoto via PowerShell (WinRM/PSRP).
    - Execução de comandos remotos.
4.  **Ferramentas de Rede**:
    - Scanner de Rede (Discovery).
    - Wake-on-LAN.
    - Port Scanner.
5.  **Segurança**:
    - Gerenciamento de credenciais criptografadas.
    - Proteção de IDs (TeamViewer).
6.  **Sistema**:
    - Backup automático.
    - Logs de operação.

## Pontos de Atenção

- **Migração de Dados**: O sistema possui lógica para migrar do antigo `hosts.json` para SQLite, indicando uma evolução recente.
- **Hibridismo**: A dependência de `npm run dev` no `main.py` sugere que o ambiente de produção pode precisar de um build process específico (empacotamento com PyInstaller + Electron Builder).
- **Performance**: O uso de `asyncio` e WebSockets demonstra preocupação com a responsividade da UI durante operações de rede pesadas.
