# Política de Segurança

## Versões Suportadas

As correções de segurança são aplicadas exclusivamente à versão mais recente publicada na branch `main` e nas [Releases do GitHub](https://github.com/raphaelredes/ferramentasderede/releases).

| Versão | Suporte |
| :--- | :--- |
| Última release (`v1.5.x`) | :white_check_mark: Suportada |
| Versões anteriores (`< 1.5.0`) | :x: Sem suporte |

## Modelo de Segurança da Aplicação

O **Ferramentas de Rede** foi projetado com premissas de menor privilégio e isolamento local:

- **API restrita a loopback**: o backend FastAPI/Uvicorn escuta exclusivamente em `127.0.0.1:8000` por padrão, com CORS limitado às origens locais (`5173`/`5174`).
- **Cofre local criptografado**: credenciais são armazenadas em `%APPDATA%\FerramentasDeRede\credentials.enc` utilizando **AES-256-GCM** com derivação de chave **PBKDF2-HMAC-SHA256 (600.000 iterações)** e salt criptográfico aleatório de 32 bytes.
- **Execução sem elevação**: o executável portátil utiliza `uac_admin=False`; elevação UAC ocorre apenas sob ação explícita do operador (ex.: atualização de `TrustedHosts` no Registro do Windows).
- **Higiene de segredos em subprocessos**: credenciais não são passadas em linha de comando nem registradas em logs ou histórico do PowerShell.
- **Protocolos em texto claro**: ferramentas que operam com protocolos inseguros (como SNMPv1/v2c) classificam o alvo (RFC 1918 / RFC 4193 vs. WAN pública) e emitem aviso pré-voo antes do envio de pacotes fora de redes privadas.

## Como Reportar uma Vulnerabilidade

**Não abra uma Issue pública** para falhas de segurança ou vulnerabilidades exploráveis (como injeção de comando, vazamento de credenciais, bypass de CORS/IPC ou falhas criptográficas).

Em vez disso:

1. Utilize o recurso **Report a vulnerability** (GitHub Security Advisories) na aba **Security** deste repositório, quando habilitado; ou
2. Entre em contato diretamente com o mantenedor através dos canais oficiais em [ferramentasderede.com.br](https://www.ferramentasderede.com.br/).

Ao reportar, inclua sempre que possível:

- Versão do aplicativo e sistema operacional (Windows 10/11, build).
- Descrição clara do vetor de ataque e impacto esperado.
- Passos reproduzíveis ou prova de conceito (PoC) utilizando apenas endereços de teste neutros (RFC 2606 / RFC 5737, como `example.com` ou `192.0.2.1`).

## Verificação de Integridade dos Binários

Os executáveis portáteis publicados em [GitHub Releases](https://github.com/raphaelredes/ferramentasderede/releases) incluem resumo criptográfico **SHA-256** gerado pelo GitHub. Antes de executar em ambientes corporativos, valide o hash localmente:

```powershell
Get-FileHash .\Ferramentas.de.Rede.v<versão>.exe -Algorithm SHA256
```
