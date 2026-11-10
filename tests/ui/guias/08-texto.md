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
6. Inspecionar `about.html` ("Sobre") e o quadro de primeiro uso em `home.html` -> esperado: termos de uso, privacidade e licenças em português, sem travessão, e botões funcionando.

Capturas:
- Passo 1 (`home.html`): `tests/ui/capturas/08-texto-home-botoes.png`
- Passo 4 (`dashboard.html`): `tests/ui/capturas/08-texto-dashboard-log.png`
- Passo 6 (`about.html`): `tests/ui/capturas/08-texto-sobre.png`

Critério de aprovação:
- Nenhum caractere de travessão (`\u2014` ou `\u2013`) em `ui/`.
- Nenhuma mensagem ou painel visível em inglês ou com flags de linha de comando/nomes técnicos (R38, R39).
- Nenhum texto cortado indevidamente nem botão sem ação (R39, R48).

Resultado: aprovado na 3ª rodada.
- Histórico (1ª rodada): reprovado por inglês/flags no `#log` de `dashboard.html`, `(RuntimeError)` e `work/generate.log` em `#dashErr`, `"voz de voz · pocket"` em `#tSub` e caminho absoluto em `ready.html`.
- Histórico (2ª rodada): reprovadas apenas as âncoras `#doar` (`"Doar"`) e `#android` (`"Lista de espera Android"`) em `home.html`, que apareciam visíveis sem `href` porque `a.btn { display: inline-block }` vencia `[hidden]`.
- 3ª rodada (todas as telas conferidas: `home.html`, primeiro uso, `review.html`, `voice.html`, `dashboard.html`, `ready.html` e `about.html`):
  - Com `[hidden] { display: none !important; }` em `ui/fonts.css` e `DONATION_URL` / `ANDROID_WAITLIST_URL` vazios em `studio/brand.py`, `"Doar"` e `"Lista de espera Android"` ficam ocultos (`display: "none"`, `width: 0`) (`tests/ui/capturas/08-texto-home-botoes.png`).
  - Zero elementos `[hidden]` vazando na tela (`hiddenLeaks: []`) em todas as 7 telas/estados.
  - Zero travessões (`—` ou `–`), zero textos em inglês ou nomes técnicos de exceção/caminho de log, zero texto cortado e todos os botões visíveis possuem ação funcional (`tests/ui/capturas/08-texto-dashboard-log.png`, `tests/ui/capturas/08-texto-sobre.png`).
