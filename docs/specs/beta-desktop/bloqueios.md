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


### B5. Notas de rodapé no fim do capítulo (T11)
- **Situação:** o `book.json` corrigido à mão do livro 1 ainda trazia as notas de rodapé de seis capítulos; o `prepare_book` agora as tira, como sua descrição já dizia.
- **Opção escolhida para seguir:** notas de rodapé e separadores como "*" não são lidos.
- **Para o dono decidir:** se as notas devem ser lidas.

### B6. Divisões em romano e títulos em maiúsculas (T11, R4)
- **Opção escolhida para seguir:** quando o sumário tem divisões em romano com capítulos em arábico dentro, as divisões viram partes ("Parte I: Nome") e os capítulos ficam "Parte I, capítulo 1: Subtítulo". Título todo em maiúsculas fica só com a inicial maiúscula. Capítulo chamado "Notas sobre..." fica no livro; só saem "Nota", "Notas", "Notas finais" e "Notas e referências".
- **Para o dono decidir:** se esses nomes servem.

### B7. Textos escolhidos sem estarem na especificação (T2, T13)
- **Opção escolhida para seguir:** aviso de clonagem sem login: "Para usar a sua voz, entre na sua conta do Hugging Face e aceite os termos do Pocket TTS. Sem isso, só a voz padrão e as vozes prontas funcionam." Comentário nos metadados do M4B: "Narração gerada por IA. Narrador: {nome}."
- **Para o dono decidir:** se os textos servem.

### B8. A linha de comando deixou de gerar o vídeo MP4 por padrão (T13, R29)
- **Situação:** R29 pede o vídeo só quando a pessoa pedir. Antes, `studio assemble` gerava o MP4 sempre.
- **Opção escolhida para seguir:** vídeo só com `--video`. Isso muda o fluxo atual da skill, que passa a precisar pedir o vídeo.
- **Para o dono decidir:** se a skill deve pedir o vídeo por padrão.

### B9. Mensagens da geração (T8)
- **Opção escolhida para seguir:** falta de espaço: "Sem espaço em disco: a geração precisa de cerca de N MB livres e há M MB. Libere espaço e tente de novo." Erro: "A geração falhou (Tipo). O detalhe está em work/generate.log."
- **Para o dono decidir:** se os textos servem. A segunda cita um nome técnico e um arquivo; o Testador vai avaliar no guia 8.

### B10. Licenças que pedem atenção antes de publicar (T23, R45)
- **Situação:** o instalador vai levar um `ffmpeg` com licença GPL-3.0-or-later e o `num2words` (LGPL). Os pesos do Pocket são CC-BY-4.0, que exige atribuição. O pacote `omnivoice` instalado declara AGPL-3.0-only, embora o model card diga Apache 2.0; ele não vai no instalador.
- **Opção escolhida para seguir:** registrar tudo em `THIRD_PARTY.md` e seguir. Nada é publicado nesta meta.
- **Para o dono decidir:** antes de publicar, conferir as obrigações de distribuir um binário GPL junto do app (oferta do código-fonte do `ffmpeg`) ou trocar por um build LGPL.

### B11. Medição de referência de R11 diferente da especificação (T3)
- **Situação:** `requirements.md` cita 36 palavras perdidas em 6.324 (0,57%) no áudio OmniVoice. A medição refeita pelo Motor com o método de `local.md` deu 45 (0,712%). Ainda falta o Maestro repetir a medição na fila do modelo.
- **Opção escolhida para seguir:** R11 define o teto pela medida feita com o mesmo Whisper, então vale o número medido: teto de 1,212%, cerca de 77 palavras. O critério não foi relaxado; o teste registra os dois números.
- **Para o dono decidir:** se prefere manter o teto antigo de 67 palavras.
