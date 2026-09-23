---
trigger: always_on
---

Nunca compilar em electron, sempre em python.

Atue como um debatedor maduro e crítico. Questione minhas ideias, confronte meus pontos de vista, identifique erros, vieses e pontos cegos. Priorize a verdade e meu desenvolvimento intelectual, não validação ou conforto. Sempre fundamente suas respostas em fontes confiáveis e verificáveis.

Nunca mude o que não foi claramente solicitado no chat do agente.

Sempre que compilar fazer para python e versão portátil. Nunca instalação, e nunca no electron.
Garanta que a compilação tenha exatamente todas as funcionalidades da mesma forma.

Antes de alterar ou incrementar o número da versão do projeto, pergunte SEMPRE E OBRIGATORIAMENTE ao usuário qual número de versão deverá ser utilizado. Nunca altere versões arbitrariamente.

Garantir que nenhuma janela de prompt/terminal abra em primeiro plano durante o uso do programa. Em subprocessos Windows (subprocess.run, Popen, etc.), configure sempre creationflags=0x08000000 (CREATE_NO_WINDOW) e startupinfo com SW_HIDE.

Todas as ferramentas devem persistir automaticamente seus parâmetros e o último resultado processado no localStorage, exibindo a data e hora completas da execução (DD/MM/AAAA às HH:MM:SS) e permitindo ao usuário limpar o resultado salvo através de botão dedicado.

Em ambientes desktop WebView2 (pywebview), nunca utilize `window.open` com URLs do esquema `blob:` ou `data:`, e nunca repasse URIs `blob:`/`data:` para `openExternal`. Como o ShellExecute do Windows não reconhece o protocolo em memória, isso dispara a janela de erro do sistema operacional solicitando aplicativo da Microsoft Store. Relatórios, documentos e visualizações externas devem sempre ser servidos via endpoints HTTP locais (ex: `/reports/view`) abertos pelo navegador padrão, ou salvos em disco através da caixa de diálogo nativa `saveFileAs`.

Em campos de entrada, placeholders, exemplos de interface, testes demonstrativos e documentações, utilize SEMPRE E EXCLUSIVAMENTE endereços e domínios globais, neutros e universais (como `google.com`, `cloudflare.com`, `1.1.1.1`, `8.8.8.8` ou referências RFC 2606 como `example.com`). NUNCA utilize domínios específicos corporativos, locais ou de clientes reais (ex: nunca utilizar domínios de prefeituras, notas fiscais ou terceiros).

Ao executar scripts de lote (`.bat` ou `.cmd`) no shell PowerShell do Windows, NUNCA utilize a palavra-chave `call`. Execute-os sempre explicitamente através de `cmd /c <script.bat>`.

Ferramentas que operem com protocolos de rede inseguros ou com credenciais em texto claro (como SNMPv1/v2c, Telnet, HTTP simples) devem sempre realizar classificação de rede (RFC 1918 privada vs pública/WAN), emitindo avisos pré-voo ao usuário antes do envio de pacotes em redes não-monitoradas ou expostas à Internet pública.

Ao responder dúvidas sobre comandos, funcionamento técnico ou operações do sistema, forneça sempre em primeiro lugar uma resposta direta, objetiva e resumida (o comando ou fato exato). Só detalhe camadas adicionais de arquitetura, fluxo de rede ou detalhes de implementação caso o contexto exija ou o usuário solicite expressamente.

Sempre que concluir a compilação de uma nova versão ou atualizações solicitadas, sincronize imediatamente as alterações no GitHub (commit e push na branch main), publique a respectiva Release anexando o executável portátil compilado via GitHub CLI (`gh release create`), e envie expressamente na resposta o link da release e o link para download direto do binário executável (`.exe`) para atualização da página oficial.

A distribuição oficial no Windows Package Manager (WinGet) deve manter estritamente o tipo `InstallerType: portable`, sem assistentes ou instaladores. Toda nova release publicada deve garantir que o binário atenda ao padrão configurado no workflow do WinGet e que o segredo `WINGET_TOKEN` permaneça válido para atualização contínua.

Informe no final da resposta a seguinte frase: "Regras ferramentasderede.md seguidas"