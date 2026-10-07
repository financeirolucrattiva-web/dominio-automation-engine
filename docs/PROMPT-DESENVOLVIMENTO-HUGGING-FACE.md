# Instrução para continuar o Domínio Automation Engine com Hugging Face

Copie o texto abaixo para o assistente que continuará o desenvolvimento.
As referências descrevem o projeto atual; capacidades futuras precisam
de implementação e evidência antes de serem consideradas disponíveis.

---

Continue o desenvolvimento do **Domínio Automation Engine neste mesmo
repositório**, tornando a ferramenta existente robusta e utilizável.
Use Hugging Face como fonte de componentes para resolver problemas
concretos do motor. Não crie outro produto, laboratório de IA, projeto
de pesquisa ou arquitetura paralela.

## 1. Entenda o projeto antes de alterar código

Leia `CLAUDE.md`, `.claude/agents/automacao-dominio.md`,
`docs/HANDOFF.md`, `docs/00-analise-e-plano-fase0.md`,
`docs/ROADMAP-RPA.md` e `docs/RETOMADA.md`. Confira também o estado do
Git: outro assistente pode estar trabalhando neste repositório.
Preserve alterações existentes e publique sem sobrescrever trabalho.

Mapeie a estrutura, os pontos de entrada e as assinaturas utilizadas
pela interface e pelos scripts. Examine especialmente:

- `app/tela.py`: captura, recortes, escalas, Tesseract, OCR nativo do
  Windows, OpenCV e fingerprint;
- `app/dominio.py` e `app/interacao.py`: navegação, foco, SPED Fiscal,
  EFD Contribuições, Livros Fiscais e lote;
- `app/estados.py` e `app/tela_principal.py`: espera por estado,
  evidências de execução e referência local de retorno;
- `app/arquivos.py`, `app/erros.py`, `app/ia.py`, `app/visao.py`,
  `app/historico.py`, `app/capacidades.py`, `scripts/gui.py` e `tests/`.

Identifique o que foi observado no Windows, o que passou apenas em
testes simulados e o que continua pendente. Não reescreva as rotinas que
funcionam para encaixá-las num framework novo. A pendência de conferência
do período/nome do PDF foi pausada pelo usuário; mantenha essa decisão
até receber orientação para retomá-la. Não desative a validação para
fazer o resultado aparecer como sucesso.

## 2. Preserve a rotina SPED e o comportamento atual

Rode os testes existentes antes das mudanças. Acrescente regressões
relevantes para seleção e confirmação do período, navegação conhecida,
aviso de geração, erro/timeout, nova tentativa, retorno à interface e
propagação de `False` para o histórico. Preserve assinaturas, formatos
de retorno, fallback, limites de espera e o contrato dos chamadores.

Uma leitura de OCR, um clique, um arquivo existente ou uma resposta de
modelo não comprovam sucesso. Confirme o efeito com a evidência da
etapa correspondente. Nunca avance automaticamente de um estado
desconhecido para outra empresa/documento.

Testes de lógica e regressão na nuvem não comprovam funcionamento no
Domínio. A aprovação operacional exige log e verificação no Windows.

## 3. Respeite a restrição real da interface

Neste ambiente o Domínio é entregue por **GraphOn GO-Global**. A árvore
de controles de Windows UI Automation/Win32 foi investigada e não está
disponível para os controles internos do aplicativo.

Use captura + OCR/OpenCV para percepção e as primitivas existentes de
mouse/teclado para ação. Win32 pode identificar e conferir foco da janela
externa; isso não permite acessar campos internos por ID. Não retome
tentativas de UI Automation para esta sessão sem nova evidência de
mudança no ambiente. Em uma futura interface nativa, avalie acessibilidade
somente onde ela for demonstrada.

## 4. Use Hugging Face de forma incremental

Consulte fontes oficiais e registre modelo, ID, revisão, licença,
dependências e documentação. A disponibilidade no Hub não comprova
compatibilidade com Windows ou qualidade nas telas do Domínio.

Prioridades:

1. **Tesseract:** continue como padrão durante a avaliação e preserve
   como fallback após qualquer integração. Preserve também o OCR do
   Windows já existente.
2. **PP-OCR/PaddleOCR:** primeiro candidato para texto pequeno em
   português e localização por caixas/polígonos. Avalie uma configuração
   apropriada, começando pelo detector móvel PP-OCRv5 e reconhecimento
   latino com suporte documentado a português; não instale toda a família.
3. **PaddleOCR-VL-1.6:** avalie somente se houver uma dificuldade de
   percepção/documento que justifique seu custo. Verifique o ID oficial
   `PaddlePaddle/PaddleOCR-VL-1.6` e seus requisitos atuais. Um parser de
   documentos não é automaticamente um localizador confiável de botões.
4. **Layout:** use apenas se melhorar uma localização que o sistema
   realmente precisa. Classes de documento não equivalem a controles GUI.
5. **Visão/VLM:** último recurso após OCR/OpenCV disponíveis falharem;
   apenas percepção estruturada, nunca autorização para inventar ações.
6. **Embeddings/classificadores:** somente com problema, entrada e
   critério de resultado definidos, como classificar estados conhecidos.

