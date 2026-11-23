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
- Garantir OPSEC antes de compilar: rodar `python scripts/check_opsec.py` (código de saída `0` obrigatório).
- Preferir `cmd /c build_system.bat` na raiz (nunca usar `call` no PowerShell).
- Se `npm install` travar (>3 min, CPU ~0) e `electron/node_modules` existir, matar a task
  e rodar: `cmd /c "cd electron && npx vite build && cd ..\python && build_exe.bat"`.
- Artefato: `python\dist\Ferramentas.de.Rede.v<versão>.exe` (~46 MB).
- Rodar o build como task em background e aguardar a notificação (sem polling).
- Ao concluir, coletar hash e tamanho exatos no PowerShell:
  `(Get-FileHash "python\dist\Ferramentas.de.Rede.v<versão>.exe" -Algorithm SHA256).Hash` e
  `(Get-Item "python\dist\Ferramentas.de.Rede.v<versão>.exe").Length`.

## 4. Git + Release
- Antes de commitar, verificar `python scripts/check_opsec.py` e `python scripts/check_opsec.py --staged` (saída `0` obrigatória).
- `git add` apenas os arquivos alterados (nunca `git add -A`: há `dist/` e `build/`).
  Se `electron/src/data/changelog.ts` não entrar por regra de ignore em arquivos novos, usar explicitamente o arquivo modificado já rastreado.
- `git push` escreve em stderr: o exit code 1 do PowerShell é falso alarme se a saída
  contém `old..new  main -> main`.
- Gravar as notas da release em arquivo temporário UTF-8 e publicar com `--notes-file` para evitar quebra de aspas e acentuação no PowerShell:
  `gh release create v<versão> "python\dist\Ferramentas.de.Rede.v<versão>.exe" --repo raphaelredes/ferramentasderede --target main --title "Ferramentas de Rede v<versão>" --notes-file <caminho_notas.md>`
- Verificar: `gh release view v<versão> --repo raphaelredes/ferramentasderede --json url,assets`
  (NÃO combinar `--jq` com expressões que contenham espaços no PowerShell; quebra os argumentos).
- Conferir o workflow: `gh run list --repo raphaelredes/ferramentasderede --workflow winget.yml --limit 2`.

## 5. Resposta final obrigatória
- Link da release: `https://github.com/raphaelredes/ferramentasderede/releases/tag/v<versão>`
- Link direto do `.exe`: `https://github.com/raphaelredes/ferramentasderede/releases/download/v<versão>/Ferramentas.de.Rede.v<versão>.exe`
- **Prompt pronto para copiar** destinado ao computador/agente que hospeda o site oficial (`https://www.ferramentasderede.com.br/`), contendo versão, data, link direto do `.exe`, URL da release, hash SHA-256, tamanho exato e resumo das novidades/changelog.

Template padrão do bloco pronto para copiar:
```text
Atualize o site oficial Ferramentas de Rede (https://www.ferramentasderede.com.br/) para a nova versão v<versão>:
- Versão: <versão>
- Data da Release: <DD/MM/AAAA> (<YYYY-MM-DD>)
- Link direto do download (.exe portátil Windows x64): https://github.com/raphaelredes/ferramentasderede/releases/download/v<versão>/Ferramentas.de.Rede.v<versão>.exe
- Link da página da Release no GitHub: https://github.com/raphaelredes/ferramentasderede/releases/tag/v<versão>
- Nome do arquivo: Ferramentas.de.Rede.v<versão>.exe
- Tamanho: <bytes> bytes (~<MiB> MiB)
- SHA-256: <SHA256>
Resumo do Changelog:
- <principais itens da release>
Atualize badges, botões de download, changelog, metadados SEO/OpenGraph e valide todos os links apontando para v<versão>.
```
