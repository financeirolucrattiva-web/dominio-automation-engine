"""Script de exploração manual — Registro de Entradas (Livro Fiscal).

A navegação foi testada contra o Domínio real (seções 0.59–0.61).
A exportação com nome por empresa/competência e validação antes do
sucesso ainda aguarda teste ao vivo (seção 0.63).

Como rodar (de dentro da pasta do projeto, com o Domínio aberto,
visível na tela, e a empresa certa JÁ selecionada):

    python scripts\\explorar_registro_entradas.py

Use --cnpj para conferir também se a empresa do PDF é a esperada;
--data-inicial e --data-final permitem escolher uma competência já
apurada (formato DD/MM/AAAA). Confirme a apuração antes de executar.

Durante a execução, não toque no teclado/mouse nem troque de janela.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao, verificacao

PASTA_DESTINO = Path(__file__).resolve().parent.parent / "saida"

# Mesma competência já usada (e confirmada apurada) nos testes de
# Registro de Saídas — ajuste se for testar outra.
DATA_INICIAL = "01/08/2026"
DATA_FINAL = "31/08/2026"


def main():
    parser = argparse.ArgumentParser(description="Gera e confere o Livro Fiscal da empresa já selecionada.")
    parser.add_argument("--cnpj", help="CNPJ esperado para conferir a empresa no conteúdo do PDF.")
    parser.add_argument("--data-inicial", default=DATA_INICIAL, help="Data inicial de competência já apurada (DD/MM/AAAA).")
    parser.add_argument("--data-final", default=DATA_FINAL, help="Data final de competência já apurada (DD/MM/AAAA).")
    args = parser.parse_args()
    if not args.cnpj:
        print("CNPJ esperado não informado: a empresa será identificada no PDF, mas não comparada com uma empresa esperada.")
    print("Focando o Domínio...")
    interacao.focar_dominio()

    sucesso, caminho = dominio.gerar_registro_entradas(
        PASTA_DESTINO, data_inicial=args.data_inicial, data_final=args.data_final,
        cnpj_esperado=args.cnpj,
    )
    if not sucesso:
        if caminho:
            print(f"PDF gerado e conferido: {caminho}. Encerramento da interface ficou pendente; confira o Domínio.")
        else:
            print("Rotina não concluída. Veja o log e os prints de erro em capturas/.")
        return

    print(f"Arquivo gerado: {caminho}")
    print("Conferindo o conteúdo do arquivo...")
    resultado = verificacao.verificar_livro_fiscal_pdf(
        caminho,
        texto_cabecalho_esperado="REGISTRO DE ENTRADAS",
        cnpj_esperado=args.cnpj,
        data_inicial_esperada=args.data_inicial,
        data_final_esperada=args.data_final,
    )
    for linha in resultado["detalhes"]:
        print(" -", linha)

    if resultado["ok"]:
        print(f"Conteúdo conferido (método: {resultado['metodo']}). Rotina concluída com sucesso.")
    else:
        print("ATENÇÃO: conteúdo NÃO bateu com o esperado — confira manualmente antes de confiar neste arquivo.")


if __name__ == "__main__":
    main()
