# Configuração de Segurança - Ferramentas de Rede

## Arquivos Sensíveis Protegidos

Este projeto foi configurado para **NÃO** incluir dados sensíveis no controle de versão Git. Os seguintes tipos de arquivos são automaticamente ignorados:

### 🔒 Dados de Rede Sensíveis
- `hosts.json` - Lista de hosts da rede com IPs e hostnames
- `cache/services/` - Cache de serviços descobertos
- `discovery_cache.json` - Cache de descoberta de rede
- Todos os arquivos de cache (`*.cache`, `**/*cache*.json`)

### 🔐 Configurações e Credenciais
- `ui_preferences.json` - Preferências do usuário
- `.env*` - Variáveis de ambiente
- `credentials.json.enc*` - Credenciais criptografadas
- `*.key`, `*.salt` - Chaves de criptografia
- `secrets.json` - Arquivos de segredos

### 📋 Logs e Dados Temporários
- `data/logs/` - Logs da aplicação (podem conter IPs/hostnames)
- `*.log` - Todos os arquivos de log
- `*.tmp`, `*.temp` - Arquivos temporários

## 🚀 Configuração Inicial

### 1. Copiar Arquivos Template
```bash
# Copiar templates para usar na aplicação
cp hosts.json.template hosts.json
cp ui_preferences.json.template ui_preferences.json
cp .env.template .env
```

### 2. Configurar Hosts
Edite o arquivo `hosts.json` com seus hosts reais:
```json
[
    {
        "name": "seu-servidor.local",
        "ip": "192.168.1.10",
        "mac": "",
        "nickname": "Servidor Principal",
        "resolved_hostname": "seu-servidor.local",
        "current_ip": "192.168.1.10"
    }
]
```

### 3. Configurar Preferências
Edite `ui_preferences.json` conforme suas preferências:
```json
{
    "theme": "dark",
    "language": "pt-BR",
    "window_geometry": "1200x800+100+100"
}
```

### 4. Configurar Variáveis de Ambiente
Edite `.env` com suas configurações específicas:
```bash
LOG_LEVEL=INFO
DEFAULT_PING_TIMEOUT=1000
ENABLE_CREDENTIAL_ENCRYPTION=true
```

## ⚠️ IMPORTANTE - Segurança

### ❌ NÃO Commit estes arquivos:
- `hosts.json` (contém IPs e hostnames reais)
- `ui_preferences.json` (pode conter paths sensíveis)
- `.env` (contém configurações específicas)
- `cache/` (contém dados de rede descobertos)
- `data/logs/` (contém logs com informações sensíveis)

### ✅ Apenas commit:
- `*.template` (arquivos de exemplo)
- Código fonte
- Documentação
- Configurações gerais

## 🔧 Verificação

Para verificar se arquivos sensíveis não estão sendo rastreados:
```bash
# Verificar status do git
git status

# Verificar se .gitignore está funcionando
git check-ignore hosts.json ui_preferences.json .env
```

## 🛡️ Backup Seguro

Para fazer backup dos seus dados sensíveis:
1. Crie uma pasta separada fora do repositório Git
2. Copie apenas os arquivos de configuração necessários
3. Use criptografia para proteger backups
4. Nunca inclua backups no controle de versão

## 📞 Suporte

Se você acidentalmente commitou dados sensíveis:
1. Remova imediatamente do tracking: `git rm --cached arquivo_sensivel`
2. Commit a remoção: `git commit -m "Remove sensitive data"`
3. Consider reescrever o histórico se necessário: `git filter-branch`

---
**⚠️ LEMBRE-SE: Segurança em primeiro lugar! Nunca compartilhe dados sensíveis da rede em repositórios públicos.**