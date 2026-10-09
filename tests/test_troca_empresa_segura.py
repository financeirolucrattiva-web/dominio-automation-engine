"""Fluxo real da função F8 com desktop substituído, sem dados de clientes."""

import contextlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


class TestTrocaEmpresaSegura(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.desktop = {nome: Mock() for nome in (
            "arquivos", "empresas", "erros", "estados", "ia", "interacao",
            "tela", "tela_principal", "visao")}
        stack.enter_context(patch.multiple("app", create=True, **self.desktop))
        arquivo = Path(__file__).resolve().parents[1] / "app" / "dominio.py"
        spec = importlib.util.spec_from_file_location("app.dominio_troca_teste", arquivo)
        self.modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.modulo)
        stack.enter_context(patch.object(self.modulo.time, "sleep"))
        stack.enter_context(patch.object(self.modulo, "salvar"))

    def test_recuperacao_inconclusiva_nao_repete_f8_nem_digita(self):
        self.desktop["tela"].achar_texto_ou_no_centro.return_value = None
        recuperar = Mock(return_value=False)
        self.assertFalse(self.modulo.trocar_empresa("52", recuperar_inicio=recuperar))
        recuperar.assert_called_once_with()
        self.desktop["interacao"].pressionar_tecla.assert_called_once_with("f8")
        self.desktop["interacao"].pressionar_esc_repetidas.assert_not_called()
        self.desktop["interacao"].digitar.assert_not_called()
        self.desktop["interacao"].clicar.assert_not_called()

    def test_f8_so_e_repetido_apos_recuperacao_confirmada(self):
        self.desktop["tela"].achar_texto_ou_no_centro.side_effect = [None, (50, 60), None]
        def recuperar():
            # Até aqui ocorreu somente a primeira tentativa de abrir a troca.
            self.desktop["interacao"].pressionar_tecla.assert_called_once_with("f8")
            self.desktop["interacao"].digitar.assert_not_called()
            return True
        self.assertTrue(self.modulo.trocar_empresa("52", recuperar_inicio=recuperar))
        self.assertEqual(self.desktop["interacao"].pressionar_tecla.call_count, 2)
        self.desktop["interacao"].pressionar_esc_repetidas.assert_not_called()
        self.desktop["interacao"].digitar.assert_called_once_with("52")
        self.desktop["interacao"].clicar.assert_called_once_with(50, 60)


if __name__ == "__main__":
    unittest.main()
