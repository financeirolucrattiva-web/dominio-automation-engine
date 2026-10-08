"""API e arquivos da interface; nenhuma importação de mouse/teclado aqui."""

from contextlib import asynccontextmanager
import hmac
from pathlib import Path
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, SecretStr, Field, field_validator

from app import capacidades
from app.servidor import PrecondicaoRecusada, SessaoOcupada, periodo_anterior
from app.autenticacao import CredenciaisLogin, LoginRecusado
from app import configuracao_rotinas

ROOT = Path(__file__).resolve().parents[1]


class PedidoTarefa(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: StrictStr
    capacidade: StrictStr
    empresa_codigo: StrictStr
    inicio: StrictStr
    fim: StrictStr
    apuracao_confirmada: StrictBool


class PedidoLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: StrictStr = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    senha_onvio: SecretStr = Field(min_length=1, max_length=256)
    usuario_dominio: StrictStr = Field(min_length=1, max_length=100)
    senha_dominio: SecretStr = Field(min_length=1, max_length=256)
    confirmar_reinicio: StrictBool = False

    @field_validator("usuario_dominio", "senha_dominio")
    @classmethod
    def validar_teclado_remoto(cls, valor):
        texto = valor.get_secret_value() if isinstance(valor, SecretStr) else valor
        if not texto.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in texto):
            raise ValueError("O teclado remoto exige caracteres ASCII imprimíveis.")
        return valor


class PedidoCodigo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solicitacao_id: StrictStr = Field(pattern=r"^[0-9a-f]{32}$")
    codigo: SecretStr = Field(min_length=4, max_length=16)


class PedidoCalibracao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tela_principal_confirmada: StrictBool


