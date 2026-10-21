"""Liga/desliga as otimizações de velocidade sem mexer em código (volta ao caminho clássico).

    python scripts/modo_otimizacoes.py status
    python scripts/modo_otimizacoes.py seguro        # tudo no caminho clássico (mais lento, já testado)
    python scripts/modo_otimizacoes.py rapido        # tudo ligado (padrão)
    python scripts/modo_otimizacoes.py desligar ocr_paralelo
    python scripts/modo_otimizacoes.py ligar ocr_paralelo

Grava `data/otimizacoes.json`; vale na próxima leitura (não precisa reiniciar o servidor).
"""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import otimizacoes  # noqa: E402


def _ler():
    try:
        dados = json.loads(otimizacoes.ARQUIVO.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados):
    arquivo = otimizacoes.ARQUIVO
    if not dados:
        arquivo.unlink(missing_ok=True)
        return
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporario, arquivo)


def modo_seguro(ligado):
    dados = _ler()
    if ligado:
        dados["modo_seguro"] = True
    else:
        dados.pop("modo_seguro", None)
    _gravar(dados)


def definir(nome, valor):
    if nome not in otimizacoes.NOMES:
        raise KeyError("Otimizacao desconhecida: " + nome + ". Validas: " + ", ".join(otimizacoes.NOMES))
    dados = _ler()
    if valor:
        dados.pop(nome, None)
    else:
        dados[nome] = False
    _gravar(dados)


def status():
    otimizacoes.restaurar_para_testes()
    existe = " (existe)" if otimizacoes.ARQUIVO.exists() else " (nao existe)"
    linhas = ["Arquivo: " + str(otimizacoes.ARQUIVO) + existe]
    if os.environ.get("DOMINIO_MODO_SEGURO", "").strip():
        linhas.append("Variavel DOMINIO_MODO_SEGURO definida: " + os.environ["DOMINIO_MODO_SEGURO"])
    for nome, ativa in otimizacoes.estado().items():
        linhas.append(("  LIGADA     " if ativa else "  desligada  ") + nome + " - " + otimizacoes.NOMES[nome])
    return "\n".join(linhas)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("acao", choices=("status", "seguro", "rapido", "desligar", "ligar"))
    parser.add_argument("nome", nargs="?")
    argumentos = parser.parse_args(argv)
    try:
        if argumentos.acao == "seguro":
            modo_seguro(True)
        elif argumentos.acao == "rapido":
            modo_seguro(False)
        elif argumentos.acao in ("desligar", "ligar"):
            if not argumentos.nome:
                parser.error("informe o nome da otimizacao")
            definir(argumentos.nome, argumentos.acao == "ligar")
        print(status())
    except (KeyError, OSError) as erro:
        print("Nao foi possivel: " + str(erro), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
