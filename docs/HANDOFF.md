# Domínio Automation Engine — handoff

## Três releituras do Resumo também falham: diagnosticar a captura salva — 14/10/2026

Operador voltou com geometri:false nos seis motores/preparos, antes do campo
final, inclusive na terceira tentativa. Informou que o formulário continuava
aberto com as duas datas. O motor não enviou OK e recuperou o painel azul.
Esse log não distingue rótulos, bordas, área textual ou alinhamento: não
ajustar limiares/posições ou aumentar tentativas sem a evidência que falta.

RESUMO_RECORTE agora registra motivo fechado de rejeição e somente rótulos
canônicos com suas caixas; também distingue OCR indisponível/erro de leitura.
Não imprime mensagem de exceção, nomes, CNPJ nem OCR livre. A decisão de
liberar emissão permanece a mesma; esta revisão é diagnóstico.

No PC, `python scripts\revisar_periodo_resumo.py --ultima-falha` escolhe o
PNG mais recente de *erro_periodo_resumo.png em capturas/ e analisa offline,
sem captura nova, clique, digitação, troca de empresa ou emissão. Mostra
dimensões/título reconhecido e o motivo por motor. Captura integral continua
somente no PC; compartilhar somente o texto limitado do diagnóstico.

Próximo passo depende desse diagnóstico. A falha real do Resumo segue aberta.
Validação da ferramenta: 557 testes passaram; sintaxe Python e diff conferidos.

## Resumo perde uma leitura; operador interrompe a espera da EFD — 14/10/2026

Novo log: uma leitura do Resumo confirmou ambas as datas de agosto/2026.
O campo inicial já estava correto, mas a leitura seguinte, antes do campo
final, não encontrou a geometria. A rotina encerrou antes de reconhecer OK.
Não confundir esta tentativa com o problema de OK da seção anterior.
Agora tenta até três capturas novas antes de cada campo, com ponto de
cancelamento e intervalo curto. Não usa a captura anterior para liberar
OK: a leitura mais recente precisa confirmar ambos os valores solicitados.
Três falhas de leitura ou período divergente continuam bloqueando emissão.

Na EFD, o log ficou na espera do resultado e terminou em exceção. O operador
confirmou que interrompeu porque ficou esperando. Não houve marcador de
geração reconhecida nessa tentativa; não classificar como falha de fechamento
nem promover a execução a sucesso com base no relato ou em arquivo anterior.

Revisão encontrou duas limitações da espera: somente Tesseract2x e assinatura
perceptual8x8, que pode pular um aviso pequeno com pixels diferentes. Somente
na espera EFD, comparar pixels por digest, tentar Tesseract2x/4x e Windows2x/4x
em tela/centro antes de classificar erros. O corpo positivo é o já observado
em0.21, “Arquivo gerado com sucesso”; “sucesso” isolado não confirma geração.
O título positivo também é Aviso: todas as opiniões de sucesso precedem
a classificação do título. Avisos desconhecidos continuam em erros.decidir.
As opções sobrevivem à segunda espera após aviso informativo. A busca EFD
não imprime OCR livre. Não gerar novamente para resolver a espera.

Sem novo log de Livros nesta mensagem. Marcação dos três livros e validação
dos PDFs mantêm as travas existentes. Correção de código precisa de novo teste
individual no Windows, agosto/2026 apenas na empresa já confirmada fechada.

Validação desta revisão: 552 testes passaram; sintaxe Python e diff
conferidos. Nenhuma emissão real foi executada nesta sessão de nuvem.

## Resumo confirma datas mas não encontra OK; EFD gerada e livros parciais — 14/10/2026

Novo log Windows do Resumo: antes de digitar, ambos campos já confirmavam
01/08/2026 e31/08/2026. Após digitação, OCR oscilou brevemente 2028/2026,
mas releitura2 confirmou2026 nos dois. preencher_periodo foi confirmado;
gerar_previa começou e falhou sem OK. Código usava só OCR2x para OK.
Portanto essa tentativa não falhou em localizar/preencher o período.

Novo helper puro botoes_formulario.achar_ok_resumo exige título/campos,
mede botões da coluna observada e reconhece texto completo OK em escalas/
motores ou recorte PSM7. Fechar delimita a coluna, nunca calcula offset.
Aviso, outro OK, borda ausente ou ambiguidade impede clique. Mensagem
ok_resumo_nao_reconhecido informa datas confirmadas/OK bloqueado.
Campos já no valor pedido não são redigitados; valores diferentes
continuam sendo preenchidos/reconferidos antes de emitir.

Livros marcou só Entradas; sem logs de LIVROS_SELECAO não atribuir causa.
Pós-clique agora espera até cinco novas leituras por estado, aceita OCR
transitório, nunca reclique/desmarca e não vai à próxima caixa antes de
confirmar atual. Grupo16/estado inequívoco e ausência de outras opções
continuam obrigatórios; timeout impede emissão.

Operador informa EFD arquivo gerado com sucesso mas rotina falha. Revisão
comprovou wrapper descartar retorno positivo da limpeza após geração.
Agora somente fase encerrar com todas etapas anteriores confirmadas e
janela vinculada pode completar após nova confirmação de foco/painel,
sem regerar. Falha anterior à geração ou exceção não é promovida.
Worker preserva aviso_resultado_reconhecido e classifica resultado parcial
como nao_confirmada/geracao_sinalizada_encerramento_nao_confirmado.
Esse aviso não comprova conteúdo do arquivo; nenhuma leitura fiscal nova.
No CLI a pendência de encerramento também ganha mensagem explícita.

539 testes passaram, incluindo OCR real em pixels sintéticos para OK,
ambiguidade/avisos, datas já corretas, marcação atrasada sem reclique,
EFD gerada+limpeza positiva sem repetição e falta de foco/geração sem
promoção. Motivo/aviso persistem no worker após falha/exceção. Execução
Windows desta correção ainda pendente; testar individual em agosto/2026
na empresa previamente confirmada e conservar logs/capturas locais.

## Novo teste falhou na abertura dos livros e no período do Resumo — 14/10/2026

Operador atualizou para main2c7a1f7 e informou falha em todas as rotinas.
Especificou Livros em abrir_livros, sem marcar as três caixas; Resumo em
preencher_periodo, sem reconhecer datas. Captura parcial mostra rótulos
Registro de Entradas/Saídas/ICMS e caixas desmarcadas, sem painel completo
ou dados da empresa. Não comprova a causa exata do OCR/CV na instalação.

Trava comprovada no código: abrir_livros exigia ler_campos antes de ler
qualquer caixa. Agora abertura/marcação usam ler_selecao_com_ocr sem
período; as três caixas e todas as outras opções continuam conferidas.
Leitura/preenchimento das datas acontece na etapa própria; antes OK exige
novamente seleção e período completo. Não marca/desmarca por offset.

OCR acrescenta cópias ampliadas 4x/6x em preto e branco (contraste/Otsu),
segmentação de formulário e linhas numéricas. Pixels originais continuam
sendo usados para caixas/marcações. Bordas claras recebem reforço medido
por outro limiar e detecção de bordas nos campos; fixtures Windows3D
sintéticas reproduzem limitações do algoritmo anterior. Não comprovam
qual renderização exata causou a falha real.

Mantém concordância de leituras completas, sem usar a data desejada como
sugestão, corrigir ano ou completar dígitos. Falha de data salva recortes
original/binária6x localmente em capturas/resumo_data_* ou livros_data_*.
LIVROS_SELECAO imprime só rótulos conhecidos/medidas/contagens/estados/
motivos fechados, inclusive leitura parcial. LIVROS_PERIODO e RESUMO_RECORTE
imprimem só campos/data/medidas. Diagnósticos CLI continuam sem ação e
agora separam leitura das caixas das datas. Capturas/PDFs ficam locais.

523 testes passaram. Incluem marcação real simulada das três caixas antes
de uma falha de período, ausência de OK, preto/branco concordante e
conflitante, imagem original preservada, sombras/caixas claras, grupo15
recusado e privacidade dos diagnósticos. Ainda sem execução Windows dessa
correção. Primeiro retestar individual em agosto/2026 na empresa confirmada.
EFD também foi informada falha, sem detalhe novo; não atribuir causa nem
alegar corrigida. Se persistir, pedir saída limitada dos diagnósticos locais,
não OCR bruto nem capturas com identificação fiscal.

## Integração dos três livros e leitura de datas — 13/10/2026

Prioridade do operador: finalizar Presumido por empresa antes dos lotes.
Git remoto revisado: Claude publicou limpeza final em limpeza-final-v2,
commit e73ab29, derivado da main 3b780c9. Incorporados fechamento por
Esc/Fechar/Ctrl+F4 e recuperação do executor, com releitura do painel e
foco a cada passo; confirmação antiga não substitui nova leitura.

