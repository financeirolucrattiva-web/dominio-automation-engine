"""Bordas e OCR de fixtures sintéticas; nenhum clique ou emissão fiscal."""
import contextlib
import copy
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont

from app import botao_livros as botao, botoes_formulario as comuns
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao


def formulario(dx=0, dy=0, fator=1):
    imagem = Image.new('RGB', (450+dx, 250+dy), '#eeeeee')
    d = ImageDraw.Draw(imagem)
    fonte = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                             Path('C:/Windows/Fonts/arial.ttf')) if p.exists()), None)
    font = ImageFont.truetype(str(fonte), 12) if fonte else ImageFont.load_default()
    dados = {k: [] for k in ('text', 'left', 'top', 'width', 'height')}
    def palavra(texto, x, y, w, h=12):
        for k, v in zip(dados, (texto, (x+dx)*2, (y+dy)*2, w*2, h*2)):
            dados[k].append(v)
    d.text((20+dx, 20+dy), 'Livros Fiscais', font=font, fill='black')
    palavra('Livros', 20, 22, 36); palavra('Fiscais', 62, 22, 36)
    for texto, y, largura in (('Inicial:', 90, 35), ('Final:', 125, 29)):
        d.text((100+dx, y+5+dy), texto, font=font, fill='black')
        d.rectangle((160+dx, y+dy, 250+dx, y+22+dy), fill='white', outline='#808080')
        d.text((164+dx, y+5+dy), '01/08/2026', font=font, fill='black')
        palavra(texto, 100, y+5, largura)
    for texto, y in (('OK', 70), ('Fechar', 108), ('Soluções', 146)):
        d.rectangle((300+dx, y+dy, 380+dx, y+26+dy), fill='white', outline='#808080')
        d.text((320+dx if texto=='OK' else 309+dx, y+6+dy), texto, font=font, fill='black')
    if fator != 1:
        imagem = imagem.resize((imagem.width*fator, imagem.height*fator), Image.Resampling.NEAREST)
        for k in ('left', 'top', 'width', 'height'):
            dados[k] = [v*fator for v in dados[k]]
    return imagem, dados


class TestBotaoLivros(unittest.TestCase):
    def preparar(self, imagem, dados, recortes=True):
        stack = contextlib.ExitStack(); self.addCleanup(stack.close)
        def ocr(area, escala):
            if area.size != imagem.size:
                return {'text': []}
            leitura = copy.deepcopy(dados)
            for k in ('left', 'top', 'width', 'height'):
                leitura[k] = [v*escala/2 for v in leitura[k]]
            return leitura
        self.ocr = stack.enter_context(patch.object(botao.tela, '_ler_dados_ocr', side_effect=ocr))
        self.windows = stack.enter_context(patch.object(botao.tela, 'ler_dados_ocr_windows', return_value=None))
        if recortes:
            self.recortes = stack.enter_context(patch.object(comuns, '_texto_recorte',
                side_effect=lambda im, c: {'ok'} if c[1] < 100 else {'fechar'} if c[1] < 140 else {'solucoes'}))

    def test_sem_ok_nem_fechar_globais_le_recortes_em_bordas_reais(self):
        imagem, dados = formulario(); self.preparar(imagem, dados)
        detalhes = []
        self.assertEqual(botao.achar_ok_livros(imagem, detalhes.append), (340, 83))
        self.assertEqual(detalhes[-1]['motivo'], 'ok_literal_confirmado')
        self.assertNotIn('OK', dados['text']); self.assertNotIn('Fechar', dados['text'])
        # Espaço desta fixture é 38, sem usar o antigo deslocamento 31.
        self.assertEqual(self.recortes.call_count, 3)

    def test_geometria_deslocada_e_ampliada_nao_usa_coordenada_fixa(self):
        imagem, dados = formulario(dx=100, dy=50, fator=2)
        self.preparar(imagem, dados, recortes=False)
        with patch.object(comuns, '_texto_recorte', side_effect=lambda im, c:
                {'ok'} if c[1] < 300 else {'fechar'} if c[1] < 375 else {'solucoes'}):
            self.assertEqual(botao.achar_ok_livros(imagem), (880, 266))

    def test_so_fechar_legivel_sem_texto_ok_nao_emite(self):
        imagem, dados = formulario(); self.preparar(imagem, dados)
        self.recortes.side_effect = lambda im, c: {'fechar'} if 100 < c[1] < 140 else set()
        self.assertIsNone(botao.achar_ok_livros(imagem))

    def test_dois_botoes_ok_nao_autorizam_escolher_primeiro(self):
        imagem, dados = formulario(); self.preparar(imagem, dados)
        self.recortes.side_effect = lambda im, c: {'fechar'} if 100 < c[1] < 140 else {'ok'}
        self.assertIsNone(botao.achar_ok_livros(imagem))

    def test_aviso_de_outro_motor_bloqueia_antes_de_medicao(self):
        imagem, dados = formulario(); self.preparar(imagem, dados)
        self.windows.return_value = {'text': ['Aviso']}
        self.assertIsNone(botao.achar_ok_livros(imagem))
        self.recortes.assert_not_called()

    def test_ok_exato_fora_da_coluna_bloqueia(self):
        imagem, dados = formulario()
        for k, v in zip(dados, ('OK', 40, 400, 30, 20)):
            dados[k].append(v)
        self.preparar(imagem, dados)
        self.assertIsNone(botao.achar_ok_livros(imagem))

    def test_sem_titulo_ou_campo_fisico_nao_aceita_botoes(self):
        imagem, dados = formulario()
        dados['text'][0] = 'Outro'
        self.preparar(imagem, dados)
        self.assertIsNone(botao.achar_ok_livros(imagem))
        self.recortes.assert_not_called()

    def test_falha_de_ocr_isolada_nao_impede_outro_motor(self):
        imagem, dados = formulario(); self.preparar(imagem, dados)
        original = self.ocr.side_effect
        self.ocr.side_effect = lambda im, escala: (
            original(im, escala) if escala == 4 else (_ for _ in ()).throw(RuntimeError('privado')))
        self.assertIsNotNone(botao.achar_ok_livros(imagem))

    def test_cancelamento_antes_do_resultado_nao_devolve_alvo(self):
        imagem, dados = formulario(); self.preparar(imagem, dados)
        controle = ControleExecucao()
        def ler(im, caixa):
            controle.interromper('teste')
            return {'ok'}
        self.recortes.side_effect = ler
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            botao.achar_ok_livros(imagem)

    @unittest.skipUnless(shutil.which('tesseract'), 'Tesseract indisponível.')
    def test_ocr_real_dos_botoes_em_fixture_sintetica(self):
        imagem, dados = formulario(); self.preparar(imagem, dados, recortes=False)
        self.assertEqual(botao.achar_ok_livros(imagem), (340, 83))


if __name__ == '__main__':
    unittest.main()
