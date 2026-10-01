"""Troca de empresa via F8 — abre, busca por código e acessa.

Wrapper fino em cima de app/dominio.py::trocar_empresa(), pra testar a
troca isolada, sem gerar nada. Uso em lote fica em
scripts/executar_lote.py.

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela, fora de qualquer outro diálogo aberto):

    python scripts\\trocar_empresa.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao

CODIGO = "9996"  # código da empresa de demonstração, sem risco nenhum


def main():
    print("Focando o Domínio...")
    interacao.focar_dominio()

    if dominio.trocar_empresa(CODIGO):
        print("Confira: a empresa no canto superior direito mudou pra 'EXEMPLO ESCRITÓRIO'?")


if __name__ == "__main__":
    main()
