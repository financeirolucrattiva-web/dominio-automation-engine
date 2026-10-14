"""Limite cooperativo para OCR nativo, sem ações sobre a sessão Windows.

No máximo uma leitura nativa pode permanecer em andamento. Uma leitura
atrasada só examina a imagem recebida, nunca captura ou interage com a tela.
"""
import ctypes
import sys
import threading
import time

from .controle_execucao import ponto_seguro


class OCRTempoLimite(RuntimeError):
    pass


class OCRLeituraOcupada(RuntimeError):
    pass


class LeitorNativoLimitado:
    def __init__(self):
        self._trava=threading.Lock()
        self._atual=None

    def executar(self,funcao,imagem,lang,limite=4.0):
        ponto_seguro()
        with self._trava:
            if self._atual is not None and not self._atual['fim'].is_set():
                raise OCRLeituraOcupada('OCR nativo ainda ocupado; nenhuma nova leitura iniciada.')
            tarefa={'fim':threading.Event(),'resultado':None,'erro':None}
            self._atual=tarefa
        def ler():
            com_iniciado=False
            try:
                if sys.platform=='win32' and hasattr(ctypes,'windll'):
                    # Worker novo/MTA para awaitables WinRT; não é automação UI.
                    hr=ctypes.windll.ole32.CoInitializeEx(None,0)
                    com_iniciado=hr in (0,1)
                tarefa['resultado']=funcao(imagem,lang=lang)
            except BaseException as erro:
                tarefa['erro']=erro
            finally:
                try:
                    if com_iniciado:ctypes.windll.ole32.CoUninitialize()
                except BaseException as erro:
                    if tarefa['erro'] is None:tarefa['erro']=erro
                finally:
                    tarefa['fim'].set()
        threading.Thread(target=ler,name='ocr_nativo_local',daemon=True).start()
        fim=time.monotonic()+limite
        while True:
            ponto_seguro()
            restante=fim-time.monotonic()
            if restante<=0:
                raise OCRTempoLimite('OCR nativo excedeu seu limite; leitura tardia será descartada.')
            if tarefa['fim'].wait(min(.05,restante)):break
        ponto_seguro()
        if tarefa['erro'] is not None:raise tarefa['erro']
        return tarefa['resultado']


LEITOR_WINDOWS=LeitorNativoLimitado()
