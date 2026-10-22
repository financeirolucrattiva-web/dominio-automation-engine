"""Pré-voo do lote: cada checagem devolve OK/ALERTA/ERRO e uma com defeito não esconde as outras."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verificar_ambiente as va


class TestVerificarAmbiente(unittest.TestCase):
    def test_checagem_com_defeito_vira_alerta_e_as_outras_continuam(self):
        def quebra():
            raise RuntimeError("x")
        resultados = va.executar((("a", lambda: (va.OK, "bem")), ("b", quebra), ("c", lambda: (va.ERRO, "mal"))))
        self.assertEqual([r[:2] for r in resultados], [("a", va.OK), ("b", va.ALERTA), ("c", va.ERRO)])

    def test_codigo_de_saida_so_e_1_com_erro(self):
        def rodar(checagens):
            with patch.object(va, "VERIFICACOES", checagens), contextlib.redirect_stdout(io.StringIO()):
                return va.main()
        self.assertEqual(rodar((("a", lambda: (va.OK, "ok")), ("b", lambda: (va.ALERTA, "cuidado")))), 0)
        self.assertEqual(rodar((("a", lambda: (va.ERRO, "mal")),)), 1)

    def test_pasta_de_saida_gravavel_pouco_espaco_e_nao_gravavel(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(va.verificar_pasta_saida(pasta)[0], va.OK)
            self.assertEqual(va.verificar_pasta_saida(pasta, espaco_gb=10**9)[0], va.ALERTA)
            arquivo = Path(pasta) / "arquivo.txt"
            arquivo.write_text("x", encoding="utf-8")
            self.assertEqual(va.verificar_pasta_saida(arquivo)[0], va.ERRO)  # um arquivo, não uma pasta

    def test_servidor_ligado_e_erro_para_o_lote_por_atalho_e_so_informativo_no_resto(self):
        with patch.object(va, "servidor_escutando", return_value=True):
            self.assertEqual(va.verificar_servidor_parado()[0], va.ERRO)
            self.assertEqual(va.verificar_servidor()[0], va.OK)
        with patch.object(va, "servidor_escutando", return_value=False):
            self.assertEqual(va.verificar_servidor_parado()[0], va.OK)

    def test_lote_troca_so_a_checagem_do_servidor(self):
        nomes = [n for n, _ in va.VERIFICACOES_LOTE]
        self.assertEqual(nomes, [n for n, _ in va.VERIFICACOES])
        funcoes = dict(va.VERIFICACOES_LOTE)
        self.assertIs(funcoes["servidor"], va.verificar_servidor_parado)
        self.assertIs(funcoes["Tesseract"], va.verificar_tesseract)

    def test_atalho_da_saida_ativo_invalido_ou_ausente(self):
        from app import atalho_saida
        with patch.object(atalho_saida, "atalho_configurado", return_value=None):
            self.assertEqual(va.verificar_atalho_saida()[0], va.OK)
        with patch.object(atalho_saida, "atalho_configurado", return_value=Path("C:/saida")), \
                patch.object(atalho_saida, "destino_de_navegacao", return_value=Path("C:/saida")):
            self.assertEqual(va.verificar_atalho_saida()[0], va.OK)
        with patch.object(atalho_saida, "atalho_configurado", return_value=Path("C:/saida")), \
                patch.object(atalho_saida, "destino_de_navegacao", return_value=Path("C:/x/saida")):
            self.assertEqual(va.verificar_atalho_saida()[0], va.ALERTA)

    def test_calibracao_ausente_e_erro(self):
        from app import tela_principal
        with patch.object(tela_principal, "carregar_referencia", return_value=None):
            self.assertEqual(va.verificar_calibracao()[0], va.ERRO)
        with patch.object(tela_principal, "carregar_referencia", return_value={"ok": True}):
            self.assertEqual(va.verificar_calibracao()[0], va.OK)


if __name__ == "__main__":
    unittest.main()
