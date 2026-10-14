# Testar o Presumido por empresa e depois em lote

Atualização: 13/10/2026. Agosto/2026 foi confirmado fechado pelo operador
somente para a empresa do primeiro teste. Setembro/2026 foi informado
aberto. A confirmação precisa ser feita para cada empresa/competência.

## Primeiro: os três Livros Fiscais

1. Atualizar a main, fechar/reabrir o servidor e recarregar o painel com Ctrl+F5.
2. Em **Lucro Presumido por empresa**, escolher empresa e agosto/2026.
3. Clicar **Preparar teste dos três Livros Fiscais**. Isso só prepara o
   formulário **Nova execução**; não emite nada.
4. Conferir rotina **Livros Fiscais — Entradas, Saídas e ICMS**, código e
   competência. Confirmar apuração fechada e clicar **Executar no servidor**.
5. Deixar Domínio visível no servidor e não usar mouse/teclado durante a
   execução. O executor usa F8 se necessário e confirma código/painel azul.
6. Em **Acompanhar execução**, conferir as etapas e os três botões de
   download. Abrir os três PDFs: Entradas, Saídas e ICMS; conferir empresa,
   período e valores com o supervisor. Só então testar a sequência inteira.

**Conferir formulário dos três livros** é um diagnóstico sem emissão;
requer a aba Geral aberta. É diferente do botão para preparar a execução.
Se faltar caixa/data/unidade/pasta ou houver ambiguidade, não confirma OK.
Consulte a etapa com falha e a captura local em capturas/.

## Depois: sequência completa da empresa

No início do painel, escolher empresa e competência em **Lucro Presumido
por empresa**. Conferir a lista e confirmar a apuração; clicar
**Executar sequência nesta empresa** uma vez. A sequência inicial agora
contém três rotinas integradas:

1. Resumo por Acumulador, PDF.
2. EFD Contribuições, exportador existente. Ainda não é um demonstrativo PDF.
3. Livros Fiscais, três PDFs separados de Entradas, Saídas e ICMS.

A migração substitui o vínculo antigo da conjunta pelo gerador nativo,
preservando a ordem e escolhas do regime. Não repõe rotinas retiradas.
Se o operador acrescentou rotinas custom pendentes, elas continuam
bloqueadas; teste parcial só com a opção explícita. Pendência não é emissão.

Os resultados ficam na tabela do lote por empresa. **Ver etapas** abre o
histórico da rotina e seus arquivos. **Baixar diagnóstico das etapas**
guarda JSON local com resultados, motivos, tempos e retorno, sem caminhos,
PDF ou texto livre de OCR. Não é homologação fiscal.

Falhas permanecem no histórico. A próxima rotina só começa após retorno
confirmado ao painel azul; sem retorno, a sequência é interrompida.
Reenvio do mesmo pedido não repete emissão. Reiniciar não retoma tarefas.

## Onde ficam os arquivos

Livros são exportados primeiro para staging exclusivo em saida/. Ao final,
cada PDF confirmado vai ao destino cadastrado da empresa, com nome e
competência. Configuração padrão: FISCAL/mês/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS.
Sem raiz configurada, permanecem na saída local. **Ver destino** mostra a
previsão sem gravar; **Testar pasta** testa gravação sem emitir documento.

Os três downloads usam os arquivos exatos registrados pela tarefa. Um
livro recusado não é disponibilizado como válido. PDFs confirmados podem
continuar disponíveis mesmo quando outro livro ou o retorno falhar.
Não sobrescreve arquivos de execuções anteriores.

## Alternativa pelo CMD, com servidor parado

```bat
cd /d C:\Users\darto\dominio-automation-engine
python scripts\testar_livros_fiscais.py
```

O script pede código, competência e confirmação de apuração, usa o mesmo
worker/trava e troca empresa. O atalho Testar Livros Fiscais faz o mesmo.
Não rodar junto com o servidor. Para a sequência completa:

```bat
python scripts\explorar_presumido.py
```

Sem --somente-disponiveis, sequência custom pendente fica bloqueada.
Somente competências fechadas, escolhidas pelo operador; o calendário
sozinho não confirma apuração. Primeiro individual, depois lote do Presumido.

## Diagnóstico da atualização de 14/10/2026

O teste real anterior falhou na abertura dos livros e no período do Resumo.
A seleção dos livros agora é lida antes das datas; o OCR tenta ampliação e
preto e branco. Recortes de datas que falham ficam locais em capturas/.

Se persistir, abra somente o formulário correspondente no Domínio e rode
o diagnóstico abaixo no CMD. Volte ao formulário nos cinco segundos;
os comandos só leem a tela, sem alterar campos ou emitir:

```bat
python scripts\revisar_periodo_resumo.py
```

Para Livros, abra Relatórios → Livros → Livros Fiscais, aba Geral:

```bat
python scripts\revisar_formulario_livros.py
```

Compartilhar apenas as linhas limitadas RESUMO_RECORTE/LIVROS_SELECAO/
LIVROS_PERIODO e mensagens finais, sem capturas com dados fiscais.
