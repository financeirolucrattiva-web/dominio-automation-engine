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
from app import capacidades, painel, trava_execucao


class TestResultadoGui(unittest.TestCase):
    def setUp(self):
        # Carrega a interface real, mas bloqueia os módulos que operam o
        # desktop. Nenhuma janela Tk é construída nem thread é iniciada.
        app = types.ModuleType("app")
        app.__path__ = []
        modulos = {"app": app}
        for nome in ("dominio", "empresas", "historico", "ia", "interacao", "verificacao", "estados", "rotina_gravada", "registro_elementos"):
            modulo = types.ModuleType(f"app.{nome}")
            setattr(app, nome, modulo)
            modulos[f"app.{nome}"] = modulo
        app.historico.registrar = Mock()
        app.estados.observar_eventos = lambda callback: contextlib.nullcontext()
        for nome, modulo in (("capacidades", capacidades), ("painel", painel), ("trava_execucao", trava_execucao)):
            setattr(app, nome, modulo)
            modulos[f"app.{nome}"] = modulo
        app.interacao.focar_dominio = Mock()
        gravar = types.ModuleType("gravar")
        gravar.Gravador = Mock()
        modulos["gravar"] = gravar
        arquivo = Path(__file__).resolve().parents[1] / "scripts" / "gui.py"
        spec = importlib.util.spec_from_file_location("gui_resultado_teste", arquivo)
        self.gui = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modulos), patch.object(sys, "path", list(sys.path)):
            spec.loader.exec_module(self.gui)
        contexto_trava = patch.object(self.gui, "TravaExecucao")
        contexto_trava.start()
        self.addCleanup(contexto_trava.stop)
        self.janela = self.gui.JanelaPrincipal.__new__(self.gui.JanelaPrincipal)
        self.janela.em_execucao = False
        self.janela._confirmar_empresa_selecionada = Mock(return_value=True)
        self.janela.root = Mock()
        self.janela.fila = queue.Queue()
        self.janela.fila_estados = queue.Queue()
        self.janela.painel = painel.EstadoPainel()
        self.janela._atualizar_painel = Mock()
        self.janela.evento_pausa = threading.Event()
        self.janela.botoes = []
        self.janela.botao_pausa = Mock()
        self.janela._marcar_status = Mock()
        self.janela._fim_execucao = Mock()
        self.janela.abas = Mock()
        self.janela._aba_log = object()
        self.janela._aba_painel = object()

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

    def test_cancelamento_nao_chama_backend_e_none_nao_confirma_sucesso(self):
        self.janela._confirmar_empresa_selecionada.return_value = False
        gerador = self.executar(False)
        gerador.assert_not_called()
        self.gui.interacao.focar_dominio.assert_not_called()
        self.gui.historico.registrar.assert_not_called()
        self.assertEqual(self.gui._normalizar_resultado(None, False), (None, None))

    def test_confirmacao_de_lote_minimiza_gui_antes_de_liberar_worker(self):
        eventos = []
        self.janela.root.iconify.side_effect = lambda: eventos.append("minimizou")
        original = self.janela.fila_estados.put
        def enfileirar(item):
            original(item)
            self.janela._processar_eventos()
        with patch.object(self.janela.fila_estados, "put", side_effect=enfileirar), patch.object(self.gui.messagebox, "askyesno", side_effect=lambda *args, **kwargs: eventos.append("confirmou") or True):
            resposta = self.janela._confirmar_lote([{"codigo": "9001", "apelido": "FICTICIA"}])
        self.assertTrue(resposta)
        self.assertEqual(eventos, ["confirmou", "minimizou"])
        self.janela.root.iconify.assert_called_once_with()
        self.janela.root.after.assert_not_called()

    def test_recusa_de_lote_nao_minimiza_gui(self):
        original = self.janela.fila_estados.put
        def enfileirar(item):
            original(item)
            self.janela._processar_eventos()
        with patch.object(self.janela.fila_estados, "put", side_effect=enfileirar), patch.object(self.gui.messagebox, "askyesno", return_value=False):
            resposta = self.janela._confirmar_lote([{"codigo": "9001", "apelido": "FICTICIA"}])
        self.assertFalse(resposta)
        self.janela.root.iconify.assert_not_called()

    def test_false_mostra_falha_no_painel_e_na_barra_de_status(self):
        self.janela._carregar_historico = Mock()
        self.gui.JanelaPrincipal._fim_execucao(self.janela, False, False)
        self.janela._marcar_status.assert_called_once_with("Falha — consulte a aba Log.", "danger")
        self.assertEqual(self.janela.painel.resultado, "Falhou; consulte o log")

    def test_eventos_do_worker_sao_enfileirados_sem_renderizar_na_thread(self):
        callback = {}
        @contextlib.contextmanager
        def observar(receber):
            callback["receber"] = receber
            yield
        evento = {"execution_id": "a" * 32, "routine_id": "sped_fiscal", "attempt": 1,
                  "step": "navegar_menu", "status": "inicio", "elapsed_seconds": 0, "evidence": None}
        def gerar():
            callback["receber"](evento)
            return False
        with patch.object(self.gui.estados, "observar_eventos", observar):
            self.executar(erro=gerar)
        self.assertEqual(self.janela.fila_estados.get_nowait(), evento)
        self.janela._atualizar_painel.assert_called_once_with()  # somente o início, na thread da GUI
        self.assertEqual(self.janela.fila_estados.get_nowait(), ("finalizar_atividade", False, False))
        self.janela.root.after.assert_not_called()

    def test_ferramenta_aberta_bloqueia_nova_automacao(self):
        self.janela.ferramenta_local = Mock()
        self.janela.ferramenta_local.poll.return_value = None
        with patch.object(self.gui.messagebox, "showwarning"):
            gerador = self.executar(False)
        gerador.assert_not_called()
        self.gui.historico.registrar.assert_not_called()

    def test_atividade_sem_estado_ou_resultado_nao_fica_rodando_no_painel(self):
        self.janela._carregar_historico = Mock()
        self.janela.painel.resultado = "Em execução"
        self.gui.JanelaPrincipal._fim_execucao(self.janela, False, None)
        self.assertEqual(self.janela.painel.resultado, "Atividade encerrada; consulte o log")
        self.janela._marcar_status.assert_called_once_with("Atividade encerrada; consulte os resultados no log.", "info")

    def test_finalizacao_passa_pela_fila_apos_os_eventos(self):
        self.janela.fila_estados.put({"execution_id": "a" * 32, "routine_id": "sped_fiscal", "attempt": 1,
                                     "step": "fim", "status": "falha", "elapsed_seconds": 1.5, "evidence": None})
        self.janela.fila_estados.put(("finalizar_atividade", False, False))
        self.janela._processar_eventos()
        self.assertEqual(self.janela.painel.resultado, "Falhou")
        self.janela._fim_execucao.assert_called_once_with(False, False)

    def test_falha_de_gravacao_nao_perde_finalizacao_ou_resultado(self):
        self.gui.historico.registrar.side_effect = OSError("histórico indisponível")
        self.executar(False)
        self.assertEqual(self.janela.fila_estados.get_nowait(), ("finalizar_atividade", False, False))
        self.assertIn("Não foi possível gravar o histórico", "".join(self.janela.fila.queue))

    def test_atividade_sem_resultado_nao_registra_ok(self):
        self.executar(None)
        self.gui.historico.registrar.assert_called_once_with("SPED Fiscal", None, arquivo_gerado=None)
        self.assertEqual(self.janela.fila_estados.get_nowait(), ("finalizar_atividade", False, None))

    def test_resultado_malformado_nao_e_convertido_em_sucesso(self):
        for resultado in (("sim", "qualquer.pdf"), (1, None), {}, "OK", 1):
            with self.subTest(resultado=resultado):
                self.assertEqual(self.gui._normalizar_resultado(resultado, False), (None, None))

    def test_historico_corrompido_nao_perde_finalizacao(self):
        self.gui.historico.registrar.side_effect = ValueError("formato inválido")
        self.executar(False)
        self.assertEqual(self.janela.fila_estados.get_nowait(), ("finalizar_atividade", False, False))

    def test_fechar_durante_execucao_preserva_worker(self):
        self.janela.em_execucao = True
        with patch.object(self.gui.messagebox, "showwarning") as aviso:
            self.janela._solicitar_fechar()
        aviso.assert_called_once()
        self.janela.root.destroy.assert_not_called()

    def test_fechar_sem_atividade_destroi_janela(self):
        self.janela._solicitar_fechar()
        self.janela.root.destroy.assert_called_once_with()

    def test_arquivo_nao_toma_foco_durante_execucao(self):
        self.janela.em_execucao = True
        with patch.object(self.gui, "_abrir_no_explorador") as abrir, patch.object(self.gui.messagebox, "showwarning"):
            self.janela._abrir_caminho(Path("simulado.pdf"))
        abrir.assert_not_called()

    def test_excecao_apos_eventos_nao_deixa_painel_com_sucesso(self):
        self.janela._carregar_historico = Mock()
        self.janela.painel.receber({"execution_id": "a" * 32, "routine_id": "sped_fiscal", "attempt": 1,
                                     "step": "fim", "status": "concluido", "elapsed_seconds": 1.5, "evidence": None})
        self.gui.JanelaPrincipal._fim_execucao(self.janela, True, False)
        self.assertEqual(self.janela.painel.resultado, "Falhou; consulte o log")

    def test_thread_nao_iniciada_libera_interface_sem_operar_dominio(self):
        gerador = Mock()
        with patch.object(self.gui.threading, "Thread", side_effect=RuntimeError("sem thread")):
            self.janela._rodar_em_thread(gerador, nome_rotina="Teste")
        gerador.assert_not_called()
        self.janela._fim_execucao.assert_called_once_with(True, False)

    def test_historico_invalido_nao_impede_carregamento_da_gui(self):
        self.gui.historico.carregar = Mock(side_effect=ValueError("dados privados"))
        self.janela.tabela_historico = Mock()
        self.janela.tabela_historico.get_children.return_value = []
        self.janela._log = Mock()
        self.janela._carregar_historico()
        self.janela.tabela_historico.insert.assert_not_called()
        self.assertNotIn("dados privados", self.janela._log.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
