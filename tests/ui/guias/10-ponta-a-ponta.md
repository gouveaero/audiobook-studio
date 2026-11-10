# Guia 10: Percurso de ponta a ponta com o Pocket real

Objetivo: Percorrer todo o fluxo do aplicativo no navegador com o motor Pocket TTS real (`portuguese_24l`), sem motor falso nem download simulado, desde o primeiro uso com download real do modelo até a geração, reprodução e exportação do arquivo M4B (R1, R9, R10, R11, R14, R22, R26 a R32, R36).

Preparação:
- Servidor iniciado em pasta temporária vazia (`AUDIOBOOK_STUDIO_HOME`) e com `VOICE_PACK_DIR` apontando para o pacote da voz padrão (`portuguese_24l`), sem variáveis `FAKE_ENGINE_DELAY`, `AUDIOBOOK_PREVIEW_MOTOR` ou `AUDIOBOOK_FAKE_DOWNLOAD`.
- EPUB sintético curto gerado com `tests/epub_sintetico.py` (`curto-e2e.epub`, título `"História Curta"`, autora `"Autora Sintética"`, capa e 2 capítulos de 2 parágrafos: `"1. A Chegada"` e `"2. A Partida"`).

Passos:
1. Abrir a tela inicial (`home.html`) sem modelo baixado -> esperado: exibe o quadro `"Primeiro uso: baixar o modelo de voz"` com tamanho estimado (~700 MB), botão `"Baixar modelo"` visível e botão `"Novo audiolivro"` desabilitado (`tests/ui/capturas/10-primeiro-uso.png`).
2. Clicar em `"Baixar modelo"` -> esperado: baixa o modelo real (`portuguese_24l`) exibindo tamanho e progresso na tela em MB e percentual (`tests/ui/capturas/10-baixando-modelo.png`), oculta o quadro ao concluir (100%) e habilita `"Novo audiolivro"`.
3. Enviar o EPUB sintético curto pelo botão `"Novo audiolivro"` -> esperado: redireciona para `review.html?id=historia-curta` exibindo capa, título `"História Curta"`, autora `"Autora Sintética"` e os 2 capítulos marcados para inclusão (`tests/ui/capturas/10-conferencia.png`).
4. Clicar em `"Continuar para a voz"` -> esperado: abre `voice.html?id=historia-curta` com a voz padrão do pacote já selecionada no topo (`tests/ui/capturas/10-voz.png`).
5. Clicar em `"Continuar"` na tela de voz -> esperado: redireciona para `dashboard.html?id=historia-curta`, inicia a geração real com o Pocket TTS, atualiza o percentual, a velocidade e o tempo restante (`restam ~28 s` -> `~13 s` -> `~8 s` -> `~4 s`) (`tests/ui/capturas/10-gerando.png`) e redireciona automaticamente para `ready.html?id=historia-curta` ao concluir.
6. Na tela final (`ready.html`), tocar o capítulo 1 (`"1. A Chegada"`), avançar (`currentTime`) para o meio do capítulo e clicar em `"Salvar M4B"` -> esperado: o áudio toca e posiciona no meio sem erro (`00:14` de `00:29`), e `"Salvar M4B"` grava o audiolivro e exibe `"M4B salvo: História Curta.m4b na pasta Downloads."` sem expor caminho completo de máquina (`tests/ui/capturas/10-pronto.png`, `tests/ui/capturas/10-salvar-m4b.png`).
7. Conferir o arquivo `História Curta.m4b` com `ffprobe` e os registros em `work/generate.log` e `work/job.json` -> esperado: M4B com duração maior que zero, 2 capítulos nomeados, capa embutida (`attached_pic: 1`), metadado de narração por IA em `comment` e confirmação de uso do motor `pocket` (`portuguese_24l`).

Capturas:
- Passo 1: `tests/ui/capturas/10-primeiro-uso.png`
- Passo 2: `tests/ui/capturas/10-baixando-modelo.png`
- Passo 3: `tests/ui/capturas/10-conferencia.png`
- Passo 4: `tests/ui/capturas/10-voz.png`
- Passo 5: `tests/ui/capturas/10-gerando.png`
- Passo 6: `tests/ui/capturas/10-pronto.png` e `tests/ui/capturas/10-salvar-m4b.png`

