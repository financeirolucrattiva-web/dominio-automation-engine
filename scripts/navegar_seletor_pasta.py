"""Ensaio ao vivo da navegação do "Procurar Pasta" dos Livros Fiscais, sem emitir.

Use com o diálogo "Procurar Pasta" ABERTO (Livros Fiscais > prévia > ícone PDF > "um arquivo
PDF para cada relatório"). Em 5 segundos o script navega pela árvore até uma pasta exclusiva
LIVROS<12 dígitos> dentro de saida/ e para ANTES do OK: nada é confirmado nem emitido.
Depois feche o diálogo com Cancelar. A pasta de teste vazia é removida ao final.
Só clica/usa setas dentro do diálogo; nenhuma transmissão.
"""
import argparse
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--espera", type=int, default=5, help="Segundos antes de começar (padrão 5).")
    parser.add_argument("--confirmar-ok", action="store_true",
                        help="Também clica no OK ao final (cria arquivos só se uma emissão estiver em curso).")
    args = parser.parse_args(argv)
    from app import interacao, seletor_pasta, tela
    from app.dominio import caminho_visto_pela_sessao_remota
    saida = ROOT / "saida"
    saida.mkdir(exist_ok=True)
    destino = saida / ("LIVROS" + str(uuid.uuid4().int % 10**12).zfill(12))
    destino.mkdir()
    print("Ensaio do Procurar Pasta. Deixe o diálogo aberto; começando em", args.espera, "s...", flush=True)
    time.sleep(args.espera)
    inicio = time.monotonic()
    try:
        seletor_pasta.selecionar_pasta(
            caminho_visto_pela_sessao_remota(destino), tela.capturar_tela,
            interacao.clicar, interacao.pressionar_tecla, clicar_ok=args.confirmar_ok)
        print(f"RESULTADO: navegação concluída em {time.monotonic()-inicio:.0f}s.", flush=True)
        return 0
    except seletor_pasta.SeletorPastaNaoConfirmado as erro:
        print(f"RESULTADO: não confirmou ({erro}) após {time.monotonic()-inicio:.0f}s.", flush=True)
        return 1
    finally:
        try:
            destino.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
