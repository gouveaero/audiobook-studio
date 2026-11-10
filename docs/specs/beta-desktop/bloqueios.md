# Bloqueios e decisões pendentes

Cada item traz o que travou, a opção escolhida para seguir e o que o dono precisa decidir.

## Decisões que mudam o que a pessoa vê (nenhuma trava o desenvolvimento)

### B1. Aparência da capa gerada (T10, R7)
- **Situação:** a especificação pede "uma capa simples gerada", sem dizer como ela é.
- **Opção escolhida para seguir:** quadrado azul escuro com moldura clara, sem texto. O `ffmpeg` de desenvolvimento não tem `drawtext` e o app não leva biblioteca de imagem.
- **Para o dono decidir:** se a capa deve trazer título e autor, o que exige uma dependência de imagem.

### B2. Texto antes do primeiro título em EPUB sem sumário (T10, R6)
- **Opção escolhida para seguir:** vira um capítulo chamado "Início".
- **Para o dono decidir:** se o nome serve.

### B3. Títulos de capítulo fora de partes (T10, R3 e R4)
- **Opção escolhida para seguir:** título que é só número ("1.") vira "Capítulo 1"; "2. O rio" mantém o título; "N | Texto" perde o número.
- **Para o dono decidir:** se esses nomes servem na lista de capítulos.

### B4. Capítulos sem texto e páginas de sumário ou índice (T10, R2)
- **Opção escolhida para seguir:** não entram no `book.json`, então não aparecem na tela de conferência como itens desmarcados.
- **Para o dono decidir:** se devem aparecer desmarcados, para a pessoa poder incluir de volta.

