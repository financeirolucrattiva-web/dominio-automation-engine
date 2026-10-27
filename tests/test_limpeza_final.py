import unittest
import importlib.util
from pathlib import Path
import types
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao

with patch('ctypes.windll', Mock(), create=True), patch.dict('sys.modules', {'app.interacao': types.ModuleType('app.interacao')}):
    spec = importlib.util.spec_from_file_location('app._limpeza_teste', Path(__file__).resolve().parents[1]/'app/dominio.py')
    dominio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dominio)

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

    def test_esc_que_nao_muda_a_tela_escala_cedo_para_fechar_a_aba(self):
        from PIL import Image
        self.tela.capturar_tela.return_value = Image.new("RGB", (96, 54), "blue")
        self.verificar.return_value = NAO
        fechar = Mock(return_value=True)
        with patch.object(dominio, "fechar_aba_ativa", fechar):
            self.assertFalse(dominio.voltar_ao_inicio(JANELA))
        self.assertLessEqual(self.interacao.pressionar_esc_no_dominio.call_count, 4)
        self.assertEqual(fechar.call_count, 3)  # o limite de fechamentos continua valendo

    def test_ja_na_tela_principal_nao_envia_nada(self):
        self.assertTrue(dominio.voltar_ao_inicio())
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_not_called()

    def test_leitor_remoto_na_frente_recupera_hwnd_principal_antes_do_esc(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        self.interacao.janela_dominio_ou_remota_em_foco.return_value = True
        self.verificar.side_effect = [NAO, OK]
        ordem = []

        def recuperar(janela):
            self.assertEqual(janela, JANELA)
            ordem.append("recuperar")
            self.interacao.janela_dominio_em_foco.return_value = True
            return True

        self.interacao.voltar_ao_dominio_com_alt_tab.side_effect = recuperar
        self.interacao.pressionar_esc_no_dominio.side_effect = lambda *a, **kw: ordem.append("esc") or True
        self.assertTrue(dominio.voltar_ao_inicio(JANELA))
        self.assertEqual(ordem, ["recuperar", "esc"])
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_called_once_with(JANELA)

    def test_sobe_com_esc_ate_oito_telas_depois_de_fechar_o_adobe(self):
        self.verificar.side_effect = [NAO] * 8 + [OK]
        self.assertTrue(dominio.voltar_ao_inicio(JANELA))
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 8)

    def test_recuperacao_de_foco_falha_nao_envia_esc_nem_fecha_aba(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        self.interacao.janela_dominio_ou_remota_em_foco.return_value = True
        self.interacao.voltar_ao_dominio_com_alt_tab.return_value = False
        self.assertFalse(dominio.voltar_ao_inicio(JANELA))
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_called_once_with(JANELA)
        self.verificar.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.clicar.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()

    def test_helper_positivo_sem_foco_estrito_nao_autoriza_limpeza(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        self.interacao.janela_dominio_ou_remota_em_foco.return_value = True
        self.interacao.voltar_ao_dominio_com_alt_tab.return_value = True
        self.assertFalse(dominio.voltar_ao_inicio(JANELA))
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_called_once_with(JANELA)
        self.verificar.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.clicar.assert_not_called()

    def test_cancelamento_na_recuperacao_e_propagado_sem_esc(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        self.interacao.janela_dominio_ou_remota_em_foco.return_value = True
        self.interacao.voltar_ao_dominio_com_alt_tab.side_effect = ExecucaoInterrompida("teste")
        with self.assertRaises(ExecucaoInterrompida):
            dominio.voltar_ao_inicio(JANELA)
        self.verificar.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.clicar.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()

    def test_cancelamento_previo_impede_ativacao_e_limpeza(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        controle = ControleExecucao()
        controle.interromper("teste")
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            dominio.voltar_ao_inicio(JANELA)
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.clicar.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()

    def test_cancelamento_entre_passos_impede_segundo_esc(self):
        controle = ControleExecucao()
        self.verificar.return_value = NAO

        def primeiro_esc(*args, **kwargs):
            controle.interromper("teste")
            return True

        self.interacao.pressionar_esc_no_dominio.side_effect = primeiro_esc
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            dominio.voltar_ao_inicio(JANELA)
        self.interacao.pressionar_esc_no_dominio.assert_called_once()
        self.interacao.clicar.assert_not_called()
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
        self.verificar.side_effect = [NAO] * 13 + [OK]
        self.tela.achar_texto.return_value = (50, 60)
        self.assertTrue(dominio.voltar_ao_inicio())
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 12)
        self.interacao.clicar.assert_called_once_with(50, 60)
        self.interacao.pressionar_atalho.assert_not_called()

    def test_sem_botao_fechar_usa_ctrl_f4_e_nunca_alt_f4(self):
        self.verificar.side_effect = [NAO] * 13 + [OK]
        self.assertTrue(dominio.voltar_ao_inicio())
        self.interacao.pressionar_atalho.assert_called_once_with("ctrl", "f4")

    def test_nunca_alt_f4_mesmo_esgotando_tentativas(self):
        self.verificar.return_value = NAO
        self.assertFalse(dominio.voltar_ao_inicio())
        self.assertEqual(self.interacao.pressionar_esc_no_dominio.call_count, 12)
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

    def test_limpar_ao_encerrar_reconfirma_mesmo_apos_recuperacao(self):
        rotina = SimpleNamespace(janela_dominio=JANELA, eventos=[
            {"step": "recuperar_interface", "status": "confirmado"}])
        self.assertTrue(dominio._limpar_ao_encerrar(rotina))
        self.verificar.assert_called_once()

    def test_limpar_ao_encerrar_falha_nao_levanta(self):
        self.verificar.side_effect = RuntimeError("falha qualquer")
        self.assertFalse(dominio._limpar_ao_encerrar(SimpleNamespace(janela_dominio=JANELA, eventos=[])))

    def test_linha_base_indisponivel_nao_equivale_a_nenhum_leitor_aberto(self):
        self.interacao.listar_leitores_pdf.side_effect = OSError("inventario indisponivel")
        self.assertIsNone(dominio._linha_base_leitores_pdf())
        self.interacao.fechar_leitores_pdf_novos.assert_not_called()
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_not_called()

    def test_cancelamento_no_inventario_de_leitores_e_propagado(self):
        self.interacao.listar_leitores_pdf.side_effect = ExecucaoInterrompida("teste")
        with self.assertRaises(ExecucaoInterrompida):
            dominio._linha_base_leitores_pdf()
        self.interacao.fechar_leitores_pdf_novos.assert_not_called()

    def test_cancelamento_no_fechamento_pdf_nao_tenta_alt_tab_depois(self):
        self.interacao.fechar_leitores_pdf_novos.side_effect = ExecucaoInterrompida("teste")
        with self.assertRaises(ExecucaoInterrompida):
            dominio._fechar_leitores_pdf({}, JANELA)
        self.interacao.fechar_leitores_pdf_novos.assert_called_once_with({})
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()

    def test_cancelamento_antes_do_fechamento_pdf_nao_envia_acao(self):
        controle = ControleExecucao()
        controle.interromper("teste")
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            dominio._fechar_leitores_pdf({}, JANELA)
        self.interacao.fechar_leitores_pdf_novos.assert_not_called()
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()

    def test_cancelamento_ao_retornar_do_pdf_nao_e_ocultado(self):
        self.interacao.voltar_ao_dominio_com_alt_tab.side_effect = ExecucaoInterrompida("teste")
        with self.assertRaises(ExecucaoInterrompida):
            dominio._fechar_leitores_pdf({}, JANELA)
        self.interacao.fechar_leitores_pdf_novos.assert_called_once_with({})
        self.interacao.voltar_ao_dominio_com_alt_tab.assert_called_once_with(JANELA)
        self.interacao.pressionar_esc_no_dominio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
