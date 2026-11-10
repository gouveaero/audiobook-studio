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

### B11. Medição de referência de R11 varia entre rodadas (T3)
- **Situação:** no mesmo áudio OmniVoice e com o mesmo método, o Motor mediu 45 palavras perdidas (0,712%) e o Maestro, com o Whisper refeito do zero, mediu 36 (0,569%), igual a `requirements.md`. O Whisper varia cerca de 9 palavras entre rodadas do mesmo arquivo.
- **Opção escolhida para seguir:** vale a medição feita na mesma execução do teste, como R11 define. O teste registra os dois números.
- **Para o dono decidir:** se R11 deve usar a média de várias medições, já que a variação do Whisper é da mesma ordem que a margem de 0,5 ponto (32 palavras).

### B13. O ffmpeg embutido vem de um repositório não oficial (T20, R45)
- **Situação:** não há build oficial do `ffmpeg` LGPL para Mac com chip Apple. O instalador usa o FFmpeg 8.1.2 LGPL publicado em `github.com/livefantasia/ffmpeg-macos-build`, um repositório de terceiros.
- **Opção escolhida para seguir:** o `build_mac.sh` fixa a SHA-256 do arquivo e aborta se ela mudar, e confere que o binário não foi compilado com partes GPL ou não livres. Com isso o item B10 deixa de ter binário GPL no instalador.
- **Para o dono decidir:** antes de publicar, se aceita essa origem ou se prefere compilar o `ffmpeg` a partir do código oficial, o que exige ferramentas de compilação na máquina de build.

### B14. "Salvar M4B" copia para a pasta Downloads, sem perguntar onde (T18, T19, R32)
- **Situação:** na janela do app, o botão dizia "M4B salvo" sem gravar arquivo nenhum, porque a janela não aceita download iniciado pela página. O defeito apareceu na conferência da T19; o autoteste da janela não clicava no botão.
- **Opção escolhida para seguir:** o botão copia o M4B para a pasta Downloads da pessoa e a tela só confirma depois de o arquivo existir. Se já houver um arquivo com o mesmo nome, o novo recebe " 2", " 3" no fim. "Mostrar no Finder" mostra o arquivo salvo. O autoteste agora clica no botão e confere o arquivo no disco.
- **Decidido em 10/11/2026:** o dono deixou a escolha com o Maestro. Fica como está: salvar sempre em Downloads, que é o caminho mais simples para quem não é técnico. Uma janela para escolher a pasta pode entrar numa versão futura.

## Bloqueio que impede o resultado "completo"

### B12. R11 não passou depois de ajustar o corte (T6 sem marcar)
- **Situação:** capítulo de referência, voz padrão exportada, Whisper `small` com o método de `local.md`. Números medidos pelo Motor (a repetição pelo Maestro está registrada em `evidencia.md`):

| Medição | Palavras perdidas (trechos de 3+) de 6.324 | Percentual |
|---|---|---|
| OmniVoice (referência) | 45 | 0,712% |
| Teto de R11 (referência + 0,5 ponto) | cerca de 77 | 1,212% |
| Pocket antes da correção (dado de `requirements.md`) | 191 | 3,0% |
| Pocket, rodada 1: pré-corte por tokens, faixa de ritmo larga (10 a 22) | 200 | 3,163% |
| Pocket, rodada 2: faixa 12 a 19,5 e caixa alta em minúsculas | 84 | 1,328% |
| Pocket, rodada 3: mais o preenchimento de frases curtas | 94 | 1,486% |

- **Repetição pelo Maestro (configuração da rodada 3, capítulo gerado de novo, Whisper refeito):** OmniVoice 36 (0,569%), teto 1,069% (cerca de 67 palavras), Pocket 103 (1,629%). Reprovado também.
- **O que passou:** R10 (zero avisos "generation may skip words" em 425 pedaços) e o mecanismo de R12 (21 pedaços refeitos; 2 continuaram fora da faixa depois de 4 tentativas e ficaram marcados).
- **Composição das 94 da rodada 3, segundo o Motor:** 30 são cinco anos por extenso que o Whisper escreve em algarismos (o mesmo erro pesa no OmniVoice); 32 são uma passagem de interjeições repetidas que ficou marcada depois de 4 tentativas e aparece na tela final; 32 estão espalhadas em trechos de 3 a 5 palavras. A variação entre rodadas é de cerca de 10 palavras. Na rodada 1, 72 palavras eram erro do Whisper no começo do arquivo.
- **Opção escolhida para seguir:** o critério não foi relaxado. A T6 fica sem marcar, o código fica com a configuração da rodada 3 e o desenvolvimento segue até a T24. O resultado final é "incompleto" enquanto isto estiver aberto.
- **Para o dono decidir:** (a) aceitar o Pocket com cerca de 1,3% a 1,5% de perda medida; (b) mudar o método de R11 para normalizar anos em algarismos dos dois lados, o que tira cerca de 30 palavras da conta do Pocket e parte das 45 do OmniVoice; (c) voltar à configuração da rodada 2, que mediu 84 (a diferença para a rodada 3 está dentro da variação); (d) outra saída. Vale ouvir o capítulo antes (H1).
