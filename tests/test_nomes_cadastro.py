"""Identificação dos arquivos do painel, somente com empresas sintéticas."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from app.arquivos import nome_relatorio, nomear_relatorio_cadastrado
from app.servidor import RepositorioTarefas, ServicoExecucao
from test_servidor import aguardar, eventos_confirmados, pedido


class TestNomesCadastro(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.root = Path(pasta.name)
        self.saida = self.root / "saida"
        self.saida.mkdir()

    def test_convencao_tipos_nome_periodo_e_extensao(self):
        self.assertEqual(nome_relatorio("Resumo por Acumulador", "Empresa Fictícia", "2026-08-01", "2026-08-31"),
                         "acumulador_empresa_ficticia_2026-08.pdf")
        self.assertEqual(nome_relatorio("registro_entradas", "Empresa / Fictícia", "2026-08-15", "2026-09-02"),
                         "registro_entradas_empresa_ficticia_2026-08_a_2026-09.pdf")
        self.assertEqual(nome_relatorio("efd_contribuicoes", "Empresa Fictícia", "2026-08-01", "2026-08-31", ".TXT"),
                         "efd_contribuicoes_empresa_ficticia_2026-08.txt")
        for nome, extensao in (("../123", ".pdf"), ("Empresa", ".pdf/../txt")):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                nome_relatorio("registro_saidas", nome, "2026-08-01", "2026-08-31", extensao)

    def nomear(self, origem):
        return nomear_relatorio_cadastrado(origem, self.saida, "registro_saidas", "Empresa Fictícia", "2026-08-01", "2026-08-31")

    def test_preserva_anterior_e_conteudo_e_idempotencia(self):
        origem = self.saida / "temporario.pdf"
        origem.write_bytes(b"exportacao sintetica nova")
        anterior = self.saida / "registro_saidas_empresa_ficticia_2026-08.pdf"
        anterior.write_bytes(b"anterior")
        destino = self.nomear(origem)
        self.assertEqual(destino.name, "registro_saidas_empresa_ficticia_2026-08_2.pdf")
        self.assertEqual(destino.read_bytes(), b"exportacao sintetica nova")
        self.assertEqual(anterior.read_bytes(), b"anterior")
        self.assertFalse(origem.exists())
        self.assertEqual(self.nomear(anterior), anterior)

    def test_recusa_caminho_externo_e_symlink_externo(self):
        externo = self.root / "externo.pdf"
        externo.write_bytes(b"fora")
        link = self.saida / "link.pdf"
        link.symlink_to(externo)
        for origem in (externo, link):
            with self.subTest(origem=origem), self.assertRaises(ValueError):
                self.nomear(origem)
        self.assertEqual(externo.read_bytes(), b"fora")

    def test_falha_de_copia_preserva_origem_remove_parcial(self):
        origem = self.saida / "temporario.pdf"
        origem.write_bytes(b"original")
        def falhar(entrada, saida):
            saida.write(b"parcial")
            raise OSError("falha sintetica")
        with patch("app.arquivos.shutil.copyfileobj", side_effect=falhar), self.assertRaises(OSError):
            self.nomear(origem)
        self.assertEqual(origem.read_bytes(), b"original")
        self.assertEqual(list(self.saida.iterdir()), [origem])

    def preparar_worker(self, executor):
        repo = RepositorioTarefas(self.root / "tarefas.sqlite3")
        regime = repo.configuracao.salvar_regime(None, "Lucro Presumido sintético", ["registro_saidas"])
        repo.configuracao.salvar_empresa("52", "Empresa Fictícia", regime["id"])
        servico = ServicoExecucao(repo, executor, modo="simulacao", pasta_saida=self.saida)
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        return repo, servico, regime

    def test_worker_nome_cadastrado_codigo_normalizado_e_arquivo_historico(self):
        origem = self.saida / "nome_lido_no_dominio.pdf"
        origem.write_bytes(b"exportacao sintetica")
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True, str(origem)
        repo, servico, _ = self.preparar_worker(executar)
        tarefa = servico.solicitar({**pedido(), "empresa_codigo": "0052", "capacidade": "registro_saidas"})
        self.assertEqual(aguardar(repo, tarefa["id"])["status"], "concluida")
        destino = Path(repo.obter(tarefa["id"], privado=True)["arquivo"])
        self.assertIn("registro_saidas_empresa_ficticia_", destino.name)
        self.assertEqual(destino.read_bytes(), b"exportacao sintetica")
        self.assertFalse(origem.exists())

    def test_worker_nao_renomeia_emissao_falha_ou_inconclusiva(self):
        origem = self.saida / "diagnostico.pdf"
        origem.write_bytes(b"incompleto")
        repo, servico, _ = self.preparar_worker(lambda dados, receber: (False, str(origem)))
        for resultado, esperado in ((False, "falha"), (True, "nao_confirmada")):
            servico.executor = lambda dados, receber: (resultado, str(origem))
            tarefa = servico.solicitar({**pedido(), "capacidade": "registro_saidas"})
            self.assertEqual(aguardar(repo, tarefa["id"])["status"], esperado)
            self.assertEqual(Path(repo.obter(tarefa["id"], privado=True)["arquivo"]), origem)
            self.assertTrue(origem.exists())

    def test_worker_erro_nome_mantem_original_e_exige_conferencia(self):
        origem = self.root / "fora_da_saida.pdf"
        origem.write_bytes(b"sintetico")
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True, str(origem)
        repo, servico, _ = self.preparar_worker(executar)
        tarefa = servico.solicitar({**pedido(), "capacidade": "registro_saidas"})
        with self.assertLogs("app.servidor", level="ERROR"):
            final = aguardar(repo, tarefa["id"])
        self.assertEqual(final["status"], "nao_confirmada")
        self.assertEqual(final["motivo"], "nome_arquivo_nao_confirmado")
        self.assertEqual(Path(repo.obter(tarefa["id"], privado=True)["arquivo"]), origem)
        self.assertTrue(origem.exists())

    def test_lote_usa_nome_da_revisao_mesmo_apos_edicao(self):
        origem = self.saida / "exportacao.pdf"
        origem.write_bytes(b"sintetico")
        def executar(dados, receber):
            repo.configuracao.salvar_empresa("52", "Empresa Renomeada", regime["id"])
            eventos_confirmados(dados, receber)
            return True, str(origem)
        repo, servico, regime = self.preparar_worker(executar)
        selecao = {"empresas": ["52"], "inicio": "2026-08-01", "fim": "2026-08-31"}
        plano = repo.configuracao.planejar(selecao)
        lote = servico.solicitar_lote({**selecao, "request_id": str(uuid.uuid4()), "apuracao_confirmada": True, "plano_hash": plano["hash"]})
        tarefa = repo.obter_lote(lote["id"])["tarefas"][0]
        self.assertEqual(aguardar(repo, tarefa["id"])["status"], "concluida")
        destino = Path(repo.obter(tarefa["id"], privado=True)["arquivo"])
        self.assertEqual(destino.name, "registro_saidas_empresa_ficticia_2026-08.pdf")


if __name__ == "__main__":
    unittest.main()
