"""Tons de antialias e leitura independente do realce original; sem GUI."""
import contextlib
import io
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app import seletor_pasta as seletor, tela
from app.controle_execucao import ExecucaoInterrompida
from app.leitura_resumo import normalizar_selecao
from app.leitura_unidade import normalizar_unidade
from test_seletor_pasta_ocr import dialogo
from test_unidade_pasta_ocr_nativo import dados_unidade


class TestContrasteUnidade(unittest.TestCase):
    def campo(self,fundo=(0,120,215)):
        im=Image.new('RGB',(90,18),'white')
        ImageDraw.Draw(im).rectangle((2,2,70,15),fill=fundo)
        return im

    def test_tracos_de_25_e_50_porcento_nao_desaparecem(self):
        im=self.campo()
        im.putpixel((10,7),(64,154,225))
        im.putpixel((20,7),(128,188,235))
        antigo=normalizar_selecao(im); novo=normalizar_unidade(im)
        self.assertEqual(antigo.getpixel((10,7)),(255,255,255))
        self.assertEqual(antigo.getpixel((20,7)),(255,255,255))
        for x,esperado in ((10,191),(20,127)):
            valor=novo.getpixel((x,7))
            self.assertLessEqual(abs(valor[0]-esperado),1)
            self.assertEqual(valor,(valor[0],)*3)

    def test_azul_puro_vira_fundo_e_branco_opaco_vira_tinta(self):
        im=self.campo(); im.putpixel((12,8),(255,255,255))
        novo=normalizar_unidade(im)
        self.assertEqual(novo.getpixel((3,3)),(255,255,255))
        self.assertEqual(novo.getpixel((12,8)),(0,0,0))
        self.assertEqual(novo.size,im.size)

    def test_caret_colorido_dentro_e_fora_do_realce_nao_vira_glyph_nem_e_apagado(self):
        im=self.campo(); d=ImageDraw.Draw(im)
        d.line((55,3,55,14),fill=(255,128,32))
        d.line((72,3,72,14),fill=(255,128,32))
        # Pontuação ao lado do caret continua vindo dos próprios pixels.
        im.putpixel((54,8),(128,188,235))
        novo=normalizar_unidade(im)
        for x in (55,72):
            for y in range(3,15):self.assertEqual(novo.getpixel((x,y)),im.getpixel((x,y)))
        self.assertLess(novo.getpixel((54,8))[0],150)

    def test_campo_sem_realce_preserva_todos_os_pixels(self):
        im=Image.new('RGB',(150,18),'white'); d=ImageDraw.Draw(im)
        d.text((2,1),'Client C (M:)',fill='black')
        self.assertEqual(normalizar_unidade(im).tobytes(),im.tobytes())

    def test_cores_fora_da_mistura_azul_branco_sao_preservadas(self):
        im=self.campo()
        for x,cor in ((15,(255,0,0)),(30,(0,255,0)),(45,(0,0,0))):im.putpixel((x,7),cor)
        novo=normalizar_unidade(im)
        for x in (15,30,45):self.assertEqual(novo.getpixel((x,7)),im.getpixel((x,7)))

    def test_tema_azul_medido_nao_depende_de_uma_cor_fixa(self):
        for fundo in ((0,120,215),(51,153,255),(0,80,180)):
            with self.subTest(fundo=fundo):
                im=self.campo(fundo)
                mistura=tuple(round((v+255)/2) for v in fundo)
                im.putpixel((20,7),mistura)
                self.assertLessEqual(abs(normalizar_unidade(im).getpixel((20,7))[0]-127),1)


