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

O motor `app/estados.py` espera detectores de sucesso/erro e acompanha
as etapas das quatro rotinas conhecidas, distinguindo ação e evidência.
A revalidação Windows dos incrementos recentes continua pendente.
O gravador agora grava digitação (passos próprios, não mistura com
clique), hover marcado manualmente (F9, não inferido) e espera por
fingerprint em vez de tempo fixo entre passos (seção 0.81) — validado
por teste de lógica real com `pynput`, ainda sem uma gravação real
contra o Domínio.

A interface local agora reúne Painel de estados, Rotinas, catálogo,
Histórico, Projeto e Log. Há indicadores de evidência por etapa e de
retorno, sem assumir sucesso após enviar uma ação. A prévia visual foi
conferida em tela virtual; uso da versão atual no Windows permanece
pendente. O visual acompanha o projeto enquanto os demais incrementos
avançam, sem habilitar agentes antes da validação das capacidades.

A rodada recente de Livros Fiscais chegou à exportação, mas a nova
conferência do período no PDF a recusou. Esse resultado continua pendente.
O usuário deixou o nome do arquivo de lado; essa pendência não será
alterada neste incremento de estados.

## 1. Acompanhar uma rotina inteira por estados

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

## 2. Consolidar execução e recuperação — incremento atual

Resolver falhas confirmadas pelos logs sem inventar novas posições na
tela. Acrescentar limites de espera, interrupção entre ações e estratégias
de recuperação para cenários observados. Confirmar retorno à tela
esperada antes de iniciar outra tarefa. Levar estados às demais rotinas.
Prioridade atualizada em 08/10/2026: concluir controles/login da interface
e depois configurar lotes de rotinas por empresas e regime. O lote remoto
ainda não está habilitado.

Critério de conclusão atual: execução individual com resultado/conteúdo
e retorno conferidos; falha e recuperação registradas sem falso sucesso.
Para lote, validar isolamento por empresa/documento e troca de empresa
antes de liberar a execução remota.

Implementados para teste: referência local de retorno, verificação em
duas capturas com foco/cabeçalho, etapas SPED/Contribuições e proteção das
transições do lote calibrado. Falta validar esses comportamentos no
Windows. A calibração foi concluída pelo operador em 07/10/2026;
retorno após geração e transições de lote continuam pendentes.
A pendência de período/nome do PDF continua pausada.

## 3. Criar um catálogo de capacidades

Descrever cada rotina pelo objetivo, entradas, pré-condições, etapas,
checagens, resultado e tratamento de falhas. Separar parâmetros de
empresa/período da navegação, para reaproveitar uma capacidade sem
regravar todo o percurso. O executor aceita apenas capacidades existentes
com entradas válidas e pré-condições atendidas.

Critério de conclusão: uma rotina validada pode ser solicitada por uma
entrada estruturada e produzir um resultado igualmente estruturado.

Preparação disponível: `app/capacidades.py` e `atalhos/ferramentas/Listar Funcoes.bat`
descrevem as quatro rotinas e suas limitações. A API agora aceita pedidos
estruturados para essas funções, com parâmetros e pré-condições restritos.
Seu adaptador reutiliza os geradores existentes; ainda precisa de
validação fiscal Windows. Não há executor de agentes gerais.

## 4. Aprender novas rotinas por demonstração e evidência

Evoluir o gravador para representar cliques, hover, teclas e campos
parametrizados, acompanhados de capturas locais e estados esperados.
Usar IA para sugerir uma rotina e suas verificações, revisar a proposta,
testar com supervisão e só então incluí-la no catálogo.

Aprendizado também significa guardar padrões de erro, estratégias de
leitura que funcionaram e variações observadas. Guardar uma gravação ou
uma resposta da IA não comprova que a rotina foi aprendida corretamente.

Testar com supervisão antes de incluir no catálogo agora existe
(`app/rotina_gravada.py`, seção 0.82): toda rotina gravada nasce
rascunho, roda empresa única supervisionada, e só vira "aprovada"
depois de confirmação explícita de que o resultado no Domínio estava
certo. Rotina aprovada entra no mesmo motor de lote do SPED
Fiscal/EFD Contribuições (`dominio.executar_lote(documentos_personalizados=...)`),
sem duplicar o loop de empresas. Sem IA sugerindo a rotina ainda — a
demonstração em si é a proposta, revisão humana decide parâmetro e
aprovação. Ainda sem revalidação Windows de ponta a ponta.

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

Entrega antecipada da interface em 08/10/2026: site/PWA conectado à API,
tarefas individuais persistidas e worker exclusivo. Modos consulta e
simulação funcionam sem Domínio. Operação real depende da sessão Windows,
Domínio configurado, calibração e testes de conteúdo/retorno. O servidor
do usuário ainda não tem o Domínio configurado. Consulte
[SERVIDOR-E-INTERFACE.md](SERVIDOR-E-INTERFACE.md). Contas individuais e
agentes gerais continuam pendentes; o site não conclui todo o roadmap.

Geração/leitura continuam sendo o escopo atual. Transmissão, retificação,
exclusão e operação sobre competência em aberto não entram neste plano
como ações já autorizadas.

## Progresso observado e preparado em 07/10/2026

