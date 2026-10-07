"""Regressões de transição do lote, sem desktop ou dados reais."""

import contextlib
import importlib.util
import io
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch


class TestLote(unittest.TestCase):
    def setUp(self):
        import app
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.console = io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.console))
        interacao = types.ModuleType("app.interacao")
        with patch.dict("sys.modules", {"app.interacao": interacao}), patch.object(app, "interacao", interacao, create=True), patch("ctypes.windll", Mock(), create=True):
            spec = importlib.util.spec_from_file_location("app._dominio_lote_teste", Path(__file__).resolve().parents[1] / "app" / "dominio.py")
            self.d = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.d)
        d = self.d
        self.stack.enter_context(patch.object(d.time, "sleep"))
        for nome in ("focar_dominio", "pressionar_esc_repetidas", "_minimizar_console_proprio"):
            self.stack.enter_context(patch.object(d.interacao, nome, Mock(), create=True))
        self.stack.enter_context(patch.object(d.interacao, "identificar_janela_dominio_atual", return_value={"hwnd": 1}, create=True))
        self.foco = self.stack.enter_context(patch.object(d.interacao, "janela_dominio_em_foco", return_value=True, create=True))
        self.referencia = Mock()
        self.referencia.exists.return_value = True
        self.stack.enter_context(patch.object(d.tela_principal, "ARQUIVO_REFERENCIA", self.referencia))
        self.carregar = self.stack.enter_context(patch.object(d.tela_principal, "carregar_referencia", return_value={"referencia": "sintetica"}))
        self.corresponde = self.stack.enter_context(patch.object(d.tela_principal, "corresponde", return_value=True))
        self.stack.enter_context(patch.object(d.tela, "capturar_tela", return_value="frame"))
        self.cabecalho = self.stack.enter_context(patch.object(d, "_confirmar_conteudo_dominio", return_value=True))
        self.empresas = [{"codigo": "9001", "apelido": "FICTICIA A"}, {"codigo": "9002", "apelido": "FICTICIA B"}]
        self.stack.enter_context(patch.object(d.empresas, "carregar_empresas", return_value=self.empresas))
        self.stack.enter_context(patch.object(d.empresas, "regimes_disponiveis", return_value=["TESTE"]))
        self.stack.enter_context(patch.object(d.empresas, "filtrar_por_regime", return_value=self.empresas))
        self.stack.enter_context(patch.object(d.empresas, "documentos_necessarios", return_value=["ICMS", "CONTRIBUICOES"]))
        self.stack.enter_context(patch.object(d.ia, "resumir_lote", return_value=None))
        self.stack.enter_context(patch.object(d.erros, "decisoes_da_sessao", []))
        self.trocar = self.stack.enter_context(patch.object(d, "trocar_empresa", return_value=True))
        self.icms, self.contribuicoes = Mock(return_value=True), Mock(return_value=True)
        self.stack.enter_context(patch.object(d, "_GERADORES", {"ICMS": self.icms, "CONTRIBUICOES": self.contribuicoes}))

    def executar(self):
        self.d.executar_lote(regime="TESTE", confirmar=lambda selecionadas: True)

    def test_falha_limpa_com_principal_confirmada_segue_documentos_e_empresas(self):
        self.icms.return_value = False
        self.executar()
        self.assertEqual(self.icms.call_count, 2)
        self.assertEqual(self.contribuicoes.call_count, 2)
        self.assertEqual(self.trocar.call_count, 2)
        self.assertIn("ICMS: falha na geração, CONTRIBUICOES: sucesso", self.console.getvalue())
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()

    def test_retorno_desconhecido_para_antes_do_proximo_documento_ou_empresa(self):
        for resultado in (False, True):
            with self.subTest(resultado=resultado):
                self.icms.reset_mock()
                self.contribuicoes.reset_mock()
                self.trocar.reset_mock()
                self.corresponde.return_value = True
                def gerar(*, prefixo):
                    self.corresponde.return_value = False
                    return resultado
                self.icms.side_effect = gerar
                self.executar()
                self.icms.assert_called_once_with(prefixo="9001_ICMS_")
                self.contribuicoes.assert_not_called()
                self.trocar.assert_called_once_with("9001", prefixo="9001_")
                self.d.interacao.pressionar_esc_repetidas.assert_not_called()

    def test_referencia_invalida_para_antes_da_primeira_acao(self):
        self.carregar.return_value = None
        self.executar()
        self.trocar.assert_not_called()
        self.icms.assert_not_called()
        self.d.interacao.focar_dominio.assert_not_called()
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertIn("lote interrompido", self.console.getvalue())

    def test_excecao_em_tela_desconhecida_nao_envia_esc_nem_repete(self):
        def gerar(*, prefixo):
            self.corresponde.return_value = False
            raise RuntimeError("erro simulado")
        self.icms.side_effect = gerar
        self.executar()
        self.icms.assert_called_once_with(prefixo="9001_ICMS_")
        self.contribuicoes.assert_not_called()
        self.trocar.assert_called_once_with("9001", prefixo="9001_")
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertIn("ICMS: erro inesperado na geração", self.console.getvalue())

    def test_sem_referencia_avisa_uma_vez_e_preserva_lote_supervisionado(self):
        self.referencia.exists.return_value = False
        self.executar()
        self.assertEqual(self.console.getvalue().count("Lote sem referência da tela principal"), 1)
        self.assertEqual(self.icms.call_count, 2)
        self.assertEqual(self.contribuicoes.call_count, 2)
        self.assertEqual(self.trocar.call_count, 2)
        self.d.interacao.focar_dominio.assert_called_once_with()
        self.d.tela.capturar_tela.assert_not_called()

    def test_resumo_preserva_resultados_anteriores_ao_retorno_inconclusivo(self):
        def gerar(*, prefixo):
            self.corresponde.return_value = False
            return False
        self.contribuicoes.side_effect = gerar
        self.executar()
        self.assertIn("ICMS: sucesso, CONTRIBUICOES: falha na geração, -: lote interrompido", self.console.getvalue())
        self.assertEqual(self.icms.call_count, 1)
        self.assertEqual(self.contribuicoes.call_count, 1)

    def test_falha_troca_em_tela_desconhecida_nao_tenta_segunda_empresa(self):
        def trocar(codigo, *, prefixo):
            self.corresponde.return_value = False
            return False
        self.trocar.side_effect = trocar
        self.executar()
        self.assertEqual(self.trocar.call_count, 1)
        self.icms.assert_not_called()
        self.contribuicoes.assert_not_called()
        self.assertIn("lote interrompido", self.console.getvalue())

    def test_referencia_ilegivel_na_consulta_para_sem_acao(self):
        self.referencia.exists.side_effect = PermissionError
        self.executar()
        self.trocar.assert_not_called()
        self.icms.assert_not_called()
        self.d.interacao.focar_dominio.assert_not_called()
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()

    def test_entrada_aguarda_troca_de_foco_sem_clique_ou_esc(self):
        self.cabecalho.side_effect = [False, False] + [True] * 40
        self.executar()
        self.d.interacao._minimizar_console_proprio.assert_called_once_with()
        self.d.interacao.focar_dominio.assert_not_called()
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertEqual(self.trocar.call_count, 2)
        self.assertEqual(self.icms.call_count, 2)
        self.assertIn("Alt+Tab", self.console.getvalue())

    def test_entrada_sem_principal_termina_no_prazo_sem_acao_remota(self):
        self.cabecalho.return_value = False
        with patch.object(self.d.time, "monotonic", side_effect=[0, 16]):
            self.executar()
        self.trocar.assert_not_called()
        self.icms.assert_not_called()
        self.contribuicoes.assert_not_called()
        self.d.interacao.focar_dominio.assert_not_called()
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertIn("lote interrompido", self.console.getvalue())

    def test_entrada_sem_principal_tem_teto_de_tentativas_com_relogio_parado(self):
        self.cabecalho.return_value = False
        with patch.object(self.d.time, "monotonic", return_value=0):
            self.executar()
        self.assertEqual(self.cabecalho.call_count, 30)
        self.trocar.assert_not_called()
        self.icms.assert_not_called()

    def test_remocao_da_referencia_no_meio_do_lote_nao_rebaixa_para_legado(self):
        def gerar(*, prefixo):
            self.referencia.exists.return_value = False
            return True
        self.icms.side_effect = gerar
        self.executar()
        self.icms.assert_called_once_with(prefixo="9001_ICMS_")
        self.contribuicoes.assert_not_called()
        self.trocar.assert_called_once_with("9001", prefixo="9001_")
        self.d.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertNotIn("Lote sem referência", self.console.getvalue())
        self.assertIn("ICMS: sucesso, -: lote interrompido", self.console.getvalue())

    def test_segundo_erro_preserva_status_de_documentos_das_tentativas(self):
        self.empresas[:] = self.empresas[:1]
        self.contribuicoes.side_effect = RuntimeError("erro simulado")
        self.executar()
        self.assertEqual(self.icms.call_count, 2)
        self.assertEqual(self.contribuicoes.call_count, 2)
        self.assertEqual(self.d.interacao.pressionar_esc_repetidas.call_count, 2)
        self.assertIn("ICMS: sucesso, CONTRIBUICOES: erro inesperado na geração, -: erro inesperado, pulada após 1 tentativa", self.console.getvalue())


if __name__ == "__main__":
    unittest.main()
