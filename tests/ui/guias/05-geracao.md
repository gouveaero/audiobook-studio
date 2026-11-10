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
- Passo 1: `tests/ui/capturas/05-geracao-rodando.png`
- Passo 2: `tests/ui/capturas/05-geracao-pausada.png`
- Passo 5: `tests/ui/capturas/05-geracao-cancelada.png`

Critério de aprovação:
- Pausar, continuar e cancelar funcionam pela tela e preservam os arquivos já gerados (R14).
- Reabrir a janela reflete o estado real da tarefa em andamento (R15).
- O tempo restante aparece e muda durante a geração (R18).
- A tela não exibe textos falsos de nuvem quando a geração é 100% local nem estados contraditórios.

Resultado: reprovado.
- Passo 1 (Iniciar e tempo restante, R18): A geração iniciou automaticamente (`status: "gerando"`) e o tempo restante (`#etaTxt`) evoluiu conforme a velocidade medida (`restam ~3 min` -> `restam ~18 s` -> `restam ~15 s` -> `restam ~12 s`). Porém, a tela exibe estado que não bate com a realidade local: grava `[...] conectando à nuvem...` no quadro `#log` (`ui/dashboard.html` linha 226) e mostra o medidor `NVIDIA A100, GPU 0%` (`ui/dashboard.html` linhas 117 e 260) mesmo em geração local no Mac (`tests/ui/capturas/05-geracao-rodando.png`).
- Passo 2 e 3 (Pausar e continuar, R14): Ao clicar em "Pausar", o estado mudou para `pausado`, `#liveTxt` exibiu `pausado` e o botão "Continuar" habilitou (`tests/ui/capturas/05-geracao-pausada.png`); ao clicar em "Continuar", voltou a `gerando`.
- Passo 4 (Fechar e reabrir a janela, R15): Ao sair para `home.html` e reabrir `dashboard.html?id=livro-sem-sumario`, a geração continuou em segundo plano (`chars_done` avançou de 492 para 743) e a tela mostrou o progresso real sem reiniciar.
- Passo 5 (Cancelar, R14 - REPROVADO por estado que não bate com a realidade):
  - Esperado: ao cancelar, o processo para preservando os trechos prontos e a tela mostra o estado `cancelado`, zera/oculta a estimativa de tempo restante e permite retomar ou voltar.
  - Obtido: o backend encerrou o processo (`status: "cancelado"`) e preservou os 10 arquivos `.wav` em `work/chunks/`, mas `ui/dashboard.html` (linha 155) continua exibindo `● ao vivo` em `#liveTxt`, mantém `restam ~7 s` em `#etaTxt`, deixa os 3 botões (`Pausar`, `Continuar`, `Cancelar`) desabilitados sem opção de retomar ou voltar ao início, e segue imprimindo `gpu 0%  nuvem 0,0x  local 0,6x` no `#log` (`tests/ui/capturas/05-geracao-cancelada.png`).
