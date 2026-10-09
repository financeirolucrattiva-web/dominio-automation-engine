# Livros Fiscais: Entradas, Saídas e ICMS na mesma emissão

Mapeamento de 09/10/2026 a partir das telas e instruções do operador.
Este documento registra o fluxo para implementação e teste individual.
A emissão conjunta ainda não está implementada nem homologada no motor.
Os cadastros existentes e seus estados de validação permanecem vigentes.

**Escopo confirmado:** esquema recebido de **Lucro Presumido**
e **Lucro Real**, integrado em [ARQUITETURA-SERVIDOR.md](ARQUITETURA-SERVIDOR.md).
Destino padrão escolhido: `FISCAL\MM\RELATORIOS_APURAÇÃO\LIVROS_FISCAIS`,
com possibilidade de configurar outra subpasta por empresa no painel.
Primeiro teste individual e piloto no Lucro Presumido;
homologar Lucro Real depois. Outros caminhos/regimes serão acrescentados
futuramente, sem presumir sua estrutura agora. Cada destino deve ser
associado explicitamente ao regime cadastrado, evitando misturar saídas.

## Sequência observada

1. Partir do painel azul, com a empresa conferida e período passado apurado.
2. Abrir **Relatórios → Livros → Livros Fiscais**. Livros abre por hover;
   Livros Fiscais abre o formulário com a aba Geral.
3. Conferir selecionados **Registro de Entradas**, **Registro de Saídas**
   e **Registro de ICMS**. Na captura os três já estão marcados: clicar
   indiscriminadamente desmarcaria opções. É necessário ler e confirmar
   o estado das caixas antes e depois de qualquer alteração.
4. Preencher **Inicial** e **Final** com as datas completas solicitadas;
   reler e confirmar os dois campos.
5. Clicar no **OK** à direita. Aguardar o processamento por estado,
   sem considerar “Processando, Aguarde...” como emissão concluída.
6. A primeira prévia pode ser qualquer livro. A captura mostra Entradas;
   o operador confirmou que a ordem não deve ser fixada nesse relatório.
7. Clicar no ícone **PDF** da barra lateral da prévia. O menu observado
   oferece **Gerar em único arquivo PDF** e **Gerar um arquivo PDF para
   cada relatório**.
8. Escolher **Gerar um arquivo PDF para cada relatório**.
9. Abre **Procurar Pasta**, com seletor **Unidade** e árvore de pastas.
   A primeira tela mostra Servidor (C:); a seguinte mostra **Client C (M:)**.
   É um seletor de pasta, distinto do diálogo Salvar em PDF usado pelo
   gerador individual antigo. Não digitar nome de arquivo nesse diálogo.
10. Selecionar a pasta de destino do computador cliente e confirmar no
    **OK** desse diálogo. O operador informou navegação para a pasta do
    usuário/Dropbox. O destino completo agora pode ser conferido no painel;
    o modo de navegar a árvore ainda precisa de teste no ambiente.
11. Conferir os arquivos novos produzidos: conteúdo de cada livro,
    empresa, período e resultado individual. Os nomes e o comportamento
    do exportador após a confirmação da pasta ainda não foram observados.
12. Aplicar o nome cadastrado da empresa aos PDFs confirmados, preservando
    anteriores, e fechar as prévias/formulários até reconhecer o painel azul.

## Caminho local e caminho visto pelo Domínio

O projeto já possui `app.dominio.caminho_visto_pela_sessao_remota()`.
O histórico da seção 0.59 confirmou que o C: local aparece como Client C
na sessão GO-Global, com letra M: nessa instalação. A letra pode ser
configurada em `data/unidade_cliente.txt`; a árvore restante é preservada.

Exemplo ilustrativo, sem representar o destino do escritório:

- Caminho usado pelo Python local: `C:\Users\<usuario>\Dropbox\<destino>`.
- Caminho equivalente visto pelo Domínio: `M:\Users\<usuario>\Dropbox\<destino>`.

**Servidor (C:)** no diálogo é o disco do ambiente remoto do Domínio.
**Client C (M:)** é o disco local exposto à sessão. Confirmar ambos os
caminhos antes de integrar. Usuário, raiz Dropbox e destino devem ser
configurações locais da instalação, sem fixar dados pessoais no código.
Salvar na pasta local sincronizada usa o sistema de arquivos; não requer
integração com a API do Dropbox.

## Configuração e teste do destino

