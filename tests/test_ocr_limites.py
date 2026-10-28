"""Esperas de OCR limitadas, sem captura nem ação de desktop."""
import threading
import time
import types
import unittest
from unittest.mock import Mock,patch

from PIL import Image
from app import tela
from app.ocr_limites import LeitorNativoLimitado,OCRTempoLimite,OCRLeituraOcupada
from app.controle_execucao import ControleExecucao,ExecucaoInterrompida,controlar_execucao


class TestOCRLimites(unittest.TestCase):
    def test_apis_windows_nao_escondem_cancelamento_como_motor_indisponivel(self):
        imagem=Image.new('RGB',(100,30))
        for ler in (lambda:tela.achar_texto_windows(imagem,'OK'),lambda:tela.ler_dados_ocr_windows(imagem)):
            with self.subTest(ler=ler),patch.object(tela,'_reconhecer_ocr_windows',side_effect=ExecucaoInterrompida('reinicio_solicitado')):
                with self.assertRaises(ExecucaoInterrompida):ler()

    def test_motor_preso_nao_cria_segunda_thread_e_nao_aceita_resultado_tardio(self):
        leitor=LeitorNativoLimitado(); liberar=threading.Event(); terminou=threading.Event()
        def ler(imagem,lang):
            liberar.wait(2); terminou.set(); return 'resultado_antigo'
        self.addCleanup(liberar.set)
        inicio=time.monotonic()
        with self.assertRaises(OCRTempoLimite):leitor.executar(ler,None,'pt',limite=.03)
        self.assertLess(time.monotonic()-inicio,.5)
        segundo=Mock()
        with self.assertRaises(OCRLeituraOcupada):leitor.executar(segundo,None,'pt',limite=.03)
        segundo.assert_not_called()
        liberar.set(); self.assertTrue(terminou.wait(.5))
        # Aguarda apenas a publicação do resultado tardio da tarefa antiga.
        self.assertTrue(leitor._atual['fim'].wait(.5))
        self.assertEqual(leitor.executar(lambda im,lang:'novo',None,'pt',limite=.5),'novo')

    def test_todas_as_leituras_usam_a_mesma_thread_de_longa_vida(self):
        # Criar/encerrar uma thread (CoInitialize/CoUninitialize) por leitura derrubou o servidor com
        # violação de acesso depois de um tempo limite; uma thread só, mesmo depois do estouro.
        leitor=LeitorNativoLimitado(); liberar=threading.Event(); nomes=[]
        self.addCleanup(liberar.set)
        def ler(imagem,lang):
            nomes.append(threading.get_ident()); liberar.wait(.2) if len(nomes)==1 else None; return 'ok'
        with self.assertRaises(OCRTempoLimite):leitor.executar(ler,None,'pt',limite=.03)
        self.assertTrue(leitor._atual['fim'].wait(1))
        self.assertEqual(leitor.executar(ler,None,'pt',limite=1),'ok')
        self.assertEqual(leitor.executar(ler,None,'pt',limite=1),'ok')
        self.assertEqual(len(set(nomes)),1)
        self.assertNotEqual(nomes[0],threading.get_ident())

    def test_cancelamento_interrompe_espera_sem_nova_leitura(self):
        leitor=LeitorNativoLimitado(); liberar=threading.Event(); controle=ControleExecucao()
        self.addCleanup(liberar.set)
        def ler(imagem,lang):
            controle.interromper('reinicio_solicitado'); liberar.wait(2)
        with controlar_execucao(controle),self.assertRaises(ExecucaoInterrompida):
            leitor.executar(ler,None,'pt',limite=.5)

    def test_respeita_limite_real_do_motor_e_converte_coordenadas(self):
        imagem=Image.new('RGB',(400,200),'white'); antes=imagem.tobytes()
        engine=types.ModuleType('winocr')
        engine.OcrEngine=types.SimpleNamespace(max_image_dimension=100)
        raw={'lines':[{'words':[{'text':'OK','bounding_rect':
             {'x':10,'y':20,'width':30,'height':10}}]}]}
        engine.recognize_pil_sync=Mock(return_value=raw)
        with patch.dict('sys.modules',{'winocr':engine}):
            pos=tela.achar_texto_windows(imagem,'OK',escala=2)
        self.assertEqual(engine.recognize_pil_sync.call_args.args[0].size,(100,50))
        self.assertEqual(pos,(100,100))
        self.assertEqual(imagem.tobytes(),antes)
        self.assertEqual(raw['lines'][0]['words'][0]['bounding_rect']['x'],10)

    def test_tesseract_tem_timeout_na_leitura_de_data_e_rotulo(self):
        imagem=Image.new('RGB',(100,30))
        with patch.object(tela.pytesseract,'image_to_data',return_value={}) as motor:
            tela.ler_dados_ocr_linha_data(imagem)
            tela.ler_dados_ocr_linha_rotulo(imagem)
        self.assertTrue(all(c.kwargs['timeout']==8 for c in motor.call_args_list))


if __name__=='__main__':unittest.main()
