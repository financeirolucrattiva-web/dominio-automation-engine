"""Leitura de formulário no worker: exclusividade, cancelamento e saída limitada."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from app.autenticacao import SessaoLogin, LoginRecusado
from app.formulario_livros import ler_formulario, ler_com_ocr, resumo_diagnostico
from app.login_windows import LoginWindows
from app.servidor import RepositorioTarefas, ServicoExecucao, SessaoOcupada
from test_formulario_livros import formulario
from test_servidor import pedido
from test_controle_execucao import esperar

WEB=all(importlib.util.find_spec(n) for n in ('fastapi','httpx'))
if WEB:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app


def leitura():
    imagem,dados,_=formulario(('registro_icms',))
    return ler_formulario(imagem,dados)


class TestDiagnosticoLivros(unittest.TestCase):
    def test_resumo_so_contem_estados_datas_medidas_e_nunca_texto_livre(self):
        resultado=leitura(); resultado['texto_ocr']='PRIVADO'
        resultado['periodo']['inicial']['texto']='CNPJ PRIVADO'
        resumo=resumo_diagnostico(resultado)
        self.assertNotIn('PRIVADO',json.dumps(resumo))
        self.assertFalse(resumo['emissao_realizada'])
        self.assertEqual(resumo['outras_opcoes_marcadas'],0)
        self.assertTrue(resumo['livros']['registro_icms']['marcada'])
        for mutar in (lambda r:r['livros']['registro_icms'].update(marcada='sim'),
                      lambda r:r['periodo']['inicial'].update(valor='PRIVADO'),
                      lambda r:r['livros']['registro_icms'].update(retangulo=[1,2,3,'PRIVADO'])):
            invalido=copy.deepcopy(resultado); mutar(invalido)
            with self.assertRaises(ValueError):resumo_diagnostico(invalido)

    def test_estado_copia_resultado_e_limpa_no_novo_pedido_ou_cancelamento(self):
        sessao=SessaoLogin(); sessao.iniciar(); sessao.concluir_livros(leitura())
        publico=sessao.publico(); antigo=publico['operacao_id']
        publico['livros']['livros']['registro_icms']['marcada']=False
        self.assertTrue(sessao.publico()['livros']['livros']['registro_icms']['marcada'])
        sessao.iniciar(); self.assertNotEqual(sessao.publico()['operacao_id'],antigo)
        self.assertIsNone(sessao.publico()['livros'])
        sessao.cancelar()
        with self.assertRaises(LoginRecusado):sessao.concluir_livros(leitura())
        self.assertIsNone(sessao.publico()['livros'])

    def test_reutiliza_duas_escalas_e_fallback_windows_sem_mutar_imagem(self):
        imagem,dados,_=formulario(); antes=imagem.tobytes(); tela=Mock()
        maiores=copy.deepcopy(dados)
        for chave in ('left','top','width','height'):maiores[chave]=[v*2 for v in dados[chave]]
        tela._ler_dados_ocr.side_effect=[{'text':[]},maiores]
        with patch.multiple('app',create=True,tela=tela):
            resultado=ler_com_ocr(imagem)
        tela.ler_dados_ocr_windows.assert_not_called()
        self.assertEqual(resultado['periodo']['final']['valor'],'30/09/2026')
        tela._ler_dados_ocr.side_effect=[{'text':[]},{'text':[]}]
        tela.ler_dados_ocr_windows.return_value=dados
        with patch.multiple('app',create=True,tela=tela):
            self.assertEqual(ler_com_ocr(imagem),resultado)
        tela.ler_dados_ocr_windows.assert_called_once_with(imagem,2)
        self.assertEqual(imagem.tobytes(),antes)

    def test_adapter_windows_so_captura_formulario_e_nao_chama_cliques(self):
        imagem,dados,_=formulario(); resultado=ler_formulario(imagem,dados)
        login=LoginWindows(); sessao=SessaoLogin(); sessao.iniciar()
        interacao=Mock(); interacao._titulo_dominio.return_value=True; tela=Mock()
        with patch.multiple('app',create=True,interacao=interacao,tela=tela), \
             patch.object(login,'_janelas_visiveis',return_value=[{'hwnd':1,'titulo':'Domínio'}]), \
             patch.object(login,'_capturar',return_value=(imagem,(0,0))), \
             patch('app.formulario_livros.ler_com_ocr',return_value=resultado):
            self.assertEqual(login.revisar_livros(sessao),resultado)
        tela.salvar.assert_called_once(); interacao.clicar.assert_not_called()
        interacao.digitar.assert_not_called(); interacao.pressionar_enter.assert_not_called()


@unittest.skipUnless(WEB,'API indisponível.')
class TestApiDiagnosticoLivros(unittest.TestCase):
    def setUp(self):
        pasta=tempfile.TemporaryDirectory(); self.addCleanup(pasta.cleanup)
        self.repo=RepositorioTarefas(Path(pasta.name)/'banco.sqlite3')
        self.login=Mock(); self.login.revisar_livros.return_value=leitura()
        self.servico=ServicoExecucao(self.repo,lambda dados,receber:False,'simulacao',login=self.login)
        self.chave='d'*48; self.headers={'Authorization':'Bearer '+self.chave}
        self.cliente=TestClient(criar_app(self.servico,self.chave))
        self.cliente.__enter__(); self.addCleanup(self.cliente.__exit__,None,None,None)

    def test_api_autenticada_so_le_e_retorna_medidas_sem_criar_tarefa(self):
        rota='/api/sessao/livros/conferir'
        self.assertEqual(self.cliente.post(rota).status_code,401)
        self.assertEqual(self.cliente.post(rota,headers=self.headers).status_code,202)
        esperar(lambda:not self.servico.ocupado)
        resposta=self.cliente.get('/api/estado',headers=self.headers)
        self.assertEqual(resposta.json()['login']['estado'],'livros_conferidos')
        self.assertFalse(resposta.json()['login']['livros']['emissao_realizada'])
        self.assertEqual(self.repo.listar(),[])
        self.assertEqual(resposta.headers['cache-control'],'no-store')

    def test_diagnostico_exclusivo_e_cancelamento_nao_publica_resultado_tardio(self):
        entrou,liberar=threading.Event(),threading.Event(); self.addCleanup(liberar.set)
        def revisar(sessao):entrou.set(); liberar.wait(3); return leitura()
        self.login.revisar_livros.side_effect=revisar
        self.assertEqual(self.cliente.post('/api/sessao/livros/conferir',headers=self.headers).status_code,202)
        self.assertTrue(entrou.wait(3))
        self.assertEqual(self.cliente.post('/api/sessao/livros/conferir',headers=self.headers).status_code,409)
        with self.assertRaises(SessaoOcupada):self.servico.solicitar(pedido())
        self.cliente.post('/api/login/cancelar',headers=self.headers); liberar.set()
        esperar(lambda:not self.servico.ocupado)
        self.assertEqual(self.servico.estado_login()['estado'],'cancelado')
        self.assertIsNone(self.servico.estado_login()['livros'])

    def test_falha_de_leitura_nao_expoe_erro_privado_ou_sucesso_anterior(self):
        self.cliente.post('/api/sessao/livros/conferir',headers=self.headers); esperar(lambda:not self.servico.ocupado)
        self.login.revisar_livros.side_effect=RuntimeError('CNPJ PRIVADO')
        self.cliente.post('/api/sessao/livros/conferir',headers=self.headers); esperar(lambda:not self.servico.ocupado)
        estado=self.servico.estado_login()
        self.assertEqual(estado['estado'],'falha'); self.assertIsNone(estado['livros'])
        self.assertEqual(estado['motivo'],'diagnostico_livros_nao_confirmado')
        self.assertNotIn('PRIVADO',json.dumps(estado))
