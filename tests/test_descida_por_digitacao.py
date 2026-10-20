"""Busca por digitação no TreeView do Procurar Pasta; nó azul conferido por semelhança."""
import shutil
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont

from app import seletor_pasta as seletor


class TestSemelhanca(unittest.TestCase):
    def test_ruido_de_ocr_do_no_azul_ainda_confere_mas_outra_pasta_nao(self):
        # Leituras reais do nó azul "PerfLogs" (captura de 20/10): ruído nas bordas e glifos.
        for lida in ('iperflogsi', 'ipeffogsl', 'ipenflogsi'):
            self.assertGreaterEqual(seletor._semelhanca([lida], 'PerfLogs'), 0.66, lida)
        for outra in ('saida', 'programfiles', 'sefanet', 'users'):
            self.assertLess(seletor._semelhanca([outra], 'PerfLogs'), 0.66, outra)

    def test_folha_exclusiva_exige_quase_todos_os_digitos(self):
        esperado = 'LIVROS650253899106'
        self.assertGreaterEqual(seletor._semelhanca(['livros650253899106'], esperado), 0.88)
        # Outra pasta LIVROS de execução anterior não pode passar por esta.
        self.assertLess(seletor._semelhanca(['livros521333058434'], esperado), 0.88)

    def test_teclas_dos_nomes(self):
        self.assertTrue(seletor._tipavel('dominio-automation-engine'))
        self.assertTrue(seletor._tipavel('LIVROS123456789012'))
        self.assertFalse(seletor._tipavel('Usuário'))
        self.assertFalse(seletor._tipavel(''))
        self.assertEqual(seletor._tecla_do_caractere('L'), 'l')
        self.assertEqual(seletor._tecla_do_caractere('-'), '-')
        self.assertEqual(seletor._tecla_do_caractere(' '), 'space')


class TestNoAzul(unittest.TestCase):
    def test_le_texto_branco_sobre_azul_aproximadamente(self):
        if not shutil.which('tesseract'):
            self.skipTest('Tesseract indisponível.')
        imagem = Image.new('RGB', (300, 200), 'white')
        desenho = ImageDraw.Draw(imagem)
        try:
            fonte = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 12)
        except OSError:
            fonte = ImageFont.load_default()
        desenho.rectangle((50, 80, 100, 96), fill='#0078d7')
        desenho.text((53, 81), 'PerfLogs', font=fonte, fill='white')
        detalhes = {'arvore': (10, 10, 280, 180)}
        sel = seletor._nome_selecionado_aproximado(imagem, detalhes)
        self.assertIsNotNone(sel)
        self.assertEqual((sel['x'], sel['y']), (50, 80))
        self.assertTrue(seletor._confere_selecao(sel, 'PerfLogs'))
        self.assertFalse(seletor._confere_selecao(sel, 'saida'))

    def test_sem_caixa_azul_ou_com_duas_nao_adivinha(self):
        imagem = Image.new('RGB', (300, 200), 'white')
        self.assertIsNone(seletor._nome_selecionado_aproximado(imagem, {'arvore': (10, 10, 280, 180)}))
        ImageDraw.Draw(imagem).rectangle((50, 80, 100, 96), fill='#0078d7')
        ImageDraw.Draw(imagem).rectangle((50, 120, 100, 136), fill='#0078d7')
        self.assertIsNone(seletor._nome_selecionado_aproximado(imagem, {'arvore': (10, 10, 280, 180)}))


