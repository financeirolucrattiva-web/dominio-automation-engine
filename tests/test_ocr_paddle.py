"""Contrato de percepção opcional; sem Paddle, pesos ou dados de clientes."""

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from app import ocr_paddle


def resultado(textos=None):
    return {"rec_texts": textos or ["Relatórios"], "rec_scores": [0.98],
            "rec_polys": [[[5, 6], [25, 6], [25, 16], [5, 16]]]}


class TestNormalizacao(unittest.TestCase):
    def test_poligono_original_e_caixa_alternativa(self):
        valores = ocr_paddle.normalizar_resultado(resultado(), (100, 80))
        self.assertEqual(valores[0].caixa, (5, 6, 25, 16))
        self.assertEqual(valores[0].texto, "Relatórios")
        self.assertAlmostEqual(valores[0].confianca, 0.98)
        caixas = {"rec_texts": ["Final"], "rec_scores": [0.8], "rec_boxes": [[1, 2, 99, 79]]}
        self.assertEqual(ocr_paddle.normalizar_resultado(caixas, (100, 80))[0].caixa, (1, 2, 99, 79))

    def test_vazio_valido_diferente_de_esquema_ausente(self):
        self.assertEqual(ocr_paddle.normalizar_resultado(
            {"rec_texts": [], "rec_scores": [], "rec_boxes": []}, (10, 10)), ())
        with self.assertRaises(ocr_paddle.ErroOCRPaddle):
            ocr_paddle.normalizar_resultado({}, (10, 10))

    def test_contagens_invalidas_nao_sao_truncadas(self):
        for campo, valor in (("rec_texts", ["um", "dois"]), ("rec_scores", []), ("rec_polys", [])):
            dados = resultado()
            dados[campo] = valor
            with self.subTest(campo=campo), self.assertRaises(ocr_paddle.ErroOCRPaddle):
                ocr_paddle.normalizar_resultado(dados, (100, 80))

    def test_confianca_finita_entre_zero_e_um(self):
        for score in (float("nan"), float("inf"), -0.1, 1.01, True, "0.5"):
            dados = resultado()
            dados["rec_scores"] = [score]
            with self.subTest(score=score), self.assertRaises(ocr_paddle.ErroOCRPaddle):
                ocr_paddle.normalizar_resultado(dados, (100, 80))

    def test_caixa_fora_imagem_sem_area_ou_malformada_recusada(self):
        for caixa in ((-1, 1, 3, 4), (1, 1, 101, 4), (1, 1, 3, 81),
                      (3, 1, 3, 4), (5, 1, 3, 4), (1, float("nan"), 3, 4), (1, 2, 3)):
            dados = {"rec_texts": ["Privado"], "rec_scores": [0.9], "rec_boxes": [caixa]}
            with self.subTest(caixa=caixa), self.assertRaises(ocr_paddle.ErroOCRPaddle) as erro:
                ocr_paddle.normalizar_resultado(dados, (100, 80))
            self.assertNotIn("Privado", str(erro.exception))

    def test_poligono_e_segunda_geometria_invalidos_nao_ignorados(self):
        dados = resultado()
        dados["rec_polys"][0][0] = [-1, 6]
        with self.assertRaises(ocr_paddle.ErroOCRPaddle):
            ocr_paddle.normalizar_resultado(dados, (100, 80))
        dados = resultado()
        dados["rec_boxes"] = []
        with self.assertRaises(ocr_paddle.ErroOCRPaddle):
            ocr_paddle.normalizar_resultado(dados, (100, 80))


