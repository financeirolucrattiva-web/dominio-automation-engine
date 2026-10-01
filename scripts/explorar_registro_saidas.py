"""Script de exploração manual — Registro de Saídas (Livro Fiscal).

**AINDA NÃO VALIDADO CONTRA O DOMÍNIO REAL** — ver a docstring de
`app/dominio.py::gerar_registro_saidas()` antes de rodar. Esta é a
primeira execução de verdade desse caminho; espere precisar corrigir
pelo menos um passo depois de ler o log.

Como rodar (de dentro da pasta do projeto, com o Domínio aberto,
visível na tela, e a empresa certa JÁ selecionada — este script não
troca de empresa sozinho, use scripts/trocar_empresa.py antes se
precisar):

    python scripts\\explorar_registro_saidas.py

Durante a execução, **não toque no teclado/mouse nem troque de
janela** — isso tira o foco do Domínio e quebra a automação no meio
(achado real desta própria conversa de desenvolvimento, não só do SPED
Fiscal).
"""

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

# CNPJ da SPRAYAGRO CONSULTORIA LTDA (empresa usada nos testes de
# navegação até aqui) — troque se testar com outra empresa.
CNPJ_ESPERADO = "62.994.636/0001-53"


def main():
    print("Focando o Domínio...")
    interacao.focar_dominio()

    sucesso, caminho = dominio.gerar_registro_saidas(
        PASTA_DESTINO, data_inicial=DATA_INICIAL, data_final=DATA_FINAL,
    )
    if not sucesso:
        print("Rotina parou antes de gerar o arquivo. Veja os prints de erro em capturas/.")
        return

    print(f"Arquivo gerado: {caminho}")
    print("Conferindo o conteúdo do arquivo...")
    resultado = verificacao.verificar_registro_saidas_pdf(
        caminho,
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
