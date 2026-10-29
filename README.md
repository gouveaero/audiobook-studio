# Audiobook Studio

Transforme um livro (EPUB) em audiolivro com a sua própria voz. Roda 100% no seu computador ou numa GPU na nuvem (Google Colab), com o modelo aberto [OmniVoice](https://github.com/k2-fsa/OmniVoice) (k2-fsa, Apache-2.0).

Você entrega um EPUB e de 10 a 20 segundos da sua voz. Sai um audiolivro com capítulos marcados, capa e metadados (M4B), um arquivo por capítulo e, se quiser, um vídeo com a capa de fundo.

## Como funciona

```
EPUB ──► capítulos limpos ──┐
                            ├──► geração por trecho ──► capítulos .m4a ──► M4B + vídeo
voz (10 a 20 s) ──► clone ──┘     (local ou GPU na nuvem)
```

- **Texto:** o sumário do EPUB vira os capítulos. Notas de rodapé, bibliografia e índice ficam de fora. Em português, números, datas, horas e algarismos romanos são escritos por extenso ("século XIII" vira "século treze").
- **Voz:** o trecho de referência é recortado no fim de uma frase e transcrito com Whisper local. Você confere a transcrição.
- **Geração:** cada parágrafo (até 900 caracteres) é um trecho. Tudo fica em cache e é retomável. Cada trecho tem o ritmo conferido e é refeito se sair cortado ou repetido.
- **Montagem:** M4B com capítulos e capa, um M4A por capítulo com metadados, e um MP4 com a capa ampliada sobre fundo desfocado.

## Instalação

Requisitos: Python 3.11 ou mais novo, `ffmpeg` e `ffprobe` no PATH.

```sh
git clone <este repositório> && cd audiobook-studio
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # instale o torch certo para o seu hardware
```

Para a nuvem (opcional): `uv tool install google-colab-cli` e faça o login do Google (`gcloud auth application-default login` com o escopo do Colab). Precisa de um plano do Colab com unidades de computação.

## Uso

**Pela interface** (recomendado):

```sh
python -m studio ui --project projects/meu-livro
# abre http://localhost:8791  →  1. livro  2. voz (grave ou envie)  3. onde gerar
```

O painel ao vivo fica em `/dashboard.html` (troque o tema com as teclas 1, 2 e 3; `?demo=1` simula o progresso).

**Pela linha de comando:**

```sh
python -m studio book   livro.epub projects/meu-livro/book.json
python -m studio voice  gravacao.m4a --project projects/meu-livro      # confira voice/ref.txt
python -m studio generate --project projects/meu-livro                 # neste computador
python -m studio cloud run --project projects/meu-livro --gpu A100     # ou na nuvem
python -m studio assemble --project projects/meu-livro                 # M4B, capítulos e vídeo
```

**Pelo Claude Code:** copie `skill/audiobook-studio` para `~/.claude/skills/` e peça: "faz o audiolivro de livro.epub com a minha voz em voz.m4a". A skill traz o roteiro, as decisões que vale confirmar e as armadilhas.

## Velocidade e custo (medidos)

| Onde | Velocidade | Livro de 26 h de áudio |
|---|---|---|
| A100 no Colab, 3 processos | ~12× a fala | ~2 h 15 min, ~15 unidades de computação |
| Mac com GPU Apple | ~0,7 a 1,2× | ~25 a 35 h |
| CPU | muito abaixo do tempo real | inviável para um livro inteiro |

## Qualidade: o que mais pesa

- A **voz de referência**: de 8 a 15 s, sem ruído, no tom do livro. A transcrição precisa ser exata.
- Gere o mesmo parágrafo com mais de uma referência e ouça antes de rodar o livro inteiro.
- Nomes próprios e siglas podem sair com pronúncia errada; amostre alguns capítulos.

## Limites e uso responsável

- Use **apenas a sua voz**, ou a de quem autorizou por escrito. Avise que a narração é gerada por IA.
- O áudio de um livro com direitos autorais é para uso pessoal, salvo licença.
- O Colab tem regras de uso; mantenha o uso pessoal e moderado.
- A normalização de números existe só em português por enquanto. Para outro idioma, crie `studio/normalize_<idioma>.py` com uma função `normalize(texto)`.

## Estrutura

```
studio/    prepare_book, prepare_voice, generate, cloud, assemble, server, normalize_pt
ui/        setup.html (assistente), dashboard.html (painel ao vivo)
skill/     audiobook-studio/SKILL.md (skill do Claude Code)
projects/  seus projetos (ignorado pelo Git: livros e vozes não vão para o repositório)
```

## Créditos

Modelo: [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice) (Apache-2.0). Transcrição: faster-whisper. Números por extenso: num2words.
