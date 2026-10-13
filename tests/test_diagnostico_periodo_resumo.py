"""Datas e medidas são diagnósticos; nunca habilitam geração por si só."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PIL import Image

from scripts.revisar_periodo_resumo import dados_limitados,main
from test_resumo_acumulador import dados_ocr
from test_servidor import BaseRepositorio
from test_controle_execucao import esperar
from app.servidor import ServicoExecucao


class TestDiagnosticoPeriodoResumo(unittest.TestCase):
    def test_so_imprime_rotulos_e_datas_alinhadas_sem_texto_livre(self):
        dados=dados_ocr()
        for texto,x,y in (('CNPJ PRIVADO',600,80),('01/10/2026',600,200)):
            for chave,valor in zip(dados,(texto,x*2,y*2,60,40)):dados[chave].append(valor)
        texto=json.dumps(dados_limitados(dados,2))
        self.assertNotIn('PRIVADO',texto); self.assertNotIn('01/10/2026',texto)
        self.assertIn('01/08/2026',texto)

    def test_cli_png_tenta_motores_sem_alterar_arquivo_ou_operar_desktop(self):
        def dados_na_escala(imagem,escala):
            dados=dados_ocr()
            for chave in ('left','top','width','height'):dados[chave]=[v*escala/2 for v in dados[chave]]
            return dados
        tela=Mock(); tela._ler_dados_ocr.side_effect=dados_na_escala
        tela.ler_dados_ocr_windows.return_value=None
        with tempfile.TemporaryDirectory() as pasta:
            caminho=Path(pasta)/'formulario.png'; Image.new('RGB',(400,300)).save(caminho)
            original=caminho.read_bytes(); saida=io.StringIO()
            with patch.multiple('app',create=True,tela=tela),contextlib.redirect_stdout(saida):
                self.assertEqual(main(['--imagem',str(caminho)]),0)
            self.assertEqual(caminho.read_bytes(),original)
            tela.capturar_tela.assert_not_called(); tela.salvar.assert_not_called()
            self.assertIn('RESUMO_LEITURA',saida.getvalue()); self.assertIn('nenhum relatório foi emitido',saida.getvalue())

    def test_formulario_errado_e_ocr_incompleto_nao_confirmam_datas(self):
        tela=Mock(); tela.achar_texto_ou_no_centro.return_value=None
        tela.achar_texto_windows.return_value=None
        with tempfile.TemporaryDirectory() as pasta:
            caminho=Path(pasta)/'formulario.png'; Image.new('RGB',(400,300)).save(caminho)
            with patch.multiple('app',create=True,tela=tela),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--imagem',str(caminho)]),1)
                tela._ler_dados_ocr.assert_not_called()
                tela.achar_texto_ou_no_centro.return_value=(10,20)
                tela._ler_dados_ocr.return_value={'text':[]}; tela.ler_dados_ocr_windows.return_value=None
                self.assertEqual(main(['--imagem',str(caminho)]),1)

    def test_erro_do_ocr_e_png_ilegivel_nao_imprimem_excecao_ou_caminho(self):
        tela=Mock(); tela.achar_texto_ou_no_centro.side_effect=RuntimeError('PRIVADO')
        tela.achar_texto_windows.side_effect=RuntimeError('PRIVADO')
        with tempfile.TemporaryDirectory() as pasta:
            caminho=Path(pasta)/'PRIVADO.png'; Image.new('RGB',(400,300)).save(caminho)
            for invalido in (False,True):
                if invalido:caminho.write_bytes(b'PRIVADO')
                saida=io.StringIO()
                with patch.multiple('app',create=True,tela=tela),contextlib.redirect_stdout(saida):
                    self.assertEqual(main(['--imagem',str(caminho)]),1)
                self.assertNotIn('PRIVADO',saida.getvalue()); self.assertNotIn('Traceback',saida.getvalue())
                tela._ler_dados_ocr.assert_not_called()

    def test_windows_pode_ler_titulo_e_campos_quando_tesseract_indisponivel(self):
        tela=Mock(); tela.achar_texto_ou_no_centro.side_effect=RuntimeError('PRIVADO')
        tela.achar_texto_windows.return_value=(10,20)
        tela._ler_dados_ocr.side_effect=RuntimeError('PRIVADO')
        def dados_windows(imagem,escala):
            dados=dados_ocr()
            for chave in ('left','top','width','height'):dados[chave]=[v*escala/2 for v in dados[chave]]
            return dados
        tela.ler_dados_ocr_windows.side_effect=dados_windows
        with tempfile.TemporaryDirectory() as pasta:
            caminho=Path(pasta)/'formulario.png'; Image.new('RGB',(400,300)).save(caminho)
            saida=io.StringIO()
            with patch.multiple('app',create=True,tela=tela),contextlib.redirect_stdout(saida):
                self.assertEqual(main(['--imagem',str(caminho)]),0)
            self.assertIn('"motor": "windows"',saida.getvalue()); self.assertNotIn('PRIVADO',saida.getvalue())


class TestMotivoPeriodoWorker(BaseRepositorio,unittest.TestCase):
    def test_motivo_fixo_sobrevive_recuperacao_ao_painel_e_relatorio(self):
        self.repo.configuracao.preparar_piloto()
        regime=next(r for r in self.repo.configuracao.listar()['regimes'] if r['nome']=='Lucro Presumido')
        self.repo.configuracao.salvar_regime(regime['id'],regime['nome'],['resumo_acumulador','efd_contribuicoes'])
        self.repo.configuracao.salvar_empresa('52','Empresa Fictícia',regime['id'])
        chamadas=[]
        def executar(pedido,receber):
            chamadas.append(pedido['capacidade'])
            base={'execution_id':pedido['request_id'].replace('-',''),'routine_id':pedido['capacidade'],
                  'attempt':1,'elapsed_seconds':0}
            if pedido['capacidade']=='resumo_acumulador':
                receber(base | {'step':'preencher_periodo','status':'falha','evidence':'data_inicial_resumo_nao_confirmada'})
                receber(base | {'step':'fim','status':'falha','evidence':'data_inicial_resumo_nao_confirmada'})
                return False
            from test_servidor import eventos_confirmados
            eventos_confirmados(pedido,receber); return True
        executar.recuperar_em_lote=lambda pedido:True
        servico=ServicoExecucao(self.repo,executar,'simulacao'); servico.iniciar(); self.addCleanup(servico.encerrar)
        selecao={'empresas':['52'],'inicio':'2024-02-01','fim':'2024-02-29'}
        plano=self.repo.configuracao.planejar(selecao,piloto_presumido=True)
        import uuid
        lote=servico.solicitar_lote(selecao | {'request_id':str(uuid.uuid4()),'plano_hash':plano['hash'],
            'apuracao_confirmada':True,'piloto_presumido':True})
        esperar(lambda:self.repo.obter_lote(lote['id'])['status'] not in ('pendente','executando'))
        final=self.repo.obter_lote(lote['id'])
        self.assertEqual(final['tarefas'][0]['motivo'],'data_inicial_resumo_nao_confirmada')
        self.assertEqual(final['tarefas'][0]['status'],'falha'); self.assertEqual(len(chamadas),2)
        relatorio=self.repo.diagnostico_lote(lote['id'])['rotinas'][0]
        self.assertEqual(relatorio['motivo'],'data_inicial_resumo_nao_confirmada')
        self.assertEqual(relatorio['etapa_com_falha'],'Preencher período'); self.assertTrue(relatorio['retorno_confirmado'])
