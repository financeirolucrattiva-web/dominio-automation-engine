"""Piloto parcial explícito; não habilita rotinas cadastradas sem executor."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid

from app.servidor import RepositorioTarefas, ServicoExecucao, SessaoOcupada
from test_servidor import eventos_confirmados
from test_controle_execucao import esperar

WEB = all(importlib.util.find_spec(n) for n in ('fastapi', 'httpx'))
if WEB:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app


class TestPilotoPresumido(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(); self.addCleanup(pasta.cleanup)
        self.repo = RepositorioTarefas(Path(pasta.name) / 'data/banco.sqlite3')
        self.repo.configuracao.preparar_piloto()
        self.cadastro = self.repo.configuracao.listar()
        self.regime = next(r for r in self.cadastro['regimes'] if r['nome'] == 'Lucro Presumido')
        self.real = next(r for r in self.cadastro['regimes'] if r['nome'] == 'Lucro Real')
        for codigo in ('52', '53'):
            self.repo.configuracao.salvar_empresa(codigo, 'Empresa Fictícia '+codigo, self.regime['id'])
        self.repo.configuracao.salvar_empresa('54', 'Empresa Fictícia Real', self.real['id'])
        self.cadastro = self.repo.configuracao.listar()
        self.selecao = {'empresas': ['52'], 'inicio': '2024-02-01', 'fim': '2024-02-29'}

    def pedido(self, selecao=None):
        selecao = selecao or self.selecao
        plano = self.repo.configuracao.planejar(selecao, piloto_presumido=True)
        return {**selecao, 'request_id': str(uuid.uuid4()), 'apuracao_confirmada': True,
                'plano_hash': plano['hash'], 'piloto_presumido': True}

    def concluir(self, servico, pedido):
        lote = servico.solicitar_lote(pedido)
        esperar(lambda: self.repo.obter_lote(lote['id'])['status'] not in ('pendente', 'executando'))
        return self.repo.obter_lote(lote['id'])

    def iniciar(self, executor):
        servico = ServicoExecucao(self.repo, executor, 'simulacao')
        servico.iniciar(); self.addCleanup(servico.encerrar)
        return servico

    def test_plano_mostra_pendencia_e_preserva_cadastro_sem_liberar_conjunta(self):
        plano = self.repo.configuracao.planejar(self.selecao, piloto_presumido=True)
        self.assertEqual(plano['quantidade_rotinas'], 2)
        self.assertEqual(plano['quantidade_pendencias'], 1)
        self.assertEqual(plano['empresas'][0]['rotinas'], ['resumo_acumulador', 'efd_contribuicoes'])
        self.assertEqual(len(plano['empresas'][0]['sequencia_cadastrada']), 3)
        self.assertIn('ICMS', plano['pendencias'][0]['nome'])
        self.assertEqual(self.repo.configuracao.listar(), self.cadastro)
        with self.assertRaises(ValueError):self.repo.configuracao.planejar(self.selecao)
        self.assertEqual(self.repo.listar(), [])

    def test_recusa_outro_regime_mes_atual_periodo_incompleto_e_sem_integradas(self):
        for mudanca in ({'empresas':['54']}, {'empresas':['52','54']},
                        {'inicio':'2099-01-01','fim':'2099-01-31'}, {'inicio':'2024-02-02'}):
            with self.subTest(mudanca=mudanca), self.assertRaises(ValueError):
                self.repo.configuracao.planejar(self.selecao | mudanca, piloto_presumido=True)
        pendente = self.regime['rotinas'][-1]
        self.repo.configuracao.salvar_regime(self.regime['id'], self.regime['nome'], [pendente])
        with self.assertRaises(ValueError):self.repo.configuracao.planejar(self.selecao, piloto_presumido=True)

    def test_individual_um_pedido_gera_duas_tarefas_e_finaliza_com_pendencia(self):
        chamadas=[]
        def executar(dados, receber):
            chamadas.append(dados['capacidade']); eventos_confirmados(dados, receber); return True
        servico=self.iniciar(executar); pedido=self.pedido()
        final=self.concluir(servico,pedido)
        self.assertEqual(chamadas,['resumo_acumulador','efd_contribuicoes'])
        self.assertEqual(final['status'],'concluida_com_pendencias')
        self.assertEqual(final['motivo'],'rotinas_nao_integradas')
        relatorio=self.repo.diagnostico_lote(final['id'])
        self.assertFalse(relatorio['homologacao_fiscal'])
        self.assertEqual(len(relatorio['rotinas']),2)
        self.assertEqual(len(relatorio['pendencias_nao_executadas']),1)
        self.assertTrue(all(r['retorno_confirmado'] for r in relatorio['rotinas']))
        self.assertNotIn('pasta_relativa',json.dumps(relatorio))
        self.assertIsNone(self.repo.diagnostico_lote('inexistente'))
        self.assertTrue(all(t['status']=='concluida' for t in final['tarefas']))
        self.assertEqual(servico.solicitar_lote(pedido)['id'],final['id'])
        self.assertEqual(len(chamadas),2)

    def test_lote_agrupa_por_empresa_e_preserva_falha_recuperada(self):
        chamadas=[]
        def executar(dados, receber):
            chamadas.append((dados['empresa_codigo'],dados['capacidade']))
            if len(chamadas)==1:return False
            eventos_confirmados(dados,receber); return True
        executar.recuperar_em_lote=lambda dados:True
        final=self.concluir(self.iniciar(executar),self.pedido(self.selecao | {'empresas':['52','53']}))
        self.assertEqual(chamadas,[('52','resumo_acumulador'),('52','efd_contribuicoes'),('53','resumo_acumulador'),('53','efd_contribuicoes')])
        self.assertEqual(final['status'],'concluida_com_falhas')
        self.assertEqual(final['tarefas'][0]['status'],'falha')
        self.assertEqual(final['plano']['quantidade_pendencias'],2)

    def test_nao_avanca_sem_recuperacao_confirmada(self):
        chamadas=[]
        def executar(dados, receber):chamadas.append(dados); return False
        executar.recuperar_em_lote=lambda dados:False
        final=self.concluir(self.iniciar(executar),self.pedido())
        self.assertEqual(len(chamadas),1)
        self.assertEqual(final['status'],'interrompida')
        self.assertEqual(final['tarefas'][1]['status'],'interrompida')

    def test_hash_inclui_configuracao_pendente_e_nao_vira_lote_comum(self):
        pedido=self.pedido()
        with self.assertRaises(ValueError):self.repo.criar_lote({k:v for k,v in pedido.items() if k!='piloto_presumido'},'simulacao')
        pendente=self.regime['rotinas'][-1]
        self.repo.configuracao.configurar_rotina(pendente,{'nome':'Livros Fiscais novos','passos':[{'tipo':'clicar','valor':'Relatórios'}]})
        with self.assertRaises(ValueError):self.repo.criar_lote(pedido,'simulacao')
        self.assertEqual(self.repo.listar(),[])

    def test_sem_confirmacao_ou_reinicio_nao_repete_emissoes(self):
        pedido=self.pedido()
        with self.assertRaises(ValueError):self.repo.criar_lote(pedido | {'apuracao_confirmada':False},'simulacao')
        lote,_=self.repo.criar_lote(pedido,'simulacao')
        self.repo.retomar()
        repetido,novo=self.repo.criar_lote(pedido,'simulacao')
        self.assertFalse(novo); self.assertEqual(repetido['id'],lote['id'])
        self.assertEqual(repetido['status'],'interrompida'); self.assertIsNone(self.repo.proxima())

    def test_relatorio_preserva_etapa_falha_e_ultima_recuperacao_inconclusiva(self):
        lote,_=self.repo.criar_lote(self.pedido(),'simulacao')
        tarefa=lote['tarefas'][0]
        base={'execution_id':tarefa['pedido']['request_id'].replace('-',''),
              'routine_id':'resumo_acumulador','attempt':1,'elapsed_seconds':0}
        self.repo.registrar_evento(tarefa['id'],base | {'step':'encerrar','status':'confirmado','evidence':'tela_principal_reconhecida'})
        self.repo.registrar_evento(tarefa['id'],base | {'step':'exportar_pdf','status':'falha','evidence':None})
        self.repo.registrar_evento(tarefa['id'],base | {'step':'recuperar_interface','status':'inconclusivo','evidence':None})
        self.repo.concluir(tarefa['id'],'falha',False)
        relatorio=self.repo.diagnostico_lote(lote['id'])
        self.assertEqual(relatorio['rotinas'][0]['etapa_com_falha'],'Exportar PDF')
        self.assertFalse(relatorio['rotinas'][0]['retorno_confirmado'])
        self.assertEqual(relatorio['rotinas'][0]['status'],'falha')
        self.assertEqual(len(relatorio['pendencias_nao_executadas']),1)

    def test_cli_recusa_completo_pendente_e_trava_ocupada_antes_de_emitir(self):
        import contextlib,io
        from unittest.mock import patch,Mock
        from scripts import explorar_presumido
        from app.trava_execucao import TravaExecucao
        raiz=self.repo.caminho.parent.parent
        # O CLI usa este nome fixo para compartilhar histórico com o painel.
        destino=raiz/'data/servidor.sqlite3'
        with self.repo.conectar() as banco:
            import sqlite3
            with sqlite3.connect(destino) as copia:banco.backup(copia)
        executor=Mock()
        args=['--empresa','52','--competencia','2024-02','--apuracao-confirmada']
        with patch.object(explorar_presumido,'ROOT',raiz),patch.object(explorar_presumido.sys,'platform','win32'), \
             patch('app.executor_servidor.ExecutorDominio',return_value=executor), \
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):explorar_presumido.main(args)
            trava=TravaExecucao(raiz/'data/sessao_executor.lock'); trava.adquirir()
            try:self.assertEqual(explorar_presumido.main(args+['--somente-disponiveis']),1)
            finally:trava.liberar()
        executor.assert_not_called()
        self.assertEqual(RepositorioTarefas(destino).listar(),[])

    def test_cli_piloto_parcial_compartilha_worker_e_nao_declara_completo(self):
        import contextlib,io
        from unittest.mock import patch
        from scripts import explorar_presumido
        raiz=self.repo.caminho.parent.parent
        with self.repo.conectar() as banco:
            import sqlite3
            with sqlite3.connect(raiz/'data/servidor.sqlite3') as copia:banco.backup(copia)
        chamadas=[]
        class Executor:
            def executar_em_lote(self,dados,receber):
                chamadas.append(dados['capacidade']); eventos_confirmados(dados,receber); return True
            __call__=executar_em_lote
        saida=io.StringIO()
        with patch.object(explorar_presumido,'ROOT',raiz),patch.object(explorar_presumido.sys,'platform','win32'), \
             patch('app.executor_servidor.ExecutorDominio',return_value=Executor()), \
             patch.object(explorar_presumido.time,'sleep',return_value=None),contextlib.redirect_stdout(saida):
            resultado=explorar_presumido.main(['--empresa','52','--competencia','2024-02','--apuracao-confirmada','--somente-disponiveis'])
        self.assertEqual(resultado,2)
        self.assertEqual(chamadas,['resumo_acumulador','efd_contribuicoes'])
        self.assertIn('concluida_com_pendencias',saida.getvalue())
        self.assertIn('Pendências não executadas: 1',saida.getvalue())

    @unittest.skipUnless(WEB,'API indisponível.')
    def test_api_autenticacao_piloto_e_nao_burla_lote_comum(self):
        def executar(dados,receber):eventos_confirmados(dados,receber); return True
        servico=ServicoExecucao(self.repo,executar,'simulacao'); chave='d'*48; headers={'Authorization':'Bearer '+chave}
        with TestClient(criar_app(servico,chave)) as cliente:
            self.assertEqual(cliente.post('/api/piloto-presumido/planejar',json=self.selecao).status_code,401)
            self.assertEqual(cliente.post('/api/piloto-presumido',json={}).status_code,401)
            self.assertEqual(cliente.get('/api/lotes/inexistente/diagnostico').status_code,401)
            self.assertEqual(cliente.get('/api/lotes/inexistente/diagnostico',headers=headers).status_code,404)
            revisao=cliente.post('/api/piloto-presumido/planejar',json=self.selecao,headers=headers)
            self.assertEqual(revisao.status_code,200)
            pedido={k:v for k,v in self.pedido().items() if k!='piloto_presumido'}
            self.assertEqual(cliente.post('/api/lotes',json=pedido,headers=headers).status_code,422)
            self.assertEqual(cliente.post('/api/piloto-presumido',json=pedido | {'apuracao_confirmada':False},headers=headers).status_code,422)
            resposta=cliente.post('/api/piloto-presumido',json=pedido,headers=headers)
            self.assertEqual(resposta.status_code,202)
            relatorio=cliente.get('/api/lotes/'+resposta.json()['id']+'/diagnostico',headers=headers)
            self.assertEqual(relatorio.status_code,200)
            self.assertEqual(relatorio.headers['cache-control'],'no-store')
            self.assertNotIn('pasta_relativa',relatorio.text)
            self.assertEqual(cliente.post('/api/piloto-presumido',json=pedido,headers=headers).json()['id'],resposta.json()['id'])
