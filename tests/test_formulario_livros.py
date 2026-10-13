"""Pixels/OCR locais sintéticos; não afirmam calibração da captura real."""
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock

from PIL import Image, ImageDraw, ImageFont
from app.formulario_livros import ler_formulario, marcar_tres_livros, ROTULOS

FONTES = (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('C:/Windows/Fonts/arial.ttf'))


def formulario(marcados=(), outros=False, dx=0, dy=0, fator=1, cinzas=False):
    fonte = next((p for p in FONTES if p.exists()), None)
    font = ImageFont.truetype(str(fonte), 12) if fonte else ImageFont.load_default()
    imagem = Image.new('RGB',(1000+dx,680+dy),'#eeeeee')
    desenho = ImageDraw.Draw(imagem)
    dados = {k:[] for k in ('text','left','top','width','height')}
    def texto(frase,x,y,cor='black'):
        x+=dx; y+=dy
        desenho.text((x,y),frase,font=font,fill=cor)
        for token in frase.split():
            box = font.getbbox(token)
            valores = (token,(x+box[0])*2*fator,(y+box[1])*2*fator,
                       (box[2]-box[0])*2*fator,(box[3]-box[1])*2*fator)
            for k,v in zip(dados,valores): dados[k].append(v)
            x += font.getlength(token+' ')
    texto('Livros Fiscais',25,20)
    frases = ('Termos de abertura e encerramento','Registro de Entradas','Relação de Emitentes',
              'Registro de Saídas','Registro de ICMS','Registro de IPI','Registro de ISS',
              'Registro de Inventário','Inventário Empreendimentos','Registro Permanente',
              'Pedido de Autorização','Pedido de Formulário','RUDFTO','LMC','Registro de Veículos','Contra capa')
    caixas = {}
    for i,frase in enumerate(frases):
        x=70+(20 if i==2 else 0)+dx; y=105+i*23+dy
        cor = '#bbbbbb' if cinzas and i in (5,8,9,10,11,13,14) else 'black'
        desenho.rectangle((x,y,x+12,y+12),fill='white',outline=cor)
        tipo = next((t for t,r in ROTULOS.items() if r==frase),None)
        if tipo: caixas[tipo]=(x,y,13,13)
        if tipo in marcados or (i==6 and outros):
            desenho.line([(x+3,y+6),(x+5,y+9),(x+10,y+3)],fill='black',width=2)
        texto(frase,(90 if i==2 else 70)+17,105+i*23+1,cor)
    texto('Inicial:',450,110); texto('01/09/2026',510,110)
    texto('Final:',450,140); texto('30/09/2026',510,140)
    texto('Conforme período inicial',450,510)
    # Opção marcada no painel à direita não pertence ao grupo Emitir.
    desenho.rectangle((460+dx,300+dy,472+dx,312+dy),fill='white',outline='black')
    desenho.line([(463+dx,306+dy),(465+dx,309+dy),(470+dx,303+dy)],fill='black',width=2)
    if fator != 1:
        imagem=imagem.resize((imagem.width*fator,imagem.height*fator),Image.Resampling.NEAREST)
    return imagem,dados,caixas


