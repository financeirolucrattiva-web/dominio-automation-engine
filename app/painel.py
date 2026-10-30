"""Modelo de apresentação dos eventos reais; não escolhe ou executa ações."""

import math
import re

_PASSO = re.compile(r"^passo_(\d{2})$")


class _NomesRotinas(dict):
    """Rotinas fixas + rotinas aprovadas do configurador (`rotina_visual` nos eventos, `visual_<id>` na capacidade)."""

    def _visual(self, chave):
        return isinstance(chave, str) and (chave == "rotina_visual" or re.fullmatch(r"visual_[0-9a-f]{32}", chave) is not None)

    def __contains__(self, chave):
        return dict.__contains__(self, chave) or self._visual(chave)

    def __missing__(self, chave):
        if not self._visual(chave):
            raise KeyError(chave)
        try:
            from app import capacidades
            return capacidades.obter_capacidade(chave).nome
        except Exception:
            return "Rotina do configurador"

    def get(self, chave, padrao=None):
        return self[chave] if chave in self else padrao


class _NomesEtapas(dict):
    def __contains__(self, chave):
        return dict.__contains__(self, chave) or (isinstance(chave, str) and _PASSO.match(chave) is not None)

    def __missing__(self, chave):
        achado = _PASSO.match(chave) if isinstance(chave, str) else None
        if achado is None:
            raise KeyError(chave)
        return f"Passo {int(achado.group(1))}"

    def get(self, chave, padrao=None):
        return self[chave] if chave in self else padrao


NOMES_ROTINAS = _NomesRotinas({
    "sped_fiscal": "SPED Fiscal", "efd_contribuicoes": "Demonstrativo EFD Contribuições",
    "registro_saidas": "Registro de Saídas", "registro_entradas": "Registro de Entradas",
    "resumo_acumulador": "Resumo por Acumulador",
    "livros_fiscais": "Livros Fiscais — Entradas, Saídas e ICMS",
    "geracao_fiscal": "Geração fiscal",
})
NOMES_ETAPAS = _NomesEtapas({
    "validar_dados": "Validar dados", "identificar_empresa": "Identificar empresa",
    "abrir_livros": "Abrir Livros Fiscais", "preencher_periodo": "Preencher período",
    "abrir_resumo": "Abrir Resumo por Acumulador",
    "gerar_previa": "Gerar prévia", "exportar_pdf": "Exportar PDF",
    "conferir_pdf": "Conferir PDF", "encerrar": "Encerrar e conferir retorno",
    "navegar_menu": "Navegar pelo menu", "identificar_formulario": "Identificar formulário",
    "gerar_documento": "Gerar documento", "recuperar_interface": "Recuperar interface",
    "fim": "Resultado da rotina",
})
NOMES_STATUS = {
    "inicio": "Em andamento", "confirmado": "Confirmado",
    "acao_executada": "Ação enviada", "resultado_nao_verificado": "Não verificado",
    "inconclusivo": "Inconclusivo", "falha": "Falhou", "concluido": "Concluído pela rotina",
}
ETAPAS_LIVROS = (
    "validar_dados", "identificar_empresa", "abrir_livros", "preencher_periodo",
    "gerar_previa", "exportar_pdf", "conferir_pdf", "encerrar",
)
ETAPAS_GERACAO = (
    "navegar_menu", "preencher_periodo", "identificar_formulario", "gerar_documento", "encerrar",
)
PROJETO = (
    ("1", "Estados das rotinas", "Implementado; execução observada", "Revalidar as quatro rotinas na versão atual."),
    ("2", "Execução e recuperação", "Individual e lote para teste", "Conferir resultado e retorno; lote por empresa/regime ainda precisa da rodada Windows."),
    ("3", "Catálogo de capacidades", "Catálogo preparado", "Validar execução estruturada e seus resultados."),
    ("4", "Aprender por demonstração", "Gravação e revisão disponíveis", "Validar campos, teclas, hover e estados nas rotinas gravadas."),
    ("5", "Agentes operadores", "Planejado", "Usar capacidades validadas com uma fila por sessão."),
    ("6", "Interface e servidor dedicado", "Site e executor preparados", "Validar o Domínio na sessão Windows do servidor."),
)


