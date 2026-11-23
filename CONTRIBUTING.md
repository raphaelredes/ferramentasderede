# Guia de Contribuição

Contribuições, correções de bugs, melhorias de desempenho e novas ferramentas de diagnóstico são bem-vindas. Este documento define os padrões técnicos adotados no repositório.

## Requisitos de Ambiente

- **Windows 10/11 (x64)** para validação completa de WinRM, WMI, WebView2 e build portátil.
- **Python 3.12+** (`pip install -r python/requirements.txt`).
- **Node.js 20+** (`cd electron && npm install`).

## Regras Arquiteturais Obrigatórias

1. **Empacotamento portátil exclusivo em Python + PyWebView**:
   - O distribuível oficial é gerado via `cmd /c build_system.bat` (`python/build_webview.spec`).
   - Não utilize `electron-builder` nem `npm run build` em `electron/`.
2. **Segurança e isolamento**:
   - Mantenha o bind padrão da API em `127.0.0.1`.
   - Nunca interpole entradas do usuário diretamente em scripts PowerShell ou comandos de shell; passe parâmetros validados ou via variáveis de ambiente efêmeras.
   - Em subprocessos Windows (`subprocess.run`/`Popen`), utilize sempre `CREATE_NO_WINDOW` (`0x08000000`) e `SW_HIDE` para evitar janelas de console em primeiro plano.
   - Todo novo protocolo em texto claro deve classificar o destino (RFC 1918 vs. WAN pública) antes da transmissão.
3. **Suporte Multi-VLAN / Multi-Domínio**:
   - Operações de rede devem aceitar `source_ip` opcional e respeitar o `dns_server` da rede configurada sempre que aplicável.
4. **Exemplos, testes e placeholders neutros**:
   - Utilize exclusivamente endereços públicos de teste ou referências padronizadas (`google.com`, `cloudflare.com`, `1.1.1.1`, `8.8.8.8`, `example.com` — RFC 2606 — ou blocos RFC 1918/5737). Nunca inclua domínios corporativos, IPs internos reais ou dados de terceiros.
5. **Licenciamento compatível**:
   - Não introduza dependências sob licenças copyleft fortes (GPL/AGPL/LGPL). Ao adicionar bibliotecas, atualize [THIRD-PARTY-LICENSES.txt](THIRD-PARTY-LICENSES.txt).

## Validação Obrigatória Antes do Pull Request

Execute localmente e garanta zero erros antes de abrir um PR:

```powershell
# 1. Frontend — checagem estrita de tipos e build
cd electron
npx tsc --noEmit
npx vite build

# 2. Backend — verificação sintática e testes
cd ..\python
python -m compileall -q api src main_webview.py main.py
pytest -q tests/
```

## Padrão de Commits

Utilize [Conventional Commits](https://www.conventionalcommits.org/) com mensagens concisas no imperativo:

- `feat(tools): adicionar exportação JSON no painel DNS`
- `fix(winrm): tratar timeout em autenticação cross-domain`
- `perf(monitor): reduzir alocações no ciclo de coleta`
- `security(snmp): validar tamanho mínimo de chave USM RFC 3414`
- `docs: atualizar matriz de ferramentas no README`

## Fluxo de Pull Request

1. Crie uma branch descritiva a partir de `main` (`feat/...`, `fix/...`, `docs/...`).
2. Mantenha o escopo focado na mudança proposta (evite alterações não solicitadas).
3. Não altere a versão em `electron/package.json` sem alinhamento prévio com o mantenedor.
4. Descreva claramente o problema resolvido, como reproduzir e quais validações foram executadas.
