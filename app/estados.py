"""Motor de estados mínimo — generaliza o padrão já repetido em 4
rotinas reais contra o Domínio (SPED Fiscal, EFD Contribuições,
Registro de Saídas, Registro de Entradas): tirar print, checar se
apareceu um texto de SUCESSO, checar se apareceu um texto de ERRO,
esperar e tentar de novo — pulando a checagem (OCR) quando a tela não
mudou desde a última vez (fingerprint, `tela.assinatura_tela()`, seção
0.58).

Generalização de baixo risco, feita DEPOIS de 4 rotinas reais provarem
o mesmo padrão — não suposição de arquitetura. A primeira (e por
enquanto única) aplicação é `dominio.esperar_e_achar()`, refeita por
cima deste motor mantendo assinatura e comportamento idênticos ao de
antes — nenhuma das 4 rotinas precisou mudar uma linha, porque todas
já chamavam `esperar_e_achar()`, não este módulo diretamente.

Não é um "StateEngine" completo no sentido do prompt original do
projeto (sem máquina de transição formal entre MUITOS estados nomeados
— ainda não temos rotinas o bastante pra justificar isso) — é
deliberadamente menor: só o núcleo de "esperar até um de vários
detectores achar alguma coisa", que é o que as 4 rotinas reais
realmente precisam até agora. Crescer pra algo maior quando uma rotina
nova pedir de verdade, não antes.
"""

import time
import datetime
import json
from pathlib import Path
import uuid

from . import tela


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
    }
    CONFIRMACOES = dict(zip(ETAPAS, (
        "datas_validas", "cabecalho_nome_codigo_lidos", "titulo_livros_fiscais_lido",
        "campos_periodo_confirmados", "ancora_registro_lida", "arquivo_novo_estavel",
        "pdf_tipo_periodo_cnpj_confirmados", "esc_enviado_fechamento_nao_verificado",
    )))

    def __init__(self, rotina, pasta_logs=None):
        if rotina not in ("registro_saidas", "registro_entradas"):
            raise ValueError("Rotina sem acompanhamento configurado.")
        self.rotina = rotina
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
        if evidencia != self.CONFIRMACOES[self.etapa]:
            raise ValueError("Evidência não corresponde à etapa atual.")
        status = "acao_executada" if self.etapa == "encerrar" else "confirmado"
        self._registrar(self.etapa, status, evidencia)
        self.confirmadas.append(self.etapa)

    def tentar_novamente(self):
        if self.finalizada or self.etapa is None:
            raise ValueError("Nenhuma tentativa em andamento.")
        self._registrar(self.etapa, "falha", "tentativa_reiniciada")
        self.tentativa += 1
        self.etapa = None
        self.confirmadas = []

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

        for nome_estado, funcao in detectores:
            pos = funcao(imagem)
            if pos is not None:
                return imagem, nome_estado, pos

        print(f"Nenhum estado esperado reconhecido ainda (tentativa {tentativa}/{tentativas}) — esperando mais {intervalo}s...")
        time.sleep(intervalo)
    return None, None, None
