"""Adaptador preserva assinatura existente e recusa pré-condições falhas."""

import contextlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from app import executor_servidor, trava_execucao
from app.servidor import PrecondicaoRecusada
from test_servidor import pedido


class TestExecutorServidor(unittest.TestCase):
    def setUp(self):
        self.dados = pedido()
        self.desktop = {}
        for nome in ("dominio", "estados", "interacao", "tela", "tela_principal"):
            self.desktop[nome] = types.ModuleType("app." + nome)
        dominio = self.desktop["dominio"]
        dominio._verificar_retorno_tela_principal = Mock(return_value="tela_principal_reconhecida")
        dominio.competencia_anterior = Mock(return_value=tuple(__import__("datetime").date.fromisoformat(self.dados[chave]).strftime("%d/%m/%Y") for chave in ("inicio", "fim")))
        for nome in ("gerar_sped_fiscal", "gerar_efd_contribuicoes", "gerar_registro_saidas", "gerar_registro_entradas"):
            setattr(dominio, nome, Mock(return_value=True))
        self.desktop["estados"].observar_eventos = lambda callback: contextlib.nullcontext()
        interacao = self.desktop["interacao"]
        interacao._minimizar_console_proprio = Mock()
        interacao.identificar_janela_dominio_atual = Mock(return_value={"hwnd": 123})
        interacao.janela_dominio_em_foco = Mock(return_value=True)
        self.desktop["tela"].capturar_tela = Mock()
        self.desktop["tela"].ler_empresa_selecionada = Mock(return_value=("EMPRESA SINTÉTICA", "52"))
        self.desktop["tela_principal"].carregar_referencia = Mock(return_value={"sintetica": True})

    def executar(self):
        with patch.object(executor_servidor.sys, "platform", "win32"):
            with patch.multiple("app", create=True, **self.desktop):
                return executor_servidor.ExecutorDominio()(self.dados, Mock())

    def test_preserva_rotina_sped_sem_reescrever_navegacao(self):
        self.assertTrue(self.executar())
        self.desktop["dominio"].gerar_sped_fiscal.assert_called_once_with(prefixo="servidor_" + self.dados["request_id"].replace("-", "") + "_")

    def test_empresa_divergente_nao_chama_gerador(self):
        self.desktop["tela"].ler_empresa_selecionada.return_value = ("SINTÉTICA", "99")
        with self.assertRaises(PrecondicaoRecusada):
            self.executar()
        self.desktop["dominio"].gerar_sped_fiscal.assert_not_called()

    def test_calibracao_ausente_nao_captura_ou_envia_acao(self):
        self.desktop["tela_principal"].carregar_referencia.return_value = None
        with self.assertRaises(PrecondicaoRecusada):
            self.executar()
        self.desktop["tela"].capturar_tela.assert_not_called()
        self.desktop["interacao"]._minimizar_console_proprio.assert_not_called()

    def test_tela_nao_reconhecida_nao_chama_gerador(self):
        self.desktop["dominio"]._verificar_retorno_tela_principal.return_value = "tela_principal_nao_reconhecida"
        with self.assertRaises(PrecondicaoRecusada):
            self.executar()
        self.desktop["dominio"].gerar_sped_fiscal.assert_not_called()

    def test_livro_preserva_pasta_fixa_e_datas_da_tarefa(self):
        self.dados.update(capacidade="registro_entradas", inicio="2026-08-01", fim="2026-08-31")
        self.executar()
        argumentos = self.desktop["dominio"].gerar_registro_entradas.call_args
        self.assertEqual(argumentos.args, (executor_servidor.ROOT / "saida",))
        self.assertEqual(argumentos.kwargs["data_inicial"], "01/08/2026")
        self.assertEqual(argumentos.kwargs["data_final"], "31/08/2026")


class TestTravaExecucao(unittest.TestCase):
    def test_segundo_executor_nao_adquire_ate_liberacao(self):
        import tempfile
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "sessao.lock"
            primeira, segunda = trava_execucao.TravaExecucao(caminho), trava_execucao.TravaExecucao(caminho)
            primeira.adquirir()
            try:
                with self.assertRaises(OSError):
                    segunda.adquirir()
            finally:
                primeira.liberar()
            segunda.adquirir()
            segunda.liberar()


class TestIniciarServidor(unittest.TestCase):
    def carregar(self):
        arquivo = Path(__file__).resolve().parents[1] / "scripts" / "servidor.py"
        spec = importlib.util.spec_from_file_location("cli_servidor_teste", arquivo)
        modulo = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", list(sys.path)):
            spec.loader.exec_module(modulo)
        return modulo

    def test_acesso_externo_sem_https_recusado_antes_de_iniciar(self):
        modulo = self.carregar()
        with contextlib.redirect_stderr(__import__("io").StringIO()), self.assertRaises(SystemExit):
            modulo.main(["--host", "0.0.0.0"])

    def test_linux_recusa_execucao_real(self):
        modulo = self.carregar()
        with patch.object(modulo.sys, "platform", "linux"), contextlib.redirect_stderr(__import__("io").StringIO()), self.assertRaises(SystemExit):
            modulo.main(["--executar"])


if __name__ == "__main__":
    unittest.main()
