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
| R22 (voz padrão sem login) | T2 | `tests/test_voz_padrao.py` (`@pytest.mark.model`), rodado pelo Maestro com o Pocket real, sozinho na máquina | 2 passaram em 77 s: com `HF_HOME` vazio e sem token, a voz exportada de `portuguese_24l` falou, a voz pronta também, clonar foi recusado com mensagem em português e nenhum token apareceu na saída |
| R27 a R29, R9 e R50 na montagem | T13 | `tests/test_assemble.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 6 passaram (91 na camada): metadados, capa, capítulos e durações por `ffprobe`, capítulo tirado fica fora, renomeado aparece, vídeo só se pedido, projeto antigo monta. Não verificado: a tela final dizer que é IA (T18) e a chamada automática ao fim da geração (T8) |
| R33, R34, R30 (Range) | T14 | `tests/test_servidor_base.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 21 passaram: 403 sem token e com `Host` errado em POST, PUT e DELETE, token fechado por padrão, GET nunca devolve o token, servidor só em 127.0.0.1 (inclusive como processo real), `Range` em todo áudio, log de erro sem token. Não verificado: janela pywebview |
| R13, R9 na geração | T7 | `tests/test_retomada.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 8 passaram (172 na camada): processo morto com SIGKILL no meio retoma só o que faltava, trava velha liberada, trava vazia da nuvem respeitada, `.wav` ilegível refeito, capítulo tirado não é gerado. Não verificado: retomada com o Pocket real |
| R14 a R18 | T8 | `tests/test_tarefa.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 11 passaram: pausar, continuar, cancelar sem apagar o pronto, `caffeinate` só durante a geração, aviso de espaço antes de começar, tempo restante pela velocidade medida, montagem no fim. R15 (fechar e reabrir a janela) fica para o guia 5 do Testador. Não verificado: espaço e `caffeinate` no app empacotado |
| R51 | T9 | `tests/test_cloud.py` com `tests/fake_colab.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 5 passaram: envia `studio/engines/`, o necessário do motor do projeto e mantém as reservas. Não verificado: nuvem real (H5) |
| R45 a R48 | T23 | `tests/test_licencas_sobre.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 8 passaram (180 na camada): LICENSE MIT sem e-mail, THIRD_PARTY com a apuração do OmniVoice (model card Apache 2.0, pacote 0.5.6 declara AGPL-3.0-only), tela Sobre com os termos, README com a liberação de abertura, botões de doação e Android só com endereço configurado. A origem exata do `ffmpeg` embutido fica para a T20 |
| R33 no navegador | T19, guia 7 | `tests/ui/guias/07-seguranca.md`, executado pelo Testador no portal; captura conferida pelo Maestro | aprovado |
| R44 | T22 | `tests/test_atualizacao.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh` | 8 passaram (188 na camada): versão maior avisa, igual não avisa, sem rede e resposta inválida não causam erro; nenhum teste acessa a rede. Não verificado: consulta real às releases |
| Guias de navegação, 1ª rodada | T19 | `tests/ui/guias/01` a `09`, executados pelo Testador no portal, capturas em `tests/ui/capturas/` | Aprovados: 2 (R1, R9), 3 (R5 a R8, R38), 4 (R22 a R25, com voz de reserva e motor falso), 7 (R33), 9 (R35). Reprovados: 1 (falta a tela de download do modelo, R36), 5 (painel mostra nuvem e GPU na geração local; cancelar deixa a tela sem saída), 6 (trecho refeito continua marcado; salvar mostra caminho completo), 8 (inglês e nomes técnicos no painel). Reprovações enviadas à Interface |
| R9, R35, R39 | T16 | `tests/test_telas.py`, `tests/test_hidden_css.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh`; guias 2, 3, 8 e 9 no navegador | 208 passaram na camada; guias aprovados (o 8 na 3ª rodada). Sem travessão, sem endereço externo, fontes embutidas, início abre sem rede |
| R14, R15, R18, R30 a R32 | T18 | `tests/test_painel.py` via `VERIFY_LAYERS=base scripts/verify_beta.sh`; guias 5 e 6 no navegador | testes passaram; guias aprovados na 2ª rodada: pausar, continuar, cancelar, fechar e reabrir, tempo restante, tocar e avançar com `Range`, refazer só o trecho, salvar e mostrar no Finder. Tudo com motor falso; com o Pocket real fica para a T19 de ponta a ponta |
| Guias de navegação, rodadas 2 e 3 | T19 | `tests/ui/guias/01` a `09` | os 9 aprovados. Reprovações da 1ª rodada (guias 1, 5, 6, 8) e da 2ª (guia 8, botões de R48 visíveis) corrigidas pela Interface e conferidas de novo. Falta para a T19: o percurso de ponta a ponta com o Pocket real |

