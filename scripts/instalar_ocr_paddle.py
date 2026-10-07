"""Instala o OCR opcional para avaliação em CPU; preserva o ambiente do SPED."""

import json
from pathlib import Path
import platform
import struct
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
PASTA_AMBIENTE = ROOT / ".venv-ocr-paddle"
MARCADOR_INSTALACAO = ROOT / "data" / "ocr_paddle_instalado.json"


def ambiente_compativel():
    return (sys.platform == "win32" and platform.machine().lower() in ("amd64", "x86_64")
            and struct.calcsize("P") == 8 and (3, 10) <= sys.version_info[:2] <= (3, 13))


def instalar():
    if not ambiente_compativel():
        print("Este instalador requer Windows x64 e Python 3.10 a 3.13. Use Python 3.12 de 64 bits se precisar ajustar a instalação.")
        return 1
    print("Preparando OCR Paddle opcional em CPU. A primeira instalação baixa dependências e dois modelos.")
    print("A rotina SPED continua usando seu ambiente e o OCR atual.")
    python_ocr = PASTA_AMBIENTE / "Scripts" / "python.exe"
    try:
        if not python_ocr.is_file():
            venv.EnvBuilder(with_pip=True).create(PASTA_AMBIENTE)
        subprocess.run([str(python_ocr), "-m", "pip", "install", "-r", str(ROOT / "requirements-ocr-paddle.txt")], check=True)
        subprocess.run([str(python_ocr), "-m", "pip", "check"], check=True)
        subprocess.run([str(python_ocr), str(ROOT / "scripts" / "preparar_modelos_ocr.py")], check=True)
        MARCADOR_INSTALACAO.parent.mkdir(parents=True, exist_ok=True)
        temporario = MARCADOR_INSTALACAO.with_suffix(".tmp")
        temporario.write_text(json.dumps({"versao": 1, "uso": "avaliacao_cpu"}), encoding="utf-8")
        temporario.replace(MARCADOR_INSTALACAO)
    except Exception as erro:
        print(f"Instalação opcional não concluída ({type(erro).__name__}). Confira a mensagem acima e rode este instalador novamente.")
        return 1
    print("Instalação opcional preparada. Use Avaliar OCR Paddle.bat para comparar uma captura local.")
    print("Isso não habilita PaddleOCR como padrão nem comprova precisão no Domínio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(instalar())
