# Domínio Automation Engine — handoff

## Estado para retomada em 07/10/2026

Repositório atual: `financeirolucrattiva-web/dominio-automation-engine`,
branch remoto `main`. Codex e Claude Code podem trabalhar juntos;
confira alterações e versão remota antes de publicar, sem force push.
O texto abaixo deste checkpoint mantém o histórico de setembro.

Leia [RETOMADA.md](RETOMADA.md) para os atalhos e testes Windows,
[ROADMAP-RPA.md](ROADMAP-RPA.md) para os seis incrementos e as seções
0.67 em diante do histórico para as evidências recentes.

O incremento atual é execução/recuperação (2). Há acompanhamento das
quatro rotinas em `app/estados.py`, referência visual local em
`app/tela_principal.py`, calibração por `Calibrar Tela Principal.bat`
e proteção das transições de lote quando calibrado. Sem referência,
preserva o fluxo supervisionado anterior; não a aprende automaticamente.
GUI preserva `False` no histórico de SPED/Contribuições. O catálogo
`app/capacidades.py`/`Listar Funcoes.bat` descreve funções e pendências,
sem executar ou habilitar agentes. Os novos comportamentos precisam
de validação no Windows; testes simulados não comprovam a sessão real.

Última evidência Windows: PDF novo foi exportado, conferência recusou o
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
atalho `Instalar Python OCR.bat` solicita via winget Python 3.13 x64 por
usuário, mantendo PATH/launcher/associações, confirma o intérprete e prepara
OCR. A descoberta também cobre diretórios padrão sem launcher. Não troca
o Python do SPED. Instalação/seleção ainda precisam de teste Windows.

O usuário abriu a avaliação OCR, mas enviou apenas a mensagem Windows de
busca de arquivos, seguida de interrupção e pergunta S/N do CMD. A fonte
PaddlePaddle 3.3.1 procura `ccache` via `where` no Windows; a mensagem
isolada não diagnostica falha de Tesseract nem comprova falha de inferência.
O avaliador agora mostra progresso por leitura, distingue Ctrl+C e informa
o código de saída. `Avaliar OCR Tela.bat` captura a janela ativa em memória
para comparação local, sem ações. Teste Windows ainda pendente.

`app/tela.py` reutiliza resultados Tesseract somente durante cada checagem
de `esperar_por_estado`: região/pixels/escala exatos, escopo ContextVar,
limpeza ao sair, inclusive após erro. Preserva ordem de detectores,
coordenadas e retornos. 179 testes passaram; não foi adotado Paddle no
fluxo de produção por ausência de comparação real que demonstre ganho.

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
  app.py                    — menu único (o que `Abrir Motor SPED.bat` roda)
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
Abrir Motor SPED.bat      — atalho de duplo clique, roda scripts/app.py
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