class EstadoPainel:
    def __init__(self):
        self.limpar()

    def limpar(self):
        self.execution_id = None
        self.rotina = "Nenhuma execução"
        self.tentativa = 0
        self.etapa = "Aguardando início"
        self.resultado = "Pronto para iniciar"
        self.retorno = "Ainda não observado"
        self.etapas = ()
        self.linhas = {}

    def receber(self, evento):
        """Aceita só identificadores conhecidos; nunca exibe conteúdo OCR."""
        if not isinstance(evento, dict):
            return False
        rotina, etapa, status = (evento.get(chave) for chave in ("routine_id", "step", "status"))
        execucao, tentativa = evento.get("execution_id"), evento.get("attempt")
        segundos = evento.get("elapsed_seconds")
        if any(not isinstance(valor, str) for valor in (rotina, etapa, status)):
            return False
        if (rotina not in NOMES_ROTINAS or etapa not in NOMES_ETAPAS or status not in NOMES_STATUS
                or not isinstance(execucao, str) or len(execucao) != 32
                or any(c not in "0123456789abcdef" for c in execucao)
                or type(tentativa) is not int or tentativa < 1
                or type(segundos) not in (int, float) or not math.isfinite(segundos) or segundos < 0):
            return False
        if etapa == "encerrar" and status == "confirmado" and evento.get("evidence") != "tela_principal_reconhecida":
            return False
        if execucao != self.execution_id or tentativa != self.tentativa:
            self.limpar()
            self.execution_id, self.tentativa = execucao, tentativa
            self.rotina = NOMES_ROTINAS[rotina]
            self.etapas = (() if rotina == "rotina_visual" else
                           tuple("abrir_resumo" if e == "abrir_livros" else e for e in ETAPAS_LIVROS)
                           if rotina == "resumo_acumulador" else ETAPAS_LIVROS if rotina.startswith("registro_") or rotina == "livros_fiscais" else ETAPAS_GERACAO)
        if rotina == "rotina_visual" and etapa not in self.etapas and etapa not in ("fim", "recuperar_interface"):
            self.etapas += (etapa,)  # passos aparecem na ordem em que chegam; "encerrar" vem por último
        self.etapa = NOMES_ETAPAS[etapa]
        self.linhas[etapa] = (NOMES_STATUS[status], f"{segundos:.1f} s", status)
        evidencia = evento.get("evidence")
        if etapa in ("encerrar", "recuperar_interface"):
            if status == "confirmado" and evidencia == "tela_principal_reconhecida":
                self.retorno = "Tela principal confirmada"
            elif status in ("acao_executada", "resultado_nao_verificado"):
                self.retorno = "Ação enviada; retorno não verificado"
            elif status in ("inconclusivo", "falha"):
                self.retorno = "Retorno não confirmado"
        if etapa == "fim":
            self.resultado = NOMES_STATUS[status]
        elif status == "falha":
            self.resultado = "Falha na etapa; confira o log"
        elif status == "inicio" and self.resultado == "Pronto para iniciar":
            self.resultado = "Em execução"
        return True

    @property
    def confirmadas(self):
        return sum(self.linhas.get(etapa, (None, None, None))[2] == "confirmado" for etapa in self.etapas)

    def linhas_tabela(self):
        etapas = self.etapas + tuple(e for e in ("recuperar_interface", "fim") if e in self.linhas)
        return tuple((etapa, NOMES_ETAPAS[etapa], *self.linhas.get(etapa, ("Aguardando", "—", "aguardando")))
                     for etapa in etapas)
