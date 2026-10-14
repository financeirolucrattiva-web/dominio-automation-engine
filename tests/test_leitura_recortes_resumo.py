"""Pixels e OCR sintéticos; sem calibração do print real do operador."""
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from PIL import Image, ImageDraw, ImageFont

from app.leitura_resumo import (rotulos_periodo,medir_campos,normalizar_selecao,
                                data_da_linha,ler_campos)


def formulario(selecao='parcial',dx=0,dy=0,fator=1,ano='2026'):
    fonte=next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('C:/Windows/Fonts/arial.ttf')) if p.exists()),None)
    fonte=ImageFont.truetype(str(fonte),12) if fonte else ImageFont.load_default()
    imagem=Image.new('RGB',(410+dx,270+dy),'#eeeeee'); desenho=ImageDraw.Draw(imagem)
    dados={k:[] for k in ('text','left','top','width','height')}
    for papel,y,valor in (('inicial',80,'01/09/'+ano),('final',112,'30/09/'+ano)):
        x=35+dx
        for texto in ('Data',papel+':'):
            bbox=fonte.getbbox(texto); desenho.text((x,y+5+dy),texto,font=fonte,fill='black')
            for k,v in zip(dados,(texto,(x+bbox[0])*2*fator,(y+5+dy+bbox[1])*2*fator,
                                  (bbox[2]-bbox[0])*2*fator,(bbox[3]-bbox[1])*2*fator)):dados[k].append(v)
            x+=fonte.getlength(texto+' ')
        x=115+dx; y+=dy
        desenho.rectangle((x,y,x+97,y+23),fill='white',outline='#808080')
        desenho.line((x+81,y,x+81,y+23),fill='#808080')
        desenho.polygon([(x+86,y+8),(x+91,y+3),(x+96,y+8)],fill='black')
        desenho.polygon([(x+86,y+16),(x+91,y+21),(x+96,y+16)],fill='black')
        desenho.text((x+4,y+3),valor,font=fonte,fill='black')
        if papel=='inicial' and selecao:
            parte=valor if selecao=='total' else valor[:2]
            largura=int(fonte.getlength(parte))+1
            desenho.rectangle((x+4,y+2,x+4+largura,y+19),fill='#0078d7')
            desenho.text((x+4,y+3),parte,font=fonte,fill='white')
    desenho.rectangle((280+dx,80+dy,355+dx,105+dy),outline='#808080',fill='white')
    desenho.text((300+dx,85+dy),'OK',font=fonte,fill='black')
    if fator!=1:imagem=imagem.resize((imagem.width*fator,imagem.height*fator),Image.Resampling.NEAREST)
    return imagem,dados


def linha(textos):
    return {'text':textos,'left':[i*20 for i in range(len(textos))],
            'top':[5]*len(textos),'height':[10]*len(textos),'width':[15]*len(textos)}


