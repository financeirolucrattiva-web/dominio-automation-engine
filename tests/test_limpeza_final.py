import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import dominio

JANELA = {"hwnd": 1, "pid": 2, "classe": "DisplayClientWindowClass", "titulo": ""}
OK = "tela_principal_reconhecida"
NAO = "tela_principal_nao_reconhecida"


class TestVoltarAoInicio(unittest.TestCase):
    def setUp(self):
        self.interacao = Mock()
        self.interacao.identificar_janela_dominio_atual.return_value = JANELA
        self.interacao.janela_dominio_em_foco.return_value = True
        self.interacao.pressionar_esc_no_dominio.return_value = True
        self.tp = Mock()
        self.tp.carregar_referencia.return_value = {"ref": 1}
        self.tela = Mock()
        self.tela.achar_texto.return_value = None
        self.verificar = Mock(return_value=OK)
        for alvo, valor in (("interacao", self.interacao), ("tela_principal", self.tp), ("tela", self.tela),
                            ("_verificar_retorno_tela_principal", self.verificar)):
            patcher = patch.object(dominio, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(dominio.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ja_na_tela_principal_nao_envia_nada(self):
        self.assertTrue(dominio.voltar_ao_inicio())
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()

    def test_esc_um_por_vez_ate_reconhecer(self):
        self.verificar.side_effect = [NAO, NAO, OK]
        self.assertTrue(dominio.voltar_ao_inicio())
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 2)

    def test_sem_referencia_nao_envia_teclas_as_cegas(self):
        self.tp.carregar_referencia.return_value = None
        self.assertFalse(dominio.voltar_ao_inicio())
        self.interacao.pressionar_esc_no_dominio.assert_not_called()

    def test_sem_janela_identificada_nao_age(self):
        self.interacao.identificar_janela_dominio_atual.return_value = None
        self.assertFalse(dominio.voltar_ao_inicio())
        self.interacao.pressionar_esc_no_dominio.assert_not_called()

    def test_escala_para_botao_fechar_depois_dos_esc(self):
        self.verificar.side_effect = [NAO] * 6 + [OK]
        self.tela.achar_texto.return_value = (50, 60)
        self.assertTrue(dominio.voltar_ao_inicio())
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 5)
        self.interacao.clicar.assert_called_once_with(50, 60)
        self.interacao.pressionar_atalho.assert_not_called()

    def test_sem_botao_fechar_usa_ctrl_f4_e_nunca_alt_f4(self):
        self.verificar.side_effect = [NAO] * 6 + [OK]
        self.assertTrue(dominio.voltar_ao_inicio())
        self.interacao.pressionar_atalho.assert_called_once_with("ctrl", "f4")

    def test_nunca_alt_f4_mesmo_esgotando_tentativas(self):
        self.verificar.return_value = NAO
        self.assertFalse(dominio.voltar_ao_inicio())
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 5)
        self.assertEqual(self.interacao.pressionar_atalho.call_count, 3)
        for chamada in self.interacao.pressionar_atalho.call_args_list:
            self.assertNotIn("alt", chamada.args)

    def test_foco_perdido_interrompe_sem_enviar_mais(self):
        self.verificar.return_value = NAO
        self.interacao.pressionar_esc_no_dominio.return_value = False
        self.assertFalse(dominio.voltar_ao_inicio())
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 1)

    def test_fechar_aba_sem_foco_nao_envia(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        self.assertFalse(dominio.fechar_aba_ativa(JANELA))
        self.interacao.clicar.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()

    def test_limpar_ao_encerrar_pula_se_recuperacao_ja_confirmou(self):
        rotina = SimpleNamespace(janela_dominio=JANELA, eventos=[
            {"step": "recuperar_interface", "status": "confirmado"}])
        self.assertTrue(dominio._limpar_ao_encerrar(rotina))
        self.verificar.assert_not_called()

    def test_limpar_ao_encerrar_falha_nao_levanta(self):
        self.verificar.side_effect = RuntimeError("falha qualquer")
        self.assertFalse(dominio._limpar_ao_encerrar(SimpleNamespace(janela_dominio=JANELA, eventos=[])))


if __name__ == "__main__":
    unittest.main()
