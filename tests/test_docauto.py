import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app import docauto


def saida(rc=0, **dados):
    return lambda *a, **k: SimpleNamespace(returncode=rc, stdout=json.dumps(dados))


class TestDocauto(unittest.TestCase):
    CFG = {"python": "py.exe", "cwd": "app"}

    def test_destino_so_com_exit_zero_e_pasta_existente(self):
        self.assertEqual(docauto.destino(70, "2026-08", "livro_x", self.CFG), None)  # rotina fora do contrato
        ok = saida(caminho="D:/c/70/2026/08", existe=True)
        self.assertEqual(docauto.destino(70, "2026-08", "registro_entradas", self.CFG, ok), Path("D:/c/70/2026/08"))
        chamadas = []
        docauto.destino(70, "2026-08", "registro_icms", self.CFG, lambda cmd, **k: chamadas.append(cmd) or ok())
        self.assertEqual(chamadas[0][-3:-1], ["--tipo", "APURACAO_ICMS"])  # apuração vai por --tipo
        self.assertIsNone(docauto.destino(70, "2026-08", "resumo_acumulador", self.CFG, saida(0, caminho="x", existe=False)))
        self.assertIsNone(docauto.destino(70, "2026-08", "resumo_acumulador", self.CFG, saida(2)))

    def test_txt_vai_para_a_subpasta_do_tipo_quando_ela_existe(self):
        with tempfile.TemporaryDirectory() as raiz:
            decl = Path(raiz) / "DECLARAÇÕES"
            for nome in ("SPED_FISCAL", "SPED_CONTRIBUIÇÕES", "DCTFWEB", "REINF"):
                (decl / nome).mkdir(parents=True)
            ok = saida(caminho=str(decl), existe=True)
            self.assertEqual(docauto.destino(68, "2026-09", "sped_fiscal", self.CFG, ok), decl / "SPED_FISCAL")
            self.assertEqual(docauto.destino(68, "2026-09", "efd_contribuicoes", self.CFG, ok),
                             decl / "SPED_CONTRIBUIÇÕES")
            # sem subpasta própria (ou ambígua) fica na pasta que o docauto indicou
            vazia = Path(raiz) / "outra"
            vazia.mkdir()
            self.assertEqual(docauto.destino(68, "2026-09", "sped_fiscal", self.CFG,
                                             saida(caminho=str(vazia), existe=True)), vazia)
            (decl / "SPED FISCAL 2").mkdir()
            self.assertEqual(docauto.destino(68, "2026-09", "sped_fiscal", self.CFG, ok), decl)
            # outros tipos não mudam
            self.assertEqual(docauto.destino(68, "2026-09", "resumo_acumulador", self.CFG, ok), decl)

    def test_comando_usa_rotina_do_contrato_e_nunca_levanta(self):
        chamadas = []

        def executar(cmd, **k):
            chamadas.append((cmd, k))
            raise OSError("sem python")
        self.assertIsNone(docauto.destino(70, "2026-08", "registro_saidas", self.CFG, executar))
        cmd, k = chamadas[0]
        self.assertEqual(cmd[-3:-1], ["--rotina", "livro_saidas"])
        self.assertEqual(k["env"]["PYTHONPATH"], "src")

    def test_sem_configuracao_nao_faz_nada(self):
        with tempfile.TemporaryDirectory() as p:
            from unittest.mock import patch
            with patch.object(docauto, "ARQUIVO", Path(p) / "nao.json"):
                self.assertIsNone(docauto.destino(70, "2026-08", "resumo_acumulador"))
                self.assertFalse(docauto.registrar_resultado(70, "2026-08", "resumo_acumulador", "concluida", "x"))

    def test_resultado_automacao_cabecalho_bom_sha_e_acumula(self):
        with tempfile.TemporaryDirectory() as p:
            pdf = Path(p) / "a.pdf"
            pdf.write_bytes(b"%PDF-1")
            cfg = {**self.CFG, "resultado_automacao": str(Path(p) / "sub" / "resultado_automacao.csv")}
            self.assertTrue(docauto.registrar_resultado(70, "2026-08", "registro_entradas", "concluida", pdf, cfg))
            self.assertTrue(docauto.registrar_resultado(70, "2026-08", "resumo_acumulador", "concluida", pdf, cfg))
            bruto = Path(cfg["resultado_automacao"]).read_bytes()
            self.assertTrue(bruto.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(bruto.count(b"\xef\xbb\xbf"), 1)
            linhas = list(csv.reader(bruto.decode("utf-8-sig").splitlines(), delimiter=";"))
            self.assertEqual(linhas[0], docauto.CABECALHO)
            self.assertEqual(linhas[1][:4], ["70", "2026-08", "livro_entradas", "concluida"])
            self.assertEqual(len(linhas[1][5]), 64)
            self.assertEqual(len(linhas), 3)


if __name__ == "__main__":
    unittest.main()


class TestEmpresaSemCadastro(unittest.TestCase):
    def test_publica_na_pasta_do_docauto_mesmo_sem_cadastro_no_painel(self):
        from unittest import mock
        import app.servidor as modulo
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            saida, final = raiz / "saida", raiz / "final"
            saida.mkdir()
            final.mkdir()
            pdf = saida / "x.pdf"
            pdf.write_bytes(b"%PDF-1.4 teste")
            alvo = SimpleNamespace(pasta_saida=saida)
            pedido = {"empresa_codigo": "19", "inicio": "2026-08-01", "fim": "2026-08-31"}
            registros = []
            with mock.patch.object(docauto, "destino", return_value=final), \
                 mock.patch.object(docauto, "registrar_resultado", lambda *a, **k: registros.append(a)):
                novo = modulo.ServicoExecucao._publicar_sem_cadastro(alvo, pedido, pdf, "resumo_acumulador")
            self.assertTrue(Path(novo).is_file())
            self.assertEqual(Path(novo).parent, final.resolve())
            self.assertEqual(len(registros), 1)

    def test_sem_destino_mantem_arquivo(self):
        from unittest import mock
        import app.servidor as modulo
        pedido = {"empresa_codigo": "19", "inicio": "2026-08-01", "fim": "2026-08-31"}
        with mock.patch.object(docauto, "destino", return_value=None):
            self.assertEqual(modulo.ServicoExecucao._publicar_sem_cadastro(
                SimpleNamespace(pasta_saida=Path(".")), pedido, "a.pdf", "resumo_acumulador"), "a.pdf")


class TestLocalizarEfd(unittest.TestCase):
    PEDIDO = {"inicio": "2026-08-01", "fim": "2026-08-31"}

    def _rodar(self, arquivos_txt):
        import datetime as dt
        import app.servidor as modulo
        with tempfile.TemporaryDirectory() as raiz:
            for nome, texto in arquivos_txt.items():
                (Path(raiz) / nome).write_text(texto, encoding="latin-1")
            tarefa = {"criado": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()}
            achado = modulo.ServicoExecucao._localizar_efd(SimpleNamespace(pasta_saida=raiz), tarefa, self.PEDIDO)
            return Path(achado).name if achado else None

    def test_sped_fiscal_usa_as_posicoes_do_0000_da_efd_icms_ipi(self):
        import datetime as dt
        import app.servidor as modulo
        with tempfile.TemporaryDirectory() as raiz:
            (Path(raiz) / "S.txt").write_text("|0000|017|0|01082026|31082026|X|1|MT|", encoding="latin-1")
            tarefa = {"criado": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()}
            pedido = dict(self.PEDIDO, capacidade="sped_fiscal")
            achado = modulo.ServicoExecucao._localizar_efd(SimpleNamespace(pasta_saida=raiz), tarefa, pedido)
            self.assertEqual(Path(achado).name, "S.txt")
            # o mesmo arquivo não vale como EFD Contribuições (posições diferentes)
            pedido["capacidade"] = "efd_contribuicoes"
            self.assertIsNone(modulo.ServicoExecucao._localizar_efd(SimpleNamespace(pasta_saida=raiz), tarefa, pedido))

    def test_sped_fiscal_tem_destino_pelo_template_e_csv_com_nome_da_rotina(self):
        self.assertEqual(docauto.ROTINAS["sped_fiscal"], "RECIBO_EFD_ICMS")
        self.assertIn("RECIBO_EFD_ICMS", docauto._COMO_TIPO)

    def test_acha_o_unico_txt_do_periodo(self):
        self.assertEqual(self._rodar({"A.txt": "|0000|006|0|||01082026|31082026|X|1|MT|\n"}), "A.txt")

    def test_periodo_diferente_nao_publica(self):
        self.assertIsNone(self._rodar({"A.txt": "|0000|006|0|||01072026|31072026|X|1|MT|\n"}))
        igual = "|0000|006|0|||01082026|31082026|X|1|MT|\n"
        self.assertIn(self._rodar({"A.txt": igual, "B.txt": igual}), ("A.txt", "B.txt"))  # vale o mais recente


class TestErroDdeAcrobat(unittest.TestCase):
    def test_reconhece_mensagem_do_erro(self):
        from app import interacao
        self.assertTrue(interacao._texto_confirma_erro_dde("Fatal Error\nAcrobat failed to send a DDE command.\nOK"))
        self.assertFalse(interacao._texto_confirma_erro_dde("Fatal Error\nOutro problema qualquer"))