Evidência Windows nova: diagnóstico Resumo encontrou Data inicial/final
no OCR4x, nenhuma data inicial completa e apenas final30/09/2028. Não
corrigir o ano por suposição. Log local também mostrou abrir_resumo falhar
por Data final ausente no OCR2x; a EFD preencheu período e falhou com
exceção na geração, sem traceback fornecido. Sua causa ainda é desconhecida.

Leitor novo mede bordas dos campos a partir dos rótulos, recorta só datas,
normaliza seleção azul numa cópia e exige duas leituras completas concordantes.
Nunca recebe período esperado nem completa/corrige dígitos. Abertura Resumo
usa título e campos, duas escalas/OCRWindows, antes da leitura dos valores.
Livros reutiliza leitor para Inicial/Final e ignora o rodapé Conforme período inicial.

livros_fiscais é capacidade nativa. Migração v6 troca só cadastro conjunto
exato nas sequências LP/LR, preservando ordem/edições e arquivando roteiro
antigo sem uso. Gerador conjunto marca só as três caixas conhecidas,
relê período e seleção antes OK, valida empresa/prévia e escolhe menu
Gerar um arquivo PDF para cada relatório. Seletor Procurar Pasta mede
combo/árvore, escolhe Client C da unidade configurada e navega até staging
exclusivo em saida/LIVROS+12dígitos. Não presume campo de endereço nem
caminho pessoal. Ausência/ambiguidade impede OK e salva captura local.

Três arquivos novos estáveis são classificados pelo conteúdo; exigem tipo,
período completo e CNPJ da prévia. Título interno ICMS ainda não fornecido:
verificador conservador exige registro/apuração de ICMS no cabeçalho,
recusa Entradas/Saídas/Resumo; não classifica pelo nome ICMS NORMAL(M).
Nenhuma homologação fiscal decorre dessa família de título.

Worker publica cada PDF no destino cadastrado ao final, nomes por empresa/
competência e sem sobrescrever. Artefatos públicos têm id/tipo/nome/disponível,
sem caminhos; download autenticado exige tarefa/id/caminho/SHA256 exatos.
Falha preserva arquivos confirmados; sucesso exige três tipos únicos, fim
concluído e retorno azul. Consultas compartilham a conexão SQLite existente
para não bloquear commit entre leitor externo e leitor aninhado.

Botão Preparar teste dos três Livros Fiscais direciona a Nova execução,
copia empresa/mês escolhidos e exige confirmação nova antes de emitir.
Presumido por empresa e lote comum podem executar a sequência inicial
Resumo/EFD/Livros sem a antiga pendência de integração. Custom pendente
continua bloqueado ou explicitamente parcial. EFD continua exportador,
não demonstrativo PDF. Guia LIVROS-FISCAIS-CONJUNTOS.md e script
scripts/testar_livros_fiscais.py (servidor parado, mesmo worker/trava).

Validação: 512 testes passaram; Chromium do piloto passou sequência nativa
completa em um envio e três downloads, além dos casos de pendência/falha.
Chromium geral e destino também passaram. Sintaxe Python/JS e diff
conferidos. Fiscal/desktop são sintéticos.

Status: integrado para teste; ainda não executado/homologado no Windows.
Agosto/2026 fechado só para a empresa confirmada pelo operador. Primeiro
conferir os três livros individualmente, depois sequência Presumido nessa
empresa, só então lote. Caminhos, CSV, capturas e PDFs continuam locais.

## Datas do Resumo permaneceram em setembro — 13/10/2026

Operador informou Resumo sem trocar data e Livros como não executado/
integração pendente. Confirmou datas permaneceram no mês 09 e rotina
falhou; não há log da etapa nem confirmação se chegou à prévia. Livros
permanece sem gerador conjunto, pendência registrada corretamente.

Revisão pelo papel automacao-dominio: pedido ISO chega formatado ao
gerador, que localiza datas, usa Home+Shift+End, oito dígitos e Tab,
exige releitura exata antes do OK e confere prévia/PDF. Não comprovou
causa Windows. Falta comprovada: nenhuma informação de esperado/lido/
campo ao falhar; teste feliz simulava campos já em agosto o tempo todo.

Entrega acrescenta logs locais RESUMO_PERIODO com fase/campo/esperado/
duas datas/posições/tentativa, sem OCR livre ou identidade fiscal. Motivos
fechados para campos não localizados, inicial/final não confirmadas ou
divergência final são mantidos nos eventos, tarefa, painel e relatório,
inclusive após recuperação. Captura da falha permanece local antes da
recuperação. A estratégia de digitação não foi alterada por hipótese.

Script revisar_periodo_resumo.py só captura/lê o formulário aberto;
mostra por motor rótulos conhecidos/datas alinhadas/medidas. PNG local
opcional; não digita/clica/emite. Próximo passo: operador abrir Resumo,
rodar diagnóstico, retornar ao formulário nos cinco segundos e enviar
saída limitada. Depois testar individual em agosto/2026 fechado e copiar
linhas RESUMO_PERIODO ou o motivo do painel. Não afirmar correção de
data no Windows sem esse log.

464 testes validados (462 na rodada completa e dois casos novos do CLI
na rodada dirigida), com troca sintética setembro→agosto, inicial/final
que não mudam, OCR temporário e alteração da inicial durante digitação
da final bloqueando OK. Testes de CLI/privacidade/worker preservam motivo
mesmo após recuperação. Chromium piloto passou a exibição de motivo,
falha preservada e continuidade da EFD após recuperação. Sintaxe/diff
conferidos. Não houve novo clique/emissão ou diagnóstico Windows real.
CLI também trata OCR/título/PNG indisponível com mensagem fixa, sem
traceback livre, e tenta o título pelo OCR Windows se Tesseract falhar.

## Teste do Presumido por empresa e diagnóstico dos livros — 13/10/2026

Operador não encontrou botão para executar a conjunta; confirmado que
não existe gerador conjunto no executor. Agosto/2026 foi informado fechado
para a empresa do teste. Solicitou toda a sequência em um clique por
empresa, com prioridade individual, depois em lote. Pediu o comando do
diagnóstico; foi entregue cd /d da instalação + revisar_formulario_livros.py.
Ainda não chegou o resultado Windows dessa leitura.

Painel agora tem Lucro Presumido por empresa: consulta a sequência ao
escolher empresa/mês, exige apuração, aceita um envio e usa o worker/lote
comum. Com pendências, execução exige opção explícita de testar somente
disponíveis. Na sequência inicial roda Resumo/EFD, registra Livros como
não executado, preserva cadastro e termina concluida_com_pendencias,
sem alegar sucesso completo. API desse modo recusa outros regimes,
competência incompleta/atual, hash desatualizado e repetição divergente.
Lote comum continua estrito. Lote parcial agrupa por empresa, mantém
falha recuperada e interrompe quando não confirma retorno.

Relatório JSON autenticado/exportável agrega motivos, etapa com falha,
tempos, último estado de recuperação e pendências. Não inclui caminhos,
PDF ou OCR livre; nomes/códigos de empresas são do cadastro revisado e
ficam no relatório local do operador. Nunca equivale à homologação.

Botão Conferir formulário dos três livros usa a operação exclusiva do
worker/login; identifica/foca janela conhecida, captura local e reaproveita
leitura em duas escalas + OCR Windows. Não altera caixas/datas nem clica
OK. API publica apenas estados/datas/medidas; cancelamento, falha e nova
operação limpam resultado anterior. Nenhuma promoção automática.

Script explorar_presumido.py usa mesmo banco/trava/worker para teste
individual com servidor parado. Sem --somente-disponiveis recusa
sequência pendente; CLI devolve 2 quando o teste é parcial, não sucesso
completo. Sintaxe, 452 testes e Chromium geral/destinos/piloto passaram
(451 na rodada geral e o caso adicional do relatório na rodada dirigida).
Fiscal/desktop nos testes são sintéticos, sem emissão Windows real.

Próxima evidência: log local da aba Geral. Depois confirmar o seletor
Procurar Pasta e título interno de ICMS, implementar exportação conjunta,
três arquivos/publicação/download e testar individualmente antes do lote
inteiro. Não executar custom pendente nem usar exportador de EFD como
demonstrativo PDF. Guia TESTE-PRESUMIDO-POR-EMPRESA.md.

## Raiz compartilhada no cadastro de empresas — 13/10/2026

Operador pediu usar a raiz local compartilhada de Presumido/Real como
base preenchida e aceitar só o restante da empresa ou um caminho inteiro.
A raiz pessoal não foi versionada: configurar uma vez no PC por
configurar_destino_livros.py --raiz, em data/destino_livros.json ignorado.
O painel autenticado mostra essa raiz somente leitura e normaliza o
caminho inteiro para relativo. Recusa unidade/pasta externa, retorno e
links externos. Salvar, editar, prévia e limpar preservam a base correta.

