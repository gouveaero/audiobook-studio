# Especificação do beta para computador

Desenvolvimento guiado por especificação. Leia nesta ordem:

1. `requirements.md`: o que precisa ser verdade no fim.
2. `design.md`: as decisões de como fazer.
3. `tasks.md`: a ordem de trabalho e o progresso.
4. `local.md`: caminhos desta máquina. Fica fora do git e pode não existir em outro clone.

`lista-de-espera.md` é uma trilha separada, fora desta meta.

## Como trabalhar

- Branch `beta-desktop`, com commits pequenos. Sem push, merge, release ou publicação.
- O teste vem antes do código. Teste que falha nunca é apagado, enfraquecido ou pulado para fechar uma tarefa; se o requisito parecer errado, registre em `bloqueios.md`.
- "Pronto" exige evidência rodada, registrada em `evidencia.md`. Quando algo não puder ser verificado, diga isso em vez de presumir.
- Não mexa na voz do dono, nos livros de teste, nem nos projetos em `projects/`, exceto para ler. Saídas de teste vão para pastas temporárias.
- Nada de novas decisões de produto: o que não estiver na especificação e mudar o que a pessoa vê vai para `bloqueios.md`, com a opção escolhida para seguir.

## Limites

Sem autorização nova, nunca faça: push, release, site, formulário, n8n, Colab pago, conta nova ou instalação que exija administrador. Se algo depender disso, registre em `bloqueios.md` e siga com o resto.

## Quando termina

- **Completo:** todas as caixas de `tasks.md` marcadas, `scripts/verify_beta.sh` passando num clone limpo e `evidencia.md` completa.
- **Incompleto:** só quando um bloqueio impedir uma tarefa e todas as outras estiverem prontas. Nunca marque como completo o que depende de um item aberto.

Nos dois casos, o relatório final traz o caminho do `.dmg`, o que não foi verificado e o que está em `bloqueios.md`.
