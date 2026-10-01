"""Histórico local de execuções — registro de cada rotina rodada pela
interface gráfica, pra consultar depois (seção "painel de
acompanhamento" do pedido original: "consultar falhas e evidências").

Guardado em `data/historico_execucoes.json` — local, gitignored (mesma
regra de `data/*`), nunca sobe pro GitHub, porque pode conter nome de
arquivo com dado de cliente no caminho.
"""

import datetime
import json
from pathlib import Path

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO = PASTA_DADOS / "historico_execucoes.json"

# Não cresce sem limite — só as execuções mais recentes importam pra
# consulta do dia a dia.
MAXIMO_REGISTROS = 200


def registrar(rotina, sucesso, arquivo_gerado=None, detalhe=""):
    """Acrescenta um registro novo no histórico e devolve ele."""
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    lista = carregar()
    item = {
        "quando": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rotina": rotina,
        "sucesso": bool(sucesso),
        "arquivo_gerado": str(arquivo_gerado) if arquivo_gerado else None,
        "detalhe": detalhe,
    }
    lista.append(item)
    lista = lista[-MAXIMO_REGISTROS:]
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


def carregar():
    """Devolve a lista de execuções, mais recente por último. Lista
    vazia se o arquivo não existir ainda ou estiver corrompido."""
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        return []
