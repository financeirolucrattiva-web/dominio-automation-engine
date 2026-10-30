# Domínio Automation Engine

Antes de mexer em qualquer automação do Domínio neste repositório,
leia `docs/HANDOFF.md` e `docs/00-analise-e-plano-fase0.md` (histórico
completo de achados reais — cada um com causa e correção).

Para construir ou estender uma rotina de automação do Domínio, use o
agente `automacao-dominio` (`.claude/agents/automacao-dominio.md`) —
ele já conhece as convenções deste projeto (OCR + clique sintético via
GO-Global, nunca UI Automation; esperar por estado, nunca tempo fixo;
sempre pedir a próxima captura real em vez de supor caminho de menu).

Regras que não têm exceção:
- Nenhum dado real de cliente sai da máquina.
- Nunca operar sobre a competência corrente/em aberto.
- Nunca automatizar transmissão/retificação/exclusão, só geração/leitura.
- Nunca afirmar sucesso de uma automação sem log real de execução
  contra o Domínio.

Configurador visual de rotinas (painel): pedidos de ajuste feitos pela equipe ficam na fila
`data/configurador/pedidos`. Para atende-los use o comando `/pedidos-configurador` (ou
`python scripts/pedidos_configurador.py listar`): ler pedido + passos + ultimo teste, corrigir com evidencia,
testar, publicar e responder pelo proprio script (a resposta aparece no painel).
