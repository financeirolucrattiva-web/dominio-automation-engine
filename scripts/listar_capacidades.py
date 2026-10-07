"""Lista funções conhecidas e suas pendências, sem operar o Domínio."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capacidades import listar_capacidades, obter_capacidade


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Exibir metadados em JSON.")
    parser.add_argument("--id", help="Consultar apenas um identificador de função.")
    args = parser.parse_args(argv)
    try:
        capacidades = (obter_capacidade(args.id),) if args.id else listar_capacidades()
    except ValueError as erro:
        parser.error(str(erro))

    if args.json:
        print(json.dumps({
            "versao_catalogo": 1,
            "executavel": False,
            "capacidades": [capacidade.como_dict() for capacidade in capacidades],
        }, indent=2))
        return 0

    print("Funções conhecidas: catálogo preparatório")
    print("Esta consulta não opera o Domínio. Agentes ainda não estão habilitados.")
    for capacidade in capacidades:
        print(f"\n{capacidade.nome} ({capacidade.id})")
        print(f"  Objetivo: {capacidade.objetivo}")
        print(f"  Validação atual: {capacidade.validacao.versao_atual}")
        print(f"  Período: {capacidade.politica_periodo}")
        print("  Pendências:")
        for pendencia in capacidade.pendencias:
            print(f"    - {pendencia}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
