# Guia 02: Novo audiolivro e conferência de capítulos

Objetivo: Enviar um EPUB válido, conferir os capítulos na ordem do sumário, tirar um capítulo, renomear outro e confirmar que essas escolhas valem na geração (R1, R9).

Preparação:
- EPUB sintético `livro-valido.epub` gerado com `tests/epub_sintetico.py`, contendo 3 capítulos no sumário: "1. Manhã na Praça", "2. A Carta Azul" e "3. O Rio no Inverno".
- Servidor em execução na porta 8795 com `AUDIOBOOK_STUDIO_HOME` temporário.

Passos:
1. Abrir `home.html` e enviar `livro-valido.epub` pelo botão "Novo audiolivro" -> esperado: projeto criado e redirecionamento automático para `review.html?id=cronicas-da-praca`.
2. Conferir a lista de capítulos em `review.html` -> esperado: os 3 capítulos aparecem na ordem do sumário, todos marcados com "Incluir", com início do texto e estimativa de tempo.
3. Desmarcar a caixa "Incluir" do capítulo 2 ("2. A Carta Azul") e alterar o título do capítulo 1 para "Capítulo Um: A Praça" -> esperado: capítulo 2 fica esmaecido (`.off`), o resumo superior passa a indicar "2 capítulos incluídos" e o novo título permanece no campo.
4. Clicar em "Continuar para a voz" -> esperado: alterações salvas via `PUT /api/projects/<id>/book` e navegação para `voice.html?id=cronicas-da-praca`.
5. Configurar motor falso (`tests.fake_engine:FakeEngine`) no projeto e clicar em "Continuar" na tela de voz -> esperado: abre `dashboard.html?id=cronicas-da-praca`, gera apenas os capítulos incluídos (`01` e `03`, pulando `02`) e na tela final (`ready.html`) exibe somente os 2 capítulos incluídos, com o primeiro intitulado "Capítulo Um: A Praça".

Capturas:
- Passo 2: `tests/ui/capturas/02-conferencia-inicial.png`
- Passo 3: `tests/ui/capturas/02-conferencia-editada.png`
- Passo 5: `tests/ui/capturas/02-resultado-capitulos.png`

Critério de aprovação:
- Capítulos seguem a ordem do sumário (R1).
- Capítulo desmarcado não é gerado nem aparece na tela final, e o capítulo renomeado aparece com o novo título (R9).

Resultado: aprovado.
- Passo 1 e 2: `livro-valido.epub` enviado em `home.html` abriu `review.html?id=cronicas-da-praca` com os 3 capítulos na ordem do sumário ("1. Manhã na Praça", "2. A Carta Azul" e "3. O Rio no Inverno"), todos marcados com "Incluir", com início do texto e estimativa de tempo (`tests/ui/capturas/02-conferencia-inicial.png`).
- Passo 3 e 4: Ao desmarcar "Incluir" no capítulo 2 e renomear o capítulo 1 para "Capítulo Um: A Praça", o resumo mudou para "2 capítulos incluídos" (`tests/ui/capturas/02-conferencia-editada.png`) e "Continuar para a voz" salvou `book.json` via `PUT /api/projects/cronicas-da-praca/book`.
- Passo 5: Com o motor falso configurado, a geração produziu apenas `chapters/01.m4a` e `chapters/03.m4a` (pulando `02`), montou `Crônicas da Praça.m4b` com apenas os 2 capítulos ("Capítulo Um: A Praça" e "3. O Rio no Inverno") e abriu `ready.html` exibindo esses 2 capítulos (`tests/ui/capturas/02-resultado-capitulos.png`).
