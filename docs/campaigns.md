# Campanhas

## Modelo de dados

`Campaign` (`prisma/schema.prisma`) é a entidade central — tudo (tarefas, pesquisa,
estratégia, conteúdo, criativos, tracking, leads, aprovações, log, custo de IA) carrega
`campaignId`. Ver `docs/architecture.md` para por que o briefing é dividido entre
colunas próprias e o campo `briefingExtra` (JSON).

Status de uma campanha: `DISCOVERY` (ainda no wizard, briefing incompleto) →
`PLANNING` (confirmada, pipeline de agentes rodando) → `ACTIVE` → `PAUSED` /
`COMPLETED` / `CANCELLED`.

## Modo de Descoberta (nunca assumir dado ausente)

Implementado em `src/lib/completeness.ts` + `src/components/discovery/`. Regras:

1. **Nada é inventado.** Cada campo obrigatório ausente aparece em
   `CompletenessResult.missing`; a confirmação da campanha fica bloqueada enquanto
   `missing.length > 0`.
2. **"Ainda não sei" é uma resposta válida**, não uma pendência bloqueante. Meta,
   orçamento e capacidade podem ser marcados como desconhecidos
   (`briefingExtra.unknownFields`) — entram em `CompletenessResult.recommended`, que
   não bloqueia a confirmação.
3. **Campos condicionais**: local só é obrigatório se o formato não for `online`;
   preço só se o evento for pago; região e canais sempre obrigatórios.
4. **Chat extrai e preenche**: `src/agents/chat.ts` lê a mensagem livre do usuário e
   devolve só os campos que tem certeza que foram informados — nunca reescreve um
   campo já preenchido com uma suposição.
5. **Resumo antes de executar**: a etapa "Revisão" do wizard (`StepRevisao.tsx`)
   mostra tudo o que foi coletado, a lista de pendências (com atalho para voltar à
   etapa certa) e só libera "Confirmar e criar campanha" quando não há pendência
   obrigatória.

Só depois da confirmação o `Orchestrator` roda os agentes — nunca antes.

## Tipos de campanha suportados

`evento`, `lancamento`, `promocao`, `institucional`, `geracao_leads`, `conteudo`,
`sazonal` (`CAMPAIGN_TYPES` em `src/lib/types.ts`). O wizard hoje tem campos
condicionais completos só para `evento` (data, local, formato, capacidade, gratuito/
pago) — os demais tipos usam os campos comuns (objetivo, público, orçamento, canais).

## Campanha inicial: Evento Lucrativa Agro

`prisma/seed.ts` cria o tenant Lucrattiva e uma campanha com **apenas** o que o
briefing original informou explicitamente: nome, data (14/10/2026), objetivo
(lotar o evento), público (produtores rurais e profissionais do agro) e região (Nova
Mutum e região). Local, capacidade, orçamento, canais e CTA ficam em aberto de
propósito — completar isso é o primeiro passo ao abrir a campanha no dashboard
(`/campanhas/<id>` cai automaticamente no wizard enquanto `status = DISCOVERY`).

Rodar: `npm run db:seed`.

## Dashboard

- **Visão geral** (`/campanhas/[id]`): funil real (leads → inscritos → confirmados →
  presentes, sempre dados do banco, nunca estimativa), dias restantes até o evento,
  "o que precisamos fazer" (tarefas), "aguardando sua aprovação", "o que o agente fez"
  (activity log) e o copiloto de chat.
- **Conteúdo** (`/conteudo`): filtro por status, aprovar/rejeitar/editar, mostra a
  imagem gerada (com aviso visual quando é `mock`).
- **Leads** (`/leads`): pipeline `NEW → INTERESTED → REGISTERED → CONFIRMED →
  ATTENDED`, adicionar lead manual, avançar etapa.
- **Divulgação** (`/tracking`): links UTM com cliques reais, QR Codes com download de
  PNG.
- **Tarefas** (`/tarefas`): lista completa, criar tarefa manual, trocar status.
- **Editar briefing** (`/editar`): os mesmos formulários do wizard, sem o fluxo de
  confirmação — para ajustar a campanha depois de ativa.
- **Credenciamento** (`/credenciamento`): métricas do evento, busca de check-in e a
  tabela de participantes com filtros — ver seção própria abaixo.

Todo `/campanhas/*` (páginas e APIs internas) fica atrás da senha do dashboard quando
`DASHBOARD_PASSWORD` está configurada — ver `docs/deployment.md`.

## Landing page pública

