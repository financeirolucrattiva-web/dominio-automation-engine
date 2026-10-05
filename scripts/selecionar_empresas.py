"""Escolhe quais empresas processar hoje, filtrando por regime.

Primeiro passo da Fase 5 (múltiplas empresas — docs/00-analise-e-plano-
fase0.md, seções 0.9 e 0.15): só carrega a lista de `data/empresas.csv`
e filtra por regime (Simples/Presumido/Real). **Ainda não dispara
nenhuma rotina sozinho** — isso fica pra depois da Fase 4 (uma rotina,
uma empresa) rodar estável na empresa-alvo real, seguindo a operação
segura da seção 5.7. Por enquanto, só confirma que a lista e o filtro
funcionam.

Como rodar (usa data/empresas.csv, a lista de verdade, se ela existir):

    python scripts\\selecionar_empresas.py

Pra testar com as empresas de demonstração em vez da lista de verdade
(mesmo que data/empresas.csv já exista), usa --exemplo:

    python scripts\\selecionar_empresas.py --exemplo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import empresas


def main():
    caminho = empresas.ARQUIVO_EXEMPLO if "--exemplo" in sys.argv else None
    lista = empresas.carregar_empresas(caminho)
    if not lista:
        print("Lista de empresas vazia.")
        return

    regimes = empresas.regimes_disponiveis(lista)
    print(f"{len(lista)} empresa(s) na lista. Regimes disponíveis: {', '.join(regimes)}")
    escolha = input("Qual regime você quer processar hoje? ").strip()

    selecionadas = empresas.filtrar_por_regime(lista, escolha)
    if not selecionadas:
        print(f"Nenhuma empresa com regime '{escolha}'.")
        return

    print(f"\n{len(selecionadas)} empresa(s) selecionada(s) para hoje:")
    for e in selecionadas:
        print(f"  {e['codigo']} - {e['apelido']}")


if __name__ == "__main__":
    main()
