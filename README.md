<p align="center"><img src="assets/logo.png" width="160" alt="Audiobook Studio"></p>

<h1 align="center">Audiobook Studio</h1>

Transforme um livro em português (EPUB) em audiolivro no seu Mac, com a voz padrão do app, uma voz pronta ou a sua própria voz. Tudo roda neste computador. Depois que o modelo for baixado na primeira vez, funciona sem internet.

## O que você precisa

- Um Mac com chip Apple (M1, M2, M3 ou mais novo).
- Um arquivo EPUB em português (sem DRM).
- Opcional: conta no Hugging Face só se quiser clonar a sua voz.

## Como usar o app

1. Abra o **Audiobook Studio**.
2. Escolha **Novo audiolivro** e selecione o EPUB.
3. Confira os capítulos (incluir, tirar ou renomear).
4. Escolha a voz (padrão, pronta ou a sua).
5. Aguarde a geração. Você pode pausar, continuar ou cancelar.
6. Na tela final, ouça os capítulos, refaça trechos se precisar e salve o M4B.

A narração é gerada por inteligência artificial. Use só a sua voz, ou a de quem autorizou por escrito. Livros com direitos autorais são para uso pessoal, salvo licença.

## Se o Mac recusar abrir o app

O instalador usa assinatura ad hoc (sem conta de desenvolvedor Apple). Na primeira abertura o macOS pode avisar que o app é de um desenvolvedor não identificado.

1. Vá em **Ajustes do Sistema → Privacidade e Segurança**.
2. Procure a mensagem sobre o Audiobook Studio e clique em **Abrir mesmo assim**.
3. Se não aparecer, clique no app com a tecla **Control** pressionada (ou botão direito) → **Abrir** → confirme.

Detalhes da Apple: [Abrir um app de um desenvolvedor não identificado](https://support.apple.com/pt-br/HT202491).

## Licenças

- Código próprio: [LICENSE](LICENSE) (MIT).
- Softwares e modelos de terceiros: [THIRD_PARTY.md](THIRD_PARTY.md).

## Linha de comando (OmniVoice e Colab)

O fluxo antigo por terminal, com OmniVoice e GPU no Colab, continua valendo. Está em [docs/linha-de-comando.md](docs/linha-de-comando.md).
