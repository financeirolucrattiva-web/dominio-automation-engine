"""Tarefas individuais persistidas; independente de HTTP e do desktop."""

import datetime as dt
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import re
import sqlite3
import threading
import uuid

from app import capacidades, painel
from app.trava_execucao import TravaExecucao


class SessaoOcupada(ValueError):
    pass


class PrecondicaoRecusada(ValueError):
    pass


def periodo_anterior(hoje=None):
    hoje = hoje or dt.date.today()
    fim = hoje.replace(day=1) - dt.timedelta(days=1)
    return fim.replace(day=1).isoformat(), fim.isoformat()


def validar_pedido(pedido, hoje=None):
    """Não aceita caminhos, código, ações livres ou competência corrente."""
    hoje = hoje or dt.date.today()
    chaves = {"request_id", "capacidade", "empresa_codigo", "inicio", "fim", "apuracao_confirmada"}
    if not isinstance(pedido, dict) or set(pedido) != chaves:
        raise ValueError("Campos da tarefa inválidos.")
    try:
        if str(uuid.UUID(pedido["request_id"])) != pedido["request_id"]:
            raise ValueError
        capacidades.obter_capacidade(pedido["capacidade"])
        if not isinstance(pedido["empresa_codigo"], str) or not re.fullmatch(r"[0-9]{1,12}", pedido["empresa_codigo"]):
            raise ValueError
        if pedido["apuracao_confirmada"] is not True:
            raise ValueError
        for chave in ("inicio", "fim"):
            if not isinstance(pedido[chave], str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", pedido[chave]):
                raise ValueError
        inicio, fim = (dt.date.fromisoformat(pedido[chave]) for chave in ("inicio", "fim"))
        if inicio > fim or fim >= hoje.replace(day=1):
            raise ValueError
        if pedido["capacidade"] in ("sped_fiscal", "efd_contribuicoes"):
            if (pedido["inicio"], pedido["fim"]) != periodo_anterior(hoje):
                raise ValueError
    except (ValueError, TypeError, AttributeError, KeyError):
        raise ValueError("Confira função, empresa, período passado e confirmação da apuração.") from None
    return dict(pedido)


def _agora():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class RepositorioTarefas:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as banco:
            banco.executescript("""
                CREATE TABLE IF NOT EXISTS tarefas (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    pedido TEXT NOT NULL, status TEXT NOT NULL, modo TEXT NOT NULL,
                    resultado INTEGER, arquivo TEXT, motivo TEXT,
                    criado TEXT NOT NULL, atualizado TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS eventos (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, tarefa_id TEXT NOT NULL,
                    evento TEXT NOT NULL
                );
            """)

    @contextmanager
    def conectar(self):
        banco = sqlite3.connect(self.caminho, timeout=10)
        banco.row_factory = sqlite3.Row
        try:
            with banco:
                yield banco
        finally:
            banco.close()

    def criar(self, pedido, modo="consulta"):
        dados = json.dumps(pedido, sort_keys=True)
        with self.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            anterior = banco.execute("SELECT * FROM tarefas WHERE request_id=?", (pedido["request_id"],)).fetchone()
            if anterior:
                if anterior["pedido"] != dados:
                    raise SessaoOcupada("Identificador já usado por outra tarefa.")
                return self._publica(anterior), False
            if banco.execute("SELECT 1 FROM tarefas WHERE status IN ('pendente','executando')").fetchone():
                raise SessaoOcupada("Já existe uma execução na sessão; aguarde terminar.")
            identificador, agora = uuid.uuid4().hex, _agora()
            banco.execute("INSERT INTO tarefas VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (identificador, pedido["request_id"], dados, "pendente", modo, None, None, None, agora, agora))
        return self.obter(identificador), True

    def obter(self, identificador, privado=False):
        with self.conectar() as banco:
            item = banco.execute("SELECT * FROM tarefas WHERE id=?", (identificador,)).fetchone()
        if item is None:
            return None
        return dict(item) if privado else self._publica(item)

    @staticmethod
    def _publica(item):
        pedido = json.loads(item["pedido"])
        return {"id": item["id"], "pedido": pedido, "status": item["status"], "modo": item["modo"],
                "resultado": None if item["resultado"] is None else bool(item["resultado"]),
                "arquivo_disponivel": bool(item["arquivo"]), "motivo": item["motivo"],
                "criado": item["criado"], "atualizado": item["atualizado"]}

    def listar(self):
        with self.conectar() as banco:
            return [self._publica(item) for item in banco.execute("SELECT * FROM tarefas ORDER BY rowid DESC LIMIT 100")]

    def retomar(self):
        # Nunca repete uma ação fiscal automaticamente após reiniciar.
        with self.conectar() as banco:
            banco.execute("UPDATE tarefas SET status='interrompida', resultado=NULL, motivo='servidor_reiniciado', atualizado=? WHERE status IN ('pendente','executando')", (_agora(),))

    def proxima(self):
        with self.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            item = banco.execute("SELECT * FROM tarefas WHERE status='pendente' ORDER BY rowid LIMIT 1").fetchone()
            if item:
                banco.execute("UPDATE tarefas SET status='executando', atualizado=? WHERE id=?", (_agora(), item["id"]))
                return dict(item)
        return None

    def concluir(self, identificador, status, resultado=None, arquivo=None, motivo=None):
        with self.conectar() as banco:
            banco.execute("UPDATE tarefas SET status=?, resultado=?, arquivo=?, motivo=?, atualizado=? WHERE id=?",
                          (status, resultado, str(arquivo) if arquivo else None, motivo, _agora(), identificador))

    def registrar_evento(self, identificador, evento):
        modelo = painel.EstadoPainel()
        if not modelo.receber(evento):
            return
        # Evidência OCR livre nunca atravessa a API. Marcadores são locais.
        dados = {k: evento[k] for k in ("execution_id", "routine_id", "attempt", "step", "status", "elapsed_seconds")}
        dados["evidence"] = "tela_principal_reconhecida" if evento.get("evidence") == "tela_principal_reconhecida" else None
        with self.conectar() as banco:
            banco.execute("INSERT INTO eventos (tarefa_id, evento) VALUES (?,?)", (identificador, json.dumps(dados)))

    def eventos(self, identificador):
        with self.conectar() as banco:
            return [json.loads(item["evento"]) for item in banco.execute("SELECT evento FROM eventos WHERE tarefa_id=? ORDER BY seq", (identificador,))]


class ServicoExecucao:
    """Um único worker; novas tarefas são recusadas enquanto a sessão ocupa."""

    def __init__(self, repositorio, executor=None, modo="consulta"):
        self.repositorio, self.executor, self.modo = repositorio, executor, modo
        self._acordar = threading.Event()
        self._parar = threading.Event()
        self._worker = None
        self._trava = TravaExecucao(repositorio.caminho.parent / ("sessao_executor.lock" if modo == "windows" else "executor_simulado.lock"))

    @property
    def disponivel(self):
        return self.executor is not None and self._worker is not None and self._worker.is_alive() and not self._parar.is_set()

    def iniciar(self):
        if self._worker is not None:
            raise RuntimeError("Serviço já iniciado.")
        if self.executor is not None:
            self._trava.adquirir()
            try:
                self.repositorio.retomar()
                self._worker = threading.Thread(target=self._trabalhar, name="executor-dominio", daemon=False)
                self._worker.start()
            except Exception:
                self._trava.liberar()
                raise

    def encerrar(self):
        self._parar.set()
        self._acordar.set()
        if self._worker is not None:
            self._worker.join()  # termina a ação atual; não mata o mouse/teclado no meio
        self._trava.liberar()

    def solicitar(self, pedido):
        if not self.disponivel:
            raise PrecondicaoRecusada("executor_indisponivel")
        pedido = validar_pedido(pedido)
        tarefa, nova = self.repositorio.criar(pedido, self.modo)
        if nova:
            self._acordar.set()
        return tarefa

    def _trabalhar(self):
        try:
            self._executar_pendentes()
        except Exception:
            # Persistência indisponível: impede novas ações e pede retomada
            # manual, sem repetir uma geração cujo resultado se perdeu.
            self._parar.set()
            logging.getLogger(__name__).exception("Executor interrompido por falha de persistência.")

    def _executar_pendentes(self):
        while not self._parar.is_set():
            self._acordar.wait(timeout=1)
            self._acordar.clear()
            if self._parar.is_set():
                break
            tarefa = self.repositorio.proxima()
            if tarefa is None:
                continue
            identificador = tarefa["id"]
            try:
                pedido = validar_pedido(json.loads(tarefa["pedido"]))
                resultado = self.executor(pedido, lambda ev: self.repositorio.registrar_evento(identificador, ev))
                arquivo = None
                if isinstance(resultado, tuple) and len(resultado) == 2 and type(resultado[0]) is bool:
                    resultado, arquivo = resultado
                elif type(resultado) is not bool:
                    resultado = None
                modelo = painel.EstadoPainel()
                for evento in self.repositorio.eventos(identificador):
                    modelo.receber(evento)
                retorno = modelo.retorno == "Tela principal confirmada"
                concluido = modelo.linhas.get("fim", (None, None, None))[2] == "concluido"
                status = "falha" if resultado is False else "concluida" if resultado is True and retorno and concluido else "nao_confirmada"
                self.repositorio.concluir(identificador, status, resultado, arquivo,
                                         None if status != "nao_confirmada" else "resultado_ou_retorno_nao_confirmado")
            except PrecondicaoRecusada as erro:
                motivos = {"executor_requer_windows", "calibracao_indisponivel", "dominio_fora_de_foco",
                           "tela_principal_nao_confirmada", "empresa_nao_confirmada", "periodo_nao_confirmado"}
                motivo = str(erro) if str(erro) in motivos else "precondicao_nao_confirmada"
                self.repositorio.concluir(identificador, "recusada", False, motivo=motivo)
            except Exception:
                # Sem exceções/capturas/caminhos privados na resposta remota.
                logging.getLogger(__name__).exception("Falha na tarefa %s", identificador)
                self.repositorio.concluir(identificador, "falha", False, motivo="erro_execucao_consulte_servidor")
