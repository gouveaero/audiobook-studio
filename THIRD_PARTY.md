# Softwares de terceiros

Licenças apuradas a partir dos metadados dos pacotes instalados no `.venv` deste repositório (e, quando indicado, de outro ambiente local com o pacote). O código próprio do Audiobook Studio está em `LICENSE` (MIT).

## pocket-tts (Kyutai)

- **Uso:** motor de voz do app (Pocket TTS).
- **Pacote instalado:** `pocket-tts` 4.0.1 (`.venv`).
- **Licença do código:** MIT (arquivo `LICENSE` em `pocket_tts-4.0.1.dist-info/licenses/`).
- **Origem:** https://github.com/kyutai-labs/pocket-tts e PyPI `pocket-tts`.

## Modelo Pocket (pesos sem clonagem)

- **Uso:** baixado no primeiro uso para `AUDIOBOOK_STUDIO_HOME/hf/` (não vai no instalador).
- **Repositório:** `kyutai/pocket-tts-without-voice-cloning` no Hugging Face.
- **Licença no model card:** `cc-by-4.0` (tag `license:cc-by-4.0` no Hub, conferida via `huggingface_hub.model_info`).

## torch

- **Uso:** inferência do Pocket.
- **Pacote instalado:** `torch` 2.15.0 (`.venv`).
- **Licença (License-Expression nos metadados):** Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib.
- **Origem:** https://pytorch.org / https://github.com/pytorch/pytorch

## pywebview

- **Uso:** janela nativa do app.
- **Pacote instalado:** `pywebview` 6.2.1 (`.venv`).
- **Licença:** BSD 3-Clause (campo License e arquivo `LICENSE` do pacote).
- **Origem:** https://github.com/r0x0r/pywebview

## num2words

- **Uso:** números por extenso em português (`studio/normalize_pt.py`).
- **Pacote instalado:** `num2words` 0.5.14 (`.venv`).
- **Licença:** LGPL (campo License e classificador OSI LGPL; arquivo `COPYING` no pacote).
- **Origem:** https://github.com/savoirfairelinux/num2words

## huggingface_hub

- **Uso:** download dos pesos e embeddings do Pocket.
- **Pacote instalado:** `huggingface_hub` 2.4.0 (`.venv`).
- **Licença:** Apache-2.0 (metadados do pacote).
- **Origem:** https://github.com/huggingface/huggingface_hub

## ffmpeg / ffprobe (binário embutido no instalador)

- **Uso:** preparar voz, montar M4A/M4B e, se pedido, vídeo. No app empacotado os binários embutidos têm prioridade sobre o PATH (`studio/paths.py`).
- **Origem do binário arm64 macOS (T20):** release `autobuild-2026-08-30` de https://github.com/livefantasia/ffmpeg-macos-build — arquivo `ffmpeg-8.1.2-aarch64-apple-darwin-lgpl.zip`.
- **Versão:** FFmpeg 8.1.2.
- **Licença:** **LGPL-2.1-or-later** (build sem `--enable-gpl`, sem `--enable-nonfree`, sem `--enable-version3`). Preferido em relação a builds GPL (B10).
- **O que cobre no app:** AAC (AudioToolbox), concat, filtros de áudio, ebur128, capa (lavfi/drawbox) e vídeo opcional via VideoToolbox. Sem libx264/libx265 (software H.264/H.265).
- **Soma de verificação (SHA-256), conferida neste Mac ao rodar `scripts/build_mac.sh`:**
  - zip: `61163696da382f2c5aa7a7babe4abeb1ff7636e364db6a165e93059adfb13cd2`
  - `ffmpeg`: `99a57719e7684a82eef60881c75ec23383ff25a32aa208882b9d5ba6b477fb2e`
  - `ffprobe`: `4249ec335dc30db0331d002058c7c528c770ac86cc24c522f022020b572ce556`
  - Cópia local também em `build/bin/ffmpeg-source.txt` (fora do git).
- **Código-fonte correspondente:** tarball FFmpeg 8.1.2 em https://ffmpeg.org/ e o script de build do repositório acima (oferta LGPL).
- **Conferência nesta máquina (desenvolvimento, não é o embutido):** Homebrew `ffmpeg` 9.0.2 é GPL-3.0-or-later e não vai no instalador.

## Fontes embutidas (ui/fonts/)

- **Oxanium** e **JetBrains Mono** (arquivos `.woff2` em `ui/fonts/`), carregadas por `ui/fonts.css` sem rede.
- **Licença:** SIL Open Font License 1.1 (OFL).
- **Origem:** famílias OFL publicadas no Google Fonts / repositórios oficiais das fontes; só os arquivos locais entram no app.

## OmniVoice (não vai no instalador)

Dois fatos distintos, ambos registrados de propósito (R45):

1. **Model card do projeto k2-fsa/OmniVoice** (https://github.com/k2-fsa/OmniVoice): declara **Apache-2.0**.
2. **Pacote Python instalado** `omnivoice` 0.5.6 (metadados lidos em ambiente local com o pacote; neste worktree o `.venv` da interface **não** instala OmniVoice): declara **AGPL-3.0-only** (`License: AGPL-3.0-only` em `importlib.metadata`).

O OmniVoice **não entra no instalador** do beta para Mac. Continua disponível só no fluxo de linha de comando / nuvem descrito em `docs/linha-de-comando.md`.