O acompanhamento por estados foi observado numa rodada Windows de
Registro de Saídas: a execução chegou ao PDF novo estável e registrou a
recusa do período na etapa `conferir_pdf`, terminando em falha. Isso não
confirma a conferência final do conteúdo nem o encerramento da tela.

O incremento seguinte tenta sair da prévia com Esc após falha, mantendo
a etapa e o erro original. Passou em testes locais/simulados. O log Windows confirmou o envio de
Esc e preservou a falha original, mas não comprovou o fechamento. Retorno à interface ainda precisa de confirmação
humana; não há retomada automática apoiada nesse fechamento.

O usuário confirmou que a prévia continuou aberta nessa rodada.
A captura seguinte mostrou o Adobe Acrobat em primeiro plano com o PDF
exportado. O incremento atual guarda a janela do Domínio associada à
prévia reconhecida e exige foco confirmado antes de enviar Esc. Essa
correção foi executada no Windows: o log mostrou foco confirmado antes
de Esc, e o usuário confirmou que voltou à tela principal. A recuperação
funcionou nessa rodada, mantendo a falha original de conferência do PDF.

Agora a referência é medida localmente pelo operador no Windows, via
`atalhos/ferramentas/Calibrar Tela Principal.bat`. A cor/geometria vêm da captura real;
somente metadados são salvos. Comparação exige área calibrada uniforme,
foco e cabeçalho em duas capturas. Os critérios conservadores passaram
por testes sintéticos. Em 07/10/2026, a calibração real concluiu com
código 0 e referência salva: captura 1440×900, área azul
`[0, 128, 1377, 823]`. Falta validar a comparação de retorno após uma
rotina real; a calibração isolada não conclui essa verificação.
Nenhuma nova ação de fechamento foi introduzida.

O lote calibrado interrompe transições quando não confirma retorno,
inclusive após uma geração que devolveu `True`; preserva resultados
já produzidos. Sem calibração, permanece supervisionado e avisa. Há
acompanhamento SPED/Contribuições e correção do falso sucesso no histórico
da GUI. A [retomada](RETOMADA.md) descreve os testes pendentes.

O painel recebe eventos estruturados do motor e mostra tentativa,
etapas confirmadas, falha, recuperação e retorno como informações
distintas. A aba Projeto apresenta os seis incrementos e abre ferramentas
de calibração e avaliação local. A atividade fiscal continua usando os
mesmos callbacks, condições de confirmação e minimização da interface.
Catálogo executável, aprendizagem por demonstração e agentes gerais ainda
não foram concluídos. A aparência sozinha não valida uma capacidade.

## Componentes de percepção durante os incrementos

O [prompt Hugging Face](PROMPT-DESENVOLVIMENTO-HUGGING-FACE.md) mantém
esta sequência de projeto. Avaliação de PaddleOCR começa opcional,
local e sem ações; substituição do OCR depende de ganho nas mesmas
telas e regressão SPED. VL/layout entram apenas com dificuldade concreta
que os justifique. Isso não cria uma fase paralela nem habilita agentes.

## Próxima entrega: lotes por regime e rotinas

Pedido de 08/10/2026: escolher, por exemplo, Simples Nacional e um
conjunto de rotinas, configurar os roteiros na interface e executar as
combinações aprovadas. Reusar `app/empresas.py` e o formato local
`codigo;apelido;regime;tipo;sped`, sem confundir arquivo de exemplo com
cadastro real. O regime filtra empresas; ele não determina sozinho
quais obrigações cada empresa deve gerar.

Sequência de implementação/teste:

1. Cadastro/importação de empresas pela interface, com filtro por regime.
2. Seleção das empresas e rotinas aprovadas, calendário obrigatório e
   revisão das combinações antes do envio. Rascunhos precisam de teste
   supervisionado e validação do resultado antes de entrar no lote.
3. Troca de empresa pelo caminho F8 já existente, confirmando modo de
   busca por Código e relendo o código no cabeçalho. Hoje o executor
   remoto exige que a empresa já esteja selecionada; não presumir que
   o lote remoto já existe porque há um lote local na GUI.
4. Fila persistida no servidor, uma combinação por vez. Só avançar com
   resultado e retorno confirmados; pausa/cancelamento preservam os
   resultados anteriores. Reinício não repete uma geração inacabada.
5. Rodada Windows com duas empresas reais autorizadas e rotinas já
   validadas; revisar os documentos e os estados antes de ampliar.

## Agendamento futuro por empresa

Guardar empresa/regime selecionado, rotinas aprovadas, dia, horário,
fuso explícito (`America/Sao_Paulo`), repetição e regra de competência.
Materializar a lista de empresas e o período em cada ocorrência e
submeter à mesma fila exclusiva do lote. Calendário corrente não autoriza
operação fiscal: o período precisa ser passado e ter apuração confirmada.

Registrar a ocorrência com identificador único para não duplicar geração
após reinício ou desconexão. Se o horário foi perdido, marcar para revisão;
não executar atrasados automaticamente. Se Onvio pedir novo código,
mostrar Aguardando código na interface, com prazo e cancelamento.
Definir armazenamento protegido de credenciais no Windows antes de
prometer login sem presença: a entrega atual usa senhas só em memória
durante cada tentativa e não agenda execuções.
