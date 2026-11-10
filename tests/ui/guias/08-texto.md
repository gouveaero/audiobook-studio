# Guia 08: Revisão de texto, idioma, travessão e botões em todas as telas

Objetivo: Percorrer todas as telas da interface (`home.html`, `review.html`, `voice.html`, `dashboard.html`, `ready.html` e `setup.html`) procurando termos em inglês, travessão, texto cortado, nomes técnicos e botões sem ação (R38, R39).

Preparação:
- Servidor em execução na porta 8795 com um projeto sintético e todas as telas acessíveis no portal.

Passos:
1. Inspecionar `home.html` -> esperado: todo o texto visível em português do Brasil, zero travessões, sem texto cortado e botões funcionais.
2. Inspecionar `review.html` -> esperado: todo o texto visível em português do Brasil, zero travessões, sem texto cortado e botões "Início" e "Continuar para a voz" funcionais.
3. Inspecionar `voice.html` -> esperado: todo o texto visível em português do Brasil, zero travessões, sem texto cortado e todos os botões com ação.
4. Inspecionar `dashboard.html` -> esperado: todo o texto visível (incluindo o quadro de registro de eventos `#log`) em português do Brasil, sem jargão ou comandos em inglês (`synth`, `clone_voice --ref ... --chunk ...`), zero travessões e sem texto cortado.
5. Inspecionar `ready.html` -> esperado: todo o texto visível em português do Brasil, zero travessões, sem caminhos técnicos de máquina e botões funcionais.

Capturas:
- Passo 4: `tests/ui/capturas/08-texto-dashboard-log.png`

Critério de aprovação:
- Nenhum caractere de travessão (`\u2014` ou `\u2013`) em `ui/`.
- Nenhuma mensagem ou painel visível em inglês ou com flags de linha de comando/nomes técnicos (R38, R39).
- Nenhum texto cortado indevidamente nem botão sem ação.

Resultado: reprovado.
- Travessão (R39): Aprovado em todos os arquivos de `ui/` (`home.html`, `review.html`, `voice.html`, `dashboard.html`, `ready.html`, `setup.html`, `studio.js`, `fonts.css`): zero ocorrências de `—` (`\u2014`) ou `–` (`\u2013`).
- Passo 1 (`home.html`), Passo 2 (`review.html`) e Passo 3 (`voice.html`): Textos em português do Brasil e botões com ação. (Observação menor em `home.html` linha 59: exibe o slug interno `p.id` ao lado da autora, ex.: `Autora Sintética · cronicas-da-praca`).
- Passo 4 (`dashboard.html` - REPROVADO por inglês e nomes técnicos na tela, R38 e R39):
  1. Termos em inglês e sintaxe de linha de comando no quadro `#log` (`ui/dashboard.html` linhas 228 e 230): imprime `synth cloud ch02 » ...` e `clone_voice --ref voz.wav --chunk 1432` na tela (`tests/ui/capturas/08-texto-dashboard-log.png`).
  2. Nome de exceção e caminho técnico de arquivo de log em `#dashErr` (R38): `studio/generate.py` (linhas 246 e 266) grava `(RuntimeError)` e `work/generate.log` em `work/job.json`, e `studio/local_api.py` (`project_state`, linha 241) devolve `job.get("error")` sem passar por `erro_publico()`, exibindo `A montagem do audiolivro falhou (RuntimeError). O detalhe está em work/generate.log.` em `#dashErr` (visto na captura `tests/ui/capturas/02-resultado-capitulos.png` antes da troca da capa).
  3. Subtítulo `#tSub` (`ui/dashboard.html` linha 121 + `studio/server.py` linha 298): exibe `Autora Sintética · voz de voz · pocket` (repetição `voz de voz` quando `cfg["voz"]` não foi gravado em `config.json` por `attach_voice_to_project`, mais o identificador interno `pocket`).
- Passo 5 (`ready.html` - REPROVADO por caminho técnico na tela, R38):
  - `ui/ready.html` (linha 134) exibe o caminho absoluto completo do arquivo no disco (`M4B salvo: /.../audiobook/...m4b`) ao clicar em "Salvar M4B" (`tests/ui/capturas/06-pronto-salvar-m4b.png`).
