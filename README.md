# Domínio Automation Engine

Motor de automação para operar o **Domínio Escrita Fiscal** (Thomson
Reuters) pela interface, para a Lucrattiva Contabilidade — começando por
uma rotina ligada a SPED. Projeto irmão do
[`docauto`](https://github.com/cristiane-art/Testes-Para-Automa-o) (que
organiza documento fiscal que **chega** ao escritório); este aqui **opera
o próprio Domínio**, risco maior, repositório separado de propósito.

## Estado atual: Fase 4 — primeira geração real confirmada (em empresa de teste)

👉 **[docs/00-analise-e-plano-fase0.md](docs/00-analise-e-plano-fase0.md)**
— riscos técnicos, achados confirmados (Domínio é entregue via GraphOn
GO-Global, não local), arquitetura recomendada, roadmap e o histórico
completo de cada descoberta técnica. **Leia isso antes de mexer em
qualquer coisa neste repositório** — economiza reaprender o que já foi
resolvido na marra (foco de janela, recorte de OCR, etc).

Já validado com o Domínio de verdade: ler estado da tela (empresa,
período, menu) por OCR, achar posição de texto pra clicar, focar a
janela antes de agir, clicar e passar o mouse (hover) de forma real,
navegar sozinho até a tela de geração da EFD ICMS/IPI (SPED Fiscal),
clicar OK, **confirmar sucesso da geração ("Final da exportação.")** e
fechar a tela sozinho — ponta a ponta, sem intervenção manual no meio
(seção 0.11 do documento acima).

**Rodado até agora só em empresa de teste**, de propósito — prova que o
mecanismo funciona, mas ainda não serve como validação de conteúdo (não
tem arquivo real entregue no passado pra comparar). O período (Data
inicial/final) é **selecionado sozinho** — sempre o mês fechado
anterior ao atual, nunca o corrente (seção 0.23) — não precisa (e não
adianta) configurar isso na tela antes de rodar. Antes de rodar contra
a empresa-alvo real, só confira que ela está selecionada (não a
empresa de teste).

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Precisa também do Tesseract instalado com o idioma português (`por`) —
mesmo binário já usado pelo projeto irmão `docauto`.

### Instalar em outro computador (operador)

Pra um computador novo, de outro operador do escritório (seção 0.41 do
documento) — sem editor de código, só usando os atalhos `.bat`:

