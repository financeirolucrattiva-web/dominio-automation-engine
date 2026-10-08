"""Adaptador das rotinas existentes para uma sessão Windows dedicada.

Sem navegação nova, troca automática de empresa ou árvore UI Automation.
Só o processo no servidor importa os módulos que operam o desktop.
"""

import datetime as dt
from pathlib import Path
import sys
from types import SimpleNamespace

from app.servidor import PrecondicaoRecusada, validar_pedido

ROOT = Path(__file__).resolve().parents[1]


class ExecutorDominio:
    def __call__(self, pedido, receber_evento):
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
                or int(empresa[1]) != int(pedido["empresa_codigo"])
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
        with estados.observar_eventos(receber_evento):
            if pedido["capacidade"].startswith("registro_"):
                datas = {chave: dt.date.fromisoformat(pedido[chave]).strftime("%d/%m/%Y") for chave in ("inicio", "fim")}
                return geradores[pedido["capacidade"]](ROOT / "saida", data_inicial=datas["inicio"],
                                                       data_final=datas["fim"], prefixo=prefixo)
            if dominio.competencia_anterior() != tuple(dt.date.fromisoformat(pedido[chave]).strftime("%d/%m/%Y") for chave in ("inicio", "fim")):
                raise PrecondicaoRecusada("periodo_nao_confirmado")
            return geradores[pedido["capacidade"]](prefixo=prefixo)
