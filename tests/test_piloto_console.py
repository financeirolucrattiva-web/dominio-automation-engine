"""CLI usa o worker real com fiscal sintético, progresso e parada cooperativa."""

import contextlib
import io
import json
from pathlib import Path
import signal
import sqlite3
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch, MagicMock

from app.controle_execucao import ponto_seguro
from app.servidor import RepositorioTarefas, ServicoExecucao
from scripts import explorar_presumido, explorar_resumo_acumulador, testar_livros_fiscais
from scripts.piloto_console import (acompanhar_lote, acompanhar_tarefa,
    encerrar_servico, periodo_competencia, salvar_diagnostico,
    solicitar_cancelamento)
from test_servidor import eventos_confirmados


class TestPeriodoConsole(unittest.TestCase):
    def test_formatos_mes_completo_e_ano_bissexto(self):
        self.assertEqual(periodo_competencia('08/2026'), ('2026-08-01','2026-08-31'))
        self.assertEqual(periodo_competencia('2024-02'), ('2024-02-01','2024-02-29'))
        for valor in ('8/2026','2026-8','2026-13','amanhã',None):
            with self.subTest(valor=valor), self.assertRaises(ValueError):periodo_competencia(valor)

    def test_ctrl_c_sinaliza_sem_interromper_limpeza_e_restaura_handler(self):
        anterior=signal.getsignal(signal.SIGINT)
        with solicitar_cancelamento() as pedido:
            signal.raise_signal(signal.SIGINT)
            self.assertTrue(pedido.is_set())
            signal.raise_signal(signal.SIGINT)
            self.assertTrue(pedido.is_set())
        self.assertIs(signal.getsignal(signal.SIGINT),anterior)


