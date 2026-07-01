# Build Instructions — Ferramentas de Rede (Portátil)

## Como criar o portátil

### Método 1: Script Automático (Recomendado)

Na **raiz do projeto** (não dentro de `python/`):

```cmd
.\build_system.bat
```

Faz tudo na ordem certa: `npm install` → `vite build` → `pyinstaller build_webview.spec`.

### Método 2: Manual

```cmd
:: 1. Frontend (gera electron/dist/)
cd electron
npm install
npx vite build

:: 2. Backend + bundle portátil
cd ..\python
pyinstaller build_webview.spec --clean --noconfirm
```

## Localização do executável

```
python\dist\Ferramentas.de.Rede.v<versão>.exe
```

A versão vem de `electron/package.json` (fonte única). Tamanho típico: **~40 MB**.

## ⚠️ Não use os outros caminhos

| Caminho | Por que não |
|---|---|
| `npm run build` no electron | Invoca `electron-builder --target portable` → gera um "portátil" de **400 MB** com Chromium dentro. Não é portátil. |
| `pyinstaller build_config.spec` | Spec antigo — foi removido. Construía um `server.exe` headless para o caminho Electron, que não usamos mais. |

O **único** spec PyInstaller que importa é `build_webview.spec`. Ele empaca:
- `main_webview.py` (entry FastAPI + pywebview)
- `electron/dist/` → pasta `gui/` dentro do exe
- `python/src/system/scripts/*.ps1` → scripts WinRM
- Dependências (cryptography, pypsrp, dnspython, etc.)

## Requisitos

- Python 3.13+
- `pip install -r requirements.txt` (em `python/`)
- Node 18+ e `npm install` (em `electron/`)
- PyInstaller (`pip install pyinstaller`)

## Por que o portátil é assim

Em vez de empacotar Chromium (Electron), o portátil usa **WebView2** do próprio Windows para renderizar o frontend React. Isso reduz ~360 MB para ~40 MB e melhora muito o tempo de boot (~1s vs ~5s).

## Primeira execução num PC recém-formatado (WebView2 + admin)

O WebView2 é um componente do Windows: **Windows 11 já vem com ele**; um **Windows 10 recém-formatado / sem updates / LTSC** pode não ter. Sem esse runtime o pywebview 6.1 não tem fallback e o app não renderiza.

Como o portátil lida com isso (`main_webview.py:preflight_webview2`):

1. Detecta o WebView2 pelo registro (GUID Evergreen `{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` em `HKLM\...\EdgeUpdate\Clients`, 64/32-bit e HKCU).
2. Se existe → abre direto.
3. Se falta → mostra um diálogo em PT-BR e, ao confirmar, roda o **bootstrapper oficial da Microsoft embarcado** em `bin/MicrosoftEdgeWebview2Setup.exe` (~1,6 MB, assinado). Ele baixa e instala o runtime — **precisa de internet nessa primeira vez**. Sem internet, o app orienta o usuário a instalar manualmente em vez de travar.

Decisão de projeto (2026-07-01): **um único .exe autoinstalável**, sem variante offline. Embarcar o runtime completo (~180 MB) foi descartado — os PCs-alvo têm internet na 1ª execução. Se um dia surgir necessidade air-gapped, o gancho `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` (`_wire_bundled_webview2`) já existe: basta dropar uma cópia fixed-version do runtime em `webview2_runtime/` ao lado do exe.

**Sem admin:** o `.spec` usa `uac_admin=False`. Uma auditoria confirmou que nada local precisa de elevação (ping/tracert nativos, escrita só em `%APPDATA%`, WinRM remoto usa credenciais do alvo). Isso permite que usuários corporativos **sem** senha de admin abram o app.

## Solução de problemas

### "Frontend não encontrado em ../electron/dist/"
Você esqueceu de rodar `vite build` antes. Use `build_system.bat` da raiz, que faz a ordem certa automaticamente.

### Erro de permissão durante o build
- Feche qualquer instância do executável rodando
- Pare o `python main.py` se estiver rodando em dev mode

### Executável não inicia ao dar duplo-clique
- Se faltar o **Edge WebView2 Runtime**, o app agora **detecta e oferece instalar** (bootstrapper embarcado; requer internet na 1ª vez) — não trava mais em silêncio. Ver "Primeira execução num PC recém-formatado" acima.
- Se o app fica preso na tela "Inicializando sistema..." (splash estático, sem avançar), rode-o com `NT_WEBVIEW_DEBUG=1` e abra o DevTools (botão direito → Inspecionar) para ver o erro no Console.
- Veja `%TEMP%\network_tools_debug.log` para erros do main process
- Veja `%APPDATA%\FerramentasDeRede\errors.log` para erros do backend

### Aviso de SmartScreen "Fornecedor desconhecido"
Esperado — o exe não está assinado. Tech-debt conhecida (precisa certificado EV ou OV). Clique em **Mais informações → Executar mesmo assim**.
