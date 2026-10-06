"""OCR local sobre imagem sintética; nenhum print ou dado de cliente."""

import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont

with patch("ctypes.windll", Mock(), create=True):
    from app import tela


class TestEmpresaTela(unittest.TestCase):
    def test_cabecalho_sintetico_ocr_local(self):
        imagem = Image.new("RGB", (1439, 899), "#12345a")
        desenho = ImageDraw.Draw(imagem)
        fonte = None
        for nome_fonte in ("DejaVuSans.ttf", "arial.ttf"):
            try:
                fonte = ImageFont.truetype(nome_fonte, 18)
                break
            except OSError:
                continue
        if fonte is None:
            self.skipTest("Fonte TrueType não disponível para a imagem sintética.")
        desenho.text((1030, 50), "GERENTE", font=fonte, fill="white")
        desenho.text((1030, 80), "EMPRESA FICTICIA - 52", font=fonte, fill="white")
        desenho.text((1030, 110), "SET/2026", font=fonte, fill="white")
        self.assertEqual(tela.ler_empresa_selecionada(imagem), ("EMPRESA FICTICIA", "52"))

    def test_ocr_discordante_falha_segura(self):
        imagem = Image.new("RGB", (1439, 899))
        with patch.object(tela.pytesseract, "image_to_string", side_effect=["EMPRESA A - 1", "EMPRESA B - 2"]):
            self.assertIsNone(tela.ler_empresa_selecionada(imagem))

    def test_recorte_inclui_cabecalho_em_janela_menor(self):
        imagem = Image.new("RGB", (1000, 600))
        with patch.object(tela.pytesseract, "image_to_string", return_value="EMPRESA A - 1") as ocr:
            self.assertEqual(tela.ler_empresa_selecionada(imagem), ("EMPRESA A", "1"))
            self.assertEqual(ocr.call_args.args[0].size, (1500, 420))


if __name__ == "__main__":
    unittest.main()
