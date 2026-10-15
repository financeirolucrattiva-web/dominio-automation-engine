"""Pixels/OCR locais sintéticos; não afirmam calibração da captura real."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont
from app.formulario_livros import (ler_formulario, ler_selecao, ler_selecao_com_ocr,
                                   marcar_tres_livros, ROTULOS)

FONTES = (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('C:/Windows/Fonts/arial.ttf'))


def formulario(marcados=(), outros=False, dx=0, dy=0, fator=1, cinzas=False,
               tridimensional=False):
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
        if tridimensional:
            # Fixture ilustrativa de borda 3D, sem alegar pixels do PC real.
            desenho.line([(x,y+12),(x,y),(x+12,y)],fill='#808080')
            desenho.line([(x+1,y+11),(x+1,y+1),(x+11,y+1)],fill='#404040')
            desenho.line([(x+12,y),(x+12,y+12),(x,y+12)],fill='white')
            desenho.line([(x+11,y+1),(x+11,y+11),(x+1,y+11)],fill='#dfdfdf')
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
    def test_transitorio_antes_do_proximo_livro_e_na_conferencia_final_nao_abortam(self):
        im,dados,_=formulario();atual=ler_selecao(im,dados)
        leituras_pendentes=[]
        def ler():
            if leituras_pendentes:
                proxima=leituras_pendentes.pop(0)
                if isinstance(proxima,Exception):raise proxima
                return proxima
            return copy.deepcopy(atual)
        def clicar(x,y):
            tipo=next(t for t,c in atual['livros'].items() if c['posicao']==(x,y))
            atual['livros'][tipo]['marcada']=True
            # Confirmação pós-clique chega; captura seguinte ainda transita.
            leituras_pendentes.extend([copy.deepcopy(atual),ValueError('OCR transitório')])
        clique=Mock(side_effect=clicar)
        with patch('app.formulario_livros.time.sleep'):
            final=marcar_tres_livros(ler,clique)
        self.assertTrue(all(c['marcada'] for c in final['livros'].values()))
        self.assertEqual(clique.call_count,3)
        self.assertEqual({c.args for c in clique.call_args_list},
                         {c['posicao'] for c in atual['livros'].values()})

    def test_livro_ja_confirmado_que_desaparece_nao_e_clicado_novamente(self):
        im,dados,_=formulario();inicial=ler_selecao(im,dados)
        confirmado=copy.deepcopy(inicial);confirmado['livros']['registro_entradas']['marcada']=True
        leituras=Mock(side_effect=[inicial,confirmado]+[inicial]*5)
        clique=Mock()
        with patch('app.formulario_livros.time.sleep'),self.assertRaises(ValueError):
            marcar_tres_livros(leituras,clique)
        clique.assert_called_once_with(*inicial['livros']['registro_entradas']['posicao'])

    def test_grupo_parcial_e_posicoes_duplicadas_nao_autorizam_clique(self):
        im,dados,_=formulario();inicial=ler_selecao(im,dados)
        for caso in ('outros','posicoes'):
            atual=copy.deepcopy(inicial);clique=Mock()
            if caso=='outros':atual['outros'].pop()
            else:atual['livros']['registro_icms']['posicao']=atual['livros']['registro_entradas']['posicao']
            with self.subTest(caso=caso),patch('app.formulario_livros.time.sleep'),self.assertRaises(ValueError):
                marcar_tres_livros(lambda:atual,clique)
            clique.assert_not_called()

    def test_aguarda_checkbox_repintar_sem_clicar_de_novo(self):
        import copy
        from unittest.mock import patch
        im,dados,_=formulario(('registro_saidas','registro_icms'))
        antigo=ler_selecao(im,dados);novo=copy.deepcopy(antigo)
        novo['livros']['registro_entradas']['marcada']=True
        leituras=Mock(side_effect=[antigo,antigo,ValueError('OCR transitório'),novo,novo,novo,novo])
        clicar=Mock()
        with patch('app.formulario_livros.time.sleep'):
            final=marcar_tres_livros(leituras,clicar)
        self.assertTrue(all(l['marcada'] for l in final['livros'].values()))
        clicar.assert_called_once_with(*antigo['livros']['registro_entradas']['posicao'])

    def test_timeout_marcacao_nao_tenta_segundo_livro_nem_reclique(self):
        from unittest.mock import patch
        im,dados,_=formulario();atual=ler_selecao(im,dados);clicar=Mock()
        with patch('app.formulario_livros.time.sleep'),self.assertRaisesRegex(ValueError,'não confirmada'):
            marcar_tres_livros(lambda:atual,clicar)
        clicar.assert_called_once_with(*atual['livros']['registro_entradas']['posicao'])

    def test_selecao_nao_depende_de_datas_visiveis_ou_validas(self):
        imagem,dados,_=formulario()
        dados['text']=[t if not '/' in t else 'DATA INDISPONIVEL' for t in dados['text']]
        selecao=ler_selecao(imagem,dados)
        self.assertEqual(set(selecao),{'livros','outros'})
        self.assertEqual(len(selecao['outros']),13)
        self.assertFalse(any(c['marcada'] for c in selecao['livros'].values()))
        with self.assertRaises(ValueError):ler_formulario(imagem,dados)

    def test_diagnostico_da_selecao_e_parcial_sem_ocr_livre(self):
        imagem,dados,caixas=formulario()
        x,y,w,h=caixas['registro_icms']
        ImageDraw.Draw(imagem).rectangle((x-2,y-2,x+w+2,y+h+2),fill='#eeeeee')
        for chave,valor in zip(dados,('EMPRESA PRIVADA CNPJ',1200,1200,200,20)):
            dados[chave].append(valor)
        eventos=[]
        with self.assertRaises(ValueError):ler_selecao(imagem,dados,registrar=eventos.append)
        self.assertEqual(len(eventos),1)
        self.assertFalse(eventos[0]['confirmado'])
        self.assertEqual(eventos[0]['motivo'],'caixa_livro_nao_confirmada')
        self.assertIsInstance(eventos[0]['caixas_detectadas'],int)
        self.assertEqual(eventos[0]['livros']['registro_icms']['candidatas'],0)
        self.assertNotIn('PRIVADA',json.dumps(eventos))
        self.assertNotIn('CNPJ',json.dumps(eventos))

    def test_preparos_ocr_preservam_imagem_original_das_caixas(self):
        from app import tela
        imagem,dados,_=formulario(('registro_icms',))
        dados4 = copy.deepcopy(dados)
        for chave in ('left','top','width','height'):
            dados4[chave] = [v*2 for v in dados4[chave]]
        original=imagem.tobytes(); eventos=[]
        with patch.object(tela,'_ler_dados_ocr',return_value={'text':[]}), \
                patch.object(tela,'ler_dados_ocr_formulario',side_effect=[{'text':[]},dados4],create=True) as preparar, \
                patch.object(tela,'ler_dados_ocr_windows',return_value=None):
            resultado=ler_selecao_com_ocr(imagem,eventos.append)
        self.assertTrue(resultado['livros']['registro_icms']['marcada'])
        self.assertEqual(imagem.tobytes(),original)
        self.assertTrue(all(c.args[0] is imagem for c in preparar.call_args_list))
        self.assertEqual([c.kwargs['preparo'] for c in preparar.call_args_list],['cinza','binaria'])
        self.assertTrue(eventos[-1]['confirmado'])
        self.assertEqual(eventos[-1]['preparo'],'binaria')

    def test_rotulos_que_cada_leitura_perde_sao_combinados_na_mesma_captura(self):
        # Caso real: com Entradas marcada (negrito + grupo Anexar) cada OCR perdia 1-2 rótulos.
        from app import tela
        imagem,dados,_=formulario(('registro_entradas',))
        def sem(dados_, tokens, fator=1):
            novo={k:[] for k in dados_}
            for i,t in enumerate(dados_['text']):
                if t in tokens: continue
                for k in dados_:
                    novo[k].append(dados_[k][i]*(fator if k!='text' else 1))
            return novo
        a=sem(dados,{'Saídas','ICMS'})              # leitura 1 (escala 2): perde Saídas e ICMS
        b=sem(dados,{'Entradas','capa'},fator=2)    # leitura 2 (escala 4): perde Entradas e Contra capa
        eventos=[]
        with patch.object(tela,'_ler_dados_ocr',side_effect=[a,b]), \
                patch.object(tela,'ler_dados_ocr_formulario',return_value=None,create=True), \
                patch.object(tela,'ler_dados_ocr_windows',return_value=None):
            resultado=ler_selecao_com_ocr(imagem,eventos.append)
        self.assertTrue(resultado['livros']['registro_entradas']['marcada'])
        self.assertFalse(resultado['livros']['registro_saidas']['marcada'])
        self.assertEqual(eventos[-1]['motor'],'combinado')
        self.assertTrue(eventos[-1]['confirmado'])
        # Sem leitura complementar, continua recusando.
        with patch.object(tela,'_ler_dados_ocr',return_value=a), \
                patch.object(tela,'ler_dados_ocr_formulario',return_value=None,create=True), \
                patch.object(tela,'ler_dados_ocr_windows',return_value=None):
            with self.assertRaises(ValueError):
                ler_selecao_com_ocr(imagem)

    def test_combinacao_recusa_rotulo_com_posicoes_discordantes_ou_ordem_incoerente(self):
        from app.formulario_livros import combinar_rotulos, FRASES_SELECAO, ORDEM_VERTICAL
        def leitura(**ajustes):
            base={c:{'x':291.0,'y':20.0+30*i,'w':80.0,'h':10.0} for i,c in enumerate(ORDEM_VERTICAL)}
            base['titulo']['x']=30.0
            base.update(ajustes); return base
        self.assertIsNotNone(combinar_rotulos([leitura()]))
        # Mesmo rótulo em dois lugares diferentes: descarta tudo.
        self.assertIsNone(combinar_rotulos([leitura(), leitura(registro_icms={'x':291.0,'y':200.0,'w':80.0,'h':10.0})]))
        # Rótulo faltando em todas as leituras.
        parcial=leitura(); del parcial['registro_saidas']
        self.assertIsNone(combinar_rotulos([parcial]))
        # Ordem vertical invertida (Saídas acima de Entradas).
        self.assertIsNone(combinar_rotulos([leitura(registro_saidas={'x':291.0,'y':50.0,'w':80.0,'h':10.0},
                                                    registro_entradas={'x':291.0,'y':80.0,'w':80.0,'h':10.0})]))
        # Opções desalinhadas horizontalmente.
        self.assertIsNone(combinar_rotulos([leitura(registro_icms={'x':340.0,'y':110.0,'w':80.0,'h':10.0})]))

    def test_motor_indisponivel_nao_imprime_excecao_ou_dados_livres(self):
        from app import tela
        imagem,_,_=formulario(); eventos=[]
        with patch.object(tela,'_ler_dados_ocr',side_effect=RuntimeError('CAMINHO PRIVADO')), \
                patch.object(tela,'ler_dados_ocr_formulario',side_effect=RuntimeError('CAMINHO PRIVADO'),create=True), \
                patch.object(tela,'ler_dados_ocr_windows',return_value=None),self.assertRaises(ValueError):
            ler_selecao_com_ocr(imagem,eventos.append)
        self.assertTrue(eventos)
        self.assertNotIn('PRIVADO',json.dumps(eventos))
        self.assertTrue(all(e['motivo']=='motor_selecao_indisponivel' for e in eventos))

    def test_caixas_3d_sinteticas_nao_confundem_sombra_com_marcacao(self):
        for fator in (1,2):
            for marcados in ((),('registro_icms',)):
                imagem,dados,_=formulario(marcados,tridimensional=True,fator=fator,dx=90,dy=30)
                resultado=ler_selecao(imagem,dados)
                self.assertEqual(len(resultado['outros']),13)
                self.assertFalse(any(c['marcada'] for c in resultado['outros']))
                self.assertEqual({t for t,c in resultado['livros'].items() if c['marcada']},set(marcados))

    def test_caixa_de_outro_livro_ausente_continua_bloqueando_grupo_15(self):
        imagem,dados,_=formulario(tridimensional=True)
        # Remove a caixa de Registro de ISS, mantendo os três alvos visíveis.
        ImageDraw.Draw(imagem).rectangle((68,241,86,258),fill='#eeeeee')
        eventos=[]
        with self.assertRaises(ValueError):ler_selecao(imagem,dados,registrar=eventos.append)
        self.assertEqual(eventos[-1]['caixas_emitir'],15)
        self.assertEqual(eventos[-1]['motivo'],'grupo_emitir_incompleto')
        self.assertFalse(eventos[-1]['confirmado'])

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
