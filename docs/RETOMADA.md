# Retomada do projeto — 09/10/2026

## Próximo piloto: Lucro Presumido

Nesta entrega o servidor prepara Lucro Presumido/Real com Resumo por
Acumulador, Demonstrativo EFD Contribuições, Entradas, Saídas e Livro Fiscal
de ICMS. Atualizar/reiniciar o servidor após integrar a alteração e Ctrl+F5
no cliente. Cadastros real/simulado continuam separados. Conferir nomes,
regimes e empresas no banco do modo escolhido; não copiar empresas reais
para a nuvem nem inventar códigos. Regimes existentes preservam sua
sequência, com o vínculo ICMS acrescentado uma vez.

No painel, cadastrar pelo nome → adicionar ao regime → Configurar →
Salvar configuração → Enviar para validação. O envio marca uma pendência;
não aprova ou libera roteiro novo no executor. Configurações desses novos
cadastros ficam no SQLite; gravador JSON legado continua disponível.
Faltam mapear as telas de Resumo, Demonstrativo e ICMS e integrar o teste,
aprovação formal e execução remota de versões validadas.

Teste real da nova regra: emissão falha numa rotina integrada, retorno por
Esc até o painel azul e continuação na próxima rotina, preservando a falha.
Confirmar empresa, foco, documento, período e o resultado “Finalizado com
falhas”. Se não reconhecer o painel azul/empresa, interrompe. Confirmar
também cancelamento durante recuperação e ausência de repetição de emissão.
Tratamento de OK/Fechar continua o que já existe nas rotinas; qualquer
diálogo diferente precisa de mapeamento real, sem supor coordenadas.

O planejamento para gestores está em [ROADMAP-GESTAO.md](ROADMAP-GESTAO.md).
O checkpoint abaixo conserva as evidências e os testes da entrega anterior.

Organização dos arquivos: os três instaladores principais e `Atualizar.bat`
continuam na raiz. Os outros 17 atalhos estão em `atalhos/servidor/`,
`atalhos/interface/`, `atalhos/ocr/` e `atalhos/ferramentas/`.
Nenhuma função foi removida. Consulte o [índice](../atalhos/README.md).
Não precisa reinstalar aplicativos para receber esta organização.

## Site e servidor dedicado

O pedido atual é concluir pausa, calendário e login pelo site; em seguida
configurar lotes por empresas/regime e rotinas. Agendamento é futuro.
A interface web/PWA foi preparada no mesmo projeto, com conexão por
chave, envio de tarefas, etapas e histórico persistido no servidor.
O usuário informou que o servidor está pronto, mas o Domínio ainda não.
Não houve implantação nem execução fiscal nessa máquina.

Para testar o site: `Atualizar.bat` → `Instalar Servidor.bat` →
`atalhos/servidor/Testar Interface Servidor.bat`. Consulte
[SERVIDOR-E-INTERFACE.md](SERVIDOR-E-INTERFACE.md) para abrir a interface,
conectar, instalar no PC e configurar execução/HTTPS no servidor.
O teste simulado não acessa o Domínio nem gera documento fiscal.

Dois instaladores disponíveis para a mesma rede: `Instalar Servidor.bat`
no PC com Domínio e `Instalar Interface.bat` no outro PC, usando o pacote
gerado em `data/rede_local/interface_cliente`. Cliente recebe endereço
e certificado público, cria atalho em janela Edge/Chrome e entra com a
chave do servidor. Python/OCR/Domínio ficam no servidor.
O instalador do servidor pergunta acesso local ou rede; para o teste
anterior no próprio PC, escolha 1. Para outro PC na rede, escolha 2.
Siga o guia para a regra de firewall e `atalhos/servidor/Testar Interface na Rede.bat`.
O PC atual com Domínio pode ser servidor temporário. HTTPS/certificados
passaram em testes locais; atalho, confiança e firewall exigem teste Windows.

Na entrega dos instaladores, **253 testes locais/simulados passaram**, incluindo
cadeia de certificados, TLS real, pacote público e preservação de confiança.

Na entrega inicial (244 testes), Chromium conferiu login,
envio e conclusão da nova tarefa simulada, etapas, histórico, logout,
offline e visual em 1440/900/390 pixels. A GUI local foi renderizada
com backend fiscal bloqueado; o ciclo Tk com worker simulado também
foi conferido. Isso não valida operação fiscal real no Windows.

As alterações de gravação/digitação/hover e aprovação trazidas pelo
Claude foram integradas. A GUI mantém a gravação/revisão local;
rotinas gravadas não são executadas automaticamente pelo site.

## Teste dos novos controles

1. No PC servidor, `Atualizar.bat` e reabra
   `atalhos/servidor/Executar Dominio na Rede.bat`. No cliente, Ctrl+F5.