Ao estreitar uma raiz antiga, prefixo do mapa/cadastro só é retirado se
coincide exatamente com o final da raiz, o destino direto não existe
e a alternativa abreviada existe de modo único. Não altera o CSV nem
adivinha nomes. CLI preserva subpasta anterior ao mudar apenas a raiz.
Prévia não cria nada; Testar pasta continua sem emissão fiscal.

434 testes de lógica/API passaram; Chromium geral e destinos passaram
com base preenchida, caminho completo/relativo e edição de datas.
Configuração da raiz no PC e conferência do destino real ainda pendentes.
Nenhuma nova emissão ou integração do conjunto de três livros nesta entrega.

## Leitura do formulário Livros e recuperação confirmada — 13/10/2026

Log Windows confirmou recuperar_instalacao.py concluído em 949a760,
com backup local do código/Git e preservação de dados/configurações.
Ainda não há novo log de emissão fiscal. Captura da aba Geral mostra
Entradas/Saídas/ICMS desmarcados e período setembro/2026. Operador respondeu
que setembro não está fechado, depois pediu mês passado. Foi explicado
que mês passado em 13/10 é setembro; confirmação de agosto/outro mês
apurado nessa empresa está pendente. Não emitir setembro nessa etapa.

formulario_livros lê caixas por quadrados/pixels junto dos rótulos OCR,
sem offsets novos. Exige 16 caixas em Emitir, rejeita estado desconhecido
e separa opções do painel direito. Datas por caixas OCR, sem confundir
inicial do rodapé. Primitiva idempotente para futura seleção dos três
livros ainda não integrada a gerador/executor; não clica OK nem emite.

scripts/revisar_formulario_livros.py e atalho Revisar Formulario Livros.bat
são somente leitura. Captura local após cinco segundos para colocar a
janela em foco; imprime estados/medidas/datas/contagem de outras opções,
sem texto livre/CNPJ/empresa. PNG local opcional. Dois OCRs Tesseract e
Windows como segunda opinião. tela importa para leitura de PNG fora de
Windows sem chamar o setup de DPI; comportamento Windows permanece.

Print inline não foi convertido em arquivo/medido nesta nuvem; algoritmo
ainda precisa de log Windows. Testes usam pixels/dados sintéticos e OCR
real. Diagnóstico não comprova emissão, conteúdo ICMS, empresa ou retorno.
425 testes passaram, incluindo dez casos da leitura/seleção e CLI com PNG
local sem alteração/emissão. Sintaxe/diff conferidos. Emissão conjunta
e diagnóstico contra o formulário real ainda não executados nesta nuvem.
Guia em DIAGNOSTICO-FORMULARIO-LIVROS.md. Não recomendar a conjunta como
rotina já executável: seletor de pasta, três artefatos e conteúdo ICMS
continuam pendentes de implementação/confirmação.

## Revisão dos roteiros e recuperação da instalação — 13/10/2026

Operador pediu continuar a configuração e revisar os passos das rotinas
novas. Main consultada: 1fd8084. Nenhuma mudança de gerador fiscal nesta
entrega. REVISAO-ROTINAS-NOVAS.md separa Livros, Resumo e o produto EFD.

Cadastro v5 cria Livros Fiscais — Entradas, Saídas e ICMS como pendente.
Nos regimes LP/LR com trio completo, agrupa no primeiro livro e preserva
ordem/empresas/histórico. Sequências parciais/outros regimes permanecem;
cadastro conjunto já configurado é reutilizado. Roteiro ICMS anterior é
arquivado somente se nenhum regime o usa. Reinício não restaura vínculos
removidos. Geradores individuais continuam disponíveis; a conjunta ainda
não existe no executor, não emite três PDFs nem habilita lote remoto.

Conferência: o item Demonstrativo EFD Contribuições usa gerar_efd_contribuicoes
e o exportador de Relatórios/Informativos/Federais, sem retorno de PDF.
Perguntado ao operador se deseja essa exportação ou um demonstrativo PDF;
resposta ainda pendente. Não alterar sem confirmar menu/produto esperado.
Título interno ICMS também pendente; operador não entendeu a pergunta,
foi orientado a copiar apenas a frase do topo da primeira página.
Não definir validação ICMS pelo nome ICMS NORMAL (M) do arquivo.

Diagnóstico real de 09/10: HTML local e resposta HTTPS têm 17.171 bytes,
início zerado, comparação idêntica e form-login ausente. Site branco não
foi reproduzido com os arquivos válidos da nuvem. Regra ESET não resolveu.
Git archive HEAD falhou com not a valid object name; causa da corrupção
não determinada. Recuperação parcial por clone/web foi instruída, sem
log que comprove a abertura final ou reparo do Git original.

scripts/recuperar_instalacao.py deve rodar no clone novo da main, fora
da instalação antiga, com --destino. Confere Git/HTML e trava os dois
executores antes de aplicar. Prepara backup do código e Git; recupera
versionados e .git no caminho original, preservando data/, saídas,
capturas/.env/ambientes e arquivos não versionados. Falha tenta rollback.
Não opera desktop, recria certificados ou instala dependências.
Passo a passo em RECUPERAR-INSTALACAO.md; execução Windows confirmada no
registro acima. Emissão fiscal/abertura final do painel ainda não confirmadas.

415 testes passaram, incluindo cadastro/recuperação com SQLite e clones
Git reais locais; Chromium passou configuração/rascunho/validação da
conjunta e sequência de três rotinas, sem liberar execução. Sintaxe e
diff conferidos. Desktop/emissões/autenticação fiscal são simulados.

## Digitação de datas e abertura do Resumo revisadas — 09/10/2026

Operador relatou que a data era apagada antes de terminar de escrever e,
no teste do Resumo, falha na etapa Abrir Resumo por Acumulador. Chromium
reproduziu o reinício da edição do ano ao reaplicar input.max com o mesmo
valor. atualizarLimitePeriodo agora escreve somente quando o limite muda;
individual, lote e competência de destino usam o helper. Calendário nativo,
validade do período e confirmação de apuração permanecem. Cache web v9.

_esperar_item_menu tinha recorte superior de 300 pixels. O submenu longo
de Acompanhamentos tem Resumo abaixo dessa região; somente essa busca usa
menu_completo=True com captura completa. OCR/cache continuam conferidos
antes do clique; sem offsets novos. Console/capturas distinguem as quatro
partes da abertura. Não há evidência ainda de que esta fosse a causa exata
da tentativa Windows, apenas a etapa informada pelo operador.

404 testes passaram, incluindo OCR real de menu sintético abaixo do
recorte antigo e ausência do item sem clicar em vizinho. Smoke de destinos
testou teclado/ano vazio/parcial em sete campos, com chamadas reais à API
durante a edição, além dos cenários de destino já existentes. Fiscal/desktop
continuam simulados; repetir Resumo individual no Windows após atualizar.

Operador reforçou o nome Livros Fiscais para Entradas/Saídas/ICMS juntos.
Isso é o fluxo já documentado de três PDFs, ainda não integrado. O painel
explicita essa pendência; geradores individuais e cadastro ICMS não foram
apresentados como emissão conjunta. Nenhuma migração de vínculos nesta
correção. Implementar seletor de pasta/múltiplos arquivos/conferência ICMS
conforme docs/LIVROS-FISCAIS-CONJUNTOS.md antes de liberar a rotina conjunta.

## Atualizador sem commit de merge — 09/10/2026

Operador informou fetch bb50f50..868c5be seguido de Committer identity
unknown. Atualizar.bat usava git pull origin main: integra main na branch
atual, podendo exigir merge. O log não informa qual era a branch local;
não presumir que fosse a do Claude. Comando de recuperação informado:
git switch main && git pull --ff-only origin main, sem configurar identidade.
Operador confirmou troca para main e fast-forward bb50f50..868c5be,
com os novos arquivos de destinos e Resumo por Acumulador.

Atalho agora usa scripts/atualizar_projeto.py (somente biblioteca padrão).
Confere raiz/estado local, busca explicitamente origin/main, confere se a
main local é ancestral e abre main antes do avanço --ff-only. Commits de
outras branches permanecem nelas. Operação pendente, alterações tracked,
HEAD destacado ou main divergente interrompem sem reset/stash/rebase.
Git protege arquivos untracked que colidiriam; --no-overwrite-ignore na
troca/avanço também protege dados ignorados. Falha retorna código 1,
impedindo instalação de dependências no BAT.

Quatorze testes com repositórios Git reais locais, sem identidade configurada,
confirmam avanço, troca de branch, preservação de trabalho/dados, conflito
pendente, origem indisponível e refspec restrito. Não executado no CMD do
Windows do operador. Passo a passo em docs/ATUALIZACAO.md e seção 0.95.

## Resumo por Acumulador pronto para teste individual — 09/10/2026

