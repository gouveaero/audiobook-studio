# Requisitos do beta para computador

## Objetivo

Uma pessoa sem conhecimento técnico instala o app num Mac com chip Apple, escolhe um EPUB em português e a voz, e recebe um M4B com capítulos e capa, sem terminal, sem Python e sem ajuda de IA.

O app é grátis. O motor é o Pocket TTS 4.0.1, modelo `portuguese_24l`.

## Fora do escopo

Windows, Linux, celular, PDF, MOBI, outros idiomas, biblioteca de audiolivros, Colab e OmniVoice dentro do app, Piper, Kokoro, player completo, doações ativas, vinheta entre capítulos.

O fluxo atual com OmniVoice e Colab pela linha de comando e pela skill precisa continuar funcionando.

## Dados medidos que sustentam as decisões

Capítulo 1 do livro de teste (37.532 caracteres, cerca de 38 min), conferido com Whisper `small`:

| Modelo | Velocidade | Memória (com clonagem) | Palavras perdidas em trechos de 3+ | Palavras extras |
|---|---|---|---|---|
| `portuguese` (6 camadas) | 10× | 2,0 GB | 529 (8,4%) | 57 |
| `portuguese_24l` | 3,5× | 3,5 GB | 191 (3,0%) | 5 |

A geração avisou 24 vezes que frases longas podiam perder palavras. Parte da perda medida pode ser erro do Whisper. O projeto chama o modelo de 24 camadas de prévia.

## Requisitos

Cada requisito é verificado por teste automático, salvo os marcados como **humano**.

### Livro

- **R1.** Um EPUB válido gera capítulos na ordem do sumário.
- **R2.** Capítulo sem texto, como o que só tem imagem, sai do livro. Capítulo curto com texto, como "Parte I", fica.
- **R3.** A fala do título sai limpa: nunca "um..", "Parte primeiro." nem "um | Autor".
- **R4.** Capítulos dentro de partes recebem títulos como "Parte I, capítulo 3", e a fala começa por "Capítulo três."
- **R5.** EPUB com DRM (`META-INF/encryption.xml` com conteúdo cifrado) mostra erro claro e não cria projeto.
- **R6.** EPUB sem sumário é dividido pelos títulos do texto.
- **R7.** EPUB sem capa recebe uma capa simples gerada, e a montagem não falha.
- **R8.** Livro que não esteja em português mostra aviso e não segue no beta 1.
- **R9.** A pessoa pode incluir, tirar e renomear capítulos, e isso é respeitado na geração e na montagem.

### Geração

- **R10.** Nenhum trecho enviado ao Pocket passa do limite: zero avisos "generation may skip words" no capítulo de referência.
- **R11.** No capítulo de referência, a perda de palavras (trechos de 3+, Whisper `small`) fica no máximo 0,5 ponto percentual acima da medida com o mesmo Whisper no áudio OmniVoice do mesmo capítulo. O teste registra os dois números. Referência medida: OmniVoice perdeu 36 de 6.324 palavras (0,57%), então o teto é cerca de 1,07%, ou 67 palavras. O Pocket antes da correção perdeu 191.
- **R12.** Pedaço com ritmo fora da faixa é refeito até 4 vezes. Se continuar fora, o trecho fica marcado e aparece na tela final. "Pedaço" e "trecho" estão definidos em `design.md`.
- **R13.** Matar o processo no meio e retomar continua do último trecho íntegro, sem refazer o que está pronto e sem capítulo travado por trava velha.
- **R14.** Pausar, continuar e cancelar funcionam. Cancelar não apaga o que está pronto.
- **R15.** Fechar e reabrir a janela durante a geração mostra o estado real, e a geração não para.
- **R16.** O Mac não dorme durante a geração, e essa proteção termina junto com ela.
- **R17.** Sem espaço em disco suficiente, o app avisa antes de começar.
- **R18.** O tempo restante vem da velocidade medida na tarefa.

### Áudio

- **R19.** Cada capítulo sai com volume integrado de -21 LUFS (±1) e pico de no máximo -2,5 dBFS.
- **R20.** A virada de capítulo tem 1,5 s de silêncio antes do título e 1 s depois (±0,15 s), medidos no M4B final. O título sai 8% mais lento e 2,5 dB mais alto que o áudio gerado, conforme `design.md`.
- **R21.** O EQ aprovado se aplica conforme a regra de `design.md`, e o tratamento não exige gerar a voz de novo.

### Voz

