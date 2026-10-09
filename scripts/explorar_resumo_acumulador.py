"""Teste individual do Resumo com as mesmas travas/worker do painel.

No Windows, pare o servidor antes deste teste isolado. Use uma empresa
cadastrada e uma competência passada apurada; não toque no mouse/teclado
durante a execução. A saída e o histórico continuam locais.
"""
import argparse
import datetime as dt
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.servidor import RepositorioTarefas, ServicoExecucao, validar_pedido
from app.executor_servidor import ExecutorDominio


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empresa", help="Código da empresa cadastrada no painel real.")
    parser.add_argument("--competencia", help="AAAA-MM, competência passada já apurada.")
    parser.add_argument("--apuracao-confirmada", action="store_true")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("O teste real requer a sessão Windows com Domínio.")
    codigo = args.empresa or input("Código cadastrado no Domínio: ").strip()
    competencia = args.competencia or input("Competência passada apurada (AAAA-MM): ").strip()
    try:
        inicio = dt.date.fromisoformat(competencia + "-01")
        fim = (inicio.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        confirmado = args.apuracao_confirmada or input("A apuração dessa competência está fechada? Digite S: ").strip().upper() == "S"
        pedido = validar_pedido({"request_id": str(uuid.uuid4()), "capacidade": "resumo_acumulador",
            "empresa_codigo": codigo, "inicio": inicio.isoformat(), "fim": fim.isoformat(),
            "apuracao_confirmada": confirmado})
    except ValueError:
        parser.error("Confira código, competência passada e apuração fechada.")
    repo = RepositorioTarefas(ROOT / "data/servidor.sqlite3")
    if not any(e["codigo"] == str(int(codigo)) for e in repo.configuracao.listar()["empresas"]):
        parser.error("Cadastre esta empresa no painel real antes do teste, para usar o nome cadastrado.")
    servico = ServicoExecucao(repo, ExecutorDominio(), "windows", pasta_saida=ROOT / "saida")
    try:
        print("Coloque o Domínio em foco no painel azul nos próximos 5 segundos. Depois não toque no mouse/teclado.", flush=True)
        time.sleep(5)  # preparação humana; o executor ainda confere foco/tela/código
        servico.iniciar()
        tarefa = servico.solicitar(pedido)
        while True:
            final = repo.obter(tarefa["id"], privado=True)
            if final["status"] not in ("pendente", "executando"):
                break
            time.sleep(.3)
        print(f"Resultado: {final['status']}. Motivo: {final['motivo'] or 'sem pendência registrada' }.")
        if final["arquivo"]:
            print(f"PDF local: {final['arquivo']}")
        print("Guarde o log local; confira os valores do documento antes de homologar.")
        return 0 if final["status"] == "concluida" else 1
    except ValueError as erro:
        print(str(erro))
        return 1
    except OSError:
        print("Não consegui acessar a sessão/dados locais. Feche o servidor antes do teste isolado e confira as permissões.")
        return 1
    finally:
        servico.encerrar()


if __name__ == "__main__":
    raise SystemExit(main())
