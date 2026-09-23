---
name: winget-distribution
description: >-
  Guia operacional e referência técnica para publicação, validação e manutenção de pacotes
  portáteis no Windows Package Manager (WinGet) via repositório oficial microsoft/winget-pkgs.
---

# Guia de Distribuição WinGet (Tipo Portable)

Orientações para o agente sobre como gerar manifestos, validar e automatizar releases portáteis no Windows Package Manager sem gerar instaladores.

## 1. Princípio do Pacote Portátil
- **Sem Instalador:** O projeto proíbe o uso de instaladores convencionais (`.msi`, InnoSetup). No WinGet, utilize sempre `InstallerType: portable`.
- **Localização no Windows:** O WinGet baixa o binário cru diretamente do GitHub Releases, salva em `%LocalAppData%\Microsoft\WinGet\Packages\<PackageId>` e cria atalho de execução no `PATH` do usuário.
- **Tamanho:** O arquivo permanece idêntico ao binário portátil (~40 MB).

## 2. Estrutura de Diretórios e Nomenclatura no `microsoft/winget-pkgs`
Hierarquia obrigatória:
`manifests/<primeira_letra_minuscula>/<Publisher>/<PackageName>/<Version>/`
Exemplo: `manifests/r/RaphaelRego/FerramentasDeRede/1.5.0/`

Arquivos necessários:
1. `<Id>.yaml` (ManifestType: version, DefaultLocale: en-US)
2. `<Id>.installer.yaml` (ManifestType: installer, InstallerType: portable, Commands, UpgradeBehavior: uninstallPrevious)
3. `<Id>.locale.en-US.yaml` (ManifestType: defaultLocale — inglês é obrigatório como fallback padrão)
4. `<Id>.locale.pt-BR.yaml` (ManifestType: locale — português como idioma complementar)

*Nota de sintaxe:* O campo `Moniker` só é aceito no arquivo `defaultLocale`. Não incluí-lo em arquivos de localidade adicionais.

## 3. Validação Local
Antes de submeter qualquer manifesto, execute a validação estrita do WinGet:
```powershell
winget validate --manifest <caminho_da_pasta_do_manifesto>
```

## 4. Automação de CI/CD (Releases Futuras)
- O workflow `.github/workflows/winget.yml` monitora publicações de releases (`types: [released]`).
- Utiliza a action `vedantmgoyal2009/winget-releaser@v2`.
- Exige o segredo de repositório `WINGET_TOKEN` configurado com um Personal Access Token clássico (`public_repo`).
- Não utilize tokens Fine-Grained, pois eles não possuem permissão cross-repository para abrir PRs no `microsoft/winget-pkgs`.

## 5. Ciclo de Moderação no GitHub (`microsoft/winget-pkgs`)
- **Novos Pacotes (`New-Package`):** Exigem aprovação manual de um moderador oficial antes do merge. Mensagens como *"Review required"* e *"Merging is blocked"* são padrão de branch protection da Microsoft e indicam que a esteira está aguardando revisão humana.
- **Atualizações (`Update`):** Uma vez que o pacote inicial foi aprovado e integrado, as próximas versões são mescladas automaticamente pelo `winget-bot` assim que os testes automatizados da Azure Pipeline passarem.
