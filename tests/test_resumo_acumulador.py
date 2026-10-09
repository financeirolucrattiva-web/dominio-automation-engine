"""OCR/desktop substituídos; PDFs e persistência reais, todos sintéticos."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from app import arquivos
from app.formulario_resumo import campos_periodo
from app.servidor import RepositorioTarefas
from test_arquivos import criar_pdf, CNPJ

TEXTO = "EMPRESA FICTICIA CNPJ: 12.345.678/0001-95 Periodo: 01/08/2026 ate 31/08/2026 RESUMO POR ACUMULADOR ENTRADAS Codigo Descricao"


def dados_ocr(dx=0, dy=0):
    valores = [("Data", 50, 80, 25), ("inicial:", 82, 80, 40), ("01/08/2026", 132, 80, 75),
               ("Data", 50, 108, 25), ("final:", 82, 108, 40), ("31/08/2026", 132, 108, 75)]
    return {"text": [v[0] for v in valores], "left": [(v[1]+dx)*2 for v in valores],
            "top": [(v[2]+dy)*2 for v in valores], "width": [v[3]*2 for v in valores], "height": [24]*6}


class TestResumoDados(unittest.TestCase):
    def test_campos_medidos_acompanham_janela_e_datas_iguais_nao_confundem_campos(self):
        origem = campos_periodo(dados_ocr())
        movidos = dados_ocr(310, 210)
        movidos["text"][5] = movidos["text"][2]
        campos = campos_periodo(movidos)
        for papel in ("inicial", "final"):
            self.assertEqual(campos[papel]["posicao"], tuple(a+b for a, b in zip(origem[papel]["posicao"], (310, 210))))
        self.assertNotEqual(campos["inicial"]["posicao"], campos["final"]["posicao"])

    def test_recusa_rotulo_data_ausente_ambiguo_e_data_invalida(self):
        for indice, valor in ((1, "outra:"), (2, "31/02/2026"), (5, "??/08/2026"), (3, "Outra")):
            dados = dados_ocr()
            dados["text"][indice] = valor
            with self.subTest(indice=indice), self.assertRaises(ValueError):
                campos_periodo(dados)
        dados = dados_ocr()
        for chave in dados:
            dados[chave].append(dados[chave][2])
        with self.assertRaises(ValueError):
            campos_periodo(dados)

    def test_cabecalho_antes_ou_depois_do_titulo_e_texto_espacado(self):
        self.assertEqual(arquivos.validar_resumo_acumulador(TEXTO, "01/08/2026", "31/08/2026", CNPJ), CNPJ)
        titulo_primeiro = "RESUMO POR ACUMULADOR " + TEXTO.replace("RESUMO POR ACUMULADOR ", "")
        self.assertEqual(arquivos.validar_resumo_acumulador(" ".join(titulo_primeiro), "01/08/2026", "31/08/2026"), CNPJ)

    def test_periodo_empresa_titulo_ambiguos_ou_so_na_tabela_nao_passam(self):
        for texto in (TEXTO.replace("01/08/2026 ate 31/08/2026", "01/09/2026 ate 30/09/2026"),
                      TEXTO.replace("RESUMO POR ACUMULADOR", "REGISTRO DE ENTRADAS"),
                      TEXTO.replace("CNPJ: 12.345.678/0001-95", "") + " CNPJ: 12.345.678/0001-95",
                      TEXTO.replace("Periodo:", "CNPJ: 11.111.111/0001-11 Periodo:"),
                      TEXTO.replace("Periodo: 01/08/2026 ate 31/08/2026", "") + " Periodo: 01/08/2026 ate 31/08/2026"):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                arquivos.validar_resumo_acumulador(texto, "01/08/2026", "31/08/2026")
        with self.assertRaises(ValueError):
            arquivos.validar_resumo_acumulador(TEXTO, "01/08/2026", "31/08/2026", "00000000000000")

    def test_pdf_real_confere_cnpj_preserva_anterior_e_nao_publica_periodo_errado(self):
        with tempfile.TemporaryDirectory() as pasta:
            root = Path(pasta)
            origem = root / "novo.pdf"
            criar_pdf(origem, TEXTO)
            anterior = root / "acumulador_empresa_ficticia_2026-08.pdf"
            anterior.write_bytes(b"anterior")
            final = arquivos.finalizar_pdf(origem, "resumo_acumulador", "01/08/2026", "31/08/2026", CNPJ, "Empresa Fictícia")
            self.assertEqual(final.name, "acumulador_empresa_ficticia_2026-08_2.pdf")
            self.assertEqual(anterior.read_bytes(), b"anterior")
            criar_pdf(origem, TEXTO)
            with self.assertRaises(ValueError):
                arquivos.finalizar_pdf(origem, "resumo_acumulador", "01/09/2026", "30/09/2026", CNPJ, "Empresa Fictícia")
            self.assertTrue(origem.exists())
            self.assertFalse((root / "acumulador_empresa_ficticia_2026-09.pdf").exists())

    def test_migracao_arquiva_roteiro_preserva_ordem_e_nao_restaura_sequencia_editada(self):
        with tempfile.TemporaryDirectory() as pasta:
            repo = RepositorioTarefas(Path(pasta) / "banco.sqlite3")
            repo.configuracao.preparar_piloto()
            antigo = "a" * 32
            with repo.conectar() as banco:
                banco.execute("DELETE FROM marcos_cadastro WHERE id='piloto_lp_lr_resumo_integrado_v4'")
                banco.execute("INSERT INTO rotinas_cadastradas VALUES (?,?,?,?)", (antigo, "Resumo por Acumulador", '[{"tipo":"clicar","valor":"Relatórios"}]', "rascunho"))
                for regime in repo.configuracao.listar(banco)["regimes"]:
                    sequencia = [antigo, "registro_saidas", "resumo_acumulador"]
                    banco.execute("UPDATE regimes SET rotinas=? WHERE id=?", (json.dumps(sequencia), regime["id"]))
            repo.configuracao.preparar_piloto()
            cadastro = repo.configuracao.listar()
            for regime in cadastro["regimes"]:
                self.assertEqual(regime["rotinas"], ["resumo_acumulador", "registro_saidas"])
            with repo.conectar() as banco:
                self.assertIsNotNone(banco.execute("SELECT * FROM rotinas_cadastradas_arquivo WHERE id=?", (antigo,)).fetchone())
            regime = cadastro["regimes"][0]
            repo.configuracao.salvar_regime(regime["id"], regime["nome"], ["registro_saidas"])
            repo.configuracao.preparar_piloto()
            self.assertEqual(repo.configuracao.listar()["regimes"][0]["rotinas"], ["registro_saidas"])


class TestResumoFluxo(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        interacao = types.ModuleType("app.interacao")
        with patch("ctypes.windll", Mock(), create=True), patch.dict("sys.modules", {"app.interacao": interacao}):
            spec = importlib.util.spec_from_file_location("app._resumo_teste", Path(__file__).resolve().parents[1] / "app/dominio.py")
            self.d = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.d)
        from app.estados import AcompanhamentoRotina
        self.rotina = AcompanhamentoRotina("resumo_acumulador", Path(self.pasta.name) / "logs")
        self.stack.enter_context(patch.object(self.d.estados, "AcompanhamentoRotina", return_value=self.rotina))
        self.stack.enter_context(patch.object(self.d.time, "sleep"))
        for nome in ("focar_dominio", "clicar", "clicar_com_desvio", "passar_mouse", "selecionar_tudo_alternativo", "pressionar_atalho", "pressionar_tecla"):
            self.stack.enter_context(patch.object(self.d.interacao, nome, Mock(), create=True))
        self.stack.enter_context(patch.object(self.d.interacao, "identificar_janela_dominio_atual", return_value={"hwnd": 123}, create=True))
        self.esc = self.stack.enter_context(patch.object(self.d.interacao, "pressionar_esc_no_dominio", return_value=True, create=True))
        self.stack.enter_context(patch.object(self.d, "_verificar_retorno_tela_principal", return_value="tela_principal_reconhecida"))
        self.stack.enter_context(patch.object(self.d, "salvar"))
        self.stack.enter_context(patch.object(self.d, "_esperar_item_menu", return_value=(12, 34)))
        self.stack.enter_context(patch.object(self.d, "_esperar_tela_resumo", return_value=("frame", (10, 20))))
        self.stack.enter_context(patch.object(self.d.estados, "esperar_por_estado", return_value=("frame", "previa", (30, 40))))
        self.stack.enter_context(patch.object(self.d.tela, "capturar_tela", return_value="frame"))
        self.stack.enter_context(patch.object(self.d.tela, "recortar_topo", return_value="frame"))
        self.empresa = self.stack.enter_context(patch.object(self.d.tela, "ler_empresa_selecionada", return_value=("Empresa Fictícia", "52")))
        self.stack.enter_context(patch.object(self.d.tela, "achar_texto", return_value=(10, 20)))
        self.stack.enter_context(patch.object(self.d.tela, "achar_texto_ou_no_centro", side_effect=lambda img, alvo, **kw: None if alvo == "does not exist" else (10, 20)))
        self.icone = self.stack.enter_context(patch.object(self.d.tela, "achar_icone_robusto", return_value=(20, 340)))
        self.texto = self.stack.enter_context(patch.object(self.d.tela, "ler_texto", return_value=TEXTO))
        self.campos = self.stack.enter_context(patch.object(self.d, "_ler_campos_resumo", return_value=campos_periodo(dados_ocr())))
        self.caminho = None
        def digitar(valor):
            if valor.endswith(".pdf"):
                self.caminho = Path(valor)
        self.stack.enter_context(patch.object(self.d.interacao, "digitar", side_effect=digitar, create=True))
        def salvar():
            criar_pdf(self.caminho, TEXTO)
        self.stack.enter_context(patch.object(self.d.interacao, "pressionar_enter", side_effect=salvar, create=True))
        self.stack.enter_context(patch.object(self.d, "caminho_visto_pela_sessao_remota", side_effect=str))

    def executar(self, inicio="01/08/2026", fim="31/08/2026"):
        return self.d.gerar_resumo_acumulador(self.pasta.name, inicio, fim)

    def test_fluxo_publica_pdf_real_nomeado_e_exige_retorno_visual(self):
        ok, arquivo = self.executar()
        self.assertTrue(ok)
        self.assertEqual(Path(arquivo).name, "acumulador_empresa_ficticia_2026-08.pdf")
        self.assertEqual(self.rotina.eventos[-1]["status"], "concluido")
        self.assertTrue(any(e["evidence"] == "tela_principal_reconhecida" for e in self.rotina.eventos))
        from app.painel import EstadoPainel
        modelo = EstadoPainel()
        for evento in self.rotina.eventos:
            self.assertTrue(modelo.receber(evento))
        self.assertEqual(modelo.confirmadas, 8)
        self.assertEqual(modelo.retorno, "Tela principal confirmada")
        logs = self.rotina.caminho_log.read_text()
        self.assertNotIn("Empresa Fict", logs)
        self.assertNotIn(self.pasta.name, logs)

    def test_periodo_corrente_ou_campo_nao_confirmado_nao_gera(self):
        self.assertEqual(self.executar("01/08/2026", "01/01/2099"), (False, None))
        self.d.interacao.focar_dominio.assert_not_called()

    def test_campo_nao_localizado_nao_clica_no_ok(self):
        self.campos.side_effect = ValueError("OCR sintetico incompleto")
        self.assertEqual(self.executar(), (False, None))
        self.d.estados.esperar_por_estado.assert_not_called()
        self.icone.assert_not_called()

    def test_digitacao_nao_confirmada_nao_clica_ok(self):
        campos = campos_periodo(dados_ocr())
        campos["inicial"]["valor"] = "01/07/2026"
        self.campos.return_value = campos
        self.assertEqual(self.executar(), (False, None))
        self.d.estados.esperar_por_estado.assert_not_called()
        self.icone.assert_not_called()

    def test_previa_periodo_errado_nao_exporta_e_recupera_sem_sucesso(self):
        self.texto.return_value = TEXTO.replace("01/08/2026 ate 31/08/2026", "01/09/2026 ate 30/09/2026")
        self.assertEqual(self.executar(), (False, None))
        self.icone.assert_not_called()
        self.esc.assert_called_once()
        self.assertEqual(self.rotina.eventos[-1]["status"], "falha")

    def test_codigo_trocado_na_previa_nao_exporta(self):
        self.empresa.side_effect = [("Empresa Fictícia", "52"), ("Outra", "99")]
        self.assertEqual(self.executar(), (False, None))
        self.icone.assert_not_called()

    def test_sem_icone_pdf_nao_usa_offset(self):
        self.icone.return_value = None
        self.assertEqual(self.executar(), (False, None))
        self.d.interacao.pressionar_atalho.assert_not_called()

    def test_pdf_com_periodo_errado_permanece_temporario(self):
        self.d.interacao.pressionar_enter.side_effect = lambda: criar_pdf(self.caminho, TEXTO.replace("01/08/2026", "01/09/2026"))
        self.assertEqual(self.executar(), (False, None))
        self.assertTrue(self.caminho.is_file())
        self.assertFalse((Path(self.pasta.name) / "acumulador_empresa_ficticia_2026-08.pdf").exists())

    def test_pdf_confirmado_com_fechamento_inconclusivo_preserva_arquivo_sem_sucesso(self):
        self.d._verificar_retorno_tela_principal.return_value = "tela_principal_nao_reconhecida"
        ok, arquivo = self.executar()
        self.assertFalse(ok)
        self.assertTrue(Path(arquivo).is_file())
        self.assertEqual(self.rotina.eventos[-1]["status"], "falha")
