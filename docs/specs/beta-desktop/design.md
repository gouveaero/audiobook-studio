# Design do beta para computador

Complementa `requirements.md`. Os detalhes que não aparecem aqui ficam a critério de quem constrói, desde que os testes passem.

## Regras gerais

- Python 3.12 com `uv`, ambiente em `.venv/` (já ignorado pelo git). Dependências do app em `requirements-app.txt`, com `pocket-tts==4.0.1` fixado.
- Siga o estilo do código atual: `studio/` em Python simples, sem framework web, `ThreadingHTTPServer` e `ui/` em HTML, CSS e JS puros.
- Toda a interface em português do Brasil. Texto visível nunca usa travessão.
- Nome provisório do app: "Audiobook Studio". Ele fica em uma única constante, `studio/brand.py`, porque vai mudar.
- Nada de telemetria. O app só acessa a internet para baixar modelos, consultar a versão nova e fazer o login opcional do Hugging Face.
- O repositório é público. Nunca coloque nele áudio de voz, arquivos `.safetensors`, livros, tokens, nomes de pessoas ou caminhos de máquina. Dados locais ficam em `local.md`, ignorado pelo git.

## Pastas do app

`~/Library/Application Support/Audiobook Studio/` (`AUDIOBOOK_STUDIO_HOME` substitui o caminho nos testes):

```
settings.json
hf/                     HF_HOME do app (token com permissão 0600)
voices/<id>/manifest.json, voz_<modelo>.safetensors, ref.wav (só em voz clonada)
projects/<slug>/        mesmo formato de projeto atual, mais work/job.json
```

## Motores

`studio/engines/__init__.py` define a interface; `pocket.py` e `omnivoice.py` a implementam:

```python
class Engine:
    id: str; sample_rate: int
    chars_per_second: float        # usado no painel e nas estimativas
    rate_range: tuple[float, float]  # faixa aceitável de caracteres por segundo
    def load(self, voice) -> None: ...
    def split(self, text: str) -> list[str]: ...   # trechos dentro do limite do motor
    def synth(self, text: str, attempt: int) -> "np.ndarray": ...  # mono float32
```

- `generate.py` escolhe o motor por `config.json` (`"motor"`), com padrão `omnivoice` quando o campo não existe, para não mudar os projetos antigos e a nuvem.
- Importe `torch` e os motores só dentro das funções, porque testes sem modelo não podem precisar deles.
- `tests/fake_engine.py` gera áudio sintético com duração proporcional ao texto.

### Pocket

- API: `TTSModel.load_model(language=...)`, `get_state_for_audio_prompt(voz)`, `generate_audio(estado, texto, max_tokens=50)`, `sample_rate`.
- O Pocket avisa "Chunk has N tokens (max 50), generation may skip words" quando uma frase não tem onde ser cortada. O pré-corte em `split` usa o tokenizador do próprio modelo (ver `pocket_tts/models/text_chunking.py`, `split_into_best_sentences`):
  1. fim de frase;
  2. `,`, `;`, `:`;
  3. fronteira de palavra, como último recurso.
- Alvo de até 40 tokens por pedaço, com pausas curtas entre as partes de uma mesma frase. Nenhum aviso desse tipo pode aparecer na geração.
- **Trecho e pedaço:** o `book.json` guarda trechos de até 900 caracteres, como hoje. O Pocket os divide em pedaços na hora de gerar. O pedaço é a unidade de ritmo, nova tentativa e cache (`work/chunks/NN_KKKK.pSS.wav`). Com todos prontos, eles viram `NN_KKKK.wav`, que é o que o painel e a retomada já conhecem. "Refazer" sempre refaz o trecho inteiro.
- Ritmo medido em capítulo inteiro: cerca de 16,6 caracteres por segundo. Calibre `rate_range` nos dados, com trechos curtos, porque a faixa larga de 10 a 22 não detectou as perdas.

## Formato do livro

`book.json` continua igual, com estes acréscimos:

```json
{"id": "03", "title": "Parte I, capítulo 1", "include": true,
 "chunks": ["Capítulo um.", "..."], "pauses": [1.0, 0.7], "head": [0]}
```

`head` lista os índices de título. Projetos antigos sem `head` continuam funcionando, sem tratamento de título.

## Geração e tarefa

- `studio.generate` roda como processo separado e sobrevive ao fechamento da janela.
- `work/job.json` guarda PID, estado, motor, modelo e início. A interface deduz o estado desse arquivo, sem depender de `JOBS` na memória.
- Pausar e cancelar usam arquivos `work/pause` e `work/cancel`, lidos entre trechos.
- `caffeinate -i -w <pid>` impede o Mac de dormir, só durante a geração.
- Antes de gerar, conferir o espaço: 250 MB por hora de áudio prevista, mais 500 MB de folga. Os WAV de trecho são de 16 bits e ficam guardados, porque "refazer" e o tratamento de áudio dependem deles.
- Trecho: escrever em `.tmp` e renomear. Na retomada, descartar `.wav` ilegível.
- Travas: gravar o PID na trava e liberar apenas a de processo morto. Trava vazia continua valendo, porque `studio/cloud.py` reserva capítulos assim.

