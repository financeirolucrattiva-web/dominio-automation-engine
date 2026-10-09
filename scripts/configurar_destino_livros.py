"""Configura no PC servidor a raiz local dos destinos de Livros Fiscais."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import destinos_livros


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", help="Pasta local que contém as pastas de regimes/empresas.")
    parser.add_argument("--subpasta", default=destinos_livros.SUBPASTA_PADRAO)
    args = parser.parse_args(argv)
    raiz_texto = args.raiz or input("Cole o caminho LOCAL da raiz das empresas no Dropbox (C:\\...): ")
    try:
        raiz = destinos_livros.validar_raiz(raiz_texto.strip().strip('"'))
        subpasta = destinos_livros.caminho_relativo(args.subpasta, False)
    except ValueError as erro:
        parser.error(str(erro))
    pasta = ROOT / "data"
    pasta.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=pasta, prefix=".destino_", suffix=".tmp", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            json.dump({"raiz": str(raiz.resolve()), "subpasta_livros": subpasta}, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.replace(temporario, pasta / "destino_livros.json")
    finally:
        if temporario and temporario.exists():
            temporario.unlink()
    print("Configuração local salva. Nenhuma empresa ou pasta fiscal foi criada.")
    print("No painel: Editar empresa → pasta relativa → Salvar → Editar → competência → Ver destino / Testar pasta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
