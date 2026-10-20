"""Reprodução da saída real lient C (M:N), sem operar GUI fiscal."""
import contextlib
import io
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch

from app import leitura_unidade as leitura, referencia_unidade as ref, seletor_pasta as seletor, tela
from test_seletor_pasta_ocr import dialogo
from test_unidade_pasta_ocr_nativo import dados_unidade
from test_percurso_referencia_unidade import ArvoreComCampoIlegivel, DESTINO


class TestConsensoVariante(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.vazio={k:[] for k in ('text','left','top','width','height')}
        self.ocr=self.stack.enter_context(patch.object(tela,'ler_dados_ocr_linha_rotulo',
            side_effect=lambda im,escala,preparo:dados_unidade('lient C (M:N)',escala)))
        self.nativo=self.stack.enter_context(patch.object(tela,'ler_dados_ocr_windows',return_value=None))
        self.im=dialogo(); self.combo=(105,60,456,27)

    def ler(self,imagem=None,palavras=None):
        return seletor._refinar_unidade(imagem or self.im,palavras or [],self.combo)

    def drive(self,ps,letra='M'):
        return seletor._drive_selecionado({'combo':self.combo,'palavras':ps},letra)

    def test_variante_real_exige_consenso_e_preserva_texto_bruto(self):
        ps=self.ler()
        self.assertTrue(self.drive(ps)); self.assertFalse(self.drive(ps,'Q'))
        self.assertEqual([p['texto'] for p in ps],['lient','C','(M:N)'])
        self.assertTrue(all(p['_identidade_campo_confirmada']=='clientc:m' for p in ps))
        self.assertEqual(self.ocr.call_count,4)
        self.nativo.assert_not_called()

    def test_uma_leitura_global_malformada_nao_autoriza_destino(self):
        ps=[{'texto':'lient C (M:N)','x':112,'y':65,'w':110,'h':12}]
        self.ocr.side_effect=None; self.ocr.return_value=self.vazio
        self.assertFalse(self.drive(self.ler(palavras=ps)))

    def test_uma_opiniao_local_nao_basta(self):
        self.ocr.side_effect=[dados_unidade('lient C (M:N)',4),self.vazio,self.vazio,self.vazio]
        self.assertFalse(self.drive(self.ler()))

    def test_tipo_e_letra_continuam_literais_nunca_substituidos_pelo_esperado(self):
        for texto in ('lient Z (M:N)','lient C (Q:N)'):
            with self.subTest(texto=texto):
                self.ocr.side_effect=lambda im,escala,preparo:dados_unidade(texto,escala)
                self.assertFalse(self.drive(self.ler()))

    def test_opinioes_contraditorias_nao_formam_consenso(self):
        self.ocr.side_effect=[dados_unidade('lient C (M:N)',4),dados_unidade('lient C (Q:N)',4),
            dados_unidade('lient C (M:N)',6),dados_unidade('lient C (M:N)',6)]
        self.assertEqual(self.ler(),[])

    def test_my_hy_e_nomes_incompletos_nao_sao_reparados(self):
        for texto in ('Client C ‘My','Client C ‘Hy','Client C (MNN)','lient (M:N)',
                      'Client C (MN:)','Client C (M:N) outra coisa'):
            with self.subTest(texto=texto):
                self.ocr.side_effect=lambda im,escala,preparo:dados_unidade(texto,escala)
                self.assertFalse(self.drive(self.ler()))

    def test_caixas_fora_da_roi_nao_comprovam_variante(self):
        def fora(im,escala,preparo):
            d=dados_unidade('lient C (M:N)',escala); d['left'][0]=-1
            return d
        self.ocr.side_effect=fora
        self.assertEqual(self.ler(),[])

    def test_cache_so_reutiliza_roi_identica_e_descarta_ao_sair_da_navegacao(self):
        with leitura.cache_da_navegacao():
            self.assertTrue(self.drive(self.ler())); self.assertEqual(self.ocr.call_count,4)
            outra=self.im.copy(); outra.putpixel((20,180),(255,0,255))
            self.assertTrue(self.drive(self.ler(outra))); self.assertEqual(self.ocr.call_count,4)
            outra.putpixel((150,70),(255,0,255))
            self.assertTrue(self.drive(self.ler(outra))); self.assertEqual(self.ocr.call_count,8)
            contradicao=[{'texto':'Client Z (M:)','x':112,'y':65,'w':110,'h':12}]
            self.assertFalse(self.drive(self.ler(palavras=contradicao)))
        with leitura.cache_da_navegacao():
            self.assertTrue(self.drive(self.ler())); self.assertEqual(self.ocr.call_count,12)


class TestPercursoSemCalibracao(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        pasta=self.stack.enter_context(tempfile.TemporaryDirectory())
        self.ref=Path(pasta)/'nao_calibrada.json'
        self.stack.enter_context(patch.object(ref,'ARQUIVO',self.ref))
        self.stack.enter_context(patch.object(seletor,'_palavras',
            side_effect=lambda im:im.info['palavras_sinteticas']))
        self.stack.enter_context(patch.object(seletor.time,'sleep'))
        self.ocr=self.stack.enter_context(patch.object(tela,'ler_dados_ocr_linha_rotulo',
            side_effect=lambda im,escala,preparo:dados_unidade('lient C (M:N)',escala)))
        self.stack.enter_context(patch.object(tela,'ler_dados_ocr_windows',return_value=None))
        self.saida=io.StringIO(); self.stack.enter_context(contextlib.redirect_stdout(self.saida))

    def executar(self,arvore):
        return seletor.selecionar_pasta(DESTINO,arvore.capturar,arvore.clicar,arvore.tecla)

    def test_c_m_clique_vazio_home_desce_users_perfil_projeto_saida_e_ok(self):
        arvore=ArvoreComCampoIlegivel()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.teclas_combo,['down'])
        self.assertEqual(arvore.cliques_vazio,1)
        self.assertEqual(arvore.cliques_ok,[('Client C (M:\\)',PureWindowsPath(DESTINO).parts[1:])])
        self.assertFalse(self.ref.exists())
        self.assertIn('descendo pela árvore até Users',self.saida.getvalue())
        self.assertIn('pasta 5 de 5 confirmada',self.saida.getvalue())
        # Árvore tem 19 raízes + 33 pastas no perfil. Só relê OCR quando
        # os pixels do campo mudam (azul -> sem azul), não em cada Down.
        self.assertLessEqual(self.ocr.call_count,12)

    def test_m_ja_selecionado_nao_recebe_down_no_combo_e_foca_o_vazio(self):
        arvore=ArvoreComCampoIlegivel('Client C (M:\\)')
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.teclas_combo,[])
        self.assertEqual(arvore.cliques_vazio,1)
        self.assertEqual(len(arvore.cliques_ok),1)

    def test_outra_unidade_nao_libera_descida_ou_ok(self):
        for texto in ('lient Z (M:N)','lient C (Q:N)'):
            with self.subTest(texto=texto):
                self.ocr.side_effect=lambda im,escala,preparo:dados_unidade(texto,escala)
                arvore=ArvoreComCampoIlegivel()
                with self.assertRaises(seletor.SeletorPastaNaoConfirmado):self.executar(arvore)
                self.assertEqual(arvore.cliques_ok,[])
                self.assertNotIn('home',arvore.teclas)


if __name__=='__main__':unittest.main()
