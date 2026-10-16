"""Segunda opinião do campo Unidade; respostas locais simuladas, sem WinRT."""
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import seletor_pasta as seletor, tela
from app.controle_execucao import ExecucaoInterrompida
from test_seletor_pasta_ocr import dialogo


def dados_unidade(texto,escala):
    dados={k:[] for k in ('text','left','top','width','height')}
    x=3
    for token in texto.split():
        largura=len(token)*7
        for chave,valor in (('text',token),('left',x*escala),('top',3*escala),
                            ('width',largura*escala),('height',10*escala)):
            dados[chave].append(valor)
        x+=largura+5
    return dados


class TestUnidadeOCRNativo(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.vazio={k:[] for k in ('text','left','top','width','height')}
        self.tesseract=self.stack.enter_context(patch.object(
            tela,'ler_dados_ocr_linha_rotulo',return_value=self.vazio))
        self.nativo=self.stack.enter_context(patch.object(
            tela,'ler_dados_ocr_windows',side_effect=lambda im,escala:
                dados_unidade('Client C (M:)',escala)))
        self.imagem=dialogo()
        self.combo=(105,60,456,27)

    def ler(self):
        return seletor._refinar_unidade(self.imagem,[],self.combo)

    def destino_confirmado(self,palavras):
        return seletor._drive_selecionado({'combo':self.combo,'palavras':palavras},'M')

    def test_duas_leituras_nativas_recuperam_client_c_m_omitido_pelo_tesseract(self):
        self.assertTrue(self.destino_confirmado(self.ler()))
        self.assertEqual(self.tesseract.call_count,4)
        self.assertEqual([c.kwargs['escala'] for c in self.nativo.call_args_list],[4,6])
        self.assertTrue(all(c.args[0].size==(427,23) for c in self.nativo.call_args_list))

    def test_tipo_e_letra_diferentes_nao_liberam_destino_m(self):
        for texto in ('Client Z (M:)','Servidor (M:)','Client C (Q:)'):
            with self.subTest(texto=texto):
                self.nativo.side_effect=lambda im,escala: dados_unidade(texto,escala)
                self.assertFalse(self.destino_confirmado(self.ler()))

    def test_uma_leitura_nativa_sem_segunda_opiniao_nao_basta(self):
        self.nativo.side_effect=[dados_unidade('Client C (M:)',4),None]
        self.assertEqual(self.ler(),[])

    def test_opinioes_nativas_discordantes_nao_escolhem_letra(self):
        self.nativo.side_effect=[dados_unidade('Client C (M:)',4),dados_unidade('Client C (Q:)',6)]
        self.assertEqual(self.ler(),[])

    def test_uma_contradicao_do_tesseract_nao_e_apagada_pelo_nativo(self):
        self.tesseract.side_effect=[dados_unidade('Client Z (M:)',4),self.vazio,self.vazio,self.vazio]
        self.assertEqual(self.ler(),[])

    def test_caixas_nativas_fora_do_recorte_nao_servem_como_opiniao(self):
        def fora(im,escala):
            dados=dados_unidade('Client C (M:)',escala)
            dados['left'][0]=im.width*escala+1
            return dados
        self.nativo.side_effect=fora
        self.assertEqual(self.ler(),[])

    def test_indisponibilidade_nativa_nao_cria_confirmacao(self):
        self.nativo.return_value=None; self.nativo.side_effect=None
        self.assertEqual(self.ler(),[])
        self.nativo.assert_called_once()

    def test_consenso_tesseract_dispensa_nativo(self):
        self.tesseract.side_effect=lambda im,escala,preparo:dados_unidade('Client C (M:)',escala)
        self.assertTrue(self.destino_confirmado(self.ler()))
        self.nativo.assert_not_called()

    def test_cancelamento_nativo_nao_e_tratado_como_leitura_vazia(self):
        self.nativo.side_effect=ExecucaoInterrompida('teste')
        with self.assertRaises(ExecucaoInterrompida):self.ler()


class TestDiagnosticoSomenteUnidade(unittest.TestCase):
    def diagnosticar(self,lista,palavras):
        caminho=Path(__file__).resolve().parents[1]/'scripts'/'revisar_seletor_pasta.py'
        spec=importlib.util.spec_from_file_location('diagnostico_unidade_local',caminho)
        modulo=importlib.util.module_from_spec(spec); spec.loader.exec_module(modulo)
        detalhes={'combo':(105,60,456,27),'lista':lista,'palavras':palavras}
        with tempfile.TemporaryDirectory() as pasta:
            png=Path(pasta)/'unidade-sintetica.png'; dialogo().save(png)
            saida=io.StringIO()
            with contextlib.redirect_stdout(saida), \
                 patch.object(seletor,'medir_dialogo',return_value=detalhes) as medir, \
                 patch.object(seletor,'_completar_dialogo') as arvore, \
                 patch.object(seletor,'_ok_final') as ok:
                self.assertEqual(modulo.main(['--imagem',str(png),'--somente-unidade']),0)
            medir.assert_called_once(); self.assertTrue(medir.call_args.kwargs['somente_unidade'])
            arvore.assert_not_called(); ok.assert_not_called()
        linha=next(l for l in saida.getvalue().splitlines() if l.startswith('PASTA_DIAGNOSTICO '))
        return json.loads(linha.removeprefix('PASTA_DIAGNOSTICO '))

    def test_m_fechado_e_informado_sem_examinar_arvore_ou_ok(self):
        ps=[{'texto':'Client C (M:)','x':112,'y':65,'w':110,'h':12}]
        resultado=self.diagnosticar(None,ps)
        self.assertEqual(resultado['client_c_letras_no_campo'],['M'])
        self.assertFalse(resultado['lista_unidades_aberta'])

    def test_lista_aberta_e_campo_nao_lido_nao_inventam_m(self):
        resultado=self.diagnosticar((105,87,456,80),[])
        self.assertEqual(resultado['client_c_letras_no_campo'],[])
        self.assertTrue(resultado['lista_unidades_aberta'])


if __name__=='__main__':unittest.main()
