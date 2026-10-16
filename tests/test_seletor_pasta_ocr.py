"""OCR real em diálogo sintético e confirmação local do OK, sem desktop."""
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont
from app import seletor_pasta as seletor


def fonte_teste():
    for nome in ('DejaVuSans.ttf','arial.ttf'):
        try:return ImageFont.truetype(nome,14)
        except OSError:continue
    raise unittest.SkipTest('Fonte TrueType indisponível para a figura sintética.')


def dialogo():
    imagem=Image.new('RGB',(640,420),'#eeeeee')
    d=ImageDraw.Draw(imagem)
    fonte=fonte_teste()
    d.text((15,10),'Procurar Pasta',font=fonte,fill='black')
    d.text((30,65),'Unidade:',font=fonte,fill='black')
    d.rectangle((105,60,560,86),fill='white',outline='black')
    d.text((112,65),'Client C (M:)',font=fonte,fill='black')
    d.rectangle((30,102,560,332),fill='white',outline='black')
    d.rectangle((66,120,112,138),fill='#0078d7')
    d.text((67,122),'Users',font=fonte,fill='white')
    d.text((85,148),'usuario',font=fonte,fill='black')
    d.text((104,174),'dominio-automation-engine',font=fonte,fill='black')
    d.rectangle((350,354,430,382),outline='black')
    d.rectangle((445,354,535,382),outline='black')
    d.text((381,360),'OK',font=fonte,fill='black')
    d.text((460,360),'Cancelar',font=fonte,fill='black')
    return imagem


class TestSeletorOCR(unittest.TestCase):
    def test_ocr_real_mede_controles_e_le_nome_na_selecao_azul(self):
        imagem=dialogo()
        detalhes=seletor.medir_dialogo(imagem)
        self.assertTrue(seletor._drive_selecionado(detalhes,'M'))
        self.assertEqual(seletor._no_selecionado(imagem,detalhes)['nome'],'users')
        ok=seletor._ok_final(imagem,detalhes)
        self.assertIsNotNone(ok)
        self.assertTrue(350<ok[0]<430 and 354<ok[1]<382)

    def test_ok_ausente_na_tela_inteira_e_lido_no_botao_medido(self):
        imagem=dialogo()
        palavras=[p for p in seletor._palavras(imagem) if p['texto']!='OK']
        with patch.object(seletor,'_palavras',return_value=palavras):
            detalhes=seletor.medir_dialogo(imagem)
        self.assertIsNone(detalhes['ok'])
        ok=seletor._ok_final(imagem,detalhes)
        self.assertIsNotNone(ok)
        self.assertTrue(350<ok[0]<430 and 354<ok[1]<382)

    def test_borda_sem_palavra_ok_nao_autoriza_clicar(self):
        imagem=dialogo()
        d=ImageDraw.Draw(imagem)
        d.rectangle((352,356,428,380),fill='#eeeeee')
        detalhes=seletor.medir_dialogo(imagem)
        self.assertIsNone(detalhes['ok'])
        self.assertIsNone(seletor._ok_final(imagem,detalhes))

    def test_ok_com_texto_adicional_no_botao_nao_autoriza_clicar(self):
        imagem=dialogo()
        d=ImageDraw.Draw(imagem)
        d.rectangle((352,356,428,380),fill='#eeeeee')
        fonte=fonte_teste()
        d.text((355,360),'OK outro',font=fonte,fill='black')
        detalhes=seletor.medir_dialogo(imagem)
        self.assertIsNone(seletor._ok_final(imagem,detalhes))


if __name__=='__main__':unittest.main()
