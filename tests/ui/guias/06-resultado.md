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

Resultado: reprovado.
- Passo 1 e 2 (Tocar e avançar com Range, R30): `ready.html` listou os capítulos com `<audio>`, carregou `duration: 85,06 s`, avançou `currentTime` para `3,5 s` e respondeu ao pedido `Range: bytes=0-1023` com HTTP 206 (`Accept-Ranges: bytes`, `Content-Range: bytes 0-1023/498939`) (`tests/ui/capturas/06-pronto-inicial.png`).
- Passo 3 (Refazer trecho, R31 - REPROVADO por estado que não bate com a realidade):
  - O que funcionou no motor: clicar em "Refazer trecho 1" regerou exclusivamente `work/chunks/01_0000.wav` (`mtime` mudou de `1794320308` para `1794320814`, enquanto `01_0001.wav` a `01_0006.wav` e `03.m4a` permaneceram intactos) e remontou `chapters/01.m4a`, gravando `{"kind": "done", "ch": "01", ..., "flagged": []}` no fim de `work/progress.jsonl`.
  - Esperado na tela: após refazer com sucesso (`flagged: []`), o trecho deixa de aparecer marcado como defeituoso.
  - Obtido na tela: `_flagged_from_progress` em `studio/local_api.py` (linhas 246 a 267) soma todas as linhas históricas de `work/progress.jsonl` sem substituir o evento `done` anterior do mesmo capítulo; por isso, a tela continua mostrando "Trecho 1 marcado. Pode refazer só este pedaço." mesmo ao lado de "Trecho refeito." (`tests/ui/capturas/06-pronto-refeito.png`).
- Passo 4 (Salvar M4B, R32 / R38 - REPROVADO por expor caminho interno na tela):
  - Esperado: salvar/baixar o M4B ou confirmar em português simples sem expor caminho interno de máquina.
  - Obtido: `ui/ready.html` (linha 134) exibe `M4B salvo: <caminho absoluto completo no disco>` (`tests/ui/capturas/06-pronto-salvar-m4b.png`), o que na execução normal fora de teste expõe `/Users/.../Library/Application Support/...` diretamente na interface.
- Passo 5 (Mostrar no Finder, R32): Clicar em "Mostrar no Finder" acionou `POST /api/projects/<id>/reveal` (HTTP 200) e exibiu "Pasta aberta no Finder.".
