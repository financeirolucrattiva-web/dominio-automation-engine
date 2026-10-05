"""Script de exploração manual — Fase 1→4.

Wrapper fino em cima de app/dominio.py::gerar_sped_fiscal(): navega
Relatórios > Informativos > Federais > SPED Fiscal, clica OK, confirma
o aviso "Final da exportação." e fecha a tela — ponta a ponta, salvando
cada etapa em capturas/. Uso em lote (várias empresas) fica em
scripts/executar_lote.py.

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela):

    python scripts\\explorar.py

ATENÇÃO: a partir do clique em OK, este script deixa de ser só
navegação — ele gera um arquivo de verdade no Domínio (ver
docs/00-analise-e-plano-fase0.md, seção 0.8). O período (Data
inicial/final) é **sempre sobrescrito automaticamente** pelo mês
fechado anterior ao atual (seção 0.23) — não importa o que já estiver
na tela, o script troca antes de clicar OK. Antes de rodar, confirme só
a empresa selecionada: é a empresa-alvo (ou empresa de teste,
deliberadamente)?
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao


def main():
    print("Focando o Domínio...")
    interacao.focar_dominio()

    if dominio.gerar_sped_fiscal():
        print("Fim da rotina.")


if __name__ == "__main__":
    main()
