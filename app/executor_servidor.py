"""Adaptador das rotinas existentes para uma sessão Windows dedicada.

Individual e lote usam F8 e releem empresa/tela principal antes de gerar.
Só o processo no servidor importa os módulos que operam o desktop.
"""

import datetime as dt
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from app.servidor import PrecondicaoRecusada, validar_pedido
from app.controle_execucao import verificar_antes_de_agir, verificar_retomada, ponto_seguro

ROOT = Path(__file__).resolve().parents[1]


class FocoPerdidoDuranteExecucao(RuntimeError):
    """A emissão iniciada falhou; o worker pode tentar recuperação do lote."""


class ExecutorDominio:
    def __call__(self, pedido, receber_evento):
        return self._executar(pedido, receber_evento)

    def executar_em_lote(self, pedido, receber_evento):
        self._janela_lote = None
        return self._executar(pedido, receber_evento, em_lote=True)

    def recuperar_em_lote(self, pedido):
        """Limpa a sessão da rotina falha; nunca repete a geração."""
        if sys.platform != "win32" or getattr(self, "_janela_lote", None) is None:
            return False
        from app import interacao, tela
        janela = self._janela_lote
        if not self._voltar_ao_inicio(janela):
            return False
        empresa = tela.ler_empresa_selecionada(tela.capturar_tela())
        return (empresa is not None and str(empresa[1]).isdigit()
                and int(empresa[1]) == int(pedido["empresa_codigo"])
                and interacao.janela_dominio_em_foco(janela))

    def _voltar_ao_inicio(self, janela):
        """Retorna à tela calibrada; a identidade da empresa é conferida à parte."""
        from app import dominio, interacao, tela_principal
        if tela_principal.carregar_referencia() is None:
            return False
        contexto = SimpleNamespace(janela_dominio=janela)
        # Cada Esc usa a janela já reconhecida e volta a conferir o foco.
        # A tela azul interrompe a limpeza imediatamente, sem fechar Domínio.
        for tentativa in range(9):
            ponto_seguro()
            if dominio._verificar_retorno_tela_principal(contexto) == "tela_principal_reconhecida":
                return interacao.janela_dominio_em_foco(janela)
            if tentativa == 8:
                break
            if tentativa < 5:
                if not interacao.pressionar_esc_no_dominio(
                        janela, vezes=1, confirmar_conteudo=dominio._confirmar_conteudo_dominio):
                    return False
            elif not dominio.fechar_aba_ativa(janela):
                # Esc não bastou: botão Fechar ou Ctrl+F4 (nunca Alt+F4).
                return False
        return False

    def _executar(self, pedido, receber_evento, em_lote=False):
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
            print("Recuperando o painel azul antes de conferir a empresa.")
            if not self._voltar_ao_inicio(janela):
                raise PrecondicaoRecusada("tela_principal_nao_confirmada")
        empresa = tela.ler_empresa_selecionada(tela.capturar_tela())
        if (empresa is None or not str(empresa[1]).isdigit()
                or not interacao.janela_dominio_em_foco(janela)):
            raise PrecondicaoRecusada("empresa_nao_confirmada")
        validar_pedido(pedido)  # inclusive se o calendário mudou durante as leituras
        geradores = {
            "sped_fiscal": dominio.gerar_sped_fiscal,
            "efd_contribuicoes": dominio.gerar_efd_contribuicoes,
            "registro_saidas": dominio.gerar_registro_saidas,
            "registro_entradas": dominio.gerar_registro_entradas,
            "resumo_acumulador": dominio.gerar_resumo_acumulador,
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
        foco_perdido = False
        geracao_iniciada = False
        def conferir_foco():
            nonlocal foco_perdido
            # Uma exceção absorvida pelo gerador não libera ações posteriores.
            if foco_perdido or not interacao.janela_dominio_em_foco(janela):
                foco_perdido = True
                erro = FocoPerdidoDuranteExecucao if geracao_iniciada else PrecondicaoRecusada
                raise erro("dominio_fora_de_foco")

        with verificar_antes_de_agir(conferir_foco), verificar_retomada(preparar_retomada), estados.observar_eventos(receber_evento):
            ponto_seguro()
            if int(empresa[1]) != int(pedido["empresa_codigo"]):
                if not dominio.trocar_empresa(str(int(pedido["empresa_codigo"])), prefixo=prefixo,
                                             recuperar_inicio=lambda: self._voltar_ao_inicio(janela)):
                    raise PrecondicaoRecusada("empresa_nao_confirmada")
            # Confere novamente mesmo quando não houve troca: a tela pode ter
            # mudado entre a primeira leitura e a preparação da rotina.
            ponto_seguro()
            if dominio._verificar_retorno_tela_principal(contexto) != "tela_principal_reconhecida":
                raise PrecondicaoRecusada("tela_principal_nao_confirmada")
            atual = tela.ler_empresa_selecionada(tela.capturar_tela())
            if atual is None or not str(atual[1]).isdigit() or int(atual[1]) != int(pedido["empresa_codigo"]):
                raise PrecondicaoRecusada("empresa_nao_confirmada")
            ponto_seguro()
            validar_pedido(pedido)
            if em_lote:
                self._janela_lote = janela
            datas = {chave: dt.date.fromisoformat(pedido[chave]).strftime("%d/%m/%Y") for chave in ("inicio", "fim")}
            geracao_iniciada = True
            if pedido["capacidade"].startswith("registro_") or pedido["capacidade"] == "resumo_acumulador":
                return geradores[pedido["capacidade"]](ROOT / "saida", data_inicial=datas["inicio"],
                                                       data_final=datas["fim"], prefixo=prefixo)
            return geradores[pedido["capacidade"]](prefixo=prefixo, data_inicial=datas["inicio"], data_final=datas["fim"])
