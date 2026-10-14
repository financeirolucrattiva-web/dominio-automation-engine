"""Teste individual do Presumido no mesmo worker/lote do painel.

Pare o servidor antes de usar este script no Windows. Pendências não
viram execução; teste parcial exige --somente-disponiveis explícito.
"""
import argparse
from pathlib import Path
import sys
import sqlite3
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
    parser.add_argument('--limite-minutos', type=int, default=30,
                        help='Limite total antes de pedir cancelamento cooperativo (padrão: 30 minutos).')
    args=parser.parse_args(argv)
    if sys.platform!='win32':parser.error('O teste real requer a sessão Windows com Domínio.')
    if not 1 <= args.limite_minutos <= 120:parser.error('O limite deve ser de 1 a 120 minutos.')
    from app.servidor import RepositorioTarefas, ServicoExecucao
    from app.executor_servidor import ExecutorDominio
    from scripts.piloto_console import (acompanhar_lote, encerrar_servico, periodo_competencia,
                                        salvar_diagnostico, solicitar_cancelamento)
    print('PRESUMIDO POR EMPRESA — Resumo, EFD Contribuições e três Livros Fiscais.',flush=True)
    print('Use este atalho com o servidor parado e Domínio aberto no painel azul.',flush=True)
    print('Se o servidor estiver ligado, execute pelo painel: Lucro Presumido por empresa.',flush=True)
    codigo=args.empresa or input('Código da empresa cadastrada no Presumido: ').strip()
    competencia=args.competencia or input('Competência fechada (MM/AAAA ou AAAA-MM): ').strip()
    repo=RepositorioTarefas(ROOT/'data/servidor.sqlite3')
    try:
        inicio,fim=periodo_competencia(competencia)
        selecao={'empresas':[codigo],'inicio':inicio,'fim':fim}
        plano=repo.configuracao.planejar(selecao,piloto_presumido=True)
    except ValueError:
        parser.error('Confira empresa do Presumido, competência passada completa e cadastro das rotinas.')
    cadastro=repo.configuracao.listar()
    nomes={r['id']:r['nome'] for r in cadastro['rotinas']}
    print('Sequência disponível: '+', '.join(nomes[r] for r in plano['empresas'][0]['rotinas']))
    for pendencia in plano['pendencias']:print('NÃO EXECUTADA — integração pendente: '+pendencia['nome'])
    if plano['quantidade_pendencias'] and not args.somente_disponiveis:
        parser.error('O teste completo ainda está bloqueado. Use --somente-disponiveis apenas para testar as rotinas integradas.')
    esperadas={'resumo_acumulador','efd_contribuicoes','livros_fiscais'}
    rotinas=plano['empresas'][0]['rotinas']
    if not args.somente_disponiveis and (len(rotinas)!=3 or set(rotinas)!=esperadas):
        parser.error('Para executar as três rotinas, configure no Presumido Resumo, EFD Contribuições e Livros Fiscais. Nenhum cadastro será alterado automaticamente.')
    print(f'Empresa cadastrada de código {codigo}; período {inicio} a {fim}.',flush=True)
    confirmada=args.apuracao_confirmada or input('Confirma que ESSE mês está apurado e fechado NESSA empresa? Digite S: ').strip().upper()=='S'
    if not confirmada:parser.error('Confirme uma competência apurada antes de emitir.')
    pedido={**selecao,'request_id':str(uuid.uuid4()),'apuracao_confirmada':True,
            'plano_hash':plano['hash'],'piloto_presumido':True}
    servico=ServicoExecucao(repo,ExecutorDominio(),'windows',pasta_saida=ROOT/'saida')
    with solicitar_cancelamento() as cancelamento:
        lote=None
        try:
            # Adquire a trava antes de criar tarefas; servidor ativo recusa teste isolado.
            servico.iniciar()
            print('Deixe o Domínio em foco no painel azul nos próximos 5 segundos. Depois não toque no mouse/teclado.',flush=True)
            print('Etapas e resultado ficam neste terminal. Ctrl+C solicita cancelamento seguro, sem repetir emissão.',flush=True)
            time.sleep(5)
            if cancelamento.is_set():
                print('Cancelado antes de criar o lote; nenhuma rotina iniciada.',flush=True)
                return 130
            lote=servico.solicitar_lote(pedido)
            final=acompanhar_lote(repo,servico,lote['id'],cancelamento,args.limite_minutos*60)
            for tarefa in final['tarefas']:
                print(f"{nomes[tarefa['pedido']['capacidade']]}: {tarefa['status']}; motivo: {tarefa['motivo'] or 'nenhum' }.",flush=True)
                for artefato in tarefa.get('artefatos',[]):
                    print(f"  {artefato['tipo']}: {artefato['nome']}; disponível: {artefato['disponivel']}",flush=True)
            print('Resultado da sequência:',final['status'],flush=True)
            print('Pendências não executadas:',final['plano']['quantidade_pendencias'],flush=True)
            try:
                print('Diagnóstico local:',salvar_diagnostico(repo,final,ROOT),flush=True)
            except OSError:
                print('Não foi possível salvar o diagnóstico JSON; etapas continuam no histórico local.',flush=True)
            print('Confira etapas no histórico e os documentos locais antes de homologar.',flush=True)
            return 0 if final['status']=='concluida' else 2 if final['status']=='concluida_com_pendencias' else 1
        except OSError:
            print('Teste não iniciado. Pare o servidor e confira permissões e a sessão Windows antes de usar o script isolado.',flush=True)
            return 1
        except (ValueError,RuntimeError):
            print('Teste não confirmado. Confira cadastro, período e o histórico antes de repetir.',flush=True)
            return 1
        finally:
            try:
                if lote is not None:
                    try:
                        atual=repo.obter_lote(lote['id'])
                        if atual is not None and atual['status'] in ('pendente','executando'):
                            servico.cancelar_lote(lote['id'])
                    except (OSError,ValueError,sqlite3.DatabaseError):
                        print('Confira o histórico local: não foi possível confirmar o cancelamento do lote.',flush=True)
            finally:
                # Uma falha no histórico não pode impedir a liberação do worker.
                encerrar_servico(servico)


if __name__=='__main__':raise SystemExit(main())
