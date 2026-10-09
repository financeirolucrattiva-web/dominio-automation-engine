"""Pastas/CSV/SQLite/API reais, exclusivamente dados e documentos sintéticos."""

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from app import destinos_livros
from app.servidor import RepositorioTarefas, ServicoExecucao
from test_servidor import aguardar, eventos_confirmados, pedido

WEB = all(importlib.util.find_spec(nome) for nome in ("fastapi", "httpx"))
if WEB:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app


class TestDestinosLivros(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.root = Path(pasta.name)
        self.dados = self.root / "data"
        self.dados.mkdir()
        self.raiz = self.root / "raiz_empresas"
        self.relativa = "1 LUCRO REAL E LUCRO PRESUMIDO/1.6 EMPRESA FICTICIA"
        self.base = self.raiz.joinpath(*self.relativa.split("/"))
        (self.base / "2026" / "FISCAL").mkdir(parents=True)
        (self.dados / "destino_livros.json").write_text(json.dumps({"raiz": str(self.raiz)}))
        self.empresa = {"codigo": "52", "nome": "Empresa Fictícia", "pasta_relativa": self.relativa}

    def planejar(self, **kwargs):
        return destinos_livros.planejar_destino(self.empresa, "Lucro Presumido", "2026-08", self.dados,
                                                hoje=dt.date(2026, 10, 9), **kwargs)

    def test_previa_nao_cria_pastas_e_usa_nome_cadastrado(self):
        plano = self.planejar()
        destino = self.base / "2026/FISCAL/08/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS"
        self.assertEqual(Path(plano["caminho_local"]), destino)
        self.assertFalse(destino.exists())
        self.assertEqual(plano["arquivos_previstos"], [
            "registro_entradas_empresa_ficticia_2026-08.pdf",
            "registro_saidas_empresa_ficticia_2026-08.pdf", "livro_icms_empresa_ficticia_2026-08.pdf"])

    def test_teste_gravacao_cria_destino_remove_temporario_preserva_anteriores(self):
        plano = self.planejar()
        destino = Path(plano["caminho_local"])
        destino.mkdir(parents=True)
        anterior = destino / "anterior.pdf"
        anterior.write_bytes(b"arquivo sintetico anterior")
        resultado = destinos_livros.testar_gravacao(plano)
        self.assertTrue(resultado["gravacao_confirmada"])
        self.assertFalse(resultado["emissao_fiscal_testada"])
        self.assertEqual(list(destino.iterdir()), [anterior])
        self.assertEqual(anterior.read_bytes(), b"arquivo sintetico anterior")

    def test_empresa_sem_pasta_de_ano_usa_estrutura_existente(self):
        (self.base / "2026/FISCAL").rmdir()
        (self.base / "2026").rmdir()
        (self.base / "FISCAL").mkdir()
        self.assertEqual(Path(self.planejar()["caminho_local"]), self.base / "FISCAL/08/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS")

    def test_mapa_local_por_codigo_sem_deduzir_regime(self):
        self.empresa["pasta_relativa"] = ""
        (self.dados / "mapa_pastas_empresas.csv").write_text(
            "codigo_dominio;razao_social;cnpj;regime_pasta;pasta_relativa_a_raiz;anos_existentes\n"
            f"00052;Nome diferente no mapa;00000000000000;Pasta compartilhada;{self.relativa};2026\n", encoding="utf-8-sig")
        plano = self.planejar()
        self.assertEqual(plano["origem"], "mapa_local")
        self.assertEqual(plano["empresa"], "Empresa Fictícia")
        self.assertEqual(plano["regime"], "Lucro Presumido")

    def test_codigo_duplicado_no_mapa_e_pasta_ausente_sao_recusados(self):
        self.empresa["pasta_relativa"] = ""
        (self.dados / "mapa_pastas_empresas.csv").write_text(
            f"codigo_dominio;pasta_relativa_a_raiz\n52;{self.relativa}\n052;Outra\n")
        with self.assertRaises(ValueError):
            self.planejar()
        self.empresa["pasta_relativa"] = "Empresa inexistente"
        with self.assertRaises(ValueError):
            self.planejar()

    def test_pastas_invalidas_e_escape_por_link_sao_recusados(self):
        for pasta in ("../outra", "C:\\Users\\exemplo", "/tmp/outra", "empresa//pasta", "NUL", "empresa/..", "empresa/arquivo."):
            with self.subTest(pasta=pasta), self.assertRaises(ValueError):
                destinos_livros.caminho_relativo(pasta, False)
        externo = self.root / "externo"
        (externo / "2026/FISCAL").mkdir(parents=True)
        (self.raiz / "link").symlink_to(externo, target_is_directory=True)
        self.empresa["pasta_relativa"] = "link"
        with self.assertRaises(ValueError):
            self.planejar()

    def test_raiz_nao_configurada_e_estrutura_incompleta_nao_sao_inventadas(self):
        (self.base / "2026/FISCAL").rmdir()
        with self.assertRaises(ValueError):
            self.planejar()
        (self.dados / "destino_livros.json").unlink()
        with self.assertRaises(ValueError):
            self.planejar()

    def test_regimes_e_datas_fora_do_piloto_recusados(self):
        for regime, mes in (("Simples Nacional", "2026-08"), ("Lucro Presumido", "2026-10"), ("Lucro Real", "0000-08")):
            with self.subTest(regime=regime, mes=mes), self.assertRaises(ValueError):
                destinos_livros.planejar_destino(self.empresa, regime, mes, self.dados, dt.date(2026, 10, 9))

    def test_subpasta_personalizada_e_presumido_real_compartilham_raiz(self):
        self.empresa["subpasta_livros"] = "RELATORIOS_APURAÇÃO/MEUS_LIVROS"
        lp = self.planejar()
        lr = destinos_livros.planejar_destino(self.empresa, "Lucro Real", "2026-08", self.dados)
        self.assertEqual(lp["caminho_local"], lr["caminho_local"])
        self.assertTrue(lp["caminho_local"].endswith("MEUS_LIVROS"))

    def test_migracao_preserva_empresa_antiga_e_cadastro_sem_campos_preserva_pasta(self):
        banco = self.dados / "antigo.sqlite3"
        with sqlite3.connect(banco) as conexao:
            conexao.execute("CREATE TABLE empresas_painel(codigo TEXT PRIMARY KEY,nome TEXT NOT NULL,regime_id TEXT NOT NULL)")
            conexao.execute("INSERT INTO empresas_painel VALUES ('52','Empresa antiga','regime')")
        repo = RepositorioTarefas(banco)
        self.assertEqual(repo.configuracao.listar()["empresas"][0]["nome"], "Empresa antiga")
        regime = repo.configuracao.salvar_regime(None, "Lucro Presumido", ["registro_entradas"])
        repo.configuracao.salvar_empresa("52", "Empresa", regime["id"], self.relativa, "MEUS_LIVROS")
        empresa = repo.configuracao.salvar_empresa("52", "Novo nome", regime["id"])
        self.assertEqual(empresa["pasta_relativa"], self.relativa)
        self.assertEqual(empresa["subpasta_livros"], "MEUS_LIVROS")

    def preparar_execucao(self):
        self.saida = self.root / "saida"
        self.saida.mkdir()
        self.origem = self.saida / "exportacao.pdf"
        self.origem.write_bytes(b"documento fiscal sintetico, sem validade")
        repo = RepositorioTarefas(self.dados / "banco.sqlite3")
        regime = repo.configuracao.salvar_regime(None, "Lucro Presumido", ["registro_entradas"])
        repo.configuracao.salvar_empresa("52", "Empresa Fictícia", regime["id"], self.relativa)
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True, str(self.origem)
        servico = ServicoExecucao(repo, executar, "simulacao", pasta_saida=self.saida)
        return repo, servico, regime

    def pedido_livro(self):
        return {**pedido(), "empresa_codigo": "52", "capacidade": "registro_entradas",
                "inicio": "2026-08-01", "fim": "2026-08-31"}

    def test_worker_publica_ao_final_sem_sobrescrever_documento_anterior(self):
        repo, servico, _ = self.preparar_execucao()
        destino = Path(self.planejar()["caminho_local"])
        destino.mkdir(parents=True)
        anterior = destino / "registro_entradas_empresa_ficticia_2026-08.pdf"
        anterior.write_bytes(b"anterior")
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        tarefa = servico.solicitar(self.pedido_livro())
        self.assertEqual(aguardar(repo, tarefa["id"])["status"], "concluida")
        arquivo = Path(repo.obter(tarefa["id"], privado=True)["arquivo"])
        self.assertEqual(arquivo, destino / "registro_entradas_empresa_ficticia_2026-08_2.pdf")
        self.assertEqual(arquivo.read_bytes(), b"documento fiscal sintetico, sem validade")
        self.assertEqual(anterior.read_bytes(), b"anterior")
        self.assertTrue(repo.arquivo_publicado_permitido(tarefa["id"], arquivo))
        self.assertFalse(repo.arquivo_publicado_permitido(tarefa["id"], anterior))
        self.assertFalse(self.origem.exists())

    def test_falha_copia_final_preserva_origem_e_remove_parcial(self):
        repo, servico, _ = self.preparar_execucao()
        tarefa, _ = repo.criar(self.pedido_livro())
        def falhar(entrada, saida):
            saida.write(b"parcial")
            raise OSError("falha sintetica")
        with patch("app.arquivos.shutil.copyfileobj", side_effect=falhar), self.assertRaises(OSError):
            servico._nomear_arquivo(tarefa, self.pedido_livro(), self.origem)
        self.assertTrue(self.origem.exists())
        self.assertEqual(list(Path(self.planejar()["caminho_local"]).iterdir()), [])

    def test_periodo_multimes_nao_escolhe_um_destino_arbitrario(self):
        repo, servico, _ = self.preparar_execucao()
        dados = {**self.pedido_livro(), "fim": "2026-09-30"}
        tarefa, _ = repo.criar(dados)
        with self.assertRaises(ValueError):
            servico._nomear_arquivo(tarefa, dados, self.origem)
        self.assertTrue(self.origem.exists())
        self.assertFalse(Path(self.planejar()["caminho_local"]).exists())

    def test_lote_usa_pasta_revisada_antes_de_edicao_da_empresa(self):
        repo, servico, regime = self.preparar_execucao()
        def executar(dados, receber):
            repo.configuracao.salvar_empresa("52", "Renomeada", regime["id"], "Empresa inexistente", "OUTROS")
            eventos_confirmados(dados, receber)
            return True, str(self.origem)
        servico.executor = executar
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        selecao = {"empresas": ["52"], "inicio": "2026-08-01", "fim": "2026-08-31"}
        plano = repo.configuracao.planejar(selecao)
        lote = servico.solicitar_lote({**selecao, "request_id": str(uuid.uuid4()),
                                      "apuracao_confirmada": True, "plano_hash": plano["hash"]})
        tarefa = repo.obter_lote(lote["id"])["tarefas"][0]
        self.assertEqual(aguardar(repo, tarefa["id"])["status"], "concluida")
        arquivo = Path(repo.obter(tarefa["id"], privado=True)["arquivo"])
        self.assertEqual(arquivo.parent, Path(self.planejar()["caminho_local"]))
        self.assertEqual(arquivo.name, "registro_entradas_empresa_ficticia_2026-08.pdf")

    @unittest.skipUnless(WEB, "Componentes da API ausentes")
    def test_download_so_autoriza_pdf_publicado_e_sobrevive_a_reconfiguracao(self):
        repo, servico, _ = self.preparar_execucao()
        headers = {"Authorization": "Bearer " + "d" * 48}
        with TestClient(criar_app(servico, "d" * 48, pasta_saida=self.saida)) as cliente:
            tarefa = cliente.post("/api/tarefas", json=self.pedido_livro(), headers=headers).json()
            self.assertEqual(aguardar(repo, tarefa["id"])["status"], "concluida")
            arquivo = Path(repo.obter(tarefa["id"], privado=True)["arquivo"])
            (self.dados / "destino_livros.json").unlink()
            rota = f"/api/tarefas/{tarefa['id']}/arquivo"
            resposta = cliente.get(rota, headers=headers)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.content, b"documento fiscal sintetico, sem validade")
            self.assertIn(arquivo.name, resposta.headers["content-disposition"])
            outro = arquivo.parent / "privado.txt"
            outro.write_bytes(b"PRIVADO")
            repo.concluir(tarefa["id"], "concluida", True, arquivo=outro)
            resposta = cliente.get(rota, headers=headers)
            self.assertEqual(resposta.status_code, 404)
            self.assertNotIn("PRIVADO", resposta.text)
            repo.concluir(tarefa["id"], "concluida", True, arquivo=arquivo)
            arquivo.unlink()
            arquivo.symlink_to(outro)
            self.assertEqual(cliente.get(rota, headers=headers).status_code, 404)

    @unittest.skipUnless(WEB, "Componentes da API ausentes")
    def test_api_cadastro_preview_gravacao_e_autenticacao(self):
        repo = RepositorioTarefas(self.dados / "banco.sqlite3")
        regime = repo.configuracao.salvar_regime(None, "Lucro Presumido", ["registro_entradas"])
        servico = ServicoExecucao(repo)
        headers = {"Authorization": "Bearer " + "d" * 48}
        with TestClient(criar_app(servico, "d" * 48)) as cliente:
            empresa = {"codigo": "52", "nome": "Empresa Fictícia", "regime_id": regime["id"], "pasta_relativa": self.relativa}
            self.assertEqual(cliente.post("/api/empresas", json=empresa, headers=headers).status_code, 200)
            caminho = "/api/empresas/52/destino-livros"
            self.assertEqual(cliente.post(caminho, json={"competencia": "2026-08"}).status_code, 401)
            previa = cliente.post(caminho, json={"competencia": "2026-08"}, headers=headers)
            self.assertEqual(previa.status_code, 200)
            self.assertFalse(Path(previa.json()["caminho_local"]).exists())
            teste = cliente.post(caminho, json={"competencia": "2026-08", "testar_gravacao": True}, headers=headers)
            self.assertEqual(teste.status_code, 200)
            self.assertTrue(teste.json()["gravacao_confirmada"])
            self.assertFalse(teste.json()["emissao_fiscal_testada"])
            self.assertEqual(repo.listar(), [])
            self.assertEqual(list(Path(teste.json()["caminho_local"]).iterdir()), [])
