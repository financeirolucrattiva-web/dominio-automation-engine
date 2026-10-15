"""Botões e formulário sintéticos; nenhum clique ou homologação real."""
import copy
from pathlib import Path
import shutil
import types
import unittest
from unittest.mock import Mock,patch

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
    def test_bordas_3d_do_log_real_contam_um_botao_em_qualquer_posicao_escala(self):
        # Somente geometria do log, sem pixels ou dados de cliente.
        bordas=((835,403,82,28),(834,402,79,25),(835,435,82,28),(834,434,79,25))
        for fator,dx,dy in ((1,0,0),(2,100,40)):
            medidas=[((x+dx)*fator,(y+dy)*fator,w*fator,h*fator) for x,y,w,h in bordas]
            for ordem in (medidas,list(reversed(medidas))):
                with self.subTest(fator=fator):
                    unicos=botoes._deduplicar_retangulos(ordem)
                    self.assertEqual(set(unicos),{medidas[0],medidas[2]})

    def test_sobreposicao_sem_quatro_lados_proximos_nao_funde_botoes(self):
        caixas=((100,100,82,28),(110,100,82,28),(100,132,82,28))
        self.assertEqual(set(botoes._deduplicar_retangulos(caixas)),set(caixas))

    def test_duas_bordas_por_botao_nao_bloqueiam_ok_com_rotulo_confirmado(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        bordas=((280,80,76,26),(279,79,73,23),(280,116,76,26),(279,115,73,23))
        with patch.object(botoes,'_retangulos',return_value=botoes._deduplicar_retangulos(bordas)), \
             patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:{'fechar'} if c[1]>110 else {'ok'}):
            self.assertEqual(botoes.achar_ok_resumo(imagem),(318,93))

    def test_fechar_ausente_global_e_lido_no_botao_sem_offset(self):
        imagem,dados=tela_resumo()
        dados={k:[v for i,v in enumerate(valores) if i!=4] for k,valores in dados.items()}
        self.preparar(imagem,dados)
        with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                          {'fechar'} if c[1]>110 else {'ok'}):
            self.assertIsNotNone(botoes.achar_ok_resumo(imagem))

    def test_um_erro_ocr_nao_veta_duas_leituras_exatas_e_conflito_real_veta(self):
        imagem,_=tela_resumo()
        def dado(texto,top=None):
            tokens=texto.split(); return {'text':tokens,'top':top or [2]*len(tokens),
                                         'height':[9]*len(tokens)}
        for leituras,esperado in (([dado('0K'),dado('OK'),dado('OK'),dado('')],{'ok'}),
                                  ([dado('OK'),dado('OK'),dado('OK Cancelar'),dado('')],{'contradicao'}),
                                  ([dado('OK'),dado('OK'),dado('Fechar'),dado('')],{'contradicao'}),
                                  ([dado('OK'),dado('OK'),dado('OK Cancelar',[2,14]),dado('')],{'contradicao'})):
            with self.subTest(esperado=esperado),patch.object(botoes.tela,'ler_dados_ocr_linha_rotulo',side_effect=leituras):
                self.assertEqual(botoes._texto_recorte(imagem,(280,80,76,26)),esperado)

    def test_borda_em_l_sem_quatro_lados_nao_vira_botao(self):
        imagem,_=tela_resumo(); desenho=ImageDraw.Draw(imagem)
        desenho.rectangle((275,75,362,110),fill='#eeeeee')
        desenho.line((280,80,280,105),fill='black')
        desenho.line((280,105,355,105),fill='black')
        caixas=botoes._retangulos(imagem,24)
        self.assertFalse(any(botoes._dentro((315,94),c) for c in caixas))

    def test_wrapper_reutiliza_ocr_e_descarta_ao_terminar_a_analise(self):
        imagem,_=tela_resumo(); engine=types.ModuleType('winocr')
        engine.recognize_pil_sync=Mock(return_value={'lines':[]})
        dados={'text':[],'left':[],'top':[],'width':[],'height':[]}
        def analisar(im,registrar):
            for _ in range(3):
                botoes.tela._ler_dados_ocr(im.copy(),2)
                botoes.tela.ler_dados_ocr_windows(im.copy(),2)
            return (315,94)
        with patch.dict('sys.modules',{'winocr':engine}), \
                patch.object(botoes.tela.pytesseract,'image_to_data',return_value=dados) as tess, \
                patch.object(botoes,'_achar_ok_resumo_na_captura',side_effect=analisar):
            self.assertEqual(botoes.achar_ok_resumo(imagem),(315,94))
            self.assertEqual(tess.call_count,1); self.assertEqual(engine.recognize_pil_sync.call_count,1)
            botoes.achar_ok_resumo(imagem)
            self.assertEqual(tess.call_count,2); self.assertEqual(engine.recognize_pil_sync.call_count,2)

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract indisponível.')
    def test_ok_compartilha_leitura_local_quando_final_falta_na_tela_inteira(self):
        imagem,dados=tela_resumo()
        dados={k:[v for i,v in enumerate(valores) if i!=3] for k,valores in dados.items()}
        self.preparar(imagem,dados)
        with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                          {'fechar'} if c[1]>110 else {'ok'}):
            self.assertIsNotNone(botoes.achar_ok_resumo(imagem))

    def preparar(self,imagem,dados,ok=None):
        dados=copy.deepcopy(dados)
        if ok is not None:
            for k,v in zip(dados,('OK',(ok[0]-10)*2,(ok[1]-4)*2,40,16)):
                dados[k].append(v)
        def ocr(_imagem,escala):
            copia=copy.deepcopy(dados)
            for chave in ('left','top','width','height'):
                copia[chave]=[v*escala/2 for v in copia[chave]]
            return copia
        self.addCleanup(patch.stopall)
        self.dados_ocr=patch.object(botoes.tela,'_ler_dados_ocr',side_effect=ocr).start()
        self.dados_windows=patch.object(botoes.tela,'ler_dados_ocr_windows',return_value=None).start()
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
        self.assertEqual({c.args[1] for c in self.dados_ocr.call_args_list}, {2,4})
        self.assertEqual({c.args[1] for c in self.dados_windows.call_args_list}, {2,4})

    def test_book_fora_da_coluna_nao_veta_botao_ok_real(self):
        imagem,dados=tela_resumo()
        for k,v in zip(dados,('BOOK',40,40,100,20)):dados[k].append(v)
        self.preparar(imagem,dados)
        # Simula a busca antiga por substring devolvendo BOOK.
        self.texto.side_effect=lambda im,t,**kw:(40,30) if t=='OK' else None
        with patch.object(botoes,'_texto_recorte',side_effect=lambda im,c:
                          {'fechar'} if c[1]>110 else {'ok'}):
            self.assertIsNotNone(botoes.achar_ok_resumo(imagem))

    def test_diagnostico_do_outro_ok_nao_imprime_ocr_livre(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados,ok=(30,30))
        detalhes=[]
        self.assertIsNone(botoes.achar_ok_resumo(imagem,detalhes.append))
        self.assertEqual(detalhes[-1]['motivo'],'outro_ok_exato')
        self.assertNotIn('texto',detalhes[-1])

    def test_diagnostico_distingue_borda_de_fechar_e_texto_ok(self):
        imagem,dados=tela_resumo(); self.preparar(imagem,dados)
        detalhes=[]
        with patch.object(botoes,'_texto_recorte',return_value={'texto privado'}):
            self.assertIsNone(botoes.achar_ok_resumo(imagem,detalhes.append))
        self.assertEqual(detalhes[-1]['motivo'],'texto_fechar_nao_confirmado')
        self.assertNotIn('privado',str(detalhes))

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
