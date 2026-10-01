"""Script de exploração manual — Registro de Entradas (Livro Fiscal).

**NUNCA RODOU CONTRA O DOMÍNIO REAL** — generalização do código de
`scripts/explorar_registro_saidas.py` (seção 0.57), que já rodou e já
teve 3 correções reais. Esta é a primeira execução de verdade deste
caminho especificamente; espere precisar corrigir pelo menos o
deslocamento do checkbox (calibrado pra "Registro de Saídas", pode
precisar de ajuste fino pra "Registro de Entradas" — legendas de
comprimento diferente).

Como rodar (de dentro da pasta do projeto, com o Domínio aberto,
visível na tela, e a empresa certa JÁ selecionada):

    python scripts\\explorar_registro_entradas.py

Durante a execução, não toque no teclado/mouse nem troque de janela.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao, verificacao

PASTA_DESTINO = Path(__file__).resolve().parent.parent / "saida"

# Mesma competência já usada (e confirmada apurada) nos testes de
# Registro de Saídas — ajuste se for testar outra.
DATA_INICIAL = "01/08/2026"
DATA_FINAL = "31/08/2026"

CNPJ_ESPERADO = "62.994.636/0001-53"


def main():
    print("Focando o Domínio...")
    interacao.focar_dominio()

    sucesso, caminho = dominio.gerar_registro_entradas(
        PASTA_DESTINO, data_inicial=DATA_INICIAL, data_final=DATA_FINAL,
    )
    if not sucesso:
        print("Rotina parou antes de gerar o arquivo. Veja os prints de erro em capturas/.")
        return

    print(f"Arquivo gerado: {caminho}")
    print("Conferindo o conteúdo do arquivo...")
    resultado = verificacao.verificar_livro_fiscal_pdf(
        caminho,
        texto_cabecalho_esperado="REGISTRO DE ENTRADAS",
        cnpj_esperado=CNPJ_ESPERADO,
        data_inicial_esperada=DATA_INICIAL,
        data_final_esperada=DATA_FINAL,
    )
    for linha in resultado["detalhes"]:
        print(" -", linha)

    if resultado["ok"]:
        print(f"Conteúdo conferido (método: {resultado['metodo']}). Rotina concluída com sucesso.")
    else:
        print("ATENÇÃO: conteúdo NÃO bateu com o esperado — confira manualmente antes de confiar neste arquivo.")


if __name__ == "__main__":
    main()
