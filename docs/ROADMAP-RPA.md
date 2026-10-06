# Caminho até o RPA com agentes de IA

Este plano continua o projeto Domínio Automation Engine. O objetivo é
transformar as rotinas de leitura/geração já conhecidas em capacidades
que agentes possam escolher e executar pela interface, com resultados
verificáveis. As etapas abaixo são incrementos; os recursos futuros não
estão implementados só por constarem neste documento.

## Ponto de partida

Há OCR local, busca de ícones, interação com mouse/teclado, espera por
estado, quatro rotinas conhecidas, tratamento de alguns erros, interface
local, histórico e gravador de cliques que gera rascunhos. A IA já auxilia
em decisões restritas; isso ainda não é um agente operador geral.

O motor mínimo `app/estados.py` espera detectores de sucesso/erro. Ele
não acompanha todas as etapas de uma execução. O gravador ainda exige
revisão e complementação de digitação, hover e verificações.

A rodada recente de Livros Fiscais chegou à exportação, mas a nova
conferência do período no PDF a recusou. Esse resultado continua pendente.
O usuário deixou o nome do arquivo de lado; essa pendência não será
alterada neste incremento de estados.

## 1. Acompanhar uma rotina inteira por estados — incremento atual

Começar pelo Registro de Saídas e reaproveitar a implementação comum
para Entradas, mantendo a navegação existente. Registrar início,
confirmação e falha de cada etapa com evidência do mecanismo já usado:
identificar empresa no cabeçalho, reconhecer Livros Fiscais, conferir os
campos do período, reconhecer a prévia, exportar e conferir o PDF.

O log deve distinguir tentativa de ação, estado observado e resultado.
Um clique não comprova que uma tela mudou; Esc não comprova que ela
fechou. Toda saída de falha deve indicar a etapa corrente. Os eventos
ficam locais e não incluem conteúdo fiscal para uso por IA.

Critério de conclusão: testes de progressão e falha passam e uma rodada
Windows mostra as etapas corretas, incluindo o ponto de interrupção.
Nenhum teste simulado substitui a validação ao vivo.

## 2. Consolidar execução e recuperação

Resolver falhas confirmadas pelos logs sem inventar novas posições na
tela. Acrescentar limites de espera, interrupção entre ações e estratégias
de recuperação para cenários observados. Confirmar o retorno à tela
esperada antes de iniciar outra empresa. Levar os estados às demais
rotinas e executar lotes com resultado separado por empresa/documento.

Critério de conclusão: uma falha não contamina a próxima empresa; a
execução registra o que foi concluído, recusado ou ficou pendente.

## 3. Criar um catálogo de capacidades

Descrever cada rotina pelo objetivo, entradas, pré-condições, etapas,
checagens, resultado e tratamento de falhas. Separar parâmetros de
empresa/período da navegação, para reaproveitar uma capacidade sem
regravar todo o percurso. O executor aceita apenas capacidades existentes
com entradas válidas e pré-condições atendidas.

Critério de conclusão: uma rotina validada pode ser solicitada por uma
entrada estruturada e produzir um resultado igualmente estruturado.

## 4. Aprender novas rotinas por demonstração e evidência

Evoluir o gravador para representar cliques, hover, teclas e campos
parametrizados, acompanhados de capturas locais e estados esperados.
Usar IA para sugerir uma rotina e suas verificações, revisar a proposta,
testar com supervisão e só então incluí-la no catálogo.

Aprendizado também significa guardar padrões de erro, estratégias de
leitura que funcionaram e variações observadas. Guardar uma gravação ou
uma resposta da IA não comprova que a rotina foi aprendida corretamente.

Critério de conclusão: uma demonstração vira proposta testável, e uma
rotina só passa a estar disponível depois de validada. Mudanças de tela
exigem revalidação da capacidade afetada.

## 5. Agentes de IA como operadores

Dar a cada agente uma tarefa, um papel, permissões e acesso às capacidades
validadas. O agente observa um resumo do estado, escolhe uma capacidade
e recebe seu resultado. O executor local realiza a ação pela interface
e confirma o efeito. Os agentes não precisam receber dados fiscais
brutos para escolher uma rotina.

Definir as interfaces e sessões autorizadas nesta fase. Uma sessão de
mouse/teclado tem apenas um executor por vez; vários agentes precisam de
uma fila ou sessões separadas, para não disputar o mesmo desktop.
Histórico e autoria de cada execução devem permitir reconstruir decisões.

Critério de conclusão: uma tarefa com vários passos é completada por
capacidades conhecidas, com intervenção humana quando a evidência ou a
permissão for insuficiente. Um agente não recebe autoridade para inventar
ou executar qualquer ação apenas por conseguir descrevê-la.

## 6. Ampliar autonomia e interface de acompanhamento

Medir taxa de conclusão, leituras incertas, recuperação, duração e
intervenções humanas em ciclos reais. Usar essas medidas para ampliar
escopo gradualmente e construir o painel/fila de tarefas previstos no
roadmap original. A execução local permanece responsável pelo acesso à
sessão Windows; o ambiente de nuvem não controla esse desktop hoje.

Geração/leitura continuam sendo o escopo atual. Transmissão, retificação,
exclusão e operação sobre competência em aberto não entram neste plano
como ações já autorizadas.

## Progresso observado em 06/10/2026

O acompanhamento por estados foi observado numa rodada Windows de
Registro de Saídas: a execução chegou ao PDF novo estável e registrou a
recusa do período na etapa `conferir_pdf`, terminando em falha. Isso não
confirma a conferência final do conteúdo nem o encerramento da tela.

O incremento seguinte tenta sair da prévia com Esc após falha, mantendo
a etapa e o erro original. Passou em testes locais/simulados e aguarda
observação no Windows. Retorno à interface ainda precisa de confirmação
humana; não há retomada automática apoiada nesse fechamento.
