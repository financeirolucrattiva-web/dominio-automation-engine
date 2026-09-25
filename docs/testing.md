# Testes

```bash
npm test          # roda uma vez
npm run test:watch
```

## Como o banco de teste funciona

`vitest.config.ts` aponta `DATABASE_URL`/`DIRECT_URL` para um banco Postgres
separado do de desenvolvimento — por padrão `lucrativa_test` no mesmo Postgres local
(`tests/testDb.ts`), ou o valor de `TEST_DATABASE_URL` quando definida (útil em CI,
para apontar para um Postgres descartável). `tests/globalSetup.ts` garante o schema
em dia nesse banco antes da suíte rodar. `fileParallelism: false` porque os testes de
banco compartilham o mesmo banco de teste — rodar em paralelo geraria corrida.

## O que está coberto

| Arquivo | O quê |
|---|---|
| `tests/completeness.test.ts` | `CampaignCompletenessChecker` — campos condicionais (local só se presencial, preço só se pago), "ainda não sei" não bloqueia confirmação, campanha totalmente preenchida fica `complete: true` |
| `tests/utm.test.ts` | Geração de UTM, código curto sem caracteres ambíguos, preservação de query params existentes |
| `tests/campaign.test.ts` | Criação de campanha, **isolamento entre clientes** (uma campanha de um cliente nunca aparece na query de outro), `getOrCreateDefaultClient` idempotente |
| `tests/taskEngine.test.ts` | Toda tarefa carrega `campaignId`, transições de status, registro no activity log |
| `tests/approvals.test.ts` | Nível `AUTOMATIC` já nasce aprovado; `HUMAN_APPROVAL` fica `PENDING` até decisão; rejeitar não aprova por engano |
| `tests/credentialing.test.ts` | `participantCode` único por lead; reinscrição nunca gera uma segunda `Registration`; check-in marca `CHECKED_IN` + `checkedInAt`; `marketingConsent` nasce `false` (nunca assumido) |
| `tests/campaignUpdate.test.ts` | Regressão do bug real encontrado em teste manual: patches parciais do wizard não podem apagar campos de `briefingExtra` preenchidos numa etapa anterior; `serializeCampaign` nunca devolve array como `undefined` |

## Testado manualmente no navegador (Playwright)

Antes de considerar o wizard e o dashboard prontos, rodei o fluxo completo num
Chromium real: criar campanha → preencher as 8 etapas do wizard → confirmar → ver o
Orchestrator rodar (com degradação graciosa sem `ANTHROPIC_API_KEY`) → navegar pelas
5 abas do dashboard → adicionar lead manual → avançar no pipeline → submeter a landing
page pública de inscrição → conversar com o copiloto de chat sem chave configurada.
Foi assim que apareceu o bug real corrigido em `tests/campaignUpdate.test.ts`: as
rotas `GET`/`PATCH /api/campaigns/[id]` devolviam o registro cru do Prisma (com
`briefingExtra` ainda como string JSON) em vez do formato serializado — só aparecia
depois de duas ou três chamadas de PATCH em sequência, o tipo de bug que teste
unitário isolado não pega sozinho.

## O que falta testar (depende de `ANTHROPIC_API_KEY` real)

Research/Strategy/Content/Creative Agent fazendo chamada real à API, e o provedor de
imagem `openai`. Não há chave disponível neste ambiente de desenvolvimento — o
tratamento de ausência de chave (erro claro, tarefa humana criada, pipeline não
trava) está coberto pelo teste manual acima e pela lógica em
`src/agents/orchestrator.ts`, mas a resposta real do modelo não foi validada.

## Isolamento por client_id

Além do teste automatizado (`tests/campaign.test.ts`), toda rota de API que lê uma
campanha resolve a campanha por `id` — não há nenhum endpoint que liste campanhas sem
filtrar por `clientId`. Ao adicionar autenticação multi-cliente, adicionar um teste
que confirma que a sessão do cliente A recebe 404 (não a campanha) ao pedir uma
campanha do cliente B é o próximo passo natural.
