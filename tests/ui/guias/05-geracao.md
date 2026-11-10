# Guia 05: Painel de geração (iniciar, pausar, continuar, reabrir, cancelar e tempo restante)

Objetivo: Testar o início da geração no painel, pausar, continuar, fechar e reabrir a janela mantendo o estado real, cancelar sem apagar o que está pronto e conferir que o tempo restante é exibido e muda conforme a velocidade medida (R14, R15, R18).

Preparação:
- Servidor iniciado com `FAKE_ENGINE_DELAY=1.5` para que cada trecho leve cerca de 1,5 s.
- Projeto sintético configurado com `{"motor": "tests.fake_engine:FakeEngine"}` em `config.json`.

Passos:
1. Abrir `dashboard.html?id=<projeto>` -> esperado: a geração inicia automaticamente (`status: "gerando"`), o botão "Pausar" fica habilitado, "Continuar" fica desabilitado e após os primeiros trechos aparece a estimativa de tempo restante (`restam ~...`) calculada pela velocidade medida (R18).
2. Clicar em "Pausar" -> esperado: estado muda para `pausado`, o indicador superior mostra "pausado", o botão "Pausar" desabilita e o botão "Continuar" habilita (R14).
3. Clicar em "Continuar" -> esperado: estado volta para `gerando` ("ao vivo") e o progresso e o tempo restante voltam a atualizar (R14, R18).
4. Navegar para fora (ou recarregar/reabrir `dashboard.html?id=<projeto>`) durante a geração -> esperado: a geração continua rodando em processo separado e a tela reaberta mostra o estado e o progresso reais sem reiniciar do zero (R15).
5. Clicar em "Cancelar" -> esperado: a geração para com estado `cancelado` (ou `cancelando` -> `cancelado`), e os trechos `.wav` já prontos permanecem preservados em `work/chunks/` (R14).

Capturas:
- Passo 1 (`gerando`): `tests/ui/capturas/05-geracao-rodando.png`
- Passo 2 (`pausado`): `tests/ui/capturas/05-geracao-pausada.png`
- Passo 5 (`cancelado`): `tests/ui/capturas/05-geracao-cancelada.png`
- Estado `erro`: `tests/ui/capturas/05-geracao-erro.png`

Critério de aprovação:
- Pausar, continuar e cancelar funcionam pela tela e preservam os arquivos já gerados (R14).
- Reabrir a janela reflete o estado real da tarefa em andamento (R15).
- O tempo restante aparece e muda durante a geração (R18).
- A tela não exibe textos falsos de nuvem quando a geração é 100% local nem estados contraditórios.

Resultado: aprovado na 2ª rodada.
- Histórico (1ª rodada): reprovado porque no estado `cancelado` a tela mantinha `● ao vivo`, `restam ~7 s` e desabilitava os 3 botões sem permitir retomar/voltar, além de exibir `conectando à nuvem...` e `NVIDIA A100, GPU 0%` na geração local.
- 2ª rodada (todos os estados conferidos):
  - `gerando`: `#liveTxt` exibe `ao vivo` (`.live = true`), `#gc` (medidor de nuvem) oculto (`hidden = true`), `#log` registra `"geração local pronta para começar"` e `"ritmo local ...×"`, e `#etaTxt` evolui (`restam ~24 s` -> `restam ~14 s` -> `restam ~9 s`) (`tests/ui/capturas/05-geracao-rodando.png`).
  - `pausado`: `#liveTxt` muda para `pausado` (`.live = false`), botão `"Continuar"` (`#btnResume`) habilita e botão `"Voltar ao início"` (`#btnHome`) fica visível (`tests/ui/capturas/05-geracao-pausada.png`).
  - Fechar e reabrir (`R15`): navegar para `home.html` e voltar a `dashboard.html` manteve a geração rodando (`chars_done` avançou de 374 para 743).
  - `cancelado`: `#liveTxt` muda para `cancelado` (`.live = false`), `#etaTxt` fica vazio (`""`), `"Pausar"` e `"Cancelar"` ficam ocultos, `"Continuar a geração"` (`#btnResume`) fica habilitado, `"Voltar ao início"` (`#btnHome`) fica visível e os trechos `.wav` prontos são preservados (`tests/ui/capturas/05-geracao-cancelada.png`).
  - `montando`: `#liveTxt` exibe `montando` (`.live = false`) com botões de controle desabilitados durante a montagem final.
  - `erro`: `#liveTxt` exibe `erro`, `#dashErr` mostra mensagem limpa sem nome de exceção nem caminho de log (`"A geração falhou. Veja o log para o detalhe."`), com botões `"Tentar de novo"` e `"Voltar ao início"` (`tests/ui/capturas/05-geracao-erro.png`).
  - `pronto`: ao clicar em `"Tentar de novo"` / `"Continuar a geração"`, retomou do trecho parado, concluiu a montagem em `t=5 s` e redirecionou automaticamente para `ready.html?id=livro-sem-sumario`.
