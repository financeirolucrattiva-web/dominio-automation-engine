"""Destinos locais de Livros Fiscais; nenhum acesso ao desktop ou à nuvem."""

import csv
import datetime as dt
import io
import json
from pathlib import Path, PureWindowsPath
import re
import uuid

from app.arquivos import nome_relatorio

ROOT = Path(__file__).resolve().parents[1]
SUBPASTA_PADRAO = "RELATORIOS_APURAÇÃO/LIVROS_FISCAIS"
REGIMES_PILOTO = {"lucro presumido", "lucro real"}


def caminho_relativo(valor, permitir_vazio=True):
    if not isinstance(valor, str) or len(valor) > 500 or any(ord(c) < 32 for c in valor):
        raise ValueError("Informe uma pasta relativa válida.")
    if not valor.strip() and permitir_vazio:
        return ""
    texto = valor.strip().replace("\\", "/")
    partes = texto.split("/")
    if (PureWindowsPath(texto).drive or texto.startswith("/") or
            any(p in ("", ".", "..") or p.endswith((".", " ")) or
                any(c in p for c in '<>:"|?*') or
                re.fullmatch(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", p, re.I)
                for p in partes)):
        raise ValueError("Use uma pasta relativa, sem unidade ou retorno à pasta anterior.")
    return "/".join(partes)


def ler_configuracao(pasta_dados=ROOT / "data"):
    caminho = Path(pasta_dados) / "destino_livros.json"
    if not caminho.is_file():
        raise ValueError("Configure a raiz do servidor em Configurar Destino Livros no PC com o Domínio.")
    dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
    if not isinstance(dados, dict) or not isinstance(dados.get("raiz"), str):
        raise ValueError("Configuração local do destino inválida.")
    return validar_raiz(dados["raiz"]), caminho_relativo(dados.get("subpasta_livros", SUBPASTA_PADRAO), False)


def validar_raiz(valor):
    raiz = Path(valor)
    if not raiz.is_absolute() or not raiz.is_dir():
        raise ValueError("A raiz configurada não é uma pasta local existente.")
    raiz = raiz.resolve()
    if raiz.drive and raiz.drive.upper() != "C:":
        raise ValueError("Nesta instalação, use a raiz local em C: correspondente a Client C no Domínio.")
    return raiz


def pasta_no_mapa(codigo, pasta_dados):
    caminho = Path(pasta_dados) / "mapa_pastas_empresas.csv"
    if not caminho.is_file():
        raise ValueError("Preencha a pasta da empresa no cadastro ou configure o mapa local de pastas.")
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        texto = caminho.read_text(encoding="cp1252")
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    if not leitor.fieldnames or not {"codigo_dominio", "pasta_relativa_a_raiz"} <= set(leitor.fieldnames):
        raise ValueError("Mapa local sem as colunas de código e pasta relativa.")
    candidatas = []
    for linha in leitor:
        valor = (linha.get("codigo_dominio") or "").strip()
        if re.fullmatch(r"[0-9]{1,12}", valor) and int(valor) == int(codigo):
            candidatas.append(linha.get("pasta_relativa_a_raiz") or "")
    if len(candidatas) != 1:
        raise ValueError("O código precisa ter um único destino conferido no mapa local.")
    return caminho_relativo(candidatas[0], False)


def _dentro(raiz, destino):
    destino = destino.resolve()
    if not destino.is_relative_to(raiz):
        raise ValueError("Destino fora da raiz configurada.")
    return destino


def planejar_destino(empresa, regime, competencia, pasta_dados=ROOT / "data", hoje=None):
    if regime.strip().casefold() not in REGIMES_PILOTO:
        raise ValueError("Nesta etapa, configure Livros Fiscais para Lucro Presumido ou Lucro Real.")
    if not isinstance(competencia, str) or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", competencia):
        raise ValueError("Informe a competência com mês e ano.")
    inicio = dt.date.fromisoformat(competencia + "-01")
    if inicio >= (hoje or dt.date.today()).replace(day=1):
        raise ValueError("Use uma competência passada.")
    proximo = (inicio.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    fim = proximo - dt.timedelta(days=1)
    raiz, subpasta_padrao = ler_configuracao(pasta_dados)
    relativa = empresa.get("pasta_relativa") or pasta_no_mapa(empresa["codigo"], pasta_dados)
    base = _dentro(raiz, raiz.joinpath(*caminho_relativo(relativa, False).split("/")))
    if not base.is_dir():
        raise ValueError("A pasta da empresa não existe na raiz configurada; confira o cadastro/mapa.")
    # O mapa não comprova o regime fiscal. Ele vem do cadastro explícito.
    com_ano = _dentro(raiz, base / str(inicio.year))
    if com_ano.is_dir():
        fiscal = com_ano / "FISCAL"
    elif (base / "FISCAL").is_dir():
        fiscal = base / "FISCAL"
    else:
        raise ValueError("Não encontrei a estrutura FISCAL do ano nem a estrutura sem pasta de ano.")
    if not fiscal.is_dir():
        raise ValueError("A pasta FISCAL da competência não existe; confira a estrutura da empresa.")
    subpasta = caminho_relativo(empresa.get("subpasta_livros") or subpasta_padrao, False)
    destino = _dentro(raiz, fiscal / f"{inicio.month:02d}" / Path(*subpasta.split("/")))
    unidade_arquivo = Path(pasta_dados) / "unidade_cliente.txt"
    unidade = unidade_arquivo.read_text(encoding="utf-8").strip().rstrip(":") if unidade_arquivo.exists() else "M"
    if not re.fullmatch(r"[A-Za-z]", unidade):
        raise ValueError("Configure uma única letra em unidade_cliente.txt.")
    caminho_local = str(destino)
    # Mesma conversão do gerador existente, sem importar o desktop na API.
    caminho_dominio = f"{unidade.upper()}:{caminho_local[len(destino.drive):]}" if destino.drive else None
    return {"codigo": empresa["codigo"], "empresa": empresa["nome"], "regime": regime,
            "competencia": competencia, "caminho_local": caminho_local, "caminho_dominio": caminho_dominio,
            "pasta_existe": destino.is_dir(), "origem": "cadastro" if empresa.get("pasta_relativa") else "mapa_local",
            "arquivos_previstos": [nome_relatorio(tipo, empresa["nome"], inicio.isoformat(), fim.isoformat())
                                   for tipo in ("registro_entradas", "registro_saidas", "livro_icms")]}


def testar_gravacao(plano):
    """Teste explícito de destino: cria a pasta, grava e remove um temporário."""
    destino = Path(plano["caminho_local"])
    destino.mkdir(parents=True, exist_ok=True)
    temporario = destino / f".teste_gravacao_{uuid.uuid4().hex}.tmp"
    criado = False
    try:
        with temporario.open("xb") as arquivo:
            criado = True
            arquivo.write(b"teste de destino, sem documento fiscal")
        if temporario.read_bytes() != b"teste de destino, sem documento fiscal":
            raise OSError("Gravação não confirmada.")
    finally:
        if criado:
            temporario.unlink()
    return {**plano, "pasta_existe": True, "gravacao_confirmada": True,
            "emissao_fiscal_testada": False}