2. Escolha empresa já selecionada e competência passada/apuração fechada;
   o calendário não tem data automática. Teste SPED Fiscal individual.
3. Na tarefa ativa, Pausar execução → aguarde Execução pausada → Continuar.
   A mesma tarefa deve terminar, com documento e retorno conferidos.
4. Acesso ao Domínio e recuperação do servidor reúne login/código,
   Cancelar login, Reiniciar ciclo, Ver tela e Calibrar tela principal.
   Senhas são informadas no formulário, não neste chat, e não são salvas.
5. Para primeira calibração remota, confira a captura da tela azul,
   confirme a caixa e calibre. Para login completo, acompanhe a etapa,
   informe o código de e-mail no painel e confira o retorno à tela azul.
6. Configurar novas rotinas salva rascunhos no catálogo do gravador.
   Revisão/teste/aprovação continuam no fluxo existente; não entram no
   executor remoto automaticamente. Lote remoto por regime vem depois,
   com teste real de troca de empresa e isolamento dos resultados.

O servidor precisa de sessão Windows gráfica desbloqueada. Nuvem testou
lógica, API e navegador com fiscal/login externos simulados; não testou
Onvio autenticado, GO-Global ou conteúdo fiscal real dessa entrega.

## Execução e recuperação

O trabalho atual é o incremento **2: consolidar execução e recuperação**
do [roadmap RPA](ROADMAP-RPA.md). O documento `00-analise-e-plano-fase0.md`
é o histórico do projeto; seu nome não significa que todo desenvolvimento
continua na fase de descoberta. O plano original tem dez fases (0–9);
o roadmap RPA organiza o trabalho atual em seis incrementos.

Validação da entrega anterior: **196 testes locais/simulados passaram**,
compilação dos arquivos Python alterados e checagem de diff passaram.
Os testes não operaram a sessão real do Domínio. Separadamente, PP-OCRv5
foi carregado e executado em CPU/Linux sobre imagem sintética, com caixas
válidas. Em 07/10/2026, o operador também concluiu as seis leituras de
uma captura atual no Windows; isso valida inferência local, sem validar
precisão, estados ou execução fiscal com Paddle.

## O que foi preparado

- Interface com Painel de execução, Rotinas, Funções disponíveis,
  Histórico, Projeto e Log. Eventos estruturados mostram etapa, tempo,
  confirmação e retorno; uma recuperação não transforma a falha original
  em sucesso. A prévia visual usa eventos simulados, não execução fiscal.
- Aba Projeto abre calibração/comparação OCR em um Prompt separado e
  mantém o resultado visível até Enter. Enquanto a ferramenta estiver
  aberta, novas execuções ficam bloqueadas para não disputar a sessão.
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

## Próximo teste no Windows

**Calibração concluída em 07/10/2026:** o operador recebeu
`Referência local salva em data/tela_principal.json`, captura 1440×900,
área azul `[0, 128, 1377, 823]` e código de saída 0. Somente medidas e
cor ficaram na máquina; nenhuma captura foi salva ou publicada.
Isso confirma a preparação da referência, ainda sem testar o retorno
automático após uma rotina fiscal.

1. Pressione Enter no Prompt da ferramenta para voltar à interface.
   Não é necessário recalibrar mantendo o mesmo tamanho da sessão.
2. Confira a empresa selecionada no Domínio e deixe a tela principal
   azul visível, sem relatório, diálogo ou menu aberto.
3. Na aba Rotinas, execute **Gerar SPED Fiscal** individualmente.
   O gerador seleciona o mês anterior à data do computador; confirme
   antes que a apuração desse período está fechada.
4. Aguarde sem mexer no mouse/teclado. Ao término, confira o documento,
   os estados no Painel e o retorno visual à tela principal.
5. Guarde o log da aba Log ou `data/ultimo_log.txt`. Para retorno
   confirmado, procure `[estado] encerrar: confirmado
   (tela_principal_reconhecida)`; sucesso da rotina deve registrar
   `[estado] fim: concluido (rotina_concluida)`. Se falhar, preserve
   o log com a etapa e a evidência, sem declarar o teste aprovado.

A falha de período no PDF continua pendente, por sua decisão anterior.
Ela pode reaparecer quando repetir Saídas. Nesse teste de recuperação,
deve continuar registrando falha em `conferir_pdf`, e só registrar
`recuperar_interface: confirmado (tela_principal_reconhecida)` se a
referência for reconhecida. Confira também visualmente o retorno.
Retornar à interface não transforma a conferência do PDF em sucesso.

Com referência ausente, o fluxo supervisionado anterior continua e avisa.
Com referência existente e inválida/divergente, o retorno fica
inconclusivo e o lote para. Uma comparação só cobre o retângulo medido;
janelas fora dessa área podem exigir verificações adicionais. Recalibre
quando mudar resolução/tamanho da sessão. Não reduza os critérios só
para aceitar uma captura sem entender a divergência.

