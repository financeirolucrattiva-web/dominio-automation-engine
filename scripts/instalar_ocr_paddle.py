"""Instala o OCR opcional para avaliação em CPU; preserva o ambiente do SPED."""

import argparse
import json
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
PASTA_AMBIENTE = ROOT / ".venv-ocr-paddle"
MARCADOR_INSTALACAO = ROOT / "data" / "ocr_paddle_instalado.json"


def ambiente_compativel():
    return (sys.platform == "win32" and platform.machine().lower() in ("amd64", "x86_64")
            and platform.python_implementation() == "CPython"
            and struct.calcsize("P") == 8 and (3, 10) <= sys.version_info[:2] <= (3, 13))


def mostrar_ambiente():
    print(f"Python detectado: {'.'.join(map(str, sys.version_info[:3]))}; "
          f"{platform.python_implementation()}; {struct.calcsize('P') * 8} bits; "
          f"sistema={sys.platform}; arquitetura={platform.machine()}.")


def consultar_python(executavel):
    """Consulta só stdlib no executável encontrado, sem importar o projeto."""
    codigo = (
        "import json,platform,struct,sys; "
        "print(json.dumps({'plataforma':sys.platform,'maquina':platform.machine(),"
        "'implementacao':platform.python_implementation(),'bits':struct.calcsize('P')*8,"
        "'versao':list(sys.version_info[:3])}))"
    )
    try:
        resultado = subprocess.run([str(executavel), "-I", "-c", codigo],
                                   capture_output=True, text=True, timeout=3, check=False)
        if resultado.returncode != 0:
            return None
        dados = json.loads(resultado.stdout)
        versao = dados.get("versao") if isinstance(dados, dict) else None
        if (not isinstance(versao, list) or len(versao) != 3
                or any(type(numero) is not int for numero in versao)):
            return None
        if (dados.get("plataforma") != "win32" or dados.get("bits") != 64
                or dados.get("implementacao") != "CPython"
                or str(dados.get("maquina", "")).lower() not in ("amd64", "x86_64")
                or not (3, 10) <= tuple(versao[:2]) <= (3, 13)):
            return None
        return dados
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def localizar_python_compativel():
    """Reutiliza o ambiente OCR ou enumera instalações; nunca instala Python."""
    python_ocr = PASTA_AMBIENTE / "Scripts" / "python.exe"
    if python_ocr.is_file():
        dados = consultar_python(python_ocr)
        if dados is not None:
            return str(python_ocr), dados
    launcher = shutil.which("py")
    if launcher is None:
        return None
    try:
        # Listagem de instalações existentes: não usa py -3.x, que no
        # Python Install Manager pode disparar um download automático.
        resultado = subprocess.run([launcher, "-0p"], capture_output=True,
                                   text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if resultado.returncode != 0:
        return None
    candidatos = []
    for linha in resultado.stdout.splitlines():
        encontrado = re.match(r'^\s*-\S+\s+(?:\*\s+)?(.+?\.exe)\s*$', linha, re.IGNORECASE)
        if encontrado:
            caminho = encontrado.group(1).strip('"')
            if caminho not in candidatos:
                candidatos.append(caminho)
    validos = []
    preferencia = {12: 0, 13: 1, 11: 2, 10: 3}
    for caminho in candidatos[:8]:
        dados = consultar_python(caminho)
        if dados is not None:
            validos.append((caminho, dados))
    if not validos:
        return None
    return min(validos, key=lambda item: preferencia[item[1]["versao"][1]])


def instalar():
    if not ambiente_compativel():
        mostrar_ambiente()
        print("Este instalador requer Windows x64 e CPython 3.10 a 3.13 de 64 bits.")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usar-python-atual", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.usar_python_atual or sys.platform != "win32":
        return instalar()
    # O ambiente opcional já preparado tem precedência sobre o Python
    # do PATH. Em instalação nova, o atual compatível pode ser usado.
    python_ocr = PASTA_AMBIENTE / "Scripts" / "python.exe"
    if not python_ocr.is_file() and ambiente_compativel():
        return instalar()
    mostrar_ambiente()
    print("Procurando um Python compatível já instalado para o OCR...")
    encontrado = localizar_python_compativel()
    if encontrado is None:
        if ambiente_compativel() and not python_ocr.is_file():
            return instalar()
        print("Nenhum Python compatível foi encontrado. Instale Python 3.12 ou 3.13 de 64 bits lado a lado com o atual, mantendo o PATH existente e o launcher py.")
        print("Depois rode Instalar OCR Paddle.bat novamente. Download oficial: https://www.python.org/downloads/windows/")
        return 1
    executavel, dados = encontrado
    print(f"Usando Python {'.'.join(map(str, dados['versao']))} de 64 bits para o OCR opcional.")
    try:
        return subprocess.run([executavel, str(Path(__file__).resolve()), "--usar-python-atual"], check=False).returncode
    except OSError:
        print("Não consegui iniciar o Python compatível encontrado. Confira sua instalação e rode novamente.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
