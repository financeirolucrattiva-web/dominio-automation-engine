# Livros Fiscais: Entradas, Saídas e ICMS na mesma emissão

Mapeamento de 09/10/2026 a partir das telas e instruções do operador.
Este documento registra o fluxo para implementação e teste individual.
A emissão conjunta agora está integrada para teste; ainda não homologada
no Domínio real. O roteiro observado e seu histórico estão abaixo.

Revisão de 13/10/2026: o cadastro conjunto foi acrescentado. Nos regimes
Presumido/Real com a sequência completa, substitui os três vínculos pelo
cadastro Livros Fiscais — Entradas, Saídas e ICMS, na posição do primeiro
livro. Preserva sequências incompletas/outros regimes e não restaura
edições posteriores. O roteiro antigo de ICMS é arquivado quando deixa
de ser usado. Essa era a situação antes da integração nativa de 13/10/2026.
Agora a migração v6 substitui o vínculo exato pelo gerador livros_fiscais. Passo a passo em REVISAO-ROTINAS-NOVAS.md.

Captura de 13/10 mostra três caixas desmarcadas; o estado inicial muda
entre tentativas. Diagnóstico local de caixas/datas preparado em
DIAGNOSTICO-FORMULARIO-LIVROS.md, sem cliques/geração. Setembro exibido
foi informado ainda aberto; não usá-lo para emissão sem nova confirmação.

## Integração disponível para teste — 13/10/2026

**Preparar teste dos três Livros Fiscais** no painel direciona a Nova
execução. Só depois da revisão de código/competência/apuração e do botão
Executar no servidor ocorre emissão. Guia TESTE-PRESUMIDO-POR-EMPRESA.md.

O gerador marca/reconfere somente Entradas, Saídas e ICMS, mede campos de
data e exige releitura exata antes OK. A prévia pode ser qualquer um dos
livros. Exporta pela opção um PDF para cada relatório em Procurar Pasta.
O seletor nativo não tem campo de endereço comprovado: navega pela árvore
na unidade Client C configurada até pasta nova exclusiva em saida/.
Nome da folha, seleção e arquivos locais novos precisam ser confirmados.
Ambiguidade impede confirmação, sem inventar coordenada ou colar caminho.

A unidade é selecionada por Home/Down no combo medido, com Tab para
aplicar e fechar a lista. Cada mudança exige nova captura estável; não
repete Down durante atraso. Só começa a árvore ao ler Client C com a letra
configurada no campo fechado. Servidor C e Client Z não são aceitos.
PASTA_NAVEGACAO registra unidade_client_c antes das fases dos segmentos.
Se a unidade não mudar, ficar ambígua ou atingir o limite, não envia OK.

Quando o nome da pasta desejada já está visível no mesmo ramo/nível,
relê a captura e clica no texto diretamente, confirmando seleção azul,
nome completo, nível e unidade antes de expandir. Não precisa ler cada
pasta intermediária para chegar a Users. Não pula para homônimos de outro
ramo. Se o destino não aparece, mantém a navegação por teclado/rolagem.
O OCR/contornos são reutilizados somente dentro da mesma espera e somente
quando todos os pixels da captura continuam iguais; mudança exige leitura
nova. Isso reduz repetição de OCR em tela parada, sem reduzir confirmações.
O log clicar_pasta_visivel registra posição/nível sem nomes locais;
leitura_selecao diferencia unidade, falta de leitura e ausência de mudança.

Na correção de 16/10, a árvore é percorrida com Home/Down/Right/Left e
releitura da seleção azul/nível; Down faz a rolagem quando a próxima pasta
está fora da área visível. Em Client C segue Users → perfil local →
dominio-automation-engine → saida → LIVROS com 12 dígitos desta emissão.
O caminho é selecionado na árvore, nunca digitado nesse diálogo. A folha
exclusiva permite conferir apenas os três PDFs novos, preservando anteriores.
O botão OK precisa ser reconhecido na captura final. Se houver falha,
`python scripts\revisar_seletor_pasta.py --ultima-falha` lê a captura local
salva sem clicar ou gerar novamente.
Acrescente `--pasta Users` para verificar, sem ações, se Users está visível
no ramo atual da captura salva.

O Python local valida os três PDFs por conteúdo/período/CNPJ e só então
publica na pasta da empresa. Isso evita navegar pelo Dropbox no Domínio.
Nome final usa tipo, nome cadastrado e competência; arquivos anteriores
não são substituídos. Sem raiz configurada, saída continua local em saida/.

A tarefa oferece três downloads autenticados e mantém PDFs confirmados
mesmo em resultado parcial. Sucesso exige três tipos distintos e retorno
azul confirmado. Cabeçalho interno exato do ICMS ainda não foi fornecido;
a validação conservadora exige registro/apuração de ICMS no cabeçalho,
período e CNPJ, recusando Entradas/Saídas/Resumo. Nomes automáticos não
servem de comprovação. Conferência fiscal pelo supervisor continua pendente.

Script isolado scripts/testar_livros_fiscais.py requer servidor parado,
pergunta empresa/competência/apuração e usa o mesmo worker. Nenhuma
execução real desta integração foi observada na sessão de nuvem.

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
