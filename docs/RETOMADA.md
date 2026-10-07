# Retomada do projeto — 07/10/2026

O trabalho atual é o incremento **2: consolidar execução e recuperação**
do [roadmap RPA](ROADMAP-RPA.md). O documento `00-analise-e-plano-fase0.md`
é o histórico do projeto; seu nome não significa que todo desenvolvimento
continua na fase de descoberta. O plano original tem dez fases (0–9);
o roadmap RPA organiza o trabalho atual em seis incrementos.

Validação desta entrega: **146 testes locais/simulados passaram**,
compilação dos arquivos Python alterados e checagem de diff passaram.
Os testes não operaram a sessão real do Domínio. Separadamente, PP-OCRv5
foi carregado e executado em CPU/Linux sobre imagem sintética, com caixas
válidas. Os próximos passos abaixo produzem a evidência Windows.

## O que foi preparado

- Acompanhamento por etapas nas quatro rotinas conhecidas, com marcadores
  de evidência e logs locais; erro, ação enviada e estado confirmado são
  diferenciados.
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
Requer Windows x64 e Python 3.10–3.13 (3.12 recomendado). Depois da
primeira instalação, `Atualizar.bat` também atualiza o componente
opcional. Sem o marcador local, atualizações não instalam Paddle.

Depois use `Avaliar OCR Paddle.bat` e escolha uma captura local. A avaliação
compara leitura e tempo; não controla o Domínio. Para conferir uma âncora,
consulte `scripts/avaliar_ocr_paddle.py --help` e use `--alvo`. O resumo
não publica texto fiscal. Qualidade real e localização devem ser conferidas
no conjunto de telas usado pelo SPED, não deduzidas apenas pelo tempo.
As primeiras execuções podem demorar mais por carregar o modelo.

Instalação/inferência Paddle no Windows e ganho sobre o OCR atual ainda
precisam de medição local. A nuvem não acessa seu desktop. O prompt define
critérios para integrar somente após regressão e ganho demonstrados.
Resolução de dependências para Windows x64/Python 3.12 passou em dry-run;
isso confirma resolução, sem comprovar execução dos modelos no Windows.

## O que falta para concluir o incremento atual

Calibração e retorno automático validados no Windows; revalidação das
etapas SPED/Contribuições; lote supervisionado com falha isolada sem
contaminar o próximo documento/empresa; resultado/conteúdo final conferido.
Conferência de período e nome dos PDFs permanece pausada e é uma pendência
explícita. O catálogo é preparação do incremento 3, sem executor de agentes.
