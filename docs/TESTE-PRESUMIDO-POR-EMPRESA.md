# Testar o Presumido por empresa e depois em lote

Referência: 13/10/2026. O operador confirmou agosto/2026 fechado para a
empresa do primeiro teste. Essa confirmação não vale automaticamente para
outras empresas. Setembro/2026 foi informado aberto e não deve ser usado
nesse piloto sem nova confirmação.

## O que já pode ser testado

O painel tem **Lucro Presumido por empresa** no início da página. A
execução usa o mesmo worker, troca por F8, histórico, pausa e recuperação
dos lotes. Um pedido cria as rotinas disponíveis dessa empresa na ordem
cadastrada. Não altera o regime nem habilita roteiros pendentes.

Na configuração inicial, são executáveis Resumo por Acumulador e a
exportação existente da EFD Contribuições. Livros Fiscais — Entradas,
Saídas e ICMS permanece pendente de integração. Enquanto essa pendência
existir, o teste é **parcial**; não é execução das três rotinas completas.
A EFD atual não entrega um demonstrativo PDF validado.

1. Atualizar a main, reiniciar o servidor Windows e usar Ctrl+F5.
2. Escolher a empresa cadastrada no Presumido e a competência fechada.
3. Conferir a sequência exibida. A consulta acontece ao preencher os
   campos; Revisar sequência permite renovar a revisão.
4. Havendo pendências, marcar **testar somente as disponíveis** para
   testar a parte integrada. Sem essa opção, o botão não emite.
5. Confirmar apuração fechada, deixar o Domínio disponível no servidor
   e clicar **Executar sequência nesta empresa** uma vez.
6. Acompanhar os resultados do lote, **Ver etapas** e os arquivos locais.
   **Baixar diagnóstico das etapas** salva um JSON com resultados,
   motivos, tempos e retorno, sem caminhos, PDF ou texto livre de OCR.
7. Conferir valores fiscais com o supervisor. O relatório não é homologação.

Rotinas pendentes aparecem como **Não executada · integração pendente**.
Se todas as disponíveis terminarem, o teste parcial fica
concluida_com_pendencias, nunca concluida. Falhas têm prioridade no estado
final e mantêm as pendências no relatório. A próxima rotina só começa
quando a recuperação até o painel azul estiver confirmada. Sem isso,
o restante é interrompido. Repetir o mesmo pedido não emite novamente;
reiniciar o servidor não retoma tarefas interrompidas.

## Primeiro passo para completar os três livros

O painel também tem **Testar Livros Fiscais → Conferir formulário dos
três livros**. Abrir no servidor Relatórios → Livros → Livros Fiscais,
aba Geral, e usar esse botão. A leitura recebe a mesma exclusividade
do worker: não roda durante emissão, login ou outro diagnóstico.

Mostra estados, datas, medidas e outras opções marcadas. Não seleciona
caixas, preenche datas ou clica OK. A captura permanece no PC em capturas/;
a API entrega somente o resumo limitado. Falha/cancelamento/novo pedido
limpam resultados antigos. Não habilita automaticamente a emissão.

Alternativa no CMD da pasta do projeto:

```bat
python scripts\revisar_formulario_livros.py
```

Voltar ao formulário nos cinco segundos seguintes e enviar só o resumo
do terminal. O log real dessa leitura é necessário antes de ligar os
cliques. Ainda faltam navegação confirmada em Procurar Pasta, título de
ICMS e geração/conferência/publicação de três arquivos na mesma tarefa.

## Testar mais empresas depois

Em **Executar lote por empresas**, filtrar Lucro Presumido, selecionar
as empresas e o período. Para testar somente as disponíveis sem mudar
o regime, marcar a opção de teste acompanhado do Presumido e revisar.
A revisão mostra explicitamente as pendências que não serão executadas.
Confirmar apuração em todas as empresas e iniciar. A fila termina a
sequência de uma empresa antes da próxima. Outros regimes são recusados
nesse modo. O lote comum permanece estrito e bloqueia rotinas pendentes.

## Teste individual pelo terminal

Com o servidor parado, empresa cadastrada e Domínio visível:

```bat
python scripts\explorar_presumido.py --empresa CODIGO_CADASTRADO --competencia 2026-08 --apuracao-confirmada --somente-disponiveis
```

Use apenas quando a competência estiver fechada nessa empresa. O script
usa o banco e a trava reais, mostra as pendências e aguarda cinco segundos
para colocar o Domínio no painel azul. Quando o teste chega ao fim, código de saída 0 = sequência
cadastrada concluída, 2 = disponíveis concluídas com pendências,
1 = falha/interrupção. Sem --somente-disponiveis, recusa um teste completo
que contenha rotinas sem executor. Não substitui emissão por sucesso.

## Validação desta entrega

Worker/SQLite/API e navegador foram testados com empresas, imagens e
geradores sintéticos. Cobrem leitura/cancelamento, isolamento de dados,
identificador repetido, cadastro modificado após revisão, execução por
empresa e lote, falha com/sem recuperação, relatório e digitação de datas.
Ainda não há log de diagnóstico/emissão dessa versão no Windows real.
