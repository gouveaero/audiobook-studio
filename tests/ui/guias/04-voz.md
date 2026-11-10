# Guia 04: Escolha de voz, amostra e clonagem

Objetivo: Verificar que a voz padrão ou de reserva já vem selecionada sem login, ouvir uma voz pronta, testar o bloqueio de "Usar a minha voz" sem marcar a declaração de consentimento e conferir o aviso para regravar ao enviar arquivo ruim (R22, R23, R24, R25).

Preparação:
- Servidor iniciado com `AUDIOBOOK_PREVIEW_MOTOR=tests.fake_engine:FakeEngine` e `AUDIOBOOK_STUDIO_HOME` sem login do Hugging Face.
- Projeto sintético aberto em `voice.html?id=<projeto>`.
- Arquivo de áudio sintético ruim `voz-curta-baixa.wav` (1,5 s e amplitude muito baixa).

Passos:
1. Abrir `voice.html?id=<projeto>` -> esperado: a primeira voz da lista já aparece selecionada (`.voz.on`, voz padrão quando `VOICE_PACK_DIR` existe ou a voz pronta de reserva `Rafael` quando sem pacote), sem exigir login (R22). A tela exibe também o aviso de narração por IA e as instruções de aceite dos termos e token do Hugging Face (R24).
2. Clicar no botão "Ouvir" de uma voz pronta -> esperado: o botão muda temporariamente para "Gerando...", a rota `/api/voices/preview` retorna áudio WAV e o reprodutor `<audio id="player">` fica visível com o áudio carregado (R23).
3. Na seção "Usar a minha voz", deixar a caixa "Declaro que esta voz é minha ou que tenho autorização por escrito para usá-la." desmarcada e clicar em "Salvar minha voz" -> esperado: bloqueado com a mensagem "Marque a declaração de que a voz é sua ou que você tem autorização." (R24).
4. Enviar o arquivo `voz-curta-baixa.wav` em "Enviar arquivo", marcar a declaração de consentimento e clicar em "Salvar minha voz" -> esperado: a tela exibe aviso em português recomendando regravar por gravação muito curta e muito baixa (`#avisos` visível com instruções para regravar) (R25).

Capturas:
- Passo 1: `tests/ui/capturas/04-voz-inicial.png`
- Passo 2: `tests/ui/capturas/04-voz-ouvir-pronta.png`
- Passo 3: `tests/ui/capturas/04-voz-sem-declaracao.png`
- Passo 4: `tests/ui/capturas/04-voz-arquivo-ruim.png`

Critério de aprovação:
- Voz inicial já selecionada sem login (R22).
- Amostra de voz pronta toca no reprodutor (R23).
- Salvar voz sem marcar a declaração é bloqueado (R24).
- Áudio curto/baixo exibe aviso claro para regravar (R25).

Resultado: aprovado.
- Passo 1 (R22): `voice.html` abriu com a voz de reserva `Rafael` já selecionada (`.voz.on`) sem login, listando as 27 vozes prontas e o aviso de narração por IA (`tests/ui/capturas/04-voz-inicial.png`).
- Passo 2 (R23): Ao clicar em "Ouvir", a rota `/api/voices/preview` gerou o WAV de amostra e o reprodutor `<audio id="player">` ficou visível com o áudio carregado (`tests/ui/capturas/04-voz-ouvir-pronta.png`).
- Passo 3 (R24): Clicar em "Salvar minha voz" sem marcar a declaração de consentimento bloqueou o envio com a mensagem "Marque a declaração de que a voz é sua ou que você tem autorização." (`tests/ui/capturas/04-voz-sem-declaracao.png`).
- Passo 4 (R25): Enviar `voz-curta-baixa.wav` (1,5 s e volume muito baixo) exibiu em `#avisos`: "A gravação ficou muito curta. Grave de novo, falando por cerca de 10 segundos. A gravação ficou muito baixa. Aproxime o microfone e grave de novo." (`tests/ui/capturas/04-voz-arquivo-ruim.png`).
