"""Testa só Entradas, Saídas e ICMS no worker, com servidor parado."""
import argparse
import datetime as dt
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--empresa',help='Código da empresa no Domínio.')
    parser.add_argument('--competencia',help='AAAA-MM de competência passada fechada.')
    parser.add_argument('--apuracao-confirmada',action='store_true')
    args=parser.parse_args(argv)
    if sys.platform!='win32':parser.error('O teste real requer Windows com Domínio visível.')
    from app.servidor import RepositorioTarefas,ServicoExecucao,validar_pedido
    from app.executor_servidor import ExecutorDominio
    codigo=args.empresa or input('Código da empresa: ').strip()
    competencia=args.competencia or input('Competência fechada (AAAA-MM): ').strip()
    confirmada=args.apuracao_confirmada or input('A apuração está fechada nessa empresa? Digite S: ').strip().upper()=='S'
    try:
        inicio=dt.date.fromisoformat(competencia+'-01')
        fim=(inicio.replace(day=28)+dt.timedelta(days=4)).replace(day=1)-dt.timedelta(days=1)
        pedido={'request_id':str(uuid.uuid4()),'capacidade':'livros_fiscais','empresa_codigo':codigo,
                'inicio':inicio.isoformat(),'fim':fim.isoformat(),'apuracao_confirmada':confirmada}
        validar_pedido(pedido)
    except ValueError:parser.error('Confira código, competência passada completa e confirmação da apuração.')
    repo=RepositorioTarefas(ROOT/'data/servidor.sqlite3')
    servico=ServicoExecucao(repo,ExecutorDominio(),'windows',pasta_saida=ROOT/'saida')
    try:
        servico.iniciar()
        print('Deixe o Domínio visível no painel azul nos próximos 5 segundos. Não toque em mouse/teclado durante a execução.',flush=True)
        time.sleep(5)
        tarefa=servico.solicitar(pedido)
        while True:
            final=repo.obter(tarefa['id'])
            if final['status'] not in ('pendente','executando'):break
            time.sleep(.3)
        print('Livros Fiscais:',final['status'],'; motivo:',final['motivo'] or 'nenhum')
        for artefato in final['artefatos']:print(artefato['tipo']+': '+artefato['nome'])
        print('Confira os três PDFs e as etapas no histórico antes de homologar.')
        return 0 if final['status']=='concluida' else 1
    except (OSError,ValueError):
        print('Teste não iniciado/concluído. Pare o servidor e confira configuração e histórico antes de repetir.')
        return 1
    finally:servico.encerrar()


if __name__=='__main__':raise SystemExit(main())
