"""Resultado de SPED passa pelo callback, normalização e histórico sem Tk."""

import contextlib
import importlib.util
import io
from pathlib import Path
import queue
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch


class TestResultadoGui(unittest.TestCase):
    def setUp(self):
        # Carrega a interface real, mas bloqueia os módulos que operam o
        # desktop. Nenhuma janela Tk é construída nem thread é iniciada.
        app = types.ModuleType("app")
        app.__path__ = []
        modulos = {"app": app}
        for nome in ("dominio", "empresas", "historico", "ia", "interacao", "verificacao"):
            modulo = types.ModuleType(f"app.{nome}")
            setattr(app, nome, modulo)
            modulos[f"app.{nome}"] = modulo
        app.historico.registrar = Mock()
        app.interacao.focar_dominio = Mock()
        gravar = types.ModuleType("gravar")
        gravar.Gravador = Mock()
        modulos["gravar"] = gravar
        arquivo = Path(__file__).resolve().parents[1] / "scripts" / "gui.py"
        spec = importlib.util.spec_from_file_location("gui_resultado_teste", arquivo)
        self.gui = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modulos), patch.object(sys, "path", list(sys.path)):
            spec.loader.exec_module(self.gui)
        self.janela = self.gui.JanelaPrincipal.__new__(self.gui.JanelaPrincipal)
        self.janela.em_execucao = False
        self.janela._confirmar_empresa_selecionada = Mock(return_value=True)
        self.janela.root = Mock()
        self.janela.fila = queue.Queue()
        self.janela.evento_pausa = threading.Event()
        self.janela.botoes = []
        self.janela.botao_pausa = Mock()
        self.janela._marcar_status = Mock()
        self.janela._fim_execucao = Mock()
        self.janela.abas = Mock()
        self.janela._aba_log = object()

    def executar(self, resultado=None, erro=None):
        gerador = Mock(return_value=resultado, side_effect=erro)
        # start() roda o trabalho de _rodar_em_thread sincronamente;
        # callback e normalização são reais; a gravação é observada pelo mock.
        def thread_sincrona(*, target, daemon):
            return types.SimpleNamespace(start=target)

        with contextlib.redirect_stdout(io.StringIO()):
            with patch.object(self.gui.threading, "Thread", side_effect=thread_sincrona):
                with patch.object(Path, "open", return_value=io.StringIO()):
                    with patch.object(Path, "mkdir"):
                        self.janela._rodar_gerador(gerador, "SPED Fiscal")
        return gerador

    def test_false_do_gerador_permanece_falha_no_historico(self):
        gerador = self.executar(False)
        gerador.assert_called_once_with()
        self.gui.historico.registrar.assert_called_once_with("SPED Fiscal", False, arquivo_gerado=None)
        self.gui.interacao.focar_dominio.assert_called_once_with()
        mensagens = "".join(self.janela.fila.queue)
        self.assertNotIn("Fim da rotina", mensagens)

    def test_true_do_gerador_permanece_sucesso_no_historico(self):
        self.executar(True)
        self.gui.historico.registrar.assert_called_once_with("SPED Fiscal", True, arquivo_gerado=None)
        self.assertIn("Fim da rotina (SPED Fiscal).", "".join(self.janela.fila.queue))

    def test_excecao_do_gerador_permanece_falha_no_historico(self):
        self.executar(erro=RuntimeError("Falha simulada"))
        self.gui.historico.registrar.assert_called_once_with("SPED Fiscal", False, arquivo_gerado=None)
        self.assertIn("Erro inesperado", "".join(self.janela.fila.queue))

    def test_cancelamento_nao_chama_backend_e_normalizacao_none_preservada(self):
        self.janela._confirmar_empresa_selecionada.return_value = False
        gerador = self.executar(False)
        gerador.assert_not_called()
        self.gui.interacao.focar_dominio.assert_not_called()
        self.gui.historico.registrar.assert_not_called()
        self.assertEqual(self.gui._normalizar_resultado(None, False), (True, None))

    def test_confirmacao_de_lote_minimiza_gui_antes_de_liberar_worker(self):
        eventos = []
        self.janela.root.after.side_effect = lambda atraso, callback: callback()
        self.janela.root.iconify.side_effect = lambda: eventos.append("minimizou")
        with patch.object(self.gui.messagebox, "askyesno", side_effect=lambda *args, **kwargs: eventos.append("confirmou") or True):
            resposta = self.janela._confirmar_lote([{"codigo": "9001", "apelido": "FICTICIA"}])
        self.assertTrue(resposta)
        self.assertEqual(eventos, ["confirmou", "minimizou"])
        self.janela.root.iconify.assert_called_once_with()

    def test_recusa_de_lote_nao_minimiza_gui(self):
        self.janela.root.after.side_effect = lambda atraso, callback: callback()
        with patch.object(self.gui.messagebox, "askyesno", return_value=False):
            resposta = self.janela._confirmar_lote([{"codigo": "9001", "apelido": "FICTICIA"}])
        self.assertFalse(resposta)
        self.janela.root.iconify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
