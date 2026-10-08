"""Tarefas e lotes persistidos; independente de HTTP e do desktop."""

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
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao
from app.autenticacao import SessaoLogin, LoginRecusado
from app.configuracao_lotes import ConfiguracaoLotes


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
            proximo_mes = (inicio.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
            if inicio.day != 1 or fim != proximo_mes - dt.timedelta(days=1):
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
                CREATE TABLE IF NOT EXISTS lotes (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    pedido TEXT NOT NULL, plano TEXT NOT NULL, status TEXT NOT NULL,
                    motivo TEXT, criado TEXT NOT NULL, atualizado TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS itens_lote (
                    lote_id TEXT NOT NULL, posicao INTEGER NOT NULL,
                    tarefa_id TEXT UNIQUE NOT NULL, PRIMARY KEY(lote_id, posicao)
                );
            """)
        self.configuracao = ConfiguracaoLotes(self)

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

    def tem_pendentes(self):
        with self.conectar() as banco:
            return banco.execute("SELECT 1 FROM tarefas WHERE status IN ('pendente','executando') LIMIT 1").fetchone() is not None

    def retomar(self):
        # Nunca repete uma ação fiscal automaticamente após reiniciar.
        with self.conectar() as banco:
            banco.execute("UPDATE tarefas SET status='interrompida', resultado=NULL, motivo='servidor_reiniciado', atualizado=? WHERE status IN ('pendente','executando')", (_agora(),))
            banco.execute("UPDATE lotes SET status='interrompida', motivo='servidor_reiniciado', atualizado=? WHERE status IN ('pendente','executando')", (_agora(),))

    def proxima(self):
        with self.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            item = banco.execute("SELECT t.*, i.lote_id FROM tarefas t LEFT JOIN itens_lote i ON i.tarefa_id=t.id WHERE t.status='pendente' ORDER BY t.rowid LIMIT 1").fetchone()
            if item:
                banco.execute("UPDATE tarefas SET status='executando', atualizado=? WHERE id=?", (_agora(), item["id"]))
                if item["lote_id"]:
                    banco.execute("UPDATE lotes SET status='executando', atualizado=? WHERE id=?", (_agora(), item["lote_id"]))
                return dict(item)
        return None

    def interromper_pendentes(self):
        with self.conectar() as banco:
            banco.execute("UPDATE tarefas SET status='interrompida', resultado=NULL, motivo='reinicio_solicitado', atualizado=? WHERE status='pendente'", (_agora(),))
            banco.execute("UPDATE lotes SET status='interrompida', motivo='reinicio_solicitado', atualizado=? WHERE status IN ('pendente','executando')", (_agora(),))

    def concluir(self, identificador, status, resultado=None, arquivo=None, motivo=None):
        with self.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            banco.execute("UPDATE tarefas SET status=?, resultado=?, arquivo=?, motivo=?, atualizado=? WHERE id=?",
                          (status, resultado, str(arquivo) if arquivo else None, motivo, _agora(), identificador))
            item = banco.execute("SELECT lote_id FROM itens_lote WHERE tarefa_id=?", (identificador,)).fetchone()
            if item:
                lote = banco.execute("SELECT status FROM lotes WHERE id=?", (item["lote_id"],)).fetchone()
                if status != "concluida":
                    banco.execute("UPDATE tarefas SET status='interrompida', motivo='lote_interrompido', atualizado=? WHERE status='pendente' AND id IN (SELECT tarefa_id FROM itens_lote WHERE lote_id=?)", (_agora(), item["lote_id"]))
                    banco.execute("UPDATE lotes SET status='interrompida', motivo=COALESCE(motivo, 'rotina_nao_concluida'), atualizado=? WHERE id=?", (_agora(), item["lote_id"]))
                elif lote["status"] != "interrompida":
                    pendente = banco.execute("SELECT 1 FROM tarefas t JOIN itens_lote i ON i.tarefa_id=t.id WHERE i.lote_id=? AND t.status IN ('pendente','executando')", (item["lote_id"],)).fetchone()
                    banco.execute("UPDATE lotes SET status=?, atualizado=? WHERE id=?", ("executando" if pendente else "concluida", _agora(), item["lote_id"]))

    def criar_lote(self, pedido, modo):
        campos = {"request_id", "empresas", "inicio", "fim", "apuracao_confirmada", "plano_hash"}
        if not isinstance(pedido, dict) or set(pedido) != campos or pedido["apuracao_confirmada"] is not True:
            raise ValueError("Confira empresas, período e apuração de todas as empresas do lote.")
        try:
            if str(uuid.UUID(pedido["request_id"])) != pedido["request_id"] or not re.fullmatch(r"[0-9a-f]{64}", pedido["plano_hash"]):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Revise o plano antes de iniciar o lote.") from None
        dados = json.dumps(pedido, sort_keys=True)
        with self.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            anterior = banco.execute("SELECT * FROM lotes WHERE request_id=?", (pedido["request_id"],)).fetchone()
            if anterior:
                if anterior["pedido"] != dados:
                    raise SessaoOcupada("Identificador já usado por outro lote.")
                return self._lote_publico(banco, anterior), False
            if banco.execute("SELECT 1 FROM tarefas WHERE status IN ('pendente','executando')").fetchone():
                raise SessaoOcupada("Já existe uma execução na sessão.")
            plano = self.configuracao.planejar({k: pedido[k] for k in ("empresas", "inicio", "fim")}, banco)
            if plano["hash"] != pedido["plano_hash"]:
                raise ValueError("O cadastro ou período mudou. Revise o plano novamente.")
            identificador, agora = uuid.uuid4().hex, _agora()
            banco.execute("INSERT INTO lotes VALUES (?,?,?,?,?,?,?,?)", (identificador, pedido["request_id"], dados, json.dumps(plano), "pendente", None, agora, agora))
            posicao = 0
            for empresa in plano["empresas"]:
                for rotina in empresa["rotinas"]:
                    tarefa_id = uuid.uuid4().hex
                    tarefa = {"request_id": str(uuid.uuid5(uuid.UUID(pedido["request_id"]), str(posicao))),
                              "empresa_codigo": empresa["codigo"], "capacidade": rotina,
                              "inicio": pedido["inicio"], "fim": pedido["fim"], "apuracao_confirmada": True}
                    banco.execute("INSERT INTO tarefas VALUES (?,?,?,?,?,?,?,?,?,?)", (tarefa_id, tarefa["request_id"], json.dumps(tarefa, sort_keys=True), "pendente", modo, None, None, None, agora, agora))
                    banco.execute("INSERT INTO itens_lote VALUES (?,?,?)", (identificador, posicao, tarefa_id))
                    posicao += 1
            lote = banco.execute("SELECT * FROM lotes WHERE id=?", (identificador,)).fetchone()
            return self._lote_publico(banco, lote), True

    def _lote_publico(self, banco, lote, detalhar=True):
        plano = json.loads(lote["plano"])
        publico = {"id": lote["id"], "request_id": lote["request_id"], "plano": plano,
                "status": lote["status"], "motivo": lote["motivo"], "criado": lote["criado"],
                "atualizado": lote["atualizado"]}
        if detalhar:
            publico["tarefas"] = [self._publica(t) for t in banco.execute("SELECT t.* FROM tarefas t JOIN itens_lote i ON i.tarefa_id=t.id WHERE i.lote_id=? ORDER BY i.posicao", (lote["id"],))]
        else:
            publico["plano"] = {k: plano[k] for k in ("inicio", "fim", "quantidade_rotinas")}
        return publico

    def listar_lotes(self):
        with self.conectar() as banco:
            return [self._lote_publico(banco, l, detalhar=False) for l in banco.execute("SELECT * FROM lotes ORDER BY rowid DESC LIMIT 20")]

    def obter_lote(self, identificador):
        with self.conectar() as banco:
            lote = banco.execute("SELECT * FROM lotes WHERE id=?", (identificador,)).fetchone()
            return self._lote_publico(banco, lote) if lote else None

    def cancelar_lote(self, identificador):
        with self.conectar() as banco:
            banco.execute("BEGIN IMMEDIATE")
            lote = banco.execute("SELECT * FROM lotes WHERE id=?", (identificador,)).fetchone()
            if lote is None or lote["status"] not in ("pendente", "executando"):
                raise SessaoOcupada("Este lote não está ativo.")
            banco.execute("UPDATE lotes SET status='interrompida', motivo='lote_cancelado', atualizado=? WHERE id=?", (_agora(), identificador))
            banco.execute("UPDATE tarefas SET status='interrompida', motivo='lote_cancelado', atualizado=? WHERE status='pendente' AND id IN (SELECT tarefa_id FROM itens_lote WHERE lote_id=?)", (_agora(), identificador))
            return [i["tarefa_id"] for i in banco.execute("SELECT tarefa_id FROM itens_lote WHERE lote_id=?", (identificador,))]

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

    def __init__(self, repositorio, executor=None, modo="consulta", login=None):
        self.repositorio, self.executor, self.modo = repositorio, executor, modo
        self._acordar = threading.Event()
        self._parar = threading.Event()
        self._worker = None
        self._controle_lock = threading.Lock()
        self._controle = None
        self._tarefa_atual = None
        self.login = login
        self.sessao_login = SessaoLogin()
        self._operacao = None
        self._operacao_ativa = False
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
        with self._controle_lock:
            self.sessao_login.cancelar()
            if self._operacao and self._operacao[1] is not None:
                self._operacao[1].limpar()
            self._operacao = None
            if self._controle is not None:
                self._controle.encerrar()
        if self._worker is not None:
            self._worker.join()  # termina a ação atual; não mata o mouse/teclado no meio
        self._trava.liberar()

    @property
    def ocupado(self):
        with self._controle_lock:
            return self._ocupado()

    def _ocupado(self):
        return (self._operacao is not None or self._operacao_ativa or self._controle is not None or
                self.repositorio.tem_pendentes())

    def estado_login(self):
        return {**self.sessao_login.publico(), "disponivel": self.login is not None and self.disponivel}

    def solicitar_login(self, credenciais, reiniciar=False):
        with self._controle_lock:
            if self.login is None or not self.disponivel:
                raise PrecondicaoRecusada("login_indisponivel")
            if self._operacao is not None or self._operacao_ativa or (not reiniciar and self._ocupado()):
                raise SessaoOcupada("A sessão está ocupada.")
            if reiniciar:
                self.repositorio.interromper_pendentes()
                if self._controle is not None:
                    self._controle.interromper()
            self.sessao_login.iniciar()
            self._operacao = ("reiniciar" if reiniciar else "login", credenciais)
            self._acordar.set()
            return self.estado_login()

    def solicitar_sessao(self, acao):
        if acao not in ("calibrar", "capturar"):
            raise ValueError("Operação inválida.")
        with self._controle_lock:
            if self.login is None or not self.disponivel:
                raise PrecondicaoRecusada("login_indisponivel")
            if self._ocupado():
                raise SessaoOcupada("A sessão está ocupada.")
            self.sessao_login.iniciar()
            self._operacao = (acao, None)
            self._acordar.set()
            return self.estado_login()

    def solicitar_calibracao(self):
        return self.solicitar_sessao("calibrar")

    def estado_controle(self):
        with self._controle_lock:
            if self._controle is None:
                return None
            return {"tarefa_id": self._tarefa_atual, "estado": self._controle.estado}

    def controlar(self, identificador, acao):
        if acao not in ("pausar", "continuar"):
            raise ValueError("Controle inválido.")
        with self._controle_lock:
            if self._parar.is_set() or identificador != self._tarefa_atual or self._controle is None:
                raise SessaoOcupada("Esta execução não está ativa; confira o histórico.")
            getattr(self._controle, acao)()
            return {"tarefa_id": identificador, "estado": self._controle.estado}

    def solicitar(self, pedido):
        if not self.disponivel:
            raise PrecondicaoRecusada("executor_indisponivel")
        pedido = validar_pedido(pedido)
        with self._controle_lock:
            if self._operacao is not None or self._operacao_ativa:
                raise SessaoOcupada("Login ou recuperação em andamento.")
            tarefa, nova = self.repositorio.criar(pedido, self.modo)
            if nova:
                self._acordar.set()
        return tarefa

    def solicitar_lote(self, pedido):
        if not self.disponivel or (self.modo == "windows" and not callable(getattr(self.executor, "executar_em_lote", None))):
            raise PrecondicaoRecusada("executor_indisponivel")
        with self._controle_lock:
            if self._operacao is not None or self._operacao_ativa:
                raise SessaoOcupada("Login ou recuperação em andamento.")
            lote, novo = self.repositorio.criar_lote(pedido, self.modo)
            if novo:
                self._acordar.set()
            return lote

    def cancelar_lote(self, identificador):
        with self._controle_lock:
            tarefas = self.repositorio.cancelar_lote(identificador)
            if self._controle is not None and self._tarefa_atual in tarefas:
                self._controle.interromper("lote_cancelado")
        return {"cancelamento_solicitado": True}

    def _trabalhar(self):
        try:
            self._executar_pendentes()
        except Exception:
            # Persistência indisponível: impede novas ações e pede retomada
            # manual, sem repetir uma geração cujo resultado se perdeu.
            self._parar.set()
            logging.getLogger(__name__).exception("Executor interrompido por falha de persistência.")
        finally:
            if self.login is not None:
                # Playwright/contexto são criados e fechados na mesma thread.
                self.login.encerrar()

    def _executar_operacao(self, operacao):
        acao, credenciais = operacao
        try:
            self.sessao_login.verificar()
            if acao == "calibrar":
                self.login.calibrar(self.sessao_login)
            elif acao == "capturar":
                self.login.capturar(self.sessao_login)
            else:
                if acao == "reiniciar":
                    self.login.reiniciar(self.sessao_login)
                self.login.executar(credenciais, self.sessao_login)
        except LoginRecusado as erro:
            motivos = {"login_cancelado", "codigo_expirado", "navegador_indisponivel", "destino_nao_permitido",
                       "tela_login_nao_reconhecida", "campos_login_nao_confirmados", "janela_login_nao_confirmada",
                       "tela_principal_nao_confirmada", "fechamento_nao_confirmado", "calibracao_nao_confirmada"}
            motivo = str(erro) if str(erro) in motivos else "login_nao_confirmado"
            self.sessao_login.fase("cancelado" if motivo == "login_cancelado" else "falha", motivo)
        except Exception:
            # Exceções de navegador podem conter senhas em traces; não registrar.
            self.sessao_login.fase("falha", "login_nao_confirmado")
        finally:
            if credenciais is not None:
                credenciais.limpar()
            with self._controle_lock:
                self._operacao_ativa = False

    def _executar_pendentes(self):
        while not self._parar.is_set():
            self._acordar.wait(timeout=1)
            self._acordar.clear()
            if self._parar.is_set():
                break
            with self._controle_lock:
                operacao, self._operacao = self._operacao, None
                if operacao is not None:
                    self._operacao_ativa = True
                    tarefa = None
                else:
                    tarefa = self.repositorio.proxima()
                    if tarefa is not None:
                        controle = ControleExecucao()
                        self._controle, self._tarefa_atual = controle, tarefa["id"]
            if operacao is not None:
                self._executar_operacao(operacao)
                continue
            if tarefa is None:
                continue
            identificador = tarefa["id"]
            try:
                pedido = validar_pedido(json.loads(tarefa["pedido"]))
                with controlar_execucao(controle):
                    executar = getattr(self.executor, "executar_em_lote", self.executor) if tarefa.get("lote_id") else self.executor
                    resultado = executar(pedido, lambda ev: self.repositorio.registrar_evento(identificador, ev))
                controle.verificar_interrupcao()
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
            except ExecucaoInterrompida as erro:
                motivo = str(erro) if str(erro) in ("retomada_nao_confirmada", "servidor_encerrado_durante_pausa", "reinicio_solicitado", "lote_cancelado") else "retomada_nao_confirmada"
                self.repositorio.concluir(identificador, "interrompida", None, motivo=motivo)
            except PrecondicaoRecusada as erro:
                motivos = {"executor_requer_windows", "calibracao_indisponivel", "dominio_fora_de_foco",
                           "tela_principal_nao_confirmada", "empresa_nao_confirmada", "periodo_nao_confirmado"}
                motivo = str(erro) if str(erro) in motivos else "precondicao_nao_confirmada"
                self.repositorio.concluir(identificador, "recusada", False, motivo=motivo)
            except Exception:
                # Sem exceções/capturas/caminhos privados na resposta remota.
                logging.getLogger(__name__).exception("Falha na tarefa %s", identificador)
                self.repositorio.concluir(identificador, "falha", False, motivo="erro_execucao_consulte_servidor")
            finally:
                with self._controle_lock:
                    self._controle, self._tarefa_atual = None, None
                if not self._parar.is_set() and self.repositorio.tem_pendentes():
                    self._acordar.set()
