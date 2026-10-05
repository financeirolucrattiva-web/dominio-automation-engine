"""Carrega e filtra a lista de empresas-alvo (base pra Fase 5).

`data/empresas.csv` é a lista de verdade — código, apelido e regime de
cada empresa que o motor pode acessar. É dado de cliente real (mesmo
sendo só nome e código), então fica em `data/`, que já está no
`.gitignore` desde o início do projeto: nunca é versionada, o usuário
mantém ela localmente na própria máquina (edita num Excel/Notepad).

`data/empresas.exemplo.csv` é só o modelo de formato — as empresas de
demonstração do próprio Domínio (seção 0.15 do documento), sem risco
nenhum, e esse sim é versionado, serve de referência de como preencher
o arquivo de verdade.
"""

import csv
import unicodedata
from pathlib import Path

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO_EMPRESAS = PASTA_DADOS / "empresas.csv"
ARQUIVO_EXEMPLO = PASTA_DADOS / "empresas.exemplo.csv"


def _ler_texto(arquivo):
    """Lê `arquivo` como texto, tentando UTF-8 primeiro e caindo pra
    Windows-1252 (ANSI) se não der — achado real: editar um CSV com
    acento no Notepad/Excel em português nem sempre salva em UTF-8, e
    quem só está preenchendo uma planilha não tem como saber disso
    (byte inválido em UTF-8 tipo `0xC1` é literalmente a letra "Á" em
    Windows-1252). Sem essa segunda tentativa, um nome de empresa
    acentuado quebra o carregamento inteiro.
    """
    try:
        return arquivo.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        print(f"Aviso: {arquivo.name} não é UTF-8 — lendo como Windows-1252 (ANSI).")
        return arquivo.read_text(encoding="cp1252")


def carregar_empresas(caminho=None):
    """Lê a lista de empresas de um CSV com colunas
    `codigo;apelido;regime` (separador `;`, do jeito que o Excel em
    português salva por padrão), mais as colunas opcionais `tipo` e
    `sped` (seção 0.20 — qual documento gerar por empresa).

    Nome de coluna não diferencia maiúscula/minúscula nem espaço em
    volta (`Tipo`, `TIPO ` e `tipo` são a mesma coisa) — não dá pra
    exigir que quem preenche a planilha use exatamente uma grafia.

    `tipo`/`sped` são opcionais: se não existirem no arquivo, toda
    empresa vira `tipo=1, sped=ICMS` (comportamento de antes dessas
    colunas existirem — só SPED Fiscal/ICMS).

    Sem `caminho`, usa `data/empresas.csv`; se esse arquivo ainda não
    existir, avisa e cai pro exemplo (`data/empresas.exemplo.csv`) — só
    pra não travar quem está testando a ferramenta, nunca pra uso real.
    """
    arquivo = Path(caminho) if caminho else ARQUIVO_EMPRESAS
    if not arquivo.exists():
        if arquivo == ARQUIVO_EMPRESAS:
            print(f"Aviso: {arquivo} não existe ainda — usando o exemplo ({ARQUIVO_EXEMPLO.name}).")
            print("Copie empresas.exemplo.csv para empresas.csv e preencha com as empresas de verdade.")
            arquivo = ARQUIVO_EXEMPLO
        else:
            raise FileNotFoundError(f"Não achei {arquivo}")

    # Sempre avisa qual arquivo está em uso — achado real: sem isso, não
    # dá pra saber olhando a tela se o que apareceu é empresa de
    # verdade ou só exemplo/teste (aconteceu de confundir os dois).
    rotulo = "EXEMPLO/TESTE" if arquivo == ARQUIVO_EXEMPLO else "REAL"
    print(f"Carregando empresas de: {arquivo} [{rotulo}]")

    leitor = csv.DictReader(_ler_texto(arquivo).splitlines(), delimiter=";")
    empresas = []
    for linha_bruta in leitor:
        linha = {chave.strip().lower(): valor for chave, valor in linha_bruta.items() if chave}
        if not linha.get("codigo", "").strip():
            continue
        empresas.append(
            {
                "codigo": linha["codigo"].strip(),
                "apelido": linha["apelido"].strip(),
                "regime": linha["regime"].strip().upper(),
                "tipo": linha.get("tipo", "1").strip() or "1",
                "sped": linha.get("sped", "ICMS").strip() or "ICMS",
            }
        )
    return empresas


def _sem_acento(texto):
    """Remove acento de `texto` — pra comparar 'Contribuições' e
    'CONTRIBUICOES' como a mesma coisa, sem depender da grafia exata
    que o usuário usou na planilha."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def documentos_necessarios(empresa):
    """Devolve quais documentos gerar para `empresa`: `["ICMS"]`,
    `["CONTRIBUICOES"]` ou os dois — a partir das colunas `tipo`
    (`"1"` = só um, `"2"` = os dois) e `sped` (qual, quando `tipo` é
    `"1"`) — seção 0.20.

    A comparação de `sped` é tolerante (minúsculo, sem acento,
    substring: "ICMS", "icms", "Contribuições" e "CONTRIBUICOES" todos
    funcionam) — mesmo espírito de `achar_texto()` no resto do motor,
    não dá pra exigir grafia exata de quem preenche a planilha.
    """
    if empresa.get("tipo", "1").strip() == "2":
        return ["ICMS", "CONTRIBUICOES"]

    sped = _sem_acento(empresa.get("sped", "ICMS")).strip().lower()
    if "contrib" in sped:
        return ["CONTRIBUICOES"]
    return ["ICMS"]


def filtrar_por_regime(empresas, regime):
    """Devolve só as empresas cujo regime bate com `regime` (sem
    diferenciar maiúscula de minúscula)."""
    regime = regime.strip().upper()
    return [e for e in empresas if e["regime"] == regime]


def regimes_disponiveis(empresas):
    """Lista os regimes distintos presentes em `empresas`, na ordem em
    que aparecem — usado pra montar o prompt de seleção."""
    vistos = []
    for e in empresas:
        if e["regime"] not in vistos:
            vistos.append(e["regime"])
    return vistos
