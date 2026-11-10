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

Resultado: reprovado na 2ª rodada (apenas 1 item restante em `home.html`).
- Histórico (1ª rodada): reprovado por inglês/flags no `#log` de `dashboard.html`, `(RuntimeError)` e `work/generate.log` em `#dashErr`, `"voz de voz · pocket"` em `#tSub` e caminho absoluto em `ready.html`.
- 2ª rodada:
  - Correções confirmadas: zero travessões (`—` ou `–`) em todos os arquivos de `ui/` (incluindo `about.html`); `#log` de `dashboard.html` agora 100% em português (`"geração local pronta para começar"`, `"ritmo local 0,0×"`, `"gerando capítulo 01: ..."`, `tests/ui/capturas/08-texto-dashboard-log.png`); `#tSub` limpo (`"Autora Sintética · voz de Teste"`); `#dashErr` sanitizado por `_erro_publico`; `home.html` sem slug `p.id` nos cartões; `ready.html` sem caminho absoluto; `about.html` (`"Sobre"`, `tests/ui/capturas/08-texto-sobre.png`) em português e com botão `"Início"` funcional.
  - Passo 1 (`home.html` - REPROVADO por botões visíveis sem ação / R48):
    - Esperado: quando `DONATION_URL` e `ANDROID_WAITLIST_URL` estão vazios em `studio/brand.py`, os botões `"Doar"` (`#doar`) e `"Lista de espera Android"` (`#android`) não devem aparecer na tela (R48), e nenhum botão visível pode ficar sem ação.
    - Obtido: em `ui/home.html` (linha 17), a regra CSS `button, label.btn, a.btn { ... display: inline-block; }` sobrescreve o estilo padrão do navegador para o atributo HTML `hidden` (`[hidden] { display: none }`). Mesmo com `doar.hidden = true` e `android.hidden = true` e sem atributo `href` (`href = null`), ambos os botões `"Doar"` (`74x43 px`) e `"Lista de espera Android"` (`212x43 px`) aparecem visíveis na tela inicial e clicar neles não faz nada (`tests/ui/capturas/08-texto-home-botoes.png` e `tests/ui/capturas/01-primeiro-uso-home.png`). Basta adicionar `[hidden] { display: none !important; }` no CSS de `ui/home.html`.
