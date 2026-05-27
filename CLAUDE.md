# CLAUDE.md

Guia para agentes de IA (Claude Code, Cursor, Copilot, etc.) trabalhando neste repositório. Leia tudo antes de tocar em código.

## O que é este projeto

**Ferramentas de Rede** — aplicação desktop (Electron + React/TypeScript no front, Python/FastAPI no back) para analistas de rede que operam em **rede ampla com dois domínios AD e várias VLANs**. Funcionalidades centrais: monitoramento de hosts, descoberta de rede, ping/traceroute/scanner, terminal remoto via WinRM, vault de credenciais.

O caso de uso real (multi-domínio / multi-VLAN) **molda decisões em todo o stack** — qualquer feature de rede precisa pensar em "qual NIC sai por aqui?" e "qual DNS resolve isso?".

## Estrutura

```
ferramentasderede/
├── electron/                 ← Frontend Electron + React + Vite + Tailwind
│   ├── electron/             ← Main process (main.ts, preload.ts)
│   ├── src/
│   │   ├── components/       ← Componentes React
│   │   ├── contexts/         ← Providers globais (Monitoring, Tools, Vault, Toast, Loading)
│   │   ├── data/             ← Fontes de dados estáticos (changelog.ts ← APP_VERSION)
│   │   ├── hooks/            ← Custom hooks (useNetworks, useFilteredHosts, etc.)
│   │   ├── pages/            ← Telas (Dashboard, Tools, Settings, Security, etc.)
│   │   ├── config/api.ts     ← API_BASE / WS_BASE — single source para URL do backend
│   │   └── types.d.ts        ← Tipos TS globais (Host, etc.)
│   ├── dist-electron/        ← Build do main/preload (commitado)
│   └── package.json
├── python/                   ← Backend FastAPI
│   ├── api/
│   │   ├── server.py         ← Entry point uvicorn
│   │   └── routes/           ← network.py, security.py, settings.py, system.py
│   ├── src/
│   │   ├── config/settings.py    ← APP_VERSION + APP_DATA_DIR
│   │   ├── core/             ← database.py, host_manager.py, security.py
│   │   ├── network/          ← ping, traceroute, scanner, monitor, interfaces, dns_resolver, tools
│   │   └── system/core/      ← winrm_handler.py, terminal handlers
│   └── requirements.txt
├── TESTES.html               ← Plano de testes offline (abrir no navegador)
└── CLAUDE.md                 ← este arquivo
```

## Como rodar

```bash
# Backend (deps Python)
cd python
pip install -r requirements.txt

# Subir tudo (mata porta 8000 se ocupada, sobe Vite + Electron + backend)
python python/main.py
```

Atalhos úteis:
- Backend isolado para debug: `cd python && python -m api.server`
- Build do portátil: `.\build_system.bat` na raiz (gera `python\dist\Ferramentas.de.Rede.v<versão>.exe`, ~40 MB)
- Smoke test: `curl http://127.0.0.1:8000/` deve retornar `{"status":"online","version":"..."}`

### Como buildar o portátil (LEIA SE FOR FAZER BUILD)

O portátil é **single-file ~40 MB** via `python/build_webview.spec` (FastAPI + pywebview num exe só, usa WebView2 do Windows para a UI). Pipeline correto, do `build_system.bat`:

1. `cd electron && npm install`
2. `cd electron && npx vite build` (gera `electron/dist/`)
3. `cd python && pyinstaller build_webview.spec --clean --noconfirm`

Artefato: `python\dist\Ferramentas.de.Rede.v<versão>.exe`.

**NUNCA** rode `npm run build` inteiro nem `electron-builder`. Eles geram um "portátil" de **400 MB** com Chromium inteiro empacotado — isso **não é portátil** e foi explicitamente rejeitado. Existe um `electron-builder.yml` no repo só por inércia; se for refatorar o build, remova-o em vez de chamá-lo.

## Validação obrigatória antes de commitar

Sempre, em qualquer PR/commit:

```bash
# Frontend
cd electron && npx tsc --noEmit          # tem que ser zero erros
cd electron && npx vite build            # tem que concluir limpo

# Backend
python -m py_compile <arquivos_alterados>
```

Se mexeu em arquivos do backend que estão importados em runtime, vale rodar `python -m api.server` localmente e fazer um `curl` rápido nos endpoints alterados.

## Regras duras (não negocie)

### Segurança

