# Guia 01: Primeiro uso e download do modelo

Objetivo: Verificar a abertura sem livros, a exibição do download do modelo com tamanho e progresso, a simulação de queda de conexão e a tentativa de novo (R36).

Preparação:
- Servidor iniciado com pasta `AUDIOBOOK_STUDIO_HOME` vazia, sem livros e sem modelo baixado (`status: "ausente"` em `/api/models`).
- Nenhum EPUB pré-carregado.

Passos:
1. Abrir a tela inicial (`home.html`) com o token de sessão -> esperado: tela sem livros listados e com aviso ou painel de primeiro uso mostrando o download do modelo (`portuguese_24l`), seu tamanho total (~672 MB) e barra ou percentual de progresso.
2. Iniciar o download do modelo na interface -> esperado: estado muda para `baixando` e a tela mostra o progresso de bytes baixados sobre o total.
3. Simular queda de conexão durante o download -> esperado: a tela exibe mensagem de erro em português ("O download falhou. Verifique a conexão e tente de novo.") sem traceback e oferece botão para tentar de novo.
4. Clicar em tentar de novo -> esperado: o download recomeça e a tela atualiza o progresso até ficar `pronto`.

Capturas:
- Passo 1: `tests/ui/capturas/01-primeiro-uso-home.png`

Critério de aprovação:
- A interface exibe o tamanho do modelo e o progresso no primeiro uso, informa falha de conexão em português simples e permite tentar de novo pela própria tela (R36).

Resultado: reprovado (não executável na interface atual).
- Passo 1 a 4 (R36 - REPROVADO):
  - Esperado: ao abrir `home.html` sem livros e com `/api/models` em `"status": "ausente"` (`total_bytes: 704643072`), a tela deveria mostrar o tamanho do modelo (~672 MB), iniciar/acompanhar o progresso do download, exibir mensagem em português em caso de queda de conexão e oferecer botão "Tentar de novo".
  - Obtido: nenhuma tela em `ui/` (`ui/home.html` nem as demais) consulta `GET /api/models` ou aciona `POST /api/models/download` (`grep -rn "models" ui/` retorna vazio). A tela inicial mostra apenas "Nenhum livro ainda. Escolha um EPUB em português para começar." (`tests/ui/capturas/01-primeiro-uso-home.png`).
  - O que falta para ser executável sem baixar de verdade: (1) `ui/home.html` consultar `GET /api/models`, exibir tamanho (`total_bytes`) e progresso (`bytes`), erro (`error`) e botão para chamar `POST /api/models/download` ("Baixar modelo" / "Tentar de novo"); (2) `studio/local_api.py` aceitar simulação de download por variável de ambiente (ou a tela reagir ao arquivo `models/portuguese_24l.json` gravado em `AUDIOBOOK_STUDIO_HOME`).
