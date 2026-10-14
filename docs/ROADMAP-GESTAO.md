# Roadmap de gestão — Domínio Automation Engine

**Referência:** 14/10/2026 · **Empresa:** Lucrattiva Contabilidade

**Público:** administradores, supervisores e equipe fiscal
**Base analisada:** repositório `financeirolucrattiva-web/dominio-automation-engine`,
main `5784126` e revisão das três rotinas nesta entrega. Código e testes
validados neste ambiente; emissão e aceite fiscal dependem do Windows do
escritório.

## Revisão e teste de 14/10/2026

O último log confirmou as datas do Resumo e bloqueou a prévia ao reconhecer
OK. Nos Livros, o operador relatou marcação apenas de Entradas. A EFD
sinalizou geração, mas o operador interrompeu enquanto ela aguardava;
essa interrupção não comprova falha fiscal.

A revisão limita esperas de OCR, reforça leitura dos botões medidos,
aguarda as três marcações sem repetir cliques e confere a saída do aviso
EFD. A sequência por empresa tem novo atalho com etapas/progresso no
terminal. 615 testes automatizados e o navegador passaram com fiscal simulado;
próximo marco é a emissão real de agosto/2026 na empresa confirmada.
O piloto permanece em validação.

## Situação atual

A base técnica está implementada: cadastro empresa/código/regime, painel,
execução individual/lote, fila exclusiva, histórico, etapas, pausa e
recuperação. A prioridade é homologar **Lucro Presumido por empresa** e
só depois ampliar para lotes e Lucro Real. Não há percentual confiável:
código entregue e documento fiscal aprovado têm critérios diferentes.

Na atualização de 13/10/2026, os três Livros Fiscais foram integrados numa
única emissão com três arquivos/downloads. A limpeza final publicada pelo
Claude foi incorporada. Falhas reais de leitura do Resumo motivaram leitura
por recortes e novas verificações. A geração EFD foi sinalizada, mas seu encerramento ainda precisa
de nova conferência no Windows. Os testes em
nuvem não operam o Domínio do escritório nem homologam valores fiscais.

| Ordem | Entrega | Estado | Critério para avançar |
| --- | --- | --- | --- |
| 1 | Livros juntos: Entradas, Saídas e ICMS | Código integrado para teste individual | Três PDFs corretos de agosto/2026 na empresa confirmada, destino e retorno azul conferidos |
| 2 | Resumo por Acumulador | Leitura corrigida a partir do diagnóstico; precisa de novo teste Windows | Datas mudam para a competência pedida e PDF confirma empresa/período/valores |
| 3 | EFD Contribuições | Exportador existente; geração sinalizada, ciclo interrompido | Conferir arquivo e encerramento seguro; definir aceite do produto esperado |
| 4 | Presumido inteiro por empresa | Um envio executa a sequência nativa cadastrada | Supervisor aprova cada documento e uma falha controlada mantém histórico/continuidade segura |
| 5 | Lote do Presumido | Mesmo worker, uma empresa por vez | Repetir em poucas empresas fechadas, sem troca incorreta, duplicação ou arquivo no destino errado |
| 6 | Operação assistida e Lucro Real | Depois do aceite do Presumido | Procedimento/backup/responsáveis definidos e novo aceite para Real |

## Escopo decidido para o piloto

Os regimes preparados são **Lucro Presumido** e **Lucro Real**. O primeiro
piloto será exclusivamente no **Lucro Presumido**; Lucro Real entra depois
da aceitação do primeiro piloto.

| Indicador/rotina | Situação de partida | Próximo trabalho |
| --- | --- | --- |
| Resumo por Acumulador | Gerador integrado para teste individual; cadastro vinculado aos dois regimes | Testar OCR/exportação no Windows e homologar o documento |
| Demonstrativo EFD Contribuições | Nome vinculado ao exportador da EFD existente | Confirmar se o produto esperado é essa exportação ou um demonstrativo PDF |
| Livros Fiscais — Entradas, Saídas e ICMS | Gerador conjunto integrado; três PDFs/downloads | Testar seletor, conteúdo ICMS, destino e recuperação no Windows |
| Registro de Entradas / Registro de Saídas individuais | Geradores continuam disponíveis; ainda requerem revalidação | Testar individualmente; evitar emissão duplicada no futuro lote conjunto |

O escritório confirmou que Demonstrativo EFD Contribuições é a mesma
rotina EFD já existente. O motor é reutilizado e o nome de exibição foi
ajustado; o cadastro pendente duplicado foi substituído nos regimes,
arquivando sua configuração anterior no banco local. A revisão de 13/10
confirmou que o gerador atual é de exportação, não um demonstrativo PDF;
o resultado esperado será revisto com o operador. Livro Fiscal de ICMS
integra o cadastro conjunto e continua distinto de SPED Fiscal. Resumo tem
implementação baseada nas telas fornecidas; aguarda execução real e
homologação. Estar integrado não significa aprovação do supervisor.

O [roteiro de revisão](REVISAO-ROTINAS-NOVAS.md) registra os passos
observados, o fluxo implementado e as confirmações que faltam antes do
piloto. A conjunta inicial já é executável; rotinas custom ainda pendentes
continuam bloqueando o lote completo.

