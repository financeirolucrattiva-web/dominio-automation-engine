"""Motor de estados mínimo — generaliza o padrão já repetido em 4
rotinas reais contra o Domínio (SPED Fiscal, EFD Contribuições,
Registro de Saídas, Registro de Entradas): tirar print, checar se
apareceu um texto de SUCESSO, checar se apareceu um texto de ERRO,
esperar e tentar de novo — pulando a checagem (OCR) quando a tela não
mudou desde a última vez (fingerprint, `tela.assinatura_tela()`, seção
0.58).

Generalização de baixo risco, feita DEPOIS de 4 rotinas reais provarem
o mesmo padrão — não suposição de arquitetura. A aplicação inicial é
`dominio.esperar_e_achar()`, refeita por
cima deste motor mantendo assinatura e comportamento idênticos ao de
antes — nenhuma das 4 rotinas precisou mudar uma linha, porque todas
já chamavam `esperar_e_achar()`, não este módulo diretamente.

Esse núcleo continua sendo reutilizado. `AcompanhamentoRotina` também
registra a sequência das etapas das quatro rotinas, exige evidências
para avançar e separa ação enviada de retorno visual confirmado.
Não escolhe ações nem amplia a autonomia da IA.
"""

import time
import datetime
import json
from pathlib import Path
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from . import tela


_OBSERVADOR = ContextVar("observador_estados_da_execucao", default=None)


@contextmanager
def observar_eventos(observador):
    """Encaminha cópias de eventos à interface, somente nesta execução.

    A interface enfileira o evento; falha de exibição não modifica a
    rotina fiscal, o resultado ou o registro local de evidências.
    """
    token = _OBSERVADOR.set(observador)
    try:
        yield
    finally:
        _OBSERVADOR.reset(token)


