"""Extensão por texto preserva hover de gravações antigas por coordenadas."""
import contextlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


class TestHoverRotina(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.desktop = {nome: Mock() for nome in ("dominio", "interacao", "registro_elementos", "tela")}
        self.desktop["dominio"].achar_ou_parar.return_value = (500, 150)
        self.stack.enter_context(patch.multiple("app", create=True, **self.desktop))
        arquivo = Path(__file__).resolve().parents[1] / "app" / "rotina_gravada.py"
        spec = importlib.util.spec_from_file_location("app.rotina_hover_teste", arquivo)
        self.modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.modulo)
        self.stack.enter_context(patch.object(self.modulo.time, "sleep"))

    def test_hover_antigo_preserva_coordenadas_gravadas(self):
        self.assertTrue(self.modulo.executar_passos([{"tipo": "hover", "indice": 1, "x": 200, "y": 80}]))
        self.desktop["interacao"].passar_mouse.assert_called_once_with(200, 80)
        self.desktop["dominio"].achar_ou_parar.assert_not_called()

    def test_hover_painel_exige_alvo_lido_no_quadro_atual(self):
        self.assertTrue(self.modulo.executar_passos([{"tipo": "hover", "indice": 1, "texto_adivinhado": "Livros"}]))
        self.desktop["interacao"].passar_mouse.assert_called_once_with(500, 150)

    def test_hover_sem_alvo_reconhecido_nao_move_mouse(self):
        self.desktop["dominio"].achar_ou_parar.return_value = None
        self.assertFalse(self.modulo.executar_passos([{"tipo": "hover", "indice": 1, "texto_adivinhado": "Livros"}]))
        self.desktop["interacao"].passar_mouse.assert_not_called()
