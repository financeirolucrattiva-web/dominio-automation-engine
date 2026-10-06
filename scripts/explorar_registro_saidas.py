"""Script de exploração manual — Registro de Saídas (Livro Fiscal).

A navegação foi testada contra o Domínio real (seções 0.59–0.61).
A exportação com nome por empresa/competência e validação antes do
sucesso ainda aguarda teste ao vivo (seção 0.63).

Como rodar (de dentro da pasta do projeto, com o Domínio aberto,
visível na tela, e a empresa certa JÁ selecionada — este script não
troca de empresa sozinho, use scripts/trocar_empresa.py antes se
precisar):

    python scripts\\explorar_registro_saidas.py

Use --cnpj para conferir também se a empresa do PDF é a esperada;
--data-inicial e --data-final permitem escolher uma competência já
apurada (formato DD/MM/AAAA). Confirme a apuração antes de executar.

Durante a execução, **não toque no teclado/mouse nem troque de
janela** — isso tira o foco do Domínio e quebra a automação no meio
(achado real desta própria conversa de desenvolvimento, não só do SPED
Fiscal).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, interacao, verificacao

# Pasta onde salvar o arquivo exportado — ajuste se quiser outro lugar.
PASTA_DESTINO = Path(__file__).resolve().parent.parent / "saida"

# Agosto/2026 — confirmado pelo usuário como competência já apurada
# no Domínio pra essa empresa (seção 0.57: "mês anterior por
# calendário" não é o mesmo que "mês já apurado", por isso não usamos
# competencia_anterior() aqui).
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

    sucesso, caminho = dominio.gerar_registro_saidas(
        PASTA_DESTINO, data_inicial=args.data_inicial, data_final=args.data_final,
        cnpj_esperado=args.cnpj,
    )
    if not sucesso:
        print("Rotina parou antes de gerar o arquivo. Veja os prints de erro em capturas/.")
        return

    print(f"Arquivo gerado: {caminho}")
    print("Conferindo o conteúdo do arquivo...")
    resultado = verificacao.verificar_registro_saidas_pdf(
        caminho,
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