O painel oferece teste dos três livros sozinho e sequência Presumido por
empresa em um envio. O relatório preserva falhas, tempos, retorno e
arquivos confirmados. Com roteiros custom pendentes, só é permitido teste
parcial explícito. Agosto/2026 foi confirmado fechado para a primeira
empresa; não estender essa confirmação a outras empresas.

O preparo inicial acontece uma vez ao iniciar o servidor atualizado.
Novos cadastros ficam no banco local. Reiniciar não duplica nem restaura
sequências que o operador já editou. Regimes preexistentes preservam sua
configuração; o incremento ICMS acrescenta esse vínculo aos dois regimes.
Nenhuma empresa ou código real foi inventado ou importado.

Para vincular empresas: abrir **Empresas, regimes e rotinas do lote**,
preencher **Código no Domínio**, **Nome da empresa**, escolher o **Regime**
e clicar em **Salvar empresa**. A sequência vem do regime escolhido.
Os PDFs confirmados emitidos pelo painel passam a usar o nome cadastrado,
por exemplo `registro_entradas_empresa_exemplo_2026-08.pdf`. No lote,
o nome é o que estava na revisão inicial. A competência vem do período
pedido. Nova emissão usa sufixo se já existir o arquivo, sem substituí-lo.
Resumo usa `acumulador_empresa_exemplo_2026-08.pdf`, em `saida/` nesta etapa.
O regime permanece no cadastro/histórico. EFD atualmente retorna somente
o resultado da geração, sem caminho local de arquivo para renomear.

O esquema de pastas foi recebido e o destino escolhido é
**FISCAL → mês → RELATORIOS_APURAÇÃO → LIVROS_FISCAIS**. O cadastro da
empresa permite escolher a pasta da empresa e personalizar a subpasta
dos livros. A raiz do Dropbox fica configurada somente no PC executor.
**Ver destino** mostra o caminho completo sem criar nada; **Testar pasta**
confere gravação com um temporário removido em seguida. O teste de pasta
não emite documento nem substitui a homologação fiscal.

Entradas/Saídas individuais e os três livros conjuntos são guardados
nesse destino ao final quando confirmados, preservando anteriores. Cada
download é vinculado ao arquivo exato daquela tarefa. A emissão conjunta
está integrada, com validação/download por livro; o seletor e o cabeçalho
ICMS ainda precisam do teste/homologação no Windows. O menu do Resumo foi
identificado como **Relatórios → Acompanhamentos → Resumo por Acumulador**;
formulário/período/OK/prévia/Salvar em PDF agora estão implementados para
teste individual. O executor confere datas/empresa/PDF e retorno à tela
principal; os valores fiscais precisam da conferência humana de referência.

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

O código cadastrado determina a empresa da execução. Individual e lote
usam F8 quando o Domínio estiver em outra empresa e confirmam novamente
o código antes de emitir. Código ilegível, troca não confirmada ou perda
de foco bloqueiam a emissão. Uma tela aberta no início pode ser fechada
até o painel azul calibrado antes de preparar a rotina. O foco da janela
é conferido nos checkpoints de mouse/teclado durante a execução.

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
| 2. Configurar e testar as novas rotinas | Resumo pronto para teste individual; integrar ICMS/conjunto | Desenvolvimento + supervisor fiscal | Roteiros revisados contra telas reais e teste individual observado |
| 3. Completar a validação | Fila de revisão, aprovador, evidências, versão e liberação no executor | Desenvolvimento + supervisores | Rotina aprovada somente após conferir documento; edição exige nova revisão |
| 4. Homologar individualmente | Cinco rotinas corretas numa empresa de Lucro Presumido | Supervisor + operador | Empresa, período, conteúdo, destino e retorno confirmados; PDF de Saídas resolvido |
| 5. Homologar o lote e a recuperação | Duas empresas de Lucro Presumido, uma rotina falhando de forma controlada | Desenvolvimento + supervisor | Falha registrada, tela azul/empresa confirmadas, próxima rotina executada sem repetição |
| 6. Concluir o piloto operacional | Equipe treinada, manual, backup/restauração e painel de pendências | Administrador + supervisor | Ciclo fiscal acompanhado aceito, responsáveis definidos e recuperação demonstrada |
| 7. Expandir para Lucro Real | Mesmos indicadores, com diferenças fiscais/configurações revisadas | Supervisor fiscal + desenvolvimento | Homologação específica de Lucro Real aprovada |

Preparar o ambiente pode ocorrer junto da configuração. A homologação
individual precede o lote. Não é possível fixar uma data final somente
pelo código: o prazo depende da integração de ICMS, do teste do Resumo, da
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

O piloto de Lucro Presumido estará concluído quando Resumo, EFD e os
três livros estiverem homologados, o lote cumprir a ordem prevista, os arquivos forem
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

Verificação técnica: testes de lógica, PDFs sintéticos, persistência, API e
navegador. O painel foi exercitado com sequência completa em um envio e
três downloads separados, além de falha com recuperação, modo parcial,
cadastro/destino, idempotência, três larguras e logout. A homologação
fiscal no Windows continua pendente e exige aceite do supervisor.
