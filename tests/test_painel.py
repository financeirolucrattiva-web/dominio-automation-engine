"""Estados apresentados pela GUI preservam evidência, falha e tentativa."""

import contextlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import painel
with patch("ctypes.windll", Mock(), create=True):
    from app import estados


def evento(etapa="navegar_menu", status="inicio", **extras):
    dados = {"execution_id": "a" * 32, "routine_id": "sped_fiscal", "attempt": 1,
             "step": etapa, "status": status, "elapsed_seconds": 1.5, "evidence": None}
    dados.update(extras)
    return dados


class TestModeloPainel(unittest.TestCase):
    def setUp(self):
        self.modelo = painel.EstadoPainel()

    def test_acao_enviada_nao_confirma_retorno_ou_cem_por_cento(self):
        for etapa in painel.ETAPAS_GERACAO[:-1]:
            self.modelo.receber(evento(etapa, "confirmado"))
        self.modelo.receber(evento("encerrar", "acao_executada", evidence="fechamento_solicitado"))
        self.modelo.receber(evento("fim", "concluido"))
        self.assertEqual(self.modelo.confirmadas, 4)
        self.assertEqual(len(self.modelo.etapas), 5)
        self.assertEqual(self.modelo.retorno, "Ação enviada; retorno não verificado")
        self.assertEqual(self.modelo.resultado, "Concluído pela rotina")

    def test_confirmacao_visual_exige_marcador_especifico(self):
        self.assertFalse(self.modelo.receber(evento("encerrar", "confirmado")))
        self.assertTrue(self.modelo.receber(evento("encerrar", "confirmado", evidence="tela_principal_reconhecida")))
        self.assertEqual(self.modelo.retorno, "Tela principal confirmada")

    def test_falha_permanece_falha_apos_recuperacao_confirmada(self):
        self.modelo.receber(evento("conferir_pdf", "falha", routine_id="registro_saidas"))
        self.modelo.receber(evento("recuperar_interface", "confirmado", routine_id="registro_saidas",
                                   evidence="tela_principal_reconhecida"))
        self.modelo.receber(evento("fim", "falha", routine_id="registro_saidas"))
        self.assertEqual(self.modelo.resultado, "Falhou")
        self.assertEqual(self.modelo.retorno, "Tela principal confirmada")
        self.assertEqual(self.modelo.confirmadas, 0)

    def test_retry_e_proxima_empresa_nao_reaproveitam_confirmacoes(self):
        self.modelo.receber(evento("navegar_menu", "confirmado"))
        self.modelo.receber(evento(attempt=2))
        self.assertEqual(self.modelo.confirmadas, 0)
        self.assertEqual(self.modelo.tentativa, 2)
        self.modelo.receber(evento("navegar_menu", "confirmado", attempt=2))
        self.modelo.receber(evento(execution_id="b" * 32))
        self.assertEqual(self.modelo.confirmadas, 0)
        self.assertEqual(self.modelo.tentativa, 1)

    def test_evento_invalido_ignorado_sem_expor_dados(self):
        for extras in ({"routine_id": []}, {"routine_id": "EMPRESA PRIVADA"}, {"step": "campo privado"},
                       {"status": "sucesso inventado"}, {"execution_id": "cliente"},
                       {"elapsed_seconds": float("nan")}, {"attempt": True}):
            with self.subTest(extras=extras):
                self.assertFalse(self.modelo.receber(evento(**extras)))
        self.assertIsNone(self.modelo.execution_id)

    def test_etapas_correspondem_ao_acompanhamento_real(self):
        self.assertEqual(painel.ETAPAS_LIVROS, estados.AcompanhamentoRotina.ETAPAS)
        self.assertEqual(painel.ETAPAS_GERACAO, tuple(estados.AcompanhamentoRotina.FLUXO_GERACAO))


class TestObservadorEstados(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.console = contextlib.redirect_stdout(io.StringIO())
        self.console.__enter__()
        self.addCleanup(self.console.__exit__, None, None, None)

    def rotina(self):
        return estados.AcompanhamentoRotina("sped_fiscal", self.pasta.name)

    def test_recebe_copia_sem_modificar_evento_ou_log(self):
        recebidos = []
        def observar(ev):
            recebidos.append(ev)
            ev["status"] = "alterado"
        rotina = self.rotina()
        with estados.observar_eventos(observar):
            rotina.iniciar("navegar_menu")
        self.assertEqual(len(recebidos), 1)
        self.assertEqual(rotina.eventos[0]["status"], "inicio")
        self.assertNotIn("alterado", rotina.caminho_log.read_text())

    def test_falha_da_exibicao_nao_interrompe_rotina_e_contexto_e_restaurado(self):
        rotina = self.rotina()
        observador = Mock(side_effect=RuntimeError("exibição"))
        with estados.observar_eventos(observador):
            rotina.iniciar("navegar_menu")
        rotina.confirmar("item_menu_reconhecido")
        observador.assert_called_once()
        self.assertEqual(rotina.confirmadas, ["navegar_menu"])

    def test_observador_nao_recebe_eventos_de_outra_thread(self):
        observador = Mock()
        with estados.observar_eventos(observador):
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(self.rotina().iniciar, "navegar_menu").result()
        observador.assert_not_called()


class TestAbrirFerramenta(unittest.TestCase):
    def carregar(self):
        arquivo = Path(__file__).resolve().parents[1] / "scripts" / "abrir_ferramenta.py"
        spec = importlib.util.spec_from_file_location("abrir_ferramenta_teste", arquivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def test_conserva_codigo_e_prompt_ate_operador_ler(self):
        modulo = self.carregar()
        anterior = modulo.sys.argv
        with patch.object(modulo.runpy, "run_path", side_effect=SystemExit(130)), patch("builtins.input", return_value="") as pausar, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(modulo.main(["ocr"]), 130)
        self.assertIs(modulo.sys.argv, anterior)
        pausar.assert_called_once()

    def test_identificador_arbitrario_nao_executa_script(self):
        modulo = self.carregar()
        with patch.object(modulo.runpy, "run_path") as executar, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            modulo.main(["outro_script.py"])
        executar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
