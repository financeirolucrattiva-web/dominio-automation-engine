"""Imprime quantas tarefas estão pendentes ou rodando no servidor (0 se o banco não existir)."""
import sqlite3
import sys
from pathlib import Path

banco = Path(__file__).resolve().parent.parent / "data" / "servidor.sqlite3"
if not banco.is_file():
    print(0)
    sys.exit(0)
try:
    conexao = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    print(conexao.execute("SELECT COUNT(*) FROM tarefas WHERE status IN ('pendente','executando')").fetchone()[0])
except sqlite3.Error:
    print(0)
