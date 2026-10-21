import io
import contextlib
import unittest
from unittest.mock import patch

from app import perfil


class TestPerfil(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(perfil._totais, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_medir_conta_chamadas_e_segundos_e_devolve_o_resultado(self):
        medida = perfil._medir('tesseract', lambda x: x * 2)
        self.assertEqual(medida(21), 42)
        self.assertEqual(perfil.instantaneo()['tesseract'][0], 1)
        self.assertGreaterEqual(perfil.instantaneo()['tesseract'][1], 0)

    def test_excecao_tambem_e_contada_e_propaga(self):
        def quebra():
            raise RuntimeError('x')
        medida = perfil._medir('windows', quebra)
        with self.assertRaises(RuntimeError):
            medida()
        self.assertEqual(perfil.instantaneo()['windows'][0], 1)

    def test_diferenca_e_texto_sem_conteudo_de_tela(self):
        antes = {'tesseract': (2, 4.0)}
        depois = {'tesseract': (5, 10.0), 'windows': (3, 3.5), 'captura': (4, 1.25)}
        delta = perfil.diferenca(antes, depois)
        self.assertEqual(delta, {'tesseract': (3, 6.0), 'windows': (3, 3.5), 'captura': (4, 1.25)})
        self.assertEqual(perfil.texto(delta),
                         'ocr 6x 10s-cpu (tesseract 3x/6s, windows 3x/4s) | captura 4x/1.2s')
        self.assertEqual(perfil.texto({}), 'sem leituras OCR')

    def test_etapas_imprimem_linha_de_perfil_sem_quebrar_a_rotina(self):
        from app.estados import AcompanhamentoRotina
        import tempfile
        from pathlib import Path
        saida = io.StringIO()
        with tempfile.TemporaryDirectory() as pasta, contextlib.redirect_stdout(saida):
            rotina = AcompanhamentoRotina('livros_fiscais', Path(pasta))
            rotina.iniciar('validar_dados')
            rotina.confirmar('datas_validas')
        texto = saida.getvalue()
        self.assertIn('[estado] validar_dados: confirmado', texto)
        self.assertIn('[perfil] validar_dados: ', texto)


if __name__ == '__main__':
    unittest.main()
