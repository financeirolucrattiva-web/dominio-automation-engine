"""Acompanhamento de etapas com evidências fixas e navegação simulada."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

with patch("ctypes.windll", Mock(), create=True):
    from app import estados


class _BaseAcompanhamento(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.console = io.StringIO()
        contexto = contextlib.redirect_stdout(self.console)
        contexto.__enter__()
        self.addCleanup(contexto.__exit__, None, None, None)

    def acompanhamento(self):
        return estados.AcompanhamentoRotina("registro_saidas", self.pasta.name)


class TestAcompanhamento(_BaseAcompanhamento):
    def test_sequencia_e_fechamento_apenas_acao(self):
        rotina = self.acompanhamento()
        for etapa in rotina.ETAPAS:
            rotina.iniciar(etapa)
            rotina.confirmar(rotina.CONFIRMACOES[etapa])
        rotina.concluir(True)
        registros = [json.loads(linha) for linha in rotina.caminho_log.read_text().splitlines()]
        self.assertEqual([r["step"] for r in registros if r["status"] == "inicio"], list(rotina.ETAPAS))
        self.assertEqual(registros[-2]["status"], "acao_executada")
        self.assertEqual(registros[-1]["status"], "concluido")

    def test_nao_avanca_sem_evidencia_nem_confirma_apos_falha(self):
        rotina = self.acompanhamento()
        with self.assertRaises(ValueError):
            rotina.confirmar("datas_validas")
        rotina.iniciar("validar_dados")
        for chamada in (lambda: rotina.iniciar("identificar_empresa"), lambda: rotina.confirmar("campos_periodo_confirmados"), lambda: rotina.concluir(True)):
            with self.assertRaises(ValueError):
                chamada()
        rotina.concluir(False)
        with self.assertRaises(ValueError):
            rotina.confirmar("datas_validas")
        self.assertFalse(any(e["status"] == "confirmado" for e in rotina.eventos))

    def test_retry_mesma_execucao_sem_aproveitar_confirmacoes(self):
        rotina = self.acompanhamento()
        rotina.iniciar("validar_dados")
        rotina.confirmar("datas_validas")
        rotina.iniciar("identificar_empresa")
        rotina.tentar_novamente()
        rotina.iniciar("validar_dados")
        self.assertEqual(rotina.tentativa, 2)
        self.assertEqual(rotina.confirmadas, [])
        self.assertEqual({e["execution_id"] for e in rotina.eventos}, {rotina.execution_id})

    def test_falha_de_gravacao_avisa_e_mantem_eventos(self):
        rotina = self.acompanhamento()
        with patch.object(Path, "open", side_effect=PermissionError):
            rotina.iniciar("validar_dados")
            rotina.concluir(False)
        self.assertEqual(len(rotina.eventos), 3)
        self.assertEqual(self.console.getvalue().count("não foi possível gravar"), 1)


class TestFluxoAcompanhado(_BaseAcompanhamento):
    def setUp(self):
        super().setUp()
        # Isola o backend Windows; nenhuma ação real é executada.
        interacao = types.ModuleType("app.interacao")
        with patch.dict("sys.modules", {"app.interacao": interacao}):
            spec = importlib.util.spec_from_file_location("app._dominio_teste", Path(__file__).resolve().parents[1] / "app" / "dominio.py")
            self.dominio = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.dominio)
        self.rotina = self.acompanhamento()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        d = self.dominio
        self.stack.enter_context(patch.object(d.estados, "AcompanhamentoRotina", return_value=self.rotina))
        self.stack.enter_context(patch.object(d.time, "sleep"))
        for nome in ("focar_dominio", "clicar", "passar_mouse", "clicar_com_desvio", "selecionar_tudo_alternativo", "pressionar_enter", "pressionar_esc_repetidas"):
            self.stack.enter_context(patch.object(d.interacao, nome, Mock(), create=True))
        self.stack.enter_context(patch.object(d.interacao, "digitar", side_effect=lambda caminho: Path(caminho).write_bytes(b"%PDF-novo"), create=True))
        for nome, retorno in (("capturar_tela", "frame"), ("ler_empresa_selecionada", ("EMPRESA FICTICIA", "1")), ("recortar_topo", "frame"), ("recortar_area_menu", "frame"), ("achar_texto", (100, 100)), ("achar_icone_robusto", (20, 30))):
            self.stack.enter_context(patch.object(d.tela, nome, return_value=retorno))
        self.stack.enter_context(patch.object(d.tela, "achar_texto_ou_no_centro", side_effect=lambda imagem, texto, **kwargs: None if texto == "does not exist" else (100, 100)))
        self.stack.enter_context(patch.object(d, "achar_ou_parar", return_value=(100, 100)))
        self.stack.enter_context(patch.object(d, "preencher_periodo_livros_fiscais", return_value=True))
        self.stack.enter_context(patch.object(d, "salvar"))
        self.stack.enter_context(patch.object(d, "caminho_visto_pela_sessao_remota", side_effect=str))
        self.espera = self.stack.enter_context(patch.object(d, "esperar_e_achar", return_value=("frame", (100, 100), False)))
        self.finalizar = self.stack.enter_context(patch.object(d.arquivos, "finalizar_pdf", side_effect=lambda caminho, *args, **kwargs: caminho))

    def executar(self):
        return self.dominio.gerar_registro_saidas(self.pasta.name, "01/08/2026", "31/08/2026")

    def test_fluxo_sucesso_e_evidencias_sem_dados_fiscais(self):
        resultado = self.executar()
        self.assertTrue(resultado[0])
        self.assertEqual(self.rotina.eventos[-1]["status"], "concluido")
        texto = self.rotina.caminho_log.read_text()
        for segredo in ("EMPRESA FICTICIA", "01/08/2026", self.pasta.name):
            self.assertNotIn(segredo, texto)

    def test_falha_pdf_na_etapa_certa_sem_encerrar(self):
        self.finalizar.side_effect = ValueError("O cabeçalho do PDF não confirma o período solicitado.")
        self.assertEqual(self.executar(), (False, None))
        self.assertEqual(self.rotina.eventos[-2]["step"], "conferir_pdf")
        self.assertEqual(self.rotina.eventos[-2]["status"], "falha")
        self.assertNotIn("encerrar", [e["step"] for e in self.rotina.eventos])
        self.dominio.interacao.pressionar_esc_repetidas.assert_called_once_with(vezes=2)
        self.assertEqual([e["status"] for e in self.rotina.eventos if e["step"] == "recuperar_interface"], ["inicio", "acao_executada", "resultado_nao_verificado"])

    def test_recuperacao_uma_vez_sem_mudar_falha(self):
        self.finalizar.side_effect = ValueError("período não confirmado")
        self.assertEqual(self.executar(), (False, None))
        self.dominio._recuperar_interface_livro(self.rotina)
        self.dominio.interacao.pressionar_esc_repetidas.assert_called_once_with(vezes=2)
        self.assertEqual(self.rotina.etapa, "conferir_pdf")
        self.assertEqual(self.rotina.eventos[-1]["status"], "falha")

    def test_falha_recuperacao_nao_mascara_resultado_original(self):
        self.finalizar.side_effect = ValueError("período não confirmado")
        self.dominio.interacao.pressionar_esc_repetidas.side_effect = RuntimeError("erro teclado privado")
        self.assertEqual(self.executar(), (False, None))
        self.assertEqual(self.rotina.eventos[-2]["step"], "conferir_pdf")
        self.assertTrue(any(e["step"] == "recuperar_interface" and e["status"] == "inconclusivo" for e in self.rotina.eventos))
        self.assertNotIn("erro teclado privado", self.rotina.caminho_log.read_text())

    def test_exception_pos_previa_preserva_original_se_recuperacao_falhar(self):
        original = RuntimeError("erro geração privado")
        self.dominio.interacao.digitar.side_effect = original
        self.dominio.interacao.pressionar_esc_repetidas.side_effect = RuntimeError("erro recuperação privado")
        with self.assertRaises(RuntimeError) as contexto:
            self.executar()
        self.assertIs(contexto.exception, original)
        self.assertEqual(self.rotina.eventos[-2]["step"], "exportar_pdf")
        self.dominio.interacao.pressionar_esc_repetidas.assert_called_once_with(vezes=2)

    def test_interrupcao_manual_pos_previa_nao_envia_teclas(self):
        self.dominio.interacao.digitar.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.executar()
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertEqual(self.rotina.eventos[-2]["step"], "exportar_pdf")

    def test_falha_no_encerramento_nao_repete_esc(self):
        self.dominio.interacao.pressionar_esc_repetidas.side_effect = RuntimeError("falha saída")
        with self.assertRaises(RuntimeError):
            self.executar()
        self.dominio.interacao.pressionar_esc_repetidas.assert_called_once_with(vezes=2)
        self.assertEqual(self.rotina.eventos[-2]["step"], "encerrar")
        self.assertTrue(any(e["evidence"] == "encerramento_ja_tentado" for e in self.rotina.eventos))

    def test_arquivo_novo_ausente_nao_avanca_para_conferencia(self):
        self.dominio.interacao.digitar.side_effect = None
        self.assertEqual(self.executar(), (False, None))
        self.assertEqual(self.rotina.eventos[-2]["step"], "exportar_pdf")
        self.assertNotIn("conferir_pdf", [e["step"] for e in self.rotina.eventos])

    def test_data_invalida_falha_antes_de_focar_ou_abrir_menu(self):
        resultado = self.dominio.gerar_registro_saidas(self.pasta.name, "31/02/2026", "31/08/2026")
        self.assertEqual(resultado, (False, None))
        self.assertEqual(self.rotina.eventos[-2]["step"], "validar_dados")
        self.dominio.interacao.focar_dominio.assert_not_called()
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()

    def test_excecao_registra_falha_sem_expor_mensagem(self):
        self.espera.side_effect = RuntimeError("conteudo fiscal privado")
        with self.assertRaises(RuntimeError):
            self.executar()
        self.assertEqual(self.rotina.eventos[-2]["step"], "abrir_livros")
        self.assertEqual(self.rotina.eventos[-1]["evidence"], "excecao")
        self.assertNotIn("conteudo fiscal privado", self.rotina.caminho_log.read_text())
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()

    def test_retry_navegacao_mesma_execucao(self):
        d = self.dominio
        self.espera.side_effect = [("frame", (100, 100), False), ("frame", (100, 100), True), ("frame", (100, 100), False), ("frame", (100, 100), False)]
        self.stack.enter_context(patch.object(d, "_ler_texto_caixa", return_value="texto fiscal privado"))
        self.stack.enter_context(patch.object(d, "_fechar_caixa_erro"))
        self.stack.enter_context(patch.object(d.erros, "decidir", return_value=d.erros.TENTAR_DE_NOVO))
        self.assertTrue(self.executar()[0])
        self.assertEqual(self.rotina.tentativa, 2)
        self.assertTrue(any(e["step"] == "gerar_previa" and e["status"] == "falha" and e["attempt"] == 1 for e in self.rotina.eventos))
        self.assertEqual(self.rotina.eventos[-1]["attempt"], 2)
        self.assertNotIn("texto fiscal privado", self.rotina.caminho_log.read_text())

    def test_previa_anterior_nao_autoriza_recuperacao_em_nova_tentativa(self):
        for etapa in self.rotina.ETAPAS[:5]:
            self.rotina.iniciar(etapa)
            self.rotina.confirmar(self.rotina.CONFIRMACOES[etapa])
        self.rotina.iniciar("exportar_pdf")
        self.rotina.tentar_novamente()
        self.rotina.iniciar("validar_dados")
        self.dominio._recuperar_interface_livro(self.rotina)
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertFalse(self.rotina.recuperacao_iniciada)


if __name__ == "__main__":
    unittest.main()