class TestRecortesResumo(unittest.TestCase):
    def test_preto_branco_amplia_copia_sem_alterar_captura(self):
        from app import tela
        imagem,_=formulario('total');antes=imagem.tobytes()
        nova=tela.preparar_recorte_ocr(imagem,4,'binaria')
        self.assertEqual(nova.size,(imagem.width*4,imagem.height*4))
        self.assertLessEqual(set(nova.tobytes()),{0,255})
        self.assertEqual(imagem.tobytes(),antes)

    def test_datas_podem_ser_confirmadas_por_duas_leituras_binarias(self):
        imagem,dados=formulario();tela=Mock()
        tela._ler_dados_ocr.return_value=dados;tela.ler_dados_ocr_windows.return_value=None
        tela.ler_dados_ocr_formulario.return_value=None
        def ler(recorte,escala,preparo='cinza'):
            return linha(['01/09/2026']) if preparo=='binaria' else None
        tela.ler_dados_ocr_linha_data.side_effect=ler
        detalhes=[]
        with patch.multiple('app',create=True,tela=tela):campos=ler_campos(imagem,detalhes.append)
        self.assertEqual(campos['inicial']['valor'],'01/09/2026')
        self.assertTrue(any(l['variante']=='binaria' and l['valor']=='01/09/2026' for r in detalhes if 'leituras' in r for l in r['leituras']))

    def test_binaria_conflitante_preserva_recortes_locais_e_nao_escolhe_valor(self):
        imagem,dados=formulario();tela=Mock()
        tela._ler_dados_ocr.return_value=dados;tela.ler_dados_ocr_windows.return_value=None
        tela.ler_dados_ocr_formulario.return_value=None
        tela.ler_dados_ocr_linha_data.side_effect=lambda recorte,escala,preparo='cinza':linha(['01/09/2028' if preparo=='binaria' else '01/09/2026'])
        tela.preparar_recorte_ocr.return_value='recorte_binario'
        salvar=Mock()
        with patch.multiple('app',create=True,tela=tela),self.assertRaises(ValueError):ler_campos(imagem,salvar_recorte=salvar)
        self.assertEqual([c.args[1] for c in salvar.call_args_list],['inicial_original','inicial_binaria_6x'])

    def test_mede_bordas_claras_de_campo_windows_3d_sem_offsets(self):
        imagem,dados=formulario(None)
        desenho=ImageDraw.Draw(imagem)
        for x,y in ((115,80),(115,112)):
            desenho.line((x,y,x+97,y),fill='#808080')
            desenho.line((x,y,x,y+23),fill='#808080')
            desenho.line((x+97,y,x+97,y+23),fill='white')
            desenho.line((x,y+23,x+97,y+23),fill='white')
        campos=medir_campos(imagem,rotulos_periodo(dados,2))
        self.assertLess(campos['inicial']['posicao'][0],196)
        self.assertLess(campos['inicial']['posicao'][1],campos['final']['posicao'][1])

    def test_mede_dupla_e_spinner_com_selecao_parcial_total_ou_sem_selecao(self):
        for selecao in ('parcial','total',None):
            for fator in (1,2):
                imagem,dados=formulario(selecao,dx=140,dy=55,fator=fator)
                campos=medir_campos(imagem,rotulos_periodo(dados,2))
                for campo in campos.values():
                    self.assertGreater(campo['retangulo'][0],140*fator)
                    self.assertLess(campo['posicao'][0],(115+140+81)*fator)
                    self.assertLessEqual(campo['area_texto'][2],(115+140+81)*fator)

    def test_rotulos_unidos_e_ambiguos(self):
        imagem,dados=formulario(None)
        unido={k:[] for k in dados}
        for i,rotulo in ((0,'DataInicial:'),(2,'Data final:')):
            for k,v in zip(unido,(rotulo,dados['left'][i],dados['top'][i],150,20)):unido[k].append(v)
        self.assertEqual(set(rotulos_periodo(unido,2)),{'inicial','final'})
        duplicado={k:v+v for k,v in dados.items()}
        with self.assertRaises(ValueError):rotulos_periodo(duplicado,2)

    def test_normaliza_copia_preserva_glifos_e_nao_muda_imagem_original(self):
        imagem,_=formulario('total'); antes=imagem.tobytes()
        nova=normalizar_selecao(imagem)
        self.assertEqual(imagem.tobytes(),antes); self.assertNotEqual(nova.tobytes(),antes)
        self.assertEqual(nova.getpixel((120,83)),(255,255,255))
        regiao=nova.crop((119,83,187,100)).convert('L')
        self.assertGreater(sum(p<100 for p in regiao.tobytes()),50)

    def test_recompoe_apenas_componentes_completos_sem_corrigir_2028(self):
        for tokens in (['30/09/2028'],['30','/','09','/','20','28'],['30','09','2028'],['3009/2028'],['30/092028']):
            self.assertEqual(data_da_linha(linha(tokens)),'30/09/2028')
        for tokens in (['30/09/28'],['3/09/2028'],['30/09/2028','01/09/2028'],['31/02/2028'],['PRIVADO'],['30','09','20']):
            self.assertIsNone(data_da_linha(linha(tokens)))
        dados=linha(['30','09','2028']); dados['top'][2]=25
        self.assertIsNone(data_da_linha(dados))

    def test_campo_ausente_ou_outro_controle_proximo_recusa_geometria(self):
        imagem,dados=formulario(None); rotulos=rotulos_periodo(dados,2)
        faltando=imagem.copy(); ImageDraw.Draw(faltando).rectangle((110,110,216,139),fill='#eeeeee')
        with self.assertRaises(ValueError):medir_campos(faltando,rotulos)
        concorrente=imagem.copy(); ImageDraw.Draw(concorrente).rectangle((122,68,217,90),outline='black')
        with self.assertRaises(ValueError):medir_campos(concorrente,rotulos)

    def test_le_recortes_concordantes_sem_dependencia_da_data_solicitada(self):
        imagem,dados=formulario('total',ano='2028'); tela=Mock()
        tela._ler_dados_ocr.return_value=dados
        tela.ler_dados_ocr_windows.return_value=None
        tela.ler_dados_ocr_linha_data.return_value=linha(['30','/','09','/','2028'])
        detalhes=[]
        with patch.multiple('app',create=True,tela=tela):campos=ler_campos(imagem,detalhes.append)
        self.assertEqual(campos['inicial']['valor'],'30/09/2028')
        self.assertTrue(all(d['confirmado'] for d in detalhes if 'leituras' in d))
        self.assertTrue(all(d['valor'] is None or '2028' in d['valor'] for r in detalhes if 'leituras' in r for d in r['leituras']))

    def test_leituras_completas_conflitantes_ou_unica_leitura_recusam(self):
        imagem,dados=formulario(); tela=Mock(); tela._ler_dados_ocr.return_value=dados
        tela.ler_dados_ocr_windows.return_value=None
        for valores in ([linha(['30/09/2028']),linha(['30/09/2026'])]+[None]*2,
                        [linha(['30/09/2028'])]+[None]*3):
            tela.ler_dados_ocr_linha_data.side_effect=valores
            with self.subTest(valores=valores),patch.multiple('app',create=True,tela=tela),self.assertRaises(ValueError):
                ler_campos(imagem)

    def test_tesseract_real_le_selecao_parcial_e_total_por_recortes(self):
        import shutil
        if not shutil.which('tesseract'):self.skipTest('Tesseract indisponível.')
        from app import tela
        for selecao in ('parcial','total',None):
            imagem,dados=formulario(selecao)
            with patch.object(tela,'_ler_dados_ocr',return_value=dados),patch.object(tela,'ler_dados_ocr_windows',return_value=None):
                campos=ler_campos(imagem)
            self.assertEqual(campos['inicial']['valor'],'01/09/2026')
            self.assertEqual(campos['final']['valor'],'30/09/2026')
