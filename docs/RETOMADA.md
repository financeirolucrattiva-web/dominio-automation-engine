# Retomada do projeto — 07/10/2026

O trabalho atual é o incremento **2: consolidar execução e recuperação**
do [roadmap RPA](ROADMAP-RPA.md). O documento `00-analise-e-plano-fase0.md`
é o histórico do projeto; seu nome não significa que todo desenvolvimento
continua na fase de descoberta. O plano original tem dez fases (0–9);
o roadmap RPA organiza o trabalho atual em seis incrementos.

Validação desta entrega: **179 testes locais/simulados passaram**,
compilação dos arquivos Python alterados e checagem de diff passaram.
Os testes não operaram a sessão real do Domínio. Separadamente, PP-OCRv5
foi carregado e executado em CPU/Linux sobre imagem sintética, com caixas
válidas. Em 07/10/2026, o operador também concluiu as seis leituras de
uma captura atual no Windows; isso valida inferência local, sem validar
precisão, estados ou execução fiscal com Paddle.

## O que foi preparado

- Acompanhamento por etapas nas quatro rotinas conhecidas, com marcadores
  de evidência e logs locais; erro, ação enviada e estado confirmado são
  diferenciados.
- OCR reutilizado por pixels/região/escala em cada checagem de estado;
  reduz leituras repetidas de títulos, preservando precedência e retornos.
- Referência local da área azul da tela principal, medida no Windows;
  retorno exige foco, cabeçalho e duas capturas compatíveis.
- Lote calibrado interrompe diante de retorno desconhecido/referência
  inválida ou removida, preservando resultados já registrados. A entrada
  permite voltar ao Domínio antes do primeiro F8, sem clique/tecla remota.
- Histórico da GUI preserva o resultado falso de SPED/Contribuições.
- Catálogo descritivo das quatro funções, consultável sem executar nada.
  Agentes operadores gerais continuam desabilitados.
- [Prompt para componentes Hugging Face](PROMPT-DESENVOLVIMENTO-HUGGING-FACE.md)
  e [pesquisa oficial](HUGGING-FACE-COMPONENTES.md), com avaliação de OCR
  opcional. A rotina de produção continua usando o OCR existente.

## Primeiro teste ao voltar

1. Rode `Atualizar.bat` e confira que terminou sem erro.
2. Deixe o Domínio maximizado na tela principal azul, sem relatório,
   diálogo ou menu aberto. Essa condição precisa ser conferida por você.
3. Rode `Calibrar Tela Principal.bat`. Pressione Enter quando solicitado
   e volte ao Domínio com Alt+Tab. Aguarde sem mover mouse/teclado.
4. Confira a mensagem `Referência local salva em data/tela_principal.json`.
   O arquivo contém somente tamanho, retângulo e cor. Uma falha de
   medição não substitui uma referência anterior válida.
5. Repita a rotina de Saídas já testada, na empresa correta e em uma
   competência cuja apuração esteja fechada. Guarde o log local.

A falha de período no PDF continua pendente, por sua decisão anterior.
Ela pode reaparecer. O teste agora é a recuperação: deve continuar
registrando falha em `conferir_pdf`, e só registrar
`recuperar_interface: confirmado (tela_principal_reconhecida)` se a
referência for reconhecida. Confira também visualmente o retorno.
Retornar à interface não transforma a conferência do PDF em sucesso.

Com referência ausente, o fluxo supervisionado anterior continua e avisa.
Com referência existente e inválida/divergente, o retorno fica
inconclusivo e o lote para. Uma comparação só cobre o retângulo medido;
janelas fora dessa área podem exigir verificações adicionais. Recalibre
quando mudar resolução/tamanho da sessão. Não reduza os critérios só
para aceitar uma captura sem entender a divergência.

Depois desse teste, revalide SPED Fiscal e EFD Contribuições individualmente
em competência já fechada. Confira as novas etapas e o retorno. Só então
teste lote supervisionado, verificando documento/empresa no resumo. Ao
iniciar lote calibrado, volte ao Domínio por Alt+Tab se solicitado.

## Avaliar OCR do Hugging Face