`/inscricao/[id]` é a página de inscrição gerada automaticamente para campanhas de
evento (usada como `destinationUrl` padrão do Tracking Agent quando a campanha não
informa um link de inscrição próprio). Hero com banner (gerado na identidade da marca
por padrão — ou uma imagem real via `Campaign.bannerImageUrl`), "por que participar",
"para quem é", palestrantes, programação e o formulário — tudo lido de
`briefingExtra` (ver seção seguinte), nunca hardcoded para um evento específico.

## Credenciamento de evento

Módulo pensado para o dia a dia do evento, não só a inscrição:

- **Qualificação no formulário**: além de nome/contato, `Lead` guarda empresa, cargo,
  área de atuação (`segment`), relação com o agro, se influencia decisões, se já é
  cliente, interesse em diagnóstico — tudo opcional exceto o que o formulário marca
  como obrigatório (`src/components/RegistrationForm.tsx`).
- **Consentimento LGPD**: `marketingConsent` é sempre `false` por padrão — a pessoa
  precisa marcar explicitamente para receber comunicação futura. O consentimento
  operacional (credenciamento, lembretes deste evento) é um checkbox obrigatório
  separado. Ambos ficam registrados com `consentVersion`
  (`CONSENT_VERSION` em `src/lib/types.ts`) e `consentAt` — mude a versão sempre que o
  texto do consentimento mudar.
- **Sem duplicidade**: `POST /api/registration` busca um lead existente por
  telefone/e-mail antes de criar; se já existe inscrição para aquela campanha,
  atualiza os dados e devolve `duplicate: true` (o formulário mostra "Você já possui
  uma inscrição") em vez de criar uma segunda `Registration`.
- **Origem rastreada por pessoa**: `utmSource/utmMedium/utmCampaign/utmContent`
  ficam gravados no próprio `Lead`, lidos da URL no momento da inscrição
  (`?utm_source=instagram` ou `?partner=kennedy`, que vira `source=partner` com
  `utmContent=kennedy`) — não só agregados no link como no restante do tracking.
- **`participantCode`**: gerado na inscrição (`LC-XXXXXXX`), é a base do check-in —
  hoje digitado à mão em `/credenciamento`, arquitetado para um leitor de QR Code
  chamar a mesma rota (`POST /api/campaigns/[id]/checkin`) no futuro.
- **Check-in**: busca por código, telefone ou nome; marca `Registration.status =
  CHECKED_IN` e `checkedInAt`, e `Lead.status = ATTENDED`. Idempotente — repetir o
  check-in da mesma pessoa avisa "já tinha feito check-in" em vez de duplicar.
- **Painel de métricas**: inscritos/capacidade, confirmados, check-ins, taxa de
  comparecimento, novos clientes (`Lead.status = CUSTOMER`), potenciais clientes
  (`isExistingClient` ≠ `SIM`), interesse em diagnóstico, e fontes (Instagram/
  WhatsApp/Parceiros/Outros) — tudo calculado a partir dos leads reais da campanha,
  nunca estimado.
- **Preparado, não implementado**: `giftStatus` (brindes), `postEventInterest`,
  `diagnosticRequested`, `followUpStatus`, `followUpNotes` já existem como colunas em
  `Lead` para o pós-evento, mas sem fluxo/UI ainda — ver Fase 5/6 abaixo.

## Campanha do evento: O Novo Preço de Produzir

`prisma/seed.ts` cria o tenant Lucrattiva e atualiza a campanha com os dados reais do
evento: 14/10/2026, 18:30–21:30, Condomínio Village, até 40 participantes, palestrantes
(Cristiane Dartora, Cristiane Lantin, e Aline com `topicPending: true` — o tema dela
não foi inventado). Três coisas ficaram deliberadamente em aberto, com tarefa criada
no dashboard para cada uma: se o evento é gratuito ou pago, a mecânica exata do
diagnóstico gratuito, e o tema/sobrenome da Aline.

Rodar: `npm run db:seed`.

## O que ainda é Fase 2+ (não implementado nesta entrega)

Do módulo de credenciamento (numeração do próprio briefing): Fase 2 (link de parceiro
dedicado por pessoa, além do `?partner=` já suportado), Fase 3 (envio automático de
lembretes — hoje só a estrutura de status existe, `REMINDER_SENT`), Fase 4 (leitor de
QR Code — o check-in manual já usa a mesma rota que um leitor chamaria), Fase 5
(lista de brindes a partir dos inscritos), Fase 6 (CRM pós-evento completo).

Da Central de Campanhas mais ampla (seção 40 do briefing original): integração real
com Meta Ads, envio de WhatsApp em massa, gestão de parceiros com UI própria,
marketing físico com checklist de materiais, memória histórica entre campanhas e o
Optimization Agent. O schema já tem `Partner` e os campos de orçamento por canal
prontos para isso — falta o agente e a tela.
