"""Pausa cooperativa por execução, sem importar ou operar o desktop."""

from contextlib import contextmanager
from contextvars import ContextVar
import threading

_ATUAL = ContextVar("controle_da_execucao", default=None)
_VERIFICAR_ACAO = ContextVar("verificacao_antes_da_acao", default=None)


class ExecucaoInterrompida(RuntimeError):
    pass


class ControleExecucao:
    def __init__(self):
        self._condicao = threading.Condition()
        self._solicitada = False
        self._pausada = False
        self._interromper = False
        self._motivo = "servidor_encerrado_durante_pausa"
        self._preparar_retomada = None

    @property
    def estado(self):
        with self._condicao:
            return "pausada" if self._pausada else "pausa_solicitada" if self._solicitada else "executando"

    def pausar(self):
        with self._condicao:
            self._solicitada = True
            self._condicao.notify_all()

    def continuar(self):
        with self._condicao:
            self._solicitada = False
            self._condicao.notify_all()

    def encerrar(self):
        # Encerrar o servidor não retoma uma execução pausada sozinho.
        # Uma ação normal em andamento continua até terminar, como antes.
        with self._condicao:
            if self._solicitada or self._pausada:
                self._interromper = True
            self._condicao.notify_all()

    def interromper(self, motivo="reinicio_solicitado"):
        with self._condicao:
            self._interromper = True
            self._motivo = motivo
            self._condicao.notify_all()

    def ponto_seguro(self):
        with self._condicao:
            if self._interromper:
                raise ExecucaoInterrompida(self._motivo)
            if not self._solicitada:
                return
        verificar = self._preparar_retomada() if self._preparar_retomada else None
        with self._condicao:
            if not self._solicitada and not self._interromper:
                return
            self._pausada = True
            try:
                while self._solicitada and not self._interromper:
                    self._condicao.wait()
                if self._interromper:
                    raise ExecucaoInterrompida(self._motivo)
            finally:
                self._pausada = False
        if verificar is not None and not verificar():
            with self._condicao:
                self._interromper = True
                self._motivo = "retomada_nao_confirmada"
            raise ExecucaoInterrompida("retomada_nao_confirmada")

    def verificar_interrupcao(self):
        with self._condicao:
            if self._interromper:
                raise ExecucaoInterrompida(self._motivo)


@contextmanager
def controlar_execucao(controle):
    token = _ATUAL.set(controle)
    try:
        yield
    finally:
        _ATUAL.reset(token)


@contextmanager
def verificar_retomada(preparar):
    controle = _ATUAL.get()
    if controle is None:
        yield
        return
    anterior = controle._preparar_retomada
    controle._preparar_retomada = preparar
    try:
        yield
    finally:
        controle._preparar_retomada = anterior


@contextmanager
def verificar_antes_de_agir(verificar):
    """Verificação da sessão em cada checkpoint de mouse/teclado."""
    token = _VERIFICAR_ACAO.set(verificar)
    try:
        yield
    finally:
        _VERIFICAR_ACAO.reset(token)


def ponto_seguro():
    controle = _ATUAL.get()
    if controle is not None:
        controle.ponto_seguro()
    verificar = _VERIFICAR_ACAO.get()
    if verificar is not None:
        verificar()