Operador enviou formulário com Data inicial/Data final/OK e prévia com
RESUMO POR ACUMULADOR, CNPJ e Período, seguida de Salvar em PDF em inglês
(File name/Save). Destino mostrado: saida/ do projeto via Client C.
Formulário e prévia mostram meses diferentes; não se presume execução
única ou sucesso. Registro em docs/RESUMO-POR-ACUMULADOR.md e seção 0.94.

Novo gerar_resumo_acumulador em app/dominio.py; oito etapas com nomes do
Resumo, eventos locais sem conteúdo fiscal. Datas por centros de caixas
OCR medidas em execução, sem offsets novos; Tesseract 2/4x e segunda
opinião Windows com caixas. Digitação precisa ser relida em cada campo,
OK por OCR, espera por prévia com título/CNPJ/Período. Reconfere código
da empresa e período antes de exportar. Ícone pelo template existente,
sem fallback fixo; Salvar em PDF/File name confirmados antes de Alt+n.
Nome temporário exclusivo precisa ser lido antes de Enter.

PDF novo estável/legível precisa confirmar título/período/CNPJ da prévia;
nome acumulador_nome_cadastrado_AAAA-MM.pdf. Worker usa cadastro/snapshot,
preserva anteriores com sufixo e mantém download. Resumo fica em saida/;
não usa a subpasta LIVROS_FISCAIS. Valores do relatório de referência
precisam de conferência fiscal humana. Retorno calibrado ao painel azul
é obrigatório para concluir; recuperação não transforma falha em sucesso.

Catálogo/executor/API/painel conhecem resumo_acumulador. Migração v4 troca
IDs antigos mantendo ordem, arquiva configurações anteriores e deduplica,
sem restaurar itens removidos. Piloto LP/LR mantém cinco indicadores;
ICMS continua pendente e bloqueia lote completo. Testar Resumo individual.

CLI scripts/explorar_resumo_acumulador.py e atalho Testar Resumo por
Acumulador.bat: usam mesmo worker/lock/banco real, exigem empresa cadastrada,
competência passada e apuração confirmada. Parar servidor antes do isolado;
cinco segundos de preparação humana para focar Domínio, depois preflight
normal valida tela azul, empresa/F8/calibração/foco. Alternativa: Nova
execução no painel, datas e confirmação de apuração.

388 testes de lógica/API passaram; Chromium geral e destino passaram.
Testes de fluxo substituem desktop/OCR; PDFs/SQLite reais são sintéticos.
As imagens inline não foram medidas; nenhum offset novo foi calibrado.
Falta log no Windows: OCR das datas, ícone, foco File name, exportação,
conferência do PDF e fechamento. Não afirmar homologação ou valores corretos.

Os checkpoints abaixo preservam o histórico anterior a essa integração.

## Destino por empresa e esquema recebido — 09/10/2026

Esquema do Claude recebido no commit f71813c, branch
`claude/arquitetura-servidor-20261009`; somente documento novo, baseado
na main anterior às travas. Integrado como `docs/ARQUITETURA-SERVIDOR.md`
sobre a main bb50f50, preservando F8/foco/recuperação. Clientes citados
foram generalizados; CSV real continua somente no PC do operador.

Operador escolheu `FISCAL\MM\RELATORIOS_APURAÇÃO\LIVROS_FISCAIS` e pediu
destino configurável na empresa, com teste para conferir onde guarda.
SQLite migra `empresas_painel` preservando cadastros e adicionando
`pasta_relativa`/`subpasta_livros`. Campos omitidos por clientes antigos
preservam valores; vazios herdam CSV por código/padrão. Lote congela esses
campos na revisão. LP/LR compartilham raiz, sem deduzir regime pela pasta.

`Configurar Destino Livros.bat` salva raiz local em C: no arquivo ignorado
`data/destino_livros.json`. `app/destinos_livros.py` confere raiz/empresa/
FISCAL existentes, ano opcional, mês passado e contenção de caminho.
Não importa o desktop. API autenticada e painel: Ver destino não cria
nada; Testar pasta cria destino/grava/remove temporário, sem PDF fiscal.
Testar gravação durante execução é recusado.

Ao final de Entradas/Saídas confirmados, worker usa cadastro/snapshot e
publica no destino, com nome e competência, cópia exclusiva e sufixos.
Falha preserva origem e resulta em não confirmada. Destino mensal exige
um mês por execução. Sem raiz configurada, continua a saída antiga.
`arquivos_publicados` registra somente o caminho final daquela tarefa;
download não abre acesso genérico ao Dropbox nem depende da configuração
atual para servir documentos anteriores.

371 testes de lógica/API passaram; smoke geral Chromium passou. O smoke
específico confere cadastro, edição, prévia, gravação, edição não salva,
larguras e logout. Fiscal permanece simulado; testar no Windows antes
de homologar. Emissão conjunta continua pendente: caixas, árvore nativa
de Procurar Pasta, conteúdo de ICMS e múltiplos arquivos por tarefa.

Novo print identifica **Relatórios → Acompanhamentos → Resumo por
Acumulador**. Registrado em `docs/RESUMO-POR-ACUMULADOR.md`; ainda falta
formulário, filtros, exportação e validação. Nenhuma coordenada inventada
ou rotina pendente liberada.

## Travas de empresa e preparação de sessão — 09/10/2026

Pedido seguinte: código cadastrado X deve determinar a empresa alvo,
mesmo se o Domínio mostrar Y; recuperação segura de telas fora do padrão.
O executor individual agora também usa F8. Individual/lote releem código
e painel azul imediatamente antes do gerador, mesmo sem trocar empresa.
Código ilegível ou divergente após F8 bloqueia emissão. Busca por Código
na tela F8 ainda é pressuposto legado; conferir no teste Windows.

Preparação com tela aberta usa recuperação calibrada existente (até cinco
Esc, um por vez, parando no painel azul), antes de identificar/trocar a
empresa. `trocar_empresa()` aceita callback `recuperar_inicio`; o executor
o fornece na única nova tentativa de F8. Evita o Esc repetido legado nesse
caminho. Chamadas locais sem callback preservam fluxo anterior.

`verificar_antes_de_agir()` verifica foco nos checkpoints de mouse/teclado
da preparação/geração. O bloqueio é persistente durante essa execução: não
libera ações se o gerador absorver a exceção e o foco voltar depois.
Antes de gerar, perda de foco recusa a tarefa; durante a geração é falha
recuperável pelo worker, sem repetir a emissão.
Encerramento/cancelamento/retomada continuam respeitados. Recuperação após
falha mantém a política anterior: painel azul + código da empresa corretos
para ir à próxima; não reconhecer interrompe. Emissão conjunta de Livros
continua pendente da implementação/exportação; esquema recebido no
checkpoint acima.
355 testes de lógica/API passaram, além do smoke Chromium com fiscal/login
simulados. Homologação das travas e troca na sessão Windows ainda pendente.

## Mapeamento de 09/10/2026 — Livros Fiscais conjuntos

O operador pediu Entradas, Saídas e ICMS selecionados no mesmo formulário,
um período e um OK. Depois: ícone PDF → Gerar um arquivo PDF para cada
relatório → Procurar Pasta → Client C (M:) → destino local Dropbox ainda
a conferir no painel conforme checkpoint acima. A prévia inicial pode ser qualquer
livro. Veja [LIVROS-FISCAIS-CONJUNTOS.md](LIVROS-FISCAIS-CONJUNTOS.md).
O esquema solicitado ao Claude cobre Lucro Presumido e Lucro Real nesta
etapa; outros caminhos serão adicionados depois. Primeiro teste no Presumido.
Esse seletor de pasta difere do Salvar em PDF individual existente.
Não fixar usuário/caminho pessoal nem supor campos/coordenadas. A função
de conversão C: local → unidade cliente já existe; confirmar destino e
permissão de download. Faltam seleção verificada, exportação conjunta,
validação do PDF de ICMS, múltiplos arquivos por tarefa e teste Windows.
Mapeamento documentado; emissão conjunta ainda não implementada/homologada.

## Entrega de 09/10/2026 — cadastro e roadmap de gestão

Correção seguinte confirmada pelo usuário: o Demonstrativo EFD
Contribuições é a rotina EFD integrada existente, apenas renomeada.
Migração `piloto_lp_lr_efd_integrada_v3` substitui vínculos da cópia pendente,
evita repetição nos regimes e arquiva passos antigos no SQLite. O motor
`efd_contribuicoes` não muda. Pendentes novos: Resumo por Acumulador e ICMS.

Novo pedido: PDFs confirmados do painel usam nome cadastrado da empresa,
tipo e competência, normalizados em minúsculas. O lote conserva o nome
da revisão do plano. Cópia exclusiva evita sobrescrever; falha conserva
origem e pede conferência. Download usa o caminho final salvo na tarefa.
Chamadas locais sem cadastro conservam o nome OCR antigo. EFD ainda
retorna bool, sem caminho para renomear; Resumo aguarda integração.
343 testes de lógica/API e smoke Chromium com fiscal/login simulados;
emissão, conteúdo fiscal e recuperação no Windows ainda por homologar.