class PassoRotina(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: StrictStr = Field(max_length=10)
    valor: StrictStr = Field(max_length=100)


class PedidoRotina(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: StrictStr = Field(min_length=1, max_length=100)
    passos: list[PassoRotina] = Field(min_length=1, max_length=80)


class PedidoRegime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: StrictStr | None = None
    nome: StrictStr = Field(min_length=1, max_length=100)
    rotinas: list[StrictStr] = Field(max_length=4)


class PedidoEmpresa(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: StrictStr = Field(pattern=r"^[0-9]{1,12}$")
    nome: StrictStr = Field(min_length=1, max_length=100)
    regime_id: StrictStr = Field(pattern=r"^[0-9a-f]{32}$")


class SelecaoLote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empresas: list[StrictStr] = Field(min_length=1, max_length=100)
    inicio: StrictStr
    fim: StrictStr


class PedidoLote(SelecaoLote):
    request_id: StrictStr
    apuracao_confirmada: StrictBool
    plano_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


def obter_chave(caminho=ROOT / "data" / "servidor_chave.txt"):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        with caminho.open("x", encoding="ascii") as arquivo:
            arquivo.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    chave = caminho.read_text(encoding="ascii").strip()
    if len(chave) < 32:
        raise ValueError("Chave local do servidor inválida; arquivo preservado.")
    return chave


def criar_app(servico, chave, pasta_saida=ROOT / "saida", pasta_rotinas=configuracao_rotinas.PASTA):
    if not isinstance(chave, str) or len(chave) < 32:
        raise ValueError("Configure uma chave de acesso de pelo menos 32 caracteres.")
    pasta_saida = Path(pasta_saida).resolve()
    autenticacao = HTTPBearer(auto_error=False)

    def autorizar(credenciais: HTTPAuthorizationCredentials | None = Depends(autenticacao)):
        if (credenciais is None or credenciais.scheme.lower() != "bearer"
                or not hmac.compare_digest(credenciais.credentials.encode(), chave.encode())):
            raise HTTPException(401, "Acesso não autorizado.")

    @asynccontextmanager
    async def lifespan(app):
        servico.iniciar()
        try:
            yield
        finally:
            servico.encerrar()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def proteger_respostas(request: Request, call_next):
        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        resposta.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        return resposta

    @app.exception_handler(RequestValidationError)
    async def erro_validacao(request, erro):
        # Pydantic inclui input/segredos nos erros padrão; a API não os repete.
        return JSONResponse({"detail": "Campos da tarefa inválidos."}, status_code=422)

    @app.get("/api/estado", dependencies=[Depends(autorizar)])
    def estado():
        inicio, fim = periodo_anterior()
        return {"modo": servico.modo, "execucao_habilitada": servico.disponivel,
                "periodo_anterior": {"inicio": inicio, "fim": fim},
                "controle_execucao": servico.estado_controle(),
                "login": servico.estado_login(),
                "ocupado": servico.ocupado}

    def iniciar_login(pedido, reiniciar=False):
        if reiniciar and not pedido.confirmar_reinicio:
            raise HTTPException(422, "Confirme o fechamento do ciclo antes de reiniciar.")
        credenciais = CredenciaisLogin(pedido.email, pedido.senha_onvio.get_secret_value(),
                                      pedido.usuario_dominio, pedido.senha_dominio.get_secret_value())
        try:
            return servico.solicitar_login(credenciais, reiniciar=reiniciar)
        except SessaoOcupada:
            credenciais.limpar()
            raise HTTPException(409, "A sessão está ocupada; cancele o login ativo antes de reiniciar.") from None
        except PrecondicaoRecusada:
            credenciais.limpar()
            raise HTTPException(503, "Login requer o executor Windows e os componentes do servidor.") from None

    @app.post("/api/login/iniciar", status_code=202, dependencies=[Depends(autorizar)])
    def login_iniciar(pedido: PedidoLogin):
        return iniciar_login(pedido)

    @app.post("/api/login/reiniciar", status_code=202, dependencies=[Depends(autorizar)])
    def login_reiniciar(pedido: PedidoLogin):
        return iniciar_login(pedido, reiniciar=True)

    @app.post("/api/login/codigo", dependencies=[Depends(autorizar)])
    def login_codigo(pedido: PedidoCodigo):
        try:
            servico.sessao_login.fornecer_codigo(pedido.solicitacao_id, pedido.codigo.get_secret_value())
            return {"recebido": True}
        except LoginRecusado:
            raise HTTPException(409, "O pedido de código expirou ou já foi atendido; confira o painel.") from None

    @app.post("/api/login/cancelar", dependencies=[Depends(autorizar)])
    def login_cancelar():
        servico.sessao_login.cancelar()
        return servico.estado_login()

    @app.post("/api/sessao/calibrar", status_code=202, dependencies=[Depends(autorizar)])
    def calibrar(pedido: PedidoCalibracao):
        if not pedido.tela_principal_confirmada:
            raise HTTPException(422, "Confirme a tela principal azul, sem menus ou relatórios, para calibrar.")
        try:
            return servico.solicitar_calibracao()
        except SessaoOcupada:
            raise HTTPException(409, "Aguarde a sessão ficar disponível.") from None
        except PrecondicaoRecusada:
            raise HTTPException(503, "Calibração requer o executor Windows.") from None

    @app.post("/api/sessao/capturar", status_code=202, dependencies=[Depends(autorizar)])
    def capturar():
        try:
            return servico.solicitar_sessao("capturar")
        except SessaoOcupada:
            raise HTTPException(409, "Aguarde o login ou a execução terminar para capturar.") from None
        except PrecondicaoRecusada:
            raise HTTPException(503, "Captura requer o executor Windows.") from None

    @app.get("/api/sessao/captura", dependencies=[Depends(autorizar)])
    def captura():
        imagem = servico.login.obter_captura() if servico.login is not None else None
        if imagem is None:
            raise HTTPException(404, "A captura expirou; solicite outra no painel.")
        return Response(imagem, media_type="image/png")

    @app.get("/api/capacidades", dependencies=[Depends(autorizar)])
    def catalogo():
        return [{"id": item.id, "nome": item.nome, "objetivo": item.objetivo,
                 "tipo_periodo": "competencia" if item.id in ("sped_fiscal", "efd_contribuicoes") else "datas",
                 "periodo": ("Escolha o mês e ano da competência, com a apuração fechada."
                             if item.id in ("sped_fiscal", "efd_contribuicoes") else
                             "Usa o período informado nos campos. Confira se a apuração está fechada."),
                 "pendencias": item.pendencias} for item in capacidades.listar_capacidades()]

    @app.get("/api/tarefas", dependencies=[Depends(autorizar)])
    def listar():
        return servico.repositorio.listar()

    @app.get("/api/cadastros", dependencies=[Depends(autorizar)])
    def cadastros():
        return servico.repositorio.configuracao.listar()

    @app.post("/api/regimes", dependencies=[Depends(autorizar)])
    def regime_salvar(pedido: PedidoRegime):
        try:
            return servico.repositorio.configuracao.salvar_regime(pedido.id, pedido.nome, pedido.rotinas)
        except ValueError:
            raise HTTPException(422, "Confira nome, regime existente e rotinas sem repetição.") from None

    @app.post("/api/empresas", dependencies=[Depends(autorizar)])
    def empresa_salvar(pedido: PedidoEmpresa):
        try:
            return servico.repositorio.configuracao.salvar_empresa(pedido.codigo, pedido.nome, pedido.regime_id)
        except ValueError:
            raise HTTPException(422, "Confira código, nome e regime cadastrado da empresa.") from None

    @app.post("/api/lotes/planejar", dependencies=[Depends(autorizar)])
    def lote_planejar(pedido: SelecaoLote):
        try:
            return servico.repositorio.configuracao.planejar(pedido.model_dump())
        except ValueError:
            raise HTTPException(422, "Confira empresas cadastradas, regimes com rotinas e período passado. SPED exige um mês completo.") from None

    @app.get("/api/lotes", dependencies=[Depends(autorizar)])
    def lotes_listar():
        return servico.repositorio.listar_lotes()

    @app.post("/api/lotes", status_code=202, dependencies=[Depends(autorizar)])
    def lote_iniciar(pedido: PedidoLote):
        try:
            return servico.solicitar_lote(pedido.model_dump())
        except SessaoOcupada:
            raise HTTPException(409, "A sessão está ocupada ou esse identificador pertence a outro lote.") from None
        except PrecondicaoRecusada:
            raise HTTPException(503, "Lote requer um executor disponível.") from None
        except ValueError:
            raise HTTPException(422, "Revise o plano novamente e confirme a apuração de todas as empresas. O cadastro ou período pode ter mudado.") from None

    @app.post("/api/lotes/{identificador}/cancelar", dependencies=[Depends(autorizar)])
    def lote_cancelar(identificador: str):
        try:
            return servico.cancelar_lote(identificador)
        except SessaoOcupada:
            raise HTTPException(409, "Este lote não está ativo; confira o histórico.") from None

    @app.get("/api/lotes/{identificador}", dependencies=[Depends(autorizar)])
    def lote_obter(identificador: str):
        lote = servico.repositorio.obter_lote(identificador)
        if lote is None:
            raise HTTPException(404, "Lote não encontrado.")
        return lote

    @app.get("/api/rotinas", dependencies=[Depends(autorizar)])
    def rotinas_listar():
        return configuracao_rotinas.listar(pasta_rotinas)

    @app.post("/api/rotinas", status_code=201, dependencies=[Depends(autorizar)])
    def rotinas_salvar(pedido: PedidoRotina):
        try:
            return configuracao_rotinas.salvar(pedido.model_dump(), pasta_rotinas)
        except ValueError:
            raise HTTPException(422, "Confira nome e passos de geração/leitura. Digitação exige um parâmetro de período ou empresa.") from None
        except OSError:
            raise HTTPException(503, "Não consegui salvar o rascunho no servidor.") from None

    @app.post("/api/tarefas", status_code=202, dependencies=[Depends(autorizar)])
    def solicitar(pedido: PedidoTarefa):
        try:
            return servico.solicitar(pedido.model_dump())
        except SessaoOcupada:
            raise HTTPException(409, "Já existe uma execução ou o identificador foi usado por outra tarefa.") from None
        except PrecondicaoRecusada:
            raise HTTPException(503, "Executor indisponível neste servidor.") from None
        except ValueError:
            raise HTTPException(422, "Confira função, empresa, período passado e confirmação da apuração.") from None

    @app.get("/api/tarefas/{identificador}", dependencies=[Depends(autorizar)])
    def consultar(identificador: str):
        tarefa = servico.repositorio.obter(identificador)
        if tarefa is None:
            raise HTTPException(404, "Tarefa não encontrada.")
        return {**tarefa, "eventos": servico.repositorio.eventos(identificador)}

    def controlar(identificador, acao):
        try:
            return servico.controlar(identificador, acao)
        except SessaoOcupada:
            raise HTTPException(409, "Esta execução não está ativa; confira o histórico.") from None

    @app.post("/api/tarefas/{identificador}/pausar", dependencies=[Depends(autorizar)])
    def pausar(identificador: str):
        return controlar(identificador, "pausar")

    @app.post("/api/tarefas/{identificador}/continuar", dependencies=[Depends(autorizar)])
    def continuar(identificador: str):
        return controlar(identificador, "continuar")

    @app.get("/api/tarefas/{identificador}/arquivo", dependencies=[Depends(autorizar)])
    def arquivo(identificador: str):
        tarefa = servico.repositorio.obter(identificador, privado=True)
        if tarefa is None or not tarefa["arquivo"]:
            raise HTTPException(404, "Arquivo indisponível.")
        caminho = Path(tarefa["arquivo"]).resolve()
        if not caminho.is_relative_to(pasta_saida) or not caminho.is_file():
            raise HTTPException(404, "Arquivo indisponível.")
        return FileResponse(caminho, filename=caminho.name)

    @app.get("/")
    def interface():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(ROOT / "web" / "sw.js", media_type="application/javascript")

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
    return app
