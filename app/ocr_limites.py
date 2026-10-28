"""Limite cooperativo para OCR nativo, sem ações sobre a sessão Windows.

No máximo uma leitura nativa pode permanecer em andamento. Uma leitura
atrasada só examina a imagem recebida, nunca captura ou interage com a tela.

As leituras rodam numa ÚNICA thread de longa vida (COM inicializado uma vez, nunca desfeito). Antes, cada
leitura criava e encerrava uma thread com CoInitialize/CoUninitialize; quando uma leitura estourava o limite
e a thread era abandonada, o encerramento dela derrubou o servidor duas vezes com violação de acesso
(código -1073741819), logo depois de "OCR_WINDOWS tempo_limite", no meio de um lote real (28/10/2026).
"""
import ctypes
import queue
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
        self._fila=queue.Queue()
        self._worker=None

    def _garantir_worker(self):
        # Chamado com a trava tomada.
        if self._worker is None or not self._worker.is_alive():
            self._worker=threading.Thread(target=self._laco,name='ocr_nativo_local',daemon=True)
            self._worker.start()

    def _laco(self):
        if sys.platform=='win32' and hasattr(ctypes,'windll'):
            try:
                # Worker MTA para awaitables WinRT; não é automação UI. Nunca há CoUninitialize: a thread
                # vive até o fim do processo, sem derrubar objetos WinRT ainda em uso.
                ctypes.windll.ole32.CoInitializeEx(None,0)
            except BaseException:
                pass
        while True:
            tarefa,funcao,imagem,lang=self._fila.get()
            try:
                tarefa['resultado']=funcao(imagem,lang=lang)
            except BaseException as erro:
                tarefa['erro']=erro
            finally:
                tarefa['fim'].set()

    def executar(self,funcao,imagem,lang,limite=4.0):
        ponto_seguro()
        with self._trava:
            if self._atual is not None and not self._atual['fim'].is_set():
                raise OCRLeituraOcupada('OCR nativo ainda ocupado; nenhuma nova leitura iniciada.')
            tarefa={'fim':threading.Event(),'resultado':None,'erro':None}
            self._atual=tarefa
            self._garantir_worker()
            self._fila.put((tarefa,funcao,imagem,lang))
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
