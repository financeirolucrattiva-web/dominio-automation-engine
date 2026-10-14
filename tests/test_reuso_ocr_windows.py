"""OCR Windows só é reutilizado dentro da mesma análise de pixels."""
from concurrent.futures import ThreadPoolExecutor
import types
import unittest
from unittest.mock import Mock,patch
from PIL import Image
from app import tela


def resultado():
    return {'lines':[{'words':[{'text':'Final','bounding_rect':
        {'x':10,'y':20,'width':30,'height':10}}]}]}


class TestReusoWindows(unittest.TestCase):
    def setUp(self):
        self.engine=types.ModuleType('winocr')
        self.engine.recognize_pil_sync=Mock(side_effect=lambda im,lang:resultado())
        self.patch=patch.dict('sys.modules',{'winocr':self.engine})
        self.patch.start(); self.addCleanup(self.patch.stop)

    def test_alvos_e_dados_compartilham_uma_leitura_so_na_captura(self):
        imagem=Image.new('RGB',(100,100),'white')
        with tela.reutilizar_ocr():
            self.assertEqual(tela.achar_texto_windows(imagem,'Final',escala=2),(12,12))
            self.assertEqual(tela.ler_dados_ocr_windows(imagem.copy(),2)['text'],['Final'])
            self.assertIsNone(tela.achar_texto_windows(imagem,'Erro',escala=2))
        self.assertEqual(self.engine.recognize_pil_sync.call_count,1)
        tela.ler_dados_ocr_windows(imagem,2)
        self.assertEqual(self.engine.recognize_pil_sync.call_count,2)

    def test_pixels_escala_idioma_e_preparo_distintos_nao_reusam(self):
        imagem=Image.new('RGB',(100,100),'white')
        with tela.reutilizar_ocr():
            tela.achar_texto_windows(imagem,'Final')
            tela.ler_dados_ocr_windows(imagem,1)
            tela.achar_texto_windows(imagem,'Final',escala=2)
            tela.achar_texto_windows(imagem,'Final',escala=2,lang='en')
            imagem.putpixel((1,1),(0,0,0))
            tela.achar_texto_windows(imagem,'Final',escala=2)
        self.assertEqual(self.engine.recognize_pil_sync.call_count,5)
        self.assertEqual([c.args[0].mode for c in self.engine.recognize_pil_sync.call_args_list[:2]],['RGB','L'])

    def test_paletas_e_threads_nao_compartilham_resultados(self):
        primeira=Image.new('P',(100,100)); segunda=primeira.copy()
        primeira.putpalette([0,0,0]*256); segunda.putpalette([255,255,255]*256)
        with tela.reutilizar_ocr():
            tela.ler_dados_ocr_windows(primeira,2)
            tela.ler_dados_ocr_windows(segunda,2)
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(tela.ler_dados_ocr_windows,primeira,2).result()
            tela.ler_dados_ocr_windows(primeira,2)
        self.assertEqual(self.engine.recognize_pil_sync.call_count,3)

    def test_excecao_nao_e_cacheada_e_recuperacao_relê(self):
        self.engine.recognize_pil_sync.side_effect=[RuntimeError('falha'),resultado()]
        imagem=Image.new('RGB',(100,100))
        with tela.reutilizar_ocr():
            self.assertIsNone(tela.ler_dados_ocr_windows(imagem,2))
            self.assertEqual(tela.ler_dados_ocr_windows(imagem,2)['text'],['Final'])
        self.assertEqual(self.engine.recognize_pil_sync.call_count,2)

    def test_namespace_windows_nao_reusa_dicionario_tesseract(self):
        imagem=Image.new('RGB',(100,100))
        dados={'text':['Tesseract'],'left':[10],'top':[20],'width':[30],'height':[10]}
        with patch.object(tela.pytesseract,'image_to_data',return_value=dados) as engine_tess:
            with tela.reutilizar_ocr():
                self.assertIsNotNone(tela.achar_texto(imagem,'Tesseract',escala=2))
                self.assertEqual(tela.ler_dados_ocr_windows(imagem,2)['text'],['Final'])
                tela.achar_texto(imagem,'Tesseract',escala=2)
        engine_tess.assert_called_once(); self.engine.recognize_pil_sync.assert_called_once()


if __name__=='__main__':unittest.main()