Pedido confirmado: preparar Lucro Presumido e Lucro Real; primeiro piloto
somente Lucro Presumido. Indicadores: Resumo por Acumulador, Demonstrativo
EFD Contribuições e Livros Fiscais de Entradas, Saídas e ICMS. O ICMS é
cadastro próprio pendente, não SPED Fiscal; título/tela exatos ainda precisam
de mapeamento. `scripts/servidor.py` prepara os cadastros uma vez no SQLite,
sem empresas reais, preservando sequências existentes; a migração ICMS
acrescenta esse vínculo aos dois regimes uma vez.

Cadastro por nome, vínculo por ID, configuração individual e envio à
validação no painel. Estados pendente_configuracao/rascunho/aguardando_validacao;
editar devolve a rascunho. Roteiros do cadastro ficam no SQLite, separados dos
JSON do gravador legado. Faltam aprovação formal/evidências/versionamento e
ligação desses roteiros ao executor. Cadastro não aprova nem habilita emissão.

Pedido seguinte mudou a política de falhas do lote: registra a falha,
recupera até a tela azul e continua na próxima rotina. O adapter reutiliza
Esc com HWND/foco conferidos, uma ação por vez, até cinco ações; confere
tela calibrada e código da empresa antes de liberar continuação. Não repete
emissão, não reinicia servidor e não envia OK genérico. Pré-condição recusada,
cancelamento ou recuperação inconclusiva ainda interrompem. O resultado do
lote pode ser concluida_com_falhas, preservando resultados de cada item.

Veja [ROADMAP-GESTAO.md](ROADMAP-GESTAO.md) para o relatório aos gestores,
responsáveis propostos e critérios de conclusão. Esta entrega precisa ser
instalada e revalidada no Windows. O histórico abaixo descreve versões
anteriores e sua política anterior de interromper após qualquer falha.

## Estado para retomada em 08/10/2026

Repositório atual: `financeirolucrattiva-web/dominio-automation-engine`,
branch remoto `main`. Codex e Claude Code podem trabalhar juntos;
confira alterações e versão remota antes de publicar, sem force push.
O texto abaixo deste checkpoint mantém o histórico de setembro.

Entrega mais recente: cadastro web de regimes com rotinas integradas
ordenadas pelo usuário, empresas com seletor de regime e lote remoto
empresa por empresa. Cada empresa faz todas as rotinas antes da próxima.
Filtro/seleção, competência/datas obrigatórias, revisão do plano por hash,
snapshot no SQLite, histórico por item, pausa/retomada e interrupção.
Falha/retorno não confirmado interrompe o restante; reinício não repete.
Alteração de cadastro vale para novos lotes. Rascunhos novos continuam
fora da execução remota; agendamento permanece futuro. CSV local intacto,
sem importar exemplo ou dados reais automaticamente para o painel.

Adapter de lote reutiliza `dominio.trocar_empresa()` (F8) e exige tela
principal/foco e código relido antes da geração. Individual não troca
empresa. A busca F8 pressupõe Código como no caminho local: conferir na
primeira rodada Windows. Sem menus/coordenadas novos. Bancos de simulação
e real são separados. Atualizar servidor, reiniciar executor, Ctrl+F5 no
cliente; configurar regimes/empresas em modo real antes do teste.

313 testes passaram e Chromium verificou cadastro, ordem por empresa,
calendário bissexto, lote, pausa/retomada/interrupção e demais controles
anteriores com fiscal/login simulados. Novo teste Windows: duas empresas
autorizadas, rotinas conhecidas e competência apurada; conferir códigos,
documentos e retorno. Isso ainda não comprova lote real no Domínio.

Entrega anterior (08/10): pausa cooperativa/retomada, calendário obrigatório
por competência ou intervalo, SPED/Contribuições com datas explícitas
preservadas no retry, login Onvio com código humano e Domínio Web/Fiscal,
cancelamento, reinício do ciclo e calibração/captura pela interface.
Senhas/OTP só em memória, sem banco/log/API pública. Login e manutenção
usam o mesmo worker/trava fiscal. Captura é exceção deliberada ao contrato
antigo sem imagens: janela Domínio reconhecida, cliente autenticado da
rede, sem disco/IA e TTL de 30 segundos. Perfil de navegador próprio local.

Mapa local guarda regiões de menus confirmadas, sempre relidas por OCR;
polling visual substitui esperas fixas entre submenus conhecidos. Preserva
caminhos, clique em L, campos, geração e conferências. Tempo real falta.
Configuração web salva rascunhos no formato do gravador; hover por texto
acrescentado sem alterar hover antigo x/y. Rascunhos não foram promovidos
nem expostos para execução remota.

O usuário reabriu prioridade de lote após esses controles: empresas por
regime (ex. Simples Nacional) × rotinas aprovadas. Agendamento por empresa,
dia/horário é futuro. Próximas etapas em ROADMAP-RPA.md; o lote remoto
descrito no checkpoint acima é novo e precisa de teste Windows. Servidor dedicado
sem Domínio informado; PC atual é servidor de teste. Usuário disse que a
execução remota funcionou depois de ajustar chave e pré-condição, sem
log/documento detalhado para validar conteúdo.

290 testes de lógica/API passaram; Chromium conferiu fiscal/login simulados:
calendário bissexto, pausa/retomada, OTP, limpeza de senhas, captura,
calibração, rascunho, cancelamento/reinício, logout/offline e 3 larguras.
Wheels Playwright/greenlet verificadas para Windows x64/Python 3.14.
Falta rodada Windows completa dos novos controles/login e campos medidos.
Entrar pode pedir autorização nativa para abrir GO-Global; não inventar
essa tela. Pedir captura/estado da etapa real se bloquear. Primeiro teste:
atualizar servidor, reiniciar executor Windows e Ctrl+F5 no cliente;
SPED individual com calendário, pausa/retomada e retorno. Depois login
completo com código no painel e conferência da tela azul.

Pedido mais recente: somente organizar arquivos em pastas, mantendo
as funcionalidades. Os três instaladores principais e `Atualizar.bat`
ficam na raiz; os outros 17 BAT foram movidos para `atalhos/servidor/`,
`atalhos/interface/`, `atalhos/ocr/` e `atalhos/ferramentas/`.
Índice em `atalhos/README.md`. Os atalhos continuam usando os mesmos
scripts e opções; diretório de trabalho, chamada entre BAT e caminhos
nas instruções foram ajustados. Não unificar modos nem cortar dependências
por conta desta organização. Preservar o pacote público de cliente.

No teste Windows de conexão entre PCs, a interface abriu após mudar a
rede do servidor de Pública para Privada (perfil aceito pela regra).
Em seguida o servidor não iniciou, e o usuário informou ter alterado
a chave. `scripts/servidor.py` agora identifica chave curta/não ASCII
antes de criar executor/banco, explica mínimo de 32 caracteres e preserva
o segredo sem o imprimir. Outras falhas OSError/ValueError ao iniciar
passam a registrar a causa no log local. 254 testes passaram.
O log enviado registra WinError 10054 no callback asyncio de desconexão;
não comprova a causa da recusa de inicialização. A retomada real ainda falta.

Pedido atual: terminar o site no projeto existente. Lote deixou de ser
prioridade; manter execução individual e resultados verificáveis.
Interface web instalável/PWA em `web/`, API em `app/api_servidor.py`,
persistência/worker em `app/servidor.py` e adaptador das rotinas existentes
em `app/executor_servidor.py`. Entrada: `scripts/servidor.py`; consulta
por padrão, `--simular` sem desktop, `--executar` exige Windows.

244 testes passaram; Chromium exercitou a interface real com eventos
simulados, inclusive envio, estados, histórico, logout e offline.
Prévia: `docs/preview-interface-conectada.png`, somente dados simulados.
Leia [SERVIDOR-E-INTERFACE.md](SERVIDOR-E-INTERFACE.md) para instalação,
HTTPS/PWA e limitações. O servidor do usuário está disponível, mas ainda
sem Domínio; não houve implantação/execução fiscal nele.

Chave, banco de tarefas, logs, referência e dados fiscais continuam
locais/gitignored. Uma execução por sessão; trava compartilhada com GUI
na mesma instalação. Repetição do identificador não duplica tarefa;
reinício não repete ações inacabadas. Conclusão remota exige retorno
reconhecido além do resultado positivo. API publica eventos estruturados,
sem OCR livre/capturas/caminhos privados. Sem lote nem rotinas gravadas
no catálogo remoto; chave única do escritório, sem contas individuais.