`Atualizar.bat` entrega os scripts, mas uma instalação inicial de modelos
opcionais precisa ser solicitada pelo operador. Use `Instalar OCR Paddle.bat`
para o primeiro candidato em CPU. Ele cria `.venv-ocr-paddle` dentro deste
mesmo projeto, preservando as dependências usadas pelo SPED, e baixa somente
o detector móvel e o reconhecedor latino PP-OCRv5 de revisões fixadas do
Hugging Face. Não instala PaddleOCR-VL nem habilita um novo motor padrão.
Requer Windows x64 e Python 3.10–3.13 (3.12 recomendado). O instalador
mostra versão/arquitetura e procura um Python compatível no ambiente OCR
existente, no launcher `py` ou nos diretórios padrão de instalação por
usuário, mesmo se `python` no PATH for 3.14.
Se não encontrar, use `Instalar Python OCR.bat`: o operador solicita
explicitamente a instalação de Python 3.13 x64 via winget, para seu usuário,
sem alterar PATH, launcher ou associações de arquivos. Após confirmar o
novo intérprete, o atalho prepara o ambiente OCR. Se winget falhar ou o
intérprete não for confirmado, interrompe antes de instalar o OCR.
Se winget não estiver disponível, instale Python 3.12/3.13 de 64 bits
lado a lado, mantendo PATH e launcher, e repita `Instalar OCR Paddle.bat`.
Download oficial: <https://www.python.org/downloads/windows/>.
Depois da primeira instalação, `Atualizar.bat` também atualiza o componente
opcional. Sem o marcador local, atualizações não instalam Paddle.

Depois use `Avaliar OCR Paddle.bat` e escolha uma captura local. A avaliação
compara leitura e tempo; não controla o Domínio. Para conferir uma âncora,
consulte `scripts/avaliar_ocr_paddle.py --help` e use `--alvo`. O resumo
não publica texto fiscal. Qualidade real e localização devem ser conferidas
no conjunto de telas usado pelo SPED, não deduzidas apenas pelo tempo.
As primeiras execuções podem demorar mais por carregar o modelo.

Para testar percepção na tela real, use `Avaliar OCR Tela.bat`. Abra a
tela do Domínio desejada, pressione Enter no Prompt e volte ao Domínio
com Alt+Tab. Aguarde alguns segundos pela captura; depois volte ao Prompt
para acompanhar as três leituras por motor. A captura permanece só em
memória. O script exige a mesma janela ativa antes e depois de capturar;
aceita título Domínio ou cliente GO-Global sem título. Confira visualmente
o conteúdo do cliente remoto: a classe sozinha não identifica seu estado.
Não há clique, digitação, execução de rotina ou troca do OCR de produção.

Cada leitura imprime início e conclusão. Uma mensagem Windows de busca
de arquivo pode vir da procura de `ccache` opcional pelo Paddle; aguarde
o resultado da etapa. Ctrl+C agora é registrado como cancelamento com
código 130. A primeira avaliação foi interrompida; a rodada seguinte
concluiu em 07/10/2026 com os resultados abaixo.

| Motor CPU | Primeira leitura | Duas aquecidas | Segmentos por leitura |
| --- | --- | --- | --- |
| PP-OCRv5 mobile | 24,751s | 14,309s / 15,802s | 32 |
| Tesseract por | 0,935s | 0,623s / 0,576s | 35 |

Paddle levou aproximadamente 25 vezes mais tempo nas leituras aquecidas
dessa captura. A quantidade de segmentos não mede acerto; não foi usado
alvo de texto e RAM não foi medida. A mensagem de busca Windows apareceu,
mas não impediu a conclusão. **Manter Tesseract no fluxo atual.** Não
instalar outros modelos antes de revalidar estados/retorno do SPED.

A próxima execução é calibrar a tela principal azul e testar SPED Fiscal
individualmente em competência fechada, conferindo documento e retorno.
Paddle fica disponível para comparação de telas em que o OCR atual falha,
sem adoção automática. A nuvem não acessa seu desktop. O prompt define
critérios para integrar somente após regressão e ganho demonstrados.
Resolução de dependências para Windows x64/Python 3.12 passou em dry-run;
isso confirmou resolução; a rodada do operador acrescenta inferência CPU
concluída, sem confirmar precisão nem a seleção de intérprete por si só.

## O que falta para concluir o incremento atual

Calibração e retorno automático validados no Windows; revalidação das
etapas SPED/Contribuições; lote supervisionado com falha isolada sem
contaminar o próximo documento/empresa; resultado/conteúdo final conferido.
Conferência de período e nome dos PDFs permanece pausada e é uma pendência
explícita. O catálogo é preparação do incremento 3, sem executor de agentes.
