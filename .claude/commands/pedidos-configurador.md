---
description: Atende os pedidos de ajuste feitos no painel (configurador visual de rotinas): lê, corrige, testa, publica e responde.
---

Atenda a fila de pedidos do configurador visual de rotinas deste projeto.

1. Rode `python scripts/pedidos_configurador.py listar` para ver os pedidos pendentes.
2. Para cada pendente, rode `python scripts/pedidos_configurador.py ver <id>`: traz o texto do pedido, os passos da
   rotina e o resultado do último teste (passo que falhou e a mensagem). Se houver print da falha, ele está em
   `capturas/configurador_<8 primeiros dígitos do id da rotina>_passo_NN.png`: leia a imagem antes de decidir.
3. Decida a correção, sempre com evidência (print/log), nunca por chute:
   - Ajuste de uma rotina (passos, esperas, marcação): altere `data/configurador/rotinas/<id>/rotina.json` só se for
     um ajuste simples de campo (espera, rótulo, ordem). Para marcar um alvo de novo, peça à pessoa que remarque no
     painel e diga exatamente o que marcar. Depois do ajuste, a rotina volta a rascunho e precisa de novo teste.
   - Passo novo ou comportamento novo: implemente em `app/configurador.py` (+ painel em `web/`), com testes em
     `tests/test_configurador.py`, rode a suíte, publique em main e atualize o pacote (`scripts/gerar_pacote_instalador.py`).
   - Respeite as regras do projeto: nunca transmitir, retificar ou excluir; só competência fechada; nada de dado de
     cliente sai da máquina; só afirme sucesso com log/teste real.
4. Responda ao pedido com `python scripts/pedidos_configurador.py responder <id> "o que foi feito e o que a pessoa deve
   fazer agora (reiniciar o servidor, remarcar, testar de novo)"`. A resposta aparece no painel.
5. Ao final, diga em poucas linhas o que foi atendido e o que ficou pendente. Se o servidor precisar reiniciar para
   carregar código novo, use `scripts/servidor_permanente.ps1 -Acao reiniciar` (recusa se houver lote rodando).

Se não houver pedidos pendentes, diga isso e pergunte se há algo a melhorar no configurador.
