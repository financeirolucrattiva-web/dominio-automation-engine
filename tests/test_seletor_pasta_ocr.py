"""OCR real em diálogo sintético e confirmação local do OK, sem desktop."""
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont
from app import seletor_pasta as seletor
from app.controle_execucao import ExecucaoInterrompida


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
    def test_lista_aberta_cobre_arvore_e_mostra_opcao_pendente_sem_mudar_campo(self):
        imagem=dialogo()
        desenho=ImageDraw.Draw(imagem)
        fonte=fonte_teste()
        desenho.rectangle((107,62,530,84),fill='white')
        desenho.text((112,65),'Servidor (C:)',font=fonte,fill='black')
        desenho.rectangle((105,87,560,166),fill='white',outline='black')
        desenho.text((112,92),'Servidor (C:)',font=fonte,fill='black')
        desenho.rectangle((107,115,558,138),fill='#0078d7')
        desenho.text((112,118),'Client C (M:)',font=fonte,fill='white')
        desenho.text((112,144),'Client Z (Z:)',font=fonte,fill='black')
        detalhes=seletor.medir_dialogo(imagem,somente_unidade=True)
        self.assertIsNotNone(detalhes['lista'])
        self.assertEqual(seletor._assinatura_unidade(imagem,detalhes)[1],'servidor:c')
        opcao=seletor._opcao_unidade(imagem,detalhes)
        self.assertEqual(opcao[1][0],'realce')
        self.assertTrue(114<=opcao[1][1][1]<=116)
        self.assertFalse(seletor._primeira_opcao_unidade(imagem,detalhes))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            seletor.medir_dialogo(imagem)

    def test_identidade_da_unidade_preserva_letra_e_tipo_com_barras_ocr_diferentes(self):
        def identidade(texto):
            return seletor._identidade_unidade([{'texto':t} for t in texto.split()])
        for texto in (r'Client C (M:\)', 'Client C (M:/)', 'Client C (M:|)', 'Client C (M:)'):
            self.assertEqual(identidade(texto),'clientc:m')
        self.assertNotEqual(identidade('Client Z (M:)'),'clientc:m')
        self.assertNotEqual(identidade('Servidor (M:)'),'clientc:m')
        self.assertNotEqual(identidade('Client C (Q:)'),'clientc:m')

    def test_nome_curto_azul_omitido_no_ocr_global_e_lido_no_recorte_com_margem(self):
        imagem=dialogo()
        desenho=ImageDraw.Draw(imagem)
        desenho.rectangle((32,104,558,330),fill='white')
        fonte=fonte_teste()
        largura=round(desenho.textlength('MIT',font=fonte))+2
        desenho.rectangle((66,120,66+largura,138),fill='#0078d7')
        desenho.text((67,122),'MIT',font=fonte,fill='white')
        desenho.text((67,158),'Users',font=fonte,fill='black')
        palavras=[p for p in seletor._palavras(imagem) if not (102<p['y']<148 and p['x']>30)]
        with patch.object(seletor,'_palavras',return_value=palavras):
            detalhes=seletor.medir_dialogo(imagem)
        no=seletor._no_selecionado(imagem,detalhes)
        self.assertIsNotNone(no)
        self.assertEqual(no['nome'],'mit')
        alvo=seletor._alvo_visivel(detalhes,no,'Users')
        self.assertIsNotNone(alvo)
        self.assertTrue(66<alvo['posicao'][0]<115 and 158<alvo['posicao'][1]<180)

    def test_cliente_parcial_no_ocr_global_e_timeout_isolado_permitem_recorte(self):
        from app import tela
        imagem=dialogo()
        palavras=[p for p in seletor._palavras(imagem) if not 60<p['y']<86 or p['x']<105]
        palavras.append({'texto':'Clent','x':112,'y':65,'w':35,'h':12})
        ler=tela.ler_dados_ocr_linha_rotulo
        chamadas=[]
        def com_primeiro_timeout(*args,**kwargs):
            chamadas.append(kwargs)
            if len(chamadas)==1:raise RuntimeError('timeout sintético')
            return ler(*args,**kwargs)
        with patch.object(seletor,'_palavras',return_value=palavras), \
             patch.object(tela,'ler_dados_ocr_linha_rotulo',side_effect=com_primeiro_timeout):
            detalhes=seletor.medir_dialogo(imagem)
        self.assertTrue(seletor._drive_selecionado(detalhes,'M'))
        self.assertEqual(len(chamadas),4)

    def test_cancelamento_no_recorte_nao_e_tratado_como_timeout(self):
        from app import tela
        with patch.object(tela,'ler_dados_ocr_linha_rotulo',side_effect=ExecucaoInterrompida('teste')):
            with self.assertRaises(ExecucaoInterrompida):
                seletor._refinar_unidade(dialogo(),[],(105,60,456,27))

    def test_combo_azul_omitido_na_tela_inteira_e_relido_em_recorte(self):
        imagem=dialogo()
        desenho=ImageDraw.Draw(imagem)
        desenho.rectangle((110,63,225,83),fill='#0078d7')
        desenho.text((112,65),'Client C (M:)',font=fonte_teste(),fill='white')
        palavras=[p for p in seletor._palavras(imagem) if not 60<p['y']<86 or p['x']<105]
        with patch.object(seletor,'_palavras',return_value=palavras):
            detalhes=seletor.medir_dialogo(imagem)
        self.assertTrue(seletor._drive_selecionado(detalhes,'M'))
        self.assertFalse(seletor._drive_selecionado(detalhes,'C'))

    def test_recorte_da_unidade_nao_converte_client_z_em_client_c(self):
        imagem=dialogo()
        desenho=ImageDraw.Draw(imagem)
        desenho.rectangle((107,62,530,84),fill='white')
        desenho.text((112,65),'Client Z (M:)',font=fonte_teste(),fill='black')
        palavras=[p for p in seletor._palavras(imagem) if not 60<p['y']<86 or p['x']<105]
        with patch.object(seletor,'_palavras',return_value=palavras):
            detalhes=seletor.medir_dialogo(imagem)
        self.assertFalse(seletor._drive_selecionado(detalhes,'M'))

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
