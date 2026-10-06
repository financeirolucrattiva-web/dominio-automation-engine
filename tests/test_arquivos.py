"""Fixtures fiscais inteiramente sintéticas, sem tela ou dados reais."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject

from app.arquivos import finalizar_pdf, nome_livro, validar_livro


CNPJ = "12345678000195"
TEXTO = "REGISTRO DE SAIDAS EMPRESA: EMPRESA FICTICIA CNPJ: 12.345.678/0001-95 01/08/2026 a 31/08/2026 VALORES FISCAIS"


def criar_pdf(caminho, texto=TEXTO):
    escritor = PdfWriter()
    pagina = escritor.add_blank_page(width=600, height=800)
    fonte = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    pagina[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): escritor._add_object(fonte)})})
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 10 Tf 20 700 Td ({texto}) Tj ET".encode("ascii"))
    pagina[NameObject("/Contents")] = escritor._add_object(stream)
    escritor.write(caminho)


class TestArquivos(unittest.TestCase):
    def test_cabecalho_espacado(self):
        self.assertEqual(validar_livro(" ".join(TEXTO), "registro_saidas", "01/08/2026", "31/08/2026"), CNPJ)

    def test_rejeita_tipo_periodo_e_empresa_errados(self):
        for tipo, inicio, fim, esperado in (
            ("registro_entradas", "01/08/2026", "31/08/2026", None),
            ("registro_saidas", "01/09/2026", "30/09/2026", None),
            ("registro_saidas", "01/08/2026", "31/08/2026", "00000000000000"),
        ):
            with self.subTest(tipo=tipo, inicio=inicio, esperado=esperado), self.assertRaises(ValueError):
                validar_livro(TEXTO, tipo, inicio, fim, esperado)

    def test_cnpj_ausente_ambiguo_ou_fora_cabecalho(self):
        for texto in (
            TEXTO.replace("CNPJ: 12.345.678/0001-95", ""),
            TEXTO.replace("01/08", "CNPJ: 11.111.111/0001-11 01/08"),
            TEXTO.replace("CNPJ: 12.345.678/0001-95", "") + " CNPJ: 12.345.678/0001-95",
        ):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                validar_livro(texto, "registro_saidas", "01/08/2026", "31/08/2026")

    def test_mes_completo_intervalo_parcial_e_multimes(self):
        self.assertEqual(nome_livro("registro_saidas", CNPJ, "01/08/2026", "31/08/2026"), f"registro_saidas_{CNPJ}_2026-08.pdf")
        self.assertIn("2026-08-02_a_2026-08-31", nome_livro("registro_saidas", CNPJ, "02/08/2026", "31/08/2026"))
        self.assertIn("2026-08-01_a_2026-09-30", nome_livro("registro_saidas", CNPJ, "01/08/2026", "30/09/2026"))
        with self.assertRaises(ValueError):
            nome_livro("registro_saidas", CNPJ, "31/08/2026", "01/08/2026")

    def test_pdf_real_e_preservacao_anterior(self):
        with tempfile.TemporaryDirectory() as pasta:
            temporario = Path(pasta) / "exportacao_nova.pdf"
            anterior = Path(pasta) / nome_livro("registro_saidas", CNPJ, "01/08/2026", "31/08/2026")
            anterior.write_bytes(b"arquivo anterior preservado")
            criar_pdf(temporario)
            final = finalizar_pdf(temporario, "registro_saidas", "01/08/2026", "31/08/2026")
            self.assertEqual(final.stem, anterior.stem + "_2")
            self.assertEqual(anterior.read_bytes(), b"arquivo anterior preservado")
            self.assertFalse(temporario.exists())
            self.assertTrue(final.read_bytes().startswith(b"%PDF-"))

    def test_antigo_nao_substitui_exportacao_ausente(self):
        with tempfile.TemporaryDirectory() as pasta:
            antigo = Path(pasta) / nome_livro("registro_saidas", CNPJ, "01/08/2026", "31/08/2026")
            criar_pdf(antigo)
            with self.assertRaises(FileNotFoundError):
                finalizar_pdf(Path(pasta) / "exportacao_inexistente.pdf", "registro_saidas", "01/08/2026", "31/08/2026")
            self.assertTrue(antigo.exists())

    def test_pdf_incompleto_e_texto_disfarcado_rejeitados(self):
        with tempfile.TemporaryDirectory() as pasta:
            temporario = Path(pasta) / "exportacao_nova.pdf"
            for conteudo in (TEXTO.encode(), b"%PDF-1.7 incompleto"):
                temporario.write_bytes(conteudo)
                with self.subTest(conteudo=conteudo), self.assertRaises(Exception):
                    finalizar_pdf(temporario, "registro_saidas", "01/08/2026", "31/08/2026")
                self.assertTrue(temporario.exists())
            self.assertEqual(list(Path(pasta).iterdir()), [temporario])


if __name__ == "__main__":
    unittest.main()
