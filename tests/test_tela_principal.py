"""Percepção pura em imagens sintéticas; nenhum dado ou print de cliente."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from app import tela_principal


def tela_vazia(cor=(38, 94, 172)):
    """Janela fictícia: corpo vazio, cabeçalho, lateral e rodapé distintos."""
    imagem = Image.new("RGB", (1000, 700), (20, 40, 75))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((0, 90, 959, 649), fill=cor)
    desenho.text((750, 30), "EMPRESA FICTICIA - 1", fill="white")
    desenho.text((750, 55), "JAN/2020", fill="white")
    desenho.rectangle((970, 130, 990, 155), fill="white")
    desenho.rectangle((0, 670, 999, 699), fill=(220, 235, 240))
    return imagem


class TestTelaPrincipal(unittest.TestCase):
    def setUp(self):
        self.imagem = tela_vazia()
        self.referencia = tela_principal.construir_referencia(self.imagem)

    def test_mede_cor_e_limites_sem_guardar_cabecalho_ou_controles(self):
        self.assertEqual(self.referencia, {
            "versao": 1,
            "tamanho": [1000, 700],
            "retangulo": [0, 90, 960, 650],
            "cor_rgb": [38, 94, 172],
        })
        self.assertTrue(tela_principal.corresponde(self.imagem, self.referencia))
        self.assertEqual(self.imagem.crop(tuple(self.referencia["retangulo"])).getextrema(), ((38, 38), (94, 94), (172, 172)))

    def test_mede_outro_azul_sem_assumir_rgb_fixo(self):
        nova = tela_vazia((55, 110, 195))
        referencia = tela_principal.construir_referencia(nova)
        self.assertEqual(referencia["cor_rgb"], [55, 110, 195])
        self.assertTrue(tela_principal.corresponde(nova, referencia))
        self.assertFalse(tela_principal.corresponde(nova, self.referencia))

    def test_pdf_e_dialogo_recusados_pelo_mesmo_retangulo(self):
        for caixa in ((120, 130, 870, 630), (350, 260, 700, 450)):
            with self.subTest(caixa=caixa):
                imagem = self.imagem.copy()
                ImageDraw.Draw(imagem).rectangle(caixa, fill="white")
                self.assertFalse(tela_principal.corresponde(imagem, self.referencia))
                with self.assertRaises(ValueError):
                    tela_principal.construir_referencia(imagem)

    def test_modal_pequeno_e_ate_um_pixel_nao_somem_na_media(self):
        imagem = self.imagem.copy()
        ImageDraw.Draw(imagem).rectangle((450, 320, 465, 335), fill="white")
        self.assertFalse(tela_principal.corresponde(imagem, self.referencia))
        with self.assertRaises(ValueError):
            tela_principal.construir_referencia(imagem)
        imagem = self.imagem.copy()
        imagem.putpixel((500, 400), (39, 94, 172))
        self.assertFalse(tela_principal.corresponde(imagem, self.referencia))

    def test_painel_lateral_amplo_nao_pode_virar_calibracao_parcial(self):
        imagem = self.imagem.copy()
        ImageDraw.Draw(imagem).rectangle((850, 90, 959, 649), fill="white")
        self.assertFalse(tela_principal.corresponde(imagem, self.referencia))
        with self.assertRaises(ValueError):
            tela_principal.construir_referencia(imagem)

    def test_cor_branca_dominante_nao_e_canvas(self):
        with self.assertRaises(ValueError):
            tela_principal.construir_referencia(Image.new("RGB", self.imagem.size, "white"))

    def test_cor_neutra_ou_outra_matiz_nao_e_canvas(self):
        for cor in ((120, 120, 120), (40, 170, 90), (180, 50, 70)):
            with self.subTest(cor=cor), self.assertRaises(ValueError):
                tela_principal.construir_referencia(tela_vazia(cor))

    def test_dimensao_diferente_requer_nova_calibracao(self):
        self.assertFalse(tela_principal.corresponde(self.imagem.resize((1200, 840)), self.referencia))

    def test_mudanca_de_empresa_fora_do_corpo_nao_guarda_identidade(self):
        imagem = self.imagem.copy()
        ImageDraw.Draw(imagem).rectangle((700, 0, 999, 80), fill="black")
        self.assertTrue(tela_principal.corresponde(imagem, self.referencia))
        self.assertEqual(tela_principal.construir_referencia(imagem), self.referencia)

    def test_metadados_invalidos_nunca_reconhecem(self):
        casos = [None, {}, "invalido"]
        for chave, valor in (
            ("versao", 2), ("versao", True), ("tamanho", [1000, 0]),
            ("tamanho", [1000.0, 700]), ("retangulo", [-1, 90, 960, 650]),
            ("retangulo", [0, 90, 1001, 650]), ("retangulo", [0, 90, 80, 650]),
            ("cor_rgb", [255, 255, 255]), ("cor_rgb", [38, 94, 256]),
            ("cor_rgb", [38, 94]),
        ):
            caso = copy.deepcopy(self.referencia)
            caso[chave] = valor
            casos.append(caso)
        caso = copy.deepcopy(self.referencia)
        caso["texto_empresa"] = "EMPRESA FICTICIA"
        casos.append(caso)
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertFalse(tela_principal.corresponde(self.imagem, caso))

    def test_ausencia_json_quebrado_e_incompativel_nao_reconhecem(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "referencia.json"
            self.assertIsNone(tela_principal.carregar_referencia(caminho))
            for conteudo in ("{", "null", "[]", '{"versao": 1, "versao": 2}', "x" * 4097):
                caminho.write_text(conteudo, encoding="utf-8")
                self.assertIsNone(tela_principal.carregar_referencia(caminho))
            caminho.write_bytes(b"\xff")
            self.assertIsNone(tela_principal.carregar_referencia(caminho))
            caminho.write_text(json.dumps({**self.referencia, "versao": 999}), encoding="utf-8")
            self.assertIsNone(tela_principal.carregar_referencia(caminho))

    def test_persistencia_somente_metadados_sem_imagem(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "data" / "tela_principal.json"
            tela_principal.salvar_referencia(self.referencia, caminho)
            self.assertEqual(tela_principal.carregar_referencia(caminho), self.referencia)
            self.assertEqual(list(caminho.parent.iterdir()), [caminho])
            self.assertNotIn("EMPRESA", caminho.read_text(encoding="utf-8"))

    def test_calibracao_ruim_preserva_referencia_anterior(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "referencia.json"
            tela_principal.salvar_referencia(self.referencia, caminho)
            anterior = caminho.read_bytes()
            with self.assertRaises(ValueError):
                tela_principal.salvar_referencia(tela_principal.construir_referencia(Image.new("RGB", self.imagem.size, "white")), caminho)
            with self.assertRaises(ValueError):
                tela_principal.salvar_referencia({**self.referencia, "retangulo": [1, 1, 2, 2]}, caminho)
            self.assertEqual(caminho.read_bytes(), anterior)

    def test_falha_na_substituicao_atomica_preserva_json_sem_temporarios(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "referencia.json"
            tela_principal.salvar_referencia(self.referencia, caminho)
            anterior = caminho.read_bytes()
            nova = tela_principal.construir_referencia(tela_vazia((55, 110, 195)))
            with patch.object(tela_principal.os, "replace", side_effect=OSError("escrita recusada")):
                with self.assertRaises(OSError):
                    tela_principal.salvar_referencia(nova, caminho)
            self.assertEqual(caminho.read_bytes(), anterior)
            self.assertEqual(list(caminho.parent.iterdir()), [caminho])


if __name__ == "__main__":
    unittest.main()
