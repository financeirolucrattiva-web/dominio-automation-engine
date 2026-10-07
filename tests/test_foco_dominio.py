"""Win32 simulado: foco confirmado sem clicar nem alcançar UI real."""

import ctypes
from ctypes import wintypes
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch


def carregar_interacao():
    spec = importlib.util.spec_from_file_location("app._interacao_teste", Path(__file__).resolve().parents[1] / "app" / "interacao.py")
    modulo = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", {"pyautogui": types.ModuleType("pyautogui")}):
        spec.loader.exec_module(modulo)
    return modulo


class TestFocoDominio(unittest.TestCase):
    def setUp(self):
        self.modulo = carregar_interacao()
        self.janelas = {
            42: {"titulo": "Domínio Escrita Fiscal - Versão: 10", "classe": "DisplayClientWindowClass", "pid": 100},
            99: {"titulo": "exportacao_ficticia.pdf - Adobe Acrobat", "classe": "AcrobatWindow", "pid": 200},
        }
        self.foreground = 99
        self.api = Mock()
        self.api.IsWindow.side_effect = lambda hwnd: hwnd in self.janelas
        self.api.IsWindowVisible.return_value = True
        self.api.IsIconic.return_value = False
        self.api.GetForegroundWindow.side_effect = lambda: self.foreground
        self.api.GetWindowTextW.side_effect = lambda hwnd, buffer, tamanho: setattr(buffer, "value", self.janelas[hwnd]["titulo"])
        self.api.GetClassNameW.side_effect = lambda hwnd, buffer, tamanho: setattr(buffer, "value", self.janelas[hwnd]["classe"])
        self.api.GetWindowThreadProcessId.side_effect = lambda hwnd, pid: setattr(pid._obj, "value", self.janelas[hwnd]["pid"])

        def enumerar(callback, parametro):
            for hwnd in list(self.janelas):
                callback(hwnd, parametro)
            return True

        def ativar(hwnd):
            self.foreground = hwnd
            return True

        self.api.EnumWindows.side_effect = enumerar
        self.api.SetForegroundWindow.side_effect = ativar
        self.press = Mock()
        self.patchers = [
            patch.object(self.modulo, "_api_janelas", return_value=(self.api, lambda callback: callback)),
            patch.object(self.modulo, "pressionar_tecla", self.press),
            patch.object(self.modulo.time, "sleep"),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def token(self, hwnd=42):
        return dict(self.janelas[hwnd], hwnd=hwnd)

    def test_titulo_unico_retoma_dominio_sem_teclas_no_acrobat(self):
        self.assertTrue(self.modulo.pressionar_esc_no_dominio())
        self.api.SetForegroundWindow.assert_called_once_with(42)
        self.assertEqual(self.press.call_count, 2)
        self.press.assert_called_with("esc")

    def test_hwnd_vinculado_ao_checkpoint_aceita_titulo_vazio(self):
        self.janelas[42]["titulo"] = ""
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=lambda: True))
        self.assertEqual(self.press.call_count, 2)

    def test_classe_sozinha_sem_checkpoint_nao_autoriza_foco(self):
        self.janelas[42]["titulo"] = ""
        self.assertFalse(self.modulo.pressionar_esc_no_dominio())
        self.api.SetForegroundWindow.assert_not_called()
        self.press.assert_not_called()

    def test_janelas_elegiveis_ambiguas_nao_agir(self):
        self.janelas[43] = dict(self.janelas[42], pid=101)
        for token in (None, self.token()):
            self.assertFalse(self.modulo.pressionar_esc_no_dominio(token))
        self.api.SetForegroundWindow.assert_not_called()
        self.press.assert_not_called()

    def test_setforeground_falha_nao_envia_esc(self):
        self.api.SetForegroundWindow.side_effect = None
        self.api.SetForegroundWindow.return_value = False
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_not_called()

    def test_foco_perdido_entre_esc_interrompe_segunda_tecla(self):
        self.press.side_effect = lambda _: setattr(self, "foreground", 99)
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_called_once_with("esc")

    def test_hwnd_pid_classe_titulo_incompativeis_sem_fallback(self):
        token = self.token()
        for chave, valor in (("hwnd", 88), ("pid", 999), ("classe", "OutraClasse"), ("titulo", "")):
            invalido = dict(token, **{chave: valor})
            self.assertFalse(self.modulo.pressionar_esc_no_dominio(invalido))
        self.api.SetForegroundWindow.assert_not_called()
        self.press.assert_not_called()

    def test_captura_token_apenas_foreground_compativel_no_checkpoint(self):
        self.assertIsNone(self.modulo.identificar_janela_dominio_atual())
        self.foreground = 42
        self.janelas[42]["titulo"] = ""
        self.assertEqual(self.modulo.identificar_janela_dominio_atual(), self.token())

    def test_titulo_outro_app_na_classe_go_global_nao_vincula_checkpoint(self):
        self.foreground = 42
        self.janelas[42]["titulo"] = "Adobe Acrobat"
        self.assertIsNone(self.modulo.identificar_janela_dominio_atual())

    def test_go_global_sem_confirmacao_ocr_nao_envia_teclas(self):
        self.janelas[42]["titulo"] = ""
        ocr = Mock(return_value=False)
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=ocr))
        self.assertEqual(ocr.call_count, 3)
        self.press.assert_not_called()

    def test_go_global_ocr_confirma_apos_repintar_e_por_tecla(self):
        self.janelas[42]["titulo"] = ""
        ocr = Mock(side_effect=[False, False, True, True])
        self.assertTrue(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=ocr))
        self.assertEqual(ocr.call_count, 4)
        self.assertEqual(self.press.call_count, 2)

    def test_titulo_muda_antes_segunda_tecla_interrompe(self):
        self.press.side_effect = lambda _: self.janelas[42].update(titulo="Adobe Acrobat")
        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token()))
        self.press.assert_called_once_with("esc")

    def test_ocr_muda_foco_nao_envia_esc(self):
        self.janelas[42]["titulo"] = ""

        def ocr():
            self.foreground = 99
            return True

        self.assertFalse(self.modulo.pressionar_esc_no_dominio(self.token(), confirmar_conteudo=ocr))
        self.press.assert_not_called()

    def test_verificacao_foreground_apenas_leitura(self):
        self.assertFalse(self.modulo.janela_dominio_em_foco(self.token()))
        self.foreground = 42
        self.assertTrue(self.modulo.janela_dominio_em_foco(self.token()))
        self.api.SetForegroundWindow.assert_not_called()
        self.api.EnumWindows.assert_not_called()
        self.api.ShowWindow.assert_not_called()
        self.press.assert_not_called()


class TestTiposWin32(unittest.TestCase):
    def test_hwnd_retornos_e_argumentos_tipos_pointer(self):
        modulo = carregar_interacao()
        api = Mock()
        with patch("ctypes.windll", types.SimpleNamespace(user32=api), create=True):
            modulo._api_janelas()
        self.assertIs(api.GetForegroundWindow.restype, wintypes.HWND)
        self.assertEqual(api.SetForegroundWindow.argtypes, [wintypes.HWND])
        self.assertEqual(ctypes.sizeof(api.GetForegroundWindow.restype), ctypes.sizeof(ctypes.c_void_p))


if __name__ == "__main__":
    unittest.main()
