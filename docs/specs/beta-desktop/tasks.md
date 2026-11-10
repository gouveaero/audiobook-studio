# Tarefas

Faça na ordem. Para cada tarefa: escreva primeiro o teste que falha, implemente, rode, marque a caixa e faça um commit na branch `beta-desktop`. Se uma tarefa travar por algo que só o dono do projeto resolve, registre em `bloqueios.md` e siga com o que não depende dela.

Marcação de testes: sem marca, rodam sem modelo e em segundos (motor falso, EPUBs sintéticos gerados no próprio teste); `@pytest.mark.model` usa Pocket real; `@pytest.mark.package` usa o app empacotado.

## Base

- [x] **T1.** Configurar neste repositório, antes do primeiro commit, o autor indicado em `local.md`. Criar `.venv`, `requirements-app.txt`, `requirements-dev.txt`, `pytest.ini` e `scripts/verify_beta.sh`, que roda as três camadas de teste, grava o resultado em `EVIDENCE_PATH` e sai com erro se algo falhar. O script exige as variáveis `LOCAL_MD`, `VOICE_PACK_DIR` e `EVIDENCE_PATH`, e falha se faltar alguma. Criar já o teste de R49.
- [x] **T2.** Provar a voz padrão: gerar áudio com a voz exportada de `portuguese_24l`, usando um `HF_HOME` vazio e sem token, e confirmar que clonar uma voz nova continua bloqueado. Até agora isso só foi testado com o modelo de 6 camadas. (R22) **Se falhar:** registrar em `bloqueios.md`, usar a voz pronta como padrão e seguir.
- [ ] **T3.** Medir a referência de R11: Whisper `small` no capítulo de referência em OmniVoice, com o método de `local.md`. Guardar o número em `evidencia.md`.

## Motores e geração

- [x] **T4.** `studio/engines/` com a interface, `omnivoice.py` e motor falso. `generate.py` passa a usá-la, sem mudar o comportamento atual. (R50)
- [ ] **T5.** `pocket.py` com o pré-corte por tokens. (R10)
- [ ] **T6.** Calibrar `rate_range` em dados reais e rodar o capítulo de referência. (R10, R11, R12) **Se R11 não passar depois de ajustar o corte:** não relaxe o critério. Deixe T6 sem marcar, registre os números em `bloqueios.md`, siga até a T24 e encerre com o resultado "incompleto".
- [x] **T7.** Trechos atômicos, travas com PID, descarte de `.wav` ilegível e retomada. (R13)
- [x] **T8.** `work/job.json`, pausar, continuar, cancelar, `caffeinate`, espaço em disco e tempo restante. (R14 a R18)
- [x] **T9.** Ajustar `cloud.py`. (R51)

## Livro

- [x] **T10.** Correções em `prepare_book.py`, com EPUBs sintéticos reproduzindo cada defeito. (R1 a R8)
- [x] **T11.** Rodar nos dois livros reais de `local.md`, usando o `book.json` corrigido à mão do primeiro como lista de conferência, sem exigir igualdade. Corrigir o que aparecer, sem regra específica para um só livro.

## Áudio

- [x] **T12.** Virada de capítulo, EQ e volume ao juntar os trechos. (R19 a R21)
- [x] **T13.** Montagem automática, vídeo opcional e metadados de IA. (R27 a R29)

## Servidor e telas

- [x] **T14.** Pastas do app, `brand.py`, abrir sem `--project`, token de sessão, `Host` e `Range`. (R33, R34, R30)
- [ ] **T15.** Rotas de projetos, voz, modelos, estado e refazer trecho. (R9, R26, R31, R36, R38)
- [x] **T16.** Telas de início e conferência, fontes embutidas. (R9, R35, R39)
- [ ] **T17.** Tela de voz, com padrão, vozes prontas e clonagem guiada, e checagem da gravação. (R22 a R26)
- [x] **T18.** Painel com controles reais e tela final com player. (R14, R18, R30 a R32)
- [ ] **T19.** Teste de ponta a ponta na janela do navegador com o Chrome DevTools: EPUB curto até o M4B, sem usar a linha de comando. Conferir também as telas com capturas e corrigir o que estiver quebrado.

## Instalador e publicação preparada

- [ ] **T20.** `scripts/build_voice_pack.py`, `scripts/build_mac.sh`, `ffmpeg` embutido, microfone e autoteste na janela real. (R22, R40, R43)
- [ ] **T21.** Livro curto do início ao fim com o app empacotado em ambiente limpo. (R41, R42)
- [x] **T22.** Aviso de versão nova. (R44)
- [x] **T23.** `LICENSE`, `THIRD_PARTY.md`, tela "Sobre", README e configuração de doação e Android. (R45 a R48)
- [ ] **T24.** Teste contra dados pessoais e destinos de rede. (R37, R49)

## Fechamento

- [ ] **T25.** Rodar `scripts/verify_beta.sh` de um clone limpo da branch, com `LOCAL_MD`, `VOICE_PACK_DIR` e `EVIDENCE_PATH` apontando para fora do clone, e `EVIDENCE_PATH` para `docs/specs/beta-desktop/evidencia.md` no repositório original. Escrever nela cada requisito com o teste correspondente e o resultado, e listar H1 e H3 a H6 como não verificados.
