"""Fila de pedidos do configurador visual (painel -> Claude no VS Code).

  python scripts/pedidos_configurador.py listar            pedidos pendentes (e os últimos atendidos)
  python scripts/pedidos_configurador.py ver <id>          pedido completo: texto, passos da rotina e último teste
  python scripts/pedidos_configurador.py rotina <id|nome>  passos de uma rotina do configurador
  python scripts/pedidos_configurador.py responder <id> "texto"   marca como atendido; a resposta aparece no painel

Os dados ficam em data/configurador (nada sai do PC). Quem corrige é o Claude na sessão do VS Code, com o código e o
histórico do projeto; este script só lê e responde.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.configurador import Configurador, ConfiguradorErro  # noqa: E402


def main(argv):
    c = Configurador()
    if not argv or argv[0] == "listar":
        pedidos = c.listar_pedidos()
        pendentes = [p for p in pedidos if p["status"] == "pendente"]
        print(f"{len(pendentes)} pedido(s) pendente(s).")
        for p in pedidos[:20]:
            marca = "PENDENTE" if p["status"] == "pendente" else "atendido"
            print(f"- [{marca}] {p['id']}  {p['criado_em']}  rotina: {p['rotina_nome'] or '(geral)'}\n    {p['texto'][:160]}")
        return 0
    if argv[0] == "ver" and len(argv) == 2:
        print(json.dumps(c.obter_pedido(argv[1]), ensure_ascii=False, indent=2))
        return 0
    if argv[0] == "rotina" and len(argv) == 2:
        alvo = argv[1]
        for r in c.listar():
            if alvo in (r["id"], r["nome"]):
                print(json.dumps(c.obter(r["id"]), ensure_ascii=False, indent=2))
                return 0
        print("Rotina não encontrada.")
        return 1
    if argv[0] == "responder" and len(argv) == 3:
        c.responder_pedido(argv[1], argv[2])
        print("Resposta registrada; o painel mostra como 'Respondido'.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ConfiguradorErro as erro:
        print(f"Erro: {erro}")
        sys.exit(1)
