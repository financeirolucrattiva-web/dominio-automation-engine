"""Botões e formulário sintéticos; nenhum clique ou homologação real."""
import copy
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from PIL import ImageDraw, ImageFont
from app import botoes_formulario as botoes
from test_leitura_recortes_resumo import formulario


def tela_resumo(dx=0,dy=0,fator=1):
    imagem,dados = formulario(None,dx=dx,dy=dy)
    desenho = ImageDraw.Draw(imagem)
    fonte = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                             Path('C:/Windows/Fonts/arial.ttf')) if p.exists()),None)
    font = ImageFont.truetype(str(fonte),12) if fonte else ImageFont.load_default()
    desenho.text((20+dx,20+dy),'Resumo por acumulador',fill='black',font=font)
    desenho.rectangle((280+dx,116+dy,355+dx,141+dy),outline='#808080',fill='white')
    desenho.text((292+dx,122+dy),'Fechar',fill='black',font=font)
    bbox = font.getbbox('Fechar')
    for k,v in zip(dados,('Fechar',(292+dx+bbox[0])*2,(122+dy+bbox[1])*2,
                         (bbox[2]-bbox[0])*2,(bbox[3]-bbox[1])*2)):
        dados[k].append(v)
    if fator!=1:
        from PIL import Image
        imagem = imagem.resize((imagem.width*fator,imagem.height*fator),Image.Resampling.NEAREST)
        for chave in ('left','top','width','height'):
            dados[chave]=[v*fator for v in dados[chave]]
    return imagem,dados


class TestBotaoResumo(unittest.TestCase):
    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract indisponível.')
    def test_ok_compartilha_leitura_local_quando_final_falta_na_tela_inteira(self):
        imagem,dados=tela_resumo()
        dados={k:[v for i,v in enumerate(valores) if i!=3] for k,valores in dados.items()}
        self.preparar(imagem,dados)
        with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                          {'fechar'} if c[1]>110 else {'ok'}):
            self.assertIsNotNone(botoes.achar_ok_resumo(imagem))

    def preparar(self,imagem,dados,ok=None):
        def ocr(_imagem,escala):
            copia=copy.deepcopy(dados)
            for chave in ('left','top','width','height'):
                copia[chave]=[v*escala/2 for v in copia[chave]]
            return copia
        self.addCleanup(patch.stopall)
        patch.object(botoes.tela,'_ler_dados_ocr',side_effect=ocr).start()
        patch.object(botoes.tela,'ler_dados_ocr_windows',return_value=None).start()
        self.texto=patch.object(botoes.tela,'achar_texto_ou_no_centro',
                               side_effect=lambda im,t,**kw:ok if t=='OK' else None).start()
        self.windows=patch.object(botoes.tela,'achar_texto_windows',return_value=None).start()
        self.contexto=patch.object(botoes,'formulario_resumo_reconhecido',return_value=(40,30)).start()

    def test_fallback_mede_botoes_e_rele_recortes_sem_coordenada_fixa(self):
        for fator in (1,2):
            imagem,dados=tela_resumo(dx=100,dy=60,fator=fator)
            self.preparar(imagem,dados)
            original=imagem.tobytes()
            with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                              {'fechar'} if c[1]>=(116+60)*fator-2 else {'ok'}):
                pos=botoes.achar_ok_resumo(imagem)
            self.assertIsNotNone(pos)
            self.assertTrue((280+100)*fator < pos[0] < (355+100)*fator)
            self.assertTrue((80+60)*fator < pos[1] < (105+60)*fator)
            self.assertEqual(imagem.tobytes(),original)
            patch.stopall()

    def test_procura_ok_em_duas_escalas_e_windows_sem_clique(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados,ok=(315,94))
        with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                          {'fechar'} if c[1]>110 else {'ok'}):
            self.assertIsNotNone(botoes.achar_ok_resumo(imagem))
        self.assertEqual({c.kwargs['escala'] for c in self.texto.call_args_list if c.args[1]=='OK'}, {2,4})
        self.assertEqual({c.kwargs['escala'] for c in self.windows.call_args_list if c.args[1]=='OK'}, {2,4})

    def test_aviso_reconhecido_bloqueia_antes_de_buscar_ok(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        self.texto.side_effect=lambda im,t,**kw:(10,10) if t=='Aviso' else None
        self.assertIsNone(botoes.achar_ok_resumo(imagem))
        self.contexto.assert_not_called()
        self.assertFalse(any(c.args[1]=='OK' for c in self.texto.call_args_list))

    def test_formulario_ausente_e_ok_de_outro_contexto_nao_autorizam(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados,ok=(30,30))
        self.assertIsNone(botoes.achar_ok_resumo(imagem))
        self.contexto.return_value=None
        self.assertIsNone(botoes.achar_ok_resumo(imagem))

    def test_texto_contido_ou_leituras_conflitantes_nao_fabricam_ok(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        for valores in ({'book'}, {'ok cancelar'}, {'ok','book'}, set()):
            with self.subTest(valores=valores),patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                    {'fechar'} if c[1]>110 else valores):
                self.assertIsNone(botoes.achar_ok_resumo(imagem))

    def test_fechar_precisa_de_borda_real_sem_usar_deslocamento(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        ImageDraw.Draw(imagem).rectangle((275,112,360,145),fill='#eeeeee')
        self.assertIsNone(botoes.achar_ok_resumo(imagem))

    def test_dois_botoes_ok_medidos_sao_ambiguos(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        ImageDraw.Draw(imagem).rectangle((280,48,355,73),outline='#808080',fill='white')
        with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                          {'fechar'} if c[1]>110 else {'ok'}):
            self.assertIsNone(botoes.achar_ok_resumo(imagem))

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract indisponível.')
    def test_ocr_real_dos_recortes_reconhece_ok_e_fechar(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        pos=botoes.achar_ok_resumo(imagem)
        self.assertIsNotNone(pos)
        self.assertTrue(280 < pos[0] < 355)
        self.assertTrue(80 < pos[1] < 105)


if __name__=='__main__':unittest.main()
