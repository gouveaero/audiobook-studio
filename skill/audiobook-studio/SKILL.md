---
name: audiobook-studio
description: Use quando o usuário quiser transformar um livro (EPUB) em audiolivro com a PRÓPRIA voz clonada, localmente ou numa GPU na nuvem (Colab). Triggers "audiolivro", "audiobook", "transforma esse ebook em áudio", "gera o áudio do livro com a minha voz", "clonar voz para ler um livro", "epub para m4b". Cobre EPUB limpo por capítulos, voz de referência, geração com cache e checagem, montagem em M4B com capítulos e capa, vídeo e painel ao vivo.
---

# Audiobook Studio

Livro (EPUB) + 10 a 20 s da voz do usuário = audiolivro com capítulos, capa e metadados. Motor: OmniVoice (k2-fsa), local ou numa GPU do Colab.
O código está no repositório (`studio/`); esta skill é o roteiro de quem opera.

## Regras antes de começar

1. **Só a voz do próprio usuário, ou de quem autorizou por escrito.** Se for outra voz, pare e pergunte.
2. **Livro: uso pessoal.** Não publique o áudio de um livro com direitos autorais sem licença; diga isso ao usuário se ele falar em publicar/vender.
3. **Nuvem gasta dinheiro/unidades.** Mostre a estimativa (abaixo) e peça OK antes de subir uma GPU. Nunca deixe a VM ligada sem uso.
4. **Não publique nada** (GitHub, Drive, redes) sem pedir.

## Passo a passo

```
python -m studio book  livro.epub projects/<nome>/book.json     # capítulos limpos, números por extenso
python -m studio voice gravacao.m4a --project projects/<nome>    # recorta ≤15 s, transcreve, CONFIRA ref.txt
python -m studio generate --project projects/<nome>              # local (auto: cuda > mps > cpu), retomável
python -m studio cloud run --project projects/<nome> --gpu A100  # ou na nuvem
python -m studio assemble --project projects/<nome>              # capítulos .m4a, .m4b com capítulos, .mp4
python -m studio publish --project projects/<nome>               # envia M4B, vídeo e capa ao Google Drive e confere
python -m studio ui --project projects/<nome>                    # assistente e painel em http://localhost:8791
```

**Entrega no Drive é parte do trabalho.** Ao terminar, rode `publish` (rclone). O destino vem de `AUDIOBOOK_DRIVE_DEST` ou de
`config.local.json` na raiz do repositório (`{"drive_dest": "remote:Pasta/Audiolivros"}`); cria uma pasta com o título do livro e
confere o tamanho de cada arquivo depois do envio. Entregue o link ao usuário. Capítulos soltos só com `--with-chapters`.

Layout de projeto: `book.json`, `cover.jpg`, `voice/{ref.wav,ref.txt,peaks.json}`, `work/` (cache e progresso), `chapters/NN.m4a`, `audiobook/`.

## Decisões que valem confirmar com o usuário

- **Onde gerar.** Estimativa de tempo = horas de áudio ÷ velocidade. Referências medidas: A100 ~12× a fala com 3 processos (livro de 26 h em ~2 h 15 min); Mac (Apple GPU) ~0,7 a 1,2× (com pouca RAM livre cai muito: feche o Chrome); CPU: inviável para livro inteiro. Custo de referência: A100 ~6,7 unidades/h.
- **O que não ler.** Padrão: notas, bibliografia, índice, créditos, agradecimentos. Ajuste com `--skip-title` ou `--skip-files`.
- **Idioma.** Há normalização de números/datas/romanos só para português (`studio/normalize_pt.py`). Outros idiomas: crie `normalize_<lang>.py` com `normalize(texto)`; sem ele o modelo lê números sozinho, com mais erros.

## Voz de referência (o que mais pesa na qualidade)

- De 8 a 15 s, fala contínua, sem ruído nem música, tom parecido com o do livro (livro de história pede voz expositiva, não de conversa).
- A transcrição tem de ser **exata**; o Whisper erra palavras. Leia `voice/ref.txt` e corrija.
- Acima de 20 s o motor recusa. Mais longo não melhora e deixa cada chamada mais lenta.
- Com mais de uma referência, gere o **mesmo parágrafo** com cada uma e deixe o usuário ouvir antes de rodar o livro: trocar a voz no meio obriga a refazer tudo.

## Armadilhas já pagas (não repita)

- **Arquivo parcial.** Baixar da VM um `.m4a` enquanto ele ainda está sendo codificado gera arquivo sem `moov atom`. O gerador só renomeia para `NN.m4a` quando completo; o `cloud` confere cada download com `ffprobe`. **Verifique todos os arquivos antes de encerrar a VM**: ela perde tudo ao parar.
- **Prefira todos os trechos em cache.** `work/chunks/NN_KKKK.wav` é a unidade de retomada; apagar um arquivo refaz só aquele trecho.
- **Mais de um processo na mesma GPU** (3 em CUDA) quase dobra o ritmo, pois um processo só usa ~60% da A100.
- **`colab exec` pode pendurar sem erro** e corta em 30 s por padrão: use `--timeout` e comandos curtos; processos longos vão em `nohup` na VM.
- **Pacote do PyPI** `omnivoice` é a versão oficial do k2-fsa (Apache-2.0); versões diferentes do app VoiceStudio têm API parecida, mas devolvem numpy em vez de tensor (o código já trata).
- **Checagem de ritmo.** Trecho com caracteres/segundo fora de 10 a 17 é regenerado com outra semente; os que esgotam as tentativas aparecem em `work/progress.jsonl` com `flagged`. Ouça esses.
- **Texto do livro.** Números por extenso exigem cuidado com gênero ("duas mil", "uma") e siglas ("MI6"); amostre 3 capítulos de áudio antes de confiar.

## Antes de dizer que terminou

1. `ffprobe` em todos os `chapters/*.m4a` sem erro.
2. Durações batem com o texto (~13 caracteres/s); capítulos fora disso, ouça.
3. Ouça o começo de 2 capítulos (títulos e datas).
4. VM encerrada (`colab --auth adc usage` mostra 0 sessões).
5. Diga ao usuário o que NÃO foi verificado (voz ao longo do livro inteiro, erros de pronúncia de nomes próprios).
