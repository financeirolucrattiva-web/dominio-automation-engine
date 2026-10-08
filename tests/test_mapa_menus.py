import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock
from PIL import Image
from app.mapa_menus import MapaMenus


class TestMapaMenus(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.arquivo = Path(pasta.name) / "menus.json"
        self.mapa = MapaMenus(self.arquivo)
        self.imagem = Image.new("RGB", (1440, 300), "white")

    def test_primeiro_busca_area_original_depois_confirma_recorte_por_ocr(self):
        achar = Mock(return_value=(500, 100))
        self.assertEqual(self.mapa.localizar(self.imagem, "relatorios", "Livros", achar), (500, 100))
        achar.assert_called_once_with(self.imagem, "Livros")
        achar.reset_mock()
        achar.return_value = (180, 37)
        self.assertEqual(self.mapa.localizar(self.imagem, "relatorios", "Livros", achar), (500, 100))
        self.assertLess(achar.call_args.args[0].width, self.imagem.width)

    def test_cache_nao_autoriza_clique_quando_alvo_desaparece(self):
        self.mapa.localizar(self.imagem, "relatorios", "Livros", Mock(return_value=(500, 100)))
        achar = Mock(return_value=None)
        self.assertIsNone(self.mapa.localizar(self.imagem, "relatorios", "Livros", achar))
        self.assertEqual(achar.call_count, 2)
        self.assertIs(achar.call_args.args[0], self.imagem)

    def test_nova_resolucao_nao_reusa_posicao(self):
        self.mapa.localizar(self.imagem, "relatorios", "Livros", Mock(return_value=(500, 100)))
        atual = Image.new("RGB", (1000, 300), "white")
        achar = Mock(return_value=(600, 150))
        self.mapa.localizar(atual, "relatorios", "Livros", achar)
        achar.assert_called_once_with(atual, "Livros")

    def test_cache_corrompido_recai_na_busca_original(self):
        self.arquivo.write_text('{"relatorios:Livros": {"centro": ["erro"], "tamanho": [1440,300]}}')
        achar = Mock(return_value=None)
        self.assertIsNone(self.mapa.localizar(self.imagem, "relatorios", "Livros", achar))
        achar.assert_called_once_with(self.imagem, "Livros")
