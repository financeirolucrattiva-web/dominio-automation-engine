# Central de Campanhas — Lucrattiva

Sistema de automação de marketing da **Lucrattiva Contabilidade** (agribusiness):
transforma um objetivo de campanha ("quero lotar o evento do dia 14/10") em briefing
estruturado, pesquisa, estratégia, conteúdo, criativos, rastreamento (UTM/QR Code),
inscrições e um dashboard que mostra o que o agente já fez, o que falta fazer e o que
está aguardando aprovação.

Evolução do [Agente de Redes Sociais da Lucrattiva](https://github.com/cristiane-art/dominio-automation-engine)
original — ver `docs/architecture.md` para o histórico completo.

## Começando

```bash
npm install
cp .env.example .env
npm run db:push
npm run db:seed
npm run dev
```

Abra `http://localhost:3000` — redireciona para `/campanhas`. Sem `ANTHROPIC_API_KEY`
configurada, o sistema funciona normalmente (wizard, dashboard, tarefas, UTM/QR Code,
leads); só os agentes de IA (pesquisa, estratégia, conteúdo, criativo) ficam pausados
até você configurar a chave — ver `docs/deployment.md`.

## Documentação

| Doc | Conteúdo |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Stack, estrutura de pastas, decisões de design |
| [docs/agents.md](docs/agents.md) | Contrato de cada agente (input/output/modelo/permissões) |
| [docs/campaigns.md](docs/campaigns.md) | Modelo de dados, Modo de Descoberta, dashboard |
| [docs/integrations.md](docs/integrations.md) | Claude API, geração de imagem, referência de rotas |
| [docs/deployment.md](docs/deployment.md) | Execução, variáveis de ambiente, LGPD, segurança |
| [docs/testing.md](docs/testing.md) | Como rodar os testes e o que está coberto |

## Testes

```bash
npm test
```

## Identidade visual

Verde institucional `#1D4429`, dourado `#A97829`, marfim `#F6F1E3`, Fraunces (títulos)
+ Inter (corpo) — recuperados do material de marca original da Lucrattiva
(`src/lib/brand.ts`).
