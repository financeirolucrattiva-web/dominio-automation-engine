"""Testa só o preenchimento da competência anterior, isolado.

Wrapper fino em cima de app/dominio.py::selecionar_competencia_anterior()
(seção 0.23 do documento) — pedido do usuário: sempre selecionar o mês
fechado anterior ao atual, usando mouse+teclado, em vez de confiar no
que já estiver na tela.

**Primeira versão, nunca testada contra o Domínio real** — a posição
do campo de valor (não só o rótulo) é estimada visualmente. Espera que
a tela de geração (SPED Fiscal ou EFD Contribuições) já esteja aberta,
com "Data inicial"/"Data final" visíveis, antes de rodar.

Como rodar (com a tela de geração já aberta no Domínio):

    python scripts\\explorar_competencia.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao


def main():
    print("Focando o Domínio...")
    interacao.focar_dominio()

    if dominio.selecionar_competencia_anterior():
        print("Confira capturas/depois_competencia.png antes de clicar em qualquer OK.")


if __name__ == "__main__":
    main()
