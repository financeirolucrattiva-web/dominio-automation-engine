"""Testa só a EFD Contribuições, isolada — sem lote, sem trocar empresa.

Wrapper fino em cima de app/dominio.py::gerar_efd_contribuicoes():
navega Relatórios > Informativos > Federais > EFD Contribuições, clica
OK, confirma o aviso e fecha a tela — ponta a ponta, salvando cada
etapa em capturas/. Espelha scripts/explorar.py, mas para o documento
de Contribuições em vez de SPED Fiscal. **Confirmado rodando de ponta
a ponta por este código** (seção 0.40 do documento).

Como rodar (de dentro da pasta do projeto, com o Domínio aberto e
visível na tela, na empresa certa):

    python scripts\\explorar_contribuicoes.py

ATENÇÃO: a partir do clique em OK, este script gera um arquivo de
verdade no Domínio (ver docs/00-analise-e-plano-fase0.md, seção 0.8).
O período (Data inicial/final) é **sempre sobrescrito automaticamente**
pelo mês fechado anterior ao atual (seção 0.23) — não importa o que já
estiver na tela. Antes de rodar, confirme só a empresa selecionada: é a
empresa-alvo (ou empresa de teste, deliberadamente)?
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao


def main():
    print("Focando o Domínio...")
    interacao.focar_dominio()

    if dominio.gerar_efd_contribuicoes():
        print("Fim da rotina.")


if __name__ == "__main__":
    main()
