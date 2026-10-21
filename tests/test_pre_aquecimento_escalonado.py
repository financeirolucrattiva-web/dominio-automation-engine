"""O pré-aquecimento paralelo é ESCALONADO: o caso comum (a 1ª leitura já acha) custa o mesmo que antes;
só depois da 1ª falha as outras leituras rodam em paralelo."""
import unittest
from unittest.mock import patch

from PIL import Image

from app import dominio, leitura_resumo, tela
from app.formulario_livros import ler_selecao_com_ocr
from test_formulario_livros import formulario


class TestSelecaoDosLivros(unittest.TestCase):
    def test_primeira_leitura_que_acha_nao_dispara_o_paralelo(self):
        imagem, dados, _ = formulario(('registro_icms',))
        with patch.object(tela, '_ler_dados_ocr', return_value=dados), \
                patch('app.tela.pre_aquecer_ocr') as paralelo:
            resultado = ler_selecao_com_ocr(imagem)
        self.assertTrue(resultado['livros']['registro_icms']['marcada'])
        paralelo.assert_not_called()

    def test_primeira_falha_dispara_as_outras_seis_leituras_em_paralelo_uma_vez(self):
        import copy
        imagem, dados, _ = formulario(('registro_icms',))
        dados4 = copy.deepcopy(dados)
        for chave in ('left', 'top', 'width', 'height'):
            dados4[chave] = [v * 2 for v in dados4[chave]]
        with patch.object(tela, '_ler_dados_ocr', side_effect=[{'text': []}, dados4]), \
                patch('app.tela.pre_aquecer_ocr') as paralelo:
            ler_selecao_com_ocr(imagem)
        paralelo.assert_called_once()
        par, = paralelo.call_args.args
        self.assertIs(par[0], imagem)
        self.assertEqual(par[1], [('tesseract', 4), ('formulario', 4, 'cinza', 6), ('formulario', 4, 'binaria', 6),
                                  ('formulario', 6, 'binaria', 6), ('windows', 2), ('windows', 4)])


class TestFormularioDoResumo(unittest.TestCase):
    def test_so_aquece_o_resto_depois_da_primeira_tentativa_sem_titulo(self):
        imagem = Image.new('RGB', (200, 100), 'white')
        chamadas = []
        vazio = {'text': [], 'left': [], 'top': [], 'width': [], 'height': []}
        with patch.object(tela, 'achar_texto_ou_no_centro', return_value=None), \
                patch.object(tela, 'achar_texto_windows', return_value=None), \
                patch.object(tela, 'ler_dados_ocr_formulario', return_value=vazio):
            self.assertIsNone(leitura_resumo._formulario_resumo_reconhecido(
                imagem, lambda **k: None, lambda: chamadas.append('resto')))
        self.assertEqual(chamadas, ['resto'])

    def test_titulo_na_primeira_tentativa_nao_aquece_o_resto(self):
        imagem = Image.new('RGB', (200, 100), 'white')
        chamadas = []
        with patch.object(tela, 'achar_texto_ou_no_centro', return_value=(10, 10)), \
                patch.object(tela, '_ler_dados_ocr', return_value={'text': []}), \
                patch.object(leitura_resumo, 'resolver_rotulos_resumo', return_value=object()), \
                patch.object(leitura_resumo, 'medir_campos', return_value={}):
            self.assertEqual(leitura_resumo._formulario_resumo_reconhecido(
                imagem, lambda **k: None, lambda: chamadas.append('resto')), (10, 10))
        self.assertEqual(chamadas, [])


class TestBuscaReforcada(unittest.TestCase):
    def setUp(self):
        self.imagem = Image.new('RGB', (200, 100), 'white')

    def executar(self, achou_em, **kw):
        respostas = iter(achou_em)
        with patch.object(dominio.tela, 'achar_texto_ou_no_centro', side_effect=lambda *a, **k: next(respostas)), \
                patch.object(dominio.tela, 'achar_texto_windows', return_value=None), \
                patch('app.tela.pre_aquecer_deteccao') as paralelo:
            resultado = dominio._achar_texto_reforcado(self.imagem, 'x', **kw)
        return resultado, paralelo.call_args_list

    def test_acha_na_primeira_escala_so_aquece_a_primeira_tela_e_centro(self):
        resultado, chamadas = self.executar([(5, 5)], escalas_adicionais=(4,), ocr_windows=True)
        self.assertEqual(resultado, (5, 5))
        self.assertEqual([c.args[1] for c in chamadas], [[('tesseract', 2)]])

    def test_falha_na_primeira_aquece_o_restante_uma_vez(self):
        resultado, chamadas = self.executar([None, (7, 7)], escalas_adicionais=(4,), ocr_windows=True)
        self.assertEqual(resultado, (7, 7))
        self.assertEqual([c.args[1] for c in chamadas],
                         [[('tesseract', 2)], [('tesseract', 4), ('windows', 2), ('windows', 4)]])
        self.assertEqual(chamadas[1].args[1], chamadas[1].args[2])  # mesmas variantes na tela e no centro

    def test_uma_escala_com_windows_aquece_o_windows_antes_de_usar_o_windows(self):
        resultado, chamadas = self.executar([None], ocr_windows=True)
        self.assertIsNone(resultado)
        self.assertEqual([c.args[1] for c in chamadas], [[('tesseract', 2)], [('windows', 2)]])

    def test_sem_windows_e_uma_escala_nao_ha_o_que_aquecer_alem_da_primeira(self):
        resultado, chamadas = self.executar([None])
        self.assertIsNone(resultado)
        self.assertEqual([c.args[1] for c in chamadas], [[('tesseract', 2)]])


if __name__ == '__main__':
    unittest.main()
