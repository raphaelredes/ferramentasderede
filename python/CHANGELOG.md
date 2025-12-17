# Changelog - Ferramentas de Rede

## [1.1] - 2025-11-14

### Adicionado
- Sistema de ícones em alta qualidade (PNG 256x256) para barra de tarefas
- Interpolação LANCZOS para melhor qualidade do ícone
- Nome do executável agora inclui versão (FerramentasDeRede_v1.1.exe)
- UPX desabilitado para evitar erro "ordinal 380" em DLLs do Tcl/Tk

### Corrigido
- **CRÍTICO**: Status das abas agora atualiza corretamente após adicionar hosts via Scanner de Rede
- **CRÍTICO**: Ícone embaçado na barra de tarefas (agora usa PNG de alta qualidade)
- Implementado thread-safety para atualização de status de hosts
- Corrigido monitoramento contínuo de status para hosts adicionados dinamicamente
- Atualização visual forçada após reload de hosts

### Melhorado
- Sistema de monitoramento de status mais robusto
- Verificação assíncrona de status para novos hosts
- Uso de locks para evitar condições de corrida
- Agendamento correto de atualizações visuais na thread principal

### Técnico
- Adicionado `_host_statuses_lock` para acessos thread-safe
- Método `add_discovered_hosts` agora inicializa status e inicia verificação assíncrona
- Método `_check_and_update_host_status` usa locks e agenda updates na thread principal
- Método `reload_all_hosts_and_tabs` força atualização visual de todos os hosts

---

## [1.0] - 2025-10-XX

### Primeira Versão
- Sistema de gerenciamento de hosts
- Scanner de rede local e remoto
- Ferramentas de rede (ping, traceroute)
- Comandos remotos via WinRM
- Sistema de credenciais seguras
- Interface multi-abas responsiva
- Suporte a múltiplos idiomas (PT-BR, EN-US, ES-ES)