1. No PC executor, usar **Configurar Destino Livros.bat** para informar
   a raiz local em C: que contém os regimes/empresas. Salva em
   `data/destino_livros.json`, ignorado pelo Git.
2. No cadastro da empresa, informar a pasta relativa dentro da raiz;
   vazia, procurar o código no CSV local. Escolher o regime explicitamente.
3. Deixar a subpasta vazia para o padrão escolhido, ou personalizar dentro
   de `FISCAL/mês`. Salvar e usar **Editar** na lista.
4. Escolher competência passada e **Ver destino**: exibe caminho completo
   local, equivalente no Domínio e nomes previstos, sem criar nada.
5. **Testar pasta**: cria o destino se necessário, grava e remove um
   temporário, sem emissão fiscal. Conferir a pasta no Explorador do PC.

O resolvedor usa a pasta de ano existente, ou `FISCAL` diretamente na
empresa quando não há pasta de ano. Não inventa raiz/empresa/estrutura
FISCAL nem escolhe pasta por semelhança de nome. Presumido e Real
compartilham a pasta principal; o regime vem do cadastro.

Ao final dos geradores individuais integrados, Entradas/Saídas confirmados
são copiados para o destino da empresa com o nome cadastrado e competência.
Colisões usam sufixo; falha de cópia remove parcial e preserva a origem.
O download aceita somente o arquivo final registrado naquela tarefa,
além da saída local existente. Use um mês por emissão no destino mensal.
Isso não implementa a geração conjunta nem valida o conteúdo de ICMS.

## Esquema recebido e informações ainda necessárias

O esquema geral pode ser documentado em `docs/ARQUITETURA-SERVIDOR.md`:

- Em qual computador roda o executor e onde roda o cliente Domínio/GO-Global.
- Quais pastas o processo Python pode acessar localmente e suas equivalentes
  visíveis na sessão do Domínio; como configurar a unidade Client C.
- Organização esperada da saída: empresa, regime, competência e tipo de
  relatório; como conferir permissão de gravação e acesso pelo painel.
- Caminhos de Lucro Presumido e Lucro Real nesta etapa, com indicação das
  diferenças entre suas pastas. Outros caminhos serão adicionados depois.
- Forma de escolher o destino na tela Procurar Pasta e o estado da tela
  depois de confirmar: arquivos criados, nomes automáticos e prévias abertas.

Caminhos pessoais exatos devem ficar na configuração local ignorada pelo
Git. O esquema público usa exemplos genéricos, sem dados de clientes,
credenciais, tokens ou documentos fiscais. A navegação no seletor da
exportação conjunta e os arquivos gerados ainda precisam ser observados.

## Integração e teste pendentes

- Localizar e conferir o estado das três caixas com evidência visual.
- Localizar o menu de exportação e selecionar a opção observada.
- Navegar no seletor de pasta com o destino configurado, sem supor um
  campo de caminho que não aparece nas capturas.
- Usar uma pasta exclusiva por tentativa para distinguir arquivos novos
  de exportações antigas. Identificar cada PDF pelo conteúdo, sem depender
  da ordem de abertura nem dos nomes automáticos do Domínio.
- Conferir o título e o período do PDF de ICMS real, ainda não apresentados,
  antes de definir sua validação de conteúdo.
- Guardar três resultados/arquivos na mesma execução. O servidor atual
  aceita um único caminho por tarefa: adaptar persistência, download e
  painel para múltiplos arquivos antes de habilitar a emissão conjunta.
- Evitar emitir Entradas/Saídas novamente no mesmo lote caso o operador
  substitua as rotinas separadas pela conjunta. Preservar os históricos.
- Se um documento falhar, guardar os demais resultados confirmados;
  recuperar até o painel azul e continuar a próxima rotina quando a
  recuperação estiver confirmada, conforme a política existente.
- Homologar primeiro uma empresa de Lucro Presumido em competência passada
  apurada; conferir documentos, destino, nomes, fechamento e recuperação.

Não há log de execução automatizada dessa emissão conjunta. As imagens
enviadas no chat não foram copiadas para o repositório nem medidas por OCR
nesta sessão; nenhum novo offset de clique foi calibrado a partir delas.

A nova captura de Salvar em PDF do Resumo mostra arquivos anteriores de
ICMS NORMAL (M), Livro de Entrada e Livro de Saída com prefixo de agosto
de 2026 na mesma pasta `saida/`. Isso identifica nomes automáticos, sem
confirmar o conteúdo/título do PDF de ICMS ou uma execução automatizada.
