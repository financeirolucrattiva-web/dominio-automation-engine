"""Confirmação EFD: múltiplas leituras antes de classificar o título Aviso."""
import contextlib
import importlib.util
import io
import shutil
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont
from app import tela  # Importar extensões nativas fora do patch de sys.modules.


class TestEsperaEFD(unittest.TestCase):
    def setUp(self):
        with patch('ctypes.windll',Mock(),create=True), \
                patch.dict('sys.modules',{'app.interacao':types.ModuleType('app.interacao')}):
            spec=importlib.util.spec_from_file_location('app._espera_efd_teste',
                Path(__file__).resolve().parents[1]/'app/dominio.py')
            self.d=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.d)
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.imagem=Image.new('RGB',(100,100),'white')
        self.stack.enter_context(patch.object(self.d.tela,'capturar_tela',return_value=self.imagem))
        self.stack.enter_context(patch.object(self.d.estados.time,'sleep'))
        self.stack.enter_context(patch.object(self.d.estados,'ponto_seguro'))
        self.tess=self.stack.enter_context(patch.object(self.d.tela,'achar_texto_ou_no_centro',return_value=None))
        self.windows=self.stack.enter_context(patch.object(self.d.tela,'achar_texto_windows',return_value=None))
        self.ler_form_real=self.d.tela.ler_dados_ocr_formulario
        self.form_ocr=self.stack.enter_context(patch.object(self.d.tela,'ler_dados_ocr_formulario',return_value={}))

    def leitura(self,corpo='Arquivo gerado com sucesso.',titulo='Aviso'):
        textos=[titulo,*corpo.split(),'OK']
        n=len(textos)
        return {'text':textos,'left':[5]+[20+i*25 for i in range(n-2)]+[110],
                'top':[5]+[30]*(n-2)+[60],'width':[20]*n,'height':[10]*n,
                'block_num':[1]*n,'par_num':[1]+[2]*(n-2)+[3]}

    def test_resultado_local_exige_aviso_e_paragrafo_completo_sem_negacao(self):
        self.assertIsNotNone(self.d._resultado_efd_na_leitura(self.leitura(),2))
        self.assertIsNotNone(self.d._resultado_efd_na_leitura(self.leitura('(1) Arquivo gerado com sucesso.'),2))
        for corpo,titulo in (('sucesso','Aviso'),('Não Arquivo gerado com sucesso.','Aviso'),
                             ('0 Arquivo gerado com sucesso.','Aviso'),
                             ('Arquivo gerado com sucesso. Confira erros.','Aviso'),
                             ('Arquivo gerado com sucesso.','Atenção')):
            with self.subTest(corpo=corpo,titulo=titulo):
                self.assertIsNone(self.d._resultado_efd_na_leitura(self.leitura(corpo,titulo),2))

    def test_recorte_confirmado_vence_aviso_generico_sem_acao_no_desktop(self):
        self.form_ocr.return_value=self.leitura()
        self.tess.side_effect=lambda im,texto,**kw:(10,10) if texto=='Aviso' else None
        imagem,pos,erro=self.executar()
        self.assertIs(imagem,self.imagem)
        self.assertIsNotNone(pos);self.assertFalse(erro)
        self.assertEqual(self.form_ocr.call_args.kwargs,{'escala':4,'preparo':'cinza','psm':6})

    def test_recorte_usa_segmentacao_esparsa_se_bloco_nao_le_corpo(self):
        self.form_ocr.side_effect=lambda im,**kw:self.leitura() if kw['psm']==11 else {}
        self.assertIsNotNone(self.executar()[1])
        self.assertEqual(self.form_ocr.call_count,3)

    def test_paragrafo_positivo_duplicado_nao_autoriza_confirmar(self):
        dados=self.leitura()
        for chave in dados:dados[chave].extend(dados[chave][1:5])
        dados['par_num'][-4:]=[4]*4
        self.assertIsNone(self.d._resultado_efd_na_leitura(dados,2))

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract indisponível.')
    def test_ocr_real_em_aviso_sintetico_pequeno_sem_busca_de_tela_inteira(self):
        imagem=Image.new('RGB',(800,600),'#dcdcdc');d=ImageDraw.Draw(imagem)
        fonte=next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                               Path('C:/Windows/Fonts/arial.ttf')) if p.exists()),None)
        font=ImageFont.truetype(str(fonte),11) if fonte else ImageFont.load_default()
        d.rectangle((260,230,530,385),fill='#eeeeee',outline='#244366')
        d.rectangle((262,232,528,255),fill='#acc5de')
        d.text((267,236),'Aviso',font=font,fill='black')
        d.ellipse((274,280,300,306),fill='#3f60af',outline='white')
        d.text((284,286),'i',font=font,fill='white')
        d.text((310,286),'Arquivo gerado com sucesso.',font=font,fill='black')
        d.rectangle((435,349,515,375),outline='gray')
        d.text((466,355),'OK',font=font,fill='black')
        self.form_ocr.side_effect=self.ler_form_real
        pos=self.d._achar_resultado_efd_recorte(imagem)
        self.assertIsNotNone(pos)
        self.assertTrue(310<pos[0]<525 and 280<pos[1]<310)

    def executar(self):
        return self.d.esperar_e_achar('Arquivo gerado com sucesso',texto_erro=('Aviso','Erro'),
            escalas_adicionais=(4,),ocr_windows=True,comparacao_exata=True,
            espera_minima=0,tentativas=1,intervalo=0)

    def test_4x_confirma_corpo_antes_de_classificar_titulo_aviso(self):
        self.tess.side_effect=lambda imagem,texto,**kw: ((12,34)
            if texto=='Arquivo gerado com sucesso' and kw['escala']==4 else
            (50,60) if texto=='Aviso' else None)
        imagem,pos,erro=self.executar()
        self.assertIs(imagem,self.imagem); self.assertEqual(pos,(12,34)); self.assertFalse(erro)
        self.assertEqual([c.kwargs['escala'] for c in self.tess.call_args_list],[2,4])
        self.assertTrue(all(c.kwargs.get('max_palavras',4)==4 and not c.kwargs['debug']
                            for c in self.tess.call_args_list))
        self.windows.assert_not_called()

    def test_windows_centro_converte_coordenadas_sem_clicar(self):
        centro=Image.new('RGB',(50,50))
        self.stack.enter_context(patch.object(self.d.tela,'recortar_centro',return_value=(centro,25,25)))
        self.windows.side_effect=lambda imagem,texto,**kw: ((10,12) if imagem is centro else None)
        self.assertEqual(self.executar()[1:],((35,37),False))
        self.assertEqual(self.windows.call_count,2)

    def test_palavra_sucesso_em_aviso_desconhecido_nao_confirma(self):
        # "Não foi possível confirmar sucesso" contém a âncora antiga,
        # mas não o corpo completo observado. Somente Aviso é encontrado.
        self.tess.side_effect=lambda imagem,texto,**kw: (20,30) if texto in ('sucesso','Aviso') else None
        self.assertEqual(self.executar()[1:],((20,30),True))
        self.assertNotIn('sucesso',[c.args[1] for c in self.tess.call_args_list])

    def test_todos_motores_sem_confirmacao_retornam_inconclusivo(self):
        self.assertEqual(self.executar(),(None,None,False))
        self.assertEqual(self.tess.call_count,6)
        self.assertEqual(self.windows.call_count,12)

    def test_aviso_pequeno_na_segunda_captura_nao_e_pulado(self):
        depois=self.imagem.copy(); depois.putpixel((50,50),(0,0,0))
        self.stack.enter_context(patch.object(self.d.tela,'capturar_tela',side_effect=[self.imagem,depois]))
        self.tess.side_effect=lambda imagem,texto,**kw: (12,34) if imagem is depois else None
        resultado=self.d.esperar_e_achar('Arquivo gerado com sucesso',texto_erro=None,
            escalas_adicionais=(4,),ocr_windows=True,comparacao_exata=True,
            espera_minima=0,tentativas=2,intervalo=0)
        self.assertIs(resultado[0],depois); self.assertEqual(resultado[1:],((12,34),False))

    def test_cancelamento_entre_opinioes_ocr_interrompe_sem_confirmar(self):
        from app.controle_execucao import ControleExecucao, controlar_execucao, ExecucaoInterrompida
        controle=ControleExecucao()
        def interromper(*args,**kwargs):
            controle.interromper()
            return None
        self.tess.side_effect=interromper
        with controlar_execucao(controle),self.assertRaises(ExecucaoInterrompida):
            self.executar()
        self.tess.assert_called_once()
        self.windows.assert_not_called()

    def test_timeout_tesseract_nao_bloqueia_segunda_opiniao(self):
        self.tess.side_effect=lambda imagem,texto,**kw: ((20,30) if kw['escala']==4 else
            (_ for _ in ()).throw(RuntimeError('Tesseract process timeout')))
        self.assertEqual(self.executar()[1:],((20,30),False))

    def test_fechamento_aviso_usa_4x_ate_retornar_ao_formulario(self):
        depois=self.imagem.copy(); depois.putpixel((50,50),(0,0,0))
        self.stack.enter_context(patch.object(self.d.interacao,'janela_dominio_em_foco',return_value=True,create=True))
        self.stack.enter_context(patch.object(self.d.tela,'capturar_tela',side_effect=[self.imagem,self.imagem,depois]))
        self.tess.side_effect=lambda imagem,texto,**kw: (
            (12,34) if imagem is self.imagem and texto=='Arquivo gerado com sucesso' and kw['escala']==4 else
            (30,40) if imagem is depois and texto=='Contribui' else None)
        self.assertTrue(self.d._confirmar_saida_aviso_efd('Contribui',{'hwnd':1},'Arquivo gerado com sucesso'))
        self.assertTrue(any(c.kwargs['escala']==4 for c in self.tess.call_args_list))

    def test_fechamento_aviso_sem_foco_nao_captura_nem_aciona(self):
        self.stack.enter_context(patch.object(self.d.interacao,'janela_dominio_em_foco',return_value=False,create=True))
        self.assertFalse(self.d._confirmar_saida_aviso_efd('Contribui',{'hwnd':1},'Arquivo gerado com sucesso'))
        self.d.tela.capturar_tela.assert_not_called()
        self.tess.assert_not_called(); self.windows.assert_not_called()


if __name__=='__main__':
    unittest.main()
