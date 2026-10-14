"""Testa só Entradas, Saídas e ICMS no worker, com servidor parado."""
import argparse
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
    parser.add_argument('--limite-minutos',type=int,default=15)
    args=parser.parse_args(argv)
    if sys.platform!='win32':parser.error('O teste real requer Windows com Domínio visível.')
    if not 1 <= args.limite_minutos <= 120:parser.error('O limite deve ser de 1 a 120 minutos.')
    from app.servidor import RepositorioTarefas,ServicoExecucao,validar_pedido
    from app.executor_servidor import ExecutorDominio
    from scripts.piloto_console import (acompanhar_tarefa,encerrar_servico,periodo_competencia,
                                        salvar_diagnostico_tarefa,solicitar_cancelamento)
    print('LIVROS FISCAIS — Registro de Entradas, Registro de Saídas e ICMS.',flush=True)
    print('Servidor parado; Domínio aberto no painel azul. Com servidor ligado, use o painel.',flush=True)
    codigo=args.empresa or input('Código da empresa: ').strip()
    competencia=args.competencia or input('Competência fechada (MM/AAAA ou AAAA-MM): ').strip()
    confirmada=args.apuracao_confirmada or input('A apuração está fechada nessa empresa? Digite S: ').strip().upper()=='S'
    try:
        inicio,fim=periodo_competencia(competencia)
        pedido={'request_id':str(uuid.uuid4()),'capacidade':'livros_fiscais','empresa_codigo':codigo,
                'inicio':inicio,'fim':fim,'apuracao_confirmada':confirmada}
        validar_pedido(pedido)
    except ValueError:parser.error('Confira código, competência passada completa e confirmação da apuração.')
    repo=RepositorioTarefas(ROOT/'data/servidor.sqlite3')
    servico=ServicoExecucao(repo,ExecutorDominio(),'windows',pasta_saida=ROOT/'saida')
    with solicitar_cancelamento() as cancelamento:
        try:
            servico.iniciar()
            print('Deixe o Domínio visível no painel azul nos próximos 5 segundos. Não toque em mouse/teclado durante a execução.',flush=True)
            print('Etapas ficam neste terminal. Ctrl+C solicita cancelamento seguro.',flush=True)
            time.sleep(5)
            if cancelamento.is_set():
                print('Cancelado antes de iniciar; nenhum livro emitido.',flush=True)
                return 130
            tarefa=servico.solicitar(pedido)
            final=acompanhar_tarefa(repo,servico,tarefa['id'],cancelamento,args.limite_minutos*60)
            print('Livros Fiscais:',final['status'],'; motivo:',final['motivo'] or 'nenhum',flush=True)
            for artefato in final['artefatos']:print(artefato['tipo']+': '+artefato['nome'],flush=True)
            try:
                print('Diagnóstico local:',salvar_diagnostico_tarefa(repo,final,ROOT),flush=True)
            except OSError:
                print('Não foi possível salvar JSON; etapas permanecem no histórico local.',flush=True)
            print('Confira os três PDFs e as etapas no histórico antes de homologar.',flush=True)
            return 0 if final['status']=='concluida' else 1
        except (OSError,ValueError,RuntimeError):
            print('Teste não iniciado/concluído. Pare o servidor e confira configuração e histórico antes de repetir.',flush=True)
            return 1
        finally:encerrar_servico(servico)


if __name__=='__main__':raise SystemExit(main())
