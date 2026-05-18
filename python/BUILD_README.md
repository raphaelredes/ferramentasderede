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

## Solução de problemas

### "Frontend não encontrado em ../electron/dist/"
Você esqueceu de rodar `vite build` antes. Use `build_system.bat` da raiz, que faz a ordem certa automaticamente.

### Erro de permissão durante o build
- Feche qualquer instância do executável rodando
- Pare o `python main.py` se estiver rodando em dev mode

### Executável não inicia ao dar duplo-clique
- Verifique se o Windows tem o **Edge WebView2 Runtime** instalado (em Windows 11 já vem; em Windows 10 antigo pode precisar instalar)
- Veja `%TEMP%\network_tools_debug.log` para erros do main process
- Veja `%APPDATA%\FerramentasDeRede\errors.log` para erros do backend

### Aviso de SmartScreen "Fornecedor desconhecido"
Esperado — o exe não está assinado. Tech-debt conhecida (precisa certificado EV ou OV). Clique em **Mais informações → Executar mesmo assim**.
