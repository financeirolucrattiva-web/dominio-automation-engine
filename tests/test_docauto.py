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
        self.assertIsNone(docauto.destino(70, "2026-08", "registro_icms", self.CFG, ok))  # ICMS sem rotina no contrato
        self.assertIsNone(docauto.destino(70, "2026-08", "resumo_acumulador", self.CFG, saida(0, caminho="x", existe=False)))
        self.assertIsNone(docauto.destino(70, "2026-08", "resumo_acumulador", self.CFG, saida(2)))

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
