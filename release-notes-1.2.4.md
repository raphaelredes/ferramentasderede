# Ferramentas de Rede v1.2.4

**Coleta oportunista de informações + UX refinada**

## Novidades

- **Coleta oportunista**: quando o operador autentica em um host para qualquer ação (Terminal Remoto, TestConnection, Power Action, abrir Detalhes Avançados, buscar TeamViewer ID), o app coleta em background **MAC, domínio AD real, usuário atual, último boot e disco livre** — tudo persistido sem ação extra. Novo endpoint `/system/host-probe` + script PowerShell enxuto.
- **Confirmação pré-shutdown/restart**: novo diálogo mostra uptime, sessões ativas e reinício pendente antes de mandar a ação destrutiva. Auto-skip quando não há nada para avisar; alerta vermelho quando há usuários ativos ou host reiniciou nos últimos minutos.
- **Terminal Remoto com picker de hosts**: busca por nome/IP/grupo, indicador online/offline, opção "Digitar manualmente". Selecionar um host preenche o IP e o prefixo de domínio (`DOMINIO\`) automaticamente; trocar de host troca o domínio preservando a parte do usuário.
- **Card TeamViewer no Acesso Remoto** com 4 estados (sucesso / loading / needs_credentials / failed) e form inline de credenciais quando o cofre não pode atender — sem mais instruções manuais.
- **Apelido do host** agora é separado do hostname resolvido por DNS. O card mostra apelido se houver, senão o hostname; HostDetails/RDP continuam usando o hostname real.

## Correções

- **Assistência Remota (msra)** com path absoluto + arguments via array PowerShell — corrige caso em que o MSRA abria sem efetivar o `/offerRA`. "Executar como outro usuário" também ajustado.
- **Remover host a partir do popup de detalhes** agora fecha o popup automaticamente.
- **Modais de confirmação** (DeleteHost, ConfirmationModal) elevados para z-[110] — ficam acima do HostDetailsModal.
- **"% de perda" oculto quando offline** (já redundante com "HOST OFFLINE"); critério de online agora consolidado (não pisca verde em ping isolado dentro de 96% de perda).

## Performance

- **Persistência granular**: atualizações de status do monitor usam `UPDATE` de coluna em vez de `DELETE+INSERT` da tabela inteira (gargalo principal em 100+ hosts). PATCH `/hosts/{address}` também tem caminho rápido.
- **Monitor migrado** de 1 thread/host para `ThreadPoolExecutor(64)` com scheduler único — escala para 500+ hosts sem esgotar handles do Windows.
- **Code splitting**: Tools, Settings, HostDetails, Security e Terminal viraram chunks lazy. Bundle inicial de 1067 KB → 687 KB.

## Segurança

- `launchMsra`/`launchRdp` do pywebview validam IP e passam via env var (não interpolam em string PowerShell).
- 25 `except:` bare removidos.
- `sandbox: true` + CSP estrita no Electron. Preload restrito (sem `ipcRenderer` genérico).

## Refatoração

- Versão unificada: agora vem só de `electron/package.json` (settings.py lê em runtime, build_webview.spec lê no build, changelog.ts importa). Endpoint `GET /` não tem mais hardcode "2.0.0".

---

**Download**: `Ferramentas.de.Rede.v1.2.4.exe` (~41 MB, build portátil — sem instalador)

Roda em qualquer Windows 10/11 sem dependências externas. Dados em `%APPDATA%\FerramentasDeRede\`.
