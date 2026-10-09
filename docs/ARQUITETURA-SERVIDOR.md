# Esquema de pastas do servidor (Lucro Presumido, Lucro Real e Simples Nacional)

Levantado em 09/10/2026 a partir das pastas reais do escritório e do
cadastro exportado do Domínio. Este documento é **genérico**: não contém
nomes de clientes, CNPJ nem usuário Windows. Os caminhos e códigos reais
ficam em `data/mapa_pastas_empresas.csv` (ignorado pelo Git).

Fonte: documento do Claude no [commit f71813c](https://github.com/financeirolucrattiva-web/dominio-automation-engine/commit/f71813c6dd16bada81c6e3f0f54bc6264b0acc76).
Integrado sobre a main com as travas de empresa/foco já presentes, sem
substituir essas alterações. Referências a clientes foram generalizadas.

## Raiz e equivalência local × sessão Domínio

- A raiz é a pasta sincronizada pelo Dropbox, chamada aqui `<RAIZ>`:
  `C:\Users\<usuario>\Dropbox\servidor <ANO>\1.0 EMPRESAS <ESCRITORIO>`.
- O Domínio enxerga o mesmo disco como **Client C**, letra `M:` nesta
  instalação: `M:\Users\<usuario>\Dropbox\...`. Usar
  `app.dominio.caminho_visto_pela_sessao_remota()` e `data/unidade_cliente.txt`.
- Usuário, ano do servidor e raiz são configuração local, nunca código.
- Na tela **Procurar Pasta** (Unidade → árvore) o destino é navegado pela
  árvore de Client C; não existe campo para digitar caminho.

## Pastas por regime (irmãs dentro de `<RAIZ>`)

| Regime | Pasta | Modelo de referência |
| --- | --- | --- |
| Lucro Presumido e Lucro Real (mesma pasta) | `1 LUCRO REAL E LUCRO PRESUMIDO` | `1 PASTA EXEMPLO PRESUMIDO_REAL` |
| Simples Nacional | `2 SIMPLES NACIONAL` | `1 PASTA EXEMPLO SIMPLES NACIONAL` |

Outras pastas irmãs existem (grupo, pessoa física, MEI, IR, baixadas) e
**não** foram mapeadas; não presumir sua estrutura. Presumido e Real
dividem a mesma raiz: o regime vem do cadastro da empresa, não do
caminho. Associar o regime explicitamente a cada destino.

## Organização por empresa e competência

```
<RAIZ>\<PASTA DO REGIME>\<EMPRESA>\<ANO>\<AREA>\<MM>\<tipo>
```

- `<EMPRESA>`: Presumido/Real usa prefixo sequencial (`1.6 NOME DA EMPRESA`);
  Simples usa só o nome. Filiais têm pasta própria.
- `<ANO>`: `2026`. Exceção observada: algumas empresas do Presumido/Real
  não têm pasta de ano (áreas direto sob a empresa). O coletor deve
  checar a existência, não presumir.
- `<AREA>`: `CONTÁBIL`, `FINANCEIRO`, `FISCAL`, `FOLHA`, `HONORARIO`,
  `SOCIETÁRIO-CADASTRO`.
- `<MM>`: `01` a `12`, exceto `SOCIETÁRIO-CADASTRO`; `FISCAL` ainda tem
  `DIVERSOS` e `PARCELAMENTOS`.

### FISCAL/MM — Lucro Presumido e Real

`CERTIDÕES_DT-E`, `DARF_IMPOSTOS`, `NOTIFICAÇÃO`,
`DECLARAÇÕES\{DCTFWEB, MIT, REINF, SPED_CONTRIBUIÇÕES, SPED_FISCAL}`,
`RELATORIOS_APURAÇÃO\{1. NF-E\XML, 2. NFS-E, 3. CT-E}`.

### FISCAL/MM — Simples Nacional

`CERTIDÕES`, `DESTDA`, `GUIAS IMPOSTOS_SN_DIFAL`, `NOTIFICAÇÃO`,
`RELATORIOS APURAÇÃO\{1. NF-E\XML, 2. NFS-E, 3. CT-E}`.
(Sem DARF/SPED/DCTFWeb; nomes com espaço, não sublinhado.)

### Demais áreas

- `CONTÁBIL\MM\{EXTRATOS BANCÁRIOS, RELATÓRIOS MENSAIS}`.
- `FOLHA\MM\{DAE - MEI, DCTF WEB - E-SOCIAL, FUNRURAL, GFIP, INSS}`.
- `FINANCEIRO\MM` e `HONORARIO\MM`: sem subpastas no modelo.
- `SOCIETÁRIO-CADASTRO\{DOCUMENTOS CNPJ, DOCUMENTOS DIVERSOS, DOCUMENTOS DOS SÓCIOS}`.

## Destino escolhido e configuração por empresa

Os modelos não têm pasta de "Livros Fiscais" (Entradas, Saídas, ICMS).
**Destino escolhido pelo operador:** `FISCAL\MM\RELATORIOS_APURAÇÃO\LIVROS_FISCAIS`,
com configuração opcional por empresa. O piloto do resolvedor contempla
somente Presumido e Real. A raiz fica em `data/destino_livros.json`,
configurada pelo atalho **Configurar Destino Livros**. No cadastro:
`pasta_relativa` identifica a empresa dentro da raiz; `subpasta_livros`
substitui o padrão dentro de `FISCAL\MM`. Sem pasta relativa, procura
um único código no CSV local; não deduz regime pelo nome da pasta.

**Ver destino** não cria nada. **Testar pasta** cria o destino se necessário,
confere gravação com um temporário e o remove. Não emite documento fiscal.
O Domínio seleciona uma pasta existente pela árvore; essa navegação ainda
precisa de implementação/teste para a emissão conjunta. Entradas e Saídas
integradas já publicam seus PDFs confirmados ao final na pasta configurada.
Piloto fiscal: uma empresa de Lucro Presumido, competência passada apurada.

## Cadastro Domínio × pastas

`data/mapa_pastas_empresas.csv` (local): `codigo_dominio;razao_social;cnpj;
regime_pasta;pasta_relativa_a_raiz;anos_existentes`. Casamento feito por
nome/apelido; conferir antes de usar em produção:

- Há um casamento por apelido que precisa ser confirmado pelo operador
  antes de usar o código; consultar o CSV local.
- Uma pasta do Simples não consta no cadastro exportado (código vazio).
- Regime fiscal real de cada empresa não está no cadastro exportado;
  a coluna `regime_pasta` reflete só onde a pasta está.
