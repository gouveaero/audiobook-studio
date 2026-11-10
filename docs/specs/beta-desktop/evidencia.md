# Evidência

Cada linha só entra depois de o teste ter sido rodado pelo Maestro na `beta-desktop`.

## Requisitos

| Requisito | Tarefa | Teste | Resultado |
|---|---|---|---|
| R49 (parcial, repetir na T24) | T1 | `tests/test_privacidade.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 5 passaram; controle negativo com termo extra no `LOCAL_MD` reprovou como esperado |
| R1 a R8 | T10 | `tests/test_prepare_book.py` (EPUBs sintéticos de `tests/epub_sintetico.py`) via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 24 passaram na `beta-desktop` (29 no total da camada). Livros reais ficam para a T11 |
| R2 a R4 (livros reais) | T11 | `tests/test_prepare_book.py` (4 testes novos) e `prepare_book` rodado pelo Maestro nos dois livros de `local.md`, com saída em pasta temporária | 33 passaram na camada base. Livro 1: 32 capítulos, mesmos ids e títulos da lista corrigida à mão; texto difere só em três capítulos (2 a 3%), pelas notas de rodapé que deixaram de ser lidas. Livro 2: 66 capítulos, partes e capítulos nomeados. Não verificado: como o Pocket lê subtítulos em maiúsculas do livro 2 |
| R50 | T4 | `tests/test_engines.py`, `tests/test_generate.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 20 passaram (53 na camada). Não verificado: OmniVoice real, que não está instalado nesta máquina; o teste usa um modelo falso injetado e confere os mesmos argumentos de antes |
| R19 a R21 | T12 | `tests/test_audio.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 11 passaram (64 na camada): LUFS e pico por capítulo, silêncios da virada medidos no M4B e em qualquer ordem de geração, título 2,5 dB (±0,5) acima do corpo, remontagem sem gerar voz, EQ ligado e desligado. Não verificado: os mesmos números em áudio do Pocket real |

## Decisões de quem constrói

- **T1, R49:** o termo `hf_` do `local.md` é lido como token do Hugging Face (`hf_` seguido de 20 ou mais letras e números), para não proibir nomes como `hf_hub_download`. Os outros termos são procurados sem diferenciar maiúsculas.
- **T1:** `scripts/verify_beta.sh` aceita `VERIFY_LAYERS` (`base`, `model`, `package`; padrão: as três). Camada sem nenhum teste conta como falha.
- **T1:** o teste de R49 confere autor e committer, e também barra extensões de voz, livro e áudio nos arquivos versionados e nos commits novos.
- **T4:** `config.json` aceita o rótulo antigo "OmniVoice"; motor desconhecido dá erro em português. Os pedaços `NN_KKKK.pSS.wav` são apagados quando viram `NN_KKKK.wav`. Pausa de 0,25 s entre pedaços do mesmo trecho. Trechos gravados em 16 bits; o cache antigo em float32 continua lido.
- **T12:** a decisão do EQ é lida de `voice/manifest.json` dentro do projeto e, na falta dele, de `config.json` (`"eq": true`); sem o campo, EQ desligado. O silêncio antes do título é calculado só pelo `book.json`. `studio/audio.py` traz `eq_por_graves` para a regra dos 60% abaixo de 350 Hz, que a T17 chama.

## Execuções

## Execução do verify_beta.sh

- Data: 2026-11-10 13:41
- Commit: 198a6c2 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 5 passed in 0.46s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 13:47
- Commit: d35e3b0 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 29 passed in 3.00s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 13:50
- Commit: dd9034f (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 33 passed in 6.70s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 13:51
- Commit: 4d2a5d0 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 53 passed in 29.06s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 13:57
- Commit: b96ab7c (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 64 passed in 12.60s
- Resultado: passou
