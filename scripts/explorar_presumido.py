"""Teste individual do Presumido no mesmo worker/lote do painel.

Pare o servidor antes de usar este script no Windows. Pendências não
viram execução; teste parcial exige --somente-disponiveis explícito.
"""
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
    parser.add_argument('--empresa',help='Código da empresa cadastrada no Lucro Presumido.')
    parser.add_argument('--competencia',help='AAAA-MM de competência passada fechada.')
    parser.add_argument('--apuracao-confirmada',action='store_true')
    parser.add_argument('--somente-disponiveis',action='store_true',help='Teste parcial explícito: pendências ficam registradas sem emissão.')
    args=parser.parse_args(argv)
    if sys.platform!='win32':parser.error('O teste real requer a sessão Windows com Domínio.')
    from app.servidor import RepositorioTarefas, ServicoExecucao
    from app.executor_servidor import ExecutorDominio
    codigo=args.empresa or input('Código da empresa cadastrada no Presumido: ').strip()
    competencia=args.competencia or input('Competência fechada (AAAA-MM): ').strip()
    repo=RepositorioTarefas(ROOT/'data/servidor.sqlite3')
    try:
        inicio=dt.date.fromisoformat(competencia+'-01')
        fim=(inicio.replace(day=28)+dt.timedelta(days=4)).replace(day=1)-dt.timedelta(days=1)
        selecao={'empresas':[codigo],'inicio':inicio.isoformat(),'fim':fim.isoformat()}
        plano=repo.configuracao.planejar(selecao,piloto_presumido=True)
    except ValueError:
        parser.error('Confira empresa do Presumido, competência passada completa e cadastro das rotinas.')
    cadastro=repo.configuracao.listar()
    nomes={r['id']:r['nome'] for r in cadastro['rotinas']}
    print('Sequência disponível: '+', '.join(nomes[r] for r in plano['empresas'][0]['rotinas']))
    for pendencia in plano['pendencias']:print('NÃO EXECUTADA — integração pendente: '+pendencia['nome'])
    if plano['quantidade_pendencias'] and not args.somente_disponiveis:
        parser.error('O teste completo ainda está bloqueado. Use --somente-disponiveis apenas para testar as rotinas integradas.')
    confirmada=args.apuracao_confirmada or input('A apuração está fechada nessa empresa? Digite S: ').strip().upper()=='S'
    if not confirmada:parser.error('Confirme uma competência apurada antes de emitir.')
    pedido={**selecao,'request_id':str(uuid.uuid4()),'apuracao_confirmada':True,
            'plano_hash':plano['hash'],'piloto_presumido':True}
    servico=ServicoExecucao(repo,ExecutorDominio(),'windows',pasta_saida=ROOT/'saida')
    try:
        # Adquire a trava antes de criar tarefas; servidor ativo recusa teste isolado.
        servico.iniciar()
        print('Deixe o Domínio em foco no painel azul nos próximos 5 segundos. Depois não toque no mouse/teclado.',flush=True)
        time.sleep(5)
        lote=servico.solicitar_lote(pedido)
        while True:
            final=repo.obter_lote(lote['id'])
            if final['status'] not in ('pendente','executando'):break
            time.sleep(.3)
        for tarefa in final['tarefas']:
            print(f"{nomes[tarefa['pedido']['capacidade']]}: {tarefa['status']}; motivo: {tarefa['motivo'] or 'nenhum' }.")
        print('Resultado da sequência:',final['status'])
        print('Pendências não executadas:',final['plano']['quantidade_pendencias'])
        print('Confira etapas no histórico e os documentos locais antes de homologar.')
        return 0 if final['status']=='concluida' else 2 if final['status']=='concluida_com_pendencias' else 1
    except OSError:
        print('Teste não iniciado. Pare o servidor e confira permissões e a sessão Windows antes de usar o script isolado.')
        return 1
    except ValueError:
        print('Teste não confirmado. Confira cadastro, período e o histórico antes de repetir.')
        return 1
    finally:servico.encerrar()


if __name__=='__main__':raise SystemExit(main())