class TestOriginalUnidade(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.imagem=dialogo(); self.combo=(105,60,456,27)
        ImageDraw.Draw(self.imagem).rectangle((108,63,230,83),fill=(0,120,215))
        self.original=self.imagem.crop(seletor._area_unidade(self.combo))
        self.vazio={k:[] for k in ('text','left','top','width','height')}
        self.nativo=self.stack.enter_context(patch.object(tela,'ler_dados_ocr_windows',return_value=None))
        self.observacoes=[]
        self.calls=[]

    def so_original(self,texto):
        def ler(im,escala,preparo):
            original=im.tobytes()==self.original.tobytes()
            self.calls.append((original,escala,preparo))
            return dados_unidade(texto,escala) if original else self.vazio
        return ler

    def ler(self):
        return seletor._refinar_unidade(self.imagem,[],self.combo,registrar=self.observacoes.append)

    def test_original_azul_recupera_unidade_sem_alterar_pixels_ou_preset_da_letra(self):
        with patch.object(tela,'ler_dados_ocr_linha_rotulo',side_effect=self.so_original('Client C (M:)')):
            palavras=self.ler()
        self.assertTrue(seletor._drive_selecionado({'combo':self.combo,'palavras':palavras},'M'))
        self.assertEqual(len(self.calls),6)
        self.assertEqual(self.calls[-2:],[(True,4,'cinza'),(True,6,'cinza')])
        self.assertEqual(sum(o.get('preparo')=='original_azul' for o in self.observacoes),2)
        self.nativo.assert_not_called()

    def test_original_nao_converte_outro_tipo_ou_letra_no_destino_m(self):
        for texto in ('Client Z (M:)','Servidor (M:)','Client C (Q:)'):
            with self.subTest(texto=texto),patch.object(
                    tela,'ler_dados_ocr_linha_rotulo',side_effect=self.so_original(texto)):
                palavras=self.ler()
                self.assertFalse(seletor._drive_selecionado({'combo':self.combo,'palavras':palavras},'M'))

    def test_contradicao_da_normalizada_nao_e_substituida_por_duas_opinioes_originais(self):
        chamadas=0
        def ler(im,escala,preparo):
            nonlocal chamadas
            chamadas+=1
            if chamadas==1:return dados_unidade('Client Z (M:)',escala)
            return self.so_original('Client C (M:)')(im,escala,preparo)
        with patch.object(tela,'ler_dados_ocr_linha_rotulo',side_effect=ler):
            self.assertEqual(self.ler(),[])
        self.assertEqual(self.observacoes[-1]['identidades_distintas'],2)

    def test_uma_opiniao_original_nao_basta(self):
        chamadas=0
        def ler(im,escala,preparo):
            nonlocal chamadas
            chamadas+=1
            return dados_unidade('Client C (M:)',escala) if chamadas==5 else self.vazio
        with patch.object(tela,'ler_dados_ocr_linha_rotulo',side_effect=ler):
            self.assertEqual(self.ler(),[])

    def test_cancelamento_na_leitura_original_propaga(self):
        def ler(im,escala,preparo):
            if im.tobytes()==self.original.tobytes():raise ExecucaoInterrompida('teste')
            return self.vazio
        with patch.object(tela,'ler_dados_ocr_linha_rotulo',side_effect=ler):
            with self.assertRaises(ExecucaoInterrompida):self.ler()

    def test_sem_realce_nao_acrescenta_passadas_originais(self):
        self.imagem=dialogo()
        with patch.object(tela,'ler_dados_ocr_linha_rotulo',return_value=self.vazio) as ler:
            self.assertEqual(self.ler(),[])
        self.assertEqual(ler.call_count,4)


class TestOCRRealContraste(unittest.TestCase):
    def test_glifos_fracos_antes_apagados_agora_confirmam_identidade_literal(self):
        # Figura sintética: texto completo, mesma ROI 358x16 do diagnóstico.
        # Glifos sem núcleo opaco expõem o erro do limiar de saturação.
        try:fonte=ImageFont.truetype('DejaVuSans.ttf',56)
        except OSError:raise unittest.SkipTest('Fonte TrueType indisponível.')
        mascara=Image.new('L',(358*4,16*4))
        d=ImageDraw.Draw(mascara); texto=r'Client C (M:\)'
        d.text((8,8),texto,font=fonte,fill=255,anchor='lt')
        alpha=np.array(mascara.resize((358,16),Image.Resampling.LANCZOS))/255*.5
        fundo=np.array((0,120,215))
        pixels=np.full((16,358,3),255,dtype='uint8')
        selecionado=np.rint(fundo+alpha[:,:,None]*(255-fundo)).astype('uint8')
        largura=round(d.textlength(texto,font=fonte)/4)+4
        pixels[:,:largura]=selecionado[:,:largura]
        im=Image.new('RGB',(420,80),'white'); combo=(20,20,380,20)
        im.paste(Image.fromarray(pixels),(22,22))
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(tela,'ler_dados_ocr_windows',return_value=None):
            with patch('app.leitura_unidade.normalizar_unidade',side_effect=normalizar_selecao):
                antes=seletor._refinar_unidade(im,[],combo)
            depois=seletor._refinar_unidade(im,[],combo)
        self.assertFalse(seletor._drive_selecionado({'combo':combo,'palavras':antes},'M'))
        self.assertTrue(seletor._drive_selecionado({'combo':combo,'palavras':depois},'M'))
        self.assertFalse(seletor._drive_selecionado({'combo':combo,'palavras':depois},'Q'))


if __name__=='__main__':unittest.main()
