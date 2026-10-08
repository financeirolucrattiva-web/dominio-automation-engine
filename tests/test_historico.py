"""Persistência real em pasta temporária, inclusive falhas de substituição."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import historico


class TestHistorico(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.arquivo = self.pasta / "historico.json"
        for nome, valor in (("PASTA_DADOS", self.pasta), ("ARQUIVO", self.arquivo)):
            contexto = patch.object(historico, nome, valor)
            contexto.start()
            self.addCleanup(contexto.stop)

    def test_preserva_tres_resultados_e_arquivo_associado(self):
        for sucesso in (True, False, None):
            historico.registrar("Teste", sucesso, arquivo_gerado="simulado.pdf")
        itens = historico.carregar(estrito=True)
        self.assertEqual([item["sucesso"] for item in itens], [True, False, None])
        self.assertEqual(itens[0]["arquivo_gerado"], "simulado.pdf")
        self.assertFalse(list(self.pasta.glob("*.tmp")))

    def test_formatos_invalidos_nao_sobrescrevem_arquivo(self):
        for conteudo in ("{", "{}", "null", '["x"]', '[{"sucesso": true}]'):
            with self.subTest(conteudo=conteudo):
                self.arquivo.write_text(conteudo, encoding="utf-8")
                self.assertEqual(historico.carregar(), [])
                with self.assertRaises(ValueError):
                    historico.registrar("Teste", True)
                self.assertEqual(self.arquivo.read_text(), conteudo)

    def test_falha_na_substituicao_preserva_historico_anterior(self):
        historico.registrar("Anterior", False)
        anterior = self.arquivo.read_bytes()
        with patch.object(historico.os, "replace", side_effect=OSError("falha de disco")):
            with self.assertRaises(OSError):
                historico.registrar("Novo", True)
        self.assertEqual(self.arquivo.read_bytes(), anterior)
        self.assertFalse(list(self.pasta.glob("*.tmp")))

    def test_limita_historico_sem_perder_resultado_mais_recente(self):
        with patch.object(historico, "MAXIMO_REGISTROS", 2):
            for nome in ("A", "B", "C"):
                historico.registrar(nome, None)
        self.assertEqual([item["rotina"] for item in historico.carregar()], ["B", "C"])

    def test_booleano_invalido_nao_vira_ok(self):
        for valor in ("false", "OK", 1, [], {}):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                historico.registrar("Teste", valor)
        self.assertFalse(self.arquivo.exists())

    def test_arquivo_ausente_e_legacy_booleanos_sao_suportados(self):
        self.assertEqual(historico.carregar(estrito=True), [])
        registro = {"quando": "07/10/2026 12:00:00", "rotina": "SPED Fiscal", "sucesso": True}
        self.arquivo.write_text(json.dumps([registro]))
        self.assertEqual(historico.carregar(estrito=True), [registro])
