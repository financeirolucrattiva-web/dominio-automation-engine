import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from app import leitura_resumo as lr, otimizacoes

CAMPOS = {'inicial': {'retangulo': (609, 423, 83, 19), 'area_texto': (610, 424, 673, 441), 'posicao': (641, 432)},
          'final': {'retangulo': (609, 445, 83, 19), 'area_texto': (610, 446, 673, 463), 'posicao': (641, 454)}}


def tela(rotulo=True):
    imagem = Image.new('RGB', (1000, 600), (240, 240, 240))
    if rotulo:
        desenho = ImageDraw.Draw(imagem)
        desenho.rectangle((552, 427, 574, 436), fill='black')
        desenho.rectangle((552, 449, 574, 458), fill='black')
    return imagem


class TestGeometriaLembrada(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(otimizacoes, '_forcado', True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def lembrar(self, imagem, livros=False):
        lr._GEOMETRIA_LEMBRADA[(livros, imagem.size)] = (CAMPOS, lr._assinatura_dos_rotulos(imagem, CAMPOS))

    def test_rotulos_iguais_pulam_a_leitura_da_tela_inteira(self):
        imagem = tela()
        self.lembrar(imagem)
        valores = {'inicial': {'valor': '01/08/2026', 'posicao': (641, 432)}}
        with patch.object(lr, '_ler_valores', return_value=valores) as ler, \
                patch('app.tela._ler_dados_ocr', side_effect=AssertionError('OCR da tela inteira')):
            self.assertEqual(lr.ler_campos(imagem), valores)
        self.assertEqual(ler.call_args.args[2], [])  # sem leituras globais: só o recorte de cada campo

    def test_rotulos_diferentes_esquecem_e_refazem_a_medicao_completa(self):
        self.lembrar(tela())
        outra = tela(rotulo=False)
        with patch('app.tela._ler_dados_ocr', side_effect=RuntimeError('sem OCR')) as ocr, \
                patch('app.tela.ler_dados_ocr_windows', return_value=None), \
                patch('app.tela.ler_dados_ocr_formulario', return_value=None):
            with self.assertRaises(ValueError):
                lr.ler_campos(outra)
        self.assertTrue(ocr.called)
        self.assertEqual(lr._GEOMETRIA_LEMBRADA, {})

    def test_falha_de_leitura_com_geometria_lembrada_esquece_e_refaz(self):
        imagem = tela()
        self.lembrar(imagem)
        with patch.object(lr, '_ler_valores', side_effect=ValueError('data ilegível')), \
                patch('app.tela._ler_dados_ocr', side_effect=RuntimeError('sem OCR')) as ocr, \
                patch('app.tela.ler_dados_ocr_windows', return_value=None), \
                patch('app.tela.ler_dados_ocr_formulario', return_value=None):
            with self.assertRaises(ValueError):
                lr.ler_campos(imagem)
        self.assertTrue(ocr.called)
        self.assertEqual(lr._GEOMETRIA_LEMBRADA, {})

    def test_medicao_completa_com_duas_leituras_concordantes_grava_a_memoria(self):
        # Regressao (21/10): _ler_campos_medindo usava `otimizacoes` sem importar -> NameError no Resumo e no Livros.
        imagem = tela()
        medidas = {'inicial': {'retangulo': (609, 423, 83, 19), 'area_texto': (610, 424, 673, 441), 'posicao': (641, 432)},
                   'final': {'retangulo': (609, 445, 83, 19), 'area_texto': (610, 446, 673, 463), 'posicao': (641, 454)}}
        valores = {'inicial': {'valor': '01/08/2026', 'posicao': (641, 432)}}
        vazio = {'text': [], 'left': [], 'top': [], 'width': [], 'height': []}
        with patch('app.tela._ler_dados_ocr', return_value=vazio), \
                patch('app.tela.ler_dados_ocr_windows', return_value=vazio), \
                patch('app.tela.ler_dados_ocr_formulario', return_value=vazio), \
                patch.object(lr, 'resolver_rotulos_resumo', return_value=object()), \
                patch.object(lr, 'medir_campos', return_value=medidas), \
                patch.object(lr, 'campos_periodo', side_effect=ValueError('sem leitura global')), \
                patch.object(lr, '_ler_valores', return_value=valores):
            self.assertEqual(lr.ler_campos(imagem), valores)
        self.assertIn((False, imagem.size), lr._GEOMETRIA_LEMBRADA)
        # com a otimizacao desligada a mesma medicao completa funciona e NAO grava
        lr.esquecer_geometria()
        with patch.object(otimizacoes, '_forcado', False), \
                patch('app.tela._ler_dados_ocr', return_value=vazio), \
                patch('app.tela.ler_dados_ocr_windows', return_value=vazio), \
                patch('app.tela.ler_dados_ocr_formulario', return_value=vazio), \
                patch.object(lr, 'resolver_rotulos_resumo', return_value=object()), \
                patch.object(lr, 'medir_campos', return_value=medidas), \
                patch.object(lr, 'campos_periodo', side_effect=ValueError('sem leitura global')), \
                patch.object(lr, '_ler_valores', return_value=valores):
            self.assertEqual(lr.ler_campos(imagem), valores)
        self.assertEqual(lr._GEOMETRIA_LEMBRADA, {})

    def test_resumo_e_livros_nao_compartilham_geometria(self):
        imagem = tela()
        self.lembrar(imagem, livros=False)
        with patch.object(lr, '_ler_valores') as ler, \
                patch('app.tela._ler_dados_ocr', side_effect=RuntimeError('sem OCR')), \
                patch('app.tela.ler_dados_ocr_windows', return_value=None), \
                patch('app.tela.ler_dados_ocr_formulario', return_value=None):
            with self.assertRaises(ValueError):
                lr.ler_campos(imagem, livros=True)
        ler.assert_not_called()


if __name__ == '__main__':
    unittest.main()
