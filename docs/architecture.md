# Arquitetura

## Origem deste projeto

Este repositório é uma evolução do **Agente de Redes Sociais da Lucrattiva** original
(um único Claude Managed Agent + um painel HTML, vivos no commit `8fb9d15` de
`dominio-automation-engine`, removidos de lá em 18/09/2026 quando o escritório separou
o motor de automação fiscal do resto). A identidade visual (verde `#1D4429`, dourado
`#A97829`/`#C79A45`, tipografia Fraunces/Inter, tom de voz caloroso) foi recuperada
diretamente daquele agente — ver `src/lib/brand.ts`.

A diferença: aquele agente era um único Managed Agent gerando conteúdo diário. Este
projeto é uma aplicação web completa — banco de dados, orquestrador, múltiplos agentes
especializados e um dashboard — porque o objetivo deixou de ser "postar todo dia" e
passou a ser "gerenciar e automatizar a campanha inteira" (briefing → pesquisa →
estratégia → conteúdo → criativo → rastreamento → leads → métricas).

## Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Framework | Next.js 16 (App Router) + TypeScript | Front-end e API routes no mesmo projeto, server components para dados, sem infra extra |
| Banco | Postgres via Prisma (`prisma/schema.prisma`) | Roda em qualquer hospedagem, inclusive serverless (Vercel) — ver `docs/deployment.md`. Nenhum código de aplicação usa SQL cru |
| IA | `@anthropic-ai/sdk` direto (sem framework de agente) | Cada agente é uma função TypeScript com prompt + parsing de JSON — mais fácil de auditar/testar que um framework genérico |
| Estilo | Tailwind CSS com tokens de marca (`globals.css`) | Consistência de marca sem depender de um design system externo |
| QR/UTM | `qrcode` + geração de URL local | Cálculo puro, nunca passa por LLM (REGRA 38 do briefing) |

## Por que status/tipo não são enum do Postgres

O projeto nasceu em SQLite (que não suporta `enum` nativo no Prisma) e manteve a
mesma escolha depois de migrar para Postgres: todo campo de status/tipo fechado
(`Campaign.status`, `Task.status`, `ContentItem.status` etc.) é uma coluna `String`,
validada por schemas Zod em `src/lib/types.ts` — a fonte da verdade dos valores
válidos vive lá, não espalhada pelo código, e adicionar um valor novo nunca exige uma
migração de schema.

## Multi-tenant

Todo modelo relevante carrega `clientId` (direto ou via `campaignId → Campaign.clientId`).
O MVP resolve um único tenant (`getOrCreateDefaultClient()` em `src/lib/tenant.ts`),
mas a query em qualquer endpoint já filtra por `clientId`/`campaignId` — trocar isso
por autenticação real de múltiplos clientes é adicionar uma tela de login que resolve
o `clientId` da sessão, não reescrever as queries.

## Estrutura de pastas

```
prisma/schema.prisma        Modelo de dados (fonte da verdade do banco)
prisma/seed.ts               Cria o tenant Lucrattiva + a campanha "Evento Lucrativa Agro"
src/lib/                     Núcleo sem UI: db, claude (wrapper do SDK), types (schemas
                              Zod dos "enums"), completeness (checker), utm, qrcode,
                              activityLog, approvals, taskEngine, imageProvider, serialize
src/agents/                  Um arquivo por agente + orchestrator.ts (ver docs/agents.md)
src/app/api/                 Rotas HTTP (ver docs/integrations.md para o contrato de cada uma)
src/app/campanhas/           Páginas do Campaign Center (wizard, dashboard, sub-abas)
src/app/inscricao/[id]/      Landing page pública de inscrição de evento
src/app/r/[code]/            Redirecionador de link curto (UTM)
src/components/              UI: primitivos (ui.tsx), wizard de descoberta, dashboard, chat
tests/                       Vitest — banco de teste isolado (Postgres separado, ver TEST_DATABASE_URL), nunca o de dev/produção
```

## Fluxo de uma campanha

```
Usuário clica "Criar campanha"
  → cria Campaign(status=DISCOVERY) e entra no wizard/chat
  → CampaignCompletenessChecker bloqueia a confirmação enquanto faltar
    informação obrigatória (nunca inventa valor)
  → usuário confirma
  → Orchestrator.confirmAndRunCampaign():
      Research Agent → Strategy Agent → Content Agent → Creative Agent
      → Tracking Agent → tarefas humanas iniciais
      (cada estágio de IA que falhar — por falta de chave, por exemplo —
       é registrado e vira uma tarefa humana; o pipeline não trava)
  → Campaign(status=ACTIVE), dashboard mostra funil, tarefas, aprovações,
    activity log e o copiloto de chat
```

Ver `docs/campaigns.md` para o modelo de dados completo e `docs/agents.md` para o
contrato de cada agente.

## Decisões que valem registrar

- **Briefing em duas camadas**: colunas próprias no `Campaign` para o que o dashboard
  precisa consultar/filtrar (status, datas, orçamento, objetivo) + um campo JSON
  (`briefingExtra`) para o resto da descoberta (palestrantes, histórico, parceiros
  citados, campos marcados como "não sei"). Isso evita uma tabela com 60 colunas a
  maioria nula, sem perder a riqueza dos dados coletados pelo wizard/chat.
- **`unknownFields`**: quando o usuário marca "ainda não sei" (meta, orçamento,
  capacidade), o campo entra em `briefingExtra.unknownFields` em vez de ficar
  simplesmente vazio — isso distingue "não perguntado ainda" de "perguntado e a
  resposta é 'não sei'", que **não bloqueia** a confirmação da campanha (vira
  `recommended`, não `missing`, no `CampaignCompletenessChecker`).
- **Creative Agent não chama LLM para o briefing visual**: o texto do conteúdo já
  tem título/gancho/CTA gerados pelo Content Agent; o briefing visual é derivado
  desses campos por código puro (`src/agents/creative.ts`). Só a geração da imagem em
  si (opcional, via `IMAGE_PROVIDER`) é uma chamada externa.
