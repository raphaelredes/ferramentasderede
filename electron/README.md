# Frontend — Ferramentas de Rede

Interface web da aplicação **Ferramentas de Rede**, construída com **React 18**, **TypeScript**, **Vite** e **Tailwind CSS**.

Em produção, os artefatos estáticos gerados em `electron/dist/` são empacotados dentro do executável portátil Python via `python/build_webview.spec` e renderizados pelo **Microsoft Edge WebView2 (`pywebview`)**.

## Comandos Úteis

```powershell
# Instalar dependências
npm install

# Checagem estrita de tipos TypeScript (deve retornar zero erros)
npx tsc --noEmit

# Build dos ativos estáticos de produção (gera electron/dist/)
npx vite build

# Servidor de desenvolvimento Vite (porta 5173)
npm run dev

# Análise estática ESLint
npm run lint
```

> **Atenção:** não execute `npm run build` para gerar distribuíveis. O empacotamento oficial portátil é feito na raiz do repositório via `cmd /c build_system.bat` (Python + PyInstaller + WebView2, ~44 MB). Consulte o [README principal](../README.md) e [python/BUILD_README.md](../python/BUILD_README.md).