## Decisões de quem constrói

- **T1, R49:** o termo `hf_` do `local.md` é lido como token do Hugging Face (`hf_` seguido de 20 ou mais letras e números), para não proibir nomes como `hf_hub_download`. Os outros termos são procurados sem diferenciar maiúsculas.
- **T1:** `scripts/verify_beta.sh` aceita `VERIFY_LAYERS` (`base`, `model`, `package`; padrão: as três). Camada sem nenhum teste conta como falha.
- **T1:** o teste de R49 confere autor e committer, e também barra extensões de voz, livro e áudio nos arquivos versionados e nos commits novos.
- **T4:** `config.json` aceita o rótulo antigo "OmniVoice"; motor desconhecido dá erro em português. Os pedaços `NN_KKKK.pSS.wav` são apagados quando viram `NN_KKKK.wav`. Pausa de 0,25 s entre pedaços do mesmo trecho. Trechos gravados em 16 bits; o cache antigo em float32 continua lido.
- **T12:** a decisão do EQ é lida de `voice/manifest.json` dentro do projeto e, na falta dele, de `config.json` (`"eq": true`); sem o campo, EQ desligado. O silêncio antes do título é calculado só pelo `book.json`. `studio/audio.py` traz `eq_por_graves` para a regra dos 60% abaixo de 350 Hz, que a T17 chama.
- **T2:** o teste baixa os pesos sem clonagem (672 MB) num `HF_HOME` vazio a cada execução; `HF_HOME_SEM_LOGIN` permite reaproveitar um cache sem token.
- **T13:** entrada da montagem: `studio.assemble.montar_projeto(pasta, video=False)`. A montagem padrão deixou de gerar MP4 (R29); o teste de R7 que esperava o MP4 foi ajustado para esperar que ele não exista. Narrador nos metadados vem de `config.json`.
- **T14:** as páginas leem o token da abertura, guardam em `sessionStorage` e enviam em toda escrita por `ui/studio.js`; log de erros em `logs/server.log` na pasta do app.
- **T8:** estados em `work/job.json`: gerando, pausado, cancelado, montando, pronto, erro e concluido (tarefa que acaba sem o livro inteiro). Pausa e cancelamento lidos entre pedaços.
- **T9:** a geração na VM roda com `--no-assemble`; a montagem continua no computador.
- **T7:** um teste do próprio Motor (`test_capitulo_com_include_false_nao_e_gerado`) foi reescrito na T9 para contar só eventos `done` do `progress.jsonl` e passou a exigir que nenhum evento do capítulo tirado apareça.

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

## Execução do verify_beta.sh

- Data: 2026-11-10 13:59
- Commit: c19beab (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 64 passed, 2 deselected in 20.42s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 14:00
- Commit: 17b944e (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 91 passed, 2 deselected in 21.81s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 14:16
- Commit: e848d80 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 103 passed, 2 deselected in 46.00s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 14:23
- Commit: e58ab03 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 106 passed, 3 deselected, 1 xfailed in 33.23s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 14:29
- Commit: 9a974b6 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 115 passed, 3 deselected, 1 xfailed in 54.14s
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 14:40
- Commit: b1478c5 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: FALHOU (código 1). 2 failed, 151 passed, 6 deselected in 97.51s (0:01:37)
- Resultado: FALHOU

## Execução do verify_beta.sh

- Data: 2026-11-10 14:51
- Commit: 7df57e1 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: FALHOU (código 1). 2 failed, 157 passed, 6 deselected in 204.27s (0:03:24)
- Resultado: FALHOU

## Execução do verify_beta.sh

- Data: 2026-11-10 14:55
- Commit: e3924c9 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 165 passed, 6 deselected in 133.62s (0:02:13)
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 14:57
- Commit: 17bcb05 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 172 passed, 6 deselected in 143.40s (0:02:23)
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 15:20
- Commit: ef6976f (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 180 passed, 6 deselected in 75.14s (0:01:15)
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 15:24
- Commit: b0eacb5 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 188 passed, 6 deselected in 69.42s (0:01:09)
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 15:42
- Commit: e8d70bd (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 207 passed, 7 deselected in 90.05s (0:01:30)
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 15:59
- Commit: 4c254c3 (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 207 passed, 7 deselected in 74.61s (0:01:14)
- Resultado: passou

## Execução do verify_beta.sh

- Data: 2026-11-10 16:00
- Commit: 88b14af (com alterações não commitadas)
- Camadas pedidas: base
- Camada `base`: passou. 208 passed, 7 deselected in 89.08s (0:01:29)
- Resultado: passou
