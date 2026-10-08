"""Histórico local de execuções — registro de cada rotina rodada pela
interface gráfica, pra consultar depois (seção "painel de
acompanhamento" do pedido original: "consultar falhas e evidências").

Guardado em `data/historico_execucoes.json` — local, gitignored (mesma
regra de `data/*`), nunca sobe pro GitHub, porque pode conter nome de
arquivo com dado de cliente no caminho.
"""

import datetime
import json
import os
from pathlib import Path
import tempfile

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO = PASTA_DADOS / "historico_execucoes.json"

# Não cresce sem limite — só as execuções mais recentes importam pra
# consulta do dia a dia.
MAXIMO_REGISTROS = 200


def registrar(rotina, sucesso, arquivo_gerado=None, detalhe=""):
    """Grava de forma atômica; None significa resultado não confirmado."""
    if sucesso is not None and type(sucesso) is not bool:
        raise ValueError("Resultado precisa ser True, False ou None.")
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    # Não substitui um histórico ilegível por uma lista vazia.
    lista = carregar(estrito=True)
    item = {
        "quando": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "rotina": rotina,
        "sucesso": sucesso,
        "arquivo_gerado": str(arquivo_gerado) if arquivo_gerado else None,
        "detalhe": detalhe,
    }
    lista.append(item)
    lista = lista[-MAXIMO_REGISTROS:]
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ARQUIVO.parent,
                                         prefix=".historico_", suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(json.dumps(lista, ensure_ascii=False, indent=2))
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, ARQUIVO)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    return item


def carregar(estrito=False):
    """Devolve a lista de execuções, mais recente por último. Lista
    vazia se o arquivo não existir ainda ou estiver corrompido.
    No modo estrito informa o erro, sem expor o conteúdo do arquivo."""
    try:
        lista = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        if not isinstance(lista, list) or any(not _registro_valido(item) for item in lista):
            raise ValueError("Formato de histórico inválido.")
        return lista
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        if estrito:
            raise ValueError("Não foi possível ler o histórico local; arquivo preservado.") from None
        return []


def _registro_valido(item):
    return (isinstance(item, dict)
            and isinstance(item.get("quando"), str)
            and isinstance(item.get("rotina"), str)
            and "sucesso" in item
            and (item["sucesso"] is None or type(item["sucesso"]) is bool)
            and (item.get("arquivo_gerado") is None or isinstance(item["arquivo_gerado"], str)))
