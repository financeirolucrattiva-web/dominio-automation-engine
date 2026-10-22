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
            tela.pre_aquecer_ocr((self.imagem, variantes))
            # A prova é a concorrência observada (não o relógio: sob carga de CPU o tempo oscila).
            self.assertGreaterEqual(self.maximo, 2)
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

    def test_pre_aquecer_deteccao_le_tela_e_centro_em_paralelo_e_o_detector_acha_tudo_pronto(self):
        imagem = Image.new('RGB', (1000, 600), 'white')
        with patch('pytesseract.image_to_data', side_effect=self.lento), tela.reutilizar_ocr():
            tela.pre_aquecer_deteccao(imagem, [('tesseract', 2), ('tesseract', 4)], [('tesseract', 2), ('tesseract', 4)])
            feitas = len(self.chamadas)
            tela.achar_texto_ou_no_centro(imagem, 'qualquer', escala=2)  # tela (miss) e depois centro
            tela.achar_texto_ou_no_centro(imagem, 'qualquer', escala=4)
            self.assertEqual(len(self.chamadas), feitas)  # nada novo: veio do cache
        self.assertEqual(feitas, 4)

    def test_pre_aquecer_deteccao_nao_toca_na_imagem_com_a_otimizacao_desligada_nem_quebra_com_imagem_estranha(self):
        with patch.object(otimizacoes, '_forcado', False), tela.reutilizar_ocr():
            tela.pre_aquecer_deteccao('nao e imagem')  # desligada: nem olha a imagem
        with tela.reutilizar_ocr():
            tela.pre_aquecer_deteccao('nao e imagem')  # ligada: recorte falha e e ignorado
        with patch('pytesseract.image_to_data', side_effect=self.lento):
            tela.pre_aquecer_deteccao(self.imagem)  # sem cache de checagem ativo: nada
        self.assertEqual(self.chamadas, [])

    def test_mapear_em_paralelo_devolve_na_ordem_captura_erros_e_roda_os_seriais_numa_thread(self):
        threads = []

        def tarefa(i, falha=False, serial=False):
            def f():
                if serial:
                    threads.append(threading.get_ident())
                time.sleep(0.05)
                if falha:
                    raise RuntimeError('x%d' % i)
                return i
            return f
        tarefas = [tarefa(0), tarefa(1, falha=True), tarefa(2, serial=True), tarefa(3), tarefa(4, serial=True)]
        resultado = tela.mapear_em_paralelo(tarefas, seriais=(2, 4))
        self.assertEqual([r[0] for r in resultado], ['ok', 'erro', 'ok', 'ok', 'ok'])
        self.assertEqual([r[1] for r in resultado if r[0] == 'ok'], [0, 2, 3, 4])
        self.assertIsInstance(resultado[1][1], RuntimeError)
        self.assertEqual(len(set(threads)), 1)  # os seriais compartilham uma thread

    def test_mapear_em_paralelo_com_a_otimizacao_desligada_roda_em_sequencia_na_ordem(self):
        ordem = []
        tarefas = [lambda i=i: ordem.append(i) or i for i in range(5)]
        with patch.object(otimizacoes, '_forcado', False):
            resultado = tela.mapear_em_paralelo(tarefas)
        self.assertEqual(ordem, [0, 1, 2, 3, 4])
        self.assertEqual([r[1] for r in resultado], [0, 1, 2, 3, 4])

    def test_mapear_em_paralelo_propaga_interrupcao_do_operador(self):
        def para():
            raise ExecucaoInterrompida('teste')
        with self.assertRaises(ExecucaoInterrompida):
            tela.mapear_em_paralelo([lambda: 1, para, lambda: 3])

    def test_ler_valores_da_o_mesmo_resultado_em_paralelo_e_em_sequencia(self):
        from app import leitura_resumo as lr
        campos = {'inicial': {'retangulo': (10, 10, 80, 19), 'area_texto': (10, 10, 70, 28), 'posicao': (20, 20)},
                  'final': {'retangulo': (10, 40, 80, 19), 'area_texto': (10, 40, 70, 58), 'posicao': (20, 50)}}
        imagem = Image.new('RGB', (200, 100), 'white')
        dados = {'text': ['01/08/2026'], 'left': [0], 'top': [5], 'width': [60], 'height': [10]}

        def executar():
            with patch.object(tela, 'ler_dados_ocr_linha_data', return_value=dados), \
                    patch.object(tela, 'ler_dados_ocr_windows', return_value=dados):
                return lr._ler_valores(imagem, campos, [], None, None)
        em_paralelo = executar()
        with patch.object(otimizacoes, '_forcado', False):
            em_sequencia = executar()
        self.assertEqual(em_paralelo, em_sequencia)
        self.assertEqual(em_paralelo['inicial']['valor'], '01/08/2026')

    def test_interrupcao_do_operador_propaga(self):
        def para(*args, **kwargs):
            raise ExecucaoInterrompida('teste')
        with patch('pytesseract.image_to_data', side_effect=para), tela.reutilizar_ocr():
            with self.assertRaises(ExecucaoInterrompida):
                tela.pre_aquecer_ocr((self.imagem, [('tesseract', 2), ('tesseract', 4)]))


if __name__ == '__main__':
    unittest.main()