Depois do SPED, revalide EFD Contribuições individualmente na empresa
correta e em competência já fechada; esse gerador também seleciona o
mês anterior. Confira etapas, documento e retorno. Saídas/Entradas
continuam com a pendência PDF explícita. Lote não é requisito para o
próximo teste nem prioridade atual. Se retomado depois, precisa de
validação supervisionada separada por documento/empresa.

## Avaliar OCR do Hugging Face

`Atualizar.bat` entrega os scripts, mas uma instalação inicial de modelos
opcionais precisa ser solicitada pelo operador. Use `atalhos/ocr/Instalar OCR Paddle.bat`
para o primeiro candidato em CPU. Ele cria `.venv-ocr-paddle` dentro deste
mesmo projeto, preservando as dependências usadas pelo SPED, e baixa somente
o detector móvel e o reconhecedor latino PP-OCRv5 de revisões fixadas do
Hugging Face. Não instala PaddleOCR-VL nem habilita um novo motor padrão.
Requer Windows x64 e Python 3.10–3.13 (3.12 recomendado). O instalador
mostra versão/arquitetura e procura um Python compatível no ambiente OCR
existente, no launcher `py` ou nos diretórios padrão de instalação por
usuário, mesmo se `python` no PATH for 3.14.
Se não encontrar, use `atalhos/ocr/Instalar Python OCR.bat`: o operador solicita
explicitamente a instalação de Python 3.13 x64 via winget, para seu usuário,
sem alterar PATH, launcher ou associações de arquivos. Após confirmar o
novo intérprete, o atalho prepara o ambiente OCR. Se winget falhar ou o
intérprete não for confirmado, interrompe antes de instalar o OCR.
Se winget não estiver disponível, instale Python 3.12/3.13 de 64 bits
lado a lado, mantendo PATH e launcher, e repita `atalhos/ocr/Instalar OCR Paddle.bat`.
Download oficial: <https://www.python.org/downloads/windows/>.
Depois da primeira instalação, `Atualizar.bat` também atualiza o componente
opcional. Sem o marcador local, atualizações não instalam Paddle.

Depois use `atalhos/ocr/Avaliar OCR Paddle.bat` e escolha uma captura local. A avaliação
compara leitura e tempo; não controla o Domínio. Para conferir uma âncora,
consulte `scripts/avaliar_ocr_paddle.py --help` e use `--alvo`. O resumo
não publica texto fiscal. Qualidade real e localização devem ser conferidas
no conjunto de telas usado pelo SPED, não deduzidas apenas pelo tempo.
As primeiras execuções podem demorar mais por carregar o modelo.

Para testar percepção na tela real, use `atalhos/ocr/Avaliar OCR Tela.bat`. Abra a
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

A referência da tela principal já foi calibrada no Windows. A próxima
execução é testar SPED Fiscal individualmente em competência fechada,
conferindo documento e retorno.
Paddle fica disponível para comparação de telas em que o OCR atual falha,
sem adoção automática. A nuvem não acessa seu desktop. O prompt define
critérios para integrar somente após regressão e ganho demonstrados.
Resolução de dependências para Windows x64/Python 3.12 passou em dry-run;
isso confirmou resolução; a rodada do operador acrescenta inferência CPU
concluída, sem confirmar precisão nem a seleção de intérprete por si só.

## O que falta para concluir o incremento atual

Retorno automático usando a referência calibrada validado no Windows;
revalidação individual das etapas SPED/Contribuições e conteúdo final
conferido. Para o servidor dedicado, configurar o Domínio, calibrar
na própria sessão e validar esse mesmo ciclo pela interface conectada.
Lote fica adiado por prioridade expressa do usuário.
Conferência de período e nome dos PDFs permanece pausada e é uma pendência
explícita. O catálogo é preparação do incremento 3, sem executor de agentes.

## Caminho para a entrega final

O visual desta entrega foi renderizado em tela virtual Linux, em
1120×780 e 900×640, com backend fiscal bloqueado e eventos simulados.
Falta conferir a aparência e as execuções na instalação Windows.
Para a GUI local não há modelo adicional. O site usa as dependências
opcionais de `requirements-servidor.txt`, instaladas pelo novo atalho.

A sequência até o RPA completo permanece no [roadmap](ROADMAP-RPA.md):
consolidar execução/retorno individual; validar o catálogo executável;
evoluir demonstrações para propostas com campos/estados e revisão;
dar tarefas aos agentes usando capacidades validadas e uma fila por
sessão; medir as execuções e ampliar autonomia gradualmente. O painel
torna o andamento visível, mas não declara essas etapas concluídas.
A interface conectada foi preparada antes da autonomia dos agentes;
seu visual e API não substituem a validação das rotinas no servidor.
