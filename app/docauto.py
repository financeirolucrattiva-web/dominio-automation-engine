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

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "docauto.json"
# registro_icms não existe no contrato do docauto: usa a convenção local.
ROTINAS = {"resumo_acumulador": "resumo_acumulador", "efd_contribuicoes": "efd_contribuicoes",
           "registro_entradas": "livro_entradas", "registro_saidas": "livro_saidas"}
CABECALHO = ["codigo_dominio", "competencia", "rotina", "status", "arquivo", "sha256", "gerado_em"]
_log = logging.getLogger(__name__)


def configuracao(arquivo=None):
    try:
        dados = json.loads(Path(arquivo or ARQUIVO).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) and dados.get("python") else None


def destino(codigo, competencia, tipo, config=None, executar=subprocess.run):
    """Pasta de destino do docauto para a empresa/competência/rotina, ou None."""
    config = config or configuracao()
    rotina = ROTINAS.get(tipo)
    if not config or not rotina:
        return None
    try:
        r = executar([config["python"], "-m", "docauto", "destino", "--codigo-dominio", str(int(codigo)),
                      "--competencia", competencia, "--rotina", rotina, "--json"],
                     cwd=config.get("cwd"), env={**os.environ, "PYTHONPATH": "src"},
                     capture_output=True, text=True, encoding="utf-8", timeout=30)
        dados = json.loads(r.stdout) if r.returncode == 0 else {}
        if r.returncode != 0 or not dados.get("existe") or not dados.get("caminho"):
            _log.warning("docauto sem destino utilizável (rotina %s, saída %s)", rotina, r.returncode)
            return None
        return Path(dados["caminho"])
    except Exception as erro:  # nunca derruba a rotina
        _log.warning("docauto indisponível (%s)", type(erro).__name__)
        return None


def registrar_resultado(codigo, competencia, tipo, status, arquivo, config=None):
    """Acrescenta uma linha ao resultado_automacao.csv (se configurado). Devolve True se gravou."""
    config = config or configuracao()
    rotina = ROTINAS.get(tipo)
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
