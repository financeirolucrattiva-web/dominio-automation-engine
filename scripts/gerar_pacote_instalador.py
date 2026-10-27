"""Gera a pasta do instalador (projeto.zip + instalador + LEIAME) a partir do origin/main.

Uso: python scripts/gerar_pacote_instalador.py [pasta_destino]
Sem argumento usa a pasta "Automacao Dominio - Instalador" dentro de "0.0 DOCAUTO" da Dropbox do servidor.
O zip vem do commit publicado (git archive), então não leva data/, capturas/, saida/ nem configuração local.
"""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PADRAO = Path.home() / "Dropbox" / "servidor LUCRATIVA 2024" / "0.0 DOCAUTO" / "Automacao Dominio - Instalador"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    destino = Path(argv[0]) if argv else PADRAO
    subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=RAIZ, check=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "origin/main"], cwd=RAIZ, check=True,
                            capture_output=True, text=True).stdout.strip()
    destino.mkdir(parents=True, exist_ok=True)
    zip_final = destino / "projeto.zip"
    subprocess.run(["git", "archive", "--format=zip", "-o", str(zip_final), "origin/main"], cwd=RAIZ, check=True)
    for arquivo in (RAIZ / "instalador").iterdir():
        if arquivo.is_file():
            shutil.copyfile(arquivo, destino / arquivo.name)
    print(f"Pacote gerado em {destino} (versão {commit}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
