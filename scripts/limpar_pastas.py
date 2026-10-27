"""Limpeza das pastas geradas pela automação (capturas, caches, backups e logs antigos).

Só mexe em arquivos que a própria automação cria e que podem ser refeitos. Nunca toca em
configuração (docauto.json, rede_local, tela_principal.json, bancos, chaves) nem em saida/ além de
saida/anteriores. Sem --aplicar apenas mostra o que seria removido.
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIA = 86400
# (pasta relativa, padrão, idade mínima em dias; None = sem filtro de idade)
REGRAS = [
    ("capturas", "*", 7),
    ("saida/anteriores", "*", 30),
    ("data/execucoes", "*.jsonl", 30),
    ("data", "backup_atualizacao_*", 30),
    ("data", "backup_web_*", 30),
    ("data", "recuperacao-web-*", 30),
    ("data", "recuperacao_codigo_*", 30),
]
PASTAS_COM_CACHE = ("app", "scripts", "tests", "web")
LOGS_GRANDES = ("data/servidor_detalhes.log", "data/servidor.log", "data/servidor_permanente.log")
LIMITE_LOG = 5 * 1024 * 1024


def _tamanho(caminho):
    if caminho.is_file():
        return caminho.stat().st_size
    return sum(p.stat().st_size for p in caminho.rglob("*") if p.is_file())


def planejar(raiz=RAIZ, agora=None):
    """Lista de caminhos a remover (arquivos ou pastas inteiras)."""
    agora = time.time() if agora is None else agora
    alvos = []
    for pasta, padrao, dias in REGRAS:
        base = Path(raiz) / pasta
        if not base.is_dir():
            continue
        for item in base.glob(padrao):
            if item.is_symlink():
                continue  # nunca segue atalho para fora da pasta
            if dias is None or agora - item.stat().st_mtime > dias * DIA:
                alvos.append(item)
    for pasta in PASTAS_COM_CACHE:
        base = Path(raiz) / pasta
        if base.is_dir():
            alvos.extend(p for p in base.rglob("__pycache__") if p.is_dir() and not p.is_symlink())
    return alvos


def girar_logs(raiz=RAIZ):
    """Log acima do limite vira .1 (substituindo o .1 antigo). Falha em silêncio se o log estiver em uso."""
    girados = []
    for relativo in LOGS_GRANDES:
        log = Path(raiz) / relativo
        try:
            if log.is_file() and log.stat().st_size > LIMITE_LOG:
                destino = log.with_name(log.name + ".1")
                destino.unlink(missing_ok=True)
                log.rename(destino)
                girados.append(log)
        except OSError:
            pass
    return girados


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true", help="remove de verdade (sem isso só lista)")
    ap.add_argument("--silencioso", action="store_true")
    args = ap.parse_args(argv)
    alvos = planejar()
    total = sum(_tamanho(a) for a in alvos if a.exists())
    for alvo in alvos:
        if not args.silencioso:
            print(("Removendo " if args.aplicar else "Removeria ") + str(alvo.relative_to(RAIZ)))
        if args.aplicar:
            try:
                shutil.rmtree(alvo) if alvo.is_dir() else alvo.unlink()
            except OSError as erro:
                print("Não removido (em uso?): " + str(alvo.relative_to(RAIZ)) + " - " + type(erro).__name__)
    girados = girar_logs() if args.aplicar else []
    print(("Limpeza concluída: " if args.aplicar else "Simulação: ") + f"{len(alvos)} itens, {total / 1048576:.1f} MB"
          + (f"; {len(girados)} log(s) arquivado(s)" if girados else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
