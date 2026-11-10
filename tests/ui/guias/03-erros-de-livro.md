# Guia 03: Erros de livro (DRM, sem sumário, sem capa e em inglês)

Objetivo: Verificar o comportamento ao enviar EPUB com DRM, sem sumário, sem capa e em inglês, garantindo mensagens claras em português e ausência de traceback na tela (R5, R6, R7, R8, R38).

Preparação:
- Quatro EPUBs sintéticos gerados com `tests/epub_sintetico.py`:
  1. `livro-drm.epub` (com `META-INF/encryption.xml` cifrando conteúdo).
  2. `livro-sem-sumario.epub` (`toc_format=None`, com títulos `<h1>` no corpo).
  3. `livro-sem-capa.epub` (`cover=False`).
  4. `livro-ingles.epub` (`lang="en"` e texto em inglês).

Passos:
1. Em `home.html`, enviar `livro-drm.epub` em "Novo audiolivro" -> esperado: não cria projeto, permanece em `home.html` e mostra erro claro em português sobre proteção DRM, sem traceback nem caminho de arquivo (R5, R38).
2. Em `home.html`, enviar `livro-ingles.epub` em "Novo audiolivro" -> esperado: não cria projeto, permanece em `home.html` e mostra aviso em português informando que apenas livros em português são aceitos no beta, sem traceback (R8, R38).
3. Em `home.html`, enviar `livro-sem-sumario.epub` -> esperado: livro aceito, dividido pelos títulos `<h1>` do texto ("Primeiro Título" e "Segundo Título") e aberto em `review.html` com os 2 capítulos (R6).
4. Voltar ao início e enviar `livro-sem-capa.epub` -> esperado: livro aceito, capa simples gerada automaticamente no projeto (`cover.png` ou equivalente) e montagem final em M4B concluída sem falha (R7).

Capturas:
- Passo 1: `tests/ui/capturas/03-erro-drm.png`
- Passo 2: `tests/ui/capturas/03-erro-ingles.png`
- Passo 3: `tests/ui/capturas/03-sem-sumario-conferencia.png`

Critério de aprovação:
- DRM e inglês são bloqueados com mensagem em português simples e zero traceback ou nomes técnicos de exceção (R5, R8, R38).
- Sem sumário divide pelos títulos do texto (R6) e sem capa gera capa simples sem falhar na montagem (R7).

Resultado: aprovado.
- Passo 1 (`livro-drm.epub`, R5, R38): Permaneceu em `home.html`, não criou pasta de projeto e exibiu em `#err`: "Este EPUB tem proteção contra cópia (DRM) e não pode ser lido. Use um arquivo sem DRM, como os comprados em lojas que entregam o EPUB aberto." Zero traceback (`tests/ui/capturas/03-erro-drm.png`).
- Passo 2 (`livro-ingles.epub`, R8, R38): Permaneceu em `home.html`, não criou pasta de projeto e exibiu em `#err`: "Este livro parece estar em inglês. Por enquanto, só livros em português podem virar audiolivro." Zero traceback (`tests/ui/capturas/03-erro-ingles.png`).
- Passo 3 (`livro-sem-sumario.epub`, R6): Aceito e aberto em `review.html?id=livro-sem-sumario` dividido pelos títulos `<h1>` do corpo em 2 capítulos ("Primeiro Título" e "Segundo Título") (`tests/ui/capturas/03-sem-sumario-conferencia.png`).
- Passo 4 (`livro-sem-capa.epub`, R7): Aceito, gerou `cover.jpg` simples automaticamente (29.611 bytes) e montou `Livro Sem Capa.m4b` sem falha.
