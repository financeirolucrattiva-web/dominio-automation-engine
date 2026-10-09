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
CLASSE_ACOMPANHAMENTO = estados.AcompanhamentoRotina


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
        self.stack.enter_context(patch.object(d.interacao, "identificar_janela_dominio_atual", return_value={"hwnd": 123, "pid": 456, "classe": "DisplayClientWindowClass", "titulo": ""}, create=True))
        self.stack.enter_context(patch.object(d.interacao, "pressionar_esc_no_dominio", return_value=True, create=True))
        self.stack.enter_context(patch.object(d.interacao, "janela_dominio_em_foco", return_value=True, create=True))
        self.carregar_referencia = self.stack.enter_context(patch.object(d.tela_principal, "carregar_referencia", return_value=None))
        self.referencia_path = Mock()
        self.referencia_path.exists.return_value = False
        self.stack.enter_context(patch.object(d.tela_principal, "ARQUIVO_REFERENCIA", self.referencia_path))
        self.corresponde = self.stack.enter_context(patch.object(d.tela_principal, "corresponde", return_value=True))
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
        for segredo in ("EMPRESA FICTICIA", "01/08/2026", self.pasta.name, '"hwnd"', '"pid"', "DisplayClientWindowClass"):
            self.assertNotIn(segredo, texto)

    def test_falha_pdf_na_etapa_certa_sem_encerrar(self):
        self.finalizar.side_effect = ValueError("O cabeçalho do PDF não confirma o período solicitado.")
        self.assertEqual(self.executar(), (False, None))
        self.assertEqual(self.rotina.eventos[-2]["step"], "conferir_pdf")
        self.assertEqual(self.rotina.eventos[-2]["status"], "falha")
        self.assertNotIn("encerrar", [e["step"] for e in self.rotina.eventos])
        self.dominio.interacao.pressionar_esc_no_dominio.assert_called_once_with(self.rotina.janela_dominio, vezes=2, confirmar_conteudo=self.dominio._confirmar_conteudo_dominio)
        self.assertEqual([e["status"] for e in self.rotina.eventos if e["step"] == "recuperar_interface"], ["inicio", "acao_executada", "resultado_nao_verificado"])

    def test_recuperacao_uma_vez_sem_mudar_falha(self):
        self.finalizar.side_effect = ValueError("período não confirmado")
        self.assertEqual(self.executar(), (False, None))
        self.dominio._recuperar_interface_livro(self.rotina)
        self.dominio.interacao.pressionar_esc_no_dominio.assert_called_once_with(self.rotina.janela_dominio, vezes=2, confirmar_conteudo=self.dominio._confirmar_conteudo_dominio)
        self.assertEqual(self.rotina.etapa, "conferir_pdf")
        self.assertEqual(self.rotina.eventos[-1]["status"], "falha")

    def test_falha_recuperacao_nao_mascara_resultado_original(self):
        self.finalizar.side_effect = ValueError("período não confirmado")
        self.dominio.interacao.pressionar_esc_no_dominio.side_effect = RuntimeError("erro teclado privado")
        self.assertEqual(self.executar(), (False, None))
        self.assertEqual(self.rotina.eventos[-2]["step"], "conferir_pdf")
        self.assertTrue(any(e["step"] == "recuperar_interface" and e["status"] == "inconclusivo" for e in self.rotina.eventos))
        self.assertNotIn("erro teclado privado", self.rotina.caminho_log.read_text())

    def test_exception_pos_previa_preserva_original_se_recuperacao_falhar(self):
        original = RuntimeError("erro geração privado")
        self.dominio.interacao.digitar.side_effect = original
        self.dominio.interacao.pressionar_esc_no_dominio.side_effect = RuntimeError("erro recuperação privado")
        with self.assertRaises(RuntimeError) as contexto:
            self.executar()
        self.assertIs(contexto.exception, original)
        self.assertEqual(self.rotina.eventos[-2]["step"], "exportar_pdf")
        self.dominio.interacao.pressionar_esc_no_dominio.assert_called_once_with(self.rotina.janela_dominio, vezes=2, confirmar_conteudo=self.dominio._confirmar_conteudo_dominio)

    def test_interrupcao_manual_pos_previa_nao_envia_teclas(self):
        self.dominio.interacao.digitar.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.executar()
        self.dominio.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.assertEqual(self.rotina.eventos[-2]["step"], "exportar_pdf")

    def test_falha_no_encerramento_nao_repete_esc(self):
        self.dominio.interacao.pressionar_esc_no_dominio.side_effect = RuntimeError("falha saída")
        with self.assertRaises(RuntimeError):
            self.executar()
        self.dominio.interacao.pressionar_esc_no_dominio.assert_called_once_with(self.rotina.janela_dominio, vezes=2, confirmar_conteudo=self.dominio._confirmar_conteudo_dominio)
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
        self.dominio.interacao.pressionar_esc_no_dominio.assert_not_called()

    def test_excecao_registra_falha_sem_expor_mensagem(self):
        self.espera.side_effect = RuntimeError("conteudo fiscal privado")
        with self.assertRaises(RuntimeError):
            self.executar()
        self.assertEqual(self.rotina.eventos[-2]["step"], "abrir_livros")
        self.assertEqual(self.rotina.eventos[-1]["evidence"], "excecao")
        self.assertNotIn("conteudo fiscal privado", self.rotina.caminho_log.read_text())
        self.dominio.interacao.pressionar_esc_no_dominio.assert_not_called()

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
        self.rotina.janela_dominio = {"hwnd": 123, "pid": 456, "classe": "DisplayClientWindowClass", "titulo": ""}
        self.rotina.tentar_novamente()
        self.rotina.iniciar("validar_dados")
        self.dominio._recuperar_interface_livro(self.rotina)
        self.dominio.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.assertFalse(self.rotina.recuperacao_iniciada)
        self.assertIsNone(self.rotina.janela_dominio)

    def test_recuperacao_sem_foco_preserva_falha_e_nao_envia_esc_legado(self):
        self.finalizar.side_effect = ValueError("período não confirmado")
        self.dominio.interacao.pressionar_esc_no_dominio.return_value = False
        self.assertEqual(self.executar(), (False, None))
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertTrue(any(e["step"] == "recuperar_interface" and e["status"] == "inconclusivo" and e["evidence"] == "foco_dominio_nao_confirmado" for e in self.rotina.eventos))
        self.assertEqual(self.rotina.eventos[-2]["step"], "conferir_pdf")

    def test_pdf_validado_foco_encerramento_falha_preserva_arquivo(self):
        self.dominio.interacao.pressionar_esc_no_dominio.return_value = False
        sucesso, caminho = self.executar()
        self.assertFalse(sucesso)
        self.assertTrue(Path(caminho).exists())
        self.dominio.interacao.pressionar_esc_no_dominio.assert_called_once_with(self.rotina.janela_dominio, vezes=2, confirmar_conteudo=self.dominio._confirmar_conteudo_dominio)
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()
        self.assertEqual(self.rotina.eventos[-2]["step"], "encerrar")
        self.assertTrue(any(e["step"] == "encerrar" and e["status"] == "inconclusivo" for e in self.rotina.eventos))

    def test_cabecalho_ocr_dominio_obrigatorio_no_cliente_sem_titulo(self):
        self.assertTrue(self.dominio._confirmar_conteudo_dominio())
        with patch.object(self.dominio.tela, "achar_texto", return_value=None):
            self.assertFalse(self.dominio._confirmar_conteudo_dominio())

    def test_retorno_reconhecido_em_duas_capturas_preserva_falha_pdf(self):
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.finalizar.side_effect = ValueError("período não confirmado")
        self.assertEqual(self.executar(), (False, None))
        self.assertEqual(self.corresponde.call_count, 2)
        self.assertTrue(any(e["step"] == "recuperar_interface" and e["status"] == "confirmado" and e["evidence"] == "tela_principal_reconhecida" for e in self.rotina.eventos))
        self.assertEqual(self.rotina.eventos[-2]["step"], "conferir_pdf")

    def test_retorno_diferente_inconclusivo_preserva_pdf(self):
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.corresponde.return_value = False
        sucesso, caminho = self.executar()
        self.assertFalse(sucesso)
        self.assertTrue(Path(caminho).exists())
        # Além das 5 conferências do encerramento, a limpeza final tenta Esc e fechar a aba.
        self.assertGreater(self.corresponde.call_count, 5)
        self.assertEqual(self.dominio.interacao.pressionar_esc_no_dominio.call_count, 6)  # 1 do encerramento + 5 da limpeza
        self.assertTrue(any(e["step"] == "encerrar" and e["status"] == "inconclusivo" and e["evidence"] == "tela_principal_nao_reconhecida" for e in self.rotina.eventos))

    def test_sem_referencia_nao_alega_reconhecimento_visual(self):
        self.assertTrue(self.executar()[0])
        self.assertTrue(any(e["evidence"] == "referencia_tela_principal_ausente" for e in self.rotina.eventos))
        self.assertFalse(any(e["step"] == "encerrar" and e["status"] == "confirmado" for e in self.rotina.eventos))
        self.corresponde.assert_not_called()

    def test_frames_precisam_ser_consecutivos(self):
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.corresponde.side_effect = [True, False, True, True]
        self.assertEqual(self.dominio._verificar_retorno_tela_principal(self.rotina), "tela_principal_reconhecida")
        self.assertEqual(self.corresponde.call_count, 4)

    def test_perda_foco_durante_verificacao_nao_envia_acao(self):
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.dominio.interacao.janela_dominio_em_foco.side_effect = [True, False]
        self.assertEqual(self.dominio._verificar_retorno_tela_principal(self.rotina), "foco_dominio_nao_confirmado")
        self.dominio.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.dominio.interacao.pressionar_esc_repetidas.assert_not_called()

    def test_verificacao_tem_limite_cinco_frames_sem_teclas_adicionais(self):
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.corresponde.return_value = False
        self.dominio.time.sleep.reset_mock()
        self.assertEqual(self.dominio._verificar_retorno_tela_principal(self.rotina), "tela_principal_nao_reconhecida")
        self.assertEqual(self.corresponde.call_count, 5)
        self.assertEqual(self.dominio.time.sleep.call_count, 4)
        self.dominio.time.sleep.assert_called_with(0.3)
        self.dominio.interacao.pressionar_esc_no_dominio.assert_not_called()

    def test_excecao_verificacao_nao_mascara_erro_primario(self):
        original = RuntimeError("erro primário privado")
        self.dominio.interacao.digitar.side_effect = original
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.corresponde.side_effect = RuntimeError("erro detector privado")
        with self.assertRaises(RuntimeError) as contexto:
            self.executar()
        self.assertIs(contexto.exception, original)
        self.assertEqual(self.rotina.eventos[-2]["step"], "exportar_pdf")
        self.assertNotIn("erro detector privado", self.rotina.caminho_log.read_text())

    def test_retorno_confirmado_encerramento_sucesso(self):
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.assertTrue(self.executar()[0])
        self.assertTrue(any(e["step"] == "encerrar" and e["status"] == "confirmado" and e["evidence"] == "tela_principal_reconhecida" for e in self.rotina.eventos))

    def test_referencia_corrompida_nao_equivale_a_ausente(self):
        self.referencia_path.exists.return_value = True
        self.assertEqual(self.dominio._verificar_retorno_tela_principal(self.rotina), "referencia_tela_principal_invalida")
        self.corresponde.assert_not_called()

    def preparar_sped(self, rotina="sped_fiscal", item="SPED Fiscal", confirmacao="exporta"):
        d = self.dominio
        self.rotina = CLASSE_ACOMPANHAMENTO(rotina, self.pasta.name)
        d.estados.AcompanhamentoRotina.return_value = self.rotina
        self.item_sped = item
        self.confirmacao_sped = confirmacao
        self.competencia = self.stack.enter_context(patch.object(d, "selecionar_competencia_anterior", return_value=True))
        self.fechar_sped = self.stack.enter_context(patch.object(d, "_fechar_tela_geracao", return_value=True))
        self.stack.enter_context(patch.object(d.tela, "recortar_a_partir_de", return_value=("frame", 0, 0)))
        d.tela.achar_texto.side_effect = lambda imagem, texto, **kwargs: (100, 130) if texto == "Empresas" else (100, 100)
        d.tela.achar_texto_ou_no_centro.side_effect = lambda imagem, texto, **kwargs: None if texto == self.confirmacao_sped else (100, 100)

    def executar_sped(self):
        return self.dominio.gerar_sped(self.item_sped, self.confirmacao_sped)

    def test_sped_avisogeracao_sem_referencia_nao_alega_conteudo_ou_retorno(self):
        self.preparar_sped()
        self.assertTrue(self.executar_sped())
        self.assertEqual([e["step"] for e in self.rotina.eventos if e["status"] == "inicio"], list(self.rotina.ETAPAS))
        self.assertTrue(any(e["evidence"] == "aviso_resultado_reconhecido" for e in self.rotina.eventos))
        self.assertTrue(any(e["step"] == "encerrar" and e["status"] == "acao_executada" for e in self.rotina.eventos))
        self.assertFalse(any(e["evidence"] in ("pdf_tipo_periodo_cnpj_confirmados", "tela_principal_reconhecida") for e in self.rotina.eventos))

    def test_efd_retorno_visual_confirmado_sem_mudar_api_bool(self):
        self.preparar_sped("efd_contribuicoes", "Contribui", "sucesso")
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.assertIs(self.dominio.gerar_efd_contribuicoes(), True)
        self.assertEqual(self.rotina.eventos[-1]["routine_id"], "efd_contribuicoes")
        self.assertTrue(any(e["step"] == "encerrar" and e["status"] == "confirmado" and e["evidence"] == "tela_principal_reconhecida" for e in self.rotina.eventos))

    def test_sped_falha_periodo_preserva_etapa_e_fechamento_legado(self):
        self.preparar_sped()
        self.competencia.return_value = False
        self.assertFalse(self.executar_sped())
        self.assertEqual(self.rotina.eventos[-2]["step"], "preencher_periodo")
        self.fechar_sped.assert_called_once_with("SPED Fiscal", "")
        self.espera.assert_not_called()

    def test_sped_falha_retorno_mesmo_fechamento_legado_true(self):
        self.preparar_sped()
        self.carregar_referencia.return_value = {"referencia": "sintetica"}
        self.corresponde.return_value = False
        self.assertFalse(self.executar_sped())
        self.assertEqual(self.rotina.eventos[-2]["step"], "encerrar")
        self.assertTrue(any(e["step"] == "encerrar" and e["status"] == "inconclusivo" for e in self.rotina.eventos))
        # A limpeza final tenta voltar à tela principal com Esc, um por vez.
        self.assertEqual(self.dominio.interacao.pressionar_esc_no_dominio.call_count, 5)

    def test_sped_erro_aviso_nao_avanca_para_encerramento_sucesso(self):
        self.preparar_sped()
        self.espera.return_value = ("frame", (100, 100), True)
        self.stack.enter_context(patch.object(self.dominio, "_ler_texto_caixa", return_value="erro fiscal privado"))
        self.stack.enter_context(patch.object(self.dominio, "_fechar_caixa_erro"))
        self.stack.enter_context(patch.object(self.dominio.erros, "decidir", return_value=self.dominio.erros.PULAR))
        self.assertFalse(self.executar_sped())
        self.assertEqual(self.rotina.eventos[-2]["step"], "gerar_documento")
        self.assertNotIn("encerrar", [e["step"] for e in self.rotina.eventos])
        self.assertNotIn("erro fiscal privado", self.rotina.caminho_log.read_text())

    def test_sped_retry_mesma_execucao_tentativas_separadas(self):
        self.preparar_sped()
        self.espera.side_effect = [("frame", (100, 100), True), ("frame", (100, 100), False)]
        self.stack.enter_context(patch.object(self.dominio, "_ler_texto_caixa", return_value="erro fiscal privado"))
        self.stack.enter_context(patch.object(self.dominio, "_fechar_caixa_erro"))
        self.stack.enter_context(patch.object(self.dominio.erros, "decidir", return_value=self.dominio.erros.TENTAR_DE_NOVO))
        self.assertTrue(self.executar_sped())
        self.assertEqual(self.rotina.tentativa, 2)
        self.assertEqual({e["execution_id"] for e in self.rotina.eventos}, {self.rotina.execution_id})
        self.assertTrue(any(e["step"] == "gerar_documento" and e["status"] == "falha" and e["attempt"] == 1 for e in self.rotina.eventos))

    def test_competencia_escolhida_sobrevive_a_retry_sem_chamar_anterior(self):
        self.preparar_sped()
        selecionada = self.stack.enter_context(patch.object(self.dominio, "selecionar_competencia", return_value=True))
        self.espera.side_effect = [("frame", (100, 100), True), ("frame", (100, 100), False)]
        self.stack.enter_context(patch.object(self.dominio, "_ler_texto_caixa", return_value="erro fiscal privado"))
        self.stack.enter_context(patch.object(self.dominio, "_fechar_caixa_erro"))
        self.stack.enter_context(patch.object(self.dominio.erros, "decidir", return_value=self.dominio.erros.TENTAR_DE_NOVO))
        self.assertTrue(self.dominio.gerar_sped(self.item_sped, self.confirmacao_sped, data_inicial="01/02/2024", data_final="29/02/2024"))
        self.assertEqual(selecionada.call_count, 2)
        for chamada in selecionada.call_args_list:
            self.assertEqual(chamada.args, ("01/02/2024", "29/02/2024"))
        self.competencia.assert_not_called()

    def test_competencia_incompleta_recusa_antes_de_mouse_ou_captura(self):
        self.preparar_sped()
        self.assertFalse(self.dominio.gerar_sped(self.item_sped, self.confirmacao_sped, data_inicial="02/02/2024", data_final="29/02/2024"))
        self.dominio.interacao.focar_dominio.assert_not_called()
        self.dominio.tela.capturar_tela.assert_not_called()


if __name__ == "__main__":
    unittest.main()