Integração com Claude: preservar `ee64533`, `b209d71` e `257e90b`
(digitação/hover/fingerprint, revisão/aprovação de rotina e vocabulário
confirmado). Revisão e aprovação agora passam pela fila Tk após finalizar
o worker, para evitar chamadas `root.after` a partir da thread fiscal.

Entrega seguinte: dois instaladores na mesma rede. `Instalar Servidor.bat`
instala componentes e pergunta acesso local/rede; `app/rede_local.py`
gera HTTPS por IPv4 privado e pacote público `data/rede_local/interface_cliente`.
`Instalar Interface.bat` nesse pacote cria atalho Edge/Chrome em janela
própria, sem Python/OCR/Domínio no cliente; endereço salvo, chave informada
na página. Confiança HTTPS é instalada no usuário Windows do cliente.
`atalhos/servidor/Liberar Acesso Rede.bat` é manual, como administrador, restrito à
porta/IP/Python e sub-rede local nos perfis Private/Domain.
`atalhos/servidor/Testar Interface na Rede.bat` simula; `atalhos/servidor/Executar Dominio na Rede.bat`
usa o executor existente. Configuração/CA/chaves permanecem gitignored;
autoridade reaproveitada ao mudar IP. 253 testes passaram, incluindo TLS
real e recusa de hostname divergente. Sintaxe PowerShell conferida;
efeitos Windows (atalho, confiança/firewall) ainda sem rodada real.
O usuário agora propõe o PC atual com Domínio como servidor temporário;
o servidor dedicado definitivo continua sem Domínio informado.

**Divisão de área combinada entre as sessões (08/10/2026, pedido da
usuária, revisão cruzada feita dos dois lados)**: Claude cuida de
percepção (`app/tela.py`, `app/visao.py`), gravador
(`scripts/gravar.py`), `app/rotina_gravada.py`,
`app/registro_elementos.py` e a seção "Rotinas gravadas" da GUI. Codex
cuida de `app/servidor.py`/`api_servidor.py`/`executor_servidor.py`,
`web/`, `app/trava_execucao.py`, `app/tela_principal.py`,
`app/painel.py`, `app/capacidades.py` e infraestrutura de instalação
(PaddleOCR, bootstrap Python). `app/dominio.py` e `scripts/gui.py`
continuam compartilhados, mexidos com cuidado pelos dois (como já vem
acontecendo). Pra `docs/00-analise-e-plano-fase0.md` não repetir número
de seção de novo (já aconteceu, seção 0.70/0.71 duplicada, renumerada
pra 0.81/0.82): **antes de escrever uma seção nova, conferir a última
seção numerada via `git fetch origin` fresco, nunca da memória da
própria sessão.**
GUI preserva resultado desconhecido em vez de OK, grava histórico
atomicamente e impede arquivos/ferramentas de roubar foco durante ações.

### Evidências e preparação anteriores

Leia [RETOMADA.md](RETOMADA.md) para os atalhos e testes Windows,
[ROADMAP-RPA.md](ROADMAP-RPA.md) para os seis incrementos e as seções
0.67 em diante do histórico para as evidências recentes.

O incremento atual é execução/recuperação (2). Há acompanhamento das
quatro rotinas em `app/estados.py`, referência visual local em
`app/tela_principal.py`, calibração por `atalhos/ferramentas/Calibrar Tela Principal.bat`
e proteção das transições de lote quando calibrado. Sem referência,
preserva o fluxo supervisionado anterior; não a aprende automaticamente.
GUI preserva `False` no histórico de SPED/Contribuições. O catálogo
`app/capacidades.py`/`atalhos/ferramentas/Listar Funcoes.bat` descreve funções e pendências,
sem executar ou habilitar agentes. Os novos comportamentos precisam
de validação no Windows; testes simulados não comprovam a sessão real.

Última evidência fiscal Windows: PDF novo foi exportado, conferência recusou o
período, recuperação exigiu foco antes de Esc e o usuário confirmou
retorno à tela principal. A falha de período/nome permanece pausada
pelo usuário. Não altere a conferência para declarar sucesso.

Hugging Face será fonte de componentes locais: consulte
[PROMPT-DESENVOLVIMENTO-HUGGING-FACE.md](PROMPT-DESENVOLVIMENTO-HUGGING-FACE.md)
e [HUGGING-FACE-COMPONENTES.md](HUGGING-FACE-COMPONENTES.md). O primeiro
PaddleOCR é opcional e somente para avaliação, sem substituir Tesseract
ou OCR do Windows. Não enviar capturas/dados fiscais ao Hub ou APIs.

O primeiro teste do instalador Windows encontrou Python 3.14.7 x64,
fora da faixa de wheels do PaddlePaddle fixado (até 3.13). O bootstrap
agora mostra o ambiente e procura um CPython compatível já instalado.
Na repetição, nenhum outro Python compatível foi encontrado. O novo
atalho `atalhos/ocr/Instalar Python OCR.bat` solicita via winget Python 3.13 x64 por
usuário, mantendo PATH/launcher/associações, confirma o intérprete e prepara
OCR. A descoberta também cobre diretórios padrão sem launcher. Não troca
o Python do SPED. A rodada seguinte concluiu inferência Paddle CPU no
Windows; o log não identifica a versão do intérprete usado.

O usuário abriu a avaliação OCR, mas enviou apenas a mensagem Windows de
busca de arquivos, seguida de interrupção e pergunta S/N do CMD. A fonte
PaddlePaddle 3.3.1 procura `ccache` via `where` no Windows; a mensagem
isolada não diagnostica falha de Tesseract nem comprova falha de inferência.
O avaliador agora mostra progresso por leitura, distingue Ctrl+C e informa
o código de saída. `atalhos/ocr/Avaliar OCR Tela.bat` captura a janela ativa em memória
para comparação local, sem ações. Em 07/10/2026, o operador completou
três leituras Paddle e três Tesseract da captura atual. Paddle: inicial
24,751s, aquecidas 14,309/15,802s, 32 segmentos; Tesseract: inicial 0,935s,
aquecidas 0,623/0,576s, 35 segmentos. Paddle levou aproximadamente 25 vezes
mais tempo aquecido nessa captura. O aviso Windows não impediu a conclusão.
Precisão/coordenadas críticas/RAM não foram medidos. Manter Tesseract como
padrão e avançar para validação dos estados e retorno de SPED com a
referência agora calibrada.

`app/tela.py` reutiliza resultados Tesseract somente durante cada checagem
de `esperar_por_estado`: região/pixels/escala exatos, escopo ContextVar,
limpeza ao sair, inclusive após erro. Preserva ordem de detectores,
coordenadas e retornos. 179 testes passaram; não foi adotado Paddle no
fluxo de produção: a primeira comparação Windows mostrou perda de tempo
e não forneceu evidência de ganho de precisão.

Pedido seguinte do usuário: avançar até o RPA completo, incluindo visual.
Entrega atual em `scripts/gui.py`: Painel, Rotinas com rolagem, Funções
disponíveis, Histórico, Projeto e Log. `app/painel.py` é apresentação
pura, sem ações. `estados.observar_eventos` encaminha cópias em ContextVar
à fila da GUI; widgets são atualizados na thread Tk. Falha do observador
não interrompe o motor e não altera o JSONL. Ação enviada não confirma
retorno nem 100% das etapas; recuperação confirmada preserva falha PDF.

Aba Projeto abre as ferramentas locais com os intérpretes existentes;
`scripts/abrir_ferramenta.py` aceita somente calibração/OCR, conserva código
de saída e mantém o Prompt até Enter. Ferramenta aberta impede nova
automação. `False` no resultado agora também aparece como falha na barra
da GUI. 196 testes passaram e visual foi conferido em tela virtual Linux,
com backend fiscal bloqueado/eventos simulados. Revalidação GUI/estados
Windows ainda pendente; não habilitou agentes nem ampliou ações fiscais.
Prévia: `docs/preview-painel.png`, somente dados simulados.

O teste de ciclo Tk real encontrou travamento na antiga finalização
`root.after` chamada da thread de trabalho. Finalização e confirmação de
lote agora passam pela fila para a thread Tk. Ciclo com worker real,
eventos fiscais simulados e diálogos/minimização simulados passou: falha
chega ao painel/histórico e os botões são liberados. Erro OSError ao
gravar histórico avisa no log e preserva finalização/resultado.

Em 07/10/2026, o operador concluiu a calibração real no Windows:
referência salva em `data/tela_principal.json`, captura 1440×900, área
azul `[0, 128, 1377, 823]` e código de saída 0. O resultado também
confirma que o wrapper da ferramenta mantém o Prompt até Enter.
Somente esse relato de medidas foi registrado no Git; a referência e
as capturas permanecem locais. Ainda falta observar retorno automático
com essa referência após uma execução fiscal. Próximo teste: SPED
Fiscal individual, empresa correta e mês anterior com apuração fechada;
conferir documento, `encerrar`/`fim` no log e tela principal ao término.