class TestProcessador(unittest.TestCase):
    def test_importacao_nao_carrega_backend_desktop_ou_paddle(self):
        codigo = """
import builtins
original = builtins.__import__
def importar(nome, *args, **kwargs):
    if nome in {'paddleocr', 'paddle', 'app.tela', 'app.dominio', 'pyautogui'}:
        raise AssertionError('Importação opcional prematura')
    return original(nome, *args, **kwargs)
builtins.__import__ = importar
from app import ocr_paddle
ocr_paddle.OCRPaddleCPU()
"""
        processo = subprocess.run([sys.executable, "-c", codigo],
                                  cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(processo.returncode, 0, processo.stderr)

    def test_fabrica_unica_pixels_bgr_e_saida_fornecedor_suprimida(self):
        def prever(*, input):
            self.assertEqual(input.shape, (80, 100, 3))
            self.assertEqual(input[0, 0].tolist(), [0, 0, 255])
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
            print("Empresa Privada", file=sys.stderr)
            print("Texto confidencial")
            return [resultado()]
        processador = Mock(predict=Mock(side_effect=prever))
        fabrica = Mock(return_value=processador)
        leitor = ocr_paddle.OCRPaddleCPU(fabrica=fabrica)
        imagem = Image.new("RGB", (100, 80), "red")
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            primeiro = leitor.reconhecer(imagem)
            segundo = leitor.reconhecer(imagem)
        fabrica.assert_called_once()
        self.assertEqual(primeiro, segundo)
        self.assertEqual(processador.predict.call_count, 2)
        self.assertEqual(saida.getvalue(), "")

    def test_nao_carrega_modelo_se_arquivo_local_ausente(self):
        with tempfile.TemporaryDirectory() as pasta, self.assertRaises(ocr_paddle.ErroOCRPaddle):
            ocr_paddle.criar_processador(Path(pasta))

    def test_arquivo_vazio_nao_carrega_backend(self):
        with tempfile.TemporaryDirectory() as pasta:
            for nome in ocr_paddle.NOMES_MODELOS:
                diretorio = Path(pasta) / nome
                diretorio.mkdir()
                for arquivo in ocr_paddle.ARQUIVOS_MODELO:
                    (diretorio / arquivo).write_bytes(b"modelo ficticio")
            (Path(pasta) / ocr_paddle.NOMES_MODELOS[0] / "inference.json").write_bytes(b"")
            modulo = types.ModuleType("paddleocr")
            modulo.PaddleOCR = Mock()
            with patch.dict(sys.modules, {"paddleocr": modulo}), self.assertRaises(ocr_paddle.ErroOCRPaddle):
                ocr_paddle.criar_processador(pasta)
            modulo.PaddleOCR.assert_not_called()

    def test_factory_cpu_dirs_flags_e_ambiente_restaurado(self):
        with tempfile.TemporaryDirectory() as pasta:
            for nome in ocr_paddle.NOMES_MODELOS:
                diretorio = Path(pasta) / nome
                diretorio.mkdir()
                for arquivo in ocr_paddle.ARQUIVOS_MODELO:
                    (diretorio / arquivo).write_bytes(b"modelo ficticio")
            modulo = types.ModuleType("paddleocr")
            modulo.PaddleOCR = Mock(return_value=object())
            with patch.dict(sys.modules, {"paddleocr": modulo}), patch.dict(os.environ, {"HF_HUB_OFFLINE": "0"}):
                ocr_paddle.criar_processador(pasta)
                self.assertEqual(os.environ["HF_HUB_OFFLINE"], "0")
            parametros = modulo.PaddleOCR.call_args.kwargs
            self.assertEqual(parametros["device"], "cpu")
            self.assertIs(parametros["enable_mkldnn"], False)
            self.assertEqual(parametros["text_detection_model_name"], ocr_paddle.NOMES_MODELOS[0])
            self.assertEqual(parametros["text_recognition_model_name"], ocr_paddle.NOMES_MODELOS[1])
            self.assertEqual(parametros["text_detection_model_dir"], str(Path(pasta) / ocr_paddle.NOMES_MODELOS[0]))
            self.assertFalse(parametros["use_doc_orientation_classify"])
            self.assertFalse(parametros["use_doc_unwarping"])
            self.assertFalse(parametros["use_textline_orientation"])
            self.assertNotIn("lang", parametros)
            self.assertNotIn("ocr_version", parametros)

    def test_resultado_multiplas_imagens_e_falha_sao_sanitizados(self):
        processador = Mock()
        processador.predict.side_effect = [[resultado(), resultado()], RuntimeError("Empresa Privada C:\\privado")]
        leitor = ocr_paddle.OCRPaddleCPU(fabrica=Mock(return_value=processador))
        for _ in range(2):
            with self.assertRaises(ocr_paddle.ErroOCRPaddle) as erro:
                leitor.reconhecer(Image.new("RGB", (100, 80)))
            self.assertNotIn("Empresa Privada", str(erro.exception))
            self.assertNotIn("privado", str(erro.exception))


if __name__ == "__main__":
    unittest.main()
