---
name: release-portatil-github
description: >-
  Runbook de release do Ferramentas de Rede: bump de versão (após perguntar ao usuário),
  build portátil Python (PyInstaller), commit/push na main e `gh release create` com o .exe,
  incluindo armadilhas do PowerShell/npm/gh neste ambiente.
---

# Release do portátil (Python/PyInstaller, nunca Electron)

## 0. Pré-requisito
Perguntar SEMPRE ao usuário o número da versão. Nunca assumir.

## 1. Arquivos de versão (única fonte: `electron/package.json`)
- `electron/package.json` → `"version"`
- `electron/package-lock.json` → as **2** primeiras ocorrências de `"version"`
- `electron/src/data/changelog.ts` → nova entrada no topo de `CHANGELOG`
- Manifestos WinGet NÃO precisam ser criados: `.github/workflows/winget.yml`
  (winget-releaser) gera o PR quando a release é publicada.

## 2. Edição segura de arquivos
Nunca usar `Get-Content -Raw | Set-Content` (corrompe UTF-8: "—" vira "â€”").
Usar .NET com `UTF8Encoding($false)`:
`[IO.File]::ReadAllText($p,$enc)` / `[IO.File]::WriteAllText($p,$t,$enc)`.
Conferir com `git diff` que só as linhas de versão mudaram.

## 3. Build
- Preferir `cmd /c build_system.bat` na raiz (nunca usar `call` no PowerShell).
- Se `npm install` travar (>3 min, CPU ~0) e `electron/node_modules` existir, matar a task
  e rodar: `cmd /c "cd electron && npx vite build && cd ..\python && build_exe.bat"`.
- Artefato: `python\dist\Ferramentas.de.Rede.v<versão>.exe` (~46 MB).
- Rodar o build como task em background e aguardar a notificação (sem polling).

## 4. Git + Release
- `git add` apenas os arquivos alterados (nunca `git add -A`: há `dist/` e `build/`).
- `git push` escreve em stderr: o exit code 1 do PowerShell é falso alarme se a saída
  contém `old..new  main -> main`.
- `gh release create v<versão> <exe> --repo raphaelredes/ferramentasderede --target main --title ... --notes ...`
- Verificar: `gh release view v<versão> --repo raphaelredes/ferramentasderede --json url,assets`
  (NÃO combinar `--jq` com expressões que contenham espaços no PowerShell; quebra os argumentos).
- Conferir o workflow: `gh run list --repo raphaelredes/ferramentasderede --workflow winget.yml --limit 2`.

## 5. Resposta final obrigatória
Link da release + link direto do .exe:
`https://github.com/raphaelredes/ferramentasderede/releases/download/v<versão>/Ferramentas.de.Rede.v<versão>.exe`
