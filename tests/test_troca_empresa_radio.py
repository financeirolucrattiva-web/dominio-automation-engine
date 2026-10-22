"""Troca de empresas: força "Busca por: Código" antes de digitar (com "Apelido" abria a empresa errada)."""
import unittest
from unittest.mock import patch

from PIL import Image

from app import dominio


def dados(palavras):
    d = {'text': [], 'left': [], 'top': [], 'width': [], 'height': []}
    for texto, x, y in palavras:
        d['text'].append(texto); d['left'].append(x); d['top'].append(y); d['width'].append(60); d['height'].append(20)
    return d


# coordenadas em escala 2 (valores dobrados): Busca por em y=340, Código (radio) em y=390, cabeçalho Código em y=560
LEITURA = dados([('Busca', 990, 340), ('por', 1060, 340), ('Código', 1060, 390), ('Apelido', 1330, 390),
                 ('Código', 1040, 560), ('Apelido', 1480, 560)])


class TestRadioCodigo(unittest.TestCase):
    def test_acha_so_o_codigo_logo_abaixo_de_busca_por_e_nao_o_do_cabecalho(self):
        self.assertEqual(dominio._posicao_radio_codigo(LEITURA, 2), (519, 200))

    def test_sem_busca_por_ou_ambiguo_devolve_none(self):
        self.assertIsNone(dominio._posicao_radio_codigo(dados([('Código', 100, 100)]), 2))
        duas = dados([('Busca', 10, 10), ('por', 80, 10), ('Código', 20, 60), ('Código', 200, 60)])
        self.assertIsNone(dominio._posicao_radio_codigo(duas, 2))

    def test_forcar_clica_uma_vez_e_segue_mesmo_sem_achar(self):
        imagem = Image.new('RGB', (100, 100))
        with patch.object(dominio.tela, 'capturar_tela', return_value=imagem), \
                patch.object(dominio.tela, '_ler_dados_ocr', return_value=LEITURA), \
                patch.object(dominio.interacao, 'clicar') as clique, patch.object(dominio.time, 'sleep'):
            self.assertTrue(dominio._forcar_busca_por_codigo())
        clique.assert_called_once_with(519, 200)
        with patch.object(dominio.tela, 'capturar_tela', return_value=imagem), \
                patch.object(dominio.tela, '_ler_dados_ocr', return_value=dados([])), \
                patch.object(dominio.interacao, 'clicar') as clique, patch.object(dominio, 'salvar'):
            self.assertFalse(dominio._forcar_busca_por_codigo())
        clique.assert_not_called()


if __name__ == '__main__':
    unittest.main()
