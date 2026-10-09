# Roadmap de gestão — Domínio Automation Engine

**Referência:** 09/10/2026 · **Empresa:** Lucrattiva Contabilidade

**Público:** administradores, supervisores e equipe fiscal
**Base analisada:** repositório `financeirolucrattiva-web/dominio-automation-engine`,
commit `8713586` e alterações locais desta entrega. Implementação preparada
neste ambiente; instalação, execução e homologação no Windows do escritório
continuam sendo etapas próprias.

## Situação atual

O projeto já tem um motor que opera o Domínio pela interface, painel web,
cadastro de empresas com código e regime, sequência de rotinas por regime,
execução individual e em lote, histórico, acompanhamento por etapas,
pausa/continuação, login com código humano e instaladores para servidor e
interface cliente. A fila permite uma execução por sessão Windows.

A etapa atual é **consolidar a execução, a recuperação e a validação
das rotinas**. O projeto está preparado para testes supervisionados.
A existência do painel e os testes simulados não comprovam a qualidade
dos documentos fiscais da versão atual.

Geração de SPED Fiscal e EFD Contribuições foi observada no Windows em
versões anteriores. Ainda falta comparar o conteúdo com obrigações já
entregues e revalidar o retorno à tela principal. Entradas e Saídas já têm
motor integrado; a conferência atual de período do PDF de Saídas recusou
um resultado real, e a revisão dessa pendência permanece necessária.

Não há percentual de conclusão confiável: recursos técnicos entregues e
homologação fiscal têm critérios diferentes. Agendamento e agentes de IA
operadores continuam no roadmap ampliado.

## Escopo decidido para o piloto

Os regimes preparados são **Lucro Presumido** e **Lucro Real**. O primeiro
piloto será exclusivamente no **Lucro Presumido**; Lucro Real entra depois
da aceitação do primeiro piloto.

| Indicador/rotina | Situação de partida | Próximo trabalho |
| --- | --- | --- |
| Resumo por Acumulador | Nome cadastrado, vinculado aos dois regimes | Mapear a tela, configurar e validar o relatório |
| Demonstrativo EFD Contribuições | Nome cadastrado, vinculado aos dois regimes | Mapear e validar o demonstrativo específico |
| Livro Fiscal — Registro de Entradas | Motor integrado | Revalidar empresa, período, documento e retorno |
| Livro Fiscal — Registro de Saídas | Motor integrado, com pendência na conferência do PDF | Resolver a conferência e validar o fluxo completo |
| Livro Fiscal de ICMS | Nome cadastrado, vinculado aos dois regimes | Confirmar o relatório/título exato no Domínio e configurar |

Demonstrativo EFD Contribuições não é a geração do arquivo EFD
Contribuições. Livro Fiscal de ICMS também não é SPED Fiscal. As rotinas
novas são cadastros pendentes, sem navegação ou emissão presumida.

O preparo inicial acontece uma vez ao iniciar o servidor atualizado.
Novos cadastros ficam no banco local. Reiniciar não duplica nem restaura
sequências que o operador já editou. Regimes preexistentes preservam sua
configuração; o incremento ICMS acrescenta esse vínculo aos dois regimes.
Nenhuma empresa ou código real foi inventado ou importado.

## Fluxo de trabalho

1. Cadastrar empresa, código no Domínio e regime.
2. Cadastrar os nomes das rotinas e definir sua ordem dentro do regime.
3. Configurar cada rotina individualmente: passos, parâmetros e resultado esperado.
4. Revisar e executar um teste supervisionado em uma empresa e competência fechada.
5. Encaminhar à validação do supervisor, com evidência do resultado.
6. Aprovar uma versão identificada e liberar essa versão no executor.
7. Executar todas as rotinas da empresa antes de passar à próxima.

Nesta entrega, o cadastro permite **Pendente de configuração → Rascunho →
Aguardando validação**. Salvar alterações devolve a rotina a rascunho.
A tabela mostra os regimes vinculados e as pendências. A mesma rotina
vinculada a vários regimes compartilha a configuração; variações precisam
de cadastros próprios, com nomes distintos.

O envio atual registra uma pendência no painel. A decisão formal do
supervisor, identificação do aprovador, evidências, versionamento e
promoção ao executor ainda precisam ser implementados. Os roteiros
desse novo cadastro ficam no SQLite; o gravador local existente continua
com suas definições JSON e aprovação local. Falta ligar a validação
formal e esses roteiros ao executor comum. Rotinas novas pendentes ou
enviadas à validação continuam bloqueadas para emissão remota.

## Regra de falha e recuperação

Uma falha de emissão fica registrada na rotina. O executor tenta
recuperar a sessão até o painel azul e, quando confirma a recuperação
e a empresa, segue para a próxima rotina, sem repetir a emissão falha.

A implementação reutiliza o fechamento por Esc na janela do Domínio
reconhecida, uma ação por vez, até cinco tentativas, conferindo o retorno
antes da próxima ação. Para imediatamente ao reconhecer a tela azul.
Os fechamentos de OK/Fechar já existentes nas rotinas são preservados;
diálogos que precisem de tratamento adicional devem ser mapeados no teste
real. Não há clique genérico em OK nem encerramento indiscriminado de
processos. Reinício de ciclo não significa reiniciar Windows/servidor.

