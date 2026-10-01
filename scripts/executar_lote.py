"""Executa o SPED Fiscal em lote: troca de empresa + gera, repetindo
para cada empresa do regime escolhido.

Wrapper fino em cima de app/dominio.py::executar_lote(). Pra uso do
dia a dia sem linha de comando, prefira `scripts/app.py` (menu único,
aberto pelo atalho `Abrir Motor SPED.bat` na raiz do repositório).

TRAVA DE SEGURANÇA, DE PROPÓSITO: por padrão só roda contra
data/empresas.exemplo.csv (empresas de demonstração, sem risco). Pra
rodar contra a planilha REAL (data/empresas.csv), é preciso passar
--real explicitamente. Essa trava existe porque a Fase 5 em empresa
real ainda depende de validar a Fase 4 (uma rotina, uma empresa) na
empresa-alvo real primeiro (seção 5.7) — o que ainda não aconteceu, só
rodamos em empresa de teste/demonstração até agora (seção 0.11).

Também não muda a competência (Período) da tela — usa a que já estiver
selecionada no Domínio para todas as empresas da lista. Confira que ela
serve antes de rodar com --real.

Como rodar:

    python scripts\\executar_lote.py            # usa data/empresas.exemplo.csv
    python scripts\\executar_lote.py --real      # usa data/empresas.csv (planilha real)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio


def main():
    dominio.executar_lote(usar_real="--real" in sys.argv)


if __name__ == "__main__":
    main()
