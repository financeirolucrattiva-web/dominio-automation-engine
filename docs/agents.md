# Agentes

Cada agente é uma função TypeScript em `src/agents/`, não um framework de agente
genérico. Isso é deliberado: dá para ler o prompt e o parsing de cada um em um
arquivo só, e testar sem mockar uma abstração extra.

Padrão comum (seção 42 do briefing): toda chamada de agente passa por
`callAgent()` (`src/lib/claude.ts`), que:
- lança erro se `ANTHROPIC_API_KEY` não estiver configurada (nunca simula resposta);
- registra o custo real em `AIUsage` (tokens de entrada/saída × tabela de preço em
  `PRICING_USD_PER_MTOK`, nunca um valor inventado);
- para o Research Agent, usa a ferramenta `web_search` server-side da Anthropic —
  pesquisa de verdade, não o modelo "lembrando" fatos.

Todo agente termina registrando o que fez em `ActivityLog` (`src/lib/activityLog.ts`)
— é o que alimenta a seção "O que o agente fez" do dashboard.

## Research Agent (`src/agents/research.ts`)

- **Input**: `Campaign` (briefing).
- **Output**: `ResearchResult[]` gravados no banco.
- **Modelo**: `CLAUDE_MODEL_RESEARCH` (padrão `claude-sonnet-5` — precisa suportar a
  tool `web_search_20260209`).
- **Permissões**: lê a campanha, pesquisa na web, grava pesquisa. **Nunca publica
  conteúdo.**
- Cada resultado é categorizado como `FACTUAL` (confirmado numa fonte real, com URL),
  `INFERRED` (dedução do agente) ou `RECOMMENDATION` — nunca apresentados misturados.

## Strategy Agent (`src/agents/strategy.ts`)

- **Input**: `Campaign` + `ResearchResult[]`.
- **Output**: um `StrategyPlan` (público, mensagem central, funil, calendário, KPIs,
  sugestão de orçamento, plano de contingência).
- **Modelo**: `CLAUDE_MODEL_STRATEGY` (padrão `claude-sonnet-5`).
- Todo número que for estimativa vem marcado `isEstimate: true` no JSON — o prompt
  proíbe explicitamente inventar benchmark como se fosse fato.

## Content Agent (`src/agents/content.ts`)

- **Input**: o `StrategyPlan` mais recente.
- **Output**: até 8 `ContentItem` por rodada (limite de custo — REGRA 38), status
  `PENDING_APPROVAL`, mais uma `Approval` de nível `ASSISTED` por item.
- **Modelo**: `CLAUDE_MODEL_CONTENT` (padrão `claude-sonnet-5`).
- O system prompt carrega a identidade de marca (cores, tom de voz) — mesma fonte de
  `src/lib/brand.ts` — e proíbe a grafia "Lucrativa" (a marca real é **Lucrattiva**,
  com dois T).

## Creative Agent (`src/agents/creative.ts`)

- **Input**: um `ContentItem` já com título/gancho/CTA.
- **Output**: um `CreativeAsset` com briefing visual estruturado + imagem.
- **Não chama LLM** para montar o briefing — deriva direto dos campos do
  `ContentItem` (regra > modelo, REGRA 38). Só a geração da imagem em si passa por
  `generateImage()` (`src/lib/imageProvider.ts`), que:
  - sem `IMAGE_PROVIDER` configurado, gera um **placeholder de marca local** (SVG),
    etiquetado `provider: "mock"` em todo lugar que a UI mostra a imagem;
  - com `IMAGE_PROVIDER=openai` + `IMAGE_PROVIDER_API_KEY`, chama a API de imagens da
    OpenAI de verdade. Ver `docs/integrations.md`.

## Tracking Agent (`src/agents/tracking.ts`)

- **Cálculo puro, sem LLM** (REGRA 38 — UTM e QR Code não precisam de modelo).
- Para cada canal do briefing, cria um `TrackingLink` com UTM embutido e um código
  curto (`/r/<code>`). Canais físicos (flyers, cartazes, rádio, parceiros, eventos
  presenciais) também ganham um `QRCode`.

## Orchestrator (`src/agents/orchestrator.ts`)

`confirmAndRunCampaign(campaignId)` roda a sequência Research → Strategy → Content →
Creative → Tracking. Cada estágio é isolado: se um agente de IA falhar (tipicamente
por falta de `ANTHROPIC_API_KEY`), o erro é registrado, uma tarefa humana explicando o
bloqueio é criada, e o pipeline **continua** para o próximo estágio que não depende
dele — o Tracking Agent, por exemplo, sempre roda. A campanha nunca fica travada
silenciosamente (REGRA 8/9).

## Chat / Copiloto (`src/agents/chat.ts`)

Não é um chatbot genérico — todo turno recebe o estado atual do briefing e contadores
reais (leads, inscritos, tarefas pendentes, aprovações pendentes) como contexto, e
pode devolver `extractedFields` para preencher o formulário automaticamente. Nunca
extrai um campo que o usuário não disse explicitamente (o prompt proíbe isso) e nunca
inventa uma métrica que não veio do banco.

## Agentes descritos no briefing original e ainda não implementados

Ads Agent, WhatsApp Agent, Physical Marketing Agent, Partner Management e
Optimization Agent estão no schema (`Partner`, os campos de orçamento por canal) mas
sem agente de IA dedicado ainda — ver Fase 2/3 em `docs/campaigns.md`. Não foram
simulados: a intenção do briefing é explícita em não fingir integração que não existe
(REGRA 12), e nenhum deles tem uma API real conectada nesta entrega.
