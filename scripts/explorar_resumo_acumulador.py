"""Teste individual do Resumo com as mesmas travas/worker do painel.

No Windows, pare o servidor antes deste teste isolado. Use uma empresa
cadastrada e uma competência passada apurada; não toque no mouse/teclado
durante a execução. A saída e o histórico continuam locais.
"""
import argparse
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.servidor import RepositorioTarefas, ServicoExecucao, validar_pedido
from app.executor_servidor import ExecutorDominio
from scripts.piloto_console import (acompanhar_tarefa, encerrar_servico, periodo_competencia,
    salvar_diagnostico_tarefa, solicitar_cancelamento)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empresa", help="Código da empresa cadastrada no painel real.")
    parser.add_argument("--competencia", help="AAAA-MM, competência passada já apurada.")
    parser.add_argument("--apuracao-confirmada", action="store_true")
    parser.add_argument('--limite-minutos',type=int,default=15)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("O teste real requer a sessão Windows com Domínio.")
    if not 1 <= args.limite_minutos <= 120:parser.error('O limite deve ser de 1 a 120 minutos.')
    codigo = args.empresa or input("Código cadastrado no Domínio: ").strip()
    competencia = args.competencia or input("Competência passada apurada (AAAA-MM): ").strip()
    try:
        inicio, fim = periodo_competencia(competencia)
        confirmado = args.apuracao_confirmada or input("A apuração dessa competência está fechada? Digite S: ").strip().upper() == "S"
        pedido = validar_pedido({"request_id": str(uuid.uuid4()), "capacidade": "resumo_acumulador",
            "empresa_codigo": codigo, "inicio": inicio, "fim": fim,
            "apuracao_confirmada": confirmado})
    except ValueError:
        parser.error("Confira código, competência passada e apuração fechada.")
    repo = RepositorioTarefas(ROOT / "data/servidor.sqlite3")
    if not any(e["codigo"] == str(int(codigo)) for e in repo.configuracao.listar()["empresas"]):
        parser.error("Cadastre esta empresa no painel real antes do teste, para usar o nome cadastrado.")
    servico = ServicoExecucao(repo, ExecutorDominio(), "windows", pasta_saida=ROOT / "saida")
    with solicitar_cancelamento() as cancelamento:
        try:
            servico.iniciar()
            print("Coloque o Domínio em foco no painel azul nos próximos 5 segundos. Depois não toque no mouse/teclado.", flush=True)
            print('Etapas e progresso ficam neste terminal. Ctrl+C solicita cancelamento seguro.',flush=True)
            time.sleep(5)
            if cancelamento.is_set():return 130
            tarefa = servico.solicitar(pedido)
            final = acompanhar_tarefa(repo,servico,tarefa['id'],cancelamento,args.limite_minutos*60)
            print(f"Resultado: {final['status']}. Motivo: {final['motivo'] or 'sem pendência registrada' }.",flush=True)
            privado = repo.obter(tarefa['id'],privado=True)
            if privado and privado['arquivo']:print(f"PDF local: {privado['arquivo']}",flush=True)
            try:
                print('Diagnóstico local:',salvar_diagnostico_tarefa(repo,final,ROOT),flush=True)
            except OSError:
                print('Não foi possível salvar JSON; etapas permanecem no histórico local.',flush=True)
            print("Confira os valores do documento antes de homologar.",flush=True)
            return 0 if final['status']=='concluida' else 1
        except (OSError,ValueError,RuntimeError):
            print('Teste não confirmado. Confira sessão, cadastro e histórico antes de repetir.',flush=True)
            return 1
        finally:
            encerrar_servico(servico)


if __name__ == "__main__":
    raise SystemExit(main())
