# Domínio Automation Engine — handoff

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