class TestPilotoConsole(unittest.TestCase):
    def setUp(self):
        pasta=tempfile.TemporaryDirectory();self.addCleanup(pasta.cleanup)
        self.raiz=Path(pasta.name)
        self.repo=RepositorioTarefas(self.raiz/'data/servidor.sqlite3')
        self.repo.configuracao.preparar_piloto()
        cadastro=self.repo.configuracao.listar()
        self.regime=next(r for r in cadastro['regimes'] if r['nome']=='Lucro Presumido')
        self.repo.configuracao.salvar_empresa('52','Nome Privado Sintético',self.regime['id'])
        self.selecao={'empresas':['52'],'inicio':'2024-02-01','fim':'2024-02-29'}

    def pedido(self):
        plano=self.repo.configuracao.planejar(self.selecao,piloto_presumido=True)
        return {**self.selecao,'request_id':str(uuid.uuid4()),'apuracao_confirmada':True,
            'piloto_presumido':True,'plano_hash':plano['hash']}

    def iniciar(self,executor):
        servico=ServicoExecucao(self.repo,executor,'simulacao',pasta_saida=self.raiz/'saida')
        servico.iniciar();self.addCleanup(encerrar_servico,servico)
        return servico

    def test_monitor_mostra_etapas_e_resultados_sem_ocr_ou_dados_cliente(self):
        def executar(pedido,receber):eventos_confirmados(pedido,receber);return True
        servico=self.iniciar(executar)
        lote=servico.solicitar_lote(self.pedido())
        saida=io.StringIO()
        with contextlib.redirect_stdout(saida):
            final=acompanhar_lote(self.repo,servico,lote['id'],threading.Event(),3)
        texto=saida.getvalue()
        self.assertIn('[piloto]',texto)
        self.assertIn('Preencher período',texto)
        self.assertIn('Encerrar e conferir retorno',texto)
        self.assertNotIn('Nome Privado',texto)
        # Livros sem artefatos não viram sucesso mesmo se fiscal devolver True.
        self.assertNotEqual(final['status'],'concluida')

    def test_cancelamento_do_lote_para_antes_da_proxima_rotina(self):
        cancelar=threading.Event();chamadas=[]
        def executar(pedido,receber):
            chamadas.append(pedido['capacidade']);cancelar.set()
            for _ in range(600):
                ponto_seguro();threading.Event().wait(.005)
            return False
        servico=self.iniciar(executar)
        lote=servico.solicitar_lote(self.pedido())
        saida=io.StringIO()
        with contextlib.redirect_stdout(saida):
            final=acompanhar_lote(self.repo,servico,lote['id'],cancelar,3)
        self.assertEqual(chamadas,['resumo_acumulador'])
        self.assertEqual(final['status'],'interrompida')
        self.assertTrue(all(t['status']=='interrompida' for t in final['tarefas']))
        self.assertIn('cancelando o lote',saida.getvalue())

    def test_limite_pede_cancelamento_sem_matar_worker(self):
        chamadas=[]
        def executar(pedido,receber):
            chamadas.append(pedido['capacidade'])
            for _ in range(600):
                ponto_seguro();threading.Event().wait(.005)
            return False
        servico=self.iniciar(executar)
        lote=servico.solicitar_lote(self.pedido())
        saida=io.StringIO()
        with contextlib.redirect_stdout(saida):
            final=acompanhar_lote(self.repo,servico,lote['id'],threading.Event(),0)
        self.assertEqual(final['status'],'interrompida')
        self.assertLessEqual(len(chamadas),1)
        self.assertIn('Limite da execução',saida.getvalue())

    def test_json_local_omite_nome_codigo_caminhos_e_arquivo_privado(self):
        lote,_=self.repo.criar_lote(self.pedido(),'simulacao')
        lote['tarefas'][0]['artefatos']=[{'tipo':'resumo_acumulador','disponivel':True,
            'nome':'NomePrivado.pdf','caminho':'C:/Segredo/NomePrivado.pdf'}]
        destino=salvar_diagnostico(self.repo,lote,self.raiz)
        dados=json.loads(destino.read_text(encoding='utf-8'))
        texto=destino.read_text(encoding='utf-8')
        self.assertFalse(dados['homologacao_fiscal'])
        for proibido in ('Nome Privado','NomePrivado','empresa_codigo','C:/Segredo','caminho'):
            self.assertNotIn(proibido,texto)
        self.assertEqual(dados['rotinas'][0]['artefatos'],[{'tipo':'resumo_acumulador','disponivel':True}])

    def test_worker_indisponivel_nao_deixa_monitor_esperando_para_sempre(self):
        lote,_=self.repo.criar_lote(self.pedido(),'simulacao')
        class Servico:disponivel=False
        saida=io.StringIO()
        with contextlib.redirect_stdout(saida):
            final=acompanhar_lote(self.repo,Servico(),lote['id'],threading.Event(),3)
        self.assertEqual(final['status'],'pendente')
        self.assertIn('Worker indisponível',saida.getvalue())

    def test_tarefa_isolada_cancelada_por_controle_publico(self):
        cancelar=threading.Event()
        def executar(pedido,receber):
            cancelar.set()
            for _ in range(600):
                ponto_seguro();threading.Event().wait(.005)
            return False
        servico=self.iniciar(executar)
        pedido={'request_id':str(uuid.uuid4()),'capacidade':'livros_fiscais','empresa_codigo':'52',
            'inicio':'2024-02-01','fim':'2024-02-29','apuracao_confirmada':True}
        tarefa=servico.solicitar(pedido)
        with contextlib.redirect_stdout(io.StringIO()):
            final=acompanhar_tarefa(self.repo,servico,tarefa['id'],cancelar,3)
        self.assertEqual(final['status'],'interrompida')
        self.assertIsNone(servico.estado_controle())

    def test_cli_recusa_nome_real_nao_presumido_mes_atual_e_config_incompleta(self):
        executor=lambda *_:self.fail('Fiscal não pode ser chamado.')
        argumentos=['--competencia','2024-02','--apuracao-confirmada']
        with patch.object(explorar_presumido,'ROOT',self.raiz), \
             patch.object(explorar_presumido.sys,'platform','win32'), \
             patch('app.executor_servidor.ExecutorDominio',return_value=executor), \
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            for codigo in ('desconhecida','99'):
                with self.subTest(codigo=codigo),self.assertRaises(SystemExit):
                    explorar_presumido.main(['--empresa',codigo,*argumentos])
            self.repo.configuracao.salvar_regime(self.regime['id'],self.regime['nome'],['resumo_acumulador'])
            with self.assertRaises(SystemExit):explorar_presumido.main(['--empresa','52',*argumentos])
        self.assertEqual(self.repo.listar(),[])

    def test_atalho_usa_python_sem_buffer_e_mesmo_cli(self):
        raiz=Path(__file__).resolve().parents[1]
        bat=(raiz/'atalhos/ferramentas/Executar Presumido por Empresa.bat').read_text()
        self.assertIn('-u scripts\\explorar_presumido.py',bat)
        self.assertNotIn('--apuracao-confirmada',bat)

    def test_cli_lote_completo_duas_empresas_na_mesma_fila_sem_duplicar(self):
        from test_arquivos import criar_pdf
        self.repo.configuracao.salvar_empresa('53','Empresa Sintética 53',self.regime['id'])
        chamadas=[]
        def executar(pedido,receber):
            chamadas.append((pedido['empresa_codigo'],pedido['capacidade']))
            eventos_confirmados(pedido,receber)
            if pedido['capacidade']!='livros_fiscais':return True
            pasta=self.raiz/'saida';pasta.mkdir(exist_ok=True)
            artefatos=[]
            for tipo,titulo in (('registro_entradas','REGISTRO DE ENTRADAS'),
                                ('registro_saidas','REGISTRO DE SAIDAS'),
                                ('registro_icms','REGISTRO DE APURACAO DO ICMS')):
                caminho=pasta/(pedido['request_id']+'_'+tipo+'.pdf')
                criar_pdf(caminho,titulo+' CNPJ: 12.345.678/0001-95 Periodo 01/02/2024 a 29/02/2024')
                artefatos.append({'tipo':tipo,'caminho':str(caminho)})
            return True,artefatos
        executar.executar_em_lote=executar
        with patch.object(explorar_presumido,'ROOT',self.raiz), \
             patch.object(explorar_presumido.sys,'platform','win32'), \
             patch.object(explorar_presumido.time,'sleep'), \
             patch('app.executor_servidor.ExecutorDominio',return_value=executar), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(explorar_presumido.main(['--empresas','52,53','--competencia','2024-02','--apuracao-confirmada']),0)
        self.assertEqual(chamadas,[(codigo,rotina) for codigo in ('52','53') for rotina in self.regime['rotinas']])
        lotes=self.repo.listar_lotes();self.assertEqual(len(lotes),1)
        final=self.repo.obter_lote(lotes[0]['id'])
        self.assertEqual(final['status'],'concluida')
        self.assertEqual(len(final['tarefas']),6)
        self.assertTrue(all(t['status']=='concluida' for t in final['tarefas']))
        self.assertEqual(sum(len(t['artefatos']) for t in final['tarefas']),6)

    def test_cli_lote_recusa_codigos_duplicados_ou_incompletos_antes_de_emitir(self):
        self.repo.configuracao.salvar_empresa('53','Empresa Sintética 53',self.regime['id'])
        with patch.object(explorar_presumido,'ROOT',self.raiz), \
             patch.object(explorar_presumido.sys,'platform','win32'), \
             patch('app.executor_servidor.ExecutorDominio') as executor, \
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            for codigos in ('52,52','052,52','52,','52,99','52,desconhecida'):
                with self.subTest(codigos=codigos),self.assertRaises(SystemExit):
                    explorar_presumido.main(['--empresas',codigos,'--competencia','2024-02','--apuracao-confirmada'])
        executor.assert_not_called();self.assertEqual(self.repo.listar_lotes(),[])

    def test_resumo_isolado_usa_monitor_sem_iniciar_efd_ou_livros(self):
        s=explorar_resumo_acumulador;servico=MagicMock()
        servico.solicitar.return_value={'id':'resumo_teste'}
        final={'id':'resumo_teste','status':'concluida','motivo':None}
        with patch.object(s,'ROOT',self.raiz),patch.object(s.sys,'platform','win32'), \
             patch.object(s.time,'sleep'),patch.object(s,'ServicoExecucao',return_value=servico), \
             patch.object(s,'ExecutorDominio'),patch.object(s,'acompanhar_tarefa',return_value=final) as monitor, \
             patch.object(s,'salvar_diagnostico_tarefa'),patch.object(s,'encerrar_servico') as encerrar, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s.main(['--empresa','52','--competencia','08/2026','--apuracao-confirmada']),0)
        pedido=servico.solicitar.call_args.args[0]
        self.assertEqual(pedido['capacidade'],'resumo_acumulador')
        self.assertEqual((pedido['inicio'],pedido['fim']),('2026-08-01','2026-08-31'))
        servico.solicitar.assert_called_once()
        monitor.assert_called_once();encerrar.assert_called_once_with(servico)

    def test_resumo_cancelado_antes_do_inicio_nao_cria_tarefa(self):
        s=explorar_resumo_acumulador;servico=MagicMock();cancelamento=threading.Event();cancelamento.set()
        with patch.object(s,'ROOT',self.raiz),patch.object(s.sys,'platform','win32'), \
             patch.object(s.time,'sleep'),patch.object(s,'ServicoExecucao',return_value=servico), \
             patch.object(s,'ExecutorDominio'),patch.object(s,'encerrar_servico') as encerrar, \
             patch.object(s,'solicitar_cancelamento',return_value=contextlib.nullcontext(cancelamento)), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s.main(['--empresa','52','--competencia','2026-08','--apuracao-confirmada']),130)
        servico.solicitar.assert_not_called();encerrar.assert_called_once_with(servico)

    def test_cli_encerra_worker_mesmo_se_historico_falhar_na_limpeza(self):
        servico=MagicMock()
        lote={'id':'piloto_sintetico'}
        servico.solicitar_lote.return_value=lote
        for resultado in (None,sqlite3.OperationalError('histórico indisponível')):
            with self.subTest(resultado=type(resultado).__name__), \
                 patch.object(explorar_presumido,'ROOT',self.raiz), \
                 patch.object(explorar_presumido.sys,'platform','win32'), \
                 patch.object(explorar_presumido.time,'sleep'), \
                 patch('app.servidor.RepositorioTarefas',return_value=self.repo), \
                 patch('app.servidor.ServicoExecucao',return_value=servico), \
                 patch('app.executor_servidor.ExecutorDominio'), \
                 patch.object(self.repo,'obter_lote',side_effect=resultado if isinstance(resultado,Exception) else None,return_value=None), \
                 patch('scripts.piloto_console.acompanhar_lote',side_effect=RuntimeError('falha de acompanhamento')), \
                 patch('scripts.piloto_console.encerrar_servico') as encerrar, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(explorar_presumido.main(['--empresa','52','--competencia','2024-02','--apuracao-confirmada']),1)
                encerrar.assert_called_once_with(servico)


if __name__=='__main__':unittest.main()
