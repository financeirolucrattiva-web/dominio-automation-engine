"""Gera a pasta do instalador (projeto.zip + instalador + LEIAME) a partir do origin/main.

Uso: python scripts/gerar_pacote_instalador.py [pasta_destino]
Sem argumento usa a pasta "Automacao Dominio - Instalador" dentro de "0.0 DOCAUTO" da Dropbox do servidor.
O zip vem do commit publicado (git archive), então não leva data/, capturas/, saida/ nem configuração local.
Todo .bat/.cmd/.vbs/.ps1 sai com fim de linha CRLF: arquivo de lote só com LF quebra no cmd do Windows.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PADRAO = Path.home() / "Dropbox" / "servidor LUCRATIVA 2024" / "0.0 DOCAUTO" / "Automacao Dominio - Instalador"
EXTENSOES_LOTE = (".bat", ".cmd", ".vbs", ".ps1")
CR, LF = b"\r", b"\n"


def com_crlf(dados):
    return dados.replace(CR + LF, LF).replace(LF, CR + LF)


def _normalizar_zip(origem, destino):
    with zipfile.ZipFile(origem) as entrada, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as saida:
        for item in entrada.infolist():
            dados = entrada.read(item.filename)
            if item.filename.lower().endswith(EXTENSOES_LOTE):
                dados = com_crlf(dados)
            saida.writestr(item, dados)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    destino = Path(argv[0]) if argv else PADRAO
    subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=RAIZ, check=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "origin/main"], cwd=RAIZ, check=True,
                            capture_output=True, text=True).stdout.strip()
    destino.mkdir(parents=True, exist_ok=True)
    bruto = destino / "projeto.bruto.zip"
    subprocess.run(["git", "archive", "--format=zip", "-o", str(bruto), "origin/main"], cwd=RAIZ, check=True)
    _normalizar_zip(bruto, destino / "projeto.zip")
    bruto.unlink()
    for arquivo in (RAIZ / "instalador").iterdir():
        if arquivo.is_file():
            dados = arquivo.read_bytes()
            if arquivo.suffix.lower() in EXTENSOES_LOTE + (".txt",):
                dados = com_crlf(dados)
            (destino / arquivo.name).write_bytes(dados)
    interface = RAIZ / "data" / "rede_local" / "interface_cliente"
    if interface.is_dir():  # só endereço e certificado público: nenhuma chave de acesso
        alvo = destino / "Interface - outros PCs"
        shutil.rmtree(alvo, ignore_errors=True)
        shutil.copytree(interface, alvo)
    print(f"Pacote gerado em {destino} (versão {commit}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
