# Integrações

## Claude API (Research, Strategy, Content, Chat)

Variável: `ANTHROPIC_API_KEY` (console.anthropic.com/settings/keys). Sem ela, todo
agente de IA lança um erro claro e o Orchestrator registra uma tarefa humana pedindo
para configurar a chave — o resto do pipeline (Tracking Agent, QR Codes, tarefas,
dashboard) continua funcionando normalmente. Nada é simulado no lugar de uma resposta
real (REGRA 10/12 do briefing).

Modelos configuráveis por agente (`.env`):

```
CLAUDE_MODEL_RESEARCH="claude-sonnet-5"   # precisa suportar a tool web_search_20260209
CLAUDE_MODEL_STRATEGY="claude-sonnet-5"
CLAUDE_MODEL_CONTENT="claude-sonnet-5"
CLAUDE_MODEL_CHAT="claude-sonnet-5"
```

Custo é medido de verdade por chamada (tokens reais × tabela de preço em
`src/lib/claude.ts`), gravado em `AIUsage`, nunca inventado.

## Geração de imagem (Creative Agent)

Interface plugável em `src/lib/imageProvider.ts`. Dois modos:

- **Mock (padrão, sem configuração nenhuma)**: gera um placeholder SVG com a
  identidade visual da Lucrattiva (cores, tipografia, selo), sempre etiquetado
  `provider: "mock"` na UI. Funciona offline, sem chave.
- **OpenAI Images (`IMAGE_PROVIDER=openai` + `IMAGE_PROVIDER_API_KEY`)**: chama
  `POST https://api.openai.com/v1/images/generations` (modelo `gpt-image-1`) via
  `fetch` direto. **Não foi testada contra uma chave real nesta sessão** (sem acesso
  de rede para isso) — confira a resposta da API ao ativar pela primeira vez.

Para adicionar outro provedor (Stability, Ideogram etc.), implemente a função
`generateXxx(brief: VisualBrief): Promise<GeneratedImage>` seguindo o padrão de
`generateOpenAI` e adicione o `if` correspondente em `generateImage()`.

## Rastreamento (UTM + QR Code)

Sem integração externa — cálculo local (`src/lib/utm.ts`, `src/lib/qrcode.ts`). Link
curto (`/r/<code>`) redireciona para a URL com UTM embutido e incrementa
`TrackingLink.clicks` (e `QRCode.scans`, quando aplicável) no próprio banco.

## Inscrição de evento

`POST /api/registration` — endpoint público, sem autenticação (é a página de
inscrição de um evento). Cria/atualiza um `Lead` e um `Registration`. Minimização de
dado: só nome + (telefone OU e-mail) são obrigatórios; cidade é opcional; nenhum
campo extra é coletado (ver `docs/deployment.md` sobre LGPD).

## Integrações do briefing original ainda não conectadas

WhatsApp Business API, Meta Ads API e Google Ads não têm adaptador nesta entrega —
Não implementar uma integração falsa é uma regra explícita do briefing (REGRA 12).
Quando uma dessas for conectada, o padrão a seguir é o mesmo do `imageProvider.ts`:
uma interface clara, um modo mock óbvio, e o adaptador real isolado num arquivo só.

## Referência de rotas de API

| Rota | Método | O que faz |
|---|---|---|
| `/api/campaigns` | GET, POST | Lista / cria campanha |
| `/api/campaigns/[id]` | GET, PATCH | Lê / atualiza briefing (parcial, por etapa do wizard) |
| `/api/campaigns/[id]/confirm` | POST | Roda o Orchestrator |
| `/api/campaigns/[id]/chat` | GET, POST | Histórico / nova mensagem do copiloto |
| `/api/campaigns/[id]/research` | GET | Resultados de pesquisa |
| `/api/campaigns/[id]/strategy` | GET | Plano estratégico mais recente |
| `/api/campaigns/[id]/content` | GET | Itens de conteúdo (+ criativos) |
| `/api/content/[id]` | PATCH | Aprovar / rejeitar / editar / agendar conteúdo |
| `/api/campaigns/[id]/tasks` | GET, POST | Tarefas |
| `/api/tasks/[id]` | PATCH | Trocar status de tarefa |
| `/api/campaigns/[id]/approvals` | GET | Aprovações pendentes |
| `/api/approvals/[id]` | PATCH | Aprovar / rejeitar |
| `/api/campaigns/[id]/leads` | GET, POST | Leads (+ adicionar manual) |
| `/api/leads/[id]` | PATCH | Trocar status do lead no pipeline |
| `/api/campaigns/[id]/tracking` | GET | Links UTM + QR Codes |
| `/api/qrcodes/[id]/png` | GET | PNG do QR Code (gerado na hora) |
| `/api/campaigns/[id]/checkin` | POST | Credenciamento — busca por código/telefone/nome e marca `CHECKED_IN` |
| `/api/registration` | POST | Inscrição pública (landing page) — **pública**, sem senha |
| `/r/[code]` | GET | Redirecionador de link curto — **pública** |
| `/api/campaigns/[id]/activity` | GET | Log de auditoria da campanha |
| `/api/auth/login` | POST | Login do dashboard (`DASHBOARD_PASSWORD`) |
| `/api/auth/logout` | POST | Encerra a sessão do dashboard |

Todas as rotas acima, exceto as marcadas **pública**, ficam atrás de `DASHBOARD_PASSWORD` quando configurada (`src/middleware.ts`).
