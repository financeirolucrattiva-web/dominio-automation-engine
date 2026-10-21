import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

from app import otimizacoes, tela
from app.controle_execucao import ExecucaoInterrompida


def dados(texto='x'):
    return {'text': [texto], 'left': [0], 'top': [0], 'width': [1], 'height': [1]}


class TestPreAquecerOcr(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(otimizacoes, '_forcado', True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.imagem = Image.new('RGB', (40, 20), 'white')
        self.chamadas = []
        self.simultaneas = 0
        self.maximo = 0
        self.trava = threading.Lock()

    def lento(self, *args, **kwargs):
        with self.trava:
            self.simultaneas += 1
            self.maximo = max(self.maximo, self.simultaneas)
            self.chamadas.append(kwargs.get('config', ''))
        time.sleep(0.15)
        with self.trava:
            self.simultaneas -= 1
        return dados()

    def test_sem_cache_ativo_nao_faz_nada(self):
        with patch('pytesseract.image_to_data', side_effect=self.lento) as ocr:
            tela.pre_aquecer_ocr((self.imagem, [('tesseract', 2), ('tesseract', 4)]))
        ocr.assert_not_called()

    def test_leituras_rodam_em_paralelo_e_o_codigo_sequencial_acha_tudo_pronto(self):
        variantes = [('tesseract', 2), ('tesseract', 4), ('formulario', 4, 'binaria', 6), ('formulario', 4, 'cinza', 11)]
        with patch('pytesseract.image_to_data', side_effect=self.lento), tela.reutilizar_ocr():
            inicio = time.monotonic()
            tela.pre_aquecer_ocr((self.imagem, variantes))
            gasto = time.monotonic() - inicio
            self.assertGreaterEqual(self.maximo, 2)  # houve concorrência
            self.assertLess(gasto, 0.15 * len(variantes))  # mais rápido que em sequência
            antes = len(self.chamadas)
            tela._ler_dados_ocr(self.imagem, 2)
            tela._ler_dados_ocr(self.imagem, 4)
            tela.ler_dados_ocr_formulario(self.imagem, 4, 'binaria', 6)
            tela.ler_dados_ocr_formulario(self.imagem, 4, 'cinza', 11)
            self.assertEqual(len(self.chamadas), antes)  # tudo veio do cache
        self.assertEqual(antes, 4)

    def test_windows_roda_em_sequencia_numa_so_tarefa(self):
        atual = []

        def windows(imagem, escala=2):
            atual.append(threading.get_ident())
            return dados()
        with patch.object(tela, 'ler_dados_ocr_windows', side_effect=windows), \
                patch('pytesseract.image_to_data', side_effect=self.lento), tela.reutilizar_ocr():
            tela.pre_aquecer_ocr((self.imagem, [('windows', 2), ('windows', 4), ('tesseract', 2)]))
        self.assertEqual(len(atual), 2)
        self.assertEqual(len(set(atual)), 1)

    def test_falha_de_uma_variante_nao_derruba_as_outras(self):
        def quebra(imagem, *args, **kwargs):
            if kwargs.get('config') == '--psm 11':
                raise RuntimeError('ocr indisponível')
            return dados()
        with patch('pytesseract.image_to_data', side_effect=quebra), tela.reutilizar_ocr():
            tela.pre_aquecer_ocr((self.imagem, [('formulario', 4, 'cinza', 11), ('formulario', 4, 'cinza', 6)]))
            self.assertEqual(len([k for k in tela._CACHE_OCR.get()]), 1)

    def test_interrupcao_do_operador_propaga(self):
        def para(*args, **kwargs):
            raise ExecucaoInterrompida('teste')
        with patch('pytesseract.image_to_data', side_effect=para), tela.reutilizar_ocr():
            with self.assertRaises(ExecucaoInterrompida):
                tela.pre_aquecer_ocr((self.imagem, [('tesseract', 2), ('tesseract', 4)]))


if __name__ == '__main__':
    unittest.main()
