"""Referência manual local: comparação exata e nenhuma equivalência OCR."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import ImageDraw

from app import referencia_unidade as ref,seletor_pasta as seletor
from test_seletor_pasta_ocr import dialogo


class TestReferenciaUnidade(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.arquivo=Path(self.tmp.name)/'referencia.json'
        self.imagem=dialogo(); self.combo=(105,60,456,27)
        self.recorte=self.imagem.crop(seletor._area_unidade(self.combo))

    def gravar(self):
        return ref.gravar(self.imagem,self.combo,'M',arquivo=self.arquivo)

    def ler(self,recorte=None):
        return ref.reconhecer(recorte if recorte is not None else self.recorte,arquivo=self.arquivo)

    def alterar(self,**campos):
        d=json.loads(self.arquivo.read_text()); d.update(campos)
        self.arquivo.write_text(json.dumps(d))

    def test_pixels_exatos_identificam_somente_o_client_c_declarado(self):
        self.gravar(); d=self.ler()
        self.assertEqual(d,{'tipo':'client_c','letra':'M','origem':'calibracao_visual_local'})

    def test_mudar_um_pixel_ja_invalida_sem_tolerancia_ou_mascara(self):
        self.gravar(); im=self.recorte.copy(); r,g,b=im.getpixel((8,8))
        im.putpixel((8,8),(255-r,255-g,255-b))
        self.assertIsNone(self.ler(im))

    def test_tamanho_diferente_nao_e_redimensionado(self):
        self.gravar()
        self.assertIsNone(self.ler(self.recorte.resize((400,23))))

    def test_arquivo_ausente_ou_json_corrompido_nao_identifica_unidade(self):
        self.assertIsNone(self.ler())
        self.arquivo.write_text('corrompido')
        self.assertIsNone(self.ler())

    def test_tipo_letra_versao_confirmacao_ou_origem_invalidos_sao_rejeitados(self):
        for campo,valor in (('tipo','client_z'),('letra','MM'),('letra','m'),
                ('versao',2),('versao',True),('confirmada_pelo_operador',False),('origem_sha256','invalid')):
            with self.subTest(campo=campo,valor=valor):
                self.gravar(); self.alterar(**{campo:valor}); self.assertIsNone(self.ler())

    def test_metadados_de_geometria_fora_da_imagem_nao_identificam_unidade(self):
        for campo,valor in (('combo_origem',[105,60,999,27]),('dimensoes',[427,24]),
                            ('imagem_origem',[100,100]),('dimensoes',None)):
            with self.subTest(campo=campo):
                self.gravar(); self.alterar(**{campo:valor}); self.assertIsNone(self.ler())

    def test_png_ou_hash_corrompidos_nao_identificam_unidade(self):
        for campo,valor in (('png','nao e base64'),('png_sha256','0'*64)):
            with self.subTest(campo=campo):
                self.gravar(); self.alterar(**{campo:valor}); self.assertIsNone(self.ler())

    def test_conteudo_acima_do_limite_e_rejeitado(self):
        self.arquivo.write_bytes(b' '*(ref.LIMITE+1))
        self.assertIsNone(self.ler())

    def test_campo_azul_nao_e_calibrado(self):
        ImageDraw.Draw(self.imagem).rectangle((108,63,250,83),fill='#0078d7')
        with self.assertRaises(ValueError):self.gravar()
        self.assertFalse(self.arquivo.exists())

    def test_campo_vazio_nao_e_calibrado(self):
        ImageDraw.Draw(self.imagem).rectangle((107,62,534,84),fill='white')
        with self.assertRaises(ValueError):self.gravar()
        self.assertFalse(self.arquivo.exists())

    def test_gravacao_atomica_preserva_referencia_anterior_se_replace_falhar(self):
        self.gravar(); antes=self.arquivo.read_bytes()
        with patch.object(ref.os,'replace',side_effect=OSError('erro sintetico')):
            with self.assertRaises(OSError):self.gravar()
        self.assertEqual(self.arquivo.read_bytes(),antes)
        self.assertEqual(list(self.arquivo.parent.iterdir()),[self.arquivo])

    def test_match_visual_passa_pela_medicao_e_completar_sem_fingir_ocr(self):
        self.gravar(); palavras=seletor._palavras(self.imagem)
        palavras=[p for p in palavras if not (105<p['x']<561 and 60<p['y']<87)]
        palavras.append({'texto':'lient C (M:N)','x':112,'y':65,'w':100,'h':12})
        with patch.object(ref,'ARQUIVO',self.arquivo),patch.object(seletor,'_palavras',return_value=palavras), \
             patch.object(seletor,'_refinar_unidade',side_effect=AssertionError('OCR de campo desnecessario')):
            d=seletor.medir_dialogo(self.imagem,somente_unidade=True)
            completo=seletor._completar_dialogo(d)
        self.assertEqual(completo['unidade_visual']['origem'],'calibracao_visual_local')
        self.assertTrue(seletor._drive_selecionado(completo,'M'))
        self.assertFalse(seletor._drive_selecionado(completo,'Q'))
        self.assertEqual(seletor._assinatura_unidade(self.imagem,completo)[1],'clientc:m')
        self.assertTrue(any(p['texto']=='lient C (M:N)' for p in completo['palavras']))

    def test_ocr_canonico_contraditorio_impede_aplicar_referencia(self):
        self.gravar(); palavras=seletor._palavras(self.imagem)
        palavras=[p for p in palavras if not (105<p['x']<561 and 60<p['y']<87)]
        palavras.append({'texto':'Client Z (M:)','x':112,'y':65,'w':100,'h':12})
        with patch.object(ref,'ARQUIVO',self.arquivo),patch.object(seletor,'_palavras',return_value=palavras), \
             patch.object(seletor,'_refinar_unidade',side_effect=lambda im,ps,c:ps):
            d=seletor.medir_dialogo(self.imagem,somente_unidade=True)
        self.assertNotIn('unidade_visual',d)
        self.assertFalse(seletor._drive_selecionado(d,'M'))


class TestCalibracaoCLI(unittest.TestCase):
    def setUp(self):
        from scripts import revisar_seletor_pasta as diagnostico
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name)
        self.patch=patch.object(diagnostico,'ROOT',self.raiz)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def carregar(self):
        caminho=Path(__file__).resolve().parents[1]/'scripts'/'calibrar_unidade_pasta.py'
        spec=importlib.util.spec_from_file_location('calibrar_unidade_teste',caminho)
        modulo=importlib.util.module_from_spec(spec); spec.loader.exec_module(modulo)
        return modulo

    def test_calibracao_nao_consulta_referencia_antiga_e_guarda_so_roi(self):
        modulo=self.carregar(); im=dialogo(); combo=(105,60,456,27)
        d={'combo':combo,'lista':None,'palavras':[]}
        with tempfile.TemporaryDirectory() as pasta:
            pasta=Path(pasta); fonte=pasta/'fonte.png'; im.save(fonte); arquivo=pasta/'ref.json'
            saida=io.StringIO()
            with patch.object(ref,'ARQUIVO',arquivo),patch.object(seletor,'medir_dialogo',return_value=d) as medir, \
                 contextlib.redirect_stdout(saida):
                self.assertEqual(modulo.main(['--imagem',str(fonte),'--client-c','M']),0)
            self.assertFalse(medir.call_args.kwargs['usar_referencia'])
            dados=json.loads(arquivo.read_text())
            self.assertEqual(dados['dimensoes'],[427,23])
            self.assertNotIn(dados['png'],saida.getvalue())
            self.assertTrue(ref.reconhecer(im.crop(seletor._area_unidade(combo)),arquivo=arquivo))

    def test_contradicao_literal_de_outro_tipo_ou_letra_nao_cria_referencia(self):
        modulo=self.carregar()
        for texto in ('Client Z (M:)','Client C (Q:)','Servidor (C:)'):
            with self.subTest(texto=texto),tempfile.TemporaryDirectory() as pasta:
                arquivo=Path(pasta)/'ref.json'; fonte=Path(pasta)/'fonte.png'; dialogo().save(fonte)
                d={'combo':(105,60,456,27),'lista':None,
                   'palavras':[{'texto':texto,'x':112,'y':65,'w':110,'h':12}]}
                with patch.object(ref,'ARQUIVO',arquivo),patch.object(seletor,'medir_dialogo',return_value=d), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(modulo.main(['--imagem',str(fonte),'--client-c','M']),1)
                self.assertFalse(arquivo.exists())

    def test_calibracao_ao_vivo_captura_uma_vez_sem_buscar_referencia_antiga(self):
        from app import tela
        modulo=self.carregar(); im=dialogo()
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'referencia.json'
            d={'combo':(105,60,456,27),'lista':None,'palavras':[]}
            with patch.object(ref,'ARQUIVO',arquivo),patch.object(seletor,'medir_dialogo',return_value=d) as medir, \
                 patch.object(tela,'capturar_tela',return_value=im) as capturar, \
                 patch.object(modulo.time,'sleep') as esperar,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(modulo.main(['--ao-vivo','--client-c','M']),0)
            esperar.assert_called_once_with(5)
            capturar.assert_called_once_with()
            self.assertFalse(medir.call_args.kwargs['usar_referencia'])
            self.assertTrue(arquivo.exists())

    def executar_recusa(self,*,imagem=None,detalhes=None,erro_medicao=None,erro_gravacao=None):
        from app import tela
        modulo=self.carregar()
        im=dialogo() if imagem is None else imagem
        fonte=self.raiz/'fonte.png'; im.save(fonte)
        d={'combo':(105,60,456,27),'lista':None,'palavras':[]} if detalhes is None else detalhes
        arquivo=self.raiz/'referencia.json'; arquivo.write_bytes(b'referencia anterior')
        saida=io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(ref,'ARQUIVO',arquivo))
            stack.enter_context(patch.object(seletor,'medir_dialogo',return_value=d,side_effect=erro_medicao))
            capturar=stack.enter_context(patch.object(tela,'capturar_tela'))
            if erro_gravacao is not None:
                stack.enter_context(patch.object(ref,'gravar',side_effect=erro_gravacao))
            stack.enter_context(contextlib.redirect_stdout(saida))
            self.assertEqual(modulo.main(['--imagem',str(fonte),'--client-c','M']),1)
        capturar.assert_not_called()
        self.assertEqual(arquivo.read_bytes(),b'referencia anterior')
        texto=saida.getvalue()
        resultado=json.loads(next(l.removeprefix('UNIDADE_REFERENCIA ') for l in texto.splitlines()
                                  if l.startswith('UNIDADE_REFERENCIA ')))
        return resultado,texto

    def test_campo_azul_informa_causa_e_salva_so_o_campo_da_captura_recusada(self):
        from PIL import Image
        im=dialogo(); im.putpixel((0,0),(255,0,255))
        ImageDraw.Draw(im).rectangle((108,63,250,83),fill='#0078d7')
        r,texto=self.executar_recusa(imagem=im)
        self.assertEqual(r['motivo'],'campo_ainda_azul')
        self.assertEqual(r['fase'],'gravar_referencia')
        self.assertTrue(r['realce_no_campo']); self.assertFalse(r['lista_aberta'])
        self.assertIn('Clique no vazio branco dentro da árvore',texto)
        with Image.open(self.raiz/r['recorte_local']) as salvo:
            self.assertEqual(salvo.width,456*4+16)
            cores={c for _,c in salvo.convert('RGB').getcolors(salvo.width*salvo.height)}
        self.assertIn((0,120,215),cores)
        self.assertNotIn((255,0,255),cores)
        self.assertEqual(len(list((self.raiz/'capturas').glob('*.png'))),1)

    def test_campo_sem_texto_nao_e_confundido_com_campo_azul(self):
        im=dialogo(); ImageDraw.Draw(im).rectangle((107,62,534,84),fill='white')
        r,_=self.executar_recusa(imagem=im)
        self.assertEqual(r['motivo'],'campo_sem_texto_suficiente')
        self.assertFalse(r['realce_no_campo'])
        self.assertIn('recorte_local',r)

    def test_lista_aberta_tem_motivo_proprio_sem_gravar_referencia(self):
        r,_=self.executar_recusa(detalhes={'combo':(105,60,456,27),'lista':(105,88,456,50),'palavras':[]})
        self.assertEqual(r['motivo'],'lista_aberta')
        self.assertEqual(r['fase'],'conferir_unidade')
        self.assertTrue(r['lista_aberta'])

    def test_identidade_contraditoria_tem_motivo_proprio(self):
        d={'combo':(105,60,456,27),'lista':None,
           'palavras':[{'texto':'Client Z (M:)','x':112,'y':65,'w':110,'h':12}]}
        r,_=self.executar_recusa(detalhes=d)
        self.assertEqual(r['motivo'],'identidade_contraditoria')

    def test_dialogo_nao_confirmado_nao_salva_tela_inteira_nem_expoe_erro_ocr(self):
        r,texto=self.executar_recusa(erro_medicao=ValueError('DADOS_PRIVADOS_DO_OCR'))
        self.assertEqual(r['motivo'],'dialogo_nao_confirmado')
        self.assertEqual(r['fase'],'medir_dialogo')
        self.assertNotIn('DADOS_PRIVADOS_DO_OCR',texto)
        self.assertNotIn('recorte_local',r)
        self.assertFalse((self.raiz/'capturas').exists())

    def test_falha_ao_salvar_referencia_nao_expoe_mensagem_do_sistema(self):
        r,texto=self.executar_recusa(erro_gravacao=OSError('CAMINHO_PRIVADO'))
        self.assertEqual(r['motivo'],'falha_salvar_referencia')
        self.assertNotIn('CAMINHO_PRIVADO',texto)

    def test_falha_ao_salvar_recorte_nao_oculta_motivo_original(self):
        from scripts import revisar_seletor_pasta as diagnostico
        im=dialogo(); ImageDraw.Draw(im).rectangle((108,63,250,83),fill='#0078d7')
        with patch.object(diagnostico,'salvar_recorte_unidade',side_effect=OSError('DADOS_PRIVADOS')):
            r,texto=self.executar_recusa(imagem=im)
        self.assertEqual(r['motivo'],'campo_ainda_azul')
        self.assertFalse(r['recorte_salvo'])
        self.assertNotIn('DADOS_PRIVADOS',texto)


if __name__=='__main__':unittest.main()
