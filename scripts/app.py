"""Ponto de entrada único do motor — menu de texto simples.

Pensado pra ser aberto com duplo clique no atalho
`Abrir Motor SPED.bat` (raiz do repositório), sem precisar digitar
nenhum comando. Reúne as ações já existentes (trocar empresa, gerar
SPED Fiscal numa empresa, rodar em lote por regime) num único lugar —
"abrir o Domínio, apertar no app, e pronto" (pedido do usuário, seção
0.18 do documento).

Como rodar direto (sem o .bat):

    python scripts\\app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dominio, ia, interacao


def opcao_configurar_ia():
    from app.ia import ARQUIVO_CHAVE, PASTA_DADOS

    print()
    print("A IA (Claude Haiku) só é consultada quando aparece uma caixa de")
    print("erro/aviso do Domínio que o motor nunca viu antes — e só recebe o")
    print("texto da caixa, já sem nome/código/CNPJ da empresa. Sem chave, o")
    print("motor pula essas empresas em vez de arriscar (mesmo comportamento")
    print("de sempre).")
    print()
    if ia.disponivel():
        print("IA já configurada (chave encontrada).")
    else:
        print("IA ainda não configurada.")
    print()
    print("Pegue uma chave em https://console.anthropic.com/settings/keys")
    chave = input("Cole a chave aqui (ou Enter para não mexer): ").strip()
    if not chave:
        print("Nada alterado.")
        return
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_CHAVE.write_text(chave, encoding="utf-8")
    print(f"Chave salva em {ARQUIVO_CHAVE} (local, nunca sobe pro GitHub).")


def opcao_trocar_empresa():
    codigo = input("Código da empresa (ex.: 9996): ").strip()
    if not codigo:
        print("Código vazio, cancelado.")
        return
    interacao.focar_dominio()
    if dominio.trocar_empresa(codigo):
        print("Confira na tela se a empresa certa ficou selecionada.")


def opcao_gerar(gerador, nome):
    print("Confirme antes de continuar: a empresa certa já está selecionada no Domínio?")
    print("(o período é selecionado sozinho: sempre o mês fechado anterior ao atual)")
    resposta = input("Pode continuar? (sim/não) ").strip().lower()
    if resposta not in ("sim", "s"):
        print("Cancelado.")
        return
    interacao.focar_dominio()
    if gerador():
        print(f"Fim da rotina ({nome}).")


def main():
    print("=" * 56)
    print(" Automação Fiscal Domínio — SPED Fiscal")
    print("=" * 56)
    print()
    print("Antes de continuar: o Domínio Escrita Fiscal já está aberto")
    print("e visível na tela (não minimizado, não coberto por outra janela)?")
    input("Pressione Enter para continuar (ou feche esta janela para cancelar)...")

    while True:
        print()
        print("O que você quer fazer?")
        print("  1 - Rodar SPED Fiscal em lote, por regime (empresas de EXEMPLO/teste)")
        print("  2 - Rodar SPED Fiscal em lote, por regime (empresas REAIS)")
        print("  3 - Trocar só a empresa selecionada (sem gerar nada)")
        print("  4 - Gerar SPED Fiscal (ICMS) só na empresa já selecionada")
        print("  5 - Gerar EFD Contribuições só na empresa já selecionada")
        print(f"  6 - Configurar a chave da IA de erro ({'configurada' if ia.disponivel() else 'não configurada'})")
        # Automações extras, promovidas do gravador (seção 0.48) — uma
        # opção de menu a mais por item de dominio.AUTOMACOES_EXTRAS,
        # numeradas a partir de 7, sem editar nada aqui a cada uma.
        extras = dominio.AUTOMACOES_EXTRAS
        for indice, (nome, _) in enumerate(extras):
            print(f"  {7 + indice} - {nome}")
        print("  0 - Sair")
        escolha = input("Escolha uma opção: ").strip()

        if escolha == "1":
            dominio.executar_lote(usar_real=False)
        elif escolha == "2":
            dominio.executar_lote(usar_real=True)
        elif escolha == "3":
            opcao_trocar_empresa()
        elif escolha == "4":
            opcao_gerar(dominio.gerar_sped_fiscal, "SPED Fiscal")
        elif escolha == "5":
            opcao_gerar(dominio.gerar_efd_contribuicoes, "EFD Contribuições")
        elif escolha == "6":
            opcao_configurar_ia()
        elif escolha == "0":
            print("Até mais.")
            break
        elif escolha.isdigit() and 0 <= int(escolha) - 7 < len(extras):
            nome, funcao = extras[int(escolha) - 7]
            opcao_gerar(funcao, nome)
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
