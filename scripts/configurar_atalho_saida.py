"""Cria (ou remove) o atalho curto da pasta de saída para o "Procurar Pasta" andar 1 nível em vez de 4.

    python scripts/configurar_atalho_saida.py              # cria C:\\saida -> <projeto>\\saida
    python scripts/configurar_atalho_saida.py --alias D:\\saida
    python scripts/configurar_atalho_saida.py --remover    # volta ao caminho completo

Cria uma junção NTFS (`mklink /J`, sem administrador) e grava `data/atalho_saida.txt`. Não apaga nem
substitui nada: se o caminho do atalho já existir e não for uma junção para a saída, recusa.
Depois rode "Testar Seletor de Pasta.bat" para ensaiar a navegação sem emitir.
"""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import atalho_saida  # noqa: E402


def _aponta_para(alias, alvo):
    try:
        return alias.is_dir() and alias.resolve() == alvo.resolve()
    except OSError:
        return False


def criar(alias, alvo, executar=subprocess.run, arquivo=None):
    alias, alvo = Path(alias), Path(alvo)
    if not alias.is_absolute() or len(alias.parts) != 2:
        raise ValueError("O atalho precisa ficar na raiz de uma unidade, por exemplo C:\\saida.")
    alvo.mkdir(parents=True, exist_ok=True)
    if alias.exists():
        if not _aponta_para(alias, alvo):
            raise ValueError(f"{alias} já existe e não aponta para a pasta de saída; nada foi alterado. "
                             "Use --alias com outro nome.")
    else:
        resultado = executar(["cmd", "/c", "mklink", "/J", str(alias), str(alvo)],
                             capture_output=True, text=True)
        if resultado.returncode != 0 or not _aponta_para(alias, alvo):
            raise ValueError("Não consegui criar a junção: " + (resultado.stderr or resultado.stdout or "").strip())
    destino = Path(arquivo or atalho_saida.ARQUIVO)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(str(alias) + "\n", encoding="utf-8")
    return alias


def remover(arquivo=None):
    """Só desliga o uso (apaga o arquivo de configuração); a junção fica (apagar uma junção é `rmdir`)."""
    destino = Path(arquivo or atalho_saida.ARQUIVO)
    existia = destino.exists()
    destino.unlink(missing_ok=True)
    return existia


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--alias", default="C:\\saida", help="caminho do atalho (padrão C:\\saida)")
    parser.add_argument("--remover", action="store_true", help="deixa de usar o atalho")
    args = parser.parse_args(argv)
    if args.remover:
        print("Atalho desligado; o Procurar Pasta volta ao caminho completo." if remover()
              else "O atalho já não estava em uso.")
        return 0
    try:
        alias = criar(args.alias, ROOT / "saida")
    except ValueError as erro:
        print("Nao foi possivel: " + str(erro), file=sys.stderr)
        return 1
    print(f"Atalho pronto: {alias} -> {ROOT / 'saida'}")
    print("Rode 'Testar Seletor de Pasta.bat' para ensaiar (sem emitir). Para desligar: --remover.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
