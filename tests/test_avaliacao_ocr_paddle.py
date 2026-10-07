"""Avaliação isolada de OCR, sem inferência pesada nem interface do Domínio."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from app.ocr_paddle import ErroOCRPaddle, TextoOCR


CAMINHO_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "avaliar_ocr_paddle.py"
spec = importlib.util.spec_from_file_location("_avaliacao_paddle_teste", CAMINHO_SCRIPT)
avaliacao = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = avaliacao
spec.loader.exec_module(avaliacao)


class TestAvaliacao(unittest.TestCase):
    def test_tres_leituras_por_motor_mesma_imagem_tempos_sem_texto(self):
        imagem = Image.new("RGB", (100, 100))
        textos = (TextoOCR("SPED", .9, (1, 2, 10, 10)), TextoOCR("Fiscal", .8, (12, 2, 30, 10)),
                  TextoOCR("Empresa Privada", .9, (2, 20, 99, 30)))
        paddle, tesseract = Mock(return_value=textos), Mock(return_value=textos[:1])
        valores = iter((0, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14))
        resumos = avaliacao.avaliar(imagem, "SPED Fiscal", paddle, tesseract, lambda: next(valores))
        self.assertEqual(paddle.call_count, 3)
        self.assertEqual(tesseract.call_count, 3)
        for chamada in paddle.call_args_list + tesseract.call_args_list:
            self.assertIs(chamada.args[0], imagem)
        self.assertEqual(resumos[0].segundos_inicial, 3)
        self.assertEqual(resumos[0].segundos_quentes, (1, 1))
        self.assertEqual(resumos[0].alvo_encontrado, (True, True, True))
        self.assertEqual(resumos[1].alvo_encontrado, (False, False, False))
        self.assertNotIn("Empresa Privada", repr(resumos))
        self.assertEqual(avaliacao.localizar_alvo(textos, "SPED Fiscal")[0], (1, 2, 30, 10))

    def test_help_headless_sem_paddle_e_sem_desktop(self):
        resultado = subprocess.run([sys.executable, str(CAMINHO_SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("--escolher", resultado.stdout)
        self.assertIn("--imagem", resultado.stdout)

    def test_alvo_simples_nao_inclui_vizinhos_e_repetido_nao_confirma(self):
        textos = (TextoOCR("SPED", .9, (1, 2, 10, 10)), TextoOCR("Fiscal", .8, (12, 2, 30, 10)))
        self.assertEqual(avaliacao.localizar_alvo(textos, "SPED"), ((1, 2, 10, 10),))
        repetidos = textos + (TextoOCR("SPED", .9, (1, 30, 10, 40)),)
        self.assertEqual(len(avaliacao.localizar_alvo(repetidos, "SPED")), 2)
        leitura = Mock(return_value=repetidos)
        resumos = avaliacao.avaliar(Image.new("RGB", (100, 100)), "SPED", leitura, leitura)
        self.assertEqual(resumos[0].alvo_encontrado, (False, False, False))
        self.assertEqual(resumos[0].ocorrencias_alvo, (2, 2, 2))

    def executar_cli(self, argumentos):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            codigo = avaliacao.main(argumentos)
        return codigo, saida.getvalue()

    def test_cancelamento_seletor_nao_carrega_nem_avalia(self):
        with patch.object(avaliacao, "_escolher_imagem", return_value=""), \
                patch.object(avaliacao, "_carregar_imagem") as carregar, \
                patch.object(avaliacao, "avaliar") as avaliar:
            codigo, saida = self.executar_cli(["--escolher"])
        self.assertEqual(codigo, 1)
        self.assertIn("cancelada", saida)
        carregar.assert_not_called()
        avaliar.assert_not_called()

    def test_arquivo_privado_ausente_nao_expoe_caminho(self):
        codigo, saida = self.executar_cli(["--imagem", "C:\\Privado\\Empresa Segredo.png"])
        self.assertEqual(codigo, 1)
        self.assertNotIn("Privado", saida)
        self.assertNotIn("Segredo", saida)

    def test_falha_paddle_ou_inesperada_nao_imprime_repr(self):
        for erro in (ErroOCRPaddle("Modelos locais ausentes ou incompletos."), RuntimeError("C:\\Privado Empresa Segredo")):
            with patch.object(avaliacao, "_carregar_imagem", return_value=Image.new("RGB", (10, 10))), \
                    patch.object(avaliacao, "avaliar", side_effect=erro):
                codigo, saida = self.executar_cli(["--imagem", "captura.png"])
            self.assertEqual(codigo, 1)
            self.assertNotIn("Privado", saida)
            self.assertNotIn("Segredo", saida)

    def test_resumo_so_agregados_sem_alvo_ou_texto(self):
        resumo = avaliacao.ResumoOCR("Paddle CPU", 1.2, (.2, .3), (2, 2, 2), (True, True, True))
        with patch.object(avaliacao, "_carregar_imagem", return_value=Image.new("RGB", (10, 10))), \
                patch.object(avaliacao, "avaliar", return_value=(resumo,)):
            codigo, saida = self.executar_cli(["--imagem", "Empresa Segredo.png", "--alvo", "Cliente confidencial"])
        self.assertEqual(codigo, 0)
        self.assertIn("1.200s", saida)
        self.assertIn("RAM não medida", saida)
        self.assertNotIn("Segredo", saida)
        self.assertNotIn("confidencial", saida)

    def test_tesseract_normaliza_e_recusa_contagens_invalidas(self):
        modulo = types.ModuleType("pytesseract")
        modulo.Output = types.SimpleNamespace(DICT="dict")
        modulo.image_to_data = Mock(return_value={"text": ["", "Relatórios"], "conf": [-1, "91.5"],
            "left": [0, 1], "top": [0, 2], "width": [0, 9], "height": [0, 8]})
        with patch.dict(sys.modules, {"pytesseract": modulo}), patch.object(avaliacao, "_configurar_tesseract"):
            resultado = avaliacao.reconhecer_tesseract(Image.new("RGB", (100, 100)))
            self.assertEqual(resultado[0].caixa, (1, 2, 10, 10))
            self.assertAlmostEqual(resultado[0].confianca, .915)
            modulo.image_to_data.return_value["height"] = []
            with self.assertRaises(avaliacao.ErroAvaliacao):
                avaliacao.reconhecer_tesseract(Image.new("RGB", (100, 100)))


if __name__ == "__main__":
    unittest.main()