- **Backend bind em `127.0.0.1` por default**. Override com `NT_API_HOST=0.0.0.0` quando o usuário pedir explicitamente. Nunca volte a `0.0.0.0` como default.
- **CORS travado** em `localhost:5173` / `127.0.0.1:5173`. Override via `NT_CORS_ORIGINS`.
- **Nunca interpole input do usuário em script PowerShell**. Passe via env vars que o script remove na entrada (ver [`open_external_terminal`](python/api/routes/network.py) e [`launch-msra`](electron/electron/main.ts)).
- **Todo handler IPC do Electron valida argumentos** com `isSafeHost` / `isSafeExternalUrl` / `isSafeShowItemPath` etc. ([electron/main.ts](electron/electron/main.ts)). Não adicione handler novo sem validador.
- **Nunca log de senha** — nem em arquivo, nem em variável persistente. PowerShell histórico, processo command line, e dump de memória são todos vetores conhecidos.

### Multi-domínio / Multi-VLAN

- **Toda operação de rede aceita `source_ip` opcional** (ping, traceroute, discovery, check_host_status). Windows: `-S`, Linux: `-I`/`-s`. Cache de status chaveia por `(ip, source_ip)`.
- **Não use o resolver do sistema cegamente** quando há `dns_server` cadastrado para a rede do host. Use [`dns_resolver.resolve_ip`](python/src/network/dns_resolver.py) com o servidor explícito.
- **Modelo de "rede"** vive em `Settings.networks: List[NetworkConfig]` ([settings.py](python/api/routes/settings.py)). Qualquer feature multi-VLAN deve consumir essa lista, não inventar paralelo.
- **Hosts ganham `network_id` / `network_name` inferidos no GET** ([`_match_network`](python/api/routes/network.py)). Não persista — é derivado do IP × CIDRs cadastrados.

### Estabilidade / Performance

- **SQLite**: todas as escritas usam o decorator `@_retry_on_locked` + `RLock` ([database.py](python/src/core/database.py)). Se criar método novo de write, aplique o mesmo padrão.
- **Polling no frontend**: use `setTimeout` recursivo com backoff exponencial. **Nunca** `setInterval` fixo para chamada de API que pode falhar (ver [MonitoringContext.tsx](electron/src/contexts/MonitoringContext.tsx)).
- **DNS / MAC resolution no monitor**: rodar paralelo via `ThreadPoolExecutor` (16 workers). Síncrono trava com 100+ hosts.
- **Vendor lookup nunca bloqueia start** — `_initialize()` é best-effort; download é apenas via `update_database()` explícito.

### URLs / configuração

- **Toda URL de backend no frontend** vem de `API_BASE` / `WS_BASE` em [src/config/api.ts](electron/src/config/api.ts). Configurável via `VITE_API_HOST` / `VITE_API_PORT`. Não escreva `http://127.0.0.1:8000` literal em lugar nenhum.

### Logs / arquivos

