# Guia 06: Tela final (tocar e avançar capítulo, refazer trecho, salvar M4B e mostrar no Finder)

Objetivo: Na tela final (`ready.html`), tocar um capítulo e avançar para o meio com suporte a `Range`, refazer um trecho marcado, salvar o arquivo M4B e acionar o botão de mostrar no Finder (R30, R31, R32).

Preparação:
- Projeto sintético com geração concluída (`status: "pronto"`) usando `tests.fake_engine:FakeEngine` e com um trecho marcado em `work/progress.jsonl` (`{"kind": "flagged", "ch": "01", "chunk": 0}`) para exercitar a ação de refazer na interface.

Passos:
1. Abrir `ready.html?id=<projeto>` -> esperado: lista os capítulos incluídos com reprodutor `<audio>`, exibe o trecho marcado no capítulo 1 com o botão "Refazer trecho 1" e os botões superiores "Salvar M4B" e "Mostrar no Finder".
2. Tocar o áudio do capítulo 1 e avançar (`currentTime`) para o meio do capítulo -> esperado: o servidor responde com HTTP 206 (`Accept-Ranges: bytes`, `Content-Range`) e o `<audio>` posiciona o tempo no meio sem erro (R30).
3. Clicar em "Refazer trecho 1" -> esperado: o botão mostra "Refazendo...", apenas o trecho indicado é regerado e o capítulo é remontado, exibindo a confirmação "Trecho refeito." (R31).
4. Clicar em "Salvar M4B" -> esperado: monta o audiolivro M4B e exibe mensagem de confirmação em português simples, sem vazar caminho completo da máquina na tela (R32, R38).
5. Clicar em "Mostrar no Finder" -> esperado: aciona a rota `/api/projects/<id>/reveal` e exibe "Pasta aberta no Finder." (R32).

Capturas:
- Passo 1: `tests/ui/capturas/06-pronto-inicial.png`
- Passo 3: `tests/ui/capturas/06-pronto-refeito.png`
- Passo 4: `tests/ui/capturas/06-pronto-salvar-m4b.png`

Critério de aprovação:
- Áudio toca e avança com suporte a `Range` (206) (R30).
- Refazer trecho regera apenas o trecho e remonta o capítulo (R31).
- Botões "Salvar M4B" e "Mostrar no Finder" funcionam e não expõem caminhos internos da máquina na interface (R32).

Resultado: aprovado na 2ª rodada.
- Histórico (1ª rodada): reprovado porque `_flagged_from_progress` mantinha o trecho marcado após refazer e `"Salvar M4B"` exibia o caminho absoluto completo no disco.
- 2ª rodada:
  - Passo 1 e 2 (Tocar e avançar com Range, R30): player `<audio>` carregou a duração, avançou para `3,5 s` e respondeu HTTP 206 `Range` (`tests/ui/capturas/06-pronto-inicial.png`).
  - Passo 3 (Refazer trecho, R31): ao clicar em `"Refazer trecho 1"`, apenas `01_0000.wav` e `01.m4a` foram regerados, a tela exibiu `"Trecho refeito."` e o aviso de trecho marcado desapareceu (`flagCount: 0`, `flagText: null`) (`tests/ui/capturas/06-pronto-refeito.png`).
  - Passo 4 (Salvar M4B, R32 / R38): clicando em `"Salvar M4B"`, o arquivo `Crônicas da Praça.m4b` (974 KB) foi gravado e baixado, e `#ok` exibiu `"M4B salvo: Crônicas da Praça.m4b na pasta Downloads."` sem nenhum caminho interno de máquina (`tests/ui/capturas/06-pronto-salvar-m4b.png`).
  - Passo 5 (Mostrar no Finder, R32): acionou `POST /api/projects/cronicas-da-praca/reveal` e exibiu `"Pasta aberta no Finder."`.
