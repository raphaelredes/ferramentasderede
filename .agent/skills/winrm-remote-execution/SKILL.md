---
name: winrm-remote-execution
description: >-
  Referência de arquitetura para execução remota de comandos e ações (msg.exe,
  power actions, services) via WinRM/PowerShell em vez de RPC de rede direto.
  Cobre diferenças de execução local vs remota, isolamento de sessão e TrustedHosts.
---

# Arquitetura de Execução Remota (WinRM vs. RPC de Rede)

Este documento orienta o agente sobre o funcionamento e decisões de projeto na execução de comandos remotos do Ferramentas de Rede.

## 1. Princípio do Túnel Local (Por que o CMD do operador falha e o app funciona)
- Comandos utilitários do Windows (ex: `msg.exe /server:<IP>`, shutdown remoto via RPC porta 445/135) frequentemente falham em ambientes modernos porque o Windows desabilita chamadas RPC remotas de terminal (`AllowRemoteRPC = 0`) e restringe acessos UAC em rede.
- **A Solução do App:** O sistema não dispara o comando externamente contra o alvo via RPC. Ele abre um canal administrativo seguro via **WinRM (porta 5985/5986)**, cria um `RunspacePool` do PowerShell dentro do host de destino e executa o binário (ex: `msg.exe * "texto"`) **localmente no próprio host**.
- Como o processo roda localmente dentro da máquina de destino sob o contexto da credencial fornecida, ele não sofre o bloqueio de RPC de rede.

## 2. Isolamento de Sessão (Session 0)
- WinRM executa na **Sessão 0** (não interativa).
- Utilitários gráficos comuns como caixas de diálogo do Windows Forms ou VBScript ficam invisíveis ao usuário logado na Sessão 1.
- `msg.exe` é utilizado especificamente porque o subsistema de Terminal Services redireciona a mensagem para as sessões interativas dos usuários conectados (`*`), superando a barreira da Sessão 0.

## 3. Ambientes Multi-Domínio (Cross-Domain) e TrustedHosts
- **Kerberos vs. NTLM:** Dentro do mesmo domínio AD, o WinRM utiliza Kerberos transparente. Em redes com domínios diferentes sem relação de confiança mútua, Kerberos falha (`CROSS_DOMAIN_AUTH`) e o protocolo faz fallback para NTLM.
- **TrustedHosts:** Para NTLM sobre HTTP na porta 5985, o cliente Windows exige que o IP esteja em `WSMan:\localhost\Client\TrustedHosts`.
- **Elevação Efêmera:** O backend usa `TemporaryTrustedHosts` para injetar o IP no registro da máquina local durante a operação e limpá-lo imediatamente após a conclusão, garantindo segurança e transparência.

## 4. Validação Estrita de FQDN e Prevenção de Suffix Bleed (Resolução de Nomes)
- **Problema do Nome Curto (NetBIOS/PTR):** Quando o DNS reverso ou o banco retorna um nome curto (ex: `ADM-36494`), qualquer tentativa de conexão direta ou override de hostname faz o Windows resolver o nome anexando o sufixo DNS primário do computador do operador (ex: `betim.pmb`), atingindo potencialmente outra máquina ou um IP inacessível.
- **Validação de FQDN:** O backend deve sempre testar os domínios candidatos (redes cadastradas, domínios confiados da floresta como `saude.betim`, `betim.pmb`) concatenando `f"{hostname}.{dominio}"` e conferindo se a resolução direta bate exatamente com o IP alvo (`socket.gethostbyname(fqdn) == target_ip`).
- **Descarte de Hostname Inválido:** Se o nome curto ou FQDN resolver para um IP diferente do alvo, ele deve ser sumariamente descartado para conexões e SPN Kerberos, prevenindo timeouts de 15 segundos em máquinas erradas.

## 5. Hierarquia de Erros e Variantes Cross-Domain
- **Precedência de Códigos:** Respostas HTTP ativas do serviço WinRM (como HTTP 401 `AUTH_FAILED` ou `CROSS_DOMAIN_AUTH`) comprovam conectividade de rede e porta 5985 aberta. Elas **nunca** devem ser sobrepostas por `NETWORK_UNREACHABLE` proveniente de tentativas de fallback em hostnames incorretos. A precedência obrigatória é:
  `CROSS_DOMAIN_AUTH > AUTH_FAILED > TRUSTED_HOSTS_REQUIRED > WINRM_DISABLED > NETWORK_UNREACHABLE > UNKNOWN`
- **Geração de Credenciais Cruzadas:** Em ambientes com relação de confiança entre domínios, quando o domínio do alvo difere do domínio informado pelo usuário (ou preenchido pelo modal), o handler deve testar automaticamente as formas `DOMINIO_ALVO\usuario`, `usuario@dominio_alvo` e `usuario` simples.

## 6. Gravação de TrustedHosts no Registro (armadilhas confirmadas)
- **Nome do valor:** o WinRM cliente persiste a lista em
  `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN\Client`, valor REG_SZ
  **`trusted_hosts`** (minúsculo, underscore), formato `a,b,c` (vírgula sem espaço).
  Gravar em `TrustedHosts` (CamelCase) cria um valor órfão que o Windows ignora.
- **Chave pode não existir** em PCs onde o WinRM cliente nunca foi configurado: usar
  `winreg.CreateKeyEx(..., KEY_SET_VALUE | KEY_WOW64_64KEY)` e não apenas `OpenKey`.
- **Elevação:** escrever em HKLM exige admin e o app é publicado com `uac_admin=False`.
  Fallback implementado: `ShellExecuteExW(verb="runas")` sobre `reg.exe add ... /reg:64`
  com `SW_HIDE`, seguido de leitura de confirmação. Sempre expor o motivo da falha
  (`WinRMHandler.last_trusted_hosts_error`) até a UI; nunca devolver só "Erro ao adicionar".
- **Teste local:** o shell do agente costuma ser admin e mascara o bug de permissão.
  Valide também a lógica pensando num usuário sem elevação.
- **Relevância real:** o app usa `pypsrp` (Python puro), que **não consulta** o TrustedHosts
  do Windows. A lista só decide, após uma falha de conexão, se o modal
  `TRUSTED_HOSTS_REQUIRED` aparece. Adicionar um host não corrige falhas de NTLM/Kerberos.
