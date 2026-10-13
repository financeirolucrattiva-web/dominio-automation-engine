"""PDFs sintéticos reais e fluxo emulado, sem emissão no Domínio."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PIL import Image, ImageDraw, ImageFont

from app import arquivos, livros_conjuntos as livros
from app.estados import AcompanhamentoRotina
from test_arquivos import criar_pdf,CNPJ

INICIO,FIM='01/08/2026','31/08/2026'
CAB=' EMPRESA: EMPRESA FICTICIA CNPJ: 12.345.678/0001-95 '+INICIO+' a '+FIM+' VALORES FISCAIS'
TEXTOS={'registro_entradas':'REGISTRO DE ENTRADAS'+CAB,
        'registro_saidas':'REGISTRO DE SAIDAS'+CAB,
        'registro_icms':'LIVRO REGISTRO DE APURACAO DO ICMS'+CAB}


class TestConjunto(unittest.TestCase):
    def test_opcao_pdf_com_sete_palavras_nao_confunde_opcao_de_arquivo_unico(self):
        import shutil
        if not shutil.which('tesseract'):self.skipTest('Tesseract indisponível.')
        imagem=Image.new('RGB',(650,150),'white');desenho=ImageDraw.Draw(imagem)
        caminho_fonte=next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('C:/Windows/Fonts/arial.ttf')) if p.exists()),None)
        fonte=ImageFont.truetype(str(caminho_fonte),18) if caminho_fonte else ImageFont.load_default(size=18)
        desenho.text((20,30),'Gerar em único arquivo PDF',fill='black',font=fonte)
        desenho.text((20,75),livros.OPCAO_PDF,fill='black',font=fonte)
        with patch.object(livros.tela,'ler_dados_ocr_windows',return_value=None):
            pos=livros._achar_opcao_pdf(imagem)
        self.assertIsNotNone(pos)
        self.assertGreater(pos[1],75);self.assertLess(pos[1],105)

    def test_periodo_parcial_multimes_corrente_nao_envia_acao(self):
        with tempfile.TemporaryDirectory() as pasta:
            for inicial,final in (('02/08/2026',FIM),(INICIO,'30/09/2026'),('01/01/2099','31/01/2099')):
                dominio=Mock();interacao=Mock();rotina=AcompanhamentoRotina('livros_fiscais',Path(pasta)/'logs')
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertFalse(livros._executar(dominio,interacao,rotina,[],pasta,inicial,final,'',None))
                interacao.clicar.assert_not_called();interacao.digitar.assert_not_called()
                dominio._esperar_item_menu.assert_not_called()

    def test_interrupcao_devolve_pdfs_confirmados_sem_teclas_de_limpeza(self):
        from app.controle_execucao import ExecucaoInterrompida
        dominio=Mock();dominio.LoteInterrompido=type('LoteInterrompido',(Exception,),{})
        def executar(dominio,interacao,rotina,artefatos,*args):
            artefatos.append({'tipo':'registro_entradas','caminho':'confirmado.pdf'})
            raise ExecucaoInterrompida('reinicio_solicitado')
        with tempfile.TemporaryDirectory() as pasta,patch.multiple('app',create=True,dominio=dominio,interacao=Mock()),patch.object(livros,'_executar',side_effect=executar),patch.object(livros.estados,'AcompanhamentoRotina',return_value=AcompanhamentoRotina('livros_fiscais',Path(pasta)/'logs')),contextlib.redirect_stdout(io.StringIO()):
            ok,artefatos=livros.gerar_livros_fiscais(pasta,INICIO,FIM)
        self.assertFalse(ok);self.assertEqual(len(artefatos),1)
        dominio._limpar_ao_encerrar.assert_not_called()

    def test_icms_exige_titulo_cabecalho_periodo_cnpj_nao_coluna_ou_nome(self):
        self.assertEqual(arquivos.validar_livro(TEXTOS['registro_icms'],'registro_icms',INICIO,FIM,CNPJ),CNPJ)
        for texto in (TEXTOS['registro_entradas']+' ICMS',TEXTOS['registro_saidas']+' APURACAO ICMS',
                      TEXTOS['registro_icms'].replace('01/08/2026','01/09/2026'),
                      TEXTOS['registro_icms'].replace('12.345.678/0001-95','11.111.111/0001-11'),
                      'RELATORIO ICMS'+CAB,
                      TEXTOS['registro_icms'].replace('ICMS','ISS')):
            with self.subTest(texto=texto),self.assertRaises(ValueError):
                arquivos.validar_livro(texto,'registro_icms',INICIO,FIM,CNPJ)
        self.assertEqual(arquivos.nome_relatorio('registro_icms','Empresa Fictícia','2026-08-01','2026-08-31'),'livro_icms_empresa_ficticia_2026-08.pdf')

    def test_classifica_tres_por_conteudo_e_nao_pela_ordem_ou_nome_exportado(self):
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta)
            for numero,(tipo,texto) in enumerate(TEXTOS.items()):criar_pdf(root/f'invertido_{3-numero}.pdf',texto)
            saida=livros._conferir_conjunto(root,INICIO,FIM,CNPJ,'Empresa Fictícia')
            self.assertEqual({i['tipo'] for i in saida},set(TEXTOS))
            self.assertEqual(len(list(root.glob('*.pdf'))),3)
            self.assertTrue(all(Path(i['caminho']).exists() for i in saida))

    def test_pdf_divergente_e_tipo_duplicado_nao_compensam_terceiro_ausente(self):
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta)
            criar_pdf(root/'a.pdf',TEXTOS['registro_entradas'])
            criar_pdf(root/'b.pdf',TEXTOS['registro_entradas'])
            criar_pdf(root/'c.pdf',TEXTOS['registro_icms'].replace('01/08/2026','01/09/2026'))
            self.assertEqual(livros._conferir_conjunto(root,INICIO,FIM,CNPJ,'Empresa Fictícia'),[])
            self.assertEqual(len(list(root.glob('*.pdf'))),3)

    def test_parcial_preserva_so_pdf_confirmado_da_mesma_empresa(self):
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);criar_pdf(root/'a.pdf',TEXTOS['registro_entradas'])
            criar_pdf(root/'b.pdf',TEXTOS['registro_saidas'].replace('12.345.678/0001-95','11.111.111/0001-11'))
            (root/'c.pdf').write_bytes(b'%PDF-incompleto')
            saida=livros._conferir_conjunto(root,INICIO,FIM,CNPJ,'Empresa Fictícia')
            self.assertEqual([i['tipo'] for i in saida],['registro_entradas'])
            self.assertTrue((root/'b.pdf').exists());self.assertTrue((root/'c.pdf').exists())

    def test_campos_setembro_precisam_mudar_para_agosto_antes_da_emissao(self):
        atual={'periodo':{'inicial':{'valor':'01/09/2026','posicao':(30,40)},'final':{'valor':'30/09/2026','posicao':(30,70)}},
               'livros':{tipo:{'marcada':True} for tipo in TEXTOS},'outros':[]}
        interacao=Mock()
        def digitar(v):
            if v=='01082026':atual['periodo']['inicial']['valor']=INICIO
            elif v=='31082026':atual['periodo']['final']['valor']=FIM
        interacao.digitar.side_effect=digitar
        with patch.object(livros,'_ler_formulario',side_effect=lambda:atual),patch.object(livros.time,'sleep'):
            livros._preencher(INICIO,FIM,interacao)
        self.assertEqual([c.args[0] for c in interacao.digitar.call_args_list],['01082026','31082026'])
        interacao.digitar.side_effect=None; atual['periodo']['inicial']['valor']='01/09/2026'
        with patch.object(livros,'_ler_formulario',return_value=atual),patch.object(livros.time,'sleep'),self.assertRaises(ValueError):
            livros._preencher(INICIO,FIM,interacao)

    def test_fluxo_completo_tres_artefatos_e_retorno_azul(self):
        # O fiscal é simulado; publicação/PDF/conteúdo e eventos são reais.
        with tempfile.TemporaryDirectory() as pasta,contextlib.ExitStack() as stack:
            root=Path(pasta);dominio=Mock();interacao=Mock()
            dominio.competencia_anterior.return_value=(INICIO,FIM)
            dominio._esperar_item_menu.return_value=(12,30)
            dominio.TITULOS_ERRO=()
            dominio.caminho_visto_pela_sessao_remota.side_effect=str
            dominio.voltar_ao_inicio.return_value=True
            rotina=AcompanhamentoRotina('livros_fiscais',root/'logs');artefatos=[]
            formulario={'periodo':{'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}},
                        'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[]}
            stack.enter_context(patch.object(livros,'_ler_formulario',return_value=formulario))
            stack.enter_context(patch.object(livros,'_aguardar_formulario',return_value='frame'))
            stack.enter_context(patch.object(livros,'_aguardar',return_value='frame'))
            stack.enter_context(patch.object(livros.formulario_livros,'marcar_tres_livros'))
            for nome,valor in [('capturar_tela','frame'),('recortar_topo','frame'),('ler_empresa_selecionada',('Empresa Fictícia','52')),
                               ('achar_texto',(12,30)),('achar_texto_ou_no_centro',(12,30)),('achar_icone_robusto',(15,340)),('ler_texto',TEXTOS['registro_entradas'])]:
                stack.enter_context(patch.object(livros.tela,nome,return_value=valor))
            interacao.identificar_janela_dominio_atual.return_value={'hwnd':12}
            stack.enter_context(patch('app.seletor_pasta.selecionar_pasta',return_value=True))
            def exportar(staging,*args):
                for i,texto in enumerate(TEXTOS.values()):criar_pdf(staging/f'{i}.pdf',texto)
                return True
            stack.enter_context(patch.object(livros,'_aguardar_arquivos',side_effect=exportar))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertTrue(livros._executar(dominio,interacao,rotina,artefatos,root,INICIO,FIM,'',CNPJ))
            self.assertEqual({a['tipo'] for a in artefatos},set(TEXTOS))
            self.assertEqual(tuple(rotina.confirmadas),rotina.ETAPAS)
            dominio.voltar_ao_inicio.assert_called_once_with({'hwnd':12})


if __name__=='__main__':unittest.main()