Se terminar a sequência com falhas recuperadas, o lote aparece como
**Finalizado com falhas — revisar pendências**. A emissão falha continua
falha no histórico. Recuperação não confirmada, empresa divergente,
cancelamento ou reinício interrompem a sequência. Reiniciar o servidor
preserva as pendências e não reexecuta emissões automaticamente.

## Etapas até a conclusão do piloto

| Etapa | Entrega | Responsável proposto | Critério para avançar |
| --- | --- | --- | --- |
| 1. Preparar cadastros e ambiente | Regimes, cinco indicadores, empresas/códigos, servidor acessível e tela calibrada | Desenvolvimento + administrador | Cadastros conferidos; instalação e acesso no Windows funcionando |
| 2. Configurar as novas rotinas | Resumo, demonstrativo e ICMS com parâmetros e verificações | Desenvolvimento + supervisor fiscal | Cada roteiro revisado contra as telas reais e testável individualmente |
| 3. Completar a validação | Fila de revisão, aprovador, evidências, versão e liberação no executor | Desenvolvimento + supervisores | Rotina aprovada somente após conferir documento; edição exige nova revisão |
| 4. Homologar individualmente | Cinco rotinas corretas numa empresa de Lucro Presumido | Supervisor + operador | Empresa, período, conteúdo, destino e retorno confirmados; PDF de Saídas resolvido |
| 5. Homologar o lote e a recuperação | Duas empresas de Lucro Presumido, uma rotina falhando de forma controlada | Desenvolvimento + supervisor | Falha registrada, tela azul/empresa confirmadas, próxima rotina executada sem repetição |
| 6. Concluir o piloto operacional | Equipe treinada, manual, backup/restauração e painel de pendências | Administrador + supervisor | Ciclo fiscal acompanhado aceito, responsáveis definidos e recuperação demonstrada |
| 7. Expandir para Lucro Real | Mesmos indicadores, com diferenças fiscais/configurações revisadas | Supervisor fiscal + desenvolvimento | Homologação específica de Lucro Real aprovada |

Preparar o ambiente pode ocorrer junto da configuração. A homologação
individual precede o lote. Não é possível fixar uma data final somente
pelo código: o prazo depende do mapeamento das três rotinas novas, da
disponibilidade da sessão Windows e da aprovação fiscal. Planejar as
datas com os responsáveis ao concluir a primeira etapa.

## O que a administração e a supervisão precisam fornecer

- Administrador: PC/sessão Windows de execução, acesso de rede, instalação
  do Domínio no servidor escolhido, responsável por atualização e backup.
- Supervisor: empresas/códigos autorizados de Lucro Presumido, competência
  fechada, relatórios de referência e critérios de conferência de cada indicador.
- Operador: gravação/mapeamento das telas novas, testes acompanhados e
  registro de falhas, sem alterar cadastros fiscais durante a execução.
- Desenvolvimento: implementar a ligação dos roteiros ao executor,
  versionamento/aprovação e tratamento dos diálogos observados nos testes.

O acesso atual usa chave compartilhada; contas individuais, permissões
por papel e autoria verificável de aprovação são trabalho pendente.

## Quando consideraremos concluído

O piloto de Lucro Presumido estará concluído quando as cinco rotinas
estiverem homologadas, o lote cumprir a ordem prevista, os arquivos forem
conferidos e uma falha controlada mostrar recuperação e continuação
corretas. A equipe deverá conseguir executar, acompanhar e resolver as
pendências, com aprovação do supervisor e procedimento de backup/restauração.

Lucro Real, agendamento, métricas de desempenho e agentes operadores são
entregas posteriores. O projeto ampliado estará concluído quando cada
uma tiver seu próprio aceite. O escopo atual de operação fiscal é
geração/leitura de períodos fechados; apuração automática, transmissão,
retificação e exclusão exigem definição e validação específicas.

## Base e limites da análise

Foram examinados README, histórico técnico, HANDOFF, RETOMADA,
ROADMAP-RPA, painel web, catálogo, cadastro de lotes, gravador, API,
worker, executor e testes existentes. Fontes principais:

- `app/configuracao_lotes.py`, `app/configuracao_rotinas.py` e `app/capacidades.py`;
- `app/servidor.py`, `app/executor_servidor.py` e `app/api_servidor.py`;
- `app/rotina_gravada.py`, `scripts/gui.py`, `scripts/servidor.py` e `web/`;
- `docs/HANDOFF.md`, `docs/RETOMADA.md`, `docs/ROADMAP-RPA.md` e
  `docs/00-analise-e-plano-fase0.md`.

Os testes desta entrega são de lógica/API e navegador com fiscal/login
simulados. Eles não operam a sessão Windows do escritório, não configuram
as telas das rotinas novas e não conferem documentos fiscais reais.

Verificação desta entrega: **331 testes de lógica/API passaram**. O teste
Chromium verifica cadastro, configuração, envio para validação, lotes,
falha com recuperação simulada, continuidade, controles, três larguras,
logout e offline. A homologação dos cinco indicadores no Windows continua
pendente.
