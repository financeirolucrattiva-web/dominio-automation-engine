"""Calibração com capturas sintéticas; nenhuma chamada à UI Windows."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw
from app import tela_principal

spec = importlib.util.spec_from_file_location("_calibracao_teste", Path(__file__).resolve().parents[1] / "scripts" / "calibrar_tela_principal.py")
calibracao = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibracao)


class TestCalibracao(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = Path(self.pasta.name) / "referencia.json"
        self.imagem = Image.new("RGB", (100, 100), "#dddddd")
        ImageDraw.Draw(self.imagem).rectangle((0, 10, 94, 89), fill="#2a5daa")
        self.janela = {"hwnd": 123, "pid": 456}
        self.capturar = Mock(return_value=self.imagem)
        self.identificar = Mock(return_value=self.janela)
        self.foco = Mock(return_value=True)
        self.cabecalho = Mock(return_value=True)
        patcher = patch.object(calibracao.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def executar(self):
        return calibracao.calibrar(self.capturar, self.identificar, self.foco, self.cabecalho, self.caminho)

    def test_grava_apenas_medidas_apos_duas_capturas(self):
        referencia = self.executar()
        self.assertEqual(self.capturar.call_count, 2)
        self.assertEqual(self.cabecalho.call_count, 2)
        self.assertEqual(tela_principal.carregar_referencia(self.caminho), referencia)
        self.assertEqual(set(referencia), {"versao", "tamanho", "retangulo", "cor_rgb"})
        self.assertEqual([p.name for p in self.caminho.parent.iterdir()], [self.caminho.name])

    def test_segunda_captura_com_dialogo_preserva_referencia(self):
        self.executar()
        original = self.caminho.read_bytes()
        com_dialogo = self.imagem.copy()
        ImageDraw.Draw(com_dialogo).rectangle((40, 40, 50, 50), fill="white")
        self.capturar.side_effect = [self.imagem, com_dialogo]
        with self.assertRaises(ValueError):
            self.executar()
        self.assertEqual(self.caminho.read_bytes(), original)

    def test_perda_foco_no_fim_nao_salva(self):
        self.foco.side_effect = [True, True, True, True, True, False]
        with self.assertRaises(ValueError):
            self.executar()
        self.assertFalse(self.caminho.exists())

    def test_cabecalho_ausente_nao_salva(self):
        self.cabecalho.return_value = False
        with self.assertRaises(ValueError):
            self.executar()
        self.assertFalse(self.caminho.exists())

    def test_janela_desconhecida_nao_captura(self):
        self.identificar.return_value = None
        with self.assertRaises(ValueError):
            self.executar()
        self.capturar.assert_not_called()
        self.assertFalse(self.caminho.exists())

    def test_aguarda_selecao_da_janela_sem_capturar_outro_programa(self):
        self.identificar.side_effect = [None, None, self.janela]
        self.assertTrue(calibracao.aguardar_dominio(self.capturar, self.identificar, self.foco, self.cabecalho))
        self.capturar.assert_called_once()
        self.assertFalse(self.caminho.exists())

    def test_espera_limitada_se_nao_selecionar_dominio(self):
        self.identificar.return_value = None
        self.assertFalse(calibracao.aguardar_dominio(self.capturar, self.identificar, self.foco, self.cabecalho, tentativas=3))
        self.assertEqual(self.identificar.call_count, 3)
        self.capturar.assert_not_called()

    def test_foco_perdido_apos_cabecalho_nao_libera_calibracao(self):
        self.foco.side_effect = [True, False]
        self.assertFalse(calibracao.aguardar_dominio(self.capturar, self.identificar, self.foco, self.cabecalho, tentativas=1))
        self.assertFalse(self.caminho.exists())


if __name__ == "__main__":
    unittest.main()