- **R22.** O app abre com a voz padrão selecionada, sem login, usando o pacote de voz e os pesos sem clonagem. Sem o pacote, usa a voz pronta configurada.
- **R23.** As vozes prontas do Pocket podem ser escolhidas e ouvidas numa frase curta.
- **R24.** "Usar a minha voz" exige marcar a declaração de que a voz é da pessoa ou que ela tem autorização, guia o aceite dos termos e o login do Hugging Face, e funciona por gravação e por arquivo.
- **R25.** Gravação muito baixa, muito curta ou ruidosa gera um aviso com instruções para regravar. Excesso de graves não gera aviso: só liga o EQ, conforme `design.md`.
- **R26.** O token do Hugging Face fica só em `hf/token`, com permissão 0600, e nunca aparece em log ou resposta da API.
- **R27.** Metadados e tela final dizem que a narração foi gerada por IA.

### Resultado

- **R28.** O M4B traz título, autor, narrador, capa e todos os capítulos, com as durações corretas.
- **R29.** O vídeo MP4 sai só se a pessoa pedir.
- **R30.** O player toca, avança e volta em cada capítulo, inclusive com `Range`.
- **R31.** Refazer um trecho gera a voz só desse trecho e remonta o capítulo.
- **R32.** Há botões para salvar o M4B e mostrá-lo no Finder.

### App e segurança

- **R33.** POST, PUT e DELETE sem o token de sessão recebem 403. Qualquer pedido com `Host` errado recebe 403. GET não exige token, porque `<audio>` não envia cabeçalhos próprios, e por isso nenhum GET altera dados ou revela o token do Hugging Face.
- **R34.** O servidor escuta apenas em `127.0.0.1`.
- **R35.** O app abre e mostra os livros existentes sem internet, depois que o modelo foi baixado.
- **R36.** O primeiro uso mostra o tamanho do modelo e o progresso, e uma queda de conexão permite tentar de novo.
- **R37.** O app não envia dados sem a pessoa pedir. Um teste confere os destinos de rede no código: Hugging Face, GitHub Releases e o endereço opcional do formulário.
- **R38.** Erros aparecem em português simples, sem traceback na tela. O detalhe vai para o log.
- **R39.** Toda a interface fica em português e sem travessão. Um teste procura `—` em `ui/`.

### Instalador

- **R40.** `scripts/build_mac.sh` gera um `.dmg` a partir de um clone limpo.
- **R41.** O app empacotado roda com `env -i HOME=<pasta vazia> PATH=/usr/bin:/bin`, sem Homebrew e sem Python do sistema, e gera um livro curto do início ao fim.
- **R42.** O tamanho do `.dmg` é registrado na evidência. Acima de 1,5 GB, abrir um item em `bloqueios.md` e continuar.
- **R43.** O app empacotado declara `NSMicrophoneUsageDescription`, e um autoteste na janela real (WKWebView, por `evaluate_js`) confirma que `getUserMedia` e o avanço no áudio funcionam. O pywebview 6.2.1 parece não ter suporte a captura em `cocoa.py`: implementar o que faltar. Se a gravação não for possível na janela, deixar só o envio de arquivo e registrar em `bloqueios.md`.
- **R44.** O app avisa quando há versão nova nas releases do GitHub, e a falta de internet não causa erro.

### Publicação preparada, sem publicar

- **R45.** `LICENSE` do código próprio (MIT) e `THIRD_PARTY.md`. A licença do `omnivoice` é apurada e registrada: o model card diz Apache 2.0, e o pacote instalado declara AGPL-3.0. O OmniVoice não vai no instalador.
- **R46.** Tela "Sobre" com termos de uso: só voz com consentimento, livros sem DRM, sem se passar por outra pessoa, narração por IA.
- **R47.** README em português para quem não é técnico, incluindo como liberar a abertura do app sem assinatura da Apple.
- **R48.** Botões de doação e de convite para Android só aparecem quando o endereço estiver configurado em `studio/brand.py`. Por padrão, ficam vazios.
- **R49.** Os arquivos e os commits de `main..beta-desktop` não contêm voz, livro, token, e-mail pessoal, nome da máquina ou caminho de máquina. O autor dos commits novos é o de `local.md`. O teste lê os termos proibidos de `LOCAL_MD`, para não publicá-los, e permite o usuário do GitHub nas URLs do repositório. Os commits antigos da `main` ficam fora deste requisito.

### Compatibilidade

- **R50.** Projeto antigo, sem motor nem `head`, continua gerando e montando com OmniVoice.
- **R51.** `cloud.py` envia `studio/engines/` à VM, envia o necessário para o motor correto e mantém as reservas de capítulo. Um teste com `colab` simulado confere isso.

## Conferências humanas

Não bloqueiam o fim do desenvolvimento. Ficam listadas no relatório final como não verificadas:

- **H1.** Ouvir um capítulo inteiro no app.
- **H3.** Instalar num usuário novo do Mac e, se possível, em outro Mac.
- **H4.** Testar num Mac de 8 GB.
- **H5.** Testar a geração real na nuvem, que gasta unidades do Colab.
- **H6.** Conferir o pedido de permissão do microfone na primeira gravação, que não dá para automatizar.