Critério de aprovação:
- Percurso completo realizado pela interface no navegador, sem uso de linha de comando para ações do fluxo.
- Modelo real baixado na tela de primeiro uso com progresso em MB e percentual (R36).
- Geração concluída com o motor real `pocket` (`portuguese_24l`) sem erros nem avisos de palavras puladas (`generation may skip words`).
- M4B final válido no `ffprobe` com capítulos, capa (`attached_pic`), duração > 0 e metadado de narração por IA (R26 a R29).
- Nenhuma tela com texto em inglês, travessão, texto cortado, traceback ou caminho técnico (R38, R39).

Resultado: aprovado.
- Passo 1 e 2 (Primeiro uso e download real, R36): tela inicial exibiu `"Primeiro uso: baixar o modelo de voz"` com `"Novo audiolivro"` desabilitado (`tests/ui/capturas/10-primeiro-uso.png`). Ao clicar em `"Baixar modelo"`, o download real progrediu na interface (`64 MB de 665 MB (10%)` -> `256 MB de 665 MB (38%)` -> `665 MB de 665 MB (100%)`) (`tests/ui/capturas/10-baixando-modelo.png`), ocultou o bloco `#modelo` ao terminar e habilitou `"Novo audiolivro"`.
- Passo 3 (Conferência, R1 / R9): o envio de `curto-e2e.epub` abriu `review.html?id=historia-curta` com capa, título `"História Curta"`, autora `"Autora Sintética"` e os capítulos `"1. A Chegada"` (391 caracteres) e `"2. A Partida"` (409 caracteres) marcados (`tests/ui/capturas/10-conferencia.png`).
- Passo 4 (Voz padrão, R22): `voice.html?id=historia-curta` abriu com a voz padrão do pacote (`id: "padrao"`, `"Voz padrão · já neste computador"`) pré-selecionada no topo (`tests/ui/capturas/10-voz.png`).
- Passo 5 (Geração real no painel, R10 / R11 / R14): `dashboard.html?id=historia-curta` iniciou o motor `pocket` (`portuguese_24l`) para os 804 caracteres totais, exibindo o tempo restante mudando ao longo da síntese (`restam ~28 s` -> `restam ~13 s` -> `restam ~8 s` -> `restam ~4 s`, velocidade ~50,8 chars/s, 2,2x) (`tests/ui/capturas/10-gerando.png`) e redirecionou sozinho para `ready.html?id=historia-curta`.
- Passo 6 (Tela final, reprodução e Salvar M4B, R30 / R32): em `ready.html` (`tests/ui/capturas/10-pronto.png`), o capítulo 1 (`29,72 s`) tocou e avançou para o meio (`14,86 s`, exibido como `00:14` de `00:29`, `readyState: 4`, `error: null`). Ao clicar em `"Salvar M4B"`, a tela confirmou `"M4B salvo: História Curta.m4b na pasta Downloads."` (`tests/ui/capturas/10-salvar-m4b.png`).
- Passo 7 (Verificação com `ffprobe` e logs, R26 a R29):
  - `work/job.json` e `config.json`: `"motor": "pocket"`, `"model": "portuguese_24l"`, `"status": "pronto"`, `"chars_done": 804`, `"chars_total": 804`, `"error": null`.
  - `work/generate.log`: `2 faixas`, `M4B: .../História Curta.m4b 0 MB, 0.02 h`, `pronto` (sem ocorrências de `FakeEngine`, `generation may skip words` ou `Traceback`).
  - `ffprobe` em `História Curta.m4b` (467.110 bytes): duração `58.549167` s (`aac` 24000 Hz mono), 2 capítulos (`"1. A Chegada"` de `0.000000` a `29.765000` s; `"2. A Partida"` de `29.765000` a `58.506000` s), capa embutida (`mjpeg` 1400x1400 com `disposition.attached_pic = 1`), e tags `title="História Curta"`, `artist="Autora Sintética"`, `genre="Audiobook"` e `comment="Narração gerada por IA. Narrador: ..."`.
