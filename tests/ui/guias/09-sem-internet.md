# Guia 09: Funcionamento sem internet após download do modelo

Objetivo: Com o modelo já marcado como baixado e livros existentes em `AUDIOBOOK_STUDIO_HOME`, abrir o app sem internet (modo offline) e confirmar que os livros existentes aparecem e podem ser abertos normalmente (R35).

Preparação:
- `AUDIOBOOK_STUDIO_HOME` contendo o estado do modelo como `pronto` (`models/portuguese_24l.json`) e pelo menos um projeto sintético salvo em `projects/`.
- Ambiente do servidor sem acesso externo (`HF_HUB_OFFLINE=1` e sem chamadas de rede na abertura).

Passos:
1. Abrir `home.html` com `HF_HUB_OFFLINE=1` -> esperado: a página carrega imediatamente com fontes locais (`/fonts.css`), sem consultar Google Fonts nem qualquer domínio externo, e lista o livro sintético existente.
2. Clicar em "Abrir" no livro listado -> esperado: abre `review.html` com os capítulos do livro sem erro.
3. Navegar até `ready.html` do livro já pronto -> esperado: abre a tela final e toca o áudio local sem depender de internet.

Capturas:
- Passo 1: `tests/ui/capturas/09-sem-internet-home.png`

Critério de aprovação:
- O app abre, carrega as fontes locais e mostra os livros existentes sem nenhuma requisição externa (R35).

Resultado: aprovado.
- Passo 1 (R35): Com o modelo marcado como `pronto` em `models/portuguese_24l.json`, `home.html` carregou apenas recursos locais (`/fonts.css`, `/studio.js`, `/api/projects`, `externalResources: []`) e listou os livros sintéticos existentes (`Crônicas da Praça`, `Livro Sem Capa`, `Livro Sem Sumário`) (`tests/ui/capturas/09-sem-internet-home.png`).
- Passo 2: Clicar em "Abrir" em `Crônicas da Praça` abriu `review.html?id=cronicas-da-praca` com os capítulos do livro e zero requisições externas (`externalResources: []`).
- Passo 3: `ready.html?id=cronicas-da-praca` exibiu os capítulos prontos ("Capítulo Um: A Praça" e "3. O Rio no Inverno") com áudio local e zero requisições externas (`externalResources: []`).