A nuvem atual consegue executar Tesseract sobre imagens locais/sintéticas
e testes de lógica com dependências de desktop simuladas. Ela não acessa
Domínio/GO-Global nem valida ações Windows. O uso de Win32 para conferir
identidade/foco da janela externa não muda a ausência de UI Automation
nos controles internos da sessão remota.

## Histórico de setembro de 2026

Este documento é um resumo de estado pra retomar o trabalho em outra
sessão/outro assistente, sem precisar reler a conversa inteira. Ele
não substitui a documentação viva do projeto — só orienta por onde
começar. **Antes de mexer em qualquer coisa, leia
[`docs/00-analise-e-plano-fase0.md`](00-analise-e-plano-fase0.md)**,
em especial as seções 0.1 a 0.32 (histórico completo de achados reais,
cada um com causa, correção e se já foi validado ao vivo) e a seção 5
(arquitetura recomendada, segurança/LGPD, princípio de segurança 5.7).

> **Nota de 23/09/2026:** a classificação de erro por IA (item 4 da
> lista de pendências abaixo) foi desenvolvida numa sessão à parte,
> contra uma cópia deste repositório publicada em
> `anthonymaiaxl-oss/Automa-o-Dominio` (pedido do usuário, pra
> revisão), e trazida de volta pra este repositório depois de revisão
> de segurança — que continua sendo o único e o canônico, `main`,
> commit direto, sem PR. Ver seção 0.32 do documento principal.

## O que é o projeto

Motor de automação para operar o **Domínio Escrita Fiscal** (Thomson
Reuters) pela interface gráfica, para a **Lucrattiva Contabilidade**.
Repositório: `cristiane-art/dominio-automation-engine`, branch
`main` (sem fluxo de PR neste repositório — commits vão direto pra
`main`). Projeto irmão do `docauto`
(`cristiane-art/Testes-Para-Automa-o`), que organiza documento fiscal
que **chega** ao escritório; este aqui **opera o próprio Domínio**,
risco maior, por isso em repositório separado.

Objetivo prático imediato: gerar automaticamente, por empresa, os
arquivos **SPED Fiscal** (EFD ICMS/IPI) e/ou **EFD Contribuições**
(PIS/COFINS), navegando pela interface do Domínio como um usuário
faria — sem digitar comando nenhum além de abrir um `.bat` e responder
um menu simples.

## Restrição técnica central (não negociável)

O Domínio Escrita Fiscal, no ambiente da Lucrattiva, **não roda
localmente** — é entregue via **GraphOn GO-Global**, um protocolo de
renderização remota (a tela é pixel renderizado remotamente, a janela
local é só um "espelho"). Isso significa:

- **UI Automation / Win32 (encontrar controles pelo nome, IDs de
  botão, etc.) não funcionam** — não existe uma árvore de controles
  local pra inspecionar.
- A única forma de **ler o estado da tela** é OCR (`pytesseract`) sobre
  screenshot (`PIL.ImageGrab`).
- A única forma de **agir** é mouse/teclado sintético (`pyautogui`).
- Tudo que parece "óbvio" em automação de desktop Windows normal (ex.:
  `pywinauto`, `uiautomation`) não se aplica aqui.

Esse é o motivo de toda a arquitetura do projeto e da maior parte dos
achados documentados — releia isso antes de propor qualquer atalho que
dependa de inspecionar a janela por fora do OCR.

## Ambiente de desenvolvimento vs. ambiente de teste real

- **Este ambiente (sandbox Linux na nuvem) não roda `pyautogui` nem
  `pytesseract` de verdade** (sem X11, sem `ctypes.windll`, etc.).
  Tudo que é escrito aqui só pode ser **validado por sintaxe**
  (`python3 -m py_compile arquivo.py`) e por teste unitário de lógica
  pura (ex.: `competencia_anterior()`, `documentos_necessarios()`).
- **Todo teste de verdade acontece no Windows do usuário**, com o
  Domínio aberto e visível na tela. O fluxo de trabalho estabelecido
  é: eu edito o código aqui, faço commit e push pra `main`; o usuário
  roda `Atualizar.bat` (que é só um `git pull origin main`) na máquina
  dele, testa, e cola de volta o log de saída (a rotina imprime muito
  debug de OCR de propósito) — eu leio o log, diagnostico pela
  evidência, corrijo, e o ciclo se repete.
- **Nunca proponha uma correção sem uma explicação concreta baseada em
  evidência do log/print real.** Esse projeto tem um histórico forte
  de "achado real → causa → correção", documentado seção por seção; um
  chute sem log pra sustentar é contra o espírito do projeto inteiro.

## Estrutura do repositório

```
app/
  tela.py        — captura de tela, recorte e OCR (achar_texto, achar_texto_ou_no_centro,
                   recortar_topo, recortar_area_menu, recortar_ao_redor,
                   recortar_a_partir_de, recortar_centro, salvar)
  interacao.py   — foco de janela, clique, hover, teclado (focar_dominio,
                   clicar, clicar_com_desvio, passar_mouse, pressionar_tecla,
                   pressionar_enter, selecionar_tudo, selecionar_tudo_alternativo,
                   digitar)
  empresas.py    — carrega/filtra data/empresas.csv (por regime, tipo de
                   documento); tolera UTF-8 ou cp1252; distingue arquivo
                   real de arquivo de exemplo no log
  erros.py       — decide o que fazer com uma caixa de erro/aviso
                   desconhecida: anonimiza o texto, procura em catálogo
                   fixo/aprendido, só então consulta ia.py; ação sempre
                   restrita a PULAR/TENTAR_DE_NOVO/CONTINUAR/PARAR_LOTE
  ia.py          — chamada à API da Anthropic (Claude Haiku), só com
                   texto já anonimizado, resposta em JSON Schema fechado
  dominio.py     — orquestração de alto nível: trocar_empresa(), gerar_sped()
                   (genérico pra SPED Fiscal e EFD Contribuições),
                   gerar_sped_fiscal(), gerar_efd_contribuicoes(),
                   competencia_anterior(), selecionar_competencia_anterior(),
                   executar_lote() (loop por empresa/documento com resumo final)
  visao.py       — fallback de visão por IA (seção 0.58), ÚLTIMO recurso de
                   percepção, só depois de OCR/OpenCV falharem — ver regra de
                   segurança acima antes de mexer aqui
scripts/
  app.py                    — menu único (o que `atalhos/ferramentas/Abrir Motor SPED.bat` roda)
  explorar.py                — SPED Fiscal numa empresa só (já selecionada)
  explorar_contribuicoes.py  — EFD Contribuições numa empresa só
  explorar_competencia.py    — testa só a seleção de competência, isolado
  trocar_empresa.py          — troca de empresa via F8, isolado
  selecionar_empresas.py     — só carrega/filtra a planilha, não roda nada
  executar_lote.py           — lote completo (--real pra usar dado real)
data/
  empresas.exemplo.csv  — dados fictícios, versionado, seguro de testar
  empresas.csv           — dados REAIS de cliente, gitignored, nunca sobe
docs/
  00-analise-e-plano-fase0.md — documento vivo, histórico completo (leia antes de tudo)
  HANDOFF.md                   — este arquivo
README.md                — visão geral e instruções de uso
atalhos/ferramentas/Abrir Motor SPED.bat      — atalho de duplo clique, roda scripts/app.py
Atualizar.bat             — atalho de duplo clique, roda git pull origin main
```

## Como o motor funciona, resumido

1. **Foco.** `interacao.focar_dominio()` clica no meio da tela pra
   garantir que a janela do Domínio está em foco antes de qualquer
   ação — chamado no início de `trocar_empresa()` e de `gerar_sped()`,
   não só uma vez no começo do lote (achado da seção 0.28: o foco pode
   se perder no meio de um lote longo).
2. **Troca de empresa** (`trocar_empresa(codigo)`): F8 → OCR acha o
   botão "Acessar" (não o título, que não lê bem) → digita o código →
   clica Acessar (não precisa clicar na linha, ela já fica selecionada
   sozinha) → **espera por estado** até "Acessar" sumir da tela antes
   de considerar concluído (não um tempo fixo).
