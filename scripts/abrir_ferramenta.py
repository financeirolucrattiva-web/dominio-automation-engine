"""Abre uma das duas ferramentas locais e mantém o Prompt para ler o resultado."""

import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent.parent
FERRAMENTAS = {
    "calibrar": ("calibrar_tela_principal.py", ()),
    "ocr": ("avaliar_ocr_paddle.py", ("--tela",)),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ferramenta", choices=tuple(FERRAMENTAS))
    args = parser.parse_args(argv)
    arquivo, argumentos = FERRAMENTAS[args.ferramenta]
    anterior = sys.argv
    codigo = 0
    try:
        sys.argv = [str(ROOT / "scripts" / arquivo), *argumentos]
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as erro:
        codigo = erro.code if type(erro.code) is int else (0 if erro.code is None else 1)
    except KeyboardInterrupt:
        print("Ferramenta cancelada pelo teclado.")
        codigo = 130
    except Exception:
        print("Ferramenta não concluída. Confira sua instalação e tente novamente pelo atalho.")
        codigo = 1
    finally:
        sys.argv = anterior
    print(f"\nCódigo de saída da ferramenta: {codigo}.")
    try:
        input("Confira o resultado acima. Pressione Enter para voltar à interface.")
    except (EOFError, KeyboardInterrupt):
        pass
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
