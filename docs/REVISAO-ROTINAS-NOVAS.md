# Revisão das rotinas novas

Referência: 13/10/2026. Primeiro piloto: uma empresa de Lucro Presumido,
em competência passada cuja apuração esteja fechada. Lucro Real será
testado depois da aceitação desse piloto.

| Rotina | O que existe hoje | O que falta confirmar |
| --- | --- | --- |
| Livros Fiscais — Entradas, Saídas e ICMS | Cadastro conjunto nos regimes que continham os três livros; roteiro observado nas telas | Leitura das caixas, navegação em Procurar Pasta, título/conteúdo do ICMS e três arquivos por tarefa |
| Resumo por Acumulador | Gerador integrado; abertura do submenu corrigida | Repetir teste no Windows até confirmar PDF e retorno ao painel azul |
| Demonstrativo EFD Contribuições | Nome associado ao exportador existente da EFD | Confirmar se o resultado desejado é a exportação existente ou um demonstrativo em PDF |

## Passos comuns

1. Selecionar empresa cadastrada, código no Domínio e competência fechada.
2. Conferir o código visível. Se for diferente, usar F8 e trocar; reler o
   código e reconhecer o painel azul antes de começar a emissão.
3. Emitir somente a rotina escolhida. Uma rotina pendente no cadastro
   não está liberada para execução pelo painel.
4. Conferir documento novo, empresa, período e destino. Conferência de
   identidade/período não substitui a revisão dos valores pelo supervisor.
5. Encerrar as telas até reconhecer o painel azul. Em caso de falha,
   registrar o motivo e recuperar a interface; a próxima rotina do lote
   só começa quando o retorno ao início estiver confirmado.

## Livros Fiscais — emissão conjunta a configurar

Nova captura da aba Geral em 13/10 mostra os três livros desmarcados.
O [diagnóstico local](DIAGNOSTICO-FORMULARIO-LIVROS.md) lê estados e datas
sem alterar controles ou emitir. O operador informou setembro ainda não
fechado; escolher uma competência apurada antes do teste de emissão.

1. Relatórios → Livros → Livros Fiscais, aba Geral.
2. Conferir Registro de Entradas, Registro de Saídas e Registro de ICMS
   selecionados. Ler o estado antes de clicar: a captura fornecida já
   de 09/10 mostra os três marcados, mas a de 13/10 mostra desmarcados.
   Conferir que outros livros não serão emitidos.
3. Preencher Inicial e Final com as datas completas e reler os dois campos.
4. Clicar OK à direita e aguardar a prévia. A primeira prévia pode ser
   qualquer um dos livros; Processando, Aguarde não comprova conclusão.
5. Ícone PDF → Gerar um arquivo PDF para cada relatório.
6. No diálogo Procurar Pasta, selecionar Client C na unidade configurada
   da sessão (M: na instalação mostrada) e navegar até a pasta de saída.
   Essa tela tem uma árvore; não foi observado campo para digitar um
   caminho inteiro. A navegação automática ainda precisa ser confirmada.
7. Confirmar o OK do seletor e conferir os três PDFs novos. Os nomes
   automáticos observados são Livro de Entrada, Livro de Saída e ICMS
   NORMAL (M); isso não confirma o título escrito dentro do PDF de ICMS.
8. Após conferir os documentos, publicar no destino da empresa. Padrão
   escolhido: FISCAL → mês → RELATORIOS_APURAÇÃO → LIVROS_FISCAIS.
   Usar o nome cadastrado e a competência; preservar emissões anteriores.
9. Fechar prévias/formulário e confirmar o painel azul.

O cadastro agrupa a sequência completa dos três livros de Presumido/Real
no lugar do primeiro livro, preservando a ordem das demais rotinas.
Sequências incompletas e outros regimes permanecem como o operador deixou.
Entradas/Saídas continuam disponíveis no catálogo para testes individuais.
O roteiro antigo de ICMS é arquivado somente se nenhum regime o utiliza.
Configurações, empresas e históricos não são promovidos nem apagados.

A conjunta permanece **pendente de configuração**. Salvar passos como
rascunho ou enviar para validação não habilita sua execução remota.
Será necessário adaptar o gerador, persistência e downloads para os três
arquivos antes do teste automatizado completo. Não executar o lote inteiro
para testar um cadastro pendente. Detalhes em LIVROS-FISCAIS-CONJUNTOS.md.

O painel agora permite um **teste parcial explícito do Presumido por
empresa**: roda somente as integradas, registra a conjunta como não
executada e não muda a sequência do regime. Isso permite diagnosticar
Resumo/EFD enquanto a conjunta é concluída; não representa o lote inteiro.
Guia em TESTE-PRESUMIDO-POR-EMPRESA.md. Agosto/2026 foi confirmado fechado
para a empresa do primeiro teste; diagnóstico/emissão real ainda pendentes.

## Resumo por Acumulador — roteiro implementado para revalidar

1. Relatórios → Acompanhamentos → Resumo por Acumulador.
2. Preencher Data inicial/Data final e conferir os valores. Preservar
   a opção Destacar linhas como o operador deixou.
3. OK → aguardar prévia RESUMO POR ACUMULADOR. Conferir empresa/período.
4. Ícone PDF → Salvar em PDF. Esse é um diálogo de arquivo, diferente
   do seletor de pasta da emissão conjunta dos livros.
5. Salvar, conferir o PDF e aplicar o nome cadastrado da empresa.
   Destino atual: saida/ do projeto; o arquivo fica disponível no painel.
6. Fechar até confirmar o painel azul.

Teste individual pelo painel, ou pelo atalho Testar Resumo por Acumulador
com o servidor parado. Não repetir emissão enquanto outra tarefa estiver
ativa. A falha anterior foi informada na etapa de abertura; ainda falta
um log Windows da versão corrigida. Veja RESUMO-POR-ACUMULADOR.md.

## Demonstrativo EFD Contribuições — confirmar o produto esperado

O usuário pediu reutilizar/renomear a rotina existente. A revisão encontrou
que gerar_efd_contribuicoes usa Relatórios → Informativos → Federais →
item de Contribuições, com a competência, geração e fechamento da exportação.
Essa função devolve um booleano; não retorna nem valida um demonstrativo PDF.

Se o resultado esperado continuar sendo essa exportação, revisar o destino
configurado no Domínio, competência, confirmação e arquivo efetivamente novo.
Se for um PDF de demonstração, confirmar o menu/formulário/resultado dessa
opção antes de implementar. O nome na lista não transforma o exportador
em gerador de PDF. O executor existente foi preservado nesta revisão.

## Ordem da revisão com o operador

1. Livros: confirmar navegação do seletor e título interno do ICMS.
2. Implementar e testar a emissão conjunta individualmente; conferir os
   três documentos, nomes, destino e recuperação em caso de falha.
3. Repetir Resumo individual e localizar a etapa exata se falhar.
4. Confirmar e testar o resultado esperado da EFD Contribuições.
5. Somente após aceitar os resultados individuais, testar o lote de uma
   empresa de Lucro Presumido; expandir para mais empresas e Lucro Real.

Nenhuma emissão fiscal nova foi executada nesta revisão em nuvem.