1. Baixe os arquivos do projeto nesse computador — o jeito mais simples
   é abrir a página do repositório no GitHub, **Code → Download ZIP**,
   e extrair a pasta. Não copie a pasta `data\` de outro computador pra
   essa cópia nova — ela é local (dado de cliente, chave de API); a
   cópia nova começa vazia.
2. Instale o Python, se ainda não tiver: <https://www.python.org/downloads/>
   — na instalação, marque **"Add Python to PATH"**.
3. Instale o Tesseract OCR com o idioma português:
   <https://github.com/UB-Mannheim/tesseract/wiki> — marque o pacote de
   idioma **"Portuguese"**, e confirme que ele foi adicionado ao PATH
   (o instalador pergunta isso numa das telas).
4. Dentro da pasta do projeto, dê duplo clique em **`Instalar.bat`** —
   ele confere se Python/Tesseract estão presentes e instala o resto
   sozinho (`pip install -r requirements.txt`).
5. Copie `data\empresas.exemplo.csv` para `data\empresas.csv` e
   preencha com as empresas de verdade desse operador.
6. No dia a dia, use **`Abrir Interface Gráfica (Operador).bat`** —
   igual à completa, menos o botão de empresas de EXEMPLO e a seção
   "Criar automação nova" (gravador, seção 0.35). O botão de lote
   aparece como **"Rodar SPED"** nesse modo (seção 0.45).

**Ainda não testado num computador novo de verdade** — `Instalar.bat`
e o modo operador seguem o mesmo padrão já validado do resto dos
atalhos `.bat`, mas, como todos eles, só um teste real confirma (esta
sessão não roda Tkinter/pyautogui, seção 0.1).

## Uso

### Jeito fácil (recomendado)

Com o Domínio Escrita Fiscal aberto e visível na tela, dá duplo clique
em **`Abrir Motor SPED.bat`** (na raiz desta pasta). Abre um menu
numerado (rodar em lote por regime, trocar empresa, gerar SPED numa
empresa só) — não precisa digitar comando nenhum (seção 0.18 do
documento). A janela fica aberta no final pra você ler o resultado.

Antes, se fizer um tempo que você não mexe nisso, dá duplo clique em
**`Atualizar.bat`** primeiro, pra puxar as correções mais recentes do
GitHub — ele já confere/instala dependência nova sozinho
(`pip install -r requirements.txt`), não precisa rodar isso à parte.

**Novo, ainda em teste:** `Abrir Interface Gráfica.bat` — mesmas ações,
em janela com botão em vez de menu numerado, visual modernizado
(`ttkbootstrap`), abas "Rotinas"/"Histórico" (lista as últimas
execuções, com botão pra abrir o arquivo gerado ou a pasta de saída —
seção 0.57 do documento), e o andamento aparece numa caixa de texto na
própria janela. Não substitui `Abrir Motor SPED.bat` ainda — os dois
convivem até a interface gráfica ser validada contra o Domínio real
pela primeira vez.

Precisa de `data/empresas.csv` (separado por `;`) pras opções de lote —
copie `data/empresas.exemplo.csv` e preencha com as empresas de
verdade; esse arquivo é seu, local, nunca sobe pro GitHub. Colunas:

- `codigo`, `apelido`, `regime` — sempre precisou disso.
- `tipo` — `1` (um documento só) ou `2` (os dois documentos abaixo,
  ignora a coluna `sped`). Opcional; sem ela, vira `1`.
- `sped` — qual documento gerar quando `tipo` é `1`: "ICMS" ou
  "Contribuições" (seção 0.20 do documento). Opcional; sem ela, vira
  "ICMS". **EFD Contribuições confirmada rodando de ponta a ponta pelo
  próprio código** (seção 0.40), mesmo nível de validação do SPED
  Fiscal/ICMS.

### Scripts individuais (linha de comando)

Cada opção do menu também roda direto por comando, se preferir:

```bash
python scripts\explorar.py               # gera o SPED Fiscal (ICMS) na empresa já selecionada
python scripts\explorar_contribuicoes.py # gera a EFD Contribuições na empresa já selecionada
python scripts\explorar_registro_saidas.py # gera o Livro Registro de Saídas (ver aviso abaixo)
python scripts\trocar_empresa.py         # troca de empresa via F8 (código fixo no arquivo)
python scripts\selecionar_empresas.py    # só carrega e filtra a lista por regime, não roda nada
python scripts\executar_lote.py          # troca de empresa + gera, para cada empresa de um regime
python scripts\executar_lote.py --real   # idem, mas com data/empresas.csv (planilha real)
```

**`explorar_registro_saidas.py` parcialmente testado contra o Domínio
real** (seção 0.57 do documento, 3 execuções em 01/10/2026) —
navegação, marcar "Registro de Saídas", preencher período e clicar OK
já confirmados; falta confirmar a exportação completa pra PDF (ícone
achado por casamento de imagem, confiança 1.0, mas a geração do
arquivo em disco ainda não terminou numa execução real). Rode com
atenção, leia o log, e espere precisar de mais algum ajuste.

`explorar.py` navega Relatórios → Informativos → Federais → SPED
Fiscal, clica OK, confirma o aviso "Final da exportação." e fecha a
tela — salvando cada etapa em `capturas/` (pasta local, nunca
versionada — pode conter tela real com dado fiscal). Já reconhece
caixa de erro/aviso do Domínio (títulos "Atenção" e "Aviso Empresa" —
seção 0.25/0.32 do documento): salva print, decide o que fazer
(`app/erros.py`) e segue sem travar o lote.

### Arquivos dos Livros Fiscais

Registro de Saídas e Registro de Entradas salvam PDFs em `saida/` com
nome por tipo, nome da empresa e competência, por exemplo
`registro_saidas_EMPRESA_EXEMPLO_2026-08.pdf`. O nome é lido no canto
superior direito do Domínio, removendo o código final `- número` e
normalizando espaços/acentos para um nome de arquivo válido. Uma nova
rodada preserva o PDF anterior e usa um sufixo no novo nome.

A exportação começa em um caminho exclusivo. O motor só anuncia
sucesso depois de abrir o novo PDF e conferir tipo, período e CNPJ no
cabeçalho; um arquivo antigo existente não comprova uma nova geração.
Se a conferência falhar, o arquivo temporário fica para diagnóstico.
A leitura do nome por OCR ainda precisa de validação contra o Domínio
real. Se o cabeçalho não puder ser identificado, o motor para antes de
navegar e salva a captura para diagnóstico; não usa o nome de uma
rodada anterior. O CNPJ continua sendo conferido internamente no PDF.

Nos scripts individuais, `--cnpj` permite conferir a empresa esperada;
sem esse argumento, o CNPJ é identificado no próprio PDF, mas não
comparado com uma empresa esperada. Os argumentos
`--data-inicial` e `--data-final` recebem datas em `DD/MM/AAAA` de uma
competência cuja apuração já esteja fechada. A interface gráfica
continua usando os campos de período existentes.

### IA de decisão em erro desconhecido (opcional)

Quando aparece uma caixa de erro/aviso do Domínio que o motor nunca
viu, ele consulta uma IA leve (Claude Haiku) pra decidir entre um
conjunto fixo de ações (pular a empresa, tentar de novo, só continuar,
ou parar o lote inteiro) — nunca uma ação livre. **A IA nunca vê a
tela**: recebe só o texto da caixa, lido por OCR na sua própria máquina
e anonimizado antes de sair dela (número, caminho de arquivo, e-mail e
nome em maiúsculo viram marcador genérico —
`docs/00-analise-e-plano-fase0.md`, seção 0.32). Toda decisão da IA
vira regra local (`data/erros_aprendidos.json`, nunca sobe pro
GitHub) — o mesmo erro não consulta a IA de novo.

Sem chave configurada, o motor simplesmente pula essa empresa (mesmo
comportamento de sempre, sem IA nenhuma). Pra configurar: opção 6 do
menu, ou salve a chave em `data/chave_api.txt` (uma linha só). Chave
grátis/paga em <https://console.anthropic.com/settings/keys>.

Com a mesma chave, o motor também usa a IA em três pontos a mais —
**nunca decide nem executa um clique** (seção 0.49/0.51 do
documento):

- **Resumo do lote em português simples**, no final de "Rodar em
  lote" — só texto, um parágrafo curto complementando o resumo
  técnico, a partir só de código de empresa e resultado (nunca o
  apelido).
- **Nova tentativa quando uma busca de texto na tela falha**
  (`achar_ou_parar()`) — a IA escolhe entre 5 técnicas de releitura já
  usadas neste projeto (mais zoom, recorte central, print novo, OCR
  nativo do Windows como segunda opinião, ou desistir); nunca escreve
  código nem decide onde clicar — só como ler a tela de novo. Até 2
  tentativas antes de desistir de vez.
- **Palpite final**, se nem assim resolver — hipótese em texto do que
  pode ter acontecido, pra ajudar a corrigir à mão.

Os três somem sozinhos sem chave configurada, sem afetar o resto.

### Criar e promover uma automação nova

1. Grave o caminho: botão "Criar automação nova" na interface (ou
   `python scripts\gravar.py`) — clique normal nos passos, F12 pra
   parar. Gera um rascunho em `capturas/gravacao_.../rascunho.py`.
2. Revise o rascunho contra os prints da mesma pasta: confira cada
   texto adivinhado, complete hover/digitação à mão (o gravador só
   grava clique, seção 0.39), e troque busca de texto curto/tela densa
   ("OK", "Fechar") pelo padrão de `_fechar_tela_geracao()` em vez de
   `achar_ou_parar()` na tela inteira (seção 0.46 do documento).
3. Teste contra o Domínio de verdade até rodar limpo.
4. Cole a função final em `app/dominio.py` (mesmo padrão de
   `gerar_sped_fiscal()`) e acrescente uma linha em
   `AUTOMACOES_EXTRAS`, no mesmo arquivo:
   `("Nome que aparece no menu", nome_da_funcao),`.
5. Suba pro GitHub — `Atualizar.bat` leva a opção nova pro menu de
   texto e pra interface gráfica de todo mundo sozinho, sem editar
   `scripts/app.py` nem `scripts/gui.py` (seção 0.48 do documento).

- `app/tela.py` — captura de tela, recorte e leitura de texto (OCR),
  com os ajustes já validados (recorte por região, pré-processamento
  pra texto dentro de menu suspenso).
- `app/interacao.py` — foco de janela, clique, hover, tecla e digitação
  de texto, com os ajustes já validados (foco obrigatório antes de
  clicar, clique "devagar", Enter pra diálogo de um botão só).
- `app/dominio.py` — ações de alto nível (`trocar_empresa()`,
  `gerar_sped_fiscal()`), reaproveitadas pelos scripts isolados e pelo
  lote.
- `app/empresas.py` — carrega e filtra `data/empresas.csv` por regime.
- `app/erros.py` — decide o que fazer com uma caixa de erro/aviso:
  anonimiza o texto, procura no catálogo conhecido/aprendido e, se
  precisar, consulta `app/ia.py`.
- `app/ia.py` — chamada à API da Anthropic (Claude Haiku), só com
  texto anonimizado, resposta restrita a uma lista fechada de ações.
- `app/historico.py` — registro local de cada execução rodada pela
  interface gráfica (`data/historico_execucoes.json`, gitignored),
  consultado na aba "Histórico" (seção 0.57).
- `app/verificacao.py` — confere o conteúdo de um arquivo exportado
  (empresa/período batem com o esperado), não só se o arquivo existe.
- `scripts/explorar.py` — gera o SPED Fiscal numa empresa só (a que já
  estiver selecionada no Domínio).
- `scripts/trocar_empresa.py` — troca a empresa selecionada via F8.
- `scripts/selecionar_empresas.py` — só carrega e filtra a lista por
  regime, não roda nada.
- `scripts/executar_lote.py` — troca de empresa + gera o SPED Fiscal
  pra cada empresa do regime escolhido.
- `scripts/app.py` — menu único (texto) que reúne as opções acima; é o
  que `Abrir Motor SPED.bat` roda.
- `scripts/explorar_registro_saidas.py` — gera o Livro Registro de
  Saídas numa empresa só (ver aviso na seção "Scripts individuais"
  acima — parcialmente validado).
- `scripts/gui.py` — mesmas ações, em janela (`ttkbootstrap`, abas
  Rotinas/Histórico); é o que `Abrir Interface Gráfica.bat` roda
  (seção 0.33, reescrita visualmente na seção 0.57 — ainda em teste
  contra o Domínio real).
- `scripts/gravar.py` — grava clique manual no Domínio e gera o
  rascunho de uma automação nova (seção 0.35; pipeline completo
  validado de ponta a ponta na seção 0.47) — gera rascunho pra
  revisar, não automação pronta; hover não é gravado, só clique
  (seção 0.39), precisa completar à mão. Também disponível
  como botão na interface gráfica ("Criar automação nova").
- `Instalar.bat` — prepara um computador novo (Python/Tesseract já
  instalados, só falta a dependência Python do projeto) — seção 0.41,
  pensado pra instalar num computador de outro operador.
- `Abrir Motor SPED.bat` / `Abrir Interface Gráfica.bat` /
  `Abrir Interface Gráfica (Operador).bat` / `Atualizar.bat` — atalhos
  de duplo clique (raiz do repositório) pro dia a dia, sem linha de
  comando. A versão "(Operador)" esconde só "Criar automação nova"
  (gravador) e o botão de empresas de EXEMPLO (seção 0.45) — pensada
  pro computador de outro operador.

## Histórico deste repositório

Este nome (`dominio-automation-engine`) reaproveita um repositório que
antes tinha um projeto sem relação nenhuma com este (um agente de redes
sociais da Lucrattiva) — mantido em duplicidade em outra conta e removido
daqui por decisão do escritório em 18/09/2026. O conteúdo antigo continua
recuperável no histórico do Git (`git log`), caso necessário.