3. **Geração de documento** (`gerar_sped(item_menu, texto_confirmacao)`,
   uma função só reaproveitada pelos dois documentos):
   - Navega Relatórios → Informativos → Federais → item de menu
     (`"SPED Fiscal"` ou `"Contribui"`), com hover em cascata; o
     último clique usa `clicar_com_desvio()` (move em L, não em linha
     reta) pra não passar o mouse por cima do item vizinho ("Estaduais")
     e trocar o submenu aberto sem querer (seção 0.24).
   - **Sempre** sobrescreve o período com o mês fechado anterior ao
     atual (`competencia_anterior()`/`selecionar_competencia_anterior()`),
     nunca confia no que já estiver na tela — e confere por OCR, depois
     de digitar, que os dois campos realmente mudaram (campo mascarado,
     `Ctrl+A` não funciona nele; usa `Home`+`Shift+End` e digita só
     dígitos).
   - Clica "OK" — mas o texto "OK" (2 letras) é **estruturalmente
     ilegível pro OCR** nesta aplicação, em qualquer zoom/recorte já
     tentado. A posição de "OK" é sempre **calculada por aritmética** a
     partir de "Fechar" (um botão vizinho, sempre legível), usando o
     espaçamento vertical entre "Fechar" e "Empresas..." como
     referência — nunca tenta ler "OK" diretamente (seção 0.13/0.22).
   - Espera a confirmação de sucesso **por estado**, não por tempo
     fixo, com um teto de ~90 tentativas de 2s (~3 minutos) — empresa
     real com bastante movimento demora bem mais que a de teste pra
     exportar (seção 0.27). Cada tentativa também verifica se apareceu
     uma caixa de erro do Domínio (título "Atenção") em vez de insistir
     esperando um sucesso que não vai vir (seção 0.25).
   - Fecha a confirmação com **Enter** (não clique — mesmo problema do
     "OK" ilegível), com até 3 tentativas de confirmar que fechou de
     verdade antes de concluir "não fechou" (a tela remota pode demorar
     mais que 1s pra repintar — seção 0.28).
   - Fecha a tela de geração clicando em "Fechar" (achado por recorte a
     partir do título) — com retry (até 3x) tanto pro título quanto pro
     "Fechar" antes de desistir, e **sempre tenta fechar em toda saída
     com falha**, não só no caminho de sucesso — deixar a tela aberta
     contaminava o próximo passo do lote (seções 0.26/0.30).
4. **Lote** (`executar_lote()`): carrega `data/empresas.csv` (ou o
   arquivo de exemplo), pergunta o regime (Simples/Presumido/Real),
   confirma com o usuário, e roda troca de empresa + geração de 1 ou 2
   documentos por empresa (`empresas.documentos_necessarios()`, colunas
   `tipo`/`sped` da planilha) — falha isolada por empresa/documento,
   nunca trava o lote inteiro, resumo no final.

## Achado técnico mais importante pra internalizar

**Um texto sendo visível e legível numa screenshot não garante que o
OCR de tela inteira vai achá-lo.** Telas densas (muito campo, muito
texto competindo pela segmentação do Tesseract) fazem o OCR falhar de
forma **determinística e repetida**, não por timing — já visto pelo
menos três vezes, em pontos diferentes (botão "OK", seção 0.10;
confirmação "Final da exportação.", seção 0.29; próprio título do
diálogo, seção 0.26). A técnica que resolve, sempre: **nunca ler o
alvo direto na tela inteira quando dá pra evitar** — ou recorta uma
área pequena a partir de uma âncora confiável já achada
(`recortar_ao_redor`/`recortar_a_partir_de`), ou, quando não há âncora
prévia conhecida (ex.: uma caixa de diálogo que pode aparecer em
qualquer posição), tenta um recorte central genérico como reforço
(`tela.achar_texto_ou_no_centro()`, seção 0.29) — nunca inventa
coordenada fixa, sempre recalcula pela OCR de cada rodada.

## Status atual (22/09/2026)

- ✅ SPED Fiscal e EFD Contribuições **já rodaram de ponta a ponta com
  sucesso** contra empresa real, incluindo troca de empresa e seleção
  automática de competência.
- ✅ Interface de linha de comando simples (`scripts/app.py` + os dois
  `.bat`) funcionando — "abre o Domínio, aperta no atalho, escolhe uma
  opção do menu".
- ⚠️ **Muitas correções foram feitas hoje (22/09), em sequência, cada
  uma respondendo a um log real de teste em lote contra empresas
  reais** (ver seções 0.24 a 0.30 do documento principal). O padrão do
  dia foi: rodar o lote, achar um jeito novo de travar, corrigir,
  repetir — típico de sistema ainda em amadurecimento. **Ainda não
  houve uma rodada completa do lote inteiro, contra várias empresas
  reais, incorporando TODAS as correções de hoje ao mesmo tempo** — a
  validação combinada é o próximo passo natural.
- ⚠️ Ainda não fizemos a validação de **conteúdo** prevista na seção
  5.7 (gerar o SPED de uma competência já fechada e comparar com o que
  foi entregue de verdade) — até agora só validamos que o **mecanismo**
  funciona (o arquivo é gerado sem travar), não que o conteúdo bate.
- ✅ Classificação de erro/aviso desconhecido por IA implementada
  (`app/erros.py` + `app/ia.py`, seção 0.32) — catálogo fixo +
  aprendido + Claude Haiku como último recurso, ação sempre restrita a
  uma lista fechada (pular/tentar de novo/continuar/parar o lote).
  **Ainda não testada contra o Domínio real** (só teste unitário de
  lógica pura, mesma limitação de sempre deste ambiente) — falta
  confirmar que o recorte em volta da caixa "Aviso Empresa" captura o
  texto inteiro, que clicar em "No" por OCR funciona na caixa Sim/Não
  de verdade, e que a IA (com chave configurada) classifica um erro
  nunca visto de forma sensata.

## Pendências / próximos passos sugeridos

1. Rodar o lote completo, acompanhado (não sem supervisão ainda), pra
   confirmar que as correções de hoje resolvem juntas — inclui validar
   a classificação de erro por IA contra uma caixa real pela primeira
   vez (ver acima).
2. Se aparecer uma falha nova: pedir o log da rotina (ela já imprime
   bastante debug de OCR de propósito) antes de propor qualquer
   correção — nunca chutar.
3. Considerar, só depois do lote está estável, a validação de conteúdo
   da seção 5.7.
4. Itens de roadmap mencionados mas não iniciados: máquina de estados
   formal (seção 5.6), painel/servidor distribuído (adiado de
   propósito).

## Regras de segurança que não podem ser flexibilizadas

- **LGPD**: `data/empresas.csv` (dado real de cliente) é gitignored e
  nunca deve ser commitado. `capturas/` (screenshots, podem conter
  dado fiscal) também é local, nunca versionado.
- **IA/LLM**: uso permitido só pra classificação estruturada de erro
  (texto/estatística anonimizada), nunca decisão autônoma sobre ação
  no Domínio (seção 5.5) — implementado em `app/erros.py`/`app/ia.py`:
  a IA só escolhe entre 4 ações fixas (`erros.ACOES`), só recebe texto
  já anonimizado (`erros.anonimizar()`), e
  `data/chave_api.txt`/`data/erros_aprendidos.json`/
  `data/ia_envios.log` ficam locais (gitignored), nunca sobem pro
  GitHub.
  - **Exceção controlada, decisão do usuário em 05/10/2026 (seção
    0.58)**: `app/visao.py` pode enviar uma IMAGEM (não só texto) pra
    IA, mas só como ÚLTIMO recurso de percepção (depois de OCR e
    casamento de imagem OpenCV já falharem) e só depois de uma
    verificação LOCAL (`visao._contem_dado_sensivel()`, OCR + checagem
    própria — mais conservadora que `erros.anonimizar()`, ver
    docstring do módulo) não achar nada que pareça dado real (número,
    nome de empresa em maiúsculo, caminho, e-mail) na imagem. Se achar,
    recusa automaticamente, sem exceção. A resposta da IA é sempre de
    um formato fechado (coordenada ou classificação de estado, nunca
    ação) e toda imagem efetivamente enviada fica salva em
    `data/visao_enviado/` (gitignored) pra auditoria. **Esta é a única
    exceção à regra "nunca manda print pra IA"** — qualquer uso de
    imagem fora de `app/visao.py` continua proibido.
- **Operação sempre reversível**: o motor só **gera** (nunca calcula
  do zero, nunca transmite) obrigação, e a validação de conteúdo real
  só deve ser feita sobre competência **já fechada e já entregue no
  passado** (seção 5.7) — nunca sobre a competência corrente/em aberto
  (por isso a seleção automática de competência anterior existe e é
  obrigatória em todo o fluxo).

## Convenções de trabalho estabelecidas nesta conversa

- Commits vão direto pra `main`, sem PR, neste repositório.
- Toda correção de código ganha uma entrada numerada na seção 0.x do
  documento principal (`docs/00-analise-e-plano-fase0.md`), no mesmo
  formato: o que aconteceu (com evidência do log), a causa raiz, a
  correção, e se já foi validada ao vivo ou ainda não.
- `README.md` é atualizado sempre que o comportamento visível ao
  usuário muda (ex.: uma limitação documentada que deixou de existir).
- Validação de sintaxe (`python3 -m py_compile`) antes de todo commit
  que toca código Python — é o único teste automatizado possível neste
  ambiente.