class TestDescida(unittest.TestCase):
    def descer(self, selecoes, partes=('Users', 'darto', 'saida'), clicar=None, ramo_mudou=True):
        teclas = []
        sequencia = iter(selecoes)
        mudou = ramo_mudou if callable(ramo_mudou) else (lambda *a: ramo_mudou)
        with patch.object(seletor, '_aguardar_dialogo', return_value=('img', {'arvore': (0, 0, 1, 1)})),                 patch.object(seletor, '_drive_selecionado', return_value=True),                 patch.object(seletor, '_nome_selecionado_aproximado', side_effect=lambda *a: next(sequencia)),                 patch.object(seletor, '_arvore_mudou_abaixo', side_effect=mudou),                 patch.object(seletor.time, 'sleep'),                 patch.object(seletor, 'ponto_seguro'):
            resultado = seletor._descer_por_digitacao(Mock(), teclas.append, 'M', list(partes), clicar=clicar)
        return teclas, resultado

    def sel(self, nome, x):
        return {'leituras': [nome], 'x': x, 'y': 100, 'w': 40, 'h': 14}

    def test_digita_cada_nome_e_abre_o_ramo_clicando_no_icone_da_pasta(self):
        cliques = []
        selecoes = [self.sel('users', 20), self.sel('darto', 40), self.sel('saida', 60)]
        teclas, (_, _, x) = self.descer(selecoes, clicar=lambda *p: cliques.append(p))
        self.assertEqual(teclas, list('users') + list('darto') + list('saida'))  # sem Right: o ícone abriu
        # Ícone da pasta ~12 px à esquerda da caixa azul, no meio da linha; um clique por ramo aberto.
        self.assertEqual(cliques, [(8, 107), (28, 107)])
        self.assertEqual(x, 60)

    def test_sem_efeito_do_icone_tenta_right_e_sem_efeito_nenhum_recusa(self):
        cliques = []
        resultados = iter([False, True, False, False])  # nível 0: ícone sem efeito, Right abre; nível 1: nada abre
        selecoes = [self.sel('users', 20), self.sel('darto', 40), self.sel('saida', 60)]
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.descer(selecoes, clicar=lambda *p: cliques.append(p), ramo_mudou=lambda *a: next(resultados))
        self.assertEqual(len(cliques), 2)  # um por nível; o segundo também sem efeito -> recusa antes de digitar saida

    def test_sem_clicar_usa_apenas_right(self):
        selecoes = [self.sel('users', 20)]
        teclas, _ = self.descer(selecoes, partes=('Users', ), clicar=None)
        self.assertEqual(teclas, list('users'))
        selecoes = [self.sel('users', 20), self.sel('darto', 40)]
        teclas, _ = self.descer(selecoes, partes=('Users', 'darto'), clicar=None)
        self.assertEqual(teclas, list('users') + ['right'] + list('darto'))

    def test_indentacao_que_nao_cresce_nao_confirma_e_nao_segue(self):
        selecoes = [self.sel('users', 20)] + [self.sel('darto', 20)] * 6
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.descer(selecoes, clicar=lambda *p: None)

    def test_nome_diferente_do_digitado_nao_confirma(self):
        selecoes = [self.sel('programfiles', 20)] * 6
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.descer(selecoes, partes=('Users',))

    def test_leitura_transitoria_vazia_e_repetida_sem_redigitar(self):
        selecoes = [None, self.sel('users', 20)]
        teclas, _ = self.descer(selecoes, partes=('Users',))
        self.assertEqual(teclas, list('users'))  # digitou uma vez; só releu


class TestArvoreMudou(unittest.TestCase):
    def test_detecta_filhos_abaixo_da_linha_selecionada_mas_ignora_o_que_esta_acima(self):
        antes = Image.new('RGB', (200, 200), 'white')
        depois = antes.copy()
        ImageDraw.Draw(depois).rectangle((60, 130, 120, 140), fill='black')  # filho apareceu abaixo
        sel = {'y': 100, 'h': 14}
        detalhes = {'arvore': (10, 10, 180, 180)}
        self.assertTrue(seletor._arvore_mudou_abaixo(antes, depois, sel, detalhes))
        acima = antes.copy()
        ImageDraw.Draw(acima).rectangle((60, 30, 120, 40), fill='black')  # mudança acima da linha: não conta
        self.assertFalse(seletor._arvore_mudou_abaixo(antes, acima, sel, detalhes))
        self.assertFalse(seletor._arvore_mudou_abaixo(antes, antes.copy(), sel, detalhes))


if __name__ == '__main__':
    unittest.main()
