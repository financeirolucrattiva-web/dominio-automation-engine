"""API e arquivos da interface; nenhuma importação de mouse/teclado aqui."""

from contextlib import asynccontextmanager
import hmac
from pathlib import Path
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from app import capacidades
from app.servidor import PrecondicaoRecusada, SessaoOcupada, periodo_anterior

ROOT = Path(__file__).resolve().parents[1]


class PedidoTarefa(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: StrictStr
    capacidade: StrictStr
    empresa_codigo: StrictStr
    inicio: StrictStr
    fim: StrictStr
    apuracao_confirmada: StrictBool


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


def criar_app(servico, chave, pasta_saida=ROOT / "saida"):
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
                "ocupado": any(item["status"] in ("pendente", "executando") for item in servico.repositorio.listar())}

    @app.get("/api/capacidades", dependencies=[Depends(autorizar)])
    def catalogo():
        return [{"id": item.id, "nome": item.nome, "objetivo": item.objetivo,
                 "periodo": ("Usa o mês anterior à data do servidor. Confira se a apuração está fechada."
                             if item.id in ("sped_fiscal", "efd_contribuicoes") else
                             "Usa o período informado nos campos. Confira se a apuração está fechada."),
                 "pendencias": item.pendencias} for item in capacidades.listar_capacidades()]

    @app.get("/api/tarefas", dependencies=[Depends(autorizar)])
    def listar():
        return servico.repositorio.listar()

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
