"""Regressão de buscas/estados com OCR reutilizado somente por captura."""

import contextlib
import io
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock, patch

from PIL import Image

with patch("ctypes.windll", Mock(), create=True):
    from app import tela, estados


def dados(texto="Final da exportação."):
    return {"text": [texto], "left": [10], "top": [20], "width": [30], "height": [10]}


class TestReusoOCR(unittest.TestCase):
    def test_mesmos_pixels_copia_e_alvos_diferentes_usam_uma_leitura(self):
        imagem = Image.new("RGB", (100, 100), "white")
        with patch.object(tela.pytesseract, "image_to_data", return_value=dados()) as ocr:
            with tela.reutilizar_ocr():
                self.assertEqual(tela.achar_texto(imagem, "Final"), (25, 25))
                self.assertIsNone(tela.achar_texto(imagem.copy(), "Erro"))
                self.assertEqual(tela.achar_texto(imagem, "exportação"), (25, 25))
            self.assertEqual(ocr.call_count, 1)
            tela.achar_texto(imagem, "Final")
            self.assertEqual(ocr.call_count, 2)

    def test_pixels_escala_e_recorte_diferentes_exigem_nova_leitura(self):
        imagem = Image.new("RGB", (100, 100), "white")
        with patch.object(tela.pytesseract, "image_to_data", return_value=dados()) as ocr:
            with tela.reutilizar_ocr():
                tela.achar_texto(imagem, "Final")
                imagem.putpixel((0, 0), (0, 0, 0))
                tela.achar_texto(imagem, "Final")
                tela.achar_texto(imagem, "Final", escala=2)
                tela.achar_texto(imagem.crop((0, 0, 50, 50)), "Final")
            self.assertEqual(ocr.call_count, 4)

    def test_excecao_encerra_cache_e_leitura_posterior_e_nova(self):
        imagem = Image.new("RGB", (100, 100))
        with patch.object(tela.pytesseract, "image_to_data", side_effect=[dados(), RuntimeError("falha"), dados()]) as ocr:
            with self.assertRaises(RuntimeError), tela.reutilizar_ocr():
                tela.achar_texto(imagem, "Final")
                tela.achar_texto(imagem, "Final", escala=2)
            tela.achar_texto(imagem, "Final")
            self.assertEqual(ocr.call_count, 3)

    def test_paletas_distintas_nao_compartilham_leitura_por_indices_iguais(self):
        primeira = Image.new("P", (100, 100))
        segunda = primeira.copy()
        primeira.putpalette([0, 0, 0] * 256)
        segunda.putpalette([255, 255, 255] * 256)
        with patch.object(tela.pytesseract, "image_to_data", return_value=dados()) as ocr:
            with tela.reutilizar_ocr():
                tela.achar_texto(primeira, "Final")
                tela.achar_texto(segunda, "Final")
        self.assertEqual(ocr.call_count, 2)

    def test_leitura_nao_e_compartilhada_com_outra_thread(self):
        imagem = Image.new("RGB", (100, 100))
        with patch.object(tela.pytesseract, "image_to_data", return_value=dados()) as ocr:
            with tela.reutilizar_ocr():
                tela.achar_texto(imagem, "Final")
                with ThreadPoolExecutor(max_workers=1) as executor:
                    self.assertEqual(executor.submit(tela.achar_texto, imagem, "Final").result(), (25, 25))
                tela.achar_texto(imagem, "Final")
            self.assertEqual(ocr.call_count, 2)


class TestEsperaComReuso(unittest.TestCase):
    def executar(self, imagens, detectores, resultados):
        contexto = contextlib.ExitStack()
        with contexto:
            contexto.enter_context(contextlib.redirect_stdout(io.StringIO()))
            contexto.enter_context(patch.object(estados.time, "sleep"))
            contexto.enter_context(patch.object(tela, "capturar_tela", side_effect=imagens))
            contexto.enter_context(patch.object(tela, "tela_mudou", return_value=True))
            ocr = contexto.enter_context(patch.object(tela.pytesseract, "image_to_data", side_effect=resultados))
            retorno = estados.esperar_por_estado(detectores, espera_minima=0, tentativas=len(imagens), intervalo=0)
            return retorno, ocr.call_count

    def test_varios_titulos_usam_so_tela_e_centro_sem_mudar_erro(self):
        imagem = Image.new("RGB", (100, 100))
        detectores = [("sucesso", lambda img: tela.achar_texto_ou_no_centro(img, "Final"))]
        for texto in ("Informação", "Aviso", "Erro"):
            detectores.append(("erro", lambda img, texto=texto: tela.achar_texto_ou_no_centro(img, texto)))
        retorno, chamadas = self.executar([imagem], detectores, [dados("Nada esperado"), dados("Erro")])
        self.assertEqual(retorno[1:], ("erro", (45, 45)))
        self.assertEqual(chamadas, 2)

    def test_primeiro_detector_mantem_precedencia_quando_ambos_estao_visiveis(self):
        imagem = Image.new("RGB", (100, 100))
        detectores = [("sucesso", lambda img: tela.achar_texto(img, "Final")),
                      ("erro", lambda img: tela.achar_texto(img, "Erro"))]
        retorno, chamadas = self.executar([imagem], detectores, [dados("Final Erro")])
        self.assertEqual(retorno[1:], ("sucesso", (25, 25)))
        self.assertEqual(chamadas, 1)

    def test_nova_tentativa_nao_reaproveita_texto_anterior_mesmo_com_pixels_iguais(self):
        imagem = Image.new("RGB", (100, 100))
        detectores = [("sucesso", lambda img: tela.achar_texto(img, "Final"))]
        retorno, chamadas = self.executar([imagem, imagem.copy()], detectores, [dados("Processando"), dados()])
        self.assertEqual(retorno[1:], ("sucesso", (25, 25)))
        self.assertEqual(chamadas, 2)

    def test_esgotamento_mantem_retorno_sem_estado(self):
        imagem = Image.new("RGB", (100, 100))
        detectores = [("sucesso", lambda img: tela.achar_texto(img, "Final")),
                      ("erro", lambda img: tela.achar_texto(img, "Erro"))]
        retorno, chamadas = self.executar([imagem], detectores, [dados("Processando")])
        self.assertEqual(retorno, (None, None, None))
        self.assertEqual(chamadas, 1)


if __name__ == "__main__":
    unittest.main()
