"""Estado do login e entrega única do código humano; sem navegador/desktop."""

from dataclasses import dataclass, field
import threading
import time
import uuid


class LoginRecusado(RuntimeError):
    pass


@dataclass(repr=False)
class CredenciaisLogin:
    email: str
    senha_onvio: str = field(repr=False)
    usuario_dominio: str
    senha_dominio: str = field(repr=False)

    def limpar(self):
        self.email = self.senha_onvio = self.usuario_dominio = self.senha_dominio = ""


class SessaoLogin:
    def __init__(self):
        self._condicao = threading.Condition()
        self._estado = "nao_iniciado"
        self._etapa = "nao_iniciado"
        self._motivo = None
        self._solicitacao = None
        self._codigo = None
        self._cancelado = False
        self._limite = None

    def publico(self):
        with self._condicao:
            return {"estado": self._estado, "etapa": self._etapa, "motivo": self._motivo,
                    "solicitacao_id": self._solicitacao,
                    "segundos_restantes": max(0, int(self._limite - time.monotonic())) if self._limite else None}

    def iniciar(self):
        with self._condicao:
            self._cancelado = False
            self._codigo = self._solicitacao = self._limite = self._motivo = None
            self._estado = "na_fila"
            self._etapa = "na_fila"

    def verificar(self):
        with self._condicao:
            if self._cancelado:
                raise LoginRecusado("login_cancelado")

    def fase(self, nome, motivo=None):
        with self._condicao:
            if self._cancelado and nome not in ("cancelado", "falha"):
                raise LoginRecusado("login_cancelado")
            self._estado, self._motivo = nome, motivo
            if nome not in ("falha", "cancelado"):
                self._etapa = nome

    def cancelar(self):
        with self._condicao:
            self._cancelado = True
            self._codigo = None
            self._solicitacao = self._limite = None
            self._estado, self._motivo = "cancelado", "login_cancelado"
            self._condicao.notify_all()

    def aguardar_codigo(self, timeout=300):
        with self._condicao:
            if self._cancelado:
                raise LoginRecusado("login_cancelado")
            self._estado = "aguardando_codigo"
            self._etapa = "aguardando_codigo"
            self._solicitacao = uuid.uuid4().hex
            self._limite = time.monotonic() + timeout
            self._codigo = None
            try:
                while self._codigo is None:
                    if self._cancelado:
                        raise LoginRecusado("login_cancelado")
                    restante = self._limite - time.monotonic()
                    if restante <= 0:
                        raise LoginRecusado("codigo_expirado")
                    self._condicao.wait(restante)
                self._estado = "verificando_codigo"
                self._etapa = "verificando_codigo"
                return self._codigo
            finally:
                self._codigo = self._solicitacao = self._limite = None

    def fornecer_codigo(self, solicitacao, codigo):
        with self._condicao:
            if (self._cancelado or self._estado != "aguardando_codigo" or not self._solicitacao
                    or solicitacao != self._solicitacao or self._codigo is not None
                    or self._limite <= time.monotonic()):
                raise LoginRecusado("solicitacao_codigo_inativa")
            self._codigo = codigo
            self._condicao.notify_all()
