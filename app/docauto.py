"""Contrato por arquivo com o docauto (arquivador de documentos fiscais): só leitura do destino e
publicação do que a automação gerou. Opt-in: sem `data/docauto.json` nada muda.

`data/docauto.json`: {"python": "<python do docauto>", "cwd": "<pasta app do docauto>",
                      "resultado_automacao": "<caminho do resultado_automacao.csv>"}
- destino: `python -m docauto destino --codigo-dominio N --competencia AAAA-MM --rotina R --json`
  (PYTHONPATH=src; só leitura; não cria pasta). Só vale com exit 0 e `existe` verdadeiro; senão a
  rotina segue com a convenção local e o motivo vai para o log.
- resultado: `codigo_dominio;competencia;rotina;status;arquivo;sha256;gerado_em` (UTF-8 BOM, ';').
Nunca levanta erro para a rotina: falha aqui só vira aviso.
"""
import csv
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import unicodedata

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "docauto.json"
# registro_icms (livro de apuração) usa `--tipo APURACAO_ICMS` no docauto, não `--rotina`.
ROTINAS = {"resumo_acumulador": "resumo_acumulador", "efd_contribuicoes": "efd_contribuicoes",
           "registro_entradas": "livro_entradas", "registro_saidas": "livro_saidas",
           "registro_icms": "APURACAO_ICMS", "sped_fiscal": "RECIBO_EFD_ICMS"}
_COMO_TIPO = {"APURACAO_ICMS", "RECIBO_EFD_ICMS"}
_NOME_NO_CSV = {"sped_fiscal": "sped_fiscal"}  # o CSV traz o nome da rotina, não o id do template
# Subpasta de DECLARAÇÕES onde cada TXT vai (nome reconhecido por palavras; ex.: SPED_FISCAL, SPED_CONTRIBUIÇÕES).
_SUBPASTA_PALAVRAS = {"efd_contribuicoes": ("SPED", "CONTRIBUI"), "sped_fiscal": ("SPED", "FISCAL")}
CABECALHO = ["codigo_dominio", "competencia", "rotina", "status", "arquivo", "sha256", "gerado_em"]
_log = logging.getLogger(__name__)


def configuracao(arquivo=None):
    try:
        dados = json.loads(Path(arquivo or ARQUIVO).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) and dados.get("python") else None


def _normalizar(nome):
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", str(nome)) if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in sem_acento.upper()).split())


def _subpasta_do_tipo(pasta, tipo):
    """Desce para a subpasta própria do tipo (SPED_FISCAL, SPED_CONTRIBUIÇÕES...) se existir exatamente uma."""
    palavras = _SUBPASTA_PALAVRAS.get(tipo)
    if not palavras:
        return pasta
    try:
        achadas = [p for p in Path(pasta).iterdir()
                   if p.is_dir() and all(w in _normalizar(p.name) for w in palavras)]
    except OSError:
        return pasta
    return achadas[0] if len(achadas) == 1 else pasta


def destino(codigo, competencia, tipo, config=None, executar=subprocess.run):
    """Pasta de destino do docauto para a empresa/competência/rotina, ou None."""
    config = config or configuracao()
    rotina = ROTINAS.get(tipo)
    if not config or not rotina:
        return None
    try:
        r = executar([config["python"], "-m", "docauto", "destino", "--codigo-dominio", str(int(codigo)),
                      "--competencia", competencia,
                      "--tipo" if rotina in _COMO_TIPO else "--rotina", rotina, "--json"],
                     cwd=config.get("cwd"), env={**os.environ, "PYTHONPATH": "src"},
                     capture_output=True, text=True, encoding="utf-8", timeout=30)
        dados = json.loads(r.stdout) if r.returncode == 0 else {}
        if r.returncode != 0 or not dados.get("existe") or not dados.get("caminho"):
            _log.warning("docauto sem destino utilizável (rotina %s, saída %s)", rotina, r.returncode)
            return None
        return _subpasta_do_tipo(Path(dados["caminho"]), tipo)
    except Exception as erro:  # nunca derruba a rotina
        _log.warning("docauto indisponível (%s)", type(erro).__name__)
        return None


def registrar_resultado(codigo, competencia, tipo, status, arquivo, config=None):
    """Acrescenta uma linha ao resultado_automacao.csv (se configurado). Devolve True se gravou."""
    config = config or configuracao()
    rotina = _NOME_NO_CSV.get(tipo) or ROTINAS.get(tipo)
    if not config or not config.get("resultado_automacao") or not rotina:
        return False
    try:
        arquivo = Path(arquivo)
        sha = hashlib.sha256(arquivo.read_bytes()).hexdigest() if arquivo.is_file() else ""
        destino_csv = Path(config["resultado_automacao"])
        destino_csv.parent.mkdir(parents=True, exist_ok=True)
        novo = not destino_csv.exists() or destino_csv.stat().st_size == 0
        with destino_csv.open("a", encoding="utf-8-sig" if novo else "utf-8", newline="") as f:
            escritor = csv.writer(f, delimiter=";")
            if novo:
                escritor.writerow(CABECALHO)
            escritor.writerow([str(int(codigo)), competencia, rotina, status, str(arquivo), sha,
                               dt.datetime.now().astimezone().isoformat(timespec="seconds")])
        return True
    except Exception as erro:
        _log.warning("resultado_automacao não gravado (%s)", type(erro).__name__)
        return False