class TestLeituraFormularioLivros(unittest.TestCase):
    def test_le_tres_desmarcados_periodo_e_ignora_opcao_marcada_fora_de_emitir(self):
        imagem,dados,_=formulario()
        resultado=ler_formulario(imagem,dados)
        self.assertEqual([l['marcada'] for l in resultado['livros'].values()],[False]*3)
        self.assertEqual(sum(l['marcada'] for l in resultado['outros']),0)
        self.assertEqual(len(resultado['outros']),13)
        self.assertEqual(resultado['periodo']['inicial']['valor'],'01/09/2026')
        self.assertEqual(resultado['periodo']['final']['valor'],'30/09/2026')

    def test_le_marcacao_mista_com_janela_movida_e_escala_diferente(self):
        for fator in (1,2):
            imagem,dados,_=formulario(('registro_entradas','registro_icms'),dx=210,dy=80,fator=fator)
            r=ler_formulario(imagem,dados)
            self.assertEqual({t:l['marcada'] for t,l in r['livros'].items()},
                             {'registro_entradas':True,'registro_saidas':False,'registro_icms':True})
            self.assertGreater(r['livros']['registro_icms']['posicao'][0],210*fator)

    def test_conta_caixas_cinzas_vazias_de_opcoes_desabilitadas(self):
        imagem,dados,_=formulario(cinzas=True)
        resultado=ler_formulario(imagem,dados)
        self.assertEqual(len(resultado['outros']),13)
        self.assertFalse(any(c['marcada'] for c in resultado['outros']))

    def test_identifica_outro_livro_marcado_e_recusa_selecao_antes_de_clicar(self):
        imagem,dados,_=formulario(outros=True)
        resultado=ler_formulario(imagem,dados)
        self.assertEqual(sum(c['marcada'] for c in resultado['outros']),1)
        clicar=Mock()
        with self.assertRaisesRegex(ValueError,'outros relatórios'):
            marcar_tres_livros(lambda:resultado,clicar)
        clicar.assert_not_called()

    def test_recusa_caixa_ausente_rotulo_duplicado_e_interno_indeterminado(self):
        imagem,dados,caixas=formulario()
        for caso in ('caixa','rotulo','estado'):
            im=imagem.copy(); d=copy.deepcopy(dados)
            if caso=='caixa':
                x,y,w,h=caixas['registro_icms']
                ImageDraw.Draw(im).rectangle((x-2,y-2,x+w+2,y+h+2),fill='#eeeeee')
            elif caso=='rotulo':
                outro=copy.deepcopy(dados)
                for k in d:d[k].extend(outro[k])
            else:
                x,y,w,h=caixas['registro_icms']
                ImageDraw.Draw(im).rectangle((x+2,y+2,x+w-3,y+h-3),fill='#999999')
            with self.subTest(caso=caso),self.assertRaises(ValueError):
                ler_formulario(im,d)

    def test_recusa_data_invalida_e_nao_confunde_inicial_do_rodape(self):
        imagem,dados,_=formulario()
        dados['text'][dados['text'].index('30/09/2026')]='31/09/2026'
        with self.assertRaises(ValueError):ler_formulario(imagem,dados)

    def test_estado_indeterminado_nao_e_tratado_como_desmarcado(self):
        imagem,dados,_=formulario()
        atual=ler_formulario(imagem,dados)
        atual['livros']['registro_icms']['marcada']=None
        clicar=Mock()
        with self.assertRaisesRegex(ValueError,'indeterminado'):
            marcar_tres_livros(lambda:atual,clicar)
        clicar.assert_not_called()

    def test_cli_arquivo_local_le_ocr_sem_alterar_arquivo_ou_emitir(self):
        import contextlib,io,tempfile
        from scripts.revisar_formulario_livros import main
        imagem,_,_=formulario(('registro_icms',))
        with tempfile.TemporaryDirectory() as pasta:
            caminho=Path(pasta)/'formulario.png'; imagem.save(caminho)
            antes=caminho.read_bytes(); saida=io.StringIO()
            with contextlib.redirect_stdout(saida):
                resultado=main(['--imagem',str(caminho)])
            self.assertEqual(resultado,0)
            self.assertEqual(caminho.read_bytes(),antes)
            self.assertIn('Registro de ICMS: marcada',saida.getvalue())
            self.assertIn('nenhum relatório foi emitido',saida.getvalue())

    def test_nao_desmarca_livros_ja_marcados_e_confere_apos_cada_alteracao(self):
        imagem,dados,_=formulario(('registro_entradas','registro_icms'))
        atual=ler_formulario(imagem,dados)
        final=copy.deepcopy(atual); final['livros']['registro_saidas']['marcada']=True
        leituras=Mock(side_effect=[atual,atual,final,final,final])
        clicar=Mock()
        self.assertEqual(marcar_tres_livros(leituras,clicar),final)
        clicar.assert_called_once_with(*atual['livros']['registro_saidas']['posicao'])
        clicar.reset_mock()
        with self.assertRaisesRegex(ValueError,'não confirmada'):
            marcar_tres_livros(lambda:atual,clicar)
        clicar.assert_called_once()

    def test_formulario_sintetico_lido_com_tesseract_real(self):
        import shutil
        if not shutil.which('tesseract'):self.skipTest('Tesseract indisponível.')
        import pytesseract
        imagem,_,_=formulario(('registro_icms',))
        dados=pytesseract.image_to_data(imagem.resize((imagem.width*2,imagem.height*2)),lang='por',output_type=pytesseract.Output.DICT)
        r=ler_formulario(imagem,dados,2)
        self.assertTrue(r['livros']['registro_icms']['marcada'])
        self.assertFalse(r['livros']['registro_entradas']['marcada'])
        self.assertEqual(r['periodo']['final']['valor'],'30/09/2026')
