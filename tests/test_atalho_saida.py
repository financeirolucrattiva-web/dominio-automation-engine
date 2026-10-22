"""Atalho curto (junção) para a pasta de saída: só vale se apontar para a MESMA pasta."""
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import atalho_saida
from scripts import configurar_atalho_saida as configurar


def _raiz_da_unidade():
    return Path(os.environ.get("SystemDrive", "C:") + "\\")


@unittest.skipUnless(sys.platform == "win32", "junção NTFS só no Windows")
class TestAtalhoSaida(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.base = Path(pasta.name)
        self.saida = self.base / "projeto" / "saida"
        self.saida.mkdir(parents=True)
        self.config = self.base / "atalho_saida.txt"
        self.alias = _raiz_da_unidade() / ("teste_atalho_" + uuid.uuid4().hex[:8])
        self.addCleanup(self._limpar_alias)

    def _limpar_alias(self):
        try:
            if self.alias.exists():
                os.rmdir(self.alias)  # apagar a junção não apaga a pasta de destino
        except OSError:
            pass

    def criar_junção(self):
        resultado = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.alias), str(self.saida)],
                                   capture_output=True, text=True)
        if resultado.returncode != 0:
            self.skipTest("sem permissão para criar a junção na raiz da unidade")

    def test_sem_configuracao_usa_o_caminho_completo(self):
        self.assertEqual(atalho_saida.destino_de_navegacao(self.saida, self.config), self.saida)

    def test_junção_para_a_mesma_pasta_e_usada(self):
        self.criar_junção()
        self.config.write_text(str(self.alias) + "\n", encoding="utf-8")
        self.assertEqual(atalho_saida.destino_de_navegacao(self.saida, self.config), self.alias)

    def test_config_com_bom_do_bloco_de_notas_funciona(self):
        self.criar_junção()
        self.config.write_bytes(b"\xef\xbb\xbf" + str(self.alias).encode("utf-8"))
        self.assertEqual(atalho_saida.destino_de_navegacao(self.saida, self.config), self.alias)

    def test_atalho_que_aponta_para_outra_pasta_e_recusado(self):
        self.criar_junção()
        outra = self.base / "outra"
        outra.mkdir()
        self.config.write_text(str(self.alias), encoding="utf-8")
        self.assertEqual(atalho_saida.destino_de_navegacao(outra, self.config), outra)

    def test_atalho_inexistente_ou_pasta_comum_diferente_e_recusado(self):
        self.config.write_text(str(self.alias), encoding="utf-8")  # nao existe
        self.assertEqual(atalho_saida.destino_de_navegacao(self.saida, self.config), self.saida)
        comum = _raiz_da_unidade() / ("comum_" + uuid.uuid4().hex[:8])
        try:
            comum.mkdir()
        except OSError:
            self.skipTest("sem permissão na raiz da unidade")
        self.addCleanup(lambda: os.rmdir(comum))
        self.config.write_text(str(comum), encoding="utf-8")
        self.assertEqual(atalho_saida.destino_de_navegacao(self.saida, self.config), self.saida)

    def test_caminho_na_sessao_remota_troca_so_a_letra_e_nao_resolve_a_junção(self):
        self.assertEqual(atalho_saida.caminho_na_sessao_remota(Path("C:\\saida"), "M"), "M:\\saida")
        self.assertEqual(atalho_saida.caminho_na_sessao_remota(Path("C:\\saida"), "m:"), "m:\\saida")
        self.criar_junção()
        self.assertEqual(atalho_saida.caminho_na_sessao_remota(self.alias, "M"), "M:\\" + self.alias.name)

    def test_criar_faz_a_junção_grava_a_config_e_e_idempotente(self):
        configurar.criar(self.alias, self.saida, arquivo=self.config)
        self.assertEqual(self.config.read_text(encoding="utf-8").strip(), str(self.alias))
        self.assertEqual(self.alias.resolve(), self.saida.resolve())
        configurar.criar(self.alias, self.saida, arquivo=self.config)  # de novo: sem erro
        (self.saida / "a.pdf").write_bytes(b"x")
        self.assertTrue((self.alias / "a.pdf").exists())  # é a MESMA pasta

    def test_criar_recusa_alias_existente_que_nao_e_a_saida_e_alias_fora_da_raiz(self):
        outra = _raiz_da_unidade() / ("outra_" + uuid.uuid4().hex[:8])
        try:
            outra.mkdir()
        except OSError:
            self.skipTest("sem permissão na raiz da unidade")
        self.addCleanup(lambda: os.rmdir(outra))
        with self.assertRaises(ValueError):
            configurar.criar(outra, self.saida, arquivo=self.config)
        self.assertFalse(self.config.exists())
        with self.assertRaises(ValueError):
            configurar.criar(self.base / "fundo" / "atalho", self.saida, arquivo=self.config)

    def test_remover_so_apaga_a_config(self):
        configurar.criar(self.alias, self.saida, arquivo=self.config)
        self.assertTrue(configurar.remover(self.config))
        self.assertFalse(configurar.remover(self.config))
        self.assertTrue(self.alias.exists())  # a junção fica; só deixou de ser usada

    def test_falha_do_mklink_nao_grava_a_config(self):
        falso = subprocess.CompletedProcess([], 1, stdout="", stderr="acesso negado")
        with patch.object(configurar.subprocess, "run", return_value=falso):
            with self.assertRaises(ValueError):
                configurar.criar(self.alias, self.saida, executar=configurar.subprocess.run, arquivo=self.config)
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