## Áudio

Ao juntar os trechos de um capítulo, sem gerar voz de novo:

- **Virada de capítulo, definida pelo dono:** 1,5 s de silêncio no total antes do título, somando o fim do capítulo anterior, e 1 s depois. O título recebe `atempo=0.92,volume=2.5dB`, aplicado antes do EQ e do volume do capítulo. Valores em constantes.
- **Tratamento aprovado pelo dono da voz padrão:**
  `highpass=f=80,equalizer=f=220:width_type=o:w=1.2:g=-2.5,equalizer=f=3500:width_type=o:w=1.5:g=2`.
- **Volume:** medir com `ebur128` e aplicar ganho fixo até -21 LUFS, seguido de `alimiter=limit=0.7:level=false:attack=5:release=80`. Sem compressor, porque ele soou estourado no teste.
- O volume vale para todas as vozes. O EQ vale para a voz padrão e para voz clonada cuja gravação tenha mais de 60% da energia abaixo de 350 Hz; o `manifest.json` guarda essa decisão (`"eq": true`).

Depois de gerar, `assemble.py` monta o M4B com capítulos e capa. O vídeo só sai se a pessoa pedir.

## Servidor local

- Só `127.0.0.1`. `app.py` gera um token aleatório por sessão e abre a janela com ele; todo POST, PUT e DELETE exige o cabeçalho `X-Studio-Token`, e todo pedido, inclusive GET, exige `Host` igual a `127.0.0.1:<porta>`. Sem isso, responder 403.
- Arquivos de áudio atendem `Range` (206), porque o WebKit precisa disso para avançar.
- O modo atual `--project` e os comandos da skill continuam funcionando.
- `app.py` precisa aceitar abrir sem `--project`.

Rotas mínimas:

```
GET  /api/projects                       POST /api/projects (corpo: EPUB)
GET  /api/projects/<id>/book             PUT  /api/projects/<id>/book
GET  /api/projects/<id>/state            POST /api/projects/<id>/{start,pause,resume,cancel,assemble}
POST /api/projects/<id>/redo             {"chapter": "03", "chunk": 12}
POST /api/projects/<id>/reveal           mostra o M4B no Finder
GET  /api/voices                         POST /api/voices (corpo: áudio + consentimento)
GET  /api/models                         POST /api/models/download
POST /api/hf-login                       token do Hugging Face, nunca registrado em log
GET  /api/version
```

## Telas

1. **Início:** livros e botão "Novo audiolivro".
2. **Conferência:** capítulos com incluir ou tirar, renomear, início do texto e tempo estimado.
3. **Voz:** voz padrão selecionada, vozes prontas, "Usar a minha voz".
4. **Geração:** o painel atual em `ui/dashboard.html`, mantendo o visual, com pausar, cancelar e tempo restante.
5. **Pronto:** player por capítulo, trechos marcados, refazer trecho, salvar M4B e mostrar no Finder.

O microfone precisa de `NSMicrophoneUsageDescription` no app empacotado. Fontes dentro do pacote, sem Google Fonts. A dica do Claude Code sai da tela.

## Voz padrão

- O pacote da voz fica fora do git, em `build/voice-pack/`, e entra só no instalador. `scripts/build_voice_pack.py` o monta a partir da origem em `local.md`.
- `manifest.json`: `{"id": "padrao", "label": "...", "engine": "pocket", "model": "portuguese_24l", "file": "voz_portuguese_24l.safetensors", "eq": true}`. A voz clonada usa o mesmo formato.
- Sem o pacote, o app usa a voz pronta `rafael`, configurada em `studio/brand.py`, que a pessoa pode trocar. É uma escolha técnica provisória, ainda sem aprovação pelo ouvido; as 27 vozes do catálogo carregaram em português.
- O rótulo vem do manifesto. Mostrar sempre o aviso de que a narração é gerada por IA.

## Instalador

- PyInstaller em modo pasta, gerando `.app` em `.dmg` só para chip Apple, com `torch` de CPU e `ffmpeg`/`ffprobe` embutidos. Registre em `THIRD_PARTY.md` a origem e a licença do `ffmpeg`.
- Assinatura ad hoc (`codesign -s -`), porque o chip Apple exige alguma assinatura. Sem conta de desenvolvedor Apple por enquanto; o README explica como liberar a abertura.
- O modelo não vai no instalador.
- `scripts/build_mac.sh` constrói tudo do zero.