class AcompanhamentoRotina:
    """Registra etapas observadas; não decide ações nem guarda dados fiscais."""

    ETAPAS = (
        "validar_dados", "identificar_empresa", "abrir_livros",
        "preencher_periodo", "gerar_previa", "exportar_pdf",
        "conferir_pdf", "encerrar",
    )
    EVIDENCIAS = {
        "datas_validas", "cabecalho_nome_codigo_lidos", "titulo_livros_fiscais_lido",
        "campos_periodo_confirmados", "ancora_registro_lida", "arquivo_novo_estavel",
        "pdf_tipo_periodo_cnpj_confirmados", "esc_enviado_fechamento_nao_verificado",
        "retorno_falha", "excecao", "tentativa_reiniciada", "rotina_concluida",
        "recuperacao_esc_enviado", "recuperacao_sem_confirmacao_visual",
        "recuperacao_esc_falhou", "encerramento_ja_tentado",
        "foco_dominio_nao_confirmado",
        "tela_principal_reconhecida", "tela_principal_nao_reconhecida",
        "referencia_tela_principal_ausente", "referencia_tela_principal_invalida",
        "item_menu_reconhecido", "formulario_e_botoes_reconhecidos",
        "aviso_resultado_reconhecido", "fechamento_solicitado",
    }
    CONFIRMACOES = dict(zip(ETAPAS, (
        "datas_validas", "cabecalho_nome_codigo_lidos", "titulo_livros_fiscais_lido",
        "campos_periodo_confirmados", "ancora_registro_lida", "arquivo_novo_estavel",
        "pdf_tipo_periodo_cnpj_confirmados", "esc_enviado_fechamento_nao_verificado",
    )))
    FLUXO_GERACAO = {
        "navegar_menu": "item_menu_reconhecido",
        "preencher_periodo": "campos_periodo_confirmados",
        "identificar_formulario": "formulario_e_botoes_reconhecidos",
        "gerar_documento": "aviso_resultado_reconhecido",
        "encerrar": "fechamento_solicitado",
    }

    def __init__(self, rotina, pasta_logs=None):
        if rotina not in ("registro_saidas", "registro_entradas", "sped_fiscal", "efd_contribuicoes", "geracao_fiscal"):
            raise ValueError("Rotina sem acompanhamento configurado.")
        self.rotina = rotina
        if rotina in ("sped_fiscal", "efd_contribuicoes", "geracao_fiscal"):
            self.CONFIRMACOES = self.FLUXO_GERACAO.copy()
            self.ETAPAS = tuple(self.CONFIRMACOES)
        self.execution_id = uuid.uuid4().hex
        pasta_logs = Path(pasta_logs) if pasta_logs is not None else Path(__file__).resolve().parent.parent / "data" / "execucoes"
        self.caminho_log = pasta_logs / f"{self.execution_id}.jsonl"
        self.eventos = []
        self.tentativa = 1
        self.etapa = None
        self.confirmadas = []
        self.finalizada = False
        self.inicio = time.monotonic()
        self.inicio_etapa = self.inicio
        self._aviso_log = False
        self.recuperacao_iniciada = False
        self.janela_dominio = None  # HWND/PID em memória; nunca no JSONL.

    def _registrar(self, etapa, status, evidencia=None):
        if evidencia is not None and evidencia not in self.EVIDENCIAS:
            raise ValueError("Evidência precisa ser um marcador sem dados fiscais.")
        evento = {
            "execution_id": self.execution_id, "routine_id": self.rotina,
            "attempt": self.tentativa, "step": etapa, "status": status,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - self.inicio_etapa, 3),
            "evidence": evidencia,
        }
        self.eventos.append(evento)
        observador = _OBSERVADOR.get()
        if observador is not None:
            try:
                observador(dict(evento))
            except Exception:
                pass
        print(f"[estado] {etapa}: {status}" + (f" ({evidencia})" if evidencia else ""))
        try:
            self.caminho_log.parent.mkdir(parents=True, exist_ok=True)
            with self.caminho_log.open("a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
        except OSError:
            if not self._aviso_log:
                print("[estado] Aviso: não foi possível gravar o histórico local; acompanhamento continua no console.")
                self._aviso_log = True

    def iniciar(self, etapa):
        if self.finalizada or etapa not in self.ETAPAS:
            raise ValueError("Etapa de rotina inválida.")
        esperado = self.ETAPAS[len(self.confirmadas)] if len(self.confirmadas) < len(self.ETAPAS) else None
        if etapa != esperado or (self.etapa is not None and self.etapa not in self.confirmadas):
            raise ValueError("Não é possível avançar sem evidência da etapa anterior.")
        self.etapa = etapa
        self.inicio_etapa = time.monotonic()
        self._registrar(etapa, "inicio")

    def confirmar(self, evidencia):
        if self.etapa is None or self.etapa in self.confirmadas or self.finalizada:
            raise ValueError("Nenhuma etapa pendente para confirmar.")
        confirmacao_visual = self.etapa == "encerrar" and evidencia == "tela_principal_reconhecida"
        if evidencia != self.CONFIRMACOES[self.etapa] and not confirmacao_visual:
            raise ValueError("Evidência não corresponde à etapa atual.")
        status = "acao_executada" if self.etapa == "encerrar" and not confirmacao_visual else "confirmado"
        self._registrar(self.etapa, status, evidencia)
        self.confirmadas.append(self.etapa)

    def tentar_novamente(self):
        if self.finalizada or self.etapa is None:
            raise ValueError("Nenhuma tentativa em andamento.")
        self._registrar(self.etapa, "falha", "tentativa_reiniciada")
        self.tentativa += 1
        self.etapa = None
        self.confirmadas = []
        self.janela_dominio = None

    def registrar_recuperacao(self, status, evidencia=None):
        """Registra saída tentada, preservando a etapa/resultado que falhou."""
        if status == "inicio":
            if self.finalizada or self.recuperacao_iniciada or "gerar_previa" not in self.confirmadas:
                return False
            self.recuperacao_iniciada = True
        elif self.finalizada or not self.recuperacao_iniciada or status not in ("acao_executada", "resultado_nao_verificado", "inconclusivo", "confirmado"):
            raise ValueError("Evento de recuperação inválido.")
        if status == "confirmado" and evidencia != "tela_principal_reconhecida":
            raise ValueError("Recuperação confirmada exige referência visual positiva.")
        self._registrar("recuperar_interface", status, evidencia)
        return True

    def registrar_encerramento_inconclusivo(self, evidencia="foco_dominio_nao_confirmado"):
        if self.finalizada or self.etapa != "encerrar":
            raise ValueError("Encerramento não está em andamento.")
        self._registrar("encerrar", "inconclusivo", evidencia)

    def registrar_encerramento_nao_verificado(self):
        if self.finalizada or self.etapa != "encerrar":
            raise ValueError("Encerramento não está em andamento.")
        self._registrar("encerrar", "resultado_nao_verificado", "referencia_tela_principal_ausente")

    def concluir(self, sucesso, evidencia="retorno_falha"):
        if self.finalizada:
            return
        if sucesso and tuple(self.confirmadas) != self.ETAPAS:
            raise ValueError("Sucesso exige evidências de todas as etapas.")
        if not sucesso and self.etapa is not None:
            self._registrar(self.etapa, "falha", evidencia)
        self.inicio_etapa = self.inicio
        self._registrar("fim", "concluido" if sucesso else "falha", "rotina_concluida" if sucesso else evidencia)
        self.finalizada = True


def esperar_por_estado(detectores, espera_minima=6, tentativas=90, intervalo=2):
    """Tira print repetidamente até um dos `detectores` achar alguma
    coisa, ou esgotar as tentativas — nunca por tempo fixo sozinho
    (mesmo princípio de sempre neste projeto).

    `detectores`: lista de `(nome_estado, funcao)`, testados NESSA
    ORDEM a cada tentativa — o primeiro que achar algo vence (mesmo
    princípio de `TITULOS_ERRO` ser percorrido em ordem, em
    `dominio.py`). `funcao(imagem)` devolve uma posição `(x, y)` (achou)
    ou `None`.

    Pula a chamada de todos os detectores (que geralmente envolvem OCR,
    a parte mais lenta) quando a tela está idêntica à tentativa
    anterior (`tela.assinatura_tela()`/`tela_mudou()`, seção 0.58) —
    rodar os detectores de novo sobre a mesma imagem nunca mudaria a
    resposta.

    Devolve `(imagem, nome_estado, posicao)` quando um detector achar,
    ou `(None, None, None)` se esgotar as tentativas sem achar nada.
    """
    print(f"Esperando pelo menos {espera_minima}s antes de checar...")
    time.sleep(espera_minima)
    assinatura_anterior = None
    for tentativa in range(1, tentativas + 1):
        imagem = tela.capturar_tela()
        assinatura_atual = tela.assinatura_tela(imagem)
        if not tela.tela_mudou(assinatura_anterior, assinatura_atual):
            print(f"Tela igual à tentativa anterior, pulando checagem (tentativa {tentativa}/{tentativas})...")
            time.sleep(intervalo)
            continue
        assinatura_anterior = assinatura_atual

        # A mesma captura pode ser examinada por vários títulos. Reutiliza
        # OCR por região/escala nesta tentativa, mantendo a ordem anterior.
        with tela.reutilizar_ocr():
            for nome_estado, funcao in detectores:
                pos = funcao(imagem)
                if pos is not None:
                    return imagem, nome_estado, pos

        print(f"Nenhum estado esperado reconhecido ainda (tentativa {tentativa}/{tentativas}) — esperando mais {intervalo}s...")
        time.sleep(intervalo)
    return None, None, None
