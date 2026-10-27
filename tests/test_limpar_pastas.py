import os
import tempfile
import time
import unittest
from pathlib import Path

import importlib.util

_spec = importlib.util.spec_from_file_location("limpar_pastas", Path(__file__).resolve().parents[1] / "scripts" / "limpar_pastas.py")
limpar_pastas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(limpar_pastas)


def _arquivo(caminho, dias):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"x")
    antigo = time.time() - dias * 86400
    os.utime(caminho, (antigo, antigo))
    return caminho


class TestLimparPastas(unittest.TestCase):
    def test_remove_so_o_antigo_e_nunca_configuracao(self):
        with tempfile.TemporaryDirectory() as t:
            raiz = Path(t)
            velho = _arquivo(raiz / "capturas" / "velha.png", 10)
            novo = _arquivo(raiz / "capturas" / "nova.png", 1)
            anterior = _arquivo(raiz / "saida" / "anteriores" / "a.pdf", 40)
            saida_atual = _arquivo(raiz / "saida" / "atual.pdf", 400)
            config = [_arquivo(raiz / "data" / n, 400) for n in
                      ("docauto.json", "tela_principal.json", "servidor.sqlite3", "servidor_chave.txt")]
            cache = _arquivo(raiz / "app" / "__pycache__" / "m.pyc", 0)
            alvos = limpar_pastas.planejar(raiz)
            nomes = {a.name for a in alvos}
            self.assertTrue({"velha.png", "a.pdf", "__pycache__"} <= nomes)
            for protegido in [novo, saida_atual, *config]:
                self.assertNotIn(protegido.name, nomes)
            self.assertTrue(cache.parent.is_dir())

    def test_gira_log_grande(self):
        with tempfile.TemporaryDirectory() as t:
            raiz = Path(t)
            log = raiz / "data" / "servidor.log"
            log.parent.mkdir()
            log.write_bytes(b"x" * (limpar_pastas.LIMITE_LOG + 1))
            self.assertEqual(limpar_pastas.girar_logs(raiz), [log])
            self.assertTrue((raiz / "data" / "servidor.log.1").is_file())
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
