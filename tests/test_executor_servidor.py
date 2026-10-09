"""Adaptador preserva assinatura existente e recusa pré-condições falhas."""

import contextlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from app import executor_servidor, trava_execucao
from app.servidor import PrecondicaoRecusada, RepositorioTarefas, ServicoExecucao
from app.controle_execucao import ponto_seguro
from test_servidor import aguardar, eventos_confirmados, pedido


class TestExecutorServidor(unittest.TestCase):
    def setUp(self):
        self.dados = pedido()
        self.desktop = {}
        for nome in ("dominio", "estados", "interacao", "tela", "tela_principal"):
            self.desktop[nome] = types.ModuleType("app." + nome)
        dominio = self.desktop["dominio"]
        dominio.trocar_empresa = Mock(return_value=True)
        dominio._verificar_retorno_tela_principal = Mock(return_value="tela_principal_reconhecida")
        dominio._confirmar_conteudo_dominio = Mock(return_value=True)
        dominio.competencia_anterior = Mock(return_value=tuple(__import__("datetime").date.fromisoformat(self.dados[chave]).strftime("%d/%m/%Y") for chave in ("inicio", "fim")))
        for nome in ("gerar_sped_fiscal", "gerar_efd_contribuicoes", "gerar_registro_saidas", "gerar_registro_entradas", "gerar_resumo_acumulador"):
            setattr(dominio, nome, Mock(return_value=True))
        self.desktop["estados"].observar_eventos = lambda callback: contextlib.nullcontext()
        interacao = self.desktop["interacao"]
        interacao._minimizar_console_proprio = Mock()
        interacao.identificar_janela_dominio_atual = Mock(return_value={"hwnd": 123})
        interacao.janela_dominio_em_foco = Mock(return_value=True)
        interacao.pressionar_esc_no_dominio = Mock(return_value=True)
        self.desktop["tela"].capturar_tela = Mock()
        self.desktop["tela"].ler_empresa_selecionada = Mock(return_value=("EMPRESA SINTÉTICA", "52"))
        self.desktop["tela_principal"].carregar_referencia = Mock(return_value={"sintetica": True})

    def executar(self, lote=False):
        with patch.object(executor_servidor.sys, "platform", "win32"):
            with patch.multiple("app", create=True, **self.desktop):
                executor = executor_servidor.ExecutorDominio()
                return (executor.executar_em_lote if lote else executor)(self.dados, Mock())

    def test_preserva_rotina_sped_sem_reescrever_navegacao(self):
        self.assertTrue(self.executar())
        import datetime as dt
        self.desktop["dominio"].gerar_sped_fiscal.assert_called_once_with(
            prefixo="servidor_" + self.dados["request_id"].replace("-", "") + "_",
            data_inicial=dt.date.fromisoformat(self.dados["inicio"]).strftime("%d/%m/%Y"),
            data_final=dt.date.fromisoformat(self.dados["fim"]).strftime("%d/%m/%Y"))

    def test_competencia_escolhida_nao_e_substituida_pelo_mes_anterior(self):
        self.dados.update(capacidade="efd_contribuicoes", inicio="2024-02-01", fim="2024-02-29")
        self.executar()
        gerador = self.desktop["dominio"].gerar_efd_contribuicoes
        self.assertEqual(gerador.call_args.kwargs["data_inicial"], "01/02/2024")
        self.assertEqual(gerador.call_args.kwargs["data_final"], "29/02/2024")
        self.desktop["dominio"].competencia_anterior.assert_not_called()

    def test_resumo_usa_datas_solicitadas_e_pasta_local(self):
        self.dados.update(capacidade="resumo_acumulador", inicio="2024-02-01", fim="2024-02-29")
        self.executar()
        gerador = self.desktop["dominio"].gerar_resumo_acumulador
        self.assertEqual(gerador.call_args.args, (executor_servidor.ROOT / "saida",))
        self.assertEqual(gerador.call_args.kwargs["data_inicial"], "01/02/2024")
        self.assertEqual(gerador.call_args.kwargs["data_final"], "29/02/2024")

    def test_empresa_individual_divergente_nao_confirmada_nao_chama_gerador(self):
        self.desktop["tela"].ler_empresa_selecionada.return_value = ("SINTÉTICA", "99")
        with self.assertRaises(PrecondicaoRecusada):
            self.executar()
        self.desktop["dominio"].gerar_sped_fiscal.assert_not_called()
        self.desktop["dominio"].trocar_empresa.assert_called_once()

    def test_individual_troca_empresa_divergente_e_confere_antes_de_gerar(self):
        self.desktop["tela"].ler_empresa_selecionada.side_effect = [("SINTÉTICA", "99"), ("SINTÉTICA", "52")]
        self.assertTrue(self.executar())
        self.desktop["dominio"].trocar_empresa.assert_called_once()
        self.assertEqual(self.desktop["dominio"].trocar_empresa.call_args.args, ("52",))
        self.desktop["dominio"].gerar_sped_fiscal.assert_called_once()

    def test_troca_f8_retornando_falso_nao_gera_nem_repete(self):
        self.desktop["tela"].ler_empresa_selecionada.return_value = ("SINTÉTICA", "99")
        self.desktop["dominio"].trocar_empresa.return_value = False
        with self.assertRaisesRegex(PrecondicaoRecusada, "empresa_nao_confirmada"):
            self.executar(lote=True)
        self.desktop["dominio"].trocar_empresa.assert_called_once()
        self.desktop["dominio"].gerar_sped_fiscal.assert_not_called()

    def test_codigo_com_zeros_equivale_ao_codigo_lido(self):
        self.dados["empresa_codigo"] = "00052"
        self.assertTrue(self.executar())
        self.desktop["dominio"].trocar_empresa.assert_not_called()

    def test_codigo_muda_entre_leituras_bloqueia_emissao(self):
        self.desktop["tela"].ler_empresa_selecionada.side_effect = [("SINTÉTICA", "52"), ("SINTÉTICA", "99")]
        with self.assertRaisesRegex(PrecondicaoRecusada, "empresa_nao_confirmada"):
            self.executar(lote=True)
        self.desktop["dominio"].gerar_sped_fiscal.assert_not_called()
        self.desktop["dominio"].trocar_empresa.assert_not_called()

    def test_codigo_ilegivel_nao_tenta_f8_nem_gera(self):
        self.desktop["tela"].ler_empresa_selecionada.return_value = None
        with self.assertRaisesRegex(PrecondicaoRecusada, "empresa_nao_confirmada"):
            self.executar(lote=True)
        self.desktop["dominio"].trocar_empresa.assert_not_called()
        self.desktop["dominio"].gerar_sped_fiscal.assert_not_called()

    def test_foco_perdido_bloqueia_acao_mesmo_se_excecao_for_absorvida(self):
        foco = self.desktop["interacao"].janela_dominio_em_foco
        def gerar(**kwargs):
            foco.return_value = False
            try:
                ponto_seguro()
            except executor_servidor.FocoPerdidoDuranteExecucao:
                pass
            foco.return_value = True
            # Não pode voltar a agir na mesma emissão depois da perda de foco.
            ponto_seguro()
            self.fail("Checkpoint permitiu ação depois de perder o foco.")
        self.desktop["dominio"].gerar_sped_fiscal.side_effect = gerar
        with self.assertRaisesRegex(executor_servidor.FocoPerdidoDuranteExecucao, "dominio_fora_de_foco"):
            self.executar(lote=True)

    def test_worker_foco_perdido_na_emissao_recupera_e_segue_proxima(self):
        import uuid
        with tempfile.TemporaryDirectory() as pasta:
            repo = RepositorioTarefas(Path(pasta) / "tarefas.sqlite3")
            regime = repo.configuracao.salvar_regime(None, "Regime sintético", ["sped_fiscal", "efd_contribuicoes"])
            repo.configuracao.salvar_empresa("52", "Empresa sintética", regime["id"])
            selecao = {"empresas": ["52"], "inicio": "2024-02-01", "fim": "2024-02-29"}
            plano = repo.configuracao.planejar(selecao)
            chamadas, observador = [], []
            @contextlib.contextmanager
            def observar(callback):
                observador.append(callback)
                try:
                    yield
                finally:
                    observador.pop()
            self.desktop["estados"].observar_eventos = observar
            foco = self.desktop["interacao"].janela_dominio_em_foco
            def emitir(capacidade):
                def gerar(**kwargs):
                    chamadas.append(capacidade)
                    if len(chamadas) == 1:
                        foco.return_value = False
                        ponto_seguro()  # perde foco depois de iniciar a emissão
                    eventos_confirmados({"request_id": str(uuid.uuid4()), "capacidade": capacidade}, observador[-1])
                    return True
                return gerar
            self.desktop["dominio"].gerar_sped_fiscal.side_effect = emitir("sped_fiscal")
            self.desktop["dominio"].gerar_efd_contribuicoes.side_effect = emitir("efd_contribuicoes")
            self.desktop["dominio"]._verificar_retorno_tela_principal.side_effect = lambda contexto: (
                "tela_principal_reconhecida" if foco.return_value else "tela_principal_nao_reconhecida")
            def recuperar_foco(*args, **kwargs):
                foco.return_value = True  # confirmação sintética do HWND conhecido
                return True
            self.desktop["interacao"].pressionar_esc_no_dominio.side_effect = recuperar_foco
            with patch.object(executor_servidor.sys, "platform", "win32"), patch.multiple("app", create=True, **self.desktop):
                servico = ServicoExecucao(repo, executor_servidor.ExecutorDominio(), modo="simulacao")
                servico.iniciar()
                try:
                    with self.assertLogs("app.servidor", level="ERROR"):
                        lote = servico.solicitar_lote({**selecao, "request_id": str(uuid.uuid4()), "apuracao_confirmada": True, "plano_hash": plano["hash"]})
                        tarefas = repo.obter_lote(lote["id"])["tarefas"]
                        self.assertEqual(aguardar(repo, tarefas[0]["id"])["status"], "falha")
                        self.assertEqual(aguardar(repo, tarefas[1]["id"])["status"], "concluida")
                finally:
                    servico.encerrar()
            self.assertEqual(chamadas, ["sped_fiscal", "efd_contribuicoes"])
            self.assertEqual(repo.obter_lote(lote["id"])["status"], "concluida_com_falhas")
            self.desktop["interacao"].pressionar_esc_no_dominio.assert_called_once()

    def test_tela_presa_inicial_recupera_antes_de_trocar_empresa(self):
        d = self.desktop["dominio"]
        d._verificar_retorno_tela_principal.side_effect = ["tela_principal_nao_reconhecida"] * 2 + ["tela_principal_reconhecida"] * 2
        self.desktop["tela"].ler_empresa_selecionada.side_effect = [("SINTÉTICA", "99"), ("SINTÉTICA", "52")]
        chamadas = Mock()
        chamadas.attach_mock(self.desktop["interacao"].pressionar_esc_no_dominio, "esc")
        chamadas.attach_mock(d.trocar_empresa, "f8")
        chamadas.attach_mock(d.gerar_sped_fiscal, "gerar")
        self.assertTrue(self.executar(lote=True))
        self.assertEqual([c[0] for c in chamadas.mock_calls], ["esc", "f8", "gerar"])

    def test_janela_ausente_ou_sem_foco_nao_tenta_limpar_ou_trocar(self):
        for janela, foco in ((None, True), ({"hwnd": 123}, False)):
            with self.subTest(janela=janela):
                self.desktop["interacao"].identificar_janela_dominio_atual.return_value = janela
                self.desktop["interacao"].janela_dominio_em_foco.return_value = foco
                with self.assertRaisesRegex(PrecondicaoRecusada, "dominio_fora_de_foco"):
                    self.executar(lote=True)
                self.desktop["interacao"].pressionar_esc_no_dominio.assert_not_called()
                self.desktop["dominio"].trocar_empresa.assert_not_called()

    def test_lote_reutiliza_f8_e_confere_codigo_antes_de_gerar(self):
        self.desktop["tela"].ler_empresa_selecionada.side_effect = [("SINTÉTICA", "99"), ("SINTÉTICA", "52")]
        self.assertTrue(self.executar(lote=True))
        self.desktop["dominio"].trocar_empresa.assert_called_once()
        self.assertEqual(self.desktop["dominio"].trocar_empresa.call_args.args, ("52",))

    def test_lote_nao_troca_empresa_que_ja_esta_correta(self):
        self.assertTrue(self.executar(lote=True))
        self.desktop["dominio"].trocar_empresa.assert_not_called()

    def test_troca_nao_confirmada_no_cabecalho_nao_gera(self):
        self.desktop["tela"].ler_empresa_selecionada.return_value = ("SINTÉTICA", "99")
        with self.assertRaises(PrecondicaoRecusada):
            self.executar(lote=True)
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

    def recuperar(self, janela=True):
        executor = executor_servidor.ExecutorDominio()
        if janela:
            executor._janela_lote = {"hwnd": 123}
        with patch.object(executor_servidor.sys, "platform", "win32"), patch.multiple("app", create=True, **self.desktop):
            return executor.recuperar_em_lote(self.dados)

    def test_recuperacao_ja_na_tela_azul_nao_envia_esc(self):
        self.desktop["interacao"].pressionar_esc_no_dominio = Mock(return_value=True)
        self.assertTrue(self.recuperar())
        self.desktop["interacao"].pressionar_esc_no_dominio.assert_not_called()

    def test_recuperacao_fecha_uma_tela_por_vez_e_confere_empresa(self):
        d = self.desktop["dominio"]
        d._verificar_retorno_tela_principal.side_effect = ["tela_principal_nao_reconhecida"] * 2 + ["tela_principal_reconhecida"]
        d._confirmar_conteudo_dominio = Mock(return_value=True)
        esc = self.desktop["interacao"].pressionar_esc_no_dominio = Mock(return_value=True)
        self.assertTrue(self.recuperar())
        self.assertEqual(esc.call_count, 2)
        self.assertTrue(all(c.kwargs["vezes"] == 1 for c in esc.call_args_list))
        d.gerar_sped_fiscal.assert_not_called()

    def test_recuperacao_sem_janela_ou_calibracao_nao_envia_acao(self):
        esc = self.desktop["interacao"].pressionar_esc_no_dominio = Mock()
        self.assertFalse(self.recuperar(janela=False))
        self.desktop["tela_principal"].carregar_referencia.return_value = None
        self.assertFalse(self.recuperar())
        esc.assert_not_called()

    def test_recuperacao_recusa_empresa_divergente_e_foco_perdido(self):
        self.desktop["tela"].ler_empresa_selecionada.return_value = ("SINTÉTICA", "99")
        self.assertFalse(self.recuperar())
        self.desktop["tela"].ler_empresa_selecionada.return_value = ("SINTÉTICA", "52")
        self.desktop["interacao"].janela_dominio_em_foco.return_value = False
        self.assertFalse(self.recuperar())

    def test_recuperacao_tem_limite_e_recusa_envio_sem_foco(self):
        self.desktop["dominio"]._verificar_retorno_tela_principal.return_value = "tela_principal_nao_reconhecida"
        self.desktop["dominio"]._confirmar_conteudo_dominio = Mock(return_value=True)
        esc = self.desktop["interacao"].pressionar_esc_no_dominio = Mock(return_value=True)
        self.assertFalse(self.recuperar())
        self.assertEqual(esc.call_count, 5)
        esc.reset_mock(); esc.return_value = False
        self.assertFalse(self.recuperar())
        self.assertEqual(esc.call_count, 1)


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
