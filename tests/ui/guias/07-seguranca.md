# Guia 07: Segurança do servidor local

Objetivo: Confirmar que pedidos mutáveis (POST, PUT, DELETE) sem o token de sessão recebem HTTP 403 e qualquer pedido com cabeçalho `Host` diferente de `127.0.0.1:<porta>` recebe HTTP 403 (R33).

Preparação:
- Servidor iniciado em `127.0.0.1:8795` com `--token demo-token`.
- Portal aberto em `http://127.0.0.1:8795/?token=demo-token`.

Passos:
1. No navegador do portal, disparar um `POST /api/projects` sem o cabeçalho `X-Studio-Token` -> esperado: resposta HTTP 403 com `{"error": "Pedido recusado."}`.
2. Disparar um `PUT /api/projects/qualquer/book` e um `DELETE /api/projects/qualquer` sem `X-Studio-Token` -> esperado: ambos recebem HTTP 403.
3. Disparar um `POST /api/projects` com `X-Studio-Token: token-errado` -> esperado: resposta HTTP 403.
4. Fazer um pedido HTTP ao servidor (`GET /api/projects` e `POST /api/projects`) enviando `Host: evil.example:8795` e `Host: localhost:8795` -> esperado: ambos recebem HTTP 403 com `{"error": "Pedido recusado."}`.

Capturas:
- Passo 4: `tests/ui/capturas/07-seguranca-403.png`

Critério de aprovação:
- 100% dos pedidos POST, PUT e DELETE sem token ou com token inválido recebem 403, e 100% dos pedidos com `Host` diferente de `127.0.0.1:8795` recebem 403 (R33).

Resultado: aprovado.
- Passo 1 (`POST /api/projects` sem `X-Studio-Token`): retornou HTTP 403 com `{"error": "Pedido recusado."}`.
- Passo 2 (`PUT /api/projects/x/book` e `DELETE /api/projects/x` sem `X-Studio-Token`): ambos retornaram HTTP 403.
- Passo 3 (`POST /api/projects` com `X-Studio-Token: errado`): retornou HTTP 403.
- Passo 4 (`GET /api/projects` com `Host: evil.example:8795` e `POST /api/projects` com `Host: localhost:8795` mesmo enviando o token): ambos retornaram HTTP 403 com `{"error": "Pedido recusado."}`.
- Captura: `tests/ui/capturas/07-seguranca-403.png`.
