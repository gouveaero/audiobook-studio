# Guia 01: Primeiro uso e download do modelo

Objetivo: Verificar a abertura sem livros, a exibição do download do modelo com tamanho e progresso, a simulação de queda de conexão e a tentativa de novo (R36).

Preparação:
- Servidor iniciado com pasta `AUDIOBOOK_STUDIO_HOME` vazia, sem livros e sem modelo baixado (`status: "ausente"` em `/api/models`).
- Nenhum EPUB pré-carregado.

Passos:
1. Abrir a tela inicial (`home.html`) com o token de sessão -> esperado: tela sem livros listados e com aviso ou painel de primeiro uso mostrando o download do modelo (`portuguese_24l`), seu tamanho total (~672 MB) e barra ou percentual de progresso.
2. Iniciar o download do modelo na interface -> esperado: estado muda para `baixando` e a tela mostra o progresso de bytes baixados sobre o total.
3. Simular queda de conexão durante o download -> esperado: a tela exibe mensagem de erro em português ("O download falhou. Verifique a conexão e tente de novo.") sem traceback e oferece botão para tentar de novo.
4. Clicar em tentar de novo -> esperado: o download recomeça e a tela atualiza o progresso até ficar `pronto`.

Capturas:
- Passo 1: `tests/ui/capturas/01-primeiro-uso-home.png`
- Passo 2: `tests/ui/capturas/01-primeiro-uso-progresso.png`
- Passo 3: `tests/ui/capturas/01-primeiro-uso-erro.png`

Critério de aprovação:
- A interface exibe o tamanho do modelo e o progresso no primeiro uso, informa falha de conexão em português simples e permite tentar de novo pela própria tela (R36).

Resultado: aprovado na 2ª rodada.
- Histórico (1ª rodada): reprovado porque nenhuma tela em `ui/` consultava `/api/models` nem `/api/models/download`.
- 2ª rodada (com `AUDIOBOOK_FAKE_DOWNLOAD=1` e `AUDIOBOOK_STUDIO_HOME` vazia):
  - Passo 1: `home.html` abriu sem livros, exibiu o quadro `#modelo` com `"Tamanho do download: cerca de 672 MB."`, botão `"Baixar modelo"` e manteve `"Novo audiolivro"` desabilitado (`epub.disabled = true`, `novoLbl.classList.contains("disabled") = true`) (`tests/ui/capturas/01-primeiro-uso-home.png`).
  - Passo 2: Ao iniciar o download, a barra (`#modeloFill`) e o texto (`#modeloProg`, ex.: `"Baixando… 269 MB de 672 MB (40%)."`) atualizaram na tela (`tests/ui/capturas/01-primeiro-uso-progresso.png`).
  - Passo 3: Na 1ª tentativa simulada, a queda de conexão exibiu `"O download falhou. Verifique a conexão e tente de novo."` e o botão mudou para `"Tentar de novo"` (`tests/ui/capturas/01-primeiro-uso-erro.png`).
  - Passo 4: Ao clicar em `"Tentar de novo"`, a 2ª tentativa completou até `pronto`, ocultou `#modelo` (`hidden = true`) e habilitou `"Novo audiolivro"` (`epub.disabled = false`).
