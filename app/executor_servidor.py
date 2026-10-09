"""Adaptador das rotinas existentes para uma sessão Windows dedicada.

Lote usa a troca F8 existente e relê empresa/tela principal antes de gerar.
Só o processo no servidor importa os módulos que operam o desktop.
"""

import datetime as dt
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from app.servidor import PrecondicaoRecusada, validar_pedido
from app.controle_execucao import verificar_retomada, ponto_seguro

ROOT = Path(__file__).resolve().parents[1]


class ExecutorDominio:
    def __call__(self, pedido, receber_evento):
        return self._executar(pedido, receber_evento)

    def executar_em_lote(self, pedido, receber_evento):
        # Só o worker pode escolher este caminho; a tarefa HTTP não aceita
        # flags para desligar a conferência da empresa individual.
        self._janela_lote = None
        return self._executar(pedido, receber_evento, trocar_empresa=True)

    def recuperar_em_lote(self, pedido):
        """Limpa a sessão da rotina falha; nunca repete a geração."""
        if sys.platform != "win32" or getattr(self, "_janela_lote", None) is None:
            return False
        from app import dominio, interacao, tela, tela_principal
        janela = self._janela_lote
        if tela_principal.carregar_referencia() is None:
            return False
        contexto = SimpleNamespace(janela_dominio=janela)
        # Cada Esc usa a janela já reconhecida e volta a conferir o foco.
        # A tela azul interrompe a limpeza imediatamente, sem fechar Domínio.
        for tentativa in range(6):
            ponto_seguro()
            if dominio._verificar_retorno_tela_principal(contexto) == "tela_principal_reconhecida":
                empresa = tela.ler_empresa_selecionada(tela.capturar_tela())
                return (empresa is not None and str(empresa[1]).isdigit()
                        and int(empresa[1]) == int(pedido["empresa_codigo"])
                        and interacao.janela_dominio_em_foco(janela))
            if tentativa == 5:
                break
            if not interacao.pressionar_esc_no_dominio(
                    janela, vezes=1, confirmar_conteudo=dominio._confirmar_conteudo_dominio):
                return False
        return False

    def _executar(self, pedido, receber_evento, trocar_empresa=False):
        if sys.platform != "win32":
            raise PrecondicaoRecusada("executor_requer_windows")
        validar_pedido(pedido)
        from app import dominio, estados, interacao, tela, tela_principal

        if tela_principal.carregar_referencia() is None:
            raise PrecondicaoRecusada("calibracao_indisponivel")
        # Minimiza somente o console do servidor; não tenta focar por clique
        # uma tela cujo estado ainda não foi reconhecido.
        interacao._minimizar_console_proprio()
        janela = interacao.identificar_janela_dominio_atual()
        if janela is None or not interacao.janela_dominio_em_foco(janela):
            raise PrecondicaoRecusada("dominio_fora_de_foco")
        contexto = SimpleNamespace(janela_dominio=janela)
        if dominio._verificar_retorno_tela_principal(contexto) != "tela_principal_reconhecida":
            raise PrecondicaoRecusada("tela_principal_nao_confirmada")
        empresa = tela.ler_empresa_selecionada(tela.capturar_tela())
        if (empresa is None or not str(empresa[1]).isdigit()
                or (not trocar_empresa and int(empresa[1]) != int(pedido["empresa_codigo"]))
                or not interacao.janela_dominio_em_foco(janela)):
            raise PrecondicaoRecusada("empresa_nao_confirmada")
        validar_pedido(pedido)  # inclusive se o calendário mudou durante as leituras
        geradores = {
            "sped_fiscal": dominio.gerar_sped_fiscal,
            "efd_contribuicoes": dominio.gerar_efd_contribuicoes,
            "registro_saidas": dominio.gerar_registro_saidas,
            "registro_entradas": dominio.gerar_registro_entradas,
        }
        prefixo = f"servidor_{pedido['request_id'].replace('-', '')}_"
        def preparar_retomada():
            referencia = tela_principal.carregar_referencia()
            if referencia is None or not interacao.janela_dominio_em_foco(janela):
                return lambda: False
            imagem = tela.capturar_tela()
            # Exclui a barra do Windows (relógio), usando a medição local.
            area = (0, 0, imagem.width, referencia["retangulo"][3])
            antes = imagem.crop(area).convert("RGB")
            def verificar():
                for tentativa in range(4):
                    if not interacao.janela_dominio_em_foco(janela):
                        return False
                    atual = tela.capturar_tela()
                    if atual.size == imagem.size and atual.crop(area).convert("RGB").tobytes() == antes.tobytes():
                        return interacao.janela_dominio_em_foco(janela)
                    if tentativa < 3:
                        time.sleep(0.25)  # admite outra fase do cursor piscante
                return False
            return verificar
        with verificar_retomada(preparar_retomada), estados.observar_eventos(receber_evento):
            if trocar_empresa and int(empresa[1]) != int(pedido["empresa_codigo"]):
                if not dominio.trocar_empresa(pedido["empresa_codigo"], prefixo=prefixo):
                    raise PrecondicaoRecusada("empresa_nao_confirmada")
                if (not interacao.janela_dominio_em_foco(janela) or
                        dominio._verificar_retorno_tela_principal(contexto) != "tela_principal_reconhecida"):
                    raise PrecondicaoRecusada("tela_principal_nao_confirmada")
                atual = tela.ler_empresa_selecionada(tela.capturar_tela())
                if (atual is None or not str(atual[1]).isdigit() or int(atual[1]) != int(pedido["empresa_codigo"])
                        or not interacao.janela_dominio_em_foco(janela)):
                    raise PrecondicaoRecusada("empresa_nao_confirmada")
            validar_pedido(pedido)
            if trocar_empresa:
                self._janela_lote = janela
            datas = {chave: dt.date.fromisoformat(pedido[chave]).strftime("%d/%m/%Y") for chave in ("inicio", "fim")}
            if pedido["capacidade"].startswith("registro_"):
                return geradores[pedido["capacidade"]](ROOT / "saida", data_inicial=datas["inicio"],
                                                       data_final=datas["fim"], prefixo=prefixo)
            return geradores[pedido["capacidade"]](prefixo=prefixo, data_inicial=datas["inicio"], data_final=datas["fim"])
