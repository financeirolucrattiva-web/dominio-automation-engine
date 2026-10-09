# Domínio Automation Engine — análise inicial e plano da Fase 0

> **O que é este documento.** Resposta ao briefing do "Domínio Automation
> Engine" (nome provisório): motor reutilizável para operar o **Domínio
> (Thomson Reuters) pela interface**, começando por uma rotina ligada a
> SPED. Por pedido explícito do briefing, **nenhum código de automação foi
> escrito ainda** — isto é análise, riscos, descobertas necessárias,
> arquitetura recomendada, roadmap e o plano da Fase 0.
>
> **Isto é um projeto separado do `docauto`**
> (<https://github.com/cristiane-art/Testes-Para-Automa-o>), que organiza
> documento fiscal que **chega** ao escritório. O Domínio Automation
> Engine vai **operar o próprio Domínio** pela tela — comando inverso,
> risco maior (grava/processa em vez de só ler e copiar). Por isso vive em
> repositório próprio.
>
> **A análise original que deu origem a este documento** foi feita no
> repositório do `docauto`
> (PR <https://github.com/cristiane-art/Testes-Para-Automa-o/pull/2>) e
> migrada para cá quando este repositório passou a existir (18/09/2026).
> Consulte aquela PR se quiser o histórico completo da discussão; este
> arquivo já incorpora todas as decisões tomadas lá.

---

## Checkpoint — 21/09/2026 (retomar por aqui)

**Marco da sessão: primeira geração real ponta a ponta, com sucesso
confirmado pelo próprio Domínio** ("Final da exportação.", seção 0.11)
— rodada contra uma **empresa de teste**, deliberadamente, não a
empresa-alvo real. Mecanismo provado; falta rodar contra a empresa-alvo
real com competência verificada (item 1 abaixo) pra virar o oráculo de
verificação da seção 5.7.

**Provado nesta sessão, além de tudo que já estava provado em 18/09
(lista abaixo):**
- Clique sintético real funciona na tela remota do GO-Global, desde que
  o Domínio esteja **em foco** no momento do clique (seção 0.6).
- OCR dentro de menu suspenso só funciona com pré-processamento (2x de
  tamanho + tons de cinza) antes de rodar (seção 0.7).
- Hover (sem clicar) realmente abre submenu em cascata — confirmado
  ponta a ponta, não é mais hipótese.
- **Navegação completa e reproduzível por script**: Relatórios →
  Informativos → Federais → SPED Fiscal, chegando na tela real de
  geração da EFD ICMS/IPI (seção 0.8).
- Código organizado em `app/tela.py`, `app/interacao.py`,
  `scripts/explorar.py` — a estrutura da seção 5.2 saiu de "proposta"
  para "existe e funciona".
- Bug de correspondência OCR multi-palavra corrigido (testar janela de
  1 palavra em todas as posições antes de tentar 2/3/4 palavras juntas
  — senão um alvo mais longo por coincidência vence o certo).
- **Texto curto (2 letras, ex. "OK") dentro de tela densa precisa de
  âncora + recorte**, não de OCR de tela inteira nem de recorte fixo
  (seção 0.10).
- **Geração real confirmada com sucesso** ("Final da exportação.") —
  responde a pergunta 9 da seção 3.2: mensagem de resultado é uma caixa
  de diálogo padrão do Windows, pequena e simples (seção 0.11).
- Script agora vai ponta a ponta: navega, clica OK, confirma o aviso
  de sucesso, e fecha a tela do SPED Fiscal sozinho.

**Ficou em aberto:**
1. **Repetir esta mesma rotina na empresa-alvo real (fora do Simples
   Nacional) só depois de confirmar** (seção 0.8): (a) ela está
   selecionada, não a `HABITA PROJETOS -78`/empresa de teste; (b) a
   competência usada já foi de fato fechada e entregue por ela antes —
   só assim vira o oráculo de verificação da seção 5.7, comparando o
   arquivo gerado agora com o que foi entregue de verdade.
2. Levantamento das competências já entregues da empresa-alvo (pergunta
   3 da seção 3.1) continua não feito — bloqueio direto do item 1.
3. Casamento de imagem (template matching) para **ícone** continua não
   validado.
4. Chamado com a Thomson Reuters continua não aberto.
5. Identificar a janela do Domínio de forma confiável **por si só**
   (sem depender de estar maximizado e em foco) continua sem solução de
   raiz — na prática contornado (funciona bem maximizado + em foco),
   baixa prioridade enquanto o contorno seguir funcionando.
6. **Para a Fase 5 (não é para agora, só para não perder a ideia):**
   lista de empresas-alvo em ordem de prioridade, dias/horário de
   execução, gatilho manual vs. agendado, e loop
   trocar-empresa-e-repetir-a-mesma-rotina (seção 0.9).

### Checkpoint anterior — 18/09/2026 (histórico, superado pelo de cima)

**Provado hoje, não precisa testar de novo:**
- Domínio Escrita Fiscal roda via GraphOn GO-Global (seção 0.2) — UI
  Automation e Win32 **nunca** vão funcionar para esta tela. Não tentar
  de novo por esse caminho.
- OCR por recorte de região lê estado (empresa/período/menu) de forma
  confiável (seção 0.3).
- Rastrear onde clicaria em alvo de **texto**, sem clicar de verdade,
  funciona via posição de palavra do OCR (seção 0.4).
- Script de trabalho: `C:\Users\darto\OneDrive\Área de Trabalho\inspecionar.py`
  (mesmo arquivo reaproveitado a cada teste — conteúdo é trocado a cada
  vez, não acumula).

**Ficou em aberto — começar por aqui na próxima sessão:**
1. **Identificar a janela do Domínio de forma confiável não está
   resolvido.** Título não funciona (vazio/corrompido). Classe
   (`DisplayClientWindowClass`) não é exclusiva — outro programa deste
   computador usa a mesma. "Procurar em todas as janelas grandes por
   conteúdo" gerou 2 falsos positivos (QAAgent, Alternância de
   Tarefas/Alt-Tab) — `ImageGrab.grab(bbox=...)` captura pixels de uma
   *coordenada*, não de um programa específico, então retângulos que só
   coincidem por acaso já bastam pra confundir. **O que continua
   funcionando de verdade:** captura de tela cheia + recorte fixo do topo
   (`0,0,largura,120`), com o Domínio genuinamente maximizado — validado
   nas seções 0.3 e 0.4. Ainda não confirmamos se funciona com o Domínio
   fora de foco mas visível (a última tentativa, com Snap, não chegou a
   um resultado limpo — o atalho `Win+Seta` encaixou a janela errada mais
   de uma vez). **Recomendação para retomar:** voltar ao Domínio
   maximizado (sem Snap) antes de tentar de novo qualquer coisa mais
   esperta de identificação de janela.
2. Casamento de imagem (template matching) para **ícone** ainda não foi
   validado com sucesso — a única tentativa falhou por recorte manual sem
   conteúdo único (seção 0.4).
3. Chamado com a Thomson Reuters (seção 4, já com a pergunta do
   GO-Global) ainda não foi aberto.
4. Levantamento das competências já entregues da empresa-alvo (seção
   3.1, pergunta 3) ainda não foi feito.

---

## 0. O que já existe e não pode ser ignorado

Antes desta análise, já existia uma investigação real, com acesso à tela
do Domínio Escrita Fiscal, feita em setembro/2026, registrada numa PR
**aberta e não mesclada** no repositório do `docauto`:

- **PR #1** — "Adiciona docs/18: guia de rotinas automáticas do Domínio
  (fiscal)", branch `claude/rotinas-automaticas-fiscal-a5kcr3`.
  <https://github.com/cristiane-art/Testes-Para-Automa-o/pull/1>
- Contém `docs/18-rotinas-automaticas-dominio.md` (guia escrito **antes**
  de haver acesso real à tela — hipotético) e `DOMINIO_FISCAL_ROTINAS.md`
  (registro **confirmado por print**, sessão real de configuração dentro
  do Domínio Escrita Fiscal).

### Fatos confirmados por essa PR (não são suposição — evidência real)

| Fato | Detalhe |
|---|---|
| Produto e versão | **Domínio Escrita Fiscal, versão 10.6A-08-04** |
| Acesso usado | Login como **GERENTE** |
| Ambiente de teste | **Não existe.** Toda configuração/teste é feita **direto na base de produção** |
| Menu do recurso nativo | `Arquivos → Rotinas Automáticas` (não é em Utilitários/Controle) |
| Certificado digital da Lucrattiva | A1 instalado, confirmado |
| Regime da Lucrattiva | Simples Nacional, **não é MEI** (confirmado pela própria rotina 45) |
| Perfil da carteira | **Predominantemente Simples Nacional**; só uma empresa confirmada fora disso, recolhendo ICMS/SPED Fiscal estadual |
| Foco do escritório | **Agronegócio** (razão social "LUCRATTIVA CONTABILIDADE AGRIBUSINESS LTDA") — CT-e de frete de grão/insumo é rotina de alta relevância; Fator R, DASMEI e NFC-e são baixa prioridade |
| Ferramenta paralela em uso | **SIEG** já baixa XML de NF-e/NFS-e/CT-e por fora do Domínio — rotinas de busca dentro do Domínio podem estar **duplicando** isso |
| Rotina validada ponta a ponta | **CT-e API Entradas (rotina 10)** — única confirmada 100% correta com dado real |
| **Incidente real não resolvido** | Executar uma rotina disparou **outras 3 rotinas não solicitadas** (45/46/47) mais uma "Integração Contábil" inesperada. Uma delas gerou Memória de Cálculo do **PGDAS da própria Lucrattiva, competência 09/2026, mostrando "Simples Nacional a recolher: 0,00"** com receita acumulada real de R$ 534.535,46 — **incompatível**. Documento marcado **"PENDENTE, NÃO USAR"** desde 10/09; causa raiz **não encontrada** |
| Padrão de risco já identificado | Aba "Geral" de cada rotina tem 6 checkboxes que **encadeiam ações** (Apuração, Integração Contábil, pagamento via e-CAC, Fator R, Conta Azul) — mesmo desmarcados, já dispararam sozinhos duas vezes |
| Ambiente físico | Rotinas configuradas por pessoas diferentes do escritório, cada uma apontando para o **Dropbox pessoal da própria máquina** (não um servidor de rede real) |

### O que isso muda aqui

1. **O incidente do PGDAS zerado é um bloqueio real, não hipotético.**
   Antes de qualquer automação — nativa ou por UI Automation externa —
   tocar em apuração de tributo desta carteira, a causa raiz precisa ser
   entendida. Ver seção 9.
2. **Não existe base de homologação.** Qualquer teste roda contra dado
   fiscal real de cliente real. Isso molda todo o plano de Fase 0 a 4.
3. Já existe um **caminho de automação oficial e nativo** do próprio
   Domínio (`Rotinas Automáticas`), documentado por artigos do suporte
   (`suporte.dominioatendimento.com`, artigos 9143 e 3221). Entra na ordem
   de prioridade tecnológica como camada própria — ver seção 5.
4. A carteira é majoritariamente Simples Nacional — a obrigação-alvo não
   podia ser "algo ligado a SPED" de forma vaga (ver decisão na seção 3).

**PR #1: decisão registrada — continua, não mescla, não fecha.** Ela tem
bug confirmado (marcado "NÃO USAR") e vários `PENDENTE DE CONFIRMAÇÃO`,
então não está pronta para merge; e não está obsoleta, o achado é real.
Continuá-la exige a mesma coisa que a Fase 0 deste projeto exige — alguém
com a tela do Domínio aberta, em tempo real — então as duas frentes devem
ser tratadas como **um único esforço de campo**, não dois paralelos.

### 0.1 Achados confirmados ao vivo, sessão de 18/09/2026

Início da Fase 0 na prática — máquina Windows 11 Home Single Language,
25H2 (build 26200.9457), Python 3.14.7 (64 bits) já instalado.

| Achado | Detalhe |
|---|---|
| Acesso ao Domínio | Em duas etapas: (1) portal **"Domínio Web"** — login por e-mail via `auth.thomsonreuters.com`, abre um launcher local ("Lista de Programas") com um ícone por módulo (Folha, Escrita Fiscal, Contabilidade, Atualizar, Lalur, Registro, Ponto Eletrônico, Importar Arquivos, Conexões, Gerenciador de Tarefas, Impressoras, Informações); (2) ao abrir **Escrita Fiscal**, pede um segundo login (usuário/senha do próprio Domínio) |
| Escrita Fiscal é janela nativa | **Confirmado por print**: janela Win32 de verdade (barra de título padrão do Windows, minimizar/maximizar/fechar), **não é navegador nem área de trabalho remota** — o receio inicial (o atalho "Acesso Remoto - Domínio Sistemas" sugerir RDP/Citrix) não se confirmou. Bom sinal para UI Automation/pywinauto |
| Versão já mudou desde a PR #1 | Título mostra **"Domínio Escrita Fiscal - Versão: 10.6A-08-09"** — a PR #1 (uma semana antes) tinha registrado 10.6A-08-04. Confirma na prática o risco de deriva de versão já mapeado (seção 2) |
| Menu clássico confirmado | Barra de menu: Controle / Arquivos / Movimentos / Relatórios / Utilitários / Favoritos / Ajuda — bate com o `Arquivos → Rotinas Automáticas` já documentado na PR #1 |
| Empresa e período no cabeçalho | Canto superior direito mostra usuário (`GERENTE`), empresa atual (`HABITA PROJETOS - 78` no momento do print — **não** é a empresa-alvo da POC) e competência atual (`AGO/2026`). Relevante: pelo menos parte do estado (empresa/período selecionados) aparece como texto visível na janela principal, não escondido dentro de grade — favorável para a rotina `identificar empresa selecionada` |
| Área de trabalho em branco | Canvas azul liso sob o menu, sem nada aberto — hipótese de app MDI (cada rotina abre como janela-filha dentro dela). Ainda não confirmado por inspeção real — próximo passo |
| Barra de status | Indicadores de integração na base da janela: Onvio, Suporte, eSocial, OnBalance, Docs Fiscais, "Agente" — vários com indicador verde (status de conexão?). Não investigado ainda, mas é candidato a fonte de detecção de erro/estado no futuro |

**Próximo passo em andamento:** instalar Accessibility Insights for
Windows e inspecionar (sem executar nada) o menu "Arquivos" e um botão da
barra de ferramentas, para responder a pergunta 6 da seção 3.2 (a árvore
de UI Automation tem nomes/IDs utilizáveis, ou é tudo genérico?).

### 0.2 Achado crítico: o Domínio não roda localmente — é entregue via GraphOn GO-Global

**Isto muda a ordem de prioridade tecnológica da seção 5.1 e é o achado
mais importante desta sessão.**

**Como foi descoberto:**
1. Accessibility Insights (Live Inspect) não conseguiu capturar nenhum
   elemento nomeado na janela do Domínio, mesmo depois de descartar erro
   de manuseio da ferramenta.
2. `pywinauto` com `backend="uia"` — `Desktop(backend="uia").windows()`
   **não lista a janela "Domínio Escrita Fiscal" entre as janelas
   abertas**, mesmo com ela visível e em primeiro plano na tela.
3. `pywinauto` com `backend="win32"` — mesmo resultado: **não aparece**,
   apesar de listar centenas de outras janelas/processos do sistema
   (incluindo uma janela literalmente chamada `'RemoteApp'`).
4. Gerenciador de Tarefas confirmou: o processo responsável é
   **`AppController (32 bits)`**, em
   `C:\Program Files (x86)\GraphOn\AppController`, com o launcher
   "Lista de Programas" (e presumivelmente o próprio Escrita Fiscal)
   rodando como filho dele.

**O que é isso:** [GraphOn GO-Global](https://www.graphon.com/go-global)
— produto de virtualização/publicação de aplicativos Windows,
concorrente do Citrix Virtual Apps e do RDS RemoteApp da Microsoft, usado
para publicar programas antigos (como o Domínio, que é Delphi) como se
fossem acessados remotamente sem reescrever o programa. Segundo a
documentação pública da própria GraphOn, o GO-Global usa um driver de
tela virtual que converte comandos gráficos do Windows para um protocolo
próprio ("RapidX Protocol") — ou seja, **o programa executa de verdade
num servidor remoto; o computador do escritório só reconstrói a imagem
da tela**, não hospeda uma janela local de verdade com controles
acessíveis.

Não foi encontrada, em busca pública, nenhuma API de automação/scripting
documentada para o lado cliente do GO-Global (a busca cobriu
especificamente esse ponto e não achou nada).

**Consequência prática — revisão da seção 5.1:**

```
1. API oficial confirmada por escrito com a Thomson Reuters
1.5 Rotinas Automáticas nativas do Domínio — CONTINUA VIÁVEL, roda no
    servidor independente de como a tela chega até o escritório
2. Microsoft UI Automation — NÃO VIÁVEL para esta tela (confirmado)
3. Win32 clássico — NÃO VIÁVEL para esta tela (confirmado)
4. OCR — vira a opção realista mais alta da lista para qualquer
   automação externa desta tela específica
5. Computer Vision — idem, provavelmente andando junto com OCR
6. Coordenada de mouse/teclado — deixa de ser "último recurso teórico"
   e passa a ser um componente prático necessário (OCR/CV identificam
   texto/elemento, mas o clique ainda precisa de uma coordenada de tela)
```

**Recomendação atualizada:** priorizar ainda mais fortemente o caminho
1.5 (supervisionar/disparar Rotinas Automáticas nativas, que não são
afetadas por este achado) sobre tentar clicar na tela remota do zero via
OCR/CV — este último vira um projeto bem mais caro e frágil do que se
imaginava, e só compensa se a Rotina Automática nativa genuinamente não
alcançar o que for necessário.

**Pergunta nova para o chamado com a Thomson Reuters (adicionar à
seção 4):** o acesso ao Domínio é publicado via GraphOn GO-Global (ou
tecnologia semelhante) por decisão de vocês, de um parceiro de hospedagem,
ou é assim para todos os clientes? Existe alguma forma suportada de
automação no lado do servidor, já que o lado cliente é apenas uma tela
remota?

### 0.3 Achado: OCR na tela inteira não é confiável — recorte por região funciona melhor

Primeiro teste real de OCR (`pytesseract` + Tesseract, mesmo motor já
usado pelo `docauto`), rodado contra uma captura de tela inteira do
Domínio parado (estado ocioso, sem menu aberto):

| Resultado | Exemplo |
|---|---|
| Leu certo | `HABITA PROJETOS -78`, `DOMÍNIO`, quase toda a barra de status inferior |
| **Não leu** (sumiu do resultado) | A barra de menu inteira (`Controle Arquivos Movimentos Relatórios Utilitários Favoritos Ajuda`), `GERENTE`, `AGO/2026` — apesar de nítidos na tela |
| **Inventou** (alucinação) | Trechos tipo `ARA DODD xs`, `EECRAamo Eos` — vêm dos ícones sem texto nenhum sendo interpretados como letras |

**Conclusão:** OCR de tela inteira de uma vez é pouco confiável pra esse
tipo de interface (mistura de ícone e texto espalhado confunde a
segmentação do Tesseract). O padrão correto, usado por ferramentas de RPA
para esse tipo de cenário: **recortar regiões específicas da tela antes de
rodar OCR em cada uma**, e localizar ícones/botões por **casamento de
imagem** (OpenCV template matching), nunca por OCR (ícone não é texto).

**Região priorizada:** a faixa superior da janela (menu + barra de
ferramentas + empresa/período selecionados) — é a que carrega o estado
mais importante da aplicação (qual empresa, qual período, qual menu).

**Teste seguinte, confirmado: recorte resolve.** Rodando OCR só nos
primeiros 120px do topo (`captura.crop((0, 0, largura, 120))`) em vez da
tela inteira:

| Item | Tela inteira | Recorte do topo |
|---|---|---|
| Barra de menu (Controle/Arquivos/.../Ajuda) | sumiu | **leu 100% certo** |
| `GERENTE` | sumiu | **leu certo** |
| `AGO/2026` | sumiu | leu quase certo (`AGo/2026` — só maiúscula/minúscula, trivial de normalizar) |
| `HABITA PROJETOS -78` | certo | continua certo |
| Fileira de ícones da barra de ferramentas | lixo | continua lixo (esperado — ícone não é texto, precisa de casamento de imagem) |

**Marco confirmado:** OCR por recorte de região é uma técnica viável para
detectar estado (empresa, período, menu) nesta interface, apesar do
Domínio ser entregue via GO-Global. O padrão a seguir daqui pra frente:
cada informação de estado tem sua própria região de recorte pré-definida
(coordenadas relativas à janela), OCR roda só ali, e ícones/botões são
achados por casamento de imagem, nunca por OCR de tela inteira.

### 0.4 Achado: "rastrear o clique" (modo DRY_RUN) — texto vs. ícone precisam de técnicas diferentes

Pedido do usuário antes de qualquer clique de verdade acontecer: o script
deve **achar e marcar visualmente** onde clicaria (arquivo de imagem com
uma marca no ponto exato), sem mover o mouse nem clicar de verdade —
igual ao princípio `DRY_RUN` do briefing original.

- **Tentativa 1 (casamento de imagem/template matching) para o texto
  "Relatórios" — falhou.** Confiança reportada de 98%, mas a marca caiu
  longe do alvo, em área vazia da tela. Causa: a imagem de referência
  recortada manualmente no Paint saiu majoritariamente em branco/azul
  liso (fácil de acontecer ao selecionar texto pequeno na mão) — um
  recorte sem conteúdo único "combina" com qualquer área lisa da tela,
  em qualquer lugar, com confiança alta e enganosa.
- **Tentativa 2 (posição de palavra via OCR) para o mesmo alvo —
  funcionou, confirmado por print.** Em vez de imagem de referência,
  usar `pytesseract.image_to_data(..., output_type=Output.DICT)`, que
  devolve a caixa delimitadora (x, y, largura, altura) de cada palavra
  lida. Buscar o texto exato dentro desse resultado dá a coordenada de
  clique diretamente, sem depender de recorte manual nenhum.

**Regra consolidada para o motor:** alvo de **texto** (menu, rótulo,
opção de lista) → localizar por posição de palavra do OCR. Alvo de
**ícone** (sem texto) → localizar por casamento de imagem, com uma
referência bem recortada (conteúdo visual único, não área lisa) — ainda
não validado com sucesso nesta sessão, fica para o próximo teste.

### 0.5 Achado: a janela do Domínio tem classe `DisplayClientWindowClass`

Pedido do usuário: não depender de captura de tela inteira (que quebra
se outra janela estiver em algum canto da tela) — mirar especificamente
na janela do Domínio.

Como o título dela é inutilizável (vazio ou corrompido, seção 0.2),
listamos todas as janelas grandes (`>800x400`) por **classe**, não por
título, via `Desktop(backend="win32").windows()`. Achado:

- Uma janela sem título, classe **`DisplayClientWindowClass`**, retângulo
  `(L-8, T-8, R1448, B860)` — bate com o tamanho cheio de tela do Domínio
  em todos os prints já enviados.
- A mesma classe aparece na outra janela já conhecida (o launcher "Lista
  de Programas", com o título corrompido) — confirma que
  `DisplayClientWindowClass` é a classe de janela usada pelo cliente
  GraphOn GO-Global para renderizar conteúdo remoto, independente de
  qual aplicativo publicado está sendo mostrado.

**Correção (mesmo dia, teste seguinte): a classe não é exclusiva do
GraphOn.** Ao filtrar por `DisplayClientWindowClass` + tamanho grande,
apareceram **2 candidatas — nenhuma das duas era o Domínio.** As duas
prévias por OCR mostraram texto da própria sessão do Claude/chat desta
investigação (uma delas leu literalmente um trecho da mensagem anterior
do Claude). Ou seja: **outro aplicativo neste computador usa a mesma
classe de janela**, e classe sozinha não é suficiente para identificar a
janela certa — é preciso também **conferir o conteúdo** (ex.: procurar
"GERENTE" ou o padrão de período no texto lido) antes de confiar que a
janela achada é o Domínio. A pista da classe continua útil como primeiro
filtro, só não pode ser o único critério.

**Consequência prática:** dá para restringir a busca por **classe +
tamanho**, mas o motor sempre precisa **validar por conteúdo** (OCR)
antes de agir sobre a janela encontrada — nunca confiar cegamente em
classe/tamanho sozinhos. Isso também não resolve captura com o Domínio
minimizado ou tampado por outra janela (exigiria a janela responder a
`PrintWindow`, incerto para conteúdo GO-Global, não testado ainda).

**Decisão do usuário: fixar o Domínio num tamanho e posição padrão na
tela** (em vez de maximizado), usando o recurso nativo de encaixe do
Windows (Snap, `Win+Seta`) — reduz ambiguidade (a janela do Domínio fica
com um retângulo característico, mais fácil de diferenciar de outras) e
permite acompanhar visualmente o que a automação está vendo a qualquer
momento.

### 0.6 Marco: primeiro clique sintético confirmado (sessão de 21/09/2026)

**A dúvida mais importante que restava — "dá pra interagir de verdade
com essa tela remota, ou só ler?" — está respondida: dá.**

Sequência de tentativas até funcionar, todas usando a posição de
"Relatórios" já validada (seção 0.4):

1. `pyautogui.click(x, y)` simples — o item ficou destacado (hover
   registrou) mas **o menu não abriu**.
2. Clique "devagar" (`moveTo` com duração + `mouseDown`/pausa/`mouseUp`
   em vez de `click()` instantâneo) — **mesmo resultado**, não abriu.
3. `ctypes.windll.user32.SetProcessDPIAware()` no início do script (testa
   descompasso de coordenada por escala de tela) — **mesmo resultado
   ainda**, não abriu.
4. **Causa real, achada pelo usuário:** o clique só registra de verdade
   se o Domínio já estiver **em foco (janela ativa)** no momento do
   clique. Rodando o script com o cmd.exe em foco, o clique só "acorda" a
   janela sem executar a ação nela. Clicando manualmente na janela do
   Domínio pra focar antes de rodar o script — **funcionou**, confirmado
   por print: o menu "Relatórios" abriu com a lista completa (Livros,
   Informativos, Guias, Impostos, Acompanhamentos, Estoque, Cadastrais,
   Contas a Pagar e Receber, Gerenciador de Relatórios).

**Regra consolidada para o motor:** ao contrário da leitura por OCR (que
funciona com o Domínio sem foco, seção 0.5), **clicar exige o Domínio em
foco**. Toda ação de clique da máquina de estados precisa garantir foco
na janela certa antes de agir — não basta achar a coordenada certa.

**Ainda não isolado:** não sabemos ao certo se o DPI-aware e o clique
devagar (passos 2 e 3) eram de fato necessários, ou se só o foco já
resolvia sozinho — como as três correções foram empilhadas antes do
teste que funcionou, ficou junto. Não é crítico separar agora (o combo
todo funciona), mas vale simplificar/testar isolado se algum dia isso
importar (por exemplo, se o clique devagar deixar a automação lenta
demais em lote).

### 0.7 Achado: OCR dentro de menu suspenso precisa de pré-processamento de imagem

Depois de resolver foco (0.6), navegar Relatórios → Informativos ainda
travava: o texto do menu suspenso (Livros/Informativos/Guias/Impostos/
Acompanhamentos/Estoque/Cadastrais/Contas a Pagar e Receber) **nunca**
aparecia na leitura do OCR, mesmo com a imagem comprovadamente perfeita
(confirmado salvando exatamente a imagem que foi analisada, não uma nova
captura depois — bug próprio corrigido no caminho, ver commits). Só a
barra de menu (fundo cinza claro) e fragmentos do último item da lista
liam certo — o miolo da lista, dentro da caixa branca flutuante sobre o
fundo azul, nunca.

**Hipótese:** o Tesseract, no modo automático de segmentação de página,
tem dificuldade com uma caixa branca "flutuando" sobre um fundo de cor
sólida diferente — provavelmente confunde a análise de layout dele
(pensado pra documento, não pra tela de aplicativo).

**Testado, não resolveu sozinho:** trocar o modo de segmentação
(`--psm 11`, texto esparso) — não chegou a ser testado isoladamente,
pulou direto pra próxima tentativa.

**Resolveu:** pré-processar a imagem antes do OCR — **aumentar 2x de
tamanho** (`Image.resize(..., Image.LANCZOS)`) e **converter para tons
de cinza** (`ImageOps.grayscale`). Achou "Informativos" de primeira,
hover abriu o submenu seguinte (Federais/Estaduais) corretamente.

**Regra consolidada, generalizada para o motor:** todo OCR dentro de
área de menu/caixa suspensa (não a barra de menu externa, que já
funciona sem isso) deve passar por esse pré-processamento antes de
`pytesseract.image_to_data()`. **Atenção ao converter coordenada de
volta**: se a imagem foi ampliada por um fator antes do OCR, a
coordenada encontrada precisa ser dividida por esse mesmo fator antes de
usar para clicar/passar o mouse na tela real.

**Confirmado também nesta mesma rodada:** hover (sem clicar) realmente
abre submenu em cascata (Informativos → Federais/Estaduais) — a hipótese
da seção 0.4/0.6 estava certa, só precisava do OCR achar o alvo primeiro
pra poder testar.

### 0.8 Marco: navegação completa até SPED Fiscal — pausa deliberada antes do primeiro OK

O script consolidado (`app/tela.py` + `app/interacao.py` +
`scripts/explorar.py`, seção 5.2) navegou sozinho **Relatórios →
Informativos → Federais → SPED Fiscal** e abriu a tela real de geração
da EFD ICMS/IPI (Período, campo Arquivo com `c:\sped_fiscal.txt`,
botões OK/Fechar/Empresas...). Corrigido no caminho: bug de
correspondência OCR multi-palavra em que um alvo mais comprido por
coincidência (ex.: "...Movimentos Relatórios") vencia o alvo certo de
uma palavra só — resolvido testando janela de 1 palavra em **todas** as
posições antes de tentar janelas de 2, 3, 4 palavras.

**Decisão: não clicar OK ainda sem confirmar duas coisas primeiro** —
esta seria a primeira ação real do motor (gera arquivo em disco), e a
regra da seção 5.7 só vale como oráculo de verificação se as duas
condições abaixo forem verdadeiras:

1. A empresa selecionada no Domínio no momento do clique é mesmo a
   empresa-alvo (a única fora do Simples Nacional) — não a
   `HABITA PROJETOS -78`, que ficou selecionada mais cedo na sessão por
   outro motivo, sem relação com este teste.
2. O período mostrado (01/08/2026–31/08/2026) é uma competência **já
   fechada e já entregue de fato** por essa empresa — só assim o
   arquivo gerado agora tem algo real pra comparar (o ponto da seção
   5.7 é o oráculo de verificação, não só "gerar sem dar erro").

**Achado tranquilizador, reduz o risco deste clique especificamente:**
este caminho (`Relatórios → Informativos → Federais → SPED Fiscal`) é
geração/exportação de leitura, **não** é a área
`Arquivos → Rotinas Automáticas` onde a PR #1 viu ações encadeadas não
solicitadas — nada indica que esse risco se aplique aqui. Gerar o
arquivo também não transmite nada à Receita: a transmissão de SPED
acontece por fora do Domínio, no programa validador/assinador do
governo (PVA), nunca dentro desta tela. Ou seja, o pior cenário de
clicar OK com a empresa/competência erradas é um arquivo `.txt`
descartável e sem valor de comparação — não um dado de produção
alterado nem nada transmitido.

### 0.9 Nota para a Fase 5 (múltiplas empresas) — registrada agora, não é para construir ainda

Pedido do usuário: quando chegar a hora, definir (a) lista de
empresas-alvo em ordem de prioridade, (b) dias e horário de execução,
(c) se o motor inicia por comando manual ou por agendamento, e (d) um
loop de "processar empresa → trocar de empresa → repetir a mesma
rotina". Mapeia direto para a **Fase 5 — Multiempresa** já prevista no
roadmap (seção 6: "lista de empresas, execução sequencial, erro isolado
por empresa"). Registrado aqui só para não perder a ideia entre
sessões — desenho e código ficam para depois da Fase 4 (uma rotina, uma
empresa, usando a operação segura da seção 5.7) rodar estável por 2–3
competências, exatamente como o próprio roadmap já condiciona.

**Reforço do usuário (mesma sessão, depois de ver o `esperar_e_achar`
da seção 0.12 funcionar):** esse estilo de "saber em que estado
estamos e qual o próximo passo" deveria existir no processo inteiro,
não só na espera do resultado — especialmente na hora de trocar de
empresa. Confirma exatamente a ordem que o roadmap já previa: a
**Fase 3 — State machine** (seção 5.6) não é só organização de código,
é o que torna a Fase 5 seguro (saber, a qualquer momento, em que
empresa/passo o motor está, pra poder recuperar ou pular sem perder o
lugar). Ainda não é para construir agora — os passos do script
continuam lineares (`scripts/explorar.py`) até a Fase 4 fechar.

### 0.10 Achado: tela densa de diálogo confunde OCR de tela inteira; alvo de 2 letras precisa de âncora

Primeira tentativa de achar "OK" na tela de geração do SPED Fiscal
(seção 0.8) — OCR de tela inteira, mesma técnica usada em todos os
passos anteriores — **não achou**. A lista de palavras vistas veio cheia
de lixo (`OsEto`, `«op`, `nvênio`, `adronizad`...): essa tela é um
formulário denso (dezenas de campo, checkbox, dropdown), bem mais
carregada visualmente que os menus simples testados até aqui — o mesmo
tipo de problema da seção 0.3 (tela inteira não confiável), só que numa
região ainda não calibrada. Some a isso "OK" ter só 2 letras — texto
curto demais pro Tesseract confiar sozinho em meio a tanto ruído, um
problema diferente do de recorte (confirmado por print real: o botão
existe, está visível, e "Empresas..." — no mesmo formulário — **leu
certo** na mesma tentativa).

**Solução: usar um texto vizinho, mais longo e já confirmado legível,
como âncora.** "Empresas..." é um dos botões da mesma coluna vertical
que "OK" (ordem: OK, Fechar, Empresas..., Inventário...) e leu certo
mesmo na tela inteira. A partir da posição de "Empresas...":

1. Recorta uma janela pequena ao redor dela (`recortar_ao_redor`,
   `app/tela.py`) — bem menos ruído que a tela inteira.
2. Tenta achar "OK" ali com escala maior (4x em vez de 2x, viável porque
   agora é uma imagem pequena, não a tela inteira).
3. Se ainda assim não achar (2 letras pode continuar sendo pouco pro
   OCR), calcula a posição por **aritmética**: a coluna de botões tem
   espaçamento vertical regular, então acha "Fechar" (palavra normal,
   deve ler bem) e soma a mesma distância que existe entre "Fechar" e
   "Empresas" — dá a posição de "OK" sem depender do OCR ler "OK" de
   jeito nenhum.

Confirmado visualmente por print marcado pelo usuário: o botão OK fica
exatamente um espaçamento de botão acima de "Fechar", que fica um
espaçamento acima de "Empresas..." — a suposição de espaçamento regular
está certa nesta versão do Domínio (10.6A-08-09).

**Regra generalizada para o motor:** quando o alvo de clique for texto
curto (poucas letras, ex.: "OK", "Sim", "Não") dentro de uma tela densa,
não confiar em OCR de tela inteira nem em recorte fixo — usar um texto
vizinho mais longo como âncora, recortar ao redor dela, e ter um
fallback por posição relativa (aritmética) para o caso do alvo curto
continuar ilegível mesmo de perto.

**Nota lateral:** o campo "Arquivo" desta tela mostra
`M:\teste-docauto\Aplicativo\...` — confirma que o teste está mesmo
isolado (empresa de teste, caminho de teste), não aponta pra nada de
produção real.

### 0.11 Marco: primeira geração real ponta a ponta, com sucesso confirmado

Com a técnica de âncora da seção 0.10 funcionando, o clique em "OK" da
tela de SPED Fiscal (seção 0.8) foi executado de verdade pela primeira
vez — **contra uma empresa de teste**, escolha deliberada do usuário
pra validar o mecanismo sem qualquer risco de dado real (`HABITA
PROJETOS -78`, a mesma que aparecia selecionada desde o início da
sessão; caminho do arquivo de saída também de teste,
`M:\teste-docauto\Aplicativo\...`, seção 0.10).

**Resultado: sucesso, confirmado pelo próprio Domínio.** Depois do
clique em OK e de aguardar, apareceu uma caixa de diálogo:

> Título: **SPED Fiscal** — ícone de informação — texto: **"Final da
> exportação."** — botão único: **OK**.

Isso responde, com evidência real, a **pergunta 9 da seção 3.2**
("mensagem de sucesso/erro aparece em caixa de diálogo padrão do
Windows, ou dentro de painel da própria tela?"): é uma caixa de diálogo
padrão do Windows — pequena, simples, bem menos densa que o formulário
da seção 0.8. Ainda não vimos como é a mensagem de **erro** (só a de
sucesso) — fica pra quando algo dar errado de verdade.

**Consequência prática para o motor:** esse tipo de confirmação também
usa a mesma técnica da seção 0.10 — "OK" continua com só 2 letras,
então precisa de âncora (usamos "exportação", palavra do próprio texto
da confirmação, comprida o suficiente pra ler bem) + recorte, em vez de
tentar achar "OK" direto na tela inteira.

**Script agora cobre o fluxo inteiro:** navega até SPED Fiscal, clica
OK, confirma o aviso de sucesso, e fecha a tela (botão "Fechar", mesma
coluna de botões da seção 0.8) — sem intervenção manual no meio.

**O que ainda falta pra isso virar prova de verdade (seção 5.7):** essa
rodada provou que o **mecanismo** funciona ponta a ponta, mas foi numa
empresa de teste — não tem um arquivo real entregue no passado pra
comparar. O próximo passo de validação de conteúdo (não só de
mecanismo) precisa repetir isso na empresa-alvo real, com uma
competência já fechada e entregue de fato (itens 1 e 2 do checkpoint
acima).

### 0.12 Achado: esperar tempo fixo não é confiável — precisa esperar por estado

Numa segunda rodada (mesma empresa de teste), o script terminou de
clicar OK, esperou os `5s` fixos do passo 6/7 original, tirou o print e
tentou achar a confirmação "Final da exportação" — **não achou**. A
lista de palavras vistas mostrou que a tela de SPED Fiscal (seção 0.8)
ainda estava aberta, formulário e tudo — ou seja, a confirmação
simplesmente **ainda não tinha aparecido** nesses 5 segundos (deve
variar com o volume de dado da empresa/período sendo exportado).

Diagnóstico e correção sugeridos pelo usuário, e implementados: em vez
de um tempo fixo (`time.sleep(N)` seguido de uma única checagem), o
motor deve **esperar por estado** — checar repetidamente por OCR se o
alvo já apareceu, e só desistir depois de várias tentativas. Isso é
literalmente o "wait-strategy" do briefing original do projeto (evitar
`time.sleep()` como mecanismo primário de sincronismo).

**Implementado em `scripts/explorar.py` (`esperar_e_achar`):** espera
um mínimo de 6 segundos, depois verifica a cada 2 segundos (até 15
tentativas, ~36s no total) se o alvo apareceu, em vez de checar uma vez
só. Usado no passo de aguardar a confirmação de sucesso; o mesmo padrão
serve pra qualquer espera futura do motor (ex.: esperar uma rotina
automática nativa terminar).

**Regra generalizada para o motor:** qualquer espera por uma mudança de
tela (fim de processamento, abertura de janela, mensagem de
resultado) deve ser feita por polling com OCR, com um mínimo de tempo
antes da primeira checagem e um número máximo de tentativas — nunca só
`time.sleep(N)` seguido de uma checagem única.

### 0.13 Achado: "OK" de diálogo de 1 botão resiste ao OCR mesmo de perto — resolvido com teclado (Enter)

Com o polling da seção 0.12 funcionando, a confirmação "Final da
exportação." passou a ser achada de forma confiável (âncora
"exportação"). Mas o clique em "OK" **continuou falhando** mesmo com a
técnica de âncora + recorte + zoom 4x da seção 0.10 — dessa vez
confirmado por **print real, marcado pelo usuário**: o botão OK está
fisicamente dentro da área recortada, na posição esperada (~9px à
direita, ~58px abaixo da âncora "exportação"), e mesmo assim o
Tesseract não lê o texto. Não é problema de recorte — é o texto "OK"
nessa fonte/tamanho específico que é ilegível pro OCR usado, mesmo de
perto. Duas tentativas (a tela de SPED Fiscal na seção 0.10 e esta
confirmação) confirmam que "OK" é um caso limite ruim pra essa técnica.

**Solução: parar de tentar clicar, usar teclado.** Essa confirmação é
uma caixa de diálogo **padrão do Windows com um botão só** — esse tipo
de caixa aceita **Enter** no botão padrão, sem precisar localizar nem
clicar em nada. `app/interacao.py` ganhou `pressionar_enter()`
(`pyautogui.press("enter")`). Depois de pressionar, o script confirma
que a confirmação realmente sumiu (procura "exporta" de novo — se ainda
achar, para em vez de seguir às cegas) antes de continuar pro próximo
passo.

**Primeira vez que este projeto usa teclado, não só mouse, pra
interagir com a tela remota do GO-Global** — mesma dúvida que existia
pra clique (foco necessário? funciona mesmo sendo tela remota?) ainda
não tinha sido testada especificamente para tecla. Resultado desta
tentativa fica registrado assim que confirmado.

**Regra generalizada para o motor:** pra caixa de diálogo simples de
**um botão só** (mensagem de sucesso/erro/aviso padrão do Windows),
preferir Enter a achar-e-clicar — mais simples e não depende de OCR
conseguir ler o texto do botão. Pra diálogo com **múltiplos botões**
(como a tela de SPED Fiscal, seção 0.8), Enter ativaria o botão padrão
errado às vezes — ali continua sendo achar-e-clicar (com âncora, se o
texto for curto) a técnica certa.

---

### 0.14 Marco: troca de empresa automatizada (F8 → digitar código → Acessar)

Pedido do usuário: automatizar a troca de empresa selecionada no
Domínio — pré-requisito direto da Fase 5 (seção 0.9). Descoberto e
validado nesta sessão, em `scripts/trocar_empresa.py`:

- **F8 abre "Troca de empresas"** — atalho de teclado, não precisa
  navegar menu nenhum. Primeira vez que o motor usa uma tecla de função
  (não só clique e Enter, seção 0.13).
- **O título do diálogo ("Troca de empresas") não lê de forma
  confiável no OCR** (virou lixo tipo "Elmocdempresos") — usar o botão
  **"Acessar"** como confirmação de que a tela abriu é bem mais
  confiável (palavra mais longa, e sempre presente).
- **Busca por Código é mais confiável que por Apelido** pra automação:
  nome tem risco de ambiguidade real nesta carteira (ex.: "AZURE BA",
  "AZURE FILIAL MT", "AZURE FILIAL PR" todas bateriam com uma busca por
  "AZURE"); código é sempre exato, uma empresa só. O modo de busca
  (rádio "Código"/"Apelido") **não volta pro padrão sozinho** — fica no
  que foi usado da última vez que a tela abriu.
- **Depois de digitar o código, a linha já fica selecionada sozinha no
  grid** — não precisa clicar nela, só direto em "Acessar" (confirmado
  pelo usuário testando à mão).
- O texto "HABITA PROJETOS -78" no canto superior direito **também é
  clicável** e abre a mesma tela — alternativa ao F8, não usada por
  enquanto (F8 é mais simples, não depende de achar aquele texto).

**Regra consolidada para o motor:** trocar de empresa = `F8` →
`digitar(código)` → achar e clicar "Acessar" (reaproveitando a posição
já achada na confirmação de abertura, já que o botão não se move com o
filtro do grid).

### 0.15 Base de empresas por regime — camada de dados da Fase 5 (ainda sem loop automático)

Pedido do usuário: as empresas que o motor acessa devem vir de uma
lista que ele mesmo mantém, separável por regime (ex.: "hoje só Simples
Nacional"), com o motor perguntando antes de rodar qual regime
processar. Implementado como camada de **dados + seleção**, ainda sem
disparar rotina nenhuma sozinho:

- **`data/empresas.csv`** — código, apelido e regime de cada empresa. É
  dado de cliente real (mesmo só nome/código), então fica em `data/`,
  já no `.gitignore` desde o início do projeto (seção 5.4) — nunca é
  versionado, o usuário mantém localmente (edita em Excel/Notepad).
  Separador `;` (não `,`) porque é o que o Excel em português usa por
  padrão.
- **`data/empresas.exemplo.csv`** — modelo de formato, com as empresas
  de demonstração do próprio Domínio (vistas de verdade no grid do F8,
  seção 0.14): as 4 básicas (`9996 EXEMPLO ESCRITÓRIO`, `9997 EXEMPLO
  REAL`, `9998 EXEMPLO PRESUMIDO`, `9999 EXEMPLO SIMPLES`) mais as
  séries `10051–10058 PRESUMIDO ...` (8 empresas) e `10101–10103 REAL
  ...` (3 empresas) — 15 linhas ao todo, 9 Presumido + 4 Real dentro
  dessas duas. Pedido do usuário: simular uma lista com proporção
  parecida com a carteira real (~80% Presumido / ~20% Real) pra testar
  `selecionar_empresas.py` antes de mexer na planilha de verdade. Usei
  só empresas de demonstração **confirmadas reais** (vistas por OCR,
  não inventadas) — o máximo que dá pra tirar delas é 9 Presumido/4
  Real (69%/31%), não os 17/80–20 exatos pedidos; registrado aqui caso
  precise completar com linha sintética (claramente marcada como tal)
  no futuro. Essas são todas de demonstração, sem risco nenhum, por
  isso esse arquivo é versionado, serve de referência.
- **`app/empresas.py`** — `carregar_empresas()` lê o CSV de verdade (cai
  pro exemplo com aviso se ele ainda não existir); `filtrar_por_regime()`
  filtra; `regimes_disponiveis()` lista os regimes vistos.
- **`scripts/selecionar_empresas.py`** — carrega a lista, pergunta
  (`input()`) qual regime processar hoje, mostra as empresas
  selecionadas. Testado localmente com o arquivo de exemplo.

**Deliberadamente não incluído ainda:** o loop que trocaria de empresa
(seção 0.14) e rodaria a rotina (seção 0.8) pra cada uma da lista
selecionada. Essa automação de ponta a ponta em lote é a Fase 5 de
verdade — o roadmap (seção 6) já condiciona ela a Fase 4 rodar estável
por 2–3 competências **na empresa-alvo real**, o que ainda não
aconteceu (só rodamos em empresa de teste/demonstração até agora,
seção 0.11). A camada de dados fica pronta esperando por isso.

### 0.16 Dois achados reais ao preencher `data/empresas.csv` pela primeira vez

Primeira vez que o usuário de fato copiou o exemplo pra
`data/empresas.csv` e preencheu com a carteira real (seção 0.15) —
dois problemas reais apareceram, ambos corrigidos:

1. **`UnicodeDecodeError` ao carregar o arquivo** — o byte que quebrou
   a leitura (`0xC1`) é a letra "Á" na página de código Windows-1252
   ("ANSI"), não em UTF-8. Editar um CSV com acento no Notepad/Excel em
   português nem sempre salva em UTF-8, e quem só está preenchendo uma
   planilha não tem como saber disso — não é erro do usuário, é
   armadilha conhecida de editor de texto no Windows em português.
   **Corrigido:** `carregar_empresas()` agora tenta UTF-8 e cai pra
   `cp1252` automaticamente se não der, avisando qual dos dois usou.
2. **Confusão entre lista real e lista de exemplo** — depois de criar
   `data/empresas.csv` com empresas de verdade, rodar
   `selecionar_empresas.py` mostrou a carteira real (esperado: o código
   sempre prioriza o arquivo real quando existe), mas nada na tela
   deixava claro **qual dos dois arquivos** tinha sido carregado —
   gerou a dúvida "não era pra ser com empresa teste?". **Corrigido:**
   o carregamento agora sempre imprime o caminho completo do arquivo
   usado com um rótulo `[REAL]` ou `[EXEMPLO/TESTE]`; e
   `scripts/selecionar_empresas.py --exemplo` força usar o exemplo
   mesmo com `data/empresas.csv` já existindo, pra poder testar sem
   depender de mover/renomear a planilha de verdade.

**Regra consolidada:** todo script que carrega dado que pode ser real
ou de teste deve **dizer explicitamente qual dos dois está usando**,
sempre — nunca deixar implícito só pelo nome do arquivo ou pela
ausência de aviso.

### 0.17 Motor em lote: troca de empresa + SPED Fiscal por regime

Pedido do usuário depois de ver `selecionar_empresas.py` funcionando:
"como executa?" — ligar a lista filtrada por regime (seção 0.15) às
duas ações já provadas (trocar de empresa, seção 0.14; gerar SPED
Fiscal, seções 0.8/0.11-0.13) num loop de verdade.

**Refatoração:** a lógica de `scripts/trocar_empresa.py` e
`scripts/explorar.py` foi movida pra `app/dominio.py`
(`trocar_empresa(codigo)` e `gerar_sped_fiscal()`, cada uma devolvendo
`True`/`False` em vez de só imprimir e `return` do `main()`) — assim
tanto os scripts isolados quanto o loop novo reaproveitam o mesmo
código, sem duplicar. Os dois scripts antigos viraram wrappers finos,
comportamento inalterado.

**`scripts/executar_lote.py`** — carrega a lista, pergunta o regime
(igual `selecionar_empresas.py`), pede confirmação explícita
("sim"/"não") antes de mexer em qualquer tela, e só então roda
`trocar_empresa` + `gerar_sped_fiscal` pra cada empresa selecionada,
uma de cada vez. Falha numa empresa não trava as outras (registrada
como "falha ao trocar de empresa" ou "falha na geração" no resumo
final) — erro isolado por empresa, como o roadmap (seção 6) já previa.

**Trava de segurança de propósito:** por padrão só aceita
`data/empresas.exemplo.csv` — pra rodar contra `data/empresas.csv`
(planilha real) precisa passar `--real` explicitamente. Ainda não
existe validação de conteúdo na empresa-alvo real (competência já
fechada/entregue, seção 5.7) rodando em lote — só a Fase 4 numa empresa
de teste isolada (seção 0.11) foi provada até agora. `--real` fica
disponível pra quando isso acontecer, mas o padrão continua seguro.

**Ainda não faz:** trocar a competência (Período) por empresa — usa a
que já estiver selecionada na tela para todas da lista. Só faz sentido
rodar `--real` depois de conferir que essa competência serve pra todas
as empresas do lote (ou estender o motor pra também definir o período
por empresa, ainda não construído).

### 0.18 Ponto de entrada único — menu + atalho .bat

Pedido do usuário: "ir pra prática", com uma interface amigável — abrir
o Domínio, apertar num "app", e pronto (ou com poucas instruções). Até
aqui existiam 4 scripts separados (`explorar.py`, `trocar_empresa.py`,
`selecionar_empresas.py`, `executar_lote.py`) — o usuário precisava
saber qual rodar pra cada situação, sempre por linha de comando.

**`scripts/app.py`** — menu de texto único: pergunta se o Domínio está
aberto, depois numera as opções (rodar em lote por exemplo, rodar em
lote real, trocar só a empresa, gerar SPED só na empresa já
selecionada, sair). Reaproveita só o que já existia em `app/dominio.py`
(`executar_lote()`, movida de `scripts/executar_lote.py` pra lá nesta
mesma rodada, mesmo motivo de reuso das seções 0.14/0.17 — script e
menu chamam a mesma função, não duplicam lógica).

**`Abrir Motor SPED.bat`** (raiz do repositório) — atalho de duplo
clique que entra na pasta certa sozinho (`cd /d "%~dp0"`, resolve pelo
caminho do próprio `.bat`, não depende de qual pasta o usuário abriu o
cmd) e roda `python scripts\app.py`, com `pause` no final pra não
fechar a janela sozinho (dá pra ler o resultado/erro). Resolve de
propósito o erro de "diretório errado" que já aconteceu antes nesta
sessão.

**`Atualizar.bat`** (raiz do repositório) — mesma ideia, mas roda
`git pull origin main`. Existe porque esquecer de atualizar antes de
rodar já causou confusão mais de uma vez nesta sessão (script antigo
rodando sem os achados mais recentes).

**Ainda é texto, não janela gráfica** — "interface amigável" aqui
significa duplo clique + menu numerado, não uma janela com botão. Uma
janela de verdade (Tkinter ou outra) é possível depois se for pedida,
mas o roadmap (seção 6) já reservava "Painel" pra Fase 8+, bem depois
de onde o projeto está agora — não antecipado sem pedido explícito.

### 0.19 Print de erro precisa identificar a empresa, senão uma falha apaga a evidência da outra

Pedido do usuário sobre o lote: em caso de erro, salvar o print e
seguir pra próxima empresa — já era o comportamento (seção 0.17:
`trocar_empresa()`/`gerar_sped_fiscal()` sempre devolviam `False` e
`executar_lote()` já continuava o loop). O que faltava: todo print de
erro usava nome fixo (`erro_ancora_ok.png`, `erro_fechar.png`, etc.) —
rodando várias empresas no mesmo lote, a falha da empresa B
**sobrescrevia** o print da falha da empresa A no mesmo passo, perdendo
a evidência de A justamente quando mais precisa (lote com mais de uma
falha).

**Corrigido:** `trocar_empresa()` e `gerar_sped_fiscal()` ganham
parâmetro `prefixo` (padrão `""`, sem mudança pro uso isolado);
`executar_lote()` passa o código da empresa como prefixo
(`f"{codigo}_"`), então cada print de erro carrega o código de qual
empresa ele é (ex.: `78_erro_fechar.png`). Resumo final agora também
avisa que os prints de erro estão em `capturas/` quando alguma empresa
falhou.

### 0.20 Segundo documento por empresa: EFD Contribuições, escolhido por `tipo`/`sped`

Pedido do usuário: nem toda empresa precisa só de SPED Fiscal/ICMS —
existe um documento irmão no mesmo menu do Domínio (Federais), **EFD
Contribuições** (PIS/COFINS), e cada empresa pode precisar de um dos
dois ou dos dois. O usuário já preencheu a planilha real com duas
colunas novas pra decidir isso por empresa:

- **`tipo`**: `1` (só um documento) ou `2` (os dois, ICMS e
  Contribuições, ignorando a coluna `sped`).
- **`sped`**: qual documento, só relevante quando `tipo` é `1`
  ("ICMS" ou "Contribuições").

**Implementado (`app/empresas.py`):**
- `carregar_empresas()` lê as duas colunas, com nome de cabeçalho
  tolerante a maiúscula/espaço (`Tipo`, `TIPO `, `tipo` são a mesma
  coisa) — não dá pra exigir grafia exata de quem preenche a planilha
  no Excel. Sem essas colunas no arquivo (compatível com listas
  antigas), toda empresa vira `tipo=1, sped=ICMS` — comportamento
  igual ao de antes dessas colunas existirem.
- `documentos_necessarios(empresa)` devolve `["ICMS"]`,
  `["CONTRIBUICOES"]` ou os dois. Comparação de `sped` tolerante
  (minúsculo, sem acento, substring — "ICMS", "Contribuições",
  "CONTRIBUICOES" e "contrib" todos funcionam), mesmo espírito de
  `achar_texto()` no resto do motor.

**Implementado (`app/dominio.py`):**
- `executar_lote()` agora chama `documentos_necessarios(empresa)` e
  gera cada um pela função certa (`_GERADORES`), com prefixo de print
  de erro incluindo também o documento, não só o código da empresa
  (ex.: `78_CONTRIBUICOES_erro_fechar.png` — mesmo motivo da seção
  0.19: dois documentos da mesma empresa não podem se sobrescrever).
  Falha isolada por documento também, não só por empresa. Resumo final
  lista o status de cada documento separadamente.
- `gerar_efd_contribuicoes()` — implementada depois da exploração da
  seção 0.21, mas **ainda não confirmada rodando de ponta a ponta por
  este código** (só a tela e a confirmação de sucesso foram vistas,
  clicando na mão).
- `data/empresas.exemplo.csv` ganhou as duas colunas nas linhas de
  demonstração já existentes, incluindo uma com `tipo=2` (`9997
  EXEMPLO REAL`) e uma com `sped=CONTRIBUICOES` (`9998 EXEMPLO
  PRESUMIDO`) — dá pra testar os três casos.

### 0.21 Exploração de EFD Contribuições — mesma estrutura de tela, confirmação de sucesso diferente

Passo de campo pedido pela seção 0.20: antes de escrever
`gerar_efd_contribuicoes()`, o usuário navegou até
Relatórios > Informativos > Federais no Domínio real e mandou prints.

**Achado 1 — nome exato do item de menu:** "EFD Contribuições",
segundo item da lista, logo abaixo de "SPED Fiscal". A lista completa
do submenu Federais é grande e tem itens parecidos (EFD-Reinf, DIRBI,
Sintegra, MIT, DCTF, DACON, DNF, DIRF, DIPJ, DASN, DeSTDA, DEFIS,
Receitas MEI, comprovantes de retenção, SINCO, SVA, IBGE) — em
particular **"EFD-Reinf" e "EFD Contribuições" começam com o mesmo
prefixo "EFD"**, então o alvo de busca não pode ser só "EFD": usa
"Contribui" (só bate com "Contribuições").

**Achado 2 — a tela de geração tem a mesma estrutura que SPED Fiscal:**
Período (Data inicial/final), opção de contador diferente, Arquivo
(Caminho), e a coluna de botões à direita **na mesma ordem**: OK,
Fechar, Empresas..., depois botões específicos dessa obrigação (SCP,
Outros dados..., INSS - Bloco P, no lugar de Inventário/Valores
Agregados/Convênio 115 da tela de SPED Fiscal), Auditar Arquivo...,
Visualizar Arquivo, Concluir Atividade..., Conteúdo..., Soluções. Como
OK/Fechar/Empresas... ficam na mesma posição relativa, a técnica de
âncora da seção 0.10 (achar "Empresas...", recortar a vizinhança,
achar "OK" ali) se aplica sem mudança nenhuma.

**Achado 3 — a confirmação de sucesso NÃO usa o mesmo texto.** O
usuário clicou OK na mão e mandou o print: caixa de diálogo título
**"Aviso"** (não "EFD Contribuições" como seria de se esperar por
analogia ao título "SPED Fiscal" da confirmação anterior — mas isso não
importa pro código, que nunca leu o título, só o corpo), ícone de
informação, texto **"Arquivo gerado com sucesso."** — diferente de
"Final da exportação." do SPED Fiscal. Se o código tivesse reaproveitado
a âncora "exporta" sem ajuste, teria travado sempre nessa tela. Âncora
usada para Contribuições: "sucesso".

**Refatoração:** com as duas telas confirmadas estruturalmente iguais
(só o item de menu e o texto de confirmação mudam), o que antes era só
`gerar_sped_fiscal()` virou uma função genérica
`gerar_sped(item_menu, texto_confirmacao, prefixo="")`, com
`gerar_sped_fiscal()` e `gerar_efd_contribuicoes()` como wrappers finos
passando os dois textos certos. Evita duas cópias quase idênticas de
~90 linhas.

**Nota lateral de segurança:** o campo Arquivo/Caminho da tela de EFD
Contribuições mostrado no print é
`M:\Users\darto\Dropbox\servidor LUCRATIVA 2024\1.0 E...` — parece
caminho de servidor/Dropbox real do escritório, não um caminho de
teste isolado como `M:\teste-docauto\...` (seção 0.10). Não é perigoso
por si só (gerar o arquivo continua sendo só exportação, não altera
lançamento nem transmite — seção 5.7), mas vale conferir esse caminho
antes de rodar em lote de verdade, pra não gerar/sobrescrever um
arquivo num lugar que outra pessoa do escritório já usa pra outra
coisa.

**Ainda em aberto:** `gerar_efd_contribuicoes()` nunca rodou de ponta a
ponta pelo próprio código — só a tela e a confirmação foram vistas
manualmente. Falta confirmar que `achar_texto` encontra "Contribui" no
submenu (nunca testado) e que o restante do fluxo (OK, espera,
Enter, Fechar) funciona igual ao do SPED Fiscal nessa tela específica.

### 0.22 Primeiro teste real de `gerar_efd_contribuicoes()`: âncora "Empresas..." falhou até na tela inteira

Rodando `scripts/explorar_contribuicoes.py` pela primeira vez: passos
1-4 funcionaram perfeitamente (achou "Contribui" no submenu Federais,
clicou, tela abriu). O passo 5 (achar "Empresas..." como âncora pro
botão OK, seção 0.10) **falhou** — e dessa vez não só "OK": nenhum dos
4 botões do topo da coluna (OK, Fechar, Empresas..., SCP) apareceu na
leitura da tela inteira, apesar de estarem visivelmente nítidos no
print (confirmado — não é problema de renderização nem de recorte,
o Tesseract simplesmente não segmentou aquela faixa da tela dessa vez).
Diferente do problema original da seção 0.10 (só "OK" sumia,
"Empresas..." sempre lia certo) — aqui a âncora que sempre funcionou
falhou também.

**Tentativa 1 (não funcionou): Enter como retaguarda.** Hipótese: como
"OK" é sempre o primeiro botão da coluna nessa família de telas, ele
seria o botão padrão do diálogo (convenção do Windows), e Enter
ativaria ele sem precisar achar nada por OCR — mesmo mecanismo já
validado pra confirmação de sucesso (seção 0.13). **Testado contra o
Domínio real e não funcionou** — Enter não clicou em OK (achado real do
usuário). Diferente da confirmação de um botão só, o diálogo de vários
botões (OK/Fechar/Empresas/...) não trata Enter como "ativa o botão
padrão" do mesmo jeito. **Não usar Enter de novo pra esse caso** —
`interacao.pressionar_enter()` foi atualizada pra deixar isso registrado
na própria docstring.

**Tentativa 2 (não funcionou): esperar por estado antes de desistir da
âncora.** Hipótese: a tela remota do GO-Global ainda não tinha
terminado de desenhar aquela faixa no instante da captura — mesma
classe da seção 0.12 (tempo fixo nem sempre basta). **Testado contra o
Domínio real e não funcionou**: as 5 tentativas (~1s cada) devolveram
a **mesma lista de palavras, idêntica byte a byte, todas as vezes** —
prova que não é timing (se fosse, o texto teria variado ou aparecido
em algum momento das 5 capturas). A causa real de por que "Empresas...
"/"OK"/"Fechar"/"SCP" não leem na tela inteira continua desconhecida,
mas descartamos timing como explicação.

**Solução 3 (adotada): recortar pela área do próprio diálogo antes de
procurar "OK", em vez de indireção via "Empresas...".** Mesma lição da
seção 0.3 (tela inteira não confia, recorte resolve), aplicada de novo:
o **título** do diálogo (a mesma string de `item_menu` — "SPED
Fiscal"/"EFD Contribuições" — continua lendo certo, inclusive nas
tentativas que falharam pra achar os botões) serve de âncora pra
recortar uma janela grande (`tela.recortar_a_partir_de()`, nova,
estende principalmente pra direita/baixo a partir de um ponto)
cobrindo o diálogo inteiro, incluindo a coluna de botões. Dentro desse
recorte bem menos ruidoso, procura "OK" **direto** — pedido do usuário
("não procuramos Empresas, procuramos OK"), sem a indireção da seção
0.10. O mesmo recorte-por-título substitui a âncora "Empresas..." no
passo de fechar a tela (passo 8) também, por consistência.

**Resultado do teste real: o recorte por título resolveu "Empresas..."
e "Fechar" (leram certo, coisa que nunca tinha acontecido na tela
inteira), mas "OK" continuou ilegível mesmo dentro do recorte, a
escala=4.** Ou seja: recortar reduz ruído de verdade (achado
confirmado), mas não é a causa raiz do problema específico de "OK" —
esse texto de 2 letras parece ser um caso limite ruim pro Tesseract
neste app, independente de quanto se reduza o ruído ao redor.

**Solução final (adotada): nunca ler "OK" — calcular a posição por
aritmética a partir de "Fechar" e "Empresas..."**, que agora leem
certo de forma confiável dentro do recorte por título. Mesma ideia já
usada antes (seção 0.10), só que agora dentro do recorte confiável em
vez da tela inteira (que falhava até pra essas duas). `gerar_sped()`
acha as duas âncoras dentro de `area_dialogo`, calcula o espaçamento
entre elas, e aplica esse espaçamento acima de "Fechar" pra achar "OK"
— nunca precisa que o OCR leia "OK" de jeito nenhum.

**Regra consolidada:** "OK" nesta aplicação nunca deve ser um alvo
direto de OCR — sempre por aritmética a partir de botões vizinhos
legíveis, com o recorte certo (por título do diálogo) só pra tornar
essa vizinhança confiável.

**Confirmado por rodada real completa:** com essa correção somada à
seleção de competência (seção 0.23), `gerar_efd_contribuicoes()` rodou
ponta a ponta pela primeira vez sem travar — navega, seleciona
competência, calcula e clica OK, espera a confirmação (achou na 5ª
tentativa, ~16s — reforça por que a espera por estado da seção 0.12
importa), confirma com Enter, fecha. Marco: as duas telas de geração
(SPED Fiscal e EFD Contribuições) agora compartilham a mesma
`gerar_sped()` já validada de ponta a ponta nas duas.

### 0.23 Preencher a competência anterior automaticamente — testado uma vez, integrado ao fluxo principal

Pedido do usuário: em vez de confiar no período que já estiver na tela
(sobra de teste manual anterior, arriscado), o motor deveria sempre
selecionar o **mês fechado anterior ao atual**, inteiro, usando mouse e
teclado — reforça na prática a regra de segurança da seção 5.7 (nunca
operar sobre competência corrente/em aberto).

**`app/dominio.py::competencia_anterior()`** — calcula `(data_inicial,
data_final)` do mês anterior ao atual, formato `DD/MM/AAAA`. Testado
isoladamente (sem precisar do Domínio) contra vários casos de virada
(início de ano, fevereiro em ano bissexto e não bissexto): correto em
todos.

**`app/dominio.py::selecionar_competencia_anterior()`** — acha o rótulo
"Data inicial" por OCR, clica num ponto estimado à direita dele (onde
fica o campo de valor, não o rótulo em si), `Ctrl+A` pra selecionar o
valor atual (`interacao.selecionar_tudo()`, nova), digita a data
calculada por cima, `Tab` pra confirmar.

**Primeiro teste real (`scripts/explorar_competencia.py`): o clique no
campo "Data inicial" funcionou** (posição estimada bateu). **Achado do
usuário: não precisa clicar no campo "Data final"** — `Tab` ao terminar
de digitar o primeiro já leva o foco pro segundo campo sozinho (ordem
de tabulação do formulário).

**Segundo teste real: o valor não mudou.** O campo continuou mostrando
uma data antiga (`01/09/2010`, resto de outro teste) em vez da
competência calculada — ou seja, `selecionar_tudo()` (`Ctrl+A`) +
digitar **não substituiu nada**, silenciosamente. Duas causas prováveis,
as duas corrigidas: (1) esse é um campo **mascarado**
(`99/99/9999`) e `Ctrl+A` não é um jeito confiável de selecionar o
conteúdo dele — troca pra `Home` + `Shift+End`
(`interacao.selecionar_tudo_alternativo()`, mais universal entre tipos
de campo); (2) digitar a data **com barra** (`01/08/2026`) pode
confundir o cursor da máscara, que já insere as barras sozinha — troca
pra digitar **só os dígitos** (`01082026`).

**Verificação adicionada, essencial:** como o preenchimento já falhou
silenciosamente uma vez, `selecionar_competencia_anterior()` agora
**confere por OCR**, depois de digitar, se os dois campos realmente
mostram a competência esperada — só devolve `True` se confirmar os
dois. Sem essa conferência, uma falha silenciosa parecida deixaria o
motor gerar a obrigação pra uma competência errada, sem ninguém
perceber — exatamente o risco que essa funcionalidade existe pra
evitar (seção 5.7).

**Integrada ao fluxo principal**: pedido do usuário — "deixe a
competência automática pra todos". `gerar_sped()` agora chama
`selecionar_competencia_anterior()` sempre, entre abrir a tela (passo 4)
e clicar OK (passo 5), pra SPED Fiscal e EFD Contribuições igual — não
é mais uma função isolada só de teste. Se não achar "Data inicial" ou
não confirmar os valores depois, a geração inteira para (nunca
prossegue com competência desconhecida ou errada).

### 0.24 Achado do usuário: clique em linha reta pro item de menu podia colidir com item vizinho ("Estaduais")

Pedido do usuário, a partir de um print mostrando o submenu de
"Informativos" com "Federais" e "Estaduais" empilhados na mesma
coluna: cuidado pra não passar o mouse por cima de "Estaduais" no
caminho até um item dentro do submenu de "Federais".

Risco real, visto na própria lógica do passo 4 de `gerar_sped()`: depois
de `interacao.passar_mouse()` em "Federais", o mouse fica parado na
posição de "Federais" (ex.: `(624, 104)`). O passo seguinte usava
`interacao.clicar()` direto no item de menu dentro do submenu que
abriu (ex.: "Contribui" em `(786, 129)`) — um clique "devagar" que
começa com `pyautogui.moveTo()` **em linha reta (diagonal)** da posição
atual até o alvo.

"Estaduais" fica logo abaixo de "Federais", na mesma coluna (mesmo x
aproximado). Uma linha reta de `(624, 104)` até `(786, 129)` cruza, na
diagonal, a faixa de altura onde "Estaduais" fica — mesmo que o x final
do alvo já esteja fora da coluna de "Estaduais", o trecho inicial do
movimento passa por cima dela. Se isso disparar o hover de "Estaduais"
no meio do caminho, o submenu aberto troca pro dela antes do clique
final acontecer — o clique acerta um item da lista errada (itens
estaduais, não federais), sem nenhum erro visível pro OCR detectar
depois (o item clicado existe, só que é o errado).

**Correção:** `interacao.clicar_com_desvio()` (nova), usada só nesse
passo 4. Em vez de ir direto em linha reta, move em L: primeiro na
horizontal, mantendo a altura atual do mouse (ainda a altura de
"Federais", não a de "Estaduais" — não desce ainda), só depois na
vertical, já com o x dentro da coluna do submenu de "Federais" (longe
da coluna de "Estaduais"). Garante que o mouse nunca ocupa, ao mesmo
tempo, uma posição dentro da faixa de "Estaduais". Não depende de saber
a coordenada exata de "Estaduais" — funciona pra qualquer item vizinho
abaixo do item pai, é a mesma lógica geométrica sempre. **Ainda não
testado contra o Domínio real** (defeito nunca chegou a se manifestar
num teste — correção preventiva a partir da inspeção do menu).

### 0.25 Primeiro erro real do Domínio contra dado real: caminho de arquivo inválido — motor não sabia parar

Primeiro teste da opção 5 (EFD Contribuições) contra empresa **real**
(depois de cadastradas as pastas das empresas). O Domínio recusou a
geração com uma caixa de erro (título "Atenção"): "O caminho
especificado não é válido. Exemplo: 'c:\sped.txt'." — a tela de
geração (Período/Arquivo) continuou aberta atrás dela.

**O motor não sabia disso.** `esperar_e_achar()` só verificava o texto
de sucesso (`texto_confirmacao`, ex.: "sucesso") — sem achar, insistia
as 15 tentativas inteiras (~30s) esperando um sucesso que nunca ia
aparecer, sem nunca reconhecer que já tinha uma resposta (um erro) na
tela desde a primeira tentativa. Pedido do usuário: não esperar só
pelo sucesso; reconhecer erro, salvar print, dispensar a caixa e
seguir em frente.

**Correção:** `esperar_e_achar()` agora verifica, a cada tentativa,
também `texto_erro` (novo parâmetro, padrão `"Atenção"`) — devolve
`(imagem, posição, houve_erro)` em vez de só `(imagem, posição)`.
`gerar_sped()` trata `houve_erro=True` como falha imediata: salva a
evidência (`{prefixo}erro_dominio.png`), dispensa a caixa com Enter
(mesmo diálogo de um botão só da seção 0.13, não precisa ler "OK"),
fecha a tela de geração que ficou aberta atrás (`_fechar_tela_geracao()`,
nova — passo 8 virou função própria, reaproveitada tanto no sucesso
quanto aqui) e devolve `False` — quem chamou (`executar_lote()`) já
sabe lidar com `False`: registra a falha daquele documento/empresa e
segue pra próxima, sem travar o lote inteiro (seção 6 do roadmap).

**Limite conhecido:** a detecção é só por esse título específico
("Atenção"), a única forma de erro vista até agora. Se aparecer erro
com título diferente, ainda cai no caminho antigo (espera as 15
tentativas, devolve falha genérica por timeout) — não trava, só demora
mais e a mensagem de log é menos específica. Ajustar quando aparecer
um exemplo real diferente, mesmo princípio de toda esta documentação
(nunca chutar título antes de ver o erro de verdade).

**Ainda pendente, fora do código:** o motivo do erro em si — "caminho
especificado não é válido" — é uma configuração dentro do próprio
Domínio (provavelmente o campo de pasta/arquivo de destino da empresa,
distinto do cadastro de pastas mencionado pelo usuário) que precisa
ser corrigida por fora, não é algo que o motor deva tentar adivinhar
ou preencher sozinho (fora do escopo de automação — é decisão/dado
que só o usuário tem).

### 0.26 Primeiro lote real com várias empresas: tela antiga aberta contaminava o passo seguinte

Primeiro teste de `executar_lote()` contra empresas **reais**, várias
seguidas. Dois lugares diferentes, mesma causa raiz: um passo falhava
no meio, devolvia `False`, mas a tela que tinha acabado de abrir
**continuava aberta** — e o próximo passo do lote (documento seguinte,
ou empresa seguinte) já rodava por cima dela, achando texto da tela
errada em vez da tela nova que esperava encontrar.

**Caso 1 — SPED Fiscal (empresa 68) contamina o EFD Contribuições
seguinte.** `gerar_sped()` clicou no item de menu certo, confirmou a
competência, mas falhou ao ler o título do diálogo — o OCR leu "SPED"
como **"spEo"** dessa vez (achado real: nem o título, até agora tratado
como sempre confiável, seções 0.8/0.22, é imune a erro pontual de
OCR). `gerar_sped()` devolveu `False` **sem fechar a tela**, que
continuou aberta. O próximo documento (EFD Contribuições) começou sua
navegação por cima dela: o "título" achado depois era, na real, texto
da tela de SPED Fiscal ainda aberta (mesmas palavras nos dois prints
de debug: "Editar Arquivo...", "Visualizar Arquivo", "Concluir
Atividade...", "Conteúdo..."), o recorte saiu errado, e a busca por
"Empresas.../Fechar" falhou.

**Caso 2 — Troca de empresas (empresa 70) contamina o SPED Fiscal
seguinte.** `trocar_empresa()` clicava em "Acessar" e só esperava
`time.sleep(1)` fixo antes de devolver `True` — sem confirmar que a
tela de busca de empresa realmente tinha fechado. O passo seguinte
(clicar Relatórios) já rodou com ela ainda aberta atrás: o print de
debug mostra o grid de busca ("Busca por Código", "Só deste módulo",
"Ocultar inativas", cabeçalho "Apelido") em vez do menu Informativos.

**Regra consolidada, a mesma da seção 0.12 (esperar por estado, não
por tempo fixo) aplicada agora também a "fechar"/"a tela anterior
sumiu", não só a "a confirmação apareceu":**

- `trocar_empresa()` agora espera, por estado (até 10 tentativas de
  1s), o botão "Acessar" sumir da tela antes de devolver `True` — só
  então a próxima ação (abrir Relatórios) pode confiar que a tela
  anterior já fechou.
- `gerar_sped()` agora chama `_fechar_tela_geracao()` (best-effort)
  em **toda** saída `False` depois do item de menu clicado — falha ao
  selecionar competência, falha ao achar o título, falha ao achar
  "Empresas.../Fechar", timeout esperando confirmação, Enter que não
  fechou a confirmação — não só no caminho feliz (passo 8) e no erro
  do Domínio (seção 0.25). Uma falha no meio nunca deveria deixar a
  tela pra trás mais.
- `_fechar_tela_geracao()` agora tenta achar o título **duas vezes**
  (com 1s de pausa) antes de concluir "já fechou sozinha" — pro mesmo
  motivo do Caso 1: um "não achei" pode ser só um erro pontual de OCR
  no título, não a tela realmente fechada, e assumir o contrário é
  exatamente o que causou a contaminação.

**Ainda não testado de ponta a ponta contra o Domínio real** — as
correções respondem exatamente ao que o print do lote real mostrou,
mas o próximo lote real é que confirma se resolveu.

### 0.27 Empresa real com bastante movimento demora mais pra exportar que o teto antigo de espera

Depois das correções da seção 0.26, `gerar_sped_fiscal()` rodou de
ponta a ponta certinho até o clique em OK (menu, competência, cálculo
de OK a partir de "Fechar" — tudo igual às rodadas validadas antes).
Só que a confirmação de sucesso ("exporta") nunca apareceu dentro do
teto de 15 tentativas (~36s, seção 0.12).

**Não é falha de OCR:** as 13 leituras feitas nesse tempo mostram a
mesma tela de parâmetros parada, palavra por palavra praticamente
idêntica — sinal de que a exportação ainda estava rodando, não de que
o texto de sucesso estava lá e o OCR não achava. Essa empresa real
tem bem mais opção configurada que a de teste (Identificação dos
produtos: Inventário; Tipo de Atividade: Industrial; Contas
Analíticas; Gera as contas contábeis/unidade de medida por Código) —
sinal de bastante movimento fiscal de verdade, natural que demore mais
que a exportação quase instantânea da empresa de teste/demonstração.

**Correção:** teto de `esperar_e_achar()` (`tentativas`) subiu de 15
pra 90 — de ~36s pra ~3 minutos de espera total antes de desistir.
Número de partida, não medido com precisão (não sabemos ainda quanto
tempo uma exportação real de verdade leva) — ajustar com mais dado
real conforme aparecer (mesmo princípio de todo este documento: número
por evidência, não chute). Se 3 minutos ainda não bastar pra alguma
empresa bem maior, o sintoma vai ser o mesmo (tela parada, sem
confirmação, sem erro) e a correção é só subir o número de novo.

### 0.28 Falso "Enter não fechou" por atraso de repintura + foco perdido pro console no meio do lote

Depois da seção 0.27 (mais tempo de espera), o SPED Fiscal dessa mesma
empresa real **achou** a confirmação ("Final da exportação.") — a
espera maior resolveu. Mas dois problemas novos apareceram na
sequência, os dois de causa bem diferente de "OCR ruim":

**1. Falso negativo no "Enter fechou a confirmação?".** Depois do
Enter, a checagem (só 1 tentativa, 1s de espera) ainda achou o texto
"exporta" na tela e concluiu "Enter não fechou". Só que, alguns
segundos depois, `_fechar_tela_geracao()` (chamado pela própria rotina
de erro) **já não achava mais a tela de geração** — ou seja, ela tinha
mesmo fechado, só que depois daquela checagem de 1s. Não é problema de
ler o texto errado (o texto lido era o texto certo, "Final da
exportação." saiu legível no print de debug) — é a tela remota
(GO-Global) demorando mais que 1s pra repintar depois de fechar um
diálogo por cima de um formulário grande e cheio de campo (esse SPED
Fiscal em particular tem bem mais campo que o de teste, seção 0.27).
Resultado: um documento que **tinha sido gerado com sucesso** foi
registrado como falha.

**2. Foco saiu do Domínio no meio do lote, foi pro console do
script.** Logo depois desse falso negativo, o próximo passo (abrir
Relatórios pro documento seguinte) leu, no print de debug, o texto da
**janela do terminal** ("dominio-automation-engine — Explora...",
"C:\WINDOWS\system32\cmd.exe") em vez do menu do Domínio — o clique em
"Relatórios" foi na janela errada. Dali em diante, a "Troca de
empresas" da empresa seguinte também falhou (F8 foi pra janela
errada). `focar_dominio()` (seção 0.6) só era chamado uma vez, no
começo do lote inteiro — nada garantia o foco de novo depois, se algo
(nem sabemos exatamente o quê — Windows trocando janela em primeiro
plano por conta própria é comum com bastante atividade de tela) o
tirasse no meio do caminho.

**Correções, nenhuma delas mexe em OCR/zoom** (não era o problema —
o texto sempre leu certo quando a tela certa estava na frente):

- Checagem pós-Enter agora tenta até 3 vezes (1s entre elas) antes de
  concluir "não fechou" — mesmo princípio da seção 0.12/0.26, espera
  por estado.
- `trocar_empresa()` e `gerar_sped()` agora chamam
  `interacao.focar_dominio()` no próprio início, não só uma vez no
  começo do lote — refaz o foco antes de cada ação de alto nível, pra
  aguentar o foco sumir no meio de um lote longo sem que isso derrube
  as empresas seguintes em cadeia.

**Ainda não testado de ponta a ponta** — resposta direta ao que os
dois prints mostraram, próximo lote real confirma.

### 0.29 Confirmação de sucesso visível na tela mas invisível pro OCR de tela inteira — mesmo problema da seção 0.10, agora na confirmação

Print real enviado pelo usuário: a caixa "SPED Fiscal" / "Final da
exportação." apareceu, clara e legível, sobre o formulário cheio de
campo dessa empresa real. Mesmo assim, `esperar_e_achar()` não achava
("Ainda não achei 'exporta'") rodada após rodada.

**Não é o texto sumindo nem demora** (isso já foi corrigido nas seções
0.27/0.28) — é o mesmo problema da seção 0.10: tela cheia demais
confunde a segmentação do Tesseract. Lá, a solução foi nunca ler "OK"
na tela inteira, só depois de recortar a área do diálogo por uma
âncora conhecida (o título). Aqui não tem âncora conhecida de
antemão — a caixa de confirmação pode aparecer em qualquer momento,
não se sabe a posição dela até achar.

**Correção:** nova `tela.recortar_centro()` (recorta 60% do centro,
sem precisar de âncora — caixa de diálogo do Windows nasce quase
sempre centralizada na janela pai) e `tela.achar_texto_ou_no_centro()`
— tenta a tela inteira primeiro, e só se falhar tenta de novo no
recorte central antes de desistir. Nunca troca a busca em tela
inteira, só reforça quando ela falha.

**Pedido do usuário: aplicar em todo ponto sensível, não só na
confirmação.** Trocado `tela.achar_texto()` por
`tela.achar_texto_ou_no_centro()` em todo lugar que lê texto direto da
tela cheia sem recorte prévio por âncora (o mesmo risco da seção 0.10
não se limita à confirmação):

- `esperar_e_achar()` — confirmação de sucesso e caixa de erro
  (o próprio achado desta seção).
- `trocar_empresa()` — botão "Acessar" (abertura e verificação de que
  a tela realmente fechou, seção 0.28).
- `gerar_sped()` — título do diálogo de geração (passo 5) e a
  checagem pós-Enter (seção 0.28).
- `_fechar_tela_geracao()` — as duas tentativas de achar o título.
- `selecionar_competencia_anterior()` — rótulo "Data inicial" e a
  conferência pós-digitação dos dois campos de data.

**Não trocado** (recorte central atrapalharia, não ajudaria): buscas
que já rodam dentro de um recorte pequeno feito por âncora conhecida
("Empresas.../Fechar" dentro de `area_dialogo`, "Fechar" dentro de
`area_fechar`, "Relatórios" dentro de `recortar_topo`, itens de menu
dentro de `recortar_area_menu`) — recortar essas imagens já pequenas
ainda mais pro centro cortaria texto que fica perto da borda.

**Ainda não testado de ponta a ponta** — próximo teste real confirma
se o recorte central resolve pra esse caso e não atrapalha os outros.

### 0.30 EFD Contribuições gerou com sucesso mas não fechou a tela — achou o título, não achou "Fechar", e desistiu na primeira

Rodada real: EFD Contribuições gerou certinho (confirmação "sucesso"
achada, Enter fechou ela). Só que a tela de geração (Período/Opções)
não fechou depois — o usuário reportou que a próxima troca de empresa
rodou com ela ainda aberta.

**Causa:** `_fechar_tela_geracao()` já tentava achar o título duas
vezes (seção 0.26/0.28) — e achou, na segunda tentativa. Mas depois de
achar o título, a busca por "Fechar" dentro do recorte só tentava
**uma vez**; falhou, e a função desistiu direto (`return False`),
deixando a tela aberta pra trás. Título e "Fechar" podem falhar no OCR
de forma independente — corrigir só a espera de um dos dois não cobre
o outro.

**Correção:** `_fechar_tela_geracao()` agora tenta achar o título E o
"Fechar" até 3 vezes cada, numa mesma volta (recaptura a tela a cada
tentativa) — só desiste de vez se "Fechar" nunca aparecer em nenhuma
das 3. Continua distinguindo "nunca achei o título" (conclui "já
fechou sozinha", `True`) de "achei o título mas nunca achei Fechar"
(conclui "ficou aberta, não consegui fechar", `False` com print de
erro) — são situações diferentes, tratamento diferente.

**Ainda não testado de ponta a ponta.**

### 0.31 "Fechar" achado antes do OK, ilegível 3 tentativas seguidas depois — reaproveitar a posição já conhecida em vez de reler

Mesmo depois da correção da seção 0.30 (3 tentativas), uma rodada real
travou de novo: título achado, mas "Fechar" não achado **nas 3
tentativas seguidas** — não foi um acaso pontual dessa vez, foi
persistente durante toda aquela janela de tempo.

**Observação do usuário, decisiva:** a posição de "Fechar" **já tinha
sido achada antes**, no mesmo `gerar_sped()` — é o próprio ponto de
referência usado pra calcular a posição de "OK" por aritmética (seção
0.13/0.22). O diálogo não muda de lugar entre abrir e clicar OK e
fechar depois — não tem por que reler "Fechar" por OCR uma segunda vez
quando a posição de tela cheia já é conhecida e confiável desde o
início da mesma chamada.

**Correção:** `gerar_sped()` agora guarda `pos_fechar_conhecido`
(coordenada de tela cheia) logo depois de calcular a posição de "OK",
e passa isso pra `_fechar_tela_geracao()` em toda chamada dentro da
mesma execução. Se informado, a função tenta clicar **direto nessa
posição primeiro**, confirma que o título sumiu, e só cai pro jeito
antigo (achar título e "Fechar" de novo por OCR, com retry) se esse
clique não fechar de verdade. Elimina a dependência de reler "Fechar"
por OCR no caso comum — só recorre a isso como reforço.

**Ainda não testado de ponta a ponta.**

### 0.32 IA de decisão em caixa de erro/aviso desconhecida (`app/erros.py` + `app/ia.py`)

Até aqui, toda caixa de erro/aviso do Domínio (título "Atenção", seção
0.25) tinha um único destino: salvar print, apertar Enter, fechar a
tela, marcar falha — mesmo quando a mensagem era só um aviso
informativo que não devia impedir a geração. Pedido do usuário:
adicionar uma IA leve (Claude Haiku) que decide o que fazer com uma
caixa **nunca vista antes**, mas só entre um conjunto fixo de ações —
nunca com liberdade de clicar/digitar o que quiser — e **sem nunca ver
a tela**: só o texto da caixa, lido por OCR localmente e anonimizado
antes de sair da máquina.

**Fluxo (`app/erros.py`, `app/ia.py`):**

1. `esperar_e_achar()` agora reconhece dois títulos de caixa
   (`TITULOS_ERRO = ("Atenção", "Aviso Empresa")`), não só "Atenção" —
   achado real (prints `52_CONTRIBUICOES_erro_dominio.png`,
   `52_CONTRIBUICOES_depois_fechar.png`): o Domínio também mostra
   aviso com o título "Aviso Empresa: <código>" (ex.: "Saldo dos
   impostos não foram calculados no período: 08/2026"), estrutura
   diferente da caixa "Atenção" de erro de verdade, e que o código
   antigo não reconhecia (caía no caminho genérico de timeout).
2. Ao achar uma dessas caixas, `gerar_sped()` lê o texto dela por OCR
   num recorte pequeno ao redor (`app.dominio._ler_texto_caixa()`,
   reaproveita `tela.recortar_ao_redor()` — nunca a tela inteira) e
   manda pra `erros.decidir()`.
3. `erros.decidir()` **sempre** anonimiza o texto primeiro
   (`erros.anonimizar()`): número (CNPJ/CPF/data/valor/código) vira
   `#`; caminho de arquivo vira `<CAMINHO>`; e-mail vira `<EMAIL>`;
   sequência de palavra em MAIÚSCULO que não é sigla fiscal conhecida
   (`_SIGLAS_PERMITIDAS`, ex.: SPED/ICMS/CNPJ) vira `<NOME>` — cobre
   tanto o nome da empresa quanto qualquer outro nome próprio que
   apareça em letra maiúscula (padrão comum em caixa de sistema
   corporativo). Só depois disso o texto é comparado/guardado/enviado.
4. Procura o texto anonimizado (comparado sem acento/maiúscula) em
   dois catálogos, nessa ordem: `ERROS_CONHECIDOS` (fixo, versionado,
   decisão de gente — hoje tem os três erros já vistos contra dado
   real: "caminho especificado não é válido" seção 0.25, "outros dados
   não digitados" e "saldo dos impostos não foram calculados", os dois
   últimos com a ação decidida pelo usuário nesta sessão) e
   `data/erros_aprendidos.json` (local, nunca sobe pro GitHub — toda
   decisão que a IA já tomou antes vira regra sem precisar consultar
   de novo).
5. Só se for um erro **nunca visto em nenhum dos dois catálogos**,
   chama `ia.classificar_erro()` (Claude Haiku, `output_config.format`
   com JSON Schema fechado — a resposta só pode ser uma das 4 ações
   mais confiança mais motivo, nunca texto livre). Confiança "baixa"
   nunca vira regra nova e sempre cai em `PULAR` (comportamento seguro
   de antes) — só confiança "alta" é gravada em
   `data/erros_aprendidos.json`.
6. Sem chave de API configurada (`data/chave_api.txt` — opção 6 do
   menu, ou variável `ANTHROPIC_API_KEY`) ou sem internet, cai
   automaticamente em `PULAR` sem travar o motor — a IA é reforço
   opcional, nunca dependência.

**As 4 ações possíveis** (`erros.ACOES`, sempre reversíveis — nenhuma
altera lançamento nem transmite, mesma regra da seção 5.7):

- `PULAR` — fecha a caixa e a tela de geração, marca falha naquele
  documento, segue pra próxima empresa (comportamento de sempre).
- `TENTAR_DE_NOVO` — fecha e tenta gerar o mesmo documento mais uma
  vez (só uma vez — `gerar_sped()` usa o prefixo `..._retry_` pra não
  entrar num loop).
- `CONTINUAR` — só fecha a caixa (aviso informativo) e volta a esperar
  a confirmação de sucesso de verdade, sem reabrir nada.
- `PARAR_LOTE` — fecha tudo e para o **lote inteiro**
  (`LoteInterrompido`, nova exceção que `executar_lote()` captura) —
  pra erro que vai se repetir em toda empresa (sessão expirada,
  licença, sistema fora do ar).

**Botão errado por padrão, achado real:** a caixa "Outros dados não
digitados! Deseja copiar do último mês digitado?" (print
`52_CONTRIBUICOES_erro_dominio.png`) tem Sim/Não, com **"Yes" em
foco** — usar o mesmo truque de Enter dos diálogos de um botão só
apertaria o botão errado. `erros.BOTAO_NAO_PADRAO` guarda, por texto
conhecido da caixa, qual botão clicar por OCR em vez de usar Enter
(`dominio._fechar_caixa_erro()`).

**Decisão do usuário pros dois avisos já vistos** (não são erro do
motor, são decisão de negócio): "Outros dados não digitados" → nunca
copiar do mês anterior sozinho, responder "Não" e pular a empresa pra
revisão manual. "Saldo dos impostos não foram calculados" → apertar OK
mas não considerar a geração válida sem a apuração feita, pular a
empresa também. As duas já estão em `ERROS_CONHECIDOS` — não dependem
da IA.

**Resumo do lote** agora lista, no final, toda decisão tomada em caixa
de erro/aviso durante aquela rodada (`erros.decisoes_da_sessao`) — pra
quem está acompanhando ver de relance sem abrir print nenhum.

**Ainda não testado de ponta a ponta contra o Domínio real** — os dois
títulos de caixa (`TITULOS_ERRO`) e a anonimização foram validados por
teste unitário de lógica pura (sem OCR/tela real, mesma limitação da
seção "ambiente de desenvolvimento" no topo deste documento); falta
confirmar contra uma caixa de verdade que: (a) o recorte
`recortar_ao_redor()` captura o texto inteiro da caixa "Aviso Empresa"
sem cortar; (b) clicar em "No" por OCR funciona na caixa Sim/Não real;
(c) a chamada à IA de verdade, com chave configurada, classifica um
erro nunca visto de forma sensata.

**Nota de consolidação (23/09/2026):** esta seção e o código que ela
descreve foram desenvolvidos numa sessão à parte, contra uma cópia
deste repositório publicada em `anthonymaiaxl-oss/Automa-o-Dominio`
(pedido do usuário, pra revisão), e trazidos de volta pra cá — que
continua sendo o repositório único e a `main` o fluxo de commit direto
de sempre (seção "ambiente de desenvolvimento" no topo, sem PR).
Revisão de segurança/LGPD feita antes de trazer o código pra cá:
confirmado que só texto anonimizado sai da máquina, nunca imagem, e
que `data/chave_api.txt`/`data/erros_aprendidos.json`/
`data/ia_envios.log` continuam fora do Git (`.gitignore`).

### 0.33 Interface gráfica (Tkinter) — segundo "jeito fácil", junto do menu de texto

Pedido do usuário: além de facilitar adicionar novos "caminhos"
(automações novas — cada documento gerado, tipo SPED Fiscal e EFD
Contribuições, é um "caminho" dentro do Domínio, e a ideia é ter mais
no futuro), criar um visual mais simples pra rodar o motor, fora do
CMD. Começando por Tkinter — já vem com o Python, roda offline, sem
instalar nada novo.

`scripts/gui.py` (novo): mesmas 6 ações do menu de texto
(`scripts/app.py`), em botão em vez de número — rodar em lote
(exemplo/real), trocar empresa, gerar SPED Fiscal/EFD Contribuições
numa empresa só, configurar a chave da IA. Uma caixa de texto na
própria janela mostra em tempo real o que antes só aparecia no
terminal (todo o debug de OCR).

**Como ficou por baixo:**

- A automação em si (`app/dominio.py`) roda numa thread separada, não
  na thread da janela — senão a janela travaria (sem responder, sem
  redesenhar) pelos até ~3 minutos que uma geração pode levar (seção
  0.27). `sys.stdout` é trocado, só durante essa thread, por um objeto
  que põe cada linha numa fila em vez de imprimir de verdade — assim
  todo `print()` que já existia em `app/dominio.py` aparece na caixa de
  texto sem precisar reescrever um por um. A janela principal lê essa
  fila a cada 100ms (`root.after()`) e escreve na caixa.
- **Achado antes mesmo do primeiro teste real** (revisão do próprio
  código, não log): o Tkinter só permite criar/mostrar caixa de
  diálogo na thread principal da interface — nunca de dentro de outra
  thread. `executar_lote()` pergunta a confirmação por uma função
  (`confirmar(selecionadas) -> bool`) que a `gui.py` passa — o
  primeiro jeito escrito chamava `messagebox.askyesno()` direto de
  dentro dessa função, que roda na thread de trabalho: um bug real,
  ainda que nunca testado ao vivo (thread errada mostrando diálogo do
  Tkinter). Corrigido antes de commitar: a função da thread de trabalho
  só agenda a pergunta de verdade na thread principal
  (`root.after(0, ...)`) e espera a resposta voltar por uma fila
  (`queue.Queue`) — a thread de trabalho fica bloqueada esperando, mas
  isso não trava a janela (a thread principal continua livre pra
  mostrar a caixa e processar a resposta).
- `app/dominio.py::executar_lote()` ganhou dois parâmetros opcionais,
  `regime` e `confirmar` — sem informar os dois (uso por
  `scripts/app.py`/`scripts/executar_lote.py`, CLI), pergunta os dois
  por `input()` como sempre; a interface gráfica informa os dois,
  pulando o terminal. Não muda nenhum comportamento do jeito CLI.
- `Abrir Interface Gráfica.bat` (novo, raiz do repositório) — atalho
  de duplo clique pra `scripts/gui.py`, ao lado (não no lugar) de
  `Abrir Motor SPED.bat` (menu de texto) — os dois continuam
  funcionando, a interface gráfica é opção nova, não substituição,
  até ser validada de verdade.

**Ainda não testado de ponta a ponta contra o Domínio real** — nem
`tkinter` está disponível neste ambiente de desenvolvimento (sandbox
Linux, sem interface gráfica) pra rodar/inspecionar a janela, só validado
por leitura de código e `python3 -m py_compile`. Primeiro teste real
decide se o design de thread/fila descrito acima realmente funciona
sem travar a janela.

### 0.34 Pausar/continuar o lote, e recuperação genérica (Esc) com 1 repetição antes de pular a empresa

Três pedidos do usuário, relacionados — sustentabilidade do lote longo
sem precisar reiniciar tudo:

1. **Pausar/continuar** o lote em execução, pela interface gráfica.
   `dominio.executar_lote()` ganhou um parâmetro `pausa` opcional (um
   `threading.Event`) — checado só **entre uma empresa e outra**
   (`_esperar_se_pausado()`), nunca no meio de uma ação: pausar durante
   um clique deixaria o Domínio num estado que ninguém garante. Sem
   informar (`pausa=None`, uso por terminal), nunca pausa — igual
   sempre. `scripts/gui.py` tem um botão "Pausar"/"Continuar" que só
   habilita nas ações em lote (não faz sentido pausar uma ação de
   empresa só, já rápida).
2. **Recuperação genérica com Esc** quando o motor não sabe mais o que
   está na tela. `interacao.pressionar_esc_repetidas()` (nova) aperta
   Esc várias vezes seguidas — ao contrário de Enter (confirma o botão
   padrão, arriscado num diálogo desconhecido, seção 0.13) ou de um
   clique (precisa saber onde), Esc só cancela/fecha uma camada de
   diálogo por vez, nunca confirma nem gera nada. Repetir desempilha
   diálogo dentro de diálogo até sobrar a tela principal, sem precisar
   saber quantas camadas tinha.
3. **Reiniciar o processo da empresa 1 vez antes de pular pra
   próxima.** `executar_lote()` teve o corpo do loop por empresa
   extraído pra `_processar_empresa()` (troca de empresa + gera cada
   documento necessário). O loop principal agora envolve essa chamada
   num `try/except`: uma exceção de verdade (não uma falha limpa de
   documento, já tratada por dentro) aciona `pressionar_esc_repetidas()`
   e repete a mesma empresa mais 1 vez; se der errado de novo, registra
   a falha e segue pra próxima — nunca trava o lote inteiro por causa
   de um erro não previsto. `LoteInterrompido` (seção 0.32)
   continua sendo tratado à parte, nunca repetido — é decisão
   explícita de parar tudo, repetir não faz sentido pra esse caso.

**Ainda não testado de ponta a ponta contra o Domínio real** — mesma
limitação de sempre deste ambiente (sem `pyautogui`/tela real aqui).

### 0.35 Gravador de clique — rascunho automático de automação nova (`scripts/gravar.py`)

Pedido do usuário: adicionar automação nova ("caminho") pro Domínio
sempre envolveu o mesmo trabalho manual — explorar a tela, escrever
`achar_ou_parar()`/`clicar()` passo a passo, ajustar depois de ver
falhar contra a tela real (foi assim pra SPED Fiscal e EFD
Contribuições). A ideia: gravar um humano fazendo a tarefa uma vez, e
já sair um rascunho de função parecido com o resto do código.

**`scripts/gravar.py` (novo):** usa `pynput` (biblioteca nova,
`requirements.txt`) — a única peça do projeto que **escuta** entrada
real (mouse/teclado) em vez de só enviar entrada sintética
(`pyautogui`). Fluxo:

1. Roda o script → grava toda vez que você clica em algo (posição +
   print de tela cheia + recorte ao redor do clique, salvos em
   `capturas/gravacao_<data-hora>/`) e tenta adivinhar o texto perto do
   clique por OCR (`tela.ler_texto()`, reaproveitada da seção 0.32).
2. F12 termina a gravação.
3. Gera `passos.json` (dado bruto de cada clique) e `rascunho.py` (uma
   função Python pronta pra revisar, um bloco `achar_ou_parar()` +
   `clicar()` por passo gravado, no mesmo estilo de `gerar_sped()`).

**Deliberadamente limitado, por design, não por falta de tempo:**

- **Gera rascunho, não automação pronta.** O texto adivinhado por OCR
  carrega o mesmo risco de sempre (texto curto ilegível, tela densa
  confundindo — seções 0.10/0.29): pode sair errado, incompleto ou
  vazio. O rascunho existe pra revisar contra o print de cada passo,
  não pra colar e rodar direto — mesmo trabalho de ajuste fino que
  toda automação deste projeto precisou, só que já parte de um
  esqueleto pronto em vez do zero.
- **Só grava clique, não digitação.** Um passo que precisa digitar
  algo (ex.: código de empresa) não sai pronto no rascunho — fica
  marcado pra preencher à mão, mesmo padrão de `trocar_empresa()`
  (digita valor vindo de dado, não gravado).
- **Nunca roda ao mesmo tempo que o resto do motor.** É um script à
  parte, escuta em vez de agir — não faz sentido (e seria arriscado)
  gravar clique enquanto `pyautogui` está enviando clique sintético em
  paralelo.

**Ainda não testado de ponta a ponta contra o Domínio real** — nem
`pynput` está instalado neste ambiente de desenvolvimento (sandbox
Linux) pra testar a escuta de verdade, só validado por leitura de
código e `python3 -m py_compile`. Primeiro uso real decide se o texto
adivinhado por OCR nesse recorte pequeno (o mesmo raio de
`recortar_ao_redor()`, nunca calibrado especificamente pra este caso)
é bom o bastante pra ser útil, ou se precisa de ajuste.

### 0.36 Primeiro teste real do gravador: palpite pegava a linha errada, não a coisa clicada

Primeiro uso real de `scripts/gravar.py` — 13 passos gravados. A
maioria dos palpites saiu inútil: título da janela inteiro ("Domínio
Escrita Fiscal - Versão..."), cabeçalho de coluna de grid inteiro
("Observações | Certificado Digital..."), lixo de OCR ("JD", "[)",
">>>"), um vazio.

**Causa:** o palpite usava `tela.ler_texto()` — lê **todo** o texto de
uma área e devolve só a **primeira linha**. Numa área com várias
colunas/rótulos (ex.: cabeçalho de grid de empresa, barra de título +
menu), a primeira linha lida quase nunca é a coisa que ficou embaixo
do cursor — é só o que top-a-baixo aparece primeiro na imagem,
independente de onde foi o clique.

**Correção:** `tela.texto_mais_proximo(imagem, x, y)` (nova) — usa
`pytesseract.image_to_data()` (posição de cada palavra, não só o
texto) pra achar a palavra **cujo centro fica mais perto do ponto
clicado**, e reconstrói a linha inteira dela (`line_num`/`block_num`
do próprio Tesseract) — assim um rótulo de mais de uma palavra (ex.:
"SPED Fiscal") sai inteiro, mas nunca mistura com uma coluna vizinha.
`scripts/gravar.py` trocou `ler_texto()` por essa função.

**Achado à parte, sobre uso, não sobre código:** o passo 1 adivinhou
"260923. 150803" — um relógio/data-hora, não um botão. O clique nº1 da
gravação provavelmente foi só pra focar a janela do Domínio antes de
começar de verdade, não um passo do caminho — ao revisar o rascunho,
descartar passo assim (aponta pra um relógio, muda a cada segundo,
nunca vai bater de novo) é esperado, não é bug.

**Ainda não testado de novo contra o Domínio real** — a correção
responde ao que o teste mostrou, mas só o próximo uso confirma se
melhorou.

### 0.37 Janela do próprio script minimizada antes de mexer no Domínio; gravador também na interface gráfica

Dois pedidos do usuário, direto:

1. **Minimizar a própria janela antes de focar o Domínio.**
   `interacao.focar_dominio()` agora chama
   `_minimizar_console_proprio()` primeiro — acha a janela do console
   rodando o script (`ctypes.windll.kernel32.GetConsoleWindow()`) e
   minimiza (`ShowWindow(..., SW_MINIMIZE)`), se existir (não faz nada
   rodando sem console, ex. `pythonw`). Como toda ação de alto nível já
   chama `focar_dominio()` primeiro (seção 0.28), isso cobre `trocar_
   empresa()`/`gerar_sped()`/etc. de uma vez só, sem precisar mexer em
   cada script individual. Reduz o mesmo risco da seção 0.28 (a própria
   janela do script roubando o foco/clique) — agora prevenido antes de
   precisar do foco, não só corrigido depois de perder.

   Na interface gráfica (Tkinter, seção 0.33), a janela principal não é
   um console — `_rodar_em_thread()` chama `self.root.iconify()` antes
   de começar qualquer ação que mexe no Domínio, e `self.root.
   deiconify()` sozinho quando termina (`_fim_execucao()`).
2. **Gravador de clique (seção 0.35/0.36) também vira botão na
   interface gráfica**, não só script à parte — `scripts/gui.py`
   importa `Gravador` de `scripts/gravar.py` direto (mesma pasta, sem
   precisar duplicar a lógica). Pergunta o nome da função por caixa de
   diálogo, confirma que a pessoa está pronta pra gravar, e roda o
   mesmo fluxo (grava até F12, gera rascunho) numa thread separada,
   igual as outras ações.

**Ainda não testado de ponta a ponta contra o Domínio real.**

### 0.38 Segundo teste real do gravador: nome de função com espaço quebrava, e menu ainda grudava item vizinho

Segundo uso real (9 passos). Dois problemas, um de código (bug meu) e
um de ajuste fino do palpite.

**Nome de função inválido.** O usuário digitou "Teste 3 pela
interface" quando perguntado o nome da função — texto livre, não um
identificador Python. O rascunho saiu `def Teste 3 pela
interface(prefixo=""):`, erro de sintaxe, nem colava. Eu nunca validei
esse texto antes de jogar direto no código gerado.

**Correção:** `nome_de_funcao_valido()` (nova, `scripts/gravar.py`) —
troca tudo que não é letra/número/underscore por `_`, garante que não
fica vazio nem começa com número. Aplicada dentro de
`gerar_rascunho()` (não em cada lugar que chama) — cobre tanto
`scripts/gravar.py::main()` (CLI) quanto `scripts/gui.py::acao_gravar()`
(interface gráfica) de uma vez, sem duplicar a validação nos dois
lugares. Testada isoladamente (só a lógica de regex, sem precisar de
OCR/tela): `"Teste 3 pela interface"` → `"teste_3_pela_interface"`,
identificador válido.

**Palpite ainda grudava item de menu vizinho.** Mesmo com a correção
da seção 0.36 (palavra mais próxima do clique, não a primeira linha da
área toda), reconstruir a **linha inteira** do Tesseract ainda juntava
demais numa barra de menu — "Arquivos", "Movimentos" e "Relatórios"
saíram como um `texto_adivinhado` só, quando o clique era só num
deles. A barra de menu inteira é uma única "linha" pro Tesseract
(todos os itens na mesma altura), então "linha inteira" nunca ia
isolar um item só ali.

**Correção:** `tela.texto_mais_proximo()` não pega mais a linha
inteira — expande a partir da palavra mais próxima, palavra por
palavra, só enquanto o espaço até a próxima for menor que 1,5x a
altura do texto (heurística: espaço entre palavra do mesmo rótulo é
bem menor que o espaço entre item e item de menu). Testada isolada com
dado de Tesseract simulado (sem OCR real): barra de menu com 3 itens
espaçados 30px isola só o item clicado; duas palavras de um rótulo só
("SPED"/"Fiscal") com 8px de espaço continuam juntas.

**Ainda não testado de novo contra o Domínio real** — as duas
correções respondem ao que os dois testes mostraram; a heurística de
1,5x altura nunca foi calibrada contra medida real de espaçamento do
Domínio, só validada com dado inventado nesse formato. Terceiro uso
real decide se precisa ajustar o multiplicador.

### 0.39 Terceiro teste real do gravador: as duas correções funcionaram; achado novo — hover não é gravado, só clique

Terceiro uso real (4 passos, caminho Relatórios → SPED Fiscal →
Fechar). **As duas correções da seção 0.38 se confirmaram:**

- Nome de função saiu válido: `teste_6_pela_interface` (era "teste 6
  pela interface" digitado, com espaço).
- Palpites saíram limpos e certos: "Relatórios", "SPED Fiscal",
  "Fechar" — batem exatamente com os textos que `gerar_sped()` já usa
  de verdade, sem nenhum item de menu vizinho grudado.

**Achado novo, esperado por design:** o rascunho pulou direto de
"Relatórios" pra "SPED Fiscal" — faltam os passos por "Informativos" e
"Federais", que na automação de verdade são **hover** (passar o mouse,
`interacao.passar_mouse()`), não clique, pra abrir o submenu em
cascata (seção 0.6). `scripts/gravar.py` só escuta clique
(`mouse.Listener(on_click=...)`) — nunca teve como gravar hover, isso
já estava documentado como limitação ("só grava clique, não
digitação"), mas esse teste mostra que a limitação também vale pra
**navegação em cascata**, não só pra digitação de dado. Pra caminho
com mais de um nível de submenu (a maioria dos itens do menu Federais,
seção 0.9), o rascunho vai sempre faltar os passos intermediários de
hover — precisam ser inseridos à mão (`interacao.passar_mouse(x, y)`
entre o clique no item pai e o clique no item final).

**Observação à parte, não é bug:** os passos 1 e 2 saíram idênticos
(mesma posição, mesmo "Relatórios") — parece um clique duplicado (dois
cliques físicos no mesmo lugar, não um erro de gravação); não atrapalha
o resultado, só gera uma linha redundante fácil de apagar na revisão.

**Ainda em aberto, não decidido:** gravar hover também (não só
clique) resolveria essa lacuna, mas exige uma lógica bem diferente —
hover não tem um "evento" único como clique, precisa de heurística
(ex.: mouse parado numa posição nova por algum tempo, sem clicar,
conta como hover proposital) — maior escopo que as correções desta
seção, ainda não pedido explicitamente pelo usuário.

**Quarto teste, confirma numa amostra maior:** 10 cliques em lugares
aleatórios da tela (não um caminho coerente, propositalmente — teste
de variedade). 8 de 10 palpites saíram limpos e plausíveis, incluindo
dois rótulos de duas palavras corretos sem grudar nada a mais
("Rotinas Automáticas", "DARF Normal") — a expansão por espaço da
seção 0.38 funciona também pra rótulo de duas palavras, não só isola
palavra única. Os 2 vazios (área sem texto) são esperados, não erro.
Zero lixo de OCR dessa vez — melhor amostra até agora, mais variada
que os três testes anteriores (que seguiam um caminho de menu
conhecido).

### 0.40 EFD Contribuições confirmada rodando de ponta a ponta pelo próprio código

Primeiro teste real de `gerar_efd_contribuicoes()`
(`scripts/explorar_contribuicoes.py`) contra o Domínio, depois de só
ter o layout confirmado por inspeção visual (seção 0.21). Rotina
completa, sem intervenção manual: Relatórios → hover Informativos →
hover Federais → clique em "Contribui" (palpite de OCR pro item "EFD
Contribuições", mesmo espírito de correspondência por substring de
sempre) → competência anterior preenchida e confirmada nos dois campos
→ posição de "OK" calculada a partir de "Fechar" (mesma técnica da
seção 0.31) → clique em OK → confirmação → Fechar.

**A busca literal por "sucesso" não achou nada em 5 tentativas** —
tela real (não a de teste) densa o bastante pra atrapalhar o OCR mesmo
pro texto de confirmação, mesma limitação já vista nas seções
0.10/0.29. **O motor não travou por isso:** o fallback de diálogo-de-
um-só-botão (`Confirmando com Enter`, seção 0.28) achou a âncora e
fechou a confirmação mesmo sem o texto bater, e o "Fechar" da tela de
geração funcionou de primeira. Rotina terminou limpa: "Contribui
fechado. Fim da rotina."

**Conclusão:** EFD Contribuições está agora no mesmo nível de
validação que o SPED Fiscal/ICMS — pode ser usada de verdade em lote
(`tipo`/`sped` em `empresas.csv`, seção 0.20). Docstrings e README que
diziam "ainda não confirmado" foram atualizados.

### 0.41 Instalação enxuta pra outro computador ("modo operador") e nome da interface em português

Pedido do usuário: amanhã instala isso num computador novo, de outro
operador do escritório — e esse computador ainda não deve ter a
gravação de automação nova (`scripts/gravar.py`, seção 0.35, só
testada nesta máquina até agora) nem as ações de empresa única (trocar
empresa/gerar um documento só) — só "Rodar em lote" contra empresas
reais.

**Decisão de design:** uma única variável de ambiente
(`DOMINIO_MODO`), lida por `scripts/gui.py`, em vez de um
repositório/branch separado — mesmo código, mesmo `git pull`/
`Atualizar.bat` pros dois computadores, só a tela muda.
`DOMINIO_MODO=operador` esconde as seções "Empresa já selecionada" e
"Criar automação nova"; sem a variável (comportamento de sempre),
continua tudo visível. `Abrir Interface Gráfica (Operador).bat` (novo)
só seta a variável antes de chamar `scripts\gui.py`.

**`Instalar.bat` (novo):** confere se Python e Tesseract estão no PATH
(avisa e para se faltar Python; avisa e segue se faltar Tesseract, já
que sem ele a automação simplesmente não lê a tela) e instala as
dependências Python (`pip install -r requirements.txt`) — sem `venv`,
de propósito: os atalhos existentes (`Atualizar.bat`, `Abrir Motor
SPED.bat` etc.) já chamam `python`/`pip` direto, sem ativar ambiente
nenhum; criar um `venv` no instalador e não usá-lo no resto dos
atalhos só quebraria tudo. Texto do `echo` sem acento de propósito
(mesmo padrão já usado em `Atualizar.bat`) — acento em `echo` de `.bat`
pode sair ilegível dependendo da code page do `cmd.exe`; nome de
arquivo com acento (`Abrir Interface Gráfica (Operador).bat`) não tem
esse problema, só o texto que o `cmd.exe` desenha é que arrisca.

**Nome da interface trocado pra português** (pedido do usuário):
"Domínio Automation Engine" tinha "Automation Engine" em inglês, tanto
no título da janela quanto no cabeçalho da interface gráfica e no
banner do menu de texto — virou **"Automação Fiscal Domínio"** nos três
lugares (`scripts/gui.py`, `scripts/app.py`). Nome de arquivo,
repositório e títulos de documento não mudaram — o pedido foi
especificamente sobre o que aparece na interface rodando, não sobre
esses.

**Ainda não testado num computador novo de verdade** — nem o modo
operador nem `Instalar.bat` foram validados contra uma instalação real
do zero (mesma limitação de sempre: este ambiente não roda
Tkinter/pyautogui, muito menos instala Python/Tesseract de verdade).
Primeiro uso real no computador novo decide se precisa ajustar.

### 0.42 Modo operador: esconde também o botão "Empresas de EXEMPLO"

Correção da seção 0.41: o modo operador só escondia "Empresa já
selecionada" e "Criar automação nova" — a seção "Rodar em lote"
continuava mostrando os dois botões (EXEMPLO e REAIS). Pedido do
usuário: o operador só vai lidar com empresa real, o botão de exemplo
não faz sentido pra ele. `secao_lote` em `scripts/gui.py` agora só
mostra "Empresas de EXEMPLO" quando `self.modo != "operador"` —
"Empresas REAIS" continua sempre visível, nos dois modos.

### 0.43 Modo operador: "Empresa já selecionada" volta a aparecer — só o gravador fica bloqueado

Correção das seções 0.41/0.42: o modo operador escondia também
"Empresa já selecionada no Domínio" (trocar empresa/gerar um documento
só). Pedido do usuário, ao ver a interface completa numa captura de
tela: essa seção pode continuar disponível pro operador — só "Criar
automação nova" (o gravador, ainda em teste, seção 0.35) fica
bloqueado por enquanto. `secao_empresa` em `scripts/gui.py` não
depende mais de `self.modo`; só `secao_gravar` continua condicionada a
`self.modo != "operador"`.

### 0.44 Modo operador: só "Gerar SPED Fiscal" na seção de empresa única

Correção da seção 0.43: pedido do usuário, "quero rodar SPED apenas"
— na seção "Empresa já selecionada", o operador só precisa de "Gerar
SPED Fiscal"; "Trocar só a empresa" e "Gerar EFD Contribuições" saem
do modo operador (continuam normais no modo completo, sem mudança
pra esta máquina). O lote ("Rodar em lote → Empresas REAIS") não
muda — já é controlado pela coluna `tipo`/`sped` de cada empresa no
CSV (seção 0.20), não por botão da interface; se esse operador só
atende empresa ICMS, basta não preencher `sped=CONTRIBUICOES` nem
`tipo=2` na planilha dele.

### 0.45 Modo operador: volta a ter os 3 botões de empresa única; botão de lote renomeado pra "Rodar SPED"

Correção da seção 0.44, ao ver a interface renderizada de verdade: a
seção "Empresa já selecionada no Domínio" volta a ter os 3 botões
("Trocar só a empresa", "Gerar SPED Fiscal", "Gerar EFD
Contribuições") também no modo operador — só "Criar automação nova"
(gravador) continua bloqueada. E o botão "Empresas REAIS" (lote)
aparece como **"Rodar SPED"** só no modo operador — mesma ação por
baixo (`executar_lote(usar_real=True, ...)`), rótulo mais direto pro
uso esperado desse computador. No modo completo, o rótulo continua
"Empresas REAIS" (lá o lote processa `tipo`/`sped` misto, seção 0.20 —
"Rodar SPED" seria impreciso nesse modo).

### 0.46 OCR em texto curto/tela densa precisa recortar antes de dar zoom — vale pra toda automação nova

`scripts/testar_gravado.py` (script temporário, seção 0.39) chamava
`achar_ou_parar(imagem, "Fechar", ...)` direto na tela inteira, escala
padrão (2x) — copiei o palpite do gravador sem revisar contra o padrão
já validado do resto do projeto. Teste real: tela de SPED Fiscal
aberta numa empresa de verdade, `"Não achei 'Fechar'."` — o texto
realmente não estava na lista de palavras lidas pelo OCR (tela densa,
cheia de opção/checkbox, mesma classe de problema das seções
0.10/0.29).

**Corrigido reaproveitando `_fechar_tela_geracao()`** (já usada por
`gerar_sped()`) em vez de reimplementar a busca: ela recorta a área do
diálogo a partir do título antes de procurar "Fechar", com zoom maior
(escala 4) só dentro desse recorte, 3 tentativas, e cai pro clique na
posição já conhecida quando aplicável (seções 0.30/0.31). Zoom sem
recorte antes não resolve do mesmo jeito — texto pequeno continua
pequeno em relação ao resto da tela, só fica maior em pixel absoluto.

**Regra pra daqui pra frente, pedida pelo usuário:** toda automação ou
caminho novo criado neste projeto — escrito à mão ou promovido de um
rascunho do gravador — que precisar achar texto curto ou numa tela
densa (ex.: "OK", "Fechar", "Sim", "Não") deve recortar a área primeiro
(por título conhecido, por região de menu, ou pelo fallback central de
`achar_texto_ou_no_centro()`) e só depois aumentar o zoom dentro do
recorte — nunca `achar_ou_parar()`/`achar_texto()` direto na tela
inteira pra um alvo desse tipo. `scripts/gravar.py::gerar_rascunho()`
agora imprime esse lembrete no rascunho gerado, pra não se perder de
novo na próxima automação nova.

### 0.47 Pipeline gravador → revisão → preenchimento manual → execução validado de ponta a ponta

Segundo teste de `scripts/testar_gravado.py` (depois da correção da
seção 0.46): rodou limpo, sem parar em nenhum passo — "Clicando em
Fechar: (948, 265)" → "SPED Fiscal fechado." → "Fim do teste — o
caminho gravado funcionou."

Isso fecha a validação de ponta a ponta do pipeline inteiro: gravar
clique (seção 0.35) → revisar o rascunho contra os prints → completar
à mão os passos que o gravador não capta (hover, seção 0.39; texto
curto/tela densa, seção 0.46) → rodar contra o Domínio real. Cada
etapa já tinha sido validada isoladamente; este foi o primeiro teste
do caminho completo, do clique gravado até a execução automatizada de
verdade.

**O que continua sendo limitação permanente da ferramenta, não bug:**
o gravador nunca vai gravar hover nem digitação sozinho (seção 0.39) —
completar isso à mão faz parte do fluxo esperado, documentado no
próprio rascunho gerado. `scripts/testar_gravado.py` cumpriu seu
propósito (validar o pipeline) e foi removido — a lógica que importa
(hover manual + `_fechar_tela_geracao()`) já está descrita aqui e no
próprio `gerar_sped()`, não precisa de um arquivo à parte.

### 0.48 Automação promovida vira opção de menu sozinha (`AUTOMACOES_EXTRAS`)

Pedido do usuário: depois de gravar, testar e corrigir um caminho novo
(seções 0.35-0.47), ele devia virar uma opção de menu de verdade — no
menu de texto (`scripts/app.py`) e na interface gráfica
(`scripts/gui.py`) — sem editar os dois toda vez.

**Mecanismo:** uma lista nova em `app/dominio.py`,
`AUTOMACOES_EXTRAS = [("Nome no menu", funcao), ...]`. Os dois pontos
de entrada leem essa lista e criam uma opção/botão a mais por item, na
ordem dela — não precisam saber quantas ou quais automações existem,
só iteram. `scripts/app.py` numera a partir de 7; `scripts/gui.py`
acrescenta um botão a mais em "Empresa já selecionada", depois dos 3
fixos.

**Fluxo completo pra promover uma automação nova, do clique até o
menu, documentado no README ("Criar e promover uma automação nova"):**
gravar → revisar/completar à mão (hover, texto curto/tela densa) →
testar de verdade → colar a função em `app/dominio.py` (mesmo padrão
de `gerar_sped_fiscal()`) → uma linha em `AUTOMACOES_EXTRAS` → commit +
push. `Atualizar.bat` leva pra toda máquina, nos dois modos da
interface (completo e operador) — sem distinção entre os dois por
enquanto; se um dia precisar esconder uma automação extra só do
operador, dá pra guardar o modo junto na lista depois, quando isso for
pedido de verdade.

**Fora do escopo desta mudança, de propósito:** não entra no lote
(`_GERADORES`/`tipo`/`sped`, seção 0.20) — esse sistema é específico
dos dois documentos SPED já conhecidos, ligado à planilha de empresas.
Automação extra roda uma empresa de cada vez, igual "Gerar SPED
Fiscal"; rodar em lote também é extensão separada, se algum dia fizer
sentido.

**Ainda não tem nenhuma automação extra cadastrada** —
`AUTOMACOES_EXTRAS` começa vazia; a primeira entrada real testa o
mecanismo de ponta a ponta.

### 0.49 IA cresce em dois pontos novos, sempre só em texto: resumo do lote e palpite de falha de OCR

Pedido do usuário: usar mais IA pra deixar o motor "mais inteligente e
útil". Duas frentes escolhidas por ficarem dentro da regra da seção
5.5 (classificação/texto → nunca ação autônoma), sem trocar a
segurança já validada por incerteza:

1. **`ia.resumir_lote()`** — no final de `executar_lote()`, se tiver
   chave configurada, pede um parágrafo em português simples
   resumindo o lote (quantas empresas, sucesso/falha, padrão de
   falha), a partir só de código de empresa + status por documento
   (nunca apelido). Complementa o resumo técnico já impresso, não
   substitui.
2. **`ia.diagnosticar_busca_falha()`**, chamada de dentro de
   `achar_ou_parar()` (`_sugerir_diagnostico()`) sempre que uma busca
   de texto falha — pega o texto que o OCR realmente leu na tela
   (`tela.ler_texto()`, anonimizado por `erros.anonimizar()` antes de
   sair da máquina, mesmo cuidado do resto deste módulo), manda pra IA
   junto com o texto-alvo não encontrado, e imprime a hipótese que
   vier. Por estar dentro do mesmo `achar_ou_parar()` que toda
   automação já usa (seção 0.46), qualquer automação nova ganha isso
   de graça, sem chamar nada extra.

Os dois são **só texto pro humano ler** — nunca decidem ação, nunca
tocam em código, nunca clicam em nada sozinhos. Sem chave configurada,
os dois viram `None` e o motor segue exatamente como antes (mesma
degradação graciosa de `classificar_erro()`).

**O que ficou de fora, de propósito, até confirmar com o usuário:** o
pedido original descrevia algo mais ambicioso — "identifica, testa, e
vê se daria certo, se der valida, senão vai arrumar até o processo
ficar redondo". Isso poderia significar um loop automático (IA sugere
correção → aplica no código → roda de novo contra o Domínio real →
repete sozinha até funcionar ou desistir). Essa parte não foi
construída: seria a IA tendo autonomia sobre a ação (clicar, repetidas
vezes, sem ninguém olhando cada tentativa) — exatamente o que a seção
5.5 existe pra evitar, ainda mais rodando contra sistema fiscal real.
O que existe hoje automatiza só o "identifica" (diagnóstico); "testa
de novo" e "arruma" continuam com uma pessoa no meio, do jeito que a
sessão inteira já vinha funcionando (gravar → revisar → rodar → colar
log → ajustar). Se o usuário confirmar que quer o loop automático
mesmo com esse risco, é uma extensão separada, com limite de
tentativas e log de cada uma.

### 0.50 Palpite de falha de OCR validado ao vivo — confirma anonimização também

Primeiro teste real de `diagnosticar_busca_falha()` (seção 0.49):
forçado por busca de texto inexistente (`achar_ou_parar()` com um alvo
fictício), contra o Domínio real, numa tela com nome de empresa de
verdade visível ("UNISEEDS FERTILIZANT"). Resultado:

- `achar_ou_parar()` falhou como esperado (`Não achei
  'PALAVRAQUENUNCAAPARECENATELA'.`) — zero clique, nenhuma mudança no
  Domínio.
- IA respondeu com hipótese coerente e a sugestão certa (recortar a
  área e dar zoom antes de buscar na tela inteira, mesmo padrão da
  seção 0.46) — um parágrafo curto em português, sem sugerir ação
  nenhuma.
- **Anonimização confirmada funcionando**: o nome real da empresa
  visível na tela ("UNISEEDS FERTILIZANT") não apareceu na resposta da
  IA — `erros.anonimizar()` trocou por `<NOME>` antes do texto sair da
  máquina, como projetado.

`resumir_lote()` (a outra metade da seção 0.49) ainda não foi testado
ao vivo — falta rodar "Empresas de EXEMPLO" em lote pra ver o parágrafo
de resumo aparecer no fim.

### 0.51 IA escolhe estratégia de nova tentativa antes de desistir — nunca escreve/executa código novo

Pedido do usuário: usar o palpite de falha de OCR (seção 0.49)
"diretamente na correção", testando de novo e repetindo o necessário.
Construído, mas com um limite deliberado, pra não cruzar a regra da
seção 5.5 (nunca IA com autonomia sobre a ação):

**O que a IA pode fazer agora:** dentro de `achar_ou_parar()`, quando
uma busca de texto falha, a IA ESCOLHE (formato fechado, igual
`erros.ACOES`) entre 4 técnicas já validadas neste projeto:
`ZOOM_MAIOR` (mais zoom no OCR), `RECORTE_CENTRAL` (só a região
central, seção 0.29), `NOVA_TELA` (print novo, seção 0.28) ou
`DESISTIR`. `achar_ou_parar()` aplica a escolhida e tenta de novo, até
2 vezes, antes de desistir de vez e cair no diagnóstico da seção 0.49.

**O que a IA nunca faz, por design:** escrever ou executar código
novo, ou decidir onde clicar. As 3 técnicas de retry só mudam COMO a
tela é lida de novo (zoom, recorte, print novo) — nenhuma interage com
o Domínio (não clica, não digita, não tira o Domínio do estado em que
está). O clique em si continua vindo de `interacao.clicar(*pos)`, na
função que chamou `achar_ou_parar()`, calculado do jeito de sempre
(posição achada por OCR) — a IA nunca influencia isso.

**Por que essa é a versão certa do pedido, e não um patch de código
autônomo:** deixar a IA reescrever o `.py` e rodar de novo sozinha
contra o Domínio real seria autonomia sobre ação de verdade — clique
repetido, sem gente olhando cada tentativa, no pior domínio possível
pra errar (fiscal real). Escolher entre técnicas já testadas e
aprovadas é o mesmo padrão de segurança já usado pra caixa de erro
(seção 0.32), só aplicado a "como ler a tela de novo" em vez de "o que
fazer com uma caixa de erro".

Aplica pra qualquer automação que use `achar_ou_parar()` — inclusive
as gravadas/promovidas (`AUTOMACOES_EXTRAS`, seção 0.48) — de graça,
sem precisar mudar nada nelas.

**Ainda não testado ao vivo** — a lógica compila e o modo "sem chave"
foi conferido isoladamente (mesmo comportamento de antes desta seção),
mas a escolha de estratégia de verdade, contra uma falha real, ainda
não foi vista rodando.

### 0.52 Tela de geração presa derruba toda empresa seguinte em cascata — corrigido com Esc em dois pontos

Primeiro lote real depois de todas as correções recentes (0.40-0.51),
7 empresas reais (70, 2, 52, 12, 78, 83, 68), `tipo`/`sped` misto.
Achado grave: a empresa 52 recebeu a caixa conhecida "Saldo dos
impostos não foram calculados" (`ERROS_CONHECIDOS`, decisão PULAR
correta) — mas depois disso, `_fechar_tela_geracao()` não achou
"Fechar" em 3 tentativas e desistiu, **deixando a tela de SPED Fiscal
aberta**. Sem nada pra limpar isso, o efeito se espalhou:

- O CONTRIBUICOES da própria empresa 52 falhou também — o clique em
  "Relatórios" caiu em cima da tela ainda presa, não no menu.
- **As 4 empresas seguintes (12, 78, 83, 68) falharam inteiras** —
  `trocar_empresa()` aperta F8, mas com a tela anterior ainda presa
  por cima, o Domínio nunca abre "Troca de empresas" de verdade,
  então nunca acha o botão "Acessar". Uma tela presa derrubou o resto
  do lote inteiro.

**Corrigido em dois pontos, os dois só com Esc (recurso genérico já
validado, seção 0.34 — fecha diálogo/menu empilhado sem precisar saber
o que era):**

1. `_fechar_tela_geracao()`: antes de desistir de vez (quando não acha
   "Fechar"), tenta `interacao.pressionar_esc_repetidas()` — reduz a
   chance de a tela ficar presa pra próxima ação, na origem do
   problema. Também passou a chamar `_sugerir_diagnostico()` nesse
   ponto (não usava `achar_ou_parar()`, então não ganhava isso de
   graça como o resto — seção 0.49/0.51 cobriam só quem passa por
   `achar_ou_parar()`).
2. `trocar_empresa()`: se não achar o botão "Acessar" depois do F8,
   tenta `pressionar_esc_repetidas()` + F8 de novo, 1 vez, antes de
   desistir — proteção na ponta que teria evitado a perda das 4
   empresas mesmo que a tela de uma empresa anterior tivesse ficado
   presa por outro motivo qualquer.

**Confirma de quebra, no mesmo log:** `ia.resumir_lote()` (seção 0.49)
teve seu primeiro teste ao vivo aqui, e resumiu certo — identificou os
2 sucessos, a falha isolada da empresa 52, e o padrão repetido de
falha ao trocar de empresa nas 4 últimas. `_sugerir_diagnostico()`
também disparou de verdade pro "Não achei 'Informativ'." da empresa
52 (efeito colateral da tela presa) — hipótese razoável (tela
"carregando/transição"), mesmo sem saber a causa real (não tem
histórico de chamadas anteriores pra cruzar).

**Ainda não testado ao vivo** — a correção não foi vista rodando
contra o mesmo cenário (ou parecido) ainda. Próximo lote real decide
se o Esc realmente evita a cascata.

### 0.53 Tesseract "não instalado" mesmo instalado — PATH nem sempre pega

Achado no computador do operador: rodando a automação, pytesseract
acusa Tesseract não instalado/não encontrado no PATH, mesmo com o
Tesseract já instalado — instalador às vezes não marca "adicionar ao
PATH" sozinho, ou o Windows só aplica a mudança de PATH numa janela de
terminal nova, nunca na que já estava aberta.

**Corrigido em `app/tela.py`**: se `shutil.which("tesseract")` não
achar nada no PATH, tenta os dois caminhos padrão de instalação do
instalador oficial (UB-Mannheim) — `C:\Program Files\Tesseract-OCR\`
e a versão `(x86)` — e configura `pytesseract.pytesseract.tesseract_cmd`
direto, sem depender do PATH. Não muda nada se o Tesseract já é achado
pelo PATH normalmente (só entra nesse caminho quando falha).

**Ainda não confirmado se resolve o caso real do operador** — corrige
a causa mais comum desse erro, mas só um teste de verdade lá confirma.

### 0.54 Caminho do Tesseract configurável (`data/tesseract_caminho.txt`), pra quando não é o padrão

Complemento da seção 0.53: os dois caminhos padrão cobrem o instalador
oficial (UB-Mannheim) normal, mas não um Tesseract instalado num lugar
fora do comum (outra unidade, pasta customizada, versão portátil).
Pra esse caso, sem precisar editar `app/tela.py` nem depender de achar
o `.exe` sozinho: um arquivo `data/tesseract_caminho.txt` (mesmo
padrão de `data/chave_api.txt` — local, uma linha só, nunca sobe pro
GitHub) com o caminho completo do `tesseract.exe`, conferido antes dos
dois caminhos padrão. `Instalar.bat` agora menciona essa opção no
aviso, pra quem já tenta instalar e não acha no lugar certo saber que
existe essa saída sem precisar perguntar.

Ordem de busca final: PATH → `data/tesseract_caminho.txt` (se existir)
→ `Program Files\Tesseract-OCR` → `Program Files (x86)\...` → desiste.

### 0.55 Aviso direto quando não acha o Tesseract em lugar nenhum

Pergunta do usuário revelou uma lacuna: quando algum dos 4 lugares
(PATH, arquivo configurado, ou os 2 caminhos padrão) acha o Tesseract,
`app/tela.py` troca sozinho, sem avisar nada — comportamento certo,
funciona liso. Mas quando **nenhum** dos 4 acha, não tinha aviso
nenhum na hora — só quebrava depois, num erro cru do `pytesseract`
("tesseract is not installed..."), na primeira vez que alguma tela
precisasse ser lida, sem contexto nenhum pra quem não é programador.

**Corrigido:** se nenhum dos 4 lugares tiver o Tesseract, imprime um
aviso claro assim que o programa abre — link de instalação e o lembrete
do `data/tesseract_caminho.txt`, em vez de deixar o erro estourar
escondido lá na frente.

### 0.56 Busca automática do Tesseract dentro de Program Files, antes de avisar

Pedido do usuário: em vez de só conferir 2 caminhos fixos, o motor
devia **procurar** o `tesseract.exe` sozinho. Buscar o `C:\` inteiro
demoraria minutos toda vez que o programa abrisse — inviável. Meio
termo: busca recursiva só dentro de `C:\Program Files` e
`C:\Program Files (x86)` (onde praticamente todo instalador do Windows
põe as coisas, mesmo numa subpasta com nome diferente do esperado,
tipo com número de versão) — rápida (segundos), por ser uma fração
pequena do disco.

Roda só quando os 2 caminhos fixos da seção 0.53 falham, e só uma vez:
achando, salva o caminho em `data/tesseract_caminho.txt` sozinho —
próxima vez que o programa abrir, cai direto nesse arquivo (rápido,
seção 0.54), sem precisar buscar de novo. Testado isoladamente (lógica
pura de `pathlib.glob`, mesma limitação de sempre pra código que
depende de Windows): acha em subpasta aninhada, não acha quando
realmente não tem.

**Ainda pode não achar** se o Tesseract estiver numa unidade diferente
de C: ou fora de Program Files de propósito — nesse caso o aviso da
seção 0.55 ainda aparece, com a saída manual (`tesseract_caminho.txt`).

### 0.57 Primeira rotina nova fora do SPED: Registro de Saídas (Livro Fiscal) — caminho mapeado por print, implementado, ainda não executado

Pedido do usuário (escopo diferente do SPED Fiscal/EFD Contribuições):
exportar o relatório de notas de saída (Livro Registro de Saídas) pra
uma empresa do Simples Nacional, com competência já conferida
manualmente. Mapeado por uma sequência de 4 prints reais enviados
nesta conversa (não por suposição) — cada um pedido depois do anterior,
só a próxima tela necessária:

1. `Relatórios → Livros → Livros Fiscais` abre uma tela **com abas**
   (Geral, Termos, Entradas, Saídas, ICMS, IPI, ISS, Inventário...) —
   estrutura bem diferente do formulário único do SPED Fiscal.
2. Na aba Geral: lista de caixas de seleção (uma por livro —
   "Registro de Entradas", "Registro de Saídas", "Registro de ICMS"
   etc.) + campos "Inicial"/"Final" (não "Data inicial"/"Data final"
   como no SPED).
3. OK abre uma **pré-visualização de livro impresso** (não uma caixa
   de confirmação de texto) — identificada pelo corpo mostrar
   "LIVRO REGISTRO DE SAÍDAS - RS - MODELO P2" e os dados reais da
   empresa (confirmado contra a SPRAYAGRO CONSULTORIA LTDA, Lucro
   Presumido — não é a empresa-alvo do piloto, serviu só pra mapear o
   caminho, já que gerar esse relatório não altera nenhum dado).
4. A pré-visualização tem uma barra de ferramentas vertical **só com
   ícones, sem texto** — um deles (confirmado "X" verde, estilo
   Excel) abre um diálogo **nativo do Windows** ("Selecione o
   arquivo"/"Save as") com campo de nome de arquivo editável e tipo já
   em "Arquivos do Excel (*.xls)".

**Dois achados técnicos novos, por medição de pixel nos próprios
prints** (não por execução — ver ressalva abaixo):

- **OCR lê "Inicial"/"Final" como "Iniciat"/"Finat"** nesta tela, na
  escala usada (2x) — troca de "l" por "t" no fim da palavra, mesma
  categoria de erro já vista noutro lugar ("SPED Fiscal" → "spEo",
  seção 0.26). Corrigido buscando só o prefixo comum "Inicia"/"Fina",
  mesmo padrão já usado pra "Informativ" em `gerar_sped()`.
- **O diálogo "Salvar como" desta tela é nativo do Windows**, não
  desenhado pelo Domínio — confirmado porque mostra pastas reais em
  inglês ("Downloads", "Desktop", "This PC"), ao contrário do resto da
  interface (português, desenhada pelo Domínio). Isso simplifica bastante
  essa etapa: aceita caminho completo digitado direto no campo de nome,
  e a confirmação de sucesso pode ser feita **checando o arquivo no
  disco** (existe + tamanho > 0) em vez de OCR — primeira vez neste
  projeto que a verificação de sucesso não depende de ler a tela.

**Ícone sem texto — primeira vez que o projeto implementa casamento de
imagem** (`tela.achar_icone()`, `cv2.matchTemplate`, reaproveitando o
`opencv-python` que já estava no `requirements.txt` mas nunca tinha
sido usado): recorte do ícone "exportar" salvo em
`app/icones/exportar_excel.png` (a partir do mesmo print real usado
pra mapear o caminho), casado contra a tela ao vivo com limiar de
confiança 0.75 — testado só contra o print estático de onde veio o
recorte (confiança 1.0, esperado, é a mesma imagem), **ainda não
testado contra a tela ao vivo via GO-Global**, onde anti-aliasing/cor
podem renderizar levemente diferente. Mantém o deslocamento calculado
por pixel (a partir da âncora "LIVRO REGISTRO", medido no mesmo print)
como plano B, caso o casamento de imagem não ache nada.

**Atualização, mesma sessão:** implementada uma segunda opinião de OCR
pra resolver a categoria "Iniciat"/"Finat" acima de vez — motor nativo
do Windows (`Windows.Media.Ocr`, pacote `winocr`, grátis e local, sem
chamada de rede), em `tela.achar_texto_windows()`, com a mesma
interface de `tela.achar_texto()`. **Testado ao vivo** contra o print
real desta investigação (não só por leitura): Tesseract não achou
"Inicial" (palavra inteira) nesse recorte; o motor do Windows achou,
de primeira, na posição certa (confirmada batendo com a medição manual
de pixel feita antes). `preencher_periodo_livros_fiscais()` agora tenta
Tesseract → OCR do Windows → prefixo truncado do Tesseract, nessa
ordem, antes de desistir. A mesma segunda opinião também virou mais
uma estratégia de retry (`OUTRO_MOTOR_OCR`) que a IA pode escolher em
`achar_ou_parar()` — nunca troca o Tesseract como motor principal, só
reforça quando ele falha. Depende do pacote de idioma Português do
Windows estar instalado (confirmado presente nesta máquina,
`OcrEngine.is_language_supported`); sem ele (ou sem o pacote `winocr`
instalado), a função devolve `None` sem quebrar nada, mesmo padrão de
funcionalidade opcional já usado pra `ia.disponivel()`.

**Primeira execução real, 01/10/2026 — parcialmente confirmado:**
navegação completa (Relatórios → Livros → Livros Fiscais), clique na
caixa "Registro de Saídas" e preenchimento do período **confirmados
funcionando** contra o Domínio real (inclusive a segunda opinião de
OCR do Windows, que entrou em ação de verdade — Tesseract não achou
"Inicial"/"Final" sozinho). Parou no cálculo do "OK": `achar_texto`
direto por "OK" de fato não achou (confirma a suspeita, só por
inspeção visual não dava pra saber com certeza), e o cálculo por
"Fechar" também falhou — **causa raiz, não ambiguidade**: o recorte da
área do diálogo (`recortar_a_partir_de`) usou a largura padrão de
650px, herdada do diálogo (bem mais estreito) do SPED Fiscal; a tela
"Livros Fiscais" é larga o bastante pra a coluna de botões
OK/Fechar/Concluir Atividade ficar a ~900px do título, fora do recorte
de 650px — cortava a coluna de botões inteira antes mesmo de tentar
ler "Fechar". Corrigido aumentando a largura/altura do recorte pra
1300×600 nesta chamada específica.

**Segunda execução real, mesmo dia** (depois da correção acima): parou
um passo antes do esperado — nem chegou a confirmar a caixa "Registro
de Saídas", porque não achou o **título** "Livros Fiscais" logo depois
de clicar no item de menu. O print de debug mostrou só a barra de menu
do Domínio (Relatórios/Livros/Informativos ainda visíveis), não o
diálogo — a tela "Livros Fiscais" simplesmente ainda não tinha
terminado de abrir no momento em que o código checou. Causa raiz: o
passo 4 (confirmar que a tela abriu) usava `time.sleep(2)` fixo +
checagem única, em vez de **esperar por estado** — exatamente a
categoria de erro que `esperar_e_achar()` já existe pra resolver desde
o SPED Fiscal (seção 0.12), só não tinha sido reaproveitado nesta
função nova ainda. Corrigido trocando pra `esperar_e_achar()` (até 15
tentativas, 1s entre elas).

**Terceira execução real, mesmo dia** (depois da segunda correção):
passou de navegação, checkbox e período — chegou a clicar OK de
verdade (o cálculo a partir de "Fechar", corrigido na execução
anterior, funcionou). Parou numa caixa de aviso real do Domínio:
**"Falta apurar saldo dos impostos neste intervalo de data!"** — a
competência escolhida automaticamente (mês anterior ao atual, por
data) ainda não teve a apuração de ICMS fechada no Domínio pra essa
empresa. Achado conceitual importante: "mês anterior por calendário"
não é o mesmo que "mês já apurado no Domínio" — pro Registro de
Saídas (que mostra totais de ICMS) precisa de uma competência
**realmente fechada**, não só a mais recente por data.

Duas correções: (1) `TITULOS_ERRO` não reconhecia o título "Aviso"
sozinho (só "Atenção"/"Aviso Empresa") — por isso o motor ficaria
martelando até 90s sem entender que era um aviso, em vez de reconhecer
na hora; adicionado "Aviso" à lista. (2) Essa mensagem já estava
prevista no catálogo de `app/erros.py` (decisão: PULAR), mas com um
texto diferente do real ("saldo dos impostos não foram calculados",
nunca confirmado ao vivo até agora) — adicionada a entrada com o texto
**confirmado de verdade**: "falta apurar saldo dos impostos". Também
corrigida a diferenciação de ação em `gerar_registro_saidas()` (antes
tratava qualquer ação do catálogo igual, sempre desistindo — agora
distingue CONTINUAR/TENTAR_DE_NOVO/PARAR_LOTE/PULAR, mesmo padrão de
`gerar_sped()`).

Ainda falta: (a) re-testar com essas correções, (b) escolher, com o
usuário, uma competência da empresa de teste que já tenha apuração de
ICMS fechada no Domínio — não dá pra confiar na regra "mês anterior"
pra esse relatório específico.

**Atualização após a 3ª execução real:** navegação, marcar a caixa,
preencher período, clicar OK e abrir a pré-visualização — tudo
confirmado contra o Domínio real. O ícone de exportar foi achado por
casamento de imagem com confiança 1.0 — mas abriu **"Salvar em PDF"**,
não Excel (suposição inicial errada, corrigida: formato de saída
trocado pra `.pdf`, `app/verificacao.py` reescrito pra `pypdf` em vez
de `xlrd`). A tentativa de salvar com extensão `.xls` num diálogo
travado em `*.pdf` deu "Path does not exist." — corrigido gerando
sempre nome com extensão `.pdf`, mais uma checagem defensiva desse
aviso específico. **Ainda não confirmado**: se a correção de extensão
resolve o salvamento de ponta a ponta — próximo passo é rodar de novo
e confirmar que o arquivo .pdf aparece em disco com conteúdo
reconhecível (`verificar_registro_saidas_pdf()`).

**Interface gráfica reescrita, mesmo dia** — pedido do usuário ("tá
feia e sem tanta utilidade"): `scripts/gui.py` passou a usar
`ttkbootstrap` (tema "flatly", skin plana moderna sobre o mesmo
Tkinter de sempre, sem infraestrutura nova) e ganhou duas coisas que
não existiam: aba "Histórico" (lista as últimas execuções, lidas de
`app/historico.py` → `data/historico_execucoes.json`, novo, gitignored
— com botão pra abrir o arquivo gerado ou a pasta de saída) e uma
seção própria pro Registro de Saídas (campos de competência + botão),
em vez de só os botões de "empresa já selecionada" que já existiam.
Testado só visualmente (construção da janela real + print automático,
seção descrita no histórico de conversa) — **nunca clicado de verdade
contra o Domínio**, os botões por trás continuam os mesmos já
documentados acima. Também corrigido um gap de LGPD encontrado nessa
mesma revisão: `saida/` (pasta com os PDFs/arquivos gerados, pode
conter dado fiscal real) não estava no `.gitignore` — adicionado.

**Pesquisa de priorização, mesmo dia** (pedido do usuário: "aprender
os caminhos e o que deve ser útil em rotinas"): cruzando o que os
próprios 57 agentes fiscais já documentam sobre obrigatoriedade por
regime — SPED Fiscal "dispensado em geral" pro Simples Nacional
(`06-sped-fiscal.md`) e EFD Contribuições só pra "Real/Presumido"
(`32-efd-contribuicoes.md`) — com a composição real da carteira (23
Simples, 15 Presumido, 3 Real): **as duas rotinas já prontas (SPED
Fiscal, EFD Contribuições) não servem pras 23 empresas do Simples**,
só pras 18 de Presumido/Real. O Registro de Saídas/Entradas (livro
fiscal, não vinculado a regime) é a peça que mais fecha essa lacuna —
confirma que a escolha de continuar nessa frente, em vez de trocar de
rotina, está certa.

Generalização de baixo custo, mesmo dia: `gerar_registro_saidas()`
virou um wrapper fino sobre uma função interna genérica
(`_gerar_livro_fiscal()`), e ganhou um irmão, `gerar_registro_entradas()`
— mesma tela, mesmo mecanismo (OK calculado, pré-visualização, ícone
de exportar, "Salvar em PDF"), só muda qual caixa marcar na aba Geral.
**"Registro de Entradas" nunca rodou contra o Domínio real** — é só
generalização de código, o deslocamento do checkbox (calibrado pra
"Registro de Saídas") pode precisar de ajuste fino quando for testado
pela primeira vez. `app/verificacao.py` também generalizado
(`verificar_livro_fiscal_pdf()`, com `verificar_registro_saidas_pdf()`
como wrapper de compatibilidade). Interface gráfica ganhou um combo
"Registro de Saídas"/"Registro de Entradas" na mesma seção, em vez de
dois botões separados.

---

### 0.58 Complemento de percepção pedido pelo usuário: mais uma técnica sem IA (ORB) + fingerprint de tela pra velocidade + exceção controlada pra visão por IA como último recurso

Pedido do usuário (05/10/2026), depois do diagnóstico de arquitetura
(seção anterior desta conversa, não numerada no documento): "complemente
o OCR com identificação visual de outra forma, pelo menos mais uma
técnica, pra esse RPA funcionar bem e mais rápido." Três entregas:

**1. `tela.achar_icone_orb()` + `achar_icone_robusto()`** — segunda
técnica de casamento de ícone, por características (ORB), não só por
correlação de pixel (`achar_icone()`, que já tinha a ressalva própria:
"o ícone pode renderizar com leve diferença de cor/anti-aliasing na
tela ao vivo via GO-Global"). `achar_icone_robusto()` tenta pixel
primeiro, cai pra ORB só se o primeiro falhar — nenhum código existente
quebra, é aditivo. **Ainda não testado contra o Domínio real** (mesma
limitação de sempre deste ambiente de desenvolvimento) — calibrar
`minimo_bons` depois do primeiro uso real.

**2. `tela.assinatura_tela()` + `tela.tela_mudou()`** — "impressão
digital" barata da tela (average hash 8×8, só Pillow, sem dependência
nova) usada em `dominio.esperar_e_achar()` pra pular OCR (a parte mais
lenta de cada tentativa de espera) quando a tela não mudou nada desde a
tentativa anterior — rodar OCR de novo sobre uma imagem idêntica nunca
muda a resposta. **Testado por lógica pura neste ambiente** (imagens
sintéticas: assinatura igual pra imagem idêntica, diferente pra imagem
bem distinta, `tela_mudou(None, ...)` sempre True na primeira tentativa)
— comportamento confirmado correto; impacto real de velocidade só
confirma contra o Domínio de verdade.

**3. `app/visao.py` — fallback de visão por IA, exceção controlada.**
O usuário escolheu explicitamente (pergunta direta, não decisão minha)
abrir uma exceção à regra "nunca manda print pra IA" (seção 5.5),
restrita a: só como último recurso (depois de OCR e OpenCV falharem,
nova entrada `VISAO_IA` em `ia.ESTRATEGIAS_RETRY`, mesmo padrão fechado
de sempre); resposta sempre em formato fechado (coordenada ou estado,
nunca ação); toda imagem enviada fica salva local em
`data/visao_enviado/` pra auditoria. A trava central é
`visao._contem_dado_sensivel()` — roda OCR local na imagem antes de
decidir se envia.

**Achado real, testando a própria trava** (05/10/2026): a primeira
versão reaproveitava só `erros.anonimizar()` pra decidir o que é dado
sensível — mas aquela função, de propósito (comentário no próprio
código), NÃO mascara um texto 100% em maiúsculo, pra não apagar a
mensagem inteira de uma caixa de erro. Testei com o texto
`"SPRAYAGRO CONSULTORIA LTDA"` (nome de empresa real já usado neste
documento, seção 0.57) e `anonimizar()` sozinho **não barrou** — esse é
exatamente o formato mais provável de nome de empresa aparecendo
sozinho num título/cabeçalho de tela do Domínio. Corrigido com uma
checagem própria, mais conservadora, que roda ANTES: qualquer sequência
de 2+ dígitos, ou qualquer palavra de 4+ letras toda maiúscula que não
esteja numa lista pequena de vocabulário de interface já visto
(`_PALAVRAS_SEGURAS`), barra o envio — `anonimizar()` entra só como
rede adicional depois. Testado com 7 casos (texto vazio, barra de
ferramentas, título de diálogo já conhecido, o nome de empresa do bug
achado, CNPJ, caminho de arquivo, palavra maiúscula desconhecida) via
mock do OCR (`unittest.mock`, sem precisar de Tesseract de verdade
neste ambiente) — todos os 7 se comportaram como esperado depois da
correção, incluindo o caso que motivou a correção.

`docs/HANDOFF.md` atualizado com a exceção descrita por extenso (seção
de segurança) — a regra geral continua sendo "nunca manda print pra
IA", com `app/visao.py` como única exceção documentada e isolada.

**Nenhuma das três entregas foi testada contra o Domínio real ainda**
— só validação de sintaxe e lógica pura (limitação de sempre deste
ambiente de nuvem). Próximo passo natural: testar `achar_icone_robusto()`
no mesmo ponto onde `achar_icone()` já é usado (ícone "Salvar em PDF"
do Registro de Saídas, seção 0.57), e observar se `VISAO_IA` chega a
ser escolhida pela IA de retry em alguma falha real de OCR.

---

### 0.59 Causa raiz real do "Path does not exist." do Registro de Saídas: a sessão do Domínio não compartilha o disco local — achado maior que o esperado, afeta também SPED Fiscal/EFD

Retomando a validação pendente da seção 0.57 (confirmar o `.pdf` em
disco) — a primeira execução real, 06/10/2026, voltou a dar "Path does
not exist.", mesmo com a extensão `.pdf` já corrigida. Investigação por
evidência real (nunca chutada), passo a passo:

1. **Conferido que a pasta existia de verdade, no momento do erro** —
   `pasta_destino.mkdir(parents=True, exist_ok=True)` já criava
   `saida/` nesta máquina local (confirmado por `ls`, timestamp batendo
   com o horário do teste). Mesmo assim o diálogo recusou o caminho —
   descartava a hipótese de "pasta não criada a tempo".
2. **Print automático do erro** (`capturas/erro_caminho_invalido.png`,
   já salvo pelo próprio código) mostrado: o campo "Save in" do
   diálogo "Salvar em PDF" abre em **"Downloads"**, não na pasta do
   projeto — primeira pista de que o diálogo pode não estar vendo o
   mesmo disco desta máquina.
3. **Teste manual, sem automação**: salvar um arquivo (`teste123.pdf`)
   direto em "Downloads" (a pasta padrão do próprio diálogo, sem
   digitar nenhum caminho customizado) — o Domínio confirmou sucesso
   (arquivo aparece na listagem do próprio diálogo, reaberto depois).
   **O arquivo NÃO apareceu no Downloads local de verdade do usuário**
   — prova direta de que o "Downloads" da sessão do Domínio é outro,
   não o desta máquina.
4. **Pergunta ao usuário se algum arquivo gerado até hoje (SPED Fiscal,
   EFD Contribuições) já foi localizado/aberto localmente** — resposta:
   **não, só no servidor**. Achado maior que o esperado: isso não é um
   bug isolado do Registro de Saídas — **nenhum arquivo gerado por
   nenhuma rotina até agora provavelmente nunca saiu do servidor
   remoto de verdade**; "sucesso" sempre foi medido só pela confirmação
   na tela (OCR), nunca por achar o arquivo no disco local.
5. **Causa raiz confirmada, com a "ponte" encontrada**: no mesmo
   diálogo, clicando em "This PC" (a pedido), apareceram 3 discos:
   `Servidor (C:)` (o disco do servidor remoto — é esse "C:\" que o
   diálogo via, não o desta máquina), **`Client C (M:)`** (o disco C:
   **desta máquina**, mapeado como unidade de rede `M:` dentro da
   sessão remota — nome e padrão típicos de solução de renderização
   remota), e `Local Disk (Z:)` (não identificado ainda, não usado).
6. **Teste de confirmação final**: salvar em `M:\Users\darto\Downloads\teste123.pdf`
   (de dentro da sessão) → **apareceu em
   `C:\Users\darto\Downloads\teste123.pdf` no Downloads local de
   verdade**. Confirma 100%: `M:` dentro da sessão do Domínio
   corresponde a `C:` desta máquina, caminho por caminho.

**Correção aplicada** (`app/dominio.py`): nova função
`caminho_visto_pela_sessao_remota()` — converte um caminho local
(`C:\Users\darto\...`) pro equivalente visto de dentro da sessão
(`M:\Users\darto\...`, só trocando a letra da unidade, resto do
caminho igual). `_gerar_livro_fiscal()` agora usa essa conversão só no
texto DIGITADO no diálogo — `pasta_destino.mkdir()`/
`caminho_completo.exists()` continuam usando o caminho local de
verdade, sem conversão (são operações desta máquina, não da sessão
remota). Letra configurável em `data/unidade_cliente.txt` (mesmo
padrão de `data/tesseract_caminho.txt`) — "M" já confirmado e salvo
nesta máquina; pode precisar mudar noutra instalação/sessão.

**Ainda não re-testado** com a correção (próximo passo óbvio: rodar
Registro de Saídas de novo e confirmar o `.pdf` real em
`C:\Users\darto\dominio-automation-engine\saida\`).

**Pendência separada, fora do alcance de código — ação do usuário
dentro do próprio Domínio**: se a pasta de destino configurada para
SPED Fiscal/EFD Contribuições (cadastro por empresa dentro do
Domínio, não controlado por este motor — ver `erros.py`, "caminho
especificado não é válido") também aponta pra um caminho `C:\...`, os
arquivos gerados por essas duas rotinas até hoje podem estar igualmente
presos no servidor remoto. **Já verificado pelo usuário**: ela já
configura isso manualmente e sabe onde o arquivo vai — não é uma
pendência real, só valia conferir.

**Confirmado ao vivo, 06/10/2026, depois da correção**: Registro de
Saídas rodou de ponta a ponta contra a SPRAYAGRO CONSULTORIA LTDA —
arquivo `registro_saidas_01082026_31082026.pdf` apareceu de verdade em
`C:\Users\darto\dominio-automation-engine\saida\` (29.179 bytes).
Conteúdo conferido por `verificar_registro_saidas_pdf()` — achou CNPJ
62.994.636/0001-53 e o período certo. Achado secundário nessa mesma
verificação: o título do PDF sai do `pypdf` com espaço entre cada letra
("R E G I S T R O  D E  S A Í D A S", é assim que o Domínio posiciona o
texto no PDF, não erro de leitura) — `verificar_livro_fiscal_pdf()`
comparava sem tolerar isso e dava falso negativo; corrigido comparando
os dois lados sem nenhum espaço. **Primeira rotina fora do SPED
Fiscal/EFD Contribuições validada de ponta a ponta, mecanismo E
conteúdo, contra o Domínio real.**

Falta ainda: primeira execução real do Registro de Entradas (só
generalização de código até agora, nunca rodado).

---

### 0.60 Primeira execução real do Registro de Entradas: travou esperando a pré-visualização, "LIVRO REGISTRO" não achado — causa raiz na ordem de leitura do Tesseract

Primeira execução real de Registro de Entradas, 06/10/2026 (SPRAYAGRO
CONSULTORIA LTDA, 01/08 a 31/08/2026). Navegação, marcar a caixa
"Registro de Entradas", preencher período e clicar OK **funcionaram**
— print real confirma a pré-visualização aberta, com dado certo
("REGISTRO DE ENTRADAS", CNPJ 62.994.636/0001-53, período certo,
lançamentos reais). Mas o código ficou martelando "Ainda não achei
'LIVRO REGISTRO'" por várias tentativas (log real colado pelo
usuário), apesar da tela já mostrar a pré-visualização aberta.

**Causa raiz, pela evidência do próprio log** (lista de palavras que o
Tesseract leu, impressa pelo `debug=True`):

```
..., 'LIVRO', 'DOMÍNIO', 'SPRAYAGRO', 'REGISTRO', 'DE', 'ENTRADAS', ...
```

`tela.achar_texto()` só acha frase de 2+ palavras se elas estiverem
**adjacentes na ordem de leitura que o próprio Tesseract devolve**
(índice sequencial de `image_to_data`), não por proximidade visual na
tela. Aqui "LIVRO" (provavelmente lido perto do título da janela,
"...[08/2026 LIVRO DE ENTRADA]") saiu seguido de "DOMÍNIO"/"SPRAYAGRO"
(cabeçalho), não de "REGISTRO" (que só aparece depois, no corpo do
relatório) — nunca ficam adjacentes nessa execução específica, mesmo a
tela mostrando os dois. Intrigante: essa mesma busca ("LIVRO REGISTRO")
já tinha funcionado pro Registro de Saídas — a ordem de leitura do
Tesseract aparentemente não é estável entre execuções/telas parecidas,
o que torna buscar frase de 2+ palavras nesse tipo de tela densa
arriscado em geral, não só um bug pontual.

**Correção**: trocada a âncora de confirmação de "LIVRO REGISTRO" pra
só **"REGISTRO"** (uma palavra só, evita depender de adjacência) nos 2
pontos onde era usada em `_gerar_livro_fiscal()`. Risco aceito e
documentado: a tela ANTERIOR (seleção de caixas) também tem "Registro
de Entradas"/"Registro de Saídas" como rótulo — mas essa tela já devia
estar fechada (OK já foi clicado) antes desse trecho rodar. O
deslocamento fixo de plano B pro ícone de exportar (calibrado com a
âncora antiga, 2 palavras) fica levemente desatualizado — comentado no
código; não deve importar na prática porque `achar_icone_robusto()` é
tentado primeiro.

**Ainda não re-testado** com a correção — próximo passo óbvio: rodar
Registro de Entradas de novo e confirmar que passa desse ponto e gera
o PDF (mesmo padrão de validação já aplicado ao Registro de Saídas,
seção 0.59).

**Achado à parte, mesma conversa**: usuário reportou "pausar não
funciona" tentando interromper essa execução travada. Não é bug — o
botão "Pausar" só é habilitado pra ações em LOTE
(`_rodar_em_thread(..., pausavel=True)`), nunca pra uma ação de
empresa única (seção 0.34, por design). Não há hoje nenhuma forma de
CANCELAR uma ação de empresa única travada, a não ser fechar a janela
inteira — gap real de usabilidade, não endereçado ainda (fora do
escopo desta correção, considerar separadamente).

**Confirmado ao vivo, mesmo dia, depois da correção**: Registro de
Entradas rodou de ponta a ponta — `registro_entradas_01082026_31082026.pdf`
(74.926 bytes) apareceu em `saida/`, histórico marcou sucesso,
`verificar_livro_fiscal_pdf()` confirmou "REGISTRO DE ENTRADAS" e o
CNPJ certo no conteúdo. **Registro de Saídas e Registro de Entradas
agora validados os dois, mecanismo e conteúdo, contra o Domínio real**
— fecha a pendência que restava da seção 0.59/Etapa A.

---

### 0.61 Teste ao vivo de ORB + fingerprint de tela (seção 0.58) — fingerprint validado, ORB não ajuda nesse ícone (template pequeno demais); visão por IA integrada como 3º nível pro casamento de ícone

Pedido do usuário: testar ao vivo o complemento de percepção da seção
0.58. Evidência veio de graça, dos próprios logs reais das execuções
de Registro de Saídas/Entradas (`data/ultimo_log.txt`), sem precisar
forçar nenhum teste isolado:

- **`tela.assinatura_tela()`/`tela_mudou()` (fingerprint)** —
  **confirmado funcionando ao vivo**: o log real mostra "Tela igual à
  tentativa anterior, pulando OCR" repetido várias vezes seguidas
  durante a espera da pré-visualização — exatamente o comportamento
  pretendido (pula OCR quando a tela não mudou).
- **`tela.achar_icone()` (pixel)** — funcionou uma vez com confiança
  1.000, falhou outra com confiança 0.534 (abaixo do limiar 0.75) —
  confirma de verdade a ressalva original da seção 0.57 sobre
  anti-aliasing via GO-Global.
- **`tela.achar_icone_orb()`** — tentado no caso real que o pixel
  falhou, mas devolveu "poucos pontos de interesse pra comparar".
  Causa, não suposição: o template (`app/icones/salvar_pdf.png`) tem
  só **30×25 pixels** — pequeno e simples demais pro detector de
  cantos/blobs do ORB achar pontos de interesse suficientes. Não é bug
  de implementação, é limite da técnica nesse tamanho de ícone. Nos
  dois casos reais, quem efetivamente salvou foi o deslocamento
  calculado (plano C, já existia antes de hoje) — ORB não contribuiu
  em nenhum dos dois runs.

**Correção/melhoria**: integrada a visão por IA (`app/visao.py`, seção
0.58) como **3º nível** no casamento de ícone, entre
`achar_icone_robusto()` (pixel+ORB) e o deslocamento calculado final —
antes só estava plugada na busca de texto (`achar_ou_parar()`). Usa
`tela.melhor_casamento_pixel()` (núcleo de `achar_icone()` sem aplicar
limiar, exposto publicamente pra isso) como dica de ONDE recortar —
mesmo com confiança baixa, a posição tende a estar perto do ícone de
verdade — e manda só esse recorte pequeno pra IA, nunca a tela inteira
(que tem CNPJ/razão social visíveis e seria recusada pela trava de
`visao._contem_dado_sensivel()`, com razão). Testado por lógica pura
(mock de `tela.melhor_casamento_pixel()`/`visao.localizar_elemento()`):
confirma que a conversão de coordenada relativa-ao-recorte pra
coordenada-de-tela-cheia bate certo, e que só o recorte (não a imagem
inteira) é mandado pra `visao.localizar_elemento()`.

**Ainda não testado contra o Domínio real** — vai ser exercitado
naturalmente na próxima vez que `achar_icone_robusto()` falhar de novo
(não dá pra forçar isso sob demanda sem mexer no ícone/template de
propósito). Cadeia de fallback pro ícone de exportar agora tem 4
níveis: pixel → ORB → visão por IA (recorte pequeno) → deslocamento
calculado.

---

### 0.62 StateEngine mínimo (`app/estados.py`) — generalização do padrão de espera já repetido em 4 rotinas reais

Pedido do usuário: considerar a Etapa A (núcleo OCR/percepção) fechada
— já rodou SPED Fiscal/EFD Contribuições em lote antes, quer evoluir o
sistema pra testar depois contra empresas reais — e seguir pro próximo
passo do roadmap maior: formalizar um motor de estados mínimo, em vez
de cada rotina reimplementar sozinha "espera, confere erro, confere
sucesso".

**Por que agora, não antes**: o próprio roadmap desta conversa (e o
princípio geral do projeto, seção 52 do prompt original) diz pra não
formalizar arquitetura antes de ter rotinas reais o bastante pra
generalizar por padrão OBSERVADO, não suposição. Agora já são 4
rotinas reais (SPED Fiscal, EFD Contribuições, Registro de Saídas,
Registro de Entradas) todas passando pelo mesmo `esperar_e_achar()` —
dado real suficiente pra extrair o padrão com confiança.

**O que foi feito**: `app/estados.py`, novo módulo, com
`esperar_por_estado(detectores, espera_minima, tentativas, intervalo)`
— motor genérico: tira print repetidamente (pulando a checagem quando
o fingerprint de tela, seção 0.58, diz que nada mudou), testa uma
lista de `(nome_estado, funcao_detectora)` NESSA ORDEM a cada
tentativa, devolve o primeiro que achar alguma coisa.
`dominio.esperar_e_achar()` foi refeita por cima desse motor (vira o
alvo de sucesso + cada título de `texto_erro` em detectores) — mesma
assinatura, mesmo retorno de antes da extração.

**Nenhuma das 4 rotinas precisou mudar uma linha** — todas já chamavam
`esperar_e_achar()`, nunca o motor novo diretamente; o benefício (e o
risco de regressão) fica isolado num ponto só.

**Validado por equivalência comportamental** (não contra o Domínio
real — mesma limitação de sempre deste ambiente): 3 cenários testados
com mock (`tela.capturar_tela`/`achar_texto_ou_no_centro` simulados) —
sucesso numa tentativa posterior, erro achado antes do sucesso,
esgotamento sem achar nada — os 3 batendo exatamente com o
comportamento documentado da função antes da extração (mesmo formato
de retorno, mesma prioridade sucesso-antes-de-erro dentro da mesma
tentativa). Deliberadamente NÃO testado ao vivo ainda — próximo passo
natural é rodar qualquer uma das 4 rotinas de novo e confirmar que o
comportamento continua idêntico na prática, não só no teste de lógica.

**Escopo deliberadamente pequeno**: não é o "StateEngine" completo do
prompt original (sem estados nomeados tipo `LOGIN`/`PROCESSING`/
`RESULT`, sem máquina de transição formal) — só o núcleo que as 4
rotinas reais realmente usam hoje. Crescer quando uma rotina nova
pedir de verdade.

---


### 0.63 Livros fiscais: nome por tipo/CNPJ/competência e fim do falso sucesso por PDF anterior

**Achado real (log do usuário, 06/10/2026):** a exportação de Registro
de Saídas chegou ao aviso "já existe. Deseja substituí-lo?", mas não
registrou confirmação da substituição. Mesmo assim, declarou "Arquivo
gerado" ao encontrar o PDF preexistente, de 36.036 bytes. Existência e
tamanho de um arquivo antigo não provam uma exportação nesta execução.

**Pedido do usuário:** continuar aqui o trabalho iniciado no Claude
Code e nomear cada PDF com tipo de documento, empresa e competência.
A empresa é identificada pelo CNPJ lido localmente no cabeçalho do PDF;
não se inventa código/nome a partir de OCR incerto. Para mês completo:
`registro_saidas_<CNPJ>_2026-08.pdf` e
`registro_entradas_<CNPJ>_2026-08.pdf`. Períodos parciais ou de vários
meses preservam as datas: `<tipo>_<CNPJ>_2026-08-02_a_2026-09-30.pdf`.

**Correção:** ambos os livros exportam primeiro para
`exportacao_<UUID>.pdf`, exclusivo da tentativa e com o mesmo mapeamento
local/remoto da seção 0.59. Não há confirmação automática de substituição.
O arquivo deve aparecer, estabilizar tamanho/data de modificação e abrir
como PDF verdadeiro por `pypdf`; o cabeçalho da primeira página deve
confirmar título, período e CNPJ único. Aceita letras/datas espaçadas,
como já observado na extração dos títulos. CNPJ rotulado é prioritário;
sem rótulo, exige um único CNPJ formatado no cabeçalho. Não usa texto
bruto como prova de PDF válido. Todas as páginas são lidas antes de
publicar o nome definitivo. Se já existir, preserva o anterior e grava
`_2`, `_3` etc., com criação exclusiva para evitar substituição também
entre execuções concorrentes.

Sem CNPJ inequívoco, período/tipo divergentes ou arquivo incompleto,
a rotina retorna falha e mantém a exportação temporária para diagnóstico
local; um arquivo final de rodada anterior nunca satisfaz a tentativa.
`app/arquivos.py` contém essa lógica sem dependência de tela ou IA.
Nenhum PDF, identidade ou conteúdo fiscal é enviado a serviço externo.
A GUI continua usando o mesmo retorno `(sucesso, caminho)` e recebe o
nome final automaticamente. Os scripts exploratórios aceitam
`--cnpj` opcional para também conferir a empresa esperada, além de
`--data-inicial` e `--data-final`; nenhum CNPJ real fica no script.
Datas inválidas/invertidas são recusadas antes de iniciar os cliques.

**Validação disponível:** sete testes automatizados com dados sintéticos
cobrem PDF real criado em memória, título/período/empresa divergentes,
texto espaçado, identidade ausente/ambígua, intervalos parciais/múltiplos
meses, preservação de arquivo anterior, exportação nova ausente, PDF
incompleto e texto disfarçado de PDF; compilação dos arquivos alterados.
Dois cenários de integração com tela simulada também passaram: um PDF
anterior presente sem exportação nova retorna falha e permanece intacto;
a exportação sintética no caminho UUID retorna o nome final validado e
remove o temporário. Os scripts também foram verificados com gerador
simulado para a passagem das datas/CNPJ e reporte de falha.
**Ainda não validado contra o Domínio real.** A navegação, ícones e
coordenadas existentes foram preservados. O próximo teste deve usar
competência já fechada e ICMS já apurado no Domínio (seção 0.57), sem
interagir com teclado/mouse durante a execução, e conferir o log/arquivo
final localmente.

---

### 0.64 Nome de arquivo pela empresa exibida no canto superior direito

**Pedido e evidência (06/10/2026):** o usuário indicou em captura real
que quer o nome exibido no canto superior direito do Domínio, entre o
usuário conectado e a competência. A linha tem o formato
`EMPRESA EXEMPLO - 52`: o código final identifica a seleção, mas não
deve entrar no nome do PDF. Este pedido substitui o CNPJ no nome
introduzido na seção 0.63; a conferência interna do CNPJ permanece.

**Mudança:** após focar o Domínio e antes de abrir Relatórios, captura
nova da tela e leitura local por Tesseract da faixa superior direita.
O parser exige uma linha de nome seguida de hífen e código numérico,
rejeita ausência/ambiguidade, e não reutiliza nome de uma execução
anterior. Esse recorte é apenas para leitura; nenhuma coordenada de
clique, caminho de menu ou ícone foi alterado. Se a identificação
falhar, interrompe antes da navegação e salva captura para diagnóstico.

Nome final: `registro_saidas_EMPRESA_EXEMPLO_2026-08.pdf` e equivalente
para Entradas. A grafia é a exibida no cabeçalho, inclusive abreviações;
acentos, espaços e caracteres inadequados para nomes de arquivo Windows
são normalizados. A competência vem do período solicitado/conferido no
PDF, não da competência exibida no canto da tela (podem ser diferentes).
Continuam a exportação UUID, conferência do PDF/tipo/período/CNPJ e
preservação dos anteriores com sufixos, da seção 0.63.

**Validação automatizada:** 13 testes passaram, incluindo OCR real de
cabeçalho sintético, parsing de nome/código, sanitização e validação de
PDF. Duas integrações simuladas passaram: nome ausente impede abrir
menus; nome identificado chega ao PDF final sem CNPJ no nome. Compilação
dos módulos alterados e `git diff --check` também passaram.

**Limite da validação:** a captura inline foi inspecionada visualmente;
seu arquivo binário não estava acessível para rodar Tesseract neste
ambiente. Portanto a legibilidade real do cabeçalho por OCR não foi
confirmada aqui. Os testes de lógica e OCR sintético não substituem a
próxima rodada no Windows com o Domínio real. Nenhuma imagem, nome ou
conteúdo fiscal é enviado a serviço externo para essa leitura.

---

### 0.65 Diagnóstico da validação de período no PDF exportado

**Evidência real (06/10/2026):** após exportar para um UUID exclusivo,
a rodada retornou `Exportação não confirmada: O cabeçalho do PDF não
confirma o período solicitado.` Isso confirma leitura do PDF e encontro
do título, mas não permite concluir se as datas estão erradas, se o
separador difere, ou se a ordem de extração colocou as datas fora do
recorte do cabeçalho. O nome temporário ficou porque a validação não
chegou à finalização; não é por si só falha do OCR do nome.

**Diagnóstico sem mudar a automação:** `Diagnosticar PDF.bat` executa
`scripts/diagnosticar_pdf.py` no PDF `exportacao_*.pdf` mais recente de
`saida/`. Padrão inicial: Registro de Saídas, 01/08/2026 a 31/08/2026
(mesma rodada informada). CLI aceita arquivo explícito, `--inicio`,
`--fim` e `--tipo entradas|saidas`. Só lê o arquivo; não renomeia nem
opera sobre o Domínio. Compara extração padrão e layout da primeira
página e imprime posições de marcadores/datas esperadas e resultados
de correspondência na página versus cabeçalho. Não imprime nome de
empresa, CNPJ, valores ou texto do PDF.

**Validação:** execução sobre PDF sintético real passou nas duas
extrações; cenário com datas após limite do cabeçalho identificado como
página=True/cabeçalho=False; verificado que nome/CNPJ/valor sintéticos
não aparecem no resumo. Compilação e diff check passaram. A correção da
validação aguarda o resumo da execução local do usuário; não foi feita
uma alteração baseada em hipótese nem desabilitada a conferência.

**Objetivo esclarecido:** o usuário quer o RPA, não um OCR de documentos.
Depois da estabilização desta confirmação de resultado, o próximo passo
é acompanhar uma rotina por estados, com verificação após cada ação,
e depois ampliar recuperação e lote; OCR é a percepção desse fluxo.

---

### 0.66 Competência do nome sempre pelas datas informadas na interface

**Definição do usuário:** o nome deve usar mês/ano do período digitado
na máquina, independentemente do mês mostrado no cabeçalho do Domínio.
`nome_livro()` agora usa `YYYY-MM` para todo intervalo no mesmo mês,
inclusive parcial, e `YYYY-MM_a_YYYY-MM` quando atravessa meses. Esse
formato substitui os dias completos no nome descritos na seção 0.63.
Preservadas datas completas na conferência do conteúdo, nome da empresa
por OCR e proteção dos arquivos anteriores. O diagnóstico da falha
real de validação de período (seção 0.65) continua pendente: mudar o
formato do nome não altera o conteúdo exportado nem resolve esse erro.

Validação: 13 testes passaram, cobrindo mês completo/parcial, intervalo
entre meses e virada de ano; compilação e diff check passaram. O novo
formato foi testado localmente; nenhuma nova rodada real foi afirmada.

---

### 0.67 Acompanhamento dos Livros Fiscais por etapas

**Direção do usuário:** deixar o nome do PDF pendente e seguir o plano
do projeto rumo a um RPA capaz de aprender rotinas e usar agentes de IA
como operadores. Esse incremento continua o núcleo da seção 0.62; não
introduz autonomia de IA nem muda a geração/leitura autorizada.
O caminho de evolução está em `docs/ROADMAP-RPA.md`.

**Mudança:** `AcompanhamentoRotina`, em `app/estados.py`, exige sequência
de etapas e evidência antes de avançar. A execução compartilhada dos
Livros Fiscais registra validar dados, identificar empresa, abrir Livros
Fiscais, conferir campos do período, reconhecer prévia, exportar PDF,
conferir PDF e enviar fechamento. Evidências são marcadores fixos locais,
sem nome, CNPJ, período fiscal ou caminhos do cliente nos novos eventos.
Identificar nome/código não equivale a comprovar uma empresa esperada;
enviar Esc não equivale a comprovar que a tela fechou. O log distingue
essa última ação de uma confirmação de estado observado.

Há linhas `[estado]` na saída e JSON Lines em
`data/execucoes/<execution_id>.jsonl`, com execução, tentativa, etapa,
estado, tempo e marcador de evidência. Toda saída falsa registra a
etapa de falha; exceções são registradas e propagadas. Uma nova tentativa
mantém a execução e reinicia a sequência sem reutilizar confirmações.
Falha de gravação do log avisa no console e não impede a automação.

A navegação, cliques, rotinas de recuperação, retorno `(bool, caminho)`
e conferência do PDF permanecem iguais. A falha real de período da
seção 0.65 e o nome solicitado não foram alterados. Se ela reaparecer,
o acompanhamento deve registrar falha em `conferir_pdf`, sem sucesso
para etapas posteriores.

**Validação:** 23 testes passaram (13 existentes e 10 de sequência,
evidência, registro, retry e integração simulada). Compilação e diff
check passaram. **Ainda não validado contra o Domínio real.** O teste
Windows deve usar competência já apurada e conferir as linhas de estado,
inclusive no caminho de falha conhecido, sem interagir com mouse/teclado.

**Rodada real recebida em 06/10/2026:** o log confirmou `validar_dados`,
`identificar_empresa`, `abrir_livros`, `preencher_periodo`, `gerar_previa`
e `exportar_pdf`. O OCR do nome/código no canto superior direito foi
observado nessa execução. `conferir_pdf` começou e retornou a falha
conhecida de período; o fim foi registrado como falha, sem evento de
encerramento ou sucesso. Isso valida a instrumentação do caminho de
falha nesta rotina; não confirma o sucesso final da exportação/conteúdo.

---

### 0.68 Saída de falha após prévia reconhecida

**Evidência:** na rodada da seção 0.67, a prévia foi reconhecida e o
arquivo novo estabilizou, mas a conferência recusou o período. A execução
terminou sem passar por `encerrar`; portanto nenhuma ação de fechamento
foi enviada pelo motor nesse caminho. O erro do PDF e o nome continuam
pendentes, por decisão do usuário. Este incremento segue o plano de
recuperação sem alterar essas regras.

**Mudança:** quando uma execução falha após reconhecer a prévia na
tentativa atual, registra uma tentativa separada de recuperação e envia
as duas teclas Esc já usadas no caminho existente de sucesso. Não altera
a etapa principal que falhou nem transforma falha em sucesso. O registro
distingue início, envio da ação e resultado não verificado; não afirma
que a tela fechou. Antes de reconhecer a prévia não envia teclas, e não
repete o fechamento quando a própria etapa de encerramento já começou.
Nova tentativa não reutiliza confirmação de uma prévia anterior.

Falha no envio de Esc é registrada como inconclusiva, preservando o
resultado/exceção original. Interrupção explícita por teclado não
provoca uma nova ação automática. O usuário deve conferir a tela antes
de iniciar a próxima rotina; retomada automática só será adequada depois
de existir uma verificação confiável do estado de retorno.

**Validação:** 29 testes locais e simulados passaram, incluindo os
caminhos de recuperação acima. Compilação e diff check passaram.
**O novo comportamento ainda não foi validado no Domínio real.** Nenhuma nova coordenada de clique,
interpretação de período ou ação fiscal foi introduzida.

**Rodada real recebida em 06/10/2026:** após a mesma falha de período,
o log registrou `recuperar_interface` com início, `acao_executada`
(`recuperacao_esc_enviado`) e `resultado_nao_verificado`. A etapa
`conferir_pdf` e o fim permaneceram como falha. Está confirmado o envio
da recuperação nesse caminho e a preservação do resultado; o log não
comprova que a prévia fechou. A confirmação visual do usuário continua
necessária antes de declarar retorno à interface.

**Confirmação visual do usuário:** a prévia continuou aberta após essa
rodada. Portanto Esc foi enviado, mas não fechou a janela do relatório;
o retorno à interface falhou nesse caso. Não está comprovada a causa
(foco, tratamento da tecla ou comportamento do visualizador). Não foi
introduzida outra tecla/posição de fechamento por hipótese. O próximo
dado necessário é captura da janela com a prévia aberta e os controles
visíveis, para identificar o fechamento da janela interna do relatório
sem confundi-lo com o fechamento do aplicativo Domínio.

### 0.69 Leitor PDF em primeiro plano após exportação

**Evidência recebida em 06/10/2026:** o usuário repetiu a rodada e
enviou uma captura do Adobe Acrobat maximizado com o PDF temporário
exportado. O leitor ficou em primeiro plano após salvar. O envio anterior
de Esc não registrava a janela destinatária; a captura explica por que
não era seguro presumir que a tecla chegaria ao Domínio. Ela não
comprova o destino exato de cada tecla na rodada anterior.

**Causa no código:** o encerramento e a recuperação enviavam Esc sem
conferir o foco. O foco inicial legado clica no centro da tela; repetir
esse clique com o Acrobat por cima também não traria o Domínio de volta.

**Correção:** associar a janela ativa à prévia reconhecida por OCR na
tentativa atual e guardar sua identidade apenas em memória. Após
exportar, retomar essa janela e conferir o foco antes de cada Esc. HWND
e PID usam tipos Win32 explícitos; nenhuma árvore de controles do
Domínio é inspecionada. A classe `DisplayClientWindowClass` sozinha
nunca serve para buscar uma janela, pois a seção 0.5 já provou que não
é exclusiva. Sem vínculo confiável, só um título inequívoco e único do
Domínio pode servir de alternativa. Quando o cliente não fornece título
útil, o foco também exige OCR do cabeçalho conhecido: `Domínio` e
`Escrita Fiscal`, no recorte superior e com escala 2, com até três
checagens por tecla. Identidade inválida, ambiguidade ou foco não
confirmado interrompem o envio e deixam a tentativa inconclusiva.

A identidade é descartada em nova tentativa e não aparece no JSONL;
o marcador de falha é `foco_dominio_nao_confirmado`. Se o PDF já foi
conferido e apenas o encerramento ficar pendente, o retorno preserva
seu caminho com resultado falso. A interface mantém esse arquivo no
histórico, e os scripts individuais distinguem esse caso de uma geração
não concluída. A recuperação preserva o erro original do PDF.

O Adobe pode permanecer instalado e aberto. As duas teclas Esc
existentes são mantidas, sem coordenada nova de fechamento. O envio
de Esc sozinho não comprova retorno à tela principal; o motor ainda
exige conferência visual humana. A conferência de período e a renomeação
continuam pendentes, conforme decisão anterior do usuário.

**Validação local:** 46 testes passaram, incluindo foco no leitor,
troca de foco recusada, janelas ambíguas, título/classe/PID alterados,
OCR não confirmado e perda de foco entre teclas. O fluxo simulado
preserva a falha original e o arquivo já conferido. Compilação e
checagem de diff passaram, preservando CRLF em `interacao.py`.

**Validação real recebida em 06/10/2026:** a rodada Windows seguinte
registrou `Foco do Domínio confirmado; enviando Esc.`, seguida de
`recuperacao_esc_enviado` e `resultado_nao_verificado`. A etapa
`conferir_pdf` e o fim permaneceram como falha. Ao perguntar se houve
retorno à tela principal, o usuário confirmou: "voltou certinho".
Assim, a recuperação funcionou nessa rodada, com confirmação humana do
estado final. Isso não confirma o conteúdo do PDF, cujo erro continua
pendente.

**Próximo incremento da recuperação:** o motor ainda não detecta esse
retorno automaticamente. Cabeçalho, menus, empresa e usuário aparecem
também na prévia/diálogos; não servem isoladamente como marcador de
tela principal. Ausência de `REGISTRO` no OCR e mudança de fingerprint
também não comprovam fechamento. Antes de medir uma referência visual
positiva, falta a captura como arquivo da tela principal que acabou de
ser confirmada, sem relatório, diálogo ou menu aberto. Não foram
inventados recorte, limiar ou novo clique a partir dessa confirmação.

---

### 0.70 Referência local para conferir retorno à tela principal

**Evidência e direção:** após a recuperação da seção 0.69, o usuário
confirmou o retorno e enviou a tela principal azul. A imagem foi vista
na conversa, mas não estava disponível como arquivo binário para medir
pixels nesta máquina. O usuário autorizou continuar trabalho e publicar
enquanto estivesse ausente. Não foram extraídos RGB/coordenadas por
estimativa visual nem declarados testes reais sobre essa imagem.

**Implementação:** `app/tela_principal.py` mede a cor azul dominante e
o maior retângulo uniforme da captura feita localmente. Os mínimos
relativos (90% de largura, 70% de altura e 65% de área) são critérios
preliminares conservadores, sujeitos ao teste Windows; não coordenadas
inventadas de um controle. `Calibrar Tela Principal.bat` exige que o
operador confira a tela principal maximizada e vazia; depois verifica
janela em foco, cabeçalho e estabilidade entre duas capturas. Aguarda
o operador selecionar o Domínio por Alt+Tab, sem clique/tecla remota.

Somente versão, tamanho, retângulo e RGB ficam em
`data/tela_principal.json` (ignorado no Git); não imagem ou empresa.
Gravação é atômica e uma calibração recusada preserva a referência
anterior. A comparação examina todos os pixels do retângulo, na mesma
resolução. Referência corrompida/incompatível não serve como ausência
de calibração. Um pixel diferente recusa a correspondência.

**Integração:** depois do Esc já existente, exige foco/cabeçalho e duas
capturas consecutivas compatíveis antes de registrar retorno confirmado.
Falha do PDF permanece falha mesmo se a recuperação funcionar. Sem
referência, mantém aviso/resultado não verificado; referência existente
divergente torna o encerramento inconclusivo. Nenhuma ação nova de
fechamento foi acrescentada. A identidade Win32 continua externa;
nenhuma árvore de controles internos do GO-Global é usada.

**Limite:** a correspondência comprova apenas o retângulo calibrado,
com foco e cabeçalho; não prova ausência de toda janela possível fora
dele. Não habilita autonomia geral. Testes sintéticos cobrem superfície
de PDF, diálogo, área pequena/interrompida, pixel divergente, metadados
inválidos, perda de foco/cabeçalho e preservação de referência.
**Calibração/reconhecimento ainda não validados no Domínio real.**

### 0.71 Etapas SPED/Contribuições e resultado falso no histórico

**Implementação:** o wrapper `gerar_sped()` mantém assinatura e retorno,
reutilizando a navegação, campos, confirmações e recuperação existentes.
Registra navegar menu, preencher período, identificar formulário,
gerar documento e encerrar. Nova tentativa conserva a execução, mas
reinicia suas evidências. O aviso de geração confirma o mecanismo
observado na interface, não o conteúdo independente do arquivo fiscal.
Encerramento usa a referência da seção 0.70 quando disponível; sem ela,
continua como ação solicitada e resultado visual não verificado.

**Bug confirmado por inspeção:** o callback de SPED/Contribuições na GUI
descartava o booleano do gerador. `_normalizar_resultado(None, False)`
registrava sucesso, mesmo quando o gerador devolvia `False`. Agora o
callback devolve o booleano e só imprime conclusão da rotina se verdadeiro.
Testes observam callback, normalização e chamada do histórico para
sucesso, falha, exceção e cancelamento, sem construir janela Tk.

Regressões SPED cobrem período inválido, confirmação, aviso de erro,
retry e encerramento inconclusivo. Não foi alterada a conferência de
PDF nem afirmada nova geração real. **Etapas novas precisam de teste
Windows em SPED Fiscal e EFD Contribuições.**

### 0.72 Lote calibrado exige retorno antes de transições

**Implementação:** com referência local existente, conferir tela
principal antes/depois da troca de empresa e após cada gerador, mesmo
se ele devolveu `True` ou `False`. Estado desconhecido interrompe o
lote antes do próximo documento/F8. Exceções não provocam Esc/retry
genéricos em estado não confirmado. Referência inválida ou removida
durante a execução não rebaixa silenciosamente para o modo legado.
Resultados dos documentos já tentados são preservados no resumo,
inclusive diante de interrupção ou de um segundo erro inesperado.

**Entrada:** após confirmação por terminal, o console pode estar em
primeiro plano. Uma espera inicial limitada permite o operador voltar
ao Domínio; somente o próprio console/GUI é minimizado, sem clique
central ou Esc remoto. A GUI minimiza na thread principal ao aceitar
o lote. Após a entrada, transições não aguardam uma nova intervenção
para presumir recuperação. Sem referência desde o início, preserva o
fluxo supervisionado anterior e avisa uma vez.

Testes simulam duas empresas/documentos, retorno reconhecido após
falha isolada, retorno desconhecido após sucesso/falha, referência
inválida/removida, exceções, resumo e entrada com foco inicial fora do
Domínio. **Lote calibrado ainda precisa de teste supervisionado Windows.**

### 0.73 Catálogo preparatório e orientação Hugging Face

`app/capacidades.py` descreve as quatro rotinas, assinaturas reais,
pré-condições, resultados, validações históricas e pendências atuais.
`Listar Funcoes.bat` somente consulta metadados. Todas permanecem
preparatórias e agentes desabilitados: isso não cria um executor nem
conclui o incremento 3 do roadmap. Testes conferem assinatura sem
importar o desktop, imutabilidade, IDs e consulta sem acesso a dados.

**Nova direção do usuário em 07/10/2026:** usar Hugging Face como fonte
de componentes para robustecer o projeto atual, preservando SPED e
evitando um laboratório/produto separado. O prompt reutilizável está em
`docs/PROMPT-DESENVOLVIMENTO-HUGGING-FACE.md`; fontes oficiais em
`docs/HUGGING-FACE-COMPONENTES.md`. Foram confirmados PP-OCRv5 latino
com português documentado e PaddleOCR-VL-1.6 oficial. Layout de documento
não comprova localizar controle GUI; benchmark público não comprova
qualidade no Domínio. Modelos serão locais, sem upload de telas/dados.

Tesseract/OCR do Windows/OpenCV continuam no motor. UI Automation dos
controles internos permanece indisponível no GO-Global. VL/layout só
serão avaliados diante de dificuldade concreta. A conferência de
período/nome do PDF segue pausada. O prompt exige comparação local,
regressão SPED e confirmação Windows antes de promover outro backend.

### 0.74 Instalador e avaliação PaddleOCR opcionais

**Pedido:** o usuário perguntou se as ferramentas poderiam vir pelo
Git para instalar ao atualizar. A primeira instalação ocorre por
`Instalar OCR Paddle.bat`; usa CPU em `.venv-ocr-paddle`, no mesmo
projeto, preservando as dependências da automação. Combinação declarada:
PaddleOCR/PaddleX 3.7.0, PaddlePaddle 3.3.1 e Hugging Face Hub 2.1.1;
Windows AMD64, CPython 3.10–3.13. Só dois modelos (detector móvel e
reconhecedor latino) são baixados do Hugging Face, com revisões fixadas
e allowlist de arquivos de inferência. Download incompleto não publica
revisão nova nem combina arquivos antigos; preparação ocorre em pasta
temporária antes de promover o diretório.

Depois da primeira instalação, o marcador local permite `Atualizar.bat`
manter as dependências/modelos opcionais. Sem marcador, não instala
Paddle. O atualizador para se Git/dependências falharem. `Avaliar OCR
Paddle.bat` escolhe uma captura local e compara com Tesseract sem operar
o Domínio. O backend é preguiçoso, reutiliza processador, valida texto,
confiança e caixas, e não participa do fluxo de produção. O resumo não
exporta texto reconhecido; medidas de tempo/contagem não comprovam
precisão nem uma localização correta por si só.

**Validação:** resolução de dependências com pip `--dry-run`, alvo
Windows AMD64/CPython 3.12 e wheels passou; nenhum pacote foi instalado
nessa verificação. Testes simulados cobrem instalação, download e
contratos do backend/avaliação. **Instalação, inferência e desempenho
nas telas reais do Domínio ainda não foram medidos.** Tesseract continua
como padrão; PaddleOCR-VL não foi instalado.

**Verificação real de API adicional em Linux/CPU:** os pacotes e os dois
pesos foram instalados/baixados em ambiente isolado, e foi usada uma
imagem sintética, sem cliente. A primeira inferência reproduziu erro
`ConvertPirAttribute2RuntimeAttribute` no executor OneDNN. A opção
`enable_mkldnn=False`, suportada na API instalada, resolveu o cenário;
o backend aplica essa configuração CPU. Três leituras devolveram três
segmentos, alvo sintético presente e caixas válidas, com processador
reutilizado e `socket.connect` bloqueado no Python. Cache de download
padrão foi direcionado aos dados locais, preservando configuração de
cache explícita do operador. Não é benchmark Domínio nem teste Windows.

**Validação consolidada da entrega (07/10/2026):** 146 testes locais e
simulados passaram, abrangendo rotinas, foco, referência, GUI, lote,
catálogo, instalador, downloader e avaliação opcional. Compilação de
22 arquivos Python alterados e checagem de diff passaram. Nenhuma
nova execução Domínio/Paddle no Windows foi afirmada; continuam os
testes operacionais e as pendências descritas em `docs/RETOMADA.md`.

---

### 0.75 Instalador Windows iniciado com Python 3.14.7

**Evidência recebida em 07/10/2026:** ao executar `Instalar OCR Paddle.bat`,
o usuário recebeu a recusa de compatibilidade. O diagnóstico confirmou
Python **3.14.7, 64 bits, AMD64**. A arquitetura atende; a versão está
fora da faixa dos wheels Windows do PaddlePaddle 3.3.1 (até CPython 3.13).
O instalador recusou antes de criar ambiente ou instalar pacotes.

**Causa no código:** o atalho iniciava o script com `python` do PATH,
e o script só avaliava esse intérprete. A mensagem não indicava o
requisito específico nem aproveitava outro Python já instalado.

**Correção:** mostrar versão, implementação, bits, sistema e arquitetura;
reutilizar o intérprete compatível do ambiente OCR quando disponível, ou
enumerar instalações pelo launcher `py -0p`. Cada executável candidato
é verificado por subprocesso isolado de stdlib, com timeout e formato
JSON validado. Prefere 3.12, depois 3.13/3.11/3.10; exige CPython x64.
O instalador reinicia explicitamente no candidato aprovado, propagando
seu resultado sem alterar PATH ou o ambiente do SPED. A listagem não
dispara instalação automática de outro Python.

Se não houver candidato, explica o pré-requisito: instalar 3.12/3.13
de 64 bits lado a lado e repetir o atalho. O motor original continua
com seu Python existente. Testes simulam default 3.14, candidato 3.12,
venv existente, saída inválida, bitness/implementação erradas, falha,
timeout, ausência de launcher e propagação de resultado sem reinício
em loop. **Seleção/instalação ainda precisam de repetição no Windows.**

Validação: 155 testes locais/simulados passaram (nove novos de seleção
do intérprete), compilação e diff check passaram.

---

### 0.76 Pré-requisito Python instalado lado a lado

**Evidência recebida em 07/10/2026:** a repetição do instalador mostrou
Python 3.14.7 CPython x64 e não encontrou outra versão compatível. O
próximo passo é instalar um intérprete compatível para o OCR opcional.

`Instalar Python OCR.bat` chama a opção explícita `--instalar-python` do
bootstrap. Se já houver Python compatível, reutiliza-o; senão solicita
ao winget `Python.Python.3.13`, arquitetura x64, escopo usuário, fonte
winget. Os argumentos do instalador oficial preservam PATH, launcher e
associações. Não desinstala Python 3.14 nem altera dependências do SPED.
O manifesto oficial do winget e a fonte do launcher CPython 3.13 foram
consultados para conferir identificador, arquitetura e listagem.

A descoberta passa a consultar também os diretórios padrão de instalação
por usuário em LOCALAPPDATA, para localizar Python sem launcher. Um
arquivo existente só é aceito após a sonda stdlib confirmar versão,
implementação, arquitetura e bits. Falha do winget ou ausência de Python
confirmado interrompe antes de instalar OCR; ausência de winget indica
o site oficial para instalação manual. O instalador OCR normal continua
sem instalar um Python novo automaticamente.

Validação: **163 testes locais/simulados passaram**, com oito novos casos
de descoberta sem launcher, instalação explícita, preservação de ambiente
e interrupção após falha. Compilação e diff check passaram. **Não foi
executado winget nem instalador Python no Windows pela nuvem; o atalho
precisa ser executado pelo operador.**

---

### 0.77 Progresso OCR, captura atual e reutilização nas decisões de estado

**Evidência recebida em 07/10/2026:** avaliação de imagem aleatória chegou
a anunciar leituras em CPU e mostrou mensagem do Windows de arquivo não
encontrado. Depois foi enviada a mensagem genérica de interrupção, seguida
de pergunta S/N para finalizar o lote. Não há inferência concluída no
Windows. A pergunta é compatível com interrupção pelo teclado.

**Diagnóstico:** a fonte instalada de PaddlePaddle 3.3.1,
`paddle/utils/cpp_extension/extension_utils.py`, procura `ccache` opcional
com `subprocess.check_output(['where', 'ccache'])` no Windows, sem suprimir
stderr. O aviso pode aparecer mesmo durante importação válida; não prova
problema de Tesseract. Antes o avaliador só imprimia agregados depois das
seis leituras, dificultando distinguir carregamento de travamento.

**Entrega:** progresso imediato com motor, leitura 1–3, duração e quantidade
de segmentos; Ctrl+C explícito com código 130 e código de saída no atalho.
`Avaliar OCR Tela.bat`/`--tela` capturam a janela atual do Domínio/cliente
GO-Global em memória, depois que o operador seleciona a janela. Consulta
Win32 somente para identidade/retângulo/foco; nenhum controle interno de
GO-Global é inspecionado. Exige identidade estável antes/depois da captura,
com espera limitada, e pede conferência humana do conteúdo do cliente sem
título. Não envia ações, salva imagem ou modifica rotina fiscal.

**Otimização de produção:** a inspeção de `esperar_e_achar` mostrou que cada
título pode repetir OCR da mesma tela e do mesmo recorte central. Agora
`esperar_por_estado` abre um escopo de reutilização em `tela.reutilizar_ocr`.
Chave por pixels exatos, tamanho, modo e escala; ContextVar separa execuções,
limpeza obrigatória ao sair; máximo oito resultados no escopo. Imagens
indexadas incluem cores da paleta na chave. Só chamadas `achar_texto` com
a mesma configuração Tesseract participam. Mantém precedência, coordenadas,
fallback central, espera mínima, tentativas e resultado de sucesso/erro.
Não troca OCR nem introduz decisão de IA nova.

Uma medição adicional Tesseract CPU/Linux sobre a mesma imagem sintética,
com seis títulos ausentes e as duas regiões, reduziu **12 chamadas para
2**, de **2,186s para 0,386s** nesta execução, preservando todas as buscas
sem posição encontrada. Não mede espera/geração do Domínio nem ganho Windows.

**Validação:** 179 testes passaram (16 novos de progresso, captura, reuso
e decisões), compilação e diff check passaram. Sucesso, erro, esgotamento,
regiões/escalas/pixels distintos, exceção, nova tentativa e isolamento de
thread foram verificados. A comparação sintética CPU/Linux completou
Paddle 5,116s na primeira leitura e 1,136/1,529s nas aquecidas; Tesseract
0,432s e 0,389/0,252s. Esses números não medem telas Domínio/Windows nem
justificam adotar Paddle como padrão. Captura atual e rotinas otimizadas
**ainda precisam de teste real no Windows**.

---

### 0.78 Primeira comparação de inferência OCR concluída no Windows

**Log real recebido em 07/10/2026:** `Avaliar OCR Tela.bat` anunciou captura
em memória da janela identificada como Domínio/GO-Global e completou uma
leitura inicial e duas aquecidas por motor. O operador enviou somente o
resumo agregado, sem texto reconhecido ou captura.

| Motor CPU | Inicial | Aquecida 1 | Aquecida 2 | Segmentos |
| --- | --- | --- | --- | --- |
| PP-OCRv5 mobile | 24,751s | 14,309s | 15,802s | 32 / 32 / 32 |
| Tesseract por | 0,935s | 0,623s | 0,576s | 35 / 35 / 35 |

Médias aquecidas: 15,0555s Paddle e 0,5995s Tesseract, razão 25,11.
A mensagem Windows de busca de arquivo também apareceu, mas a primeira
leitura concluiu: ela não comprova uma falha de OCR. A origem provável
continua sendo `where ccache` descrito na seção anterior.

**Decisão:** manter Tesseract no fluxo atual. Não promover Paddle como
padrão nem instalar outro modelo agora: a primeira evidência local mostra
perda de tempo, sem evidência de ganho de precisão. Paddle permanece
opcional para comparar telas problemáticas no futuro. A otimização de
reutilização de OCR por estado da seção 0.77 permanece em produção e
precisa de revalidação real de SPED/Contribuições.

**Limites:** uma captura, sem alvo de texto ou verdade de referência;
32 versus 35 segmentos não compara precisão. Não foram enviados dados
de RAM, CPU específico, coordenadas críticas ou versão do intérprete.
GPU/VRAM não foram usadas. Isso confirma inferência CPU local nesse teste,
não estabilidade prolongada, ganho geral ou rotina fiscal com Paddle.

Próximo passo operacional: calibrar a tela principal humana confirmada,
executar SPED Fiscal individualmente em competência já fechada e conferir
as etapas, documento gerado e retorno. Nenhuma mudança de código nesta
entrada; conferência documental e diff check, sem repetir testes que já
passaram no commit anterior.

---

### 0.79 Painel visual, catálogo e acompanhamento do projeto

**Pedido em 07/10/2026:** preparar o que falta para seguir até o RPA
completo, incluindo o visual. Continua a interface Tk/ttkbootstrap do
mesmo projeto, sem produto separado, instalação de modelos adicionais
ou reescrita das rotinas conhecidas.

**Entrega:** abas Painel, Rotinas (com rolagem), Funções disponíveis,
Histórico, Projeto e Log. O catálogo mostra pré-condições, período,
checagens e pendências das quatro rotinas. Projeto mostra os seis
incrementos e reúne calibração, comparação OCR e instruções de retomada.
Mantém modo Operador, callbacks existentes e minimização antes da rotina.
O texto de confirmação SPED explicita que mês anterior exige apuração
fechada, em vez de afirmar que o fechamento ocorre automaticamente.

`estados.observar_eventos` usa ContextVar para encaminhar cópias dos
eventos já existentes à fila da GUI, sem parsear logs livres ou enviar
dados fiscais. Falha do observador não muda a execução nem o JSONL.
`app/painel.py` só apresenta estados: conhece etapas/status/rotinas,
limpa confirmações na nova execução/tentativa, distingue ação enviada
de retorno visual e preserva falha depois de recuperação confirmada.
Widgets são atualizados na thread Tk, nunca no callback de automação.
O indicador conta somente etapas confirmadas; não representa autonomia
do projeto, validação de conteúdo ou simples cliques executados.

Ferramentas abrem em um Prompt separado, com intérprete atual para
calibração ou ambiente OCR existente para comparação. O wrapper aceita
somente esses dois IDs, conserva o código de saída e aguarda Enter para
permitir leitura do resultado. Ferramenta aberta bloqueia nova automação;
sem ambiente OCR, indica instalação em vez de instalar automaticamente.
`False` retornado por gerador também aparece como falha no status da GUI,
preservando seu histórico. Lote sem resultado único pede consulta ao log.

**Validação:** 196 testes locais/simulados passaram, com 17 novos de
observador, estados apresentados, retry, retorno, falha, preservação de
código, fila da GUI e impedimento de nova rotina durante ferramenta.
Compilação e diff check passaram. Interface real renderizada em Xvfb
Linux local em 1120×780 e 900×640, sem backend fiscal; prévia usa eventos
simulados. A renderização identificou incompatibilidade de ScrolledFrame
diretamente no Notebook; corrigida com frame pai e revalidada. A captura
`docs/preview-painel.png` contém apenas esse cenário simulado.

O ciclo Tk real com uma thread Python e estados simulados encontrou
travamento da finalização por `root.after` chamado da thread de trabalho.
Finalização e confirmação de lote passaram para a fila consumida pela
thread Tk. O ciclo voltou a terminar, com falha corretamente exibida e
histórico preservado; diálogos e minimização foram simulados por não haver
gerenciador de janelas Windows no Xvfb. Erro de gravação de histórico não
perde finalização/resultado. Nenhuma ação fiscal foi executada no teste.

**Ainda pendente:** teste visual/execução no Windows, calibração e
retorno das rotinas, conteúdo gerado, lote com falha isolada, pendência
PDF anteriormente pausada. Catálogo executável, aprendizagem por
demonstração e agentes operadores seguem os incrementos posteriores;
o painel não os apresenta como concluídos nem os habilita.

---

### 0.80 Primeira calibração da tela principal concluída no Windows

**Evidência do operador em 07/10/2026:** a ferramenta informou
`Referência local salva em data/tela_principal.json`, tamanho da captura
`[1440, 900]`, área azul `[0, 128, 1377, 823]` e código de saída 0.
O Prompt permaneceu aberto até Enter, conforme o wrapper da aba Projeto.

Isso confirma a execução da calibração e a gravação dos metadados locais.
Nenhuma captura nem referência do operador foi copiada para o Git;
este checkpoint registra somente as medidas relatadas. As coordenadas
medidas não viraram posições fixas de cliques ou recortes no código.

**Próximo teste:** SPED Fiscal individual na empresa correta. O gerador
seleciona o mês anterior à data do computador; o operador precisa
confirmar que sua apuração está fechada. Conferir documento gerado,
etapas no Painel, `encerrar: confirmado (tela_principal_reconhecida)`
e resultado `fim` no log, além do retorno visual à tela principal.

**Ainda pendente:** comparação de retorno após geração, revalidação
SPED/Contribuições, isolamento de falha no lote e demais incrementos.
Calibrar uma tela não comprova a execução fiscal nem a robustez contra
todas as janelas sobrepostas. Pendência de período/nome PDF permanece
pausada. Nenhuma alteração de código ou dependências; conferência de
documentação e diff check, sem repetir a suíte de 196 testes do commit
anterior.

---

### 0.81 Gravador: digitação, hover marcado e espera por fingerprint (fecha as 3 lacunas do incremento 4 do roadmap)

Pedido do usuário: terminar o gravador de cliques (`scripts/gravar.py`)
pra ficar funcional, não só rascunho que precisa reescrever quase tudo
à mão. O roadmap (seção 2, "ponto de partida") já apontava exatamente
3 lacunas: "o gravador ainda exige revisão e complementação de
digitação, hover e verificações" — as 3 fechadas nesta entrada.

**1. Digitação real.** O listener de teclado agora acumula caractere
por caractere entre um clique e outro (`KeyCode.char`), e fecha o
acumulado num passo `digitar` sempre que outro tipo de passo começa
(clique, hover, tecla especial, ou F12). Enter/Tab/Esc viram passos
`tecla` próprios (`interacao.pressionar_enter()`/`pressionar_tecla()`),
não ficam misturados no texto digitado.

**Risco de privacidade documentado, não escondido**: o listener de
teclado do `pynput` é global — grava QUALQUER tecla digitada em
QUALQUER janela enquanto a gravação está ativa, não só dentro do
Domínio (mesma limitação técnica do listener de mouse já existente,
agora mais sensível porque captura texto, não só posição). Aviso
explícito no início da gravação e no docstring: pausar (F12) antes de
digitar senha/dado sensível fora do Domínio. Fica só local
(`capturas/gravacao_*/passos.json`, já gitignored) — mas o rascunho
também avisa, por passo, que texto digitado literal (ex.: código de
empresa) geralmente deveria virar parâmetro da função, não ficar fixo.

**2. Hover marcado manualmente, não inferido.** Tecla **F9** marca a
posição atual do mouse como um passo `hover`
(`interacao.passar_mouse()`), sem clicar — decisão deliberada de não
tentar adivinhar hover por pausa do mouse (confiabilidade duvidosa,
mesmo princípio de "nunca inventar" do resto do projeto); marcação
explícita é inequívoca.

**3. Espera por estado em vez de `time.sleep(2)` fixo.** Cada passo de
clique no rascunho gerado agora espera a tela mudar de verdade
(`tela.assinatura_tela()`/`tela.tela_mudou()`, mesmo fingerprint da
seção 0.58) antes de seguir pro próximo passo, em vez de um tempo fixo
— genérico de propósito (o gravador não sabe o que esperar
especificamente depois de cada clique); o docstring do rascunho deixa
claro que trocar por `estados.esperar_por_estado()` mirando um texto
conhecido continua sendo o ideal ao revisar.

**Compatibilidade**: gravação antiga (sem campo `"tipo"` no JSON, de
antes desta seção) continua gerando rascunho igual a antes — o gerador
trata a ausência de `"tipo"` como `"clicar"`.

**Validado por teste de lógica real** (não só sintaxe — `pynput` está
disponível neste ambiente, ao contrário de `pyautogui`/`pytesseract`):
simulei uma gravação completa (digitar código → Enter → clicar →
F9/hover → digitar outro valor → Tab → F12) com teclas reais do
`pynput.keyboard.KeyCode`, conferi a ordem e o conteúdo exato dos 6
passos gravados, gerei o rascunho e **compilei ele de verdade**
(`py_compile`), conferindo que `interacao.digitar()`,
`interacao.passar_mouse()`, `interacao.pressionar_enter()`,
`interacao.pressionar_tecla('tab')` e `tela.tela_mudou()` aparecem
certos e que `time.sleep(2)` fixo sumiu. Suíte completa (196 testes)
continua passando. **Ainda não usado pra gravar uma automação nova de
verdade contra o Domínio real** — a próxima vez que alguém gravar uma
rotina nova é o teste de fato.

---

### 0.82 Rotina gravada ganha ciclo de vida (rascunho → aprovada → lote), sem programador no meio

Pedido do usuário, na sequência do gravador (seção 0.81): hoje uma
gravação vira um RASCUNHO de Python que precisa de alguém programando
revisar, parametrizar e colar dentro de `app/dominio.py` — nada disso
é "fácil ao usuário". Pedido concreto: deixar excluir rotina, testar
antes de aprovar (podendo apontar correção), e só depois de validada
ela entrar na opção de lote (várias empresas) ou empresa única — com
troca de empresa automática entre uma e outra, do mesmo jeito que já
funciona pro SPED Fiscal.

**Novo módulo `app/rotina_gravada.py`** — executa os passos gravados
DIRETO do JSON (`scripts/gravar.py` já salva nesse formato), sem gerar
nem colar nenhum código Python novo:
- `executar_passos(passos, parametros, prefixo="")`: toca clique,
  digitar, hover e tecla na ordem gravada, reaproveitando
  `dominio.achar_ou_parar()` (mesma confiabilidade/catálogo de erro do
  resto do motor) pro clique e espera por fingerprint entre ações —
  mesmo princípio do rascunho gerado pelo gravador, só que direto.
- `salvar_rotina_gravada()`/`listar_rotinas_gravadas()`/
  `marcar_status()`/`excluir_rotina_gravada()`: catálogo local em
  `data/rotinas_gravadas/*.json` (gitignored, mesmo padrão de sempre).
- `criar_gerador(passos, parametros)`: embrulha `executar_passos()` no
  mesmo formato `(prefixo="") -> bool` que `dominio._GERADORES` já usa
  — é a peça que permite uma rotina aprovada entrar no motor de lote
  sem duplicar nada.

**Ciclo de vida**: toda rotina nasce `"status": "rascunho"`. Rodar uma
rascunho (sempre empresa única, sempre com confirmação de empresa
selecionada antes) pergunta, ao final, se o resultado no Domínio
estava correto DE VERDADE (não só "não travou") — só confirmando
explicitamente ela vira `"aprovada"`. Rascunho que falhou mostra aviso
pra corrigir (gravar de novo) ou excluir, continua rascunho. Isso é o
"testar antes de aprovar, podendo apontar correção" pedido.

**Excluir**: botão por rotina na interface, com confirmação, apaga o
JSON — os prints da gravação original continuam em `capturas/` caso
precise consultar depois.

**Lote reaproveitando o motor existente, não duplicado** — pedido
explícito: "quero que seja fluido e que ele entre naquele loop de
empresas em lote" + "com a troca de empresa como automático". Em vez
de escrever um segundo loop de empresas paralelo,
`dominio._processar_empresa()` e `dominio.executar_lote()` ganharam um
parâmetro opcional `documentos_personalizados` — uma lista
`[(nome, gerador)]` pra usar NO LUGAR de
`empresas.documentos_necessarios(e)` + `_GERADORES` quando informado.
`None` (padrão) preserva exatamente o comportamento de sempre do SPED
Fiscal/EFD Contribuições — confirmado por teste de lógica real, não só
leitura de código. Isso significa que uma rotina aprovada herda de
graça, sem reescrever nada: troca de empresa automática entre uma e
outra, recuperação (Esc + 1 retry), pausa, verificação de tela
principal calibrada, e isolamento de falha por empresa — toda a
robustez que o lote de SPED/EFD já tinha.

Só rotina `"aprovada"` ganha o botão "Em lote" na interface — rascunho
só roda empresa única, supervisionado, de propósito. Parâmetro (se
houver) é pedido uma vez só antes do lote começar e vale pra todas as
empresas dessa rodada — não há ainda valor diferente por empresa
dentro do mesmo lote (limitação conhecida, não endereçada agora).

**Validado por teste de lógica real** (não só sintaxe): ciclo completo
rascunho→aprovada, recusa de status inválido, `criar_gerador()`
chamando `executar_passos()` com os argumentos certos, exclusão
(inclusive excluir duas vezes sem quebrar), compatibilidade com
arquivo salvo antes do campo `status` existir (volta como rascunho,
nunca promove sozinho). E o ponto mais importante pra não quebrar o
que já funciona: `_processar_empresa()` testado COM e SEM
`documentos_personalizados`, confirmando que o caminho antigo
(SPED Fiscal/EFD Contribuições pela planilha) continua byte a byte
igual a antes quando o parâmetro novo não é usado. Suíte completa (196
testes) continua passando. **Ainda não usado de ponta a ponta contra o
Domínio real** — falta gravar, aprovar e rodar em lote uma rotina de
verdade pela primeira vez.

---

### 0.83 Registro de elementos: vocabulário que aprende sozinho, achado contra bug real (o "Element Registry" do briefing original, versão pequena e de verdade)

Contexto: ao investigar o palpite quebrado da seção 0.82
("Movimentos — Relatórios — Utilitários — Fax"), o usuário pediu
explicitamente pra eu não ficar corrigindo palpite ruim um por um pra
sempre — "gostaria que ele se auto arrumasse, realmente entendesse
quantas opções existem" — e sugeriu um banco de prints de todos os
menus. Isso é o `ElementRegistry` que o prompt original deste projeto
já previa (seção 16) e nunca tinha sido construído.

**Versão real construída, escopo deliberadamente menor que "banco de
prints de toda a aplicação"** (catalogar imagem de cada tela do
Domínio é trabalho grande, ninguém fez isso ainda): um vocabulário de
TEXTO já confirmado correto, em `app/registro_elementos.py`:

- **"DNA" inicial**: extraído por grep dos próprios alvos literais já
  usados com sucesso em `app/dominio.py` (SPED Fiscal, EFD
  Contribuições, Registro de Saídas/Entradas) — meses de uso real, não
  inventado.
- **Cresce sozinho, sem passo manual a mais**: toda vez que uma rotina
  gravada é marcada `"aprovada"` (seção 0.82 — já exige confirmação
  humana de que o clique funcionou certo), o texto de cada passo de
  clique dela entra automaticamente no vocabulário
  (`rotina_gravada.marcar_status()` chama
  `registro_elementos.registrar_confirmado()`). A aprovação JÁ ERA a
  confirmação — não inventei uma etapa nova pra isso acontecer.
- **`avaliar_palpite(texto)`**: confere um palpite novo contra o
  vocabulário — `"conhecido"` (bate com algo confirmado),
  `"parecido"` (contém um texto conhecido dentro, com sugestão — é
  exatamente o caso do bug do traço: o palpite concatenado "contém"
  o item de menu real), ou `"novo"` (nunca visto, não é
  necessariamente errado). Só informa — nunca decide nem corrige
  sozinho.
- **Tela de revisão mostra a avaliação por clique**: "✓ já conhecido",
  "parecido com 'Relatórios' — [usar]" (botão preenche a sugestão na
  hora) ou "novo (nunca confirmado)" — pedido do usuário atendido na
  prática: ela vê de cara qual palpite merece mais atenção, em vez de
  ter que abrir o print de cada passo pra desconfiar.

**Validado por teste de lógica real, inclusive contra o caso real que
motivou isso**: o palpite quebrado de verdade ("Movimentos —
Relatórios — Utilitários — Fax") foi testado direto contra
`avaliar_palpite()` e volta `"parecido"`, sugerindo "Relatórios" —
confirma que o sistema reconheceria esse erro específico sozinho.
Testado também: texto novo vira conhecido depois de
`registrar_confirmado()`, persistência em disco, e o fluxo completo
"salvar rotina → aprovar → vocabulário aprende sozinho" ponta a ponta.

**Limitação honesta**: isso é vocabulário de TEXTO, não visão —
continua sem ajudar em cliques de ÍCONE (passos 8/9/10 daquela mesma
rotina quebrada, sem texto nenhum pra comparar). Pra isso, o caminho já
existe mas é outro: `achar_icone_robusto()` (pixel+ORB) e visão por IA
como último recurso (seção 0.58/0.61) — ferramentas diferentes pra um
problema diferente (reconhecer imagem, não validar texto).

---

### 0.84 Interface web instalável e executor da sessão dedicada (08/10/2026)

**Pedido:** terminar o site no projeto existente, com usuário no navegador
ou app instalado no PC e Domínio numa sessão dedicada do servidor.
Lote deixou de ser prioridade. O servidor foi informado como disponível,
mas ainda sem Domínio configurado; não houve implantação real nele.

**Implementado:** `web/` contém interface responsiva/PWA, conexão por
chave, tarefas individuais, etapas/retorno e histórico. `app/api_servidor.py`
serve interface/API autenticada; `app/servidor.py` persiste tarefas e
eventos em SQLite e mantém um worker exclusivo. `app/executor_servidor.py`
reutiliza os quatro geradores existentes, sem reescrever navegação SPED.
Entrada `scripts/servidor.py`: consulta por padrão, simulação sem desktop
e execução real explicitamente habilitada em Windows.

O adaptador confere referência calibrada, tela principal/foco e código
da empresa já selecionada. Valida competência passada/apuração declarada;
SPED/Contribuições continuam usando mês anterior. Não troca empresa
automaticamente nem aceita código, caminhos ou ações livres do cliente.
Uma tarefa por vez; trava compartilhada com GUI/ferramentas na mesma
instalação. Identificador repetido não duplica tarefa. Reinício marca
ações inacabadas como interrompidas, sem repetir automaticamente.
Conclusão exige resultado positivo e retorno reconhecido; desconhecido,
falha e pré-condição recusada têm estados próprios.

Chave/banco/arquivos permanecem locais. API publica eventos estruturados,
sem OCR livre, captura ou caminho privado. Download autenticado exige
arquivo registrado dentro de `saida/`; SPED/Contribuições hoje devolvem
booleano, sem caminho para download. PWA armazena só interface estática,
nunca chave, tarefas ou documentos. Endereço externo exige HTTPS.
Há chave única do escritório; contas/permissões individuais continuam
pendentes. Gravações locais não entram no catálogo remoto automaticamente.

**Robustez da GUI:** histórico atomicamente gravado, leitura estrita
preserva arquivo corrompido, resultado sem confirmação não aparece como
OK; término libera interface mesmo após falha de histórico. Fechamento
ou abertura de arquivo durante ação é bloqueado para preservar execução
e foco. Foram integradas as mudanças Claude `ee64533`, `b209d71` e
`257e90b` (seções 0.81–0.83), preservando gravação/revisão/aprovação.
As novas chamadas `root.after` do worker foram substituídas pela fila
da GUI; revisão/aprovação só abrem depois de restaurar a janela.

**Validação:** 244 testes locais/simulados passaram, incluindo regressão
SPED, entradas de API, idempotência, concorrência, reinício sem repetição,
retorno/resultados, proteção de arquivo e ciclo GUI. Chromium exercitou
chave inválida, login, nova tarefa simulada identificada pelo próprio id,
etapas, conclusão, histórico, logout, modo offline e visual em
1440/900/390 pixels. Selecionar nova tarefa limpa o resultado anterior;
respostas atrasadas não reabrem a sessão desconectada. GUI foi renderizada
em Tk real com backend fiscal bloqueado; worker/retomada com eventos
simulados foram conferidos. Sintaxe/diff e dependências verificados.
Prévia `docs/preview-interface-conectada.png` usa somente dados simulados.

**Limites:** testes não operam Domínio/GO-Global nem validam instalação
Windows. Servidor real ainda precisa de Domínio, calibração própria,
endereço/HTTPS e teste individual de documento/estados/retorno. A falha
de período/nome PDF permanece pendente e pausada. Não foram instalados
novos modelos nem habilitados agentes gerais. Guia de instalação e
retomada em `docs/SERVIDOR-E-INTERFACE.md` e `docs/RETOMADA.md`.

---

### 0.85 Rotina gravada aprende a clicar em ÍCONE (não só texto) — fecha a lacuna dos passos 8/9/10 da rotina de teste quebrada

Depois da revisão cruzada com a sessão Codex (coordenação registrada no
`HANDOFF.md`), continuei na minha área (percepção/gravador/rotinas
gravadas) enquanto a outra sessão trabalhava em rede local/instaladores
— sem conflito, confirmado por `git diff --stat` nos dois lados antes
de começar.

**Lacuna real, já identificada antes** (seção 0.82, revisão da rotina
"TEste nova rotina ex"): passos 8, 9 e 10 daquela gravação eram cliques
em ÍCONE da barra de ferramentas — sem texto nenhum pra adivinhar, o
gravador só salvava `texto_adivinhado: ""`, e `rotina_gravada.
executar_passos()` desistia desses passos (`"não dá pra reproduzir com
segurança"`). O vocabulário de texto (seção 0.83) não ajuda aqui —
problema diferente (reconhecer imagem, não validar texto).

**Correção**: `scripts/gravar.py` — quando o texto adivinhado tem menos
de 2 caracteres (sem confiança nenhuma), salva TAMBÉM um recorte
pequeno ao redor do clique (mesma escala do ícone real já usado,
`app/icones/salvar_pdf.png`, 30×25px) como `template_icone` no passo.
`rotina_gravada.salvar_rotina_gravada()` ganhou `pasta_origem` — copia
esse recorte da pasta efêmera da gravação (`capturas/gravacao_*/`, sem
garantia de não ser limpa) pra uma pasta persistente dentro de
`data/rotinas_gravadas/<nome>_icones/`, salva junto com a própria
rotina. `rotina_gravada.executar_passos()` agora usa
`tela.achar_icone_robusto()` (pixel + característica, seção 0.58/0.61 —
mesma técnica já validada pro ícone de exportar PDF) quando o passo tem
`template_icone` e nenhum texto, em vez de `dominio.achar_ou_parar()`.
`excluir_rotina_gravada()` também limpa a pasta de ícones copiados.

Tela de revisão (`RevisarGravacao`) mostra "🖼 sem texto — vai clicar
por imagem" quando reconhece o ícone salvo, ou "⚠ sem texto nem ícone
salvo — não vai reproduzir" no caso raro de nenhum dos dois existir —
pra pessoa saber, antes de aprovar, que aquele passo específico
depende de casamento de imagem, não de texto.

**Validado por teste de lógica real** (não contra o Domínio — mesma
limitação de sempre): gravador salva `template_icone` só quando o
texto é fraco (confirmado que clique com texto bom NÃO gera recorte à
toa); `salvar_rotina_gravada()` copia o ícone pra local persistente
(confirmado que é cópia, não o arquivo original, e que o caminho
salvo aponta pro lugar novo); `executar_passos()` chama
`achar_icone_robusto()` (não `achar_ou_parar()`) quando só há ícone,
clica exatamente na posição devolvida; falha com segurança (devolve
`False`, sem tentar clicar às cegas) tanto quando o arquivo do
template sumiu do disco quanto no caso antigo de nem texto nem ícone;
excluir uma rotina limpa a pasta de ícones junto. Suíte completa (244
testes, incluindo os do servidor da outra sessão) passando — 1 teste
alheio (`test_duplicacao_de_requisicao_nao_reexecuta`) falhou uma vez
por lentidão de máquina com as duas sessões rodando junto, confirmado
instável (passa isolado), não é regressão.

**Ainda não testado contra o Domínio real** — falta gravar uma rotina
de verdade com clique em ícone (ex.: regravar a "TEste nova rotina ex"
corrigida) e confirmar que `achar_icone_robusto()` acha o alvo certo
numa sessão ao vivo, não só em imagem sintética.

---

### 0.86 Dois instaladores: servidor e interface cliente na rede local (08/10/2026)

**Pedido:** testar usando o PC atual com Domínio como servidor e outro
PC na mesma rede/Wi-Fi. O usuário pediu instalações separadas, com
endereço do servidor e chave de acesso na interface. Preparação feita
no mesmo repositório, sem novo produto e sem mudar navegação fiscal.

`Instalar Servidor.bat` instala API/HTTPS e pergunta acesso local ou
rede. `scripts/configurar_servidor.py` detecta IPv4 privado, pede
conferência do endereço e usa `app/rede_local.py` para gerar autoridade
local e certificado TLS com SAN do IP. Chaves/configuração ficam em
`data/rede_local`, gitignored. A autoridade é reutilizada em nova
configuração; corrupção/expiração interrompe em vez de trocar confiança
automaticamente. Certificados usam revisões separadas; configuração
publicada por escrita atômica. Foi acrescentada somente `cryptography`
ao componente opcional do servidor; Pydantic fixado na versão testada.

Pacote `data/rede_local/interface_cliente`: quatro arquivos públicos
(instalador BAT, script PowerShell, certificado CER e endereço/hash).
Não contém chave privada, chave de acesso, Python, OCR ou dados fiscais.
`Instalar Interface.bat` usa Edge/Chrome já instalado, registra a
confiança HTTPS local no usuário Windows e cria atalho em janela própria.
Endereço salvo localmente; chave continua informada na página e somente
em memória. A instalação PWA pelo navegador permanece disponível.

`Liberar Acesso Rede.bat`, executado manualmente como administrador,
cria a regra exclusiva deste app: IP/porta/Python configurados,
sub-rede local e perfis Private/Domain. Não desabilita o firewall.
`Testar Interface na Rede.bat` usa simulação; `Executar Dominio na Rede.bat`
usa o executor existente. O parâmetro `--rede-local` lê configuração
HTTPS preparada, preservando consulta/simulação/execução e atalhos locais.
O outro PC precisa apenas de navegador; Domínio/OCR permanecem no servidor.

**Validação:** 253 testes passaram após integrar o commit Claude
`0d29e41` (ícones nas rotinas gravadas, seção 0.85). Testes novos
conferem cadeia/assinatura/SAN/chave, TLS real com confiança e hostname
divergente, pacote sem chaves, reutilização da autoridade, corrupção,
caminhos restritos e escrita atômica. Sintaxe Python/PowerShell passou;
entrada HTTP no instalador cliente foi recusada antes de modificar o PC.
Resolução de wheels para Windows x64/Python 3.14 passou em dry-run.

**Ainda não validado no Windows:** importação da confiança, atalho,
regra de firewall, conexão entre os dois PCs e execução fiscal remota.
O operador precisa atualizar, instalar/configurar o servidor e levar
o pacote público ao cliente. O PC com Domínio deve permanecer visível,
desbloqueado e sem interferência durante a rotina. Guia completo em
`docs/SERVIDOR-E-INTERFACE.md`; lote/agentes gerais e falha de PDF não
foram ampliados ou declarados concluídos nesta entrega.

---

### 0.87 Atalhos organizados em pastas, sem remover funcionalidades (08/10/2026)

**Pedido:** reduzir os arquivos visíveis na raiz, mantendo todas as
funcionalidades. O usuário esclareceu que deseja apenas organizar,
sem apagar instaladores ou alterar o funcionamento.

Os três instaladores principais (`Instalar.bat`, `Instalar Servidor.bat`
e `Instalar Interface.bat`) e `Atualizar.bat` continuam na raiz.
Os outros 17 BAT estão em `atalhos/servidor/`, `atalhos/interface/`,
`atalhos/ocr/` e `atalhos/ferramentas/`. Índice em `atalhos/README.md`.
Os nomes citados nas seções anteriores correspondem à localização
antiga; os guias de uso atuais indicam os caminhos novos.

Diretório de trabalho, chamada entre os BAT de OCR e caminho do
PowerShell foram ajustados. Scripts, opções, dependências, modos e
dados locais foram preservados. Mensagens de orientação e documentação
apontam para as novas pastas. O pacote público da interface cliente
continua igual; não exige reinstalação de aplicativos.

**Validação:** todos os 21 BAT preservados, comparação dos comandos e
opções com a versão anterior, resolução dos caminhos/chamada OCR/links,
sintaxe Python/PowerShell e 253 testes locais/simulados passaram.
Os atalhos reorganizados ainda precisam do teste por duplo clique no
Windows; a nuvem não executou a sessão real do Domínio.

---

### 0.88 Diagnóstico de chave inválida ao iniciar o servidor (08/10/2026)

**Achado:** a interface no segundo PC abriu após mudar o perfil da
rede do servidor de Pública para Privada. Ao tentar iniciar o modo
real, apareceu a mensagem genérica de servidor não iniciado. O usuário
informou ter alterado a chave, sem fornecer o conteúdo.

`obter_chave()` já exige ao menos 32 caracteres e lê ASCII, mas a
entrada tratava essa recusa como falha genérica de dependências/porta.
A validação agora ocorre antes de criar executor/banco e informa o
requisito diretamente. Erro de acesso ao arquivo tem orientação própria.
A chave não é impressa nem substituída; autenticação e tamanho mínimo
foram preservados. O guia documenta alteração e reinício.

O teste cobre senha curta e conteúdo não ASCII: início recusado sem
API/servidor/banco, arquivo preservado e saída sem o segredo. 254 testes
passaram. Outras falhas OSError/ValueError ao iniciar passam a registrar
a causa no log local; recusas de chave são tratadas antes, sem traceback
de decodificação que poderia conter o segredo.

O log enviado registra WinError 10054 em callback asyncio de desconexão,
sem identificar definitivamente a causa da recusa de inicialização.
O novo diagnóstico ainda precisa ser visto no Windows.

---

### 0.89 Controles remotos, competência escolhida, login humano e menus (08/10/2026)

**Pedidos/evidências:** após conectar os dois PCs, o usuário informou
que a execução remota funcionou, sem log/documento detalhado dessa rodada.
Pediu Pausar, calendário e login integral pelo cliente. Forneceu o caminho
Onvio → Entrar → e-mail/senha → método E-mail → código → Continuar →
Domínio Web/Entrar → Lista de Programas/Escrita Fiscal → Conectando/
usuário/senha/OK → tela azul. A captura mostrou Conectar em = Contábil;
preservar esse campo. Também pediu configuração de rotinas, recuperação
sem acessar o PC servidor e redução dos 12–15s percebidos nos menus.

**Implementação:** controle cooperativo por ContextVar, checkpoints entre
ações, pausa/retomada autenticadas e estado distinto de pausa solicitada.
Retomada exige foco/quadro compatíveis; divergência ou encerramento durante
pausa interrompe a tarefa sem repetição. No cliente, SPED/Contribuições
pedem mês/ano e Livros pedem datas. Campos obrigatórios começam vazios.
API aceita meses completos passados além do anterior; os geradores recebem
datas explícitas e as preservam no retry. Chamadas locais antigas mantêm
mês anterior; máscara, Tab, OCR de confirmação e geração foram preservados.

Login e manutenção usam o mesmo worker/trava fiscal. Playwright 1.63 usa
Edge/Chrome local, perfil próprio, destinos HTTPS conhecidos e campos DOM.
O código é informado pelo usuário na interface, tem ID único/prazo de
cinco minutos/consumo único. Senhas/código não entram no banco/logs.
Na parte GO-Global, texto exato/único por OCR e retângulos medidos ao lado
dos rótulos localizam campos, sem offsets inventados nem UI Automation.
Ambiguidade recusa digitação. Falha preserva a etapa para diagnóstico.

Reiniciar ciclo interrompe num checkpoint, não repete geração e fecha
somente Domínio/Lista de Programas identificados e navegador próprio.
Não mata processos nem fecha apps indiscriminadamente. Falta confirmar
fechamento para abrir o ciclo novo. Calibração remota reaproveita medidas,
foco e duas capturas existentes; requer confirmação humana. Captura de
janela reconhecida fica só em memória, disponível por 30s ao cliente
autenticado, sem disco/IA. Isso amplia deliberadamente o contrato antigo
sem imagens para permitir conferência no outro PC.

Configuração no painel salva rascunhos no catálogo existente. Cliques e
hover por texto, teclas de formulário e parâmetros de empresa/período;
sem Python livre ou senhas literais. Hover antigo x/y continua igual.
Não promove rascunhos nem habilita execução remota de gravações.

Navegação conhecida usa polling visual no lugar de três esperas fixas de
2s no SPED/Contribuições e duas nos Livros. Mapa local guarda regiões já
confirmadas; relê por OCR, recai na região original e invalida por tamanho.
Mantém clique em L e espera de geração. Medição sintética Linux/Tesseract:
três leituras, medianas 1,028s na região original e 0,275s no recorte;
não mede velocidade ou precisão no Domínio Windows.

**Validação:** 290 testes passaram, incluindo SPED/Contribuições, mês
bissexto/recusa de período atual/incompleto, retry, pausa/retomada/encerramento,
segredos, solicitação expirada, exclusividade login/fiscal, reinício,
rascunhos, hover antigo/novo e fallback de mapa. Chromium com API/worker
reais e fiscal/login simulados conferiu os controles, responsividade
1440/900/390, logout e offline. Wheels Playwright/greenlet compatíveis
com Windows x64/Python 3.14 foram baixadas pelo PyPI. Compilação, pip check,
JavaScript e diff passaram. Ainda sem validação completa do login/campos
novos, autorização de abertura do GO-Global ou velocidade real no Windows.
Conferência de período/nome PDF permanece pausada, sem afrouxar critérios.

Prioridade seguinte reaberta pelo usuário: lotes por regime/empresas ×
rotinas aprovadas, após esses controles. Agendamento por empresa/dia/hora
é futuro; desenho e validações em ROADMAP-RPA.md. Lote remoto e agendamento
não estão habilitados nesta entrega.

---

### 0.90 Cadastro web e lote ordenado por empresa/regime (08/10/2026)

**Pedido:** o usuário esclareceu que configura as rotinas de cada regime;
cada empresa tem um seletor de regime. Rodar todas as rotinas da empresa
atual, trocar para a próxima selecionada e usar as rotinas do regime dela.
Agendamento de dia/horário permanece futuro. Não inventar obrigações pelo
regime nem reescrever geradores fiscais que já funcionam.

**Implementação:** cadastro autenticado de empresas/regimes no mesmo
SQLite do servidor. Rotinas integradas em ordem escolhida pelo usuário;
seletor de regime por empresa. Preserva CSV/lote local e não importa
exemplos automaticamente. Calendário obrigatório por competência ou
intervalo; SPED exige mês completo passado, Livros aceitam datas passadas.
Revisão mostra a sequência e exige apuração de todas as empresas. Hash
do plano detecta cadastro/período alterado entre revisão e envio.

Lote cria snapshot e tarefas atomicamente, em ordem empresa → todas as
rotinas → próxima empresa. Um worker/trava, compartilhado com individual,
login e manutenção. Identificador repetido não duplica, inclusive após
edição de cadastro ou reinício. Editar regime não altera lote iniciado.
Conclusão exige booleano positivo, fim e retorno visual reconhecido.
Falha/recusa/resultado não confirmado interrompe próximos itens e guarda
os anteriores. Pausa/retomada e interrupção no painel; cancelar acorda
uma execução pausada e interrompe num checkpoint. Reinício marca itens
inacabados interrompidos, sem repetir. Ocupação consulta todo o banco,
sem depender das últimas 100 linhas do histórico.

O adapter de lote reutiliza `trocar_empresa()` (F8) existente e confere
tela principal/foco antes/depois e código no cabeçalho antes de gerar.
Empresa já correta não é trocada. Individual preserva recusa de empresa
divergente. Geradores recebem as mesmas datas explícitas. Nenhum novo
menu ou offset foi suposto. A busca F8 pressupõe Código como no fluxo
local: ainda conferir no primeiro teste Windows. Rascunhos de novas
rotinas não foram promovidos nem expostos para execução remota.

**Validação:** 313 testes passaram; cadastro/ordem por regime, mês
bissexto, intervalo de Livros, fila concorrente/idempotente, plano
desatualizado, snapshot, interrupção após falha, resultados preservados,
cancelamento durante pausa, ocupação com mais de 100 itens e conferência
de código no adapter. Chromium com API/SQLite/worker reais e fiscal/login
simulados conferiu os cadastros, seletor por linha, sequência empresa por
empresa, revisão/calendário, lote e pausa/retomada/interrupção, além dos
controles anteriores, três larguras, logout/offline. A revisão corrigiu
seletor que ficava habilitado durante gravação de outro cadastro. A entrada
CLI de simulação também foi exercitada com configuração temporária:
HTTP/site/JavaScript, cadastro vazio inicial, plano, quatro tarefas em
ordem, reenvio sem duplicação e encerramento código 0. Compilação, pip
check, JavaScript e diff conferidos. Nenhum teste operou o Domínio real.

**Próxima rodada:** atualizar/reiniciar servidor e Ctrl+F5 no cliente;
cadastrar em modo real duas empresas autorizadas e regimes com rotinas
conhecidas; escolher competência apurada e conferir documentos, códigos,
ordem, retorno e controles. Bancos de simulação e real são separados.
Conferência de período/nome PDF permanece pausada, sem relaxar critérios.
Agendamento, importação CSV web e execução remota de rascunhos não foram
implementados neste incremento.

---

### 0.91 Mapeamento de emissão conjunta de Livros Fiscais (09/10/2026)

**Achado pelas telas e instruções do operador:** a aba Geral de Livros
Fiscais permite selecionar Entradas, Saídas e ICMS com o mesmo período.
Depois de OK/processamento, a primeira prévia pode ser qualquer livro.
O ícone PDF abre um menu; a opção escolhida é “Gerar um arquivo PDF para
cada relatório”. Ela abre “Procurar Pasta”, com Unidade/árvore/OK, distinto
do diálogo de nome de arquivo usado pelo gerador individual antigo.
As capturas mostram Servidor (C:) e depois Client C (M:).

**Consequências para a implementação:** não alternar caixas já marcadas;
confirmar as três seleções e datas. Não tratar a ordem da prévia como
identidade do PDF. Reutilizar a conversão de caminho local para unidade
cliente da seção 0.59, com destino configurável. O usuário vai solicitar
um esquema do servidor para confirmar pasta local Dropbox, organização
e acesso. Não fixar usuário nem caminho pessoal no código. A API atual
guarda um caminho por tarefa; a conjunta precisará guardar resultados e
downloads de cada documento e evitar emissão duplicada no lote.

**Estado:** [mapeamento detalhado](LIVROS-FISCAIS-CONJUNTOS.md), sem mudar
geradores nem habilitar emissão. Faltam navegação real no seletor,
arquivos produzidos, título/conteúdo do ICMS e retorno das prévias.
Imagens não foram versionadas nem medidas por OCR nesta sessão; nenhum
offset novo calibrado e nenhum log de teste automatizado no Windows.

---

### 0.92 Travas de empresa, foco e preparação da sessão (09/10/2026)

**Pedido:** código solicitado X deve selecionar X, mesmo se o Domínio
mostrar Y, e telas fora do padrão devem permitir recuperação segura.

**Achados no código:** lote já usa F8, mas individual recusava empresa
divergente. O código era lido uma vez quando não precisava trocar. Se a
tela não era o painel azul no início, recusava sem tentar recuperação.
O fallback de F8 no gerador legado envia Esc repetido sem conferir o
painel entre ações. Não são achados de uma execução fiscal nesta sessão.

**Correção:** individual e lote podem trocar por F8 e reler código/tela
principal imediatamente antes de gerar. Preparação usa recuperação
calibrada existente, com até cinco Esc na janela identificada, uma ação
por vez e parada no painel azul. O executor fornece callback de retorno
verificado à troca F8, antes da única nova tentativa de abertura da troca.
Verificação de foco nos checkpoints de mouse/teclado bloqueia ações
posteriores após perda de foco, inclusive se a exceção for absorvida.
Não habilita emissão com código ilegível/divergente nem OK desconhecido.
Busca por Código no F8 continua pressuposto do fluxo legado da seção 0.14.

**Validação:** 355 testes de lógica/API e smoke Chromium com fiscal/login
simulados passaram. Testes com desktop substituído verificam troca individual,
código alterado entre leituras, ausência de janela/calibração/foco, retorno
limitado, bloqueio persistente e callback F8. Worker/SQLite confirmam falha
por perda de foco durante a emissão, recuperação e próxima rotina sem
repetição. Compilação conferida. Falta
homologar no Windows: X com Y selecionada, empresa já correta, tela aberta
no início, falha recuperável seguida da próxima rotina e perda de foco.
Nenhuma emissão fiscal real foi executada nesta sessão. A emissão conjunta
dos três Livros Fiscais continua no mapeamento da seção 0.91.

---

## 1. Análise do projeto

O briefing pede um motor de automação de verdade (máquina de estados,
adapters trocáveis, observabilidade, execução em lote), não um script de
clique — é a diferença entre sobreviver à primeira atualização de tela do
Domínio ou não. A ambição do briefing é grande (chega a desenhar Fase 8/9
de produto SaaS multi-tenant); esta análise leva a sério o próprio aviso
do briefing de não construir tudo de uma vez — só as camadas 1–7 (core,
adapters, state machine, workflow, error handler, logging, config) têm
código nas primeiras fases. Persistência central, fila de jobs, API web e
painel ficam para a Fase 8+.

Duas diferenças estruturais em relação ao `docauto`:

- **`docauto` só lê e copia.** Erro dele, na pior hipótese, arquiva num
  lugar errado (reversível — nada é apagado). **O Domínio Automation
  Engine vai clicar em botões que calculam, geram guia e podem transmitir
  para a Receita.** Erro aqui pode ser irreversível. "Na dúvida, para e
  pergunta" vira, aqui, "**na dúvida, não clica**".
- **`docauto` roda sozinho, sem depender de tela aberta.** Este motor
  depende de uma sessão Windows com o Domínio aberto e destravado.

---

## 2. Principais riscos técnicos

| Risco | Evidência / probabilidade | Direção de mitigação |
|---|---|---|
| **Sem ambiente de homologação** — todo teste é em produção | **Confirmado** (PR #1) | Risco #1. Ver seção 5.7 — a mitigação é escolher a operação certa, não esperar por um ambiente que não existe |
| **Cálculo automático incorreto sem erro visível** (PGDAS zerado) | **Já aconteceu, real, confirmado** | Nenhuma automação de apuração roda sem comparação humana lado a lado até a causa ser entendida |
| **Rotinas encadeando ações não solicitadas** | **Já aconteceu duas vezes, confirmado** | Todo controle de "ação após concluir" desligado por padrão; disparo não previsto = `UNKNOWN_ERROR`, nunca sucesso |
| ~~Delphi/VCL com grid de terceiro pode não expor bem UI Automation~~ → **confirmado, mas por outro motivo** | A tela inteira é entregue via GO-Global (seção 0.2) — não é questão de grid, UI Automation simplesmente não alcança nada aqui | OCR **não é mais plano B** — é o único caminho viável para automação externa desta tela (seções 0.3/0.4) |
| **Este ambiente de execução (sessão de nuvem) não alcança a máquina Windows do escritório** | Confirmado (mesma limitação já documentada para o `docauto`) | Inspeção/execução real acontece na máquina do usuário; ele roda comando e cola resultado, ou usa Claude Code localmente lá |
| **Licença/instância única do Domínio** — concorrência não confirmada | Não verificado | Assumir execução serializada (uma empresa por vez) até confirmado o contrário |
| **Certificado digital / e-CAC** exigido por várias rotinas | Confirmado: uma rotina tinha opção de gerar guia via e-CAC marcada **sem ninguém ter configurado** | Nunca automatizar transmissão via certificado sem confirmação explícita; auditar checkboxes reais antes de rodar |
| **Atualização do Domínio muda a tela** | Risco clássico de RPA sobre software comercial vivo | Versionar a versão exata (10.6A-08-04); revalidar a cada atualização |
| **Múltiplas pessoas configurando por fora** (Dropbox pessoal) | Confirmado | Centralizar caminho de destino sob controle do motor, não de config pessoal |
| **ToS/contrato Thomson Reuters** — cobertura de automação externa não confirmada | Não verificado | Pergunta do chamado de suporte (seção 4) |

---

## 3. O que precisamos descobrir sobre o Domínio

### 3.1 Perguntas de negócio

1. ~~Qual obrigação exatamente é a prova de conceito?~~ → **Decidido: EFD
   ICMS/IPI (SPED Fiscal) da única empresa fora do Simples Nacional**,
   seguindo o princípio da seção 5.7 (gerar, nunca calcular/transmitir).
   Não passa pela tela de Apuração/PGDAS onde o bug está.
2. Isso roda no **Domínio Escrita Fiscal** (confirmado, 10.6A-08-04) —
   confirmar se ECD/ECF (caso venham depois) exigem também o Domínio
   Contábil.
3. Quantas competências dessa empresa já foram fechadas e entregues no
   passado (candidatas para o teste da seção 5.7)?
4. As rotinas de importação já validadas (CT-e, NF-e) e o SIEG cobrem
   sobreposição — vale automatizar as duas ou só uma? (Não bloqueia a
   Fase 0 atual, fica para quando a POC expandir.)
5. Existe possibilidade real de uma segunda instalação/licença do Domínio
   para servir de ambiente de teste, mesmo que temporária? (Desejável,
   deixou de ser bloqueio por causa da seção 5.7.)

### 3.2 Perguntas técnicas (Fase 0/1 respondem com a tela aberta)

6. O Domínio Escrita Fiscal expõe uma árvore de **UI Automation**
   utilizável (nomes, `automation_id`, `control_type` estáveis), ou os
   controles aparecem genéricos (`Pane`, `Custom`, sem nome)? Decide o
   backend do `pywinauto` (`uia` ou `win32`).
7. A tela de geração/exportação da obrigação decidida no item 1 é
   controle padrão (lê campo a campo) ou desenhada por componente de
   terceiro (exige OCR)?
8. Uma janela nova (empresa, rotina) é sempre uma janela Win32 de verdade
   (com `hwnd` próprio) ou troca de conteúdo dentro da mesma janela
   principal (MDI)? Muda a estratégia de espera.
9. Mensagem de sucesso/erro aparece em caixa de diálogo padrão do Windows
   (fácil de ler) ou dentro de painel/grade da própria tela (mais
   difícil)?
10. É possível abrir o Domínio já com a empresa e a tela certas via
    parâmetro de linha de comando, ou a navegação é sempre manual?
11. O que exatamente aciona os checkboxes/rotinas encadeadas vistos na
    PR #1 (também pergunta 4 da seção 4)?

---

## 4. APIs oficiais possivelmente relevantes

**Nada abaixo está confirmado para disparar apuração/SPED e ler o
resultado — tudo precisa de confirmação por escrito com a Thomson Reuters
antes de virar arquitetura.**

| Achado (verificado em setembro/2026) | Cobre o nosso caso? |
|---|---|
| **Central do Desenvolvedor** — `dominiosistemas.com.br/lp-centraldodesenvolvedor-api` | Existe portal de API. Documentação pública trata de **documentos fiscais de ERP (XML/TXT)** e folha — entrada de dado, não disparo de apuração/SPED |
| **Onvio BR Accounting API** — `developerportal.thomsonreuters.com/onvio-br-accounting-api` | Mesmo escopo acima |
| **Documentação Integração API para ERPs** (artigo 8476) | Mesmo escopo — importação de documento fiscal |
| **Rotinas Automáticas** (nativo do Domínio, `Arquivos → Rotinas Automáticas`) | **Não é API REST**, mas é recurso **oficial, nativo e já parcialmente testado** nesta carteira (CT-e). Tratado como camada própria — seção 5.1 |
| Artigos 9143 e 3221 do suporte | Documentam comportamento de pasta de destino e seleção de empresas nas Rotinas Automáticas |

### Perguntas para o chamado com a Thomson Reuters

> 1. Existe API oficial (REST/SOAP) para disparar apuração de tributo,
>    geração de guia ou de obrigação acessória (SPED/PGDAS-D) de uma
>    empresa e competência, sem passar pela tela?
> 2. As **Rotinas Automáticas** podem ser disparadas por linha de comando,
>    agendador de terceiros ou API, além do agendador interno e da tela?
> 3. Existe log estruturado (arquivo, banco ou API) com o resultado de
>    cada execução de Rotina Automática, consultável fora da tela?
> 4. O que aciona as ações encadeadas da aba "Geral" de uma rotina mesmo
>    quando aparentam estar desmarcadas? Há casos documentados de disparo
>    não solicitado?
> 5. O cálculo de PGDAS via Rotina Automática tem pré-requisito de
>    cadastro (anexo do Simples, atividade, Fator R) que, se ausente,
>    produz resultado zerado sem erro visível? Como validar isso?
> 6. Existe ambiente de homologação para o Domínio Escrita Fiscal/Contábil?
> 7. Há cláusula contratual/de suporte sobre automação externa da
>    interface (RPA/UI Automation)?
> 8. É suportado consultar o banco de dados do Domínio diretamente
>    (ODBC/view somente leitura), só para relatório, sem usar a tela?

**Registrar a resposta por escrito.**

---

## 5. Arquitetura recomendada

### 5.1 Ordem de prioridade tecnológica — com uma camada nova

```
1. API oficial confirmada por escrito com a Thomson Reuters
1.5 Recurso nativo oficial do próprio Domínio em lote/agendamento
    ("Rotinas Automáticas") — não é API, mas é suportado pelo fabricante
    e parte dele já foi validada nesta carteira (CT-e, rotina 10)
2. Microsoft UI Automation (backend "uia" do pywinauto)
3. Win32 clássico (backend "win32") — provável melhor opção se o Domínio
   for VCL/Delphi "puro" sem grids de terceiro
4. OCR
5. Computer Vision
6. Coordenada de mouse/teclado — último recurso
```

O papel deste motor, dado o item 1.5, pode ser mais estreito e mais
seguro do que "clicar em tudo": **supervisionar e orquestrar** as Rotinas
Automáticas nativas (disparar quando o agendador interno não bastar, ler
resultado, detectar sucesso/erro, registrar, alertar) em vez de recriar
cada tela por UI Automation. UI Automation externa entra onde o recurso
nativo não alcança.

### 5.2 Onde o código mora

Este repositório, separado do `docauto` — domínio de negócio e de risco
diferentes, e caminho mais limpo para virar produto independente na
Fase 9.

Estrutura proposta (ainda não criada — só depois da Fase 0/1 confirmarem
viabilidade técnica):

```
app/
  core/              # máquina de estados, workflow engine, orquestração
  dominio/           # adapter do Domínio propriamente dito
  automation/
    ui/               # pywinauto/UI Automation — troca de mecanismo sem tocar workflow
    nativo/           # supervisão das Rotinas Automáticas (camada 1.5)
  ocr/
  vision/
  workflows/
  state_machine/
  logging/
tests/
  unit/
  integration/        # com Domínio real, marcados para rodar só na máquina onde ele existe
  fixtures/
docs/
scripts/
.github/workflows/
```

**Ponto prático:** o `docauto` já foi mordido uma vez por manutenção de
ambiente (venv com caminho absoluto quebrando ao renomear pasta). Um
segundo repositório é uma segunda venv, um segundo "como eu atualizo
isso" para quem opera sem ser programador. Vale desenhar o mesmo tipo de
atalho (`Abrir ... .bat` / `Atualizar ... .bat`) desde o início.

### 5.3 Persistência e observabilidade — adiadas de propósito

PostgreSQL, fila de jobs e painel web só entram na Fase 8. Até lá:

- **Log estruturado em JSON Lines local** (um evento por linha:
  `execution_id`, `company_id`, `routine_id`, `timestamp`, estado, ação,
  resultado, duração, erro) — mesmo padrão do `docauto`
  (`detalhado.jsonl`).
- **Screenshots em disco local**, nunca versionados, nunca enviados a
  lugar nenhum automaticamente.
- Estado da máquina de estados em memória durante a execução; resultado
  final gravado no log JSON Lines.

### 5.4 Segurança e LGPD

- Certificado digital (A1/PFX, senha): nunca em texto no repositório,
  nunca como argumento de linha de comando (fica no histórico do
  `cmd.exe`); variável de ambiente ou arquivo local fora do Git.
- Screenshot de erro pode conter dado fiscal real — pasta em
  `.gitignore`, retenção definida, nunca colado em chat sem mascarar.
- Qualquer log/print que toque CNPJ, razão social ou valor: mascarar
  antes de aparecer em chat ou commit (mesmo princípio já aplicado no
  `docauto` — ver `src/docauto/aprendizado.py`/`normalize.py` naquele
  repositório para os utilitários já existentes, reaproveitáveis por
  referência).

### 5.5 IA

Classificação estruturada → regra determinística → ação, nunca IA com
autonomia sobre a ação. O `docauto` já implementa esse padrão
(`ia_adaptativa`, desligado por padrão, manda só estrutura/estatística
para o Claude, nunca texto de documento real) — seguir o mesmo modelo
aqui para classificar mensagem de erro desconhecida.

### 5.6 Máquina de estados

Lista de estados do briefing original, como ponto de partida, mais dois
específicos deste projeto:

- `NATIVE_ROUTINE_TRIGGERED` / `NATIVE_ROUTINE_RESULT_DETECTED` — para o
  caminho de supervisionar Rotinas Automáticas nativas (5.1).
- Qualquer ação encadeada não solicitada detectada (padrão já visto duas
  vezes na PR #1) entra direto em `UNKNOWN_ERROR` com recuperação
  "pausar e alertar" — nunca tratada como sucesso.

### 5.7 A operação "reversível e segura" para rodar sem ambiente de teste

Sem staging, a primeira operação real tem que ser reversível por
natureza, não por sorte:

> **Gerar** (nunca calcular do zero, nunca transmitir) a obrigação de uma
> **competência já fechada e já entregue no passado**, e comparar o
> arquivo gerado agora com o que foi de fato entregue então.

Por quê isso é seguro mesmo em produção:

- **Gerar um arquivo de exportação não altera lançamento nenhum** —
  leitura formatada, não escrita. Diferente de "Apuração" (calcula, e foi
  exatamente aí que o bug do PGDAS apareceu) e de "transmissão"
  (irreversível, envolve certificado/e-CAC).
- **Competência já fechada e já entregue dá um oráculo de verificação
  automático**: se o arquivo gerado agora bate com o que foi entregue
  naquela época, a POC passou — não depende de opinião.
- **Não precisa de empresa fictícia nem de ambiente de teste** — a
  segurança vem da operação escolhida, não do ambiente.

---

## 6. Roadmap completo e 7. estimativa de tempo por fase

**Nota:** o critério de aprovação de "Fase 0" adotado pelo escritório é o
checklist ponta a ponta (Domínio abre → empresa correta selecionada →
rotina/tela-alvo aberta → parâmetros preenchidos → execução → resultado
identificado → sucesso/erro registrado → screenshot quando necessário →
encerra sem estado inconsistente → pronto para a próxima). Isso
corresponde às Fases 0–2 da tabela abaixo, rodando sobre **uma única
rotina, uma única empresa**, com a operação segura da seção 5.7.

As estimativas assumem o ritmo já demonstrado no projeto irmão
(`docauto`): sessões assíncronas, um comando por vez, usuário
não-programador colando resultado de cmd.exe, sem ambiente de testes
dedicado.

| Fase | Objetivo | Entregável | Estimativa | Depende de |
|---|---|---|---|---|
| **0 — Discovery** | Abrir chamado TR, confirmar competências candidatas | Perguntas registradas por escrito | 3–7 dias corridos | Escritório |
| **1 — Inspeção de UI** | Confirmar se a árvore UIA é utilizável; escolher backend | Script de inspeção (`pywinauto`), rodado na máquina com o Domínio aberto, árvore exportada em JSON | 1 sessão de construção + 1–2 de uso real | Fase 0, acesso a uma sessão do Domínio |
| **2 — Primeira interação** | Ler e interagir com um controle real, validar mudança | Teste isolado, sem ação destrutiva | 1–2 sessões | Fase 1 |
| **3 — State machine** | Implementar os estados da seção 5.6 | `core/state_machine` com testes | 2–3 sessões | Fase 2 |
| **4 — Primeira rotina** | Gerar o EFD ICMS de uma competência já entregue, comparar | Rotina completa ponta a ponta, log JSON Lines, screenshot em erro | 3–6 sessões | Fases 1–3 |
| **5 — Multiempresa** | Lista de empresas, execução sequencial, erro isolado por empresa | CLI (`processar --empresas ...`) | 2–3 sessões | Fase 4 estável por 2–3 competências |
| **6 — Relatório** | Sucesso/erro/pendência/tempo por execução | Comando de relatório | 1 sessão | Fase 5 |
| **7 — Recovery** | Recuperação automática nos cenários de resiliência do briefing | Estratégias por tipo de erro, testadas | 1–2 semanas concentradas | Fase 6, catálogo real de erros |
| **8 — Painel** | API, dashboard, autenticação, histórico | Fora do horizonte deste documento | Semanas | Fases 0–7 estáveis por um ciclo mensal |
| **9 — Produto** | Multi-tenant, cobrança, planos | Fora do horizonte deste documento | Meses | Piloto validado |

---

## 8. Dependências

- Acesso a uma sessão Windows com **Domínio Escrita Fiscal** instalado e
  licenciado (via GraphOn GO-Global, seção 0.2) — já existe. Versão vista
  em campo já mudou uma vez (10.6A-08-04 → 10.6A-08-09) — não fixar
  número exato em código, só registrar no log de cada execução.
- Python 3.x, **`pytesseract` + Tesseract (idioma `por`)** e
  **`opencv-python` + `numpy`** — confirmados necessários e já instalados
  e testados com sucesso (seções 0.3/0.4), não são mais "só se a Fase 1
  confirmar".
- `pywinauto`/`pywin32` — úteis só para **enumerar janelas** (achar a do
  Domínio por classe/tamanho, seção 0.5), não para automação de controle
  (UI Automation/Win32 não funcionam nesta tela, confirmado).
- ~~Inspect.exe / Accessibility Insights for Windows~~ — instalado, mas
  o Live Inspect não conseguiu capturar elementos de forma confiável
  nesta tela (seção 0.2); não foi mais necessário depois disso.
- Git.
- Canal de suporte Thomson Reuters (seção 4).
- Esta sessão de nuvem **não** é dependência de execução — não alcança a
  máquina Windows do escritório. Quem executa os scripts de
  inspeção/automação é o usuário, na sua máquina, colando o resultado de
  volta — ou uma sessão do Claude Code rodando localmente lá.

---

## 9. Bloqueios possíveis, em ordem de severidade

1. **Causa raiz do PGDAS zerado não encontrada** (PR #1) — enquanto não
   for entendida, nenhuma automação de apuração desta carteira deveria
   ser considerada confiável.
2. **Nenhum ambiente de homologação existe** — mitigado (não eliminado)
   pela operação segura da seção 5.7.
3. **Não confirmado se o contrato/licença cobre automação externa da
   interface.**
4. **Acessibilidade real da árvore de UI Automation** — só a Fase 1
   resolve; se os controles forem opacos, o custo de OCR/Computer Vision
   muda a estimativa da seção 7 para cima.
5. **PR #1 esquecida** — se ninguém decidir/continuar, o achado crítico
   pode se perder entre sessões.

---

## 10. Plano da Fase 0 (acionável, sem código novo)

1. **Abrir o chamado com a Thomson Reuters** com as perguntas da seção 4.
2. **Levantar as competências já fechadas e entregues** da EFD ICMS da
   empresa-alvo, para servir de comparação (seção 5.7).
3. **Instalar as ferramentas de inspeção** na máquina onde o Domínio
   roda: Python 3.x, `pip install pywinauto comtypes uiautomation`
   (ambiente **separado** do `.venv` do `docauto`), e
   **Accessibility Insights for Windows**.
4. **Identificar versão do Windows** (`winver`) e confirmar 32/64 bits do
   Domínio instalado.
5. **Abrir o Domínio, abrir a tela de geração da EFD ICMS, e inspecionar
   com Accessibility Insights/Inspect.exe**, sem executar nada: janela
   principal, botões, campos, menus, e se a grade de resultado é legível
   por UI Automation ou parece desenhada por componente de terceiro.
6. **Documentar tudo neste mesmo arquivo** (seção 0, mesmo formato) —
   literal, com nomes exatos de tela, mesmo padrão já provado em
   `DOMINIO_FISCAL_ROTINAS.md` (repositório do `docauto`).
7. **Retomar a investigação da PR #1** (causa do PGDAS zerado) em
   paralelo, como parte do mesmo esforço de campo.

**Critério de aprovação:** chamado da seção 4 registrado por escrito,
competências candidatas levantadas, árvore de UI Automation da tela-alvo
documentada (mesmo que a resposta seja "não é utilizável, precisa de
OCR"). Nenhum desses itens exige escrever automação.