- **Logs vão para `APP_DATA_DIR`** (`%APPDATA%\FerramentasDeRede\` no Windows). Nunca CWD nem Desktop. Use o helper `_append_log` em [winrm_handler.py](python/src/system/core/winrm_handler.py) como referência.

### Defensiva

- Hosts vindos do backend **podem ter `name`/`address` null** (discovery sem hostname resolvido ainda, DBs antigas). Sempre coalescer com `?? ''` antes de operações de string. Já tivemos um crash com `null.localeCompare`.
- `try/except: pass` é proibido. Use `except Exception as e: logging.debug(...)` no mínimo. Bare except engole `KeyboardInterrupt` e `SystemExit`.

## Fluxos comuns

### Bumpar versão do app

**Regra obrigatória de release** (registrada por solicitação do dono em 2026-05-27):

> Toda atualização do `.exe` portátil que ship pra usuário (Desktop ou GitHub release) **deve** bumpar a versão e ter as correções listadas no `AboutModal`. Não distribuir `.exe` regerado com a mesma versão — usuário não consegue distinguir builds e perde o registro do que mudou.

**Fonte única: [electron/package.json](electron/package.json)** — campo `version`. Tudo o mais deriva dela.

1. Editar `version` em `electron/package.json` (incrementar patch, minor ou major conforme escopo das mudanças).
2. Adicionar entrada no topo do array `CHANGELOG` em [electron/src/data/changelog.ts](electron/src/data/changelog.ts). Cada mudança é tipada por `kind`: `feat | fix | perf | security | ui | refactor | docs`. **Não edite o `APP_VERSION`** — ele é importado de `package.json`. **Liste todos os commits desde a tag anterior** (`git log --oneline vX.Y.Z..HEAD`) para que o operador veja o que mudou ao clicar em "Versão X.Y.Z" no Sobre.
3. `cd electron && npm install --package-lock-only` para sincronizar `package-lock.json`.
4. Rebuild do portátil (`build_system.bat` ou `python/build_exe.bat`). Asset final é `python/dist/Ferramentas.de.Rede.v<versão>.exe`.
5. Substituir o `.exe` em todos os locais de distribuição (Desktop do dono, GitHub release `gh release upload v<versão> --clobber`, etc.). Tag git nova só quando for release pública (eg. `git tag v1.2.5 && git push --tags`).

Derivações automáticas:
- Backend Python lê em runtime via `src/config/settings.py:_read_app_version()` (cai em ENV `NT_APP_VERSION` se setado, depois `electron/package.json` no checkout, depois no bundle PyInstaller).
- `python/build_webview.spec` lê `electron/package.json` no momento do build e empacota uma cópia no bundle para o runtime resolver depois.
- `electron/src/data/changelog.ts` faz `import pkg from '../../package.json'`.
- `GET /` do backend retorna `version: APP_VERSION` — não há mais string hardcoded.

`AboutModal` e `LoadingScreen` importam de `data/changelog.ts`. O popup de changelog é aberto clicando em "Versão X" no Sobre.

### Adicionar uma nova rota no backend

1. Definir o handler em `python/api/routes/<arquivo>.py` com type hints (Pydantic models).
2. Se for ação destrutiva ou usar credenciais, pensar em validação (CIDR, IP, hostname seguro). Existem helpers como `_is_safe_remote_target` em [network.py](python/api/routes/network.py).
3. Se for operação de rede, aceitar `source_ip` opcional e propagar.
4. No frontend, consumir via `${API_BASE}/...`.
5. Atualizar [TESTES.html](TESTES.html) com um teste novo (ID, severidade, comando, expected).

### Adicionar uma nova feature de UI

1. Componentes vivem em `electron/src/components/<Page>/<Component>.tsx`.
2. Estado global → context (em `electron/src/contexts/`). Estado de tela → useState local.
3. Para fetch de API, importar `API_BASE` de `../config/api`.
4. Ler tipos compartilhados de [types.d.ts](electron/src/types.d.ts) ou de páginas que exportam (ex.: `NetworkConfig` de [Settings.tsx](electron/src/pages/Settings.tsx)).
5. Tailwind only, esquema dark (`bg-zinc-900`, `text-zinc-300`, `border-zinc-800`, accent `text-blue-400`).
6. Tudo em **PT-BR** na UI (botões, labels, toasts).

## Convenções de código

- **TypeScript estrito** — `tsc --noEmit` é zero-erros, sempre.
- **Lucide-react** para ícones (já tudo usa).
- **clsx** para classes condicionais.
- **Tailwind** para estilos. Sem CSS modules, sem styled-components.
- **Português** em strings de UI; **inglês** em comentários, nomes de função/variável, mensagens de log/error técnico, e textos do `CLAUDE.md` que não sejam dicas para o usuário final.

## Convenções de commit

Conventional commits curtos no título, contexto explicando "porquê" no corpo:

```
feat(api): describe in imperative one line

Why this change:
- bullet 1
- bullet 2

Implementation note if non-obvious.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Tipos comuns: `feat`, `fix`, `refactor`, `perf`, `chore`, `docs`, `style`. Escopo opcional: `(api)`, `(ui)`, `(dashboard)`, `(winrm)`, etc.

**Nunca** commit pré-existente do usuário (ver "O que NÃO mexer" abaixo).

## Push para origin

- `origin/main` é `github.com/raphaelredes/ferramentasderede`.
- Push normal é `git push origin main`. Se aparecer divergência, **não force-push sem confirmar com o usuário**.
- Histórico do remoto pode estar inconsistente (já aconteceu de remoto e local terem ancestrais diferentes). Use `--force-with-lease` em vez de `--force`.

## O que NÃO mexer

Estes arquivos têm modificações pré-existentes do dono do repo que **não vieram de agentes**. Nunca commit junto com mudanças minhas/suas. Se aparecerem como modified no `git status`, ignore:

- `python/build_webview.spec` — versão do PyInstaller spec
- `python/src/system/scripts/list_connected_users.ps1` — script PS

Se o dono pedir explicitamente para commitar, confirme antes.

## Worktrees

O Claude Code pode criar worktrees em `.claude/worktrees/<nome>/` quando rodar isolado. Esse diretório está no `.gitignore`. **Trabalhe direto no diretório principal** (`C:\Users\raphael.rego\Desktop\ferramentasderede\`) — o usuário desse projeto prefere isso e não quer mais usar worktrees.

## Plano de testes

[TESTES.html](TESTES.html) é o documento vivo de validação. Tem 27 testes organizados em 9 seções (preparação, segurança, build, multi-VLAN ⭐, estabilidade, WinRM, vendor/logs, regressão, troubleshooting). Abre offline em qualquer navegador.

**Sempre que adicionar feature visível ao usuário**, adicione um teste correspondente. Marque com `<div class="test new">` para destacar como novo.

## Tech-debt registrado (não-fazer-agora consciente)

Estes são problemas conhecidos com decisão explícita de não atacar agora. Não comece a refatorar sem entender o porquê:

1. **Virtualização de listas grandes** — Dashboard renderiza todos os cards. Conflita com `@dnd-kit/sortable` (precisa do DOM nodes). Só importa com 500+ hosts; ninguém na base atual tem isso.
2. **ToolsContext (~540 linhas)** — Ping/Trace/Scanner num único provider. Funcional, só verboso. Splittar criaria sincronização entre providers que custa mais que economiza.
3. **Vendor DB embarcada** — fallback embutido cobre 95% dos casos corporativos. Embarcar arquivo IEEE adicionaria ~3MB ao bundle pra ganho marginal.
4. **Electron 30 → LTS atual** — bump requer sessão dedicada com smoke test do executável em Windows. Riscos identificados: `setWindowOpenHandler`/`will-navigate` mudaram entre 30 e 33; `vite-plugin-electron 0.28` precisa subir junto; sandbox que acabamos de habilitar foi reforçado em 32 (verificar regressão de IPC). 27 vulnerabilidades pendentes no `npm audit` são todas de transitivas do Electron — bumpar limpa a maioria. **Critério para tirar daqui: ter capacidade de rodar smoke test do .exe em CI ou janela de manutenção dedicada.**

Ver seção "Tech-debt restante" no final do TESTES.html.

## Variáveis de ambiente

| Var | Default | Uso |
|---|---|---|
| `NT_API_HOST` | `127.0.0.1` | Bind do uvicorn |
| `NT_API_PORT` | `8000` | Porta do backend |
| `NT_CORS_ORIGINS` | (localhost:5173) | Lista CSV de origens permitidas |
| `VITE_API_HOST` | `127.0.0.1` | Onde frontend procura backend (build time) |
| `VITE_API_PORT` | `8000` | (idem) |

## Caminhos importantes

| Path | Conteúdo |
|---|---|
| `%APPDATA%\FerramentasDeRede\` | Banco SQLite, configurações, logs |
| `%APPDATA%\FerramentasDeRede\errors.log` | Erros de PowerShell remoto |
| `%APPDATA%\FerramentasDeRede\terminal_debug.log` | Trace do terminal interativo |
| `%TEMP%\network_tools_debug.log` | Log do main process do Electron |

## Endpoints novos (multi-VLAN)

| Método | Path | Descrição |
|---|---|---|
| GET | `/network/interfaces` | Lista NICs IPv4 ativas via psutil |
| POST | `/network/dns/resolve` | Forward (`name`) ou reverse (`ip`) com `dns_server` opcional |
| POST | `/tools/ping` | Body aceita `source_ip` |
| POST | `/tools/traceroute` | Body aceita `source_ip` |
| POST | `/network/discovery` | Body aceita `source_ip` |

## Códigos de erro WinRM

| Code | Significado | Ação |
|---|---|---|
| `AUTH_FAILED` | Credenciais recusadas | Verificar senha; em multi-domínio qualificar com DOMINIO\ |
| `CROSS_DOMAIN_AUTH` | Falha Kerberos | Verificar trust ou usar UPN |
| `NETWORK_UNREACHABLE` | Sem rota / timeout | Conferir NIC, firewall, rota |
| `WINRM_DISABLED` | Porta 5985 recusada | `Enable-PSRemoting -Force` no destino |
| `TRUSTED_HOSTS_REQUIRED` | Não está em TrustedHosts | App pede confirmação |

## Antes de pedir confirmação ao usuário

Coisas reversíveis (editar arquivo local, criar branch, rodar tsc, vite build, py_compile, npm install): **faça**.

Coisas com blast radius externo: **confirme**:
- `git push --force` ou `--force-with-lease`
- `git reset --hard`
- Deletar branches
- Tocar em arquivos que estão como "não-meus" (`build_webview.spec`, `list_connected_users.ps1`)
- Criar release / publicar / acionar CI
- Mexer em código que afeta credenciais armazenadas

## Se algo der errado

1. Backend não sobe → `%TEMP%\network_tools_debug.log` + rodar `python -m api.server` isolado
2. `ModuleNotFoundError: dns` → `pip install -r python/requirements.txt`
3. Aba "Redes / VLANs" não aparece → build antiga; `cd electron && npx vite build`
4. CORS error → verifique `NT_CORS_ORIGINS`
5. `database is locked` → o decorator de retry já cuida; se persistir, pode ter múltiplos processos do backend rodando