Escolha e avalie **um candidato por vez**. Dependências/modelos opcionais
não entram na instalação padrão antes de demonstrar utilidade. Ausência
do componente, falha de carregamento, timeout ou resultado incerto devem
permitir fallback ou interrupção controlada. Não baixe pesos nem inicialize
um modelo pesado a cada leitura. Fixe versões/revisões para reproduzir a
configuração aprovada.

Use modelos locais após download dos componentes. Não envie capturas,
documentos, nomes ou texto fiscal para Hugging Face Spaces, Inference
Endpoints, APIs públicas ou uploads de datasets. A disponibilidade de
uma API remota não altera as regras existentes de dados do projeto.

## 5. Compare com o atual em tarefas reais

Faça a avaliação dentro deste projeto, em ferramenta local que **somente
lê imagens**, sem clicar ou digitar no Domínio. Reutilize os mesmos
recortes e tarefas da automação. As capturas reais e suas anotações ficam
locais, fora do Git; publique apenas resultados agregados sem dados de
clientes. Testes sintéticos devem ser identificados como sintéticos.

Já há um ponto de partida opcional: `Instalar OCR Paddle.bat` e
`Avaliar OCR Paddle.bat`. Ele lê uma imagem local, compara contagem,
ocorrência de âncora e uma leitura inicial/duas aquecidas. Não controla
ações e não mede precisão geral, RAM ou p50/p95. Reaproveite esse
instrumento, ampliando-o apenas para uma tarefa/medida necessária;
não o apresente como aprovação do candidato nas telas do Domínio.

Meça para a configuração exata e para o computador testado:

- leitura correta de menus, datas, nomes e avisos; erros/omissões de texto;
- identificação do alvo correto e posição válida na captura original,
  incluindo conversão de escala e deslocamento de recorte;
- estados confundidos, falsos positivos e leituras ambíguas;
- latência de inicialização e execução, p50/p95 e duração do fluxo;
- RAM/VRAM observadas, CPU/GPU usadas e versão do Windows/Python;
- instalação, estabilidade, falhas, licença e custo de manutenção.

Não compare diretamente scores de confiança de motores distintos: eles
não têm a mesma calibração. Não escolha um vencedor por benchmark de
documentos genéricos, downloads, popularidade ou texto mais bonito.
Precisão de âncora e confirmação de estado importam para a ação.

Se não houver capturas ou acesso ao Windows, entregue a avaliação local
pronta para rodar e marque o desempenho no Domínio como **não medido**.
Não invente números nem declare a troca aprovada.

## 6. Integre somente com ganho demonstrado

Adicione o componente como backend opcional na percepção existente,
preservando as funções chamadas pelas rotinas. Normalize texto, caixas,
coordenadas, origem da leitura e indicação de incerteza. Falhas de
dependência/execução devem ter diagnóstico claro e fallback testado.

Comece comparando leituras sem que o candidato controle ações. Promova-o
apenas depois de ganho na tarefa definida, regressões passando e execução
supervisionada do SPED no Windows. Permita retornar à configuração
anterior. Se não houver ganho suficiente, mantenha o backend atual e
documente o resultado. Não prometa melhora de um problema de validação
de PDF só por trocar o OCR da tela.

## 7. Evolua a arquitetura existente

Reaproveite os módulos e contratos atuais:

```text
Domínio via GO-Global
↓
Perception: captura + OCR + OpenCV + visão local quando justificada
↓
State Engine: estado observado, evidência, limites e incerteza
↓
Decision Engine: regras/capacidades conhecidas e decisões restritas
↓
Action Engine: foco confirmado + mouse/teclado existentes
↓
Validation: conferir o efeito e o resultado
↓
Recovery: estratégia conhecida + verificar retorno
↓
Resultado: sucesso, falha ou pendência com evidência
```

OCR e modelos observam; o executor controla ações. Não introduza agentes
operadores gerais antes de estabilizar as rotinas e o catálogo. Novas
funções aprendidas por demonstração precisam de revisão, parâmetros,
verificações e validação antes de serem disponibilizadas. Uma sessão de
desktop admite um executor por vez.

Continue o incremento atual de execução/recuperação do roadmap. Gere e
leia somente competências cuja apuração esteja fechada; mês anterior no
calendário não comprova isso. Transmissão, retificação, exclusão e
apuração automática não estão neste escopo.

## 8. Entregue trabalho concreto e revisável

Na primeira entrega, apresente o mapa do projeto e baseline, a dificuldade
que o candidato tentará resolver, uma avaliação local reproduzível e
regressões pertinentes. Integre somente quando os critérios acima forem
atendidos. Não instale dezenas de modelos por precaução.

Em cada entrega informe o que mudou, os testes executados, quais modelos
foram apenas pesquisados/quais foram executados, a evidência de ganho e
o teste Windows ainda necessário. Atualize README, handoff e histórico.
Trabalhe em mudanças pequenas, faça commit/push conforme a autorização
da sessão e confira a versão remota antes de publicar, pois Codex e
Claude Code podem trabalhar juntos. Nunca sobrescreva trabalho concorrente.
