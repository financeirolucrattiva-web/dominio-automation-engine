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
    def test_periodo_ja_correto_nao_redigita_e_validacao_final_usa_mesma_captura(self):
        imagem=Image.new('RGB',(600,400),'white');interacao=Mock()
        periodo={'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}}
        selecao={'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}
        with patch.object(livros,'_ler_periodo',return_value=periodo) as campos, \
                patch.object(livros,'_ler_selecao',return_value=selecao) as selecoes, \
                patch.object(livros.tela,'capturar_tela',return_value=imagem) as captura:
            self.assertIs(livros._preencher(INICIO,FIM,interacao),imagem)
        interacao.clicar.assert_not_called();interacao.digitar.assert_not_called()
        interacao.selecionar_tudo_alternativo.assert_not_called()
        # Datas lidas UMA vez (tela igual na conferência final = sem repetir o OCR de ~20 s);
        # a seleção final é lida na captura usada para a conferência.
        self.assertEqual(campos.call_count,1);selecoes.assert_called_once_with(imagem)

    def test_datas_com_tela_diferente_na_conferencia_final_sao_relidas_na_mesma_captura(self):
        imagem=Image.new('RGB',(600,400),'white');interacao=Mock()
        periodo={'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}}
        selecao={'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}
        with patch.object(livros,'_ler_periodo',return_value=periodo) as campos,                 patch.object(livros,'_ler_selecao',return_value=selecao),                 patch.object(livros.tela,'assinatura_tela',side_effect=['0000','1111','1111','1111']),                 patch.object(livros.tela,'tela_mudou',return_value=True),                 patch.object(livros.tela,'capturar_tela',return_value=imagem):
            self.assertIs(livros._preencher(INICIO,FIM,interacao),imagem)
        campos.assert_any_call(imagem)  # a tela mudou: relê as datas na captura final

    def test_selecao_final_usa_pixels_das_caixas_conhecidas_e_cai_para_ocr_se_nao_achar(self):
        imagem=Image.new('RGB',(600,400),'white')
        periodo={'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}}
        pixels={'livros':{t:{'marcada':True,'retangulo':(1,1,12,12),'posicao':(7,7)} for t in TEXTOS},
                'outros':[{'marcada':False,'retangulo':(1,1,12,12)} for _ in range(13)],'altura':11.0}
        ref={'altura':11.0}
        with patch.object(livros,'_ler_periodo',return_value=periodo),                 patch.object(livros,'_ler_selecao') as ocr,                 patch.object(livros.formulario_livros,'reler_por_pixels',return_value=pixels) as rapido,                 patch.object(livros.tela,'capturar_tela',return_value=imagem):
            self.assertIs(livros._conferir_antes_ok(INICIO,FIM,referencia=ref),imagem)
        rapido.assert_called_once_with(imagem,ref);ocr.assert_not_called()
        with patch.object(livros,'_ler_periodo',return_value=periodo),                 patch.object(livros,'_ler_selecao',return_value={'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}) as ocr,                 patch.object(livros.formulario_livros,'reler_por_pixels',side_effect=ValueError('caixa ausente')),                 patch.object(livros.tela,'capturar_tela',return_value=imagem):
            self.assertIs(livros._conferir_antes_ok(INICIO,FIM,referencia=ref),imagem)
        ocr.assert_called_once()

    def test_periodo_aguarda_ocr_transitorio_sem_redigitar(self):
        periodo={'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}}
        campos=Mock(side_effect=[ValueError('transitório'),periodo])
        with patch.object(livros,'_ler_periodo',campos),patch.object(livros.time,'sleep'):
            self.assertEqual(livros._esperar_periodo('final',FIM),periodo)
        self.assertEqual(campos.call_count,2)

    def test_opcao_adicional_ou_indeterminada_nao_confirma_formulario_final(self):
        periodo={'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}}
        for estado in (True,None):
            selecao={'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}
            selecao['outros'][0]['marcada']=estado
            with self.subTest(estado=estado),patch.object(livros,'_ler_periodo',return_value=periodo), \
                    patch.object(livros,'_ler_selecao',return_value=selecao), \
                    patch.object(livros.tela,'capturar_tela',return_value='frame'),patch.object(livros.time,'sleep'), \
                    self.assertRaises(ValueError):
                livros._conferir_antes_ok(INICIO,FIM)

    def test_interrupcao_durante_finalizacao_preserva_lista_e_primeiro_pdf_confirmado(self):
        from app.controle_execucao import ExecucaoInterrompida
        with tempfile.TemporaryDirectory() as pasta:
            root=Path(pasta);artefatos=[]
            for i,texto in enumerate(TEXTOS.values()):criar_pdf(root/f'{i}.pdf',texto)
            original=arquivos.finalizar_pdf
            numero=[0]
            def finalizar(*args,**kwargs):
                numero[0]+=1
                if numero[0]==2:raise ExecucaoInterrompida('reinicio_solicitado')
                return original(*args,**kwargs)
            with patch.object(arquivos,'finalizar_pdf',side_effect=finalizar),self.assertRaises(ExecucaoInterrompida):
                livros._conferir_conjunto(root,INICIO,FIM,CNPJ,'Empresa Fictícia',artefatos=artefatos)
            self.assertEqual(len(artefatos),1)
            self.assertTrue(Path(artefatos[0]['caminho']).exists())
            self.assertEqual(len(list(root.glob('*.pdf'))),3)

    def test_marca_tres_livros_antes_de_tentar_datas_e_bloqueia_emissao_se_periodo_falha(self):
        with tempfile.TemporaryDirectory() as pasta,contextlib.ExitStack() as stack:
            dominio=Mock();interacao=Mock();dominio.TITULOS_ERRO=()
            dominio._esperar_item_menu.return_value=(10,20)
            rotina=AcompanhamentoRotina('livros_fiscais',Path(pasta)/'logs')
            selecao={'livros':{tipo:{'marcada':False,'posicao':(30,40+i*30)} for i,tipo in enumerate(TEXTOS)},
                     'outros':[{'marcada':False} for _ in range(13)]}
            stack.enter_context(patch.object(livros,'_ler_selecao',return_value=selecao))
            periodo=stack.enter_context(patch.object(livros,'_ler_periodo',side_effect=ValueError('Leitura sintética incompleta')))
            stack.enter_context(patch.object(livros,'_aguardar_formulario',return_value='frame'))
            for nome,valor in [('capturar_tela','frame'),('recortar_topo','frame'),('ler_empresa_selecionada',('Empresa Fictícia','52')),('achar_texto',(10,20))]:
                stack.enter_context(patch.object(livros.tela,nome,return_value=valor))
            interacao.identificar_janela_dominio_atual.return_value={'hwnd':12}
            def clicar(x,y):
                for livro in selecao['livros'].values():
                    if livro['posicao']==(x,y):livro['marcada']=True
            interacao.clicar.side_effect=clicar
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            with self.assertRaises(ValueError):livros._executar(dominio,interacao,rotina,[],pasta,INICIO,FIM,'',CNPJ)
            self.assertTrue(all(l['marcada'] for l in selecao['livros'].values()))
            self.assertEqual(rotina.etapa,'preencher_periodo')
            self.assertEqual(periodo.call_count,5);interacao.digitar.assert_not_called()
            self.assertEqual(interacao.clicar.call_count,4)  # Menu e exatamente as três caixas; nenhum OK.

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
               'livros':{tipo:{'marcada':True} for tipo in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}
        interacao=Mock()
        def digitar(v):
            if v=='01082026':atual['periodo']['inicial']['valor']=INICIO
            elif v=='31082026':atual['periodo']['final']['valor']=FIM
        interacao.digitar.side_effect=digitar
        with patch.object(livros,'_ler_periodo',side_effect=lambda imagem=None:atual['periodo']),patch.object(livros,'_ler_selecao',return_value=atual),patch.object(livros.tela,'capturar_tela',return_value='frame'),patch.object(livros.time,'sleep'):
            livros._preencher(INICIO,FIM,interacao)
        self.assertEqual([c.args[0] for c in interacao.digitar.call_args_list],['01082026','31082026'])
        interacao.digitar.side_effect=None; atual['periodo']['inicial']['valor']='01/09/2026'
        with patch.object(livros,'_ler_periodo',return_value=atual['periodo']),patch.object(livros.time,'sleep'),self.assertRaises(ValueError):
            livros._preencher(INICIO,FIM,interacao)

    def test_espera_reavalia_tela_estatica_com_pixels_exatos_e_prazo_proprio(self):
        dominio=Mock();dominio.TITULOS_ERRO=()
        with patch.object(livros.estados,'esperar_por_estado',return_value=('frame','previa',(1,2))) as espera:
            self.assertEqual(livros._aguardar(dominio,'previa',lambda img:None,'',tentativas=90),'frame')
        opcoes=espera.call_args.kwargs
        self.assertTrue(opcoes['comparacao_exata']);self.assertEqual(opcoes['rever_a_cada'],3)
        self.assertGreaterEqual(opcoes['limite_segundos'],90)

    def test_espera_dos_pdfs_fecha_o_leitor_antes_de_checar_o_foco(self):
        # O Acrobat abre na frente e a trava de foco encerraria a rodada: fecha ANTES de ponto_seguro().
        ordem=[]
        dominio=Mock();dominio.TITULOS_ERRO=()
        dominio._fechar_leitores_pdf_uma_vez.side_effect=lambda base,fechados:ordem.append('fechar')
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(livros,'ponto_seguro',side_effect=lambda:ordem.append('foco')), \
                patch.object(livros.tela,'achar_texto_ou_no_centro',return_value=None), \
                patch.object(livros.time,'sleep'):
            root=Path(pasta)
            for i in range(3):criar_pdf(root/f'{i}.pdf',TEXTOS['registro_entradas'])
            self.assertTrue(livros._aguardar_arquivos(root,lambda:'frame',dominio,'',{}))
        self.assertEqual(ordem[:2],['fechar','foco'])

    def test_parar_no_fechamento_do_pdf_sai_da_espera_sem_capturar_ou_repetir(self):
        from app.controle_execucao import ExecucaoInterrompida
        dominio=Mock(); dominio.TITULOS_ERRO=()
        dominio._fechar_leitores_pdf_uma_vez.side_effect=ExecucaoInterrompida('parar')
        capturar=Mock()
        with tempfile.TemporaryDirectory() as pasta, self.assertRaises(ExecucaoInterrompida):
            livros._aguardar_arquivos(Path(pasta),capturar,dominio,'',{})
        capturar.assert_not_called()
        dominio._fechar_leitores_pdf_uma_vez.assert_called_once()

    def test_ok_nao_lido_por_ocr_e_calculado_a_partir_de_fechar(self):
        def achar(imagem, alvo, escala=2):
            return {'Fechar': (1158, 264)}.get(alvo)
        with patch.object(livros.tela, 'achar_texto_ou_no_centro', side_effect=achar), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(livros._achar_ok('frame'), (1158, 233))  # captura real: OK em ~(1158, 233)
        with patch.object(livros.tela, 'achar_texto_ou_no_centro', return_value=None):
            self.assertIsNone(livros._achar_ok('frame'))  # sem OK nem Fechar: não clica
        with patch.object(livros.tela, 'achar_texto_ou_no_centro', return_value=(500, 400)):
            self.assertEqual(livros._achar_ok('frame'), (500, 400))  # OK lido tem prioridade

    def test_previa_dos_livros_tolera_ordem_e_pontuacao_do_ocr_mas_exige_identidade(self):
        # CNPJ lido ANTES do título, com vírgula: a conferência rígida recusa, a alternativa aceita.
        previa='EMPRESA FICTICIA Página 1/1 12.345,678/0001-95 '+INICIO+' a '+FIM+' REGISTRO DE ENTRADAS Código CFOP'
        with self.assertRaises(ValueError):
            arquivos.validar_livro(previa,'registro_entradas',INICIO,FIM,CNPJ)
        self.assertEqual(arquivos.validar_previa_livro(previa,INICIO,FIM,CNPJ,nome_empresa='Empresa Fictícia'),CNPJ)
        casos={'periodo':previa.replace(FIM,'30/09/2026'),
               'dois_cnpjs':previa.replace('12.345,678/0001-95','12.345,678/0001-95 98.765.432/0001-10'),
               'sem_titulo':previa.replace('REGISTRO DE ENTRADAS','RELATORIO'),
               'sem_cnpj':previa.replace('12.345,678/0001-95','')}
        for nome,texto in casos.items():
            with self.subTest(nome),self.assertRaises(ValueError):
                arquivos.validar_previa_livro(texto,INICIO,FIM)
        with self.assertRaises(ValueError):
            arquivos.validar_previa_livro(previa,INICIO,FIM,nome_empresa='Outra Empresa')
        with self.assertRaises(ValueError):
            arquivos.validar_previa_livro(previa,INICIO,FIM,'00000000000000')

    def test_previa_sem_cabecalho_do_dominio_e_ocr_fora_de_ordem_segue_para_exportar(self):
        with tempfile.TemporaryDirectory() as pasta,contextlib.ExitStack() as stack:
            root=Path(pasta);dominio=Mock();interacao=Mock()
            dominio.competencia_anterior.return_value=(INICIO,FIM)
            dominio._esperar_item_menu.return_value=(12,30)
            dominio.TITULOS_ERRO=()
            dominio.caminho_visto_pela_sessao_remota.side_effect=str
            dominio.voltar_ao_inicio.return_value=True
            rotina=AcompanhamentoRotina('livros_fiscais',root/'logs');artefatos=[]
            formulario={'periodo':{'inicial':{'valor':INICIO,'posicao':(30,40)},'final':{'valor':FIM,'posicao':(30,70)}},
                        'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}
            stack.enter_context(patch.object(livros,'_ler_periodo',return_value=formulario['periodo']))
            stack.enter_context(patch.object(livros,'_ler_selecao',return_value=formulario))
            stack.enter_context(patch.object(livros,'_aguardar_formulario',return_value='frame'))
            stack.enter_context(patch.object(livros,'_aguardar',return_value='frame'))
            stack.enter_context(patch.object(livros.formulario_livros,'marcar_tres_livros'))
            previa='EMPRESA FICTICIA 12.345,678/0001-95 '+INICIO+' a '+FIM+' REGISTRO DE ENTRADAS'
            for nome,valor in [('capturar_tela','frame'),('recortar_topo','frame'),
                               ('achar_texto',(12,30)),('achar_texto_ou_no_centro',(12,30)),('achar_icone_robusto',(15,340)),('ler_texto',previa)]:
                stack.enter_context(patch.object(livros.tela,nome,return_value=valor))
            # Antes de abrir o menu o cabeçalho é legível; na prévia ele está coberto pelo relatório.
            stack.enter_context(patch.object(livros.tela,'ler_empresa_selecionada',side_effect=[('Empresa Fictícia','52'),None]))
            interacao.identificar_janela_dominio_atual.return_value={'hwnd':12}
            stack.enter_context(patch('app.seletor_pasta.selecionar_pasta',return_value=True))
            def exportar(staging,*args):
                for i,texto in enumerate(TEXTOS.values()):criar_pdf(staging/f'{i}.pdf',texto)
                return True
            stack.enter_context(patch.object(livros,'_aguardar_arquivos',side_effect=exportar))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertTrue(livros._executar(dominio,interacao,rotina,artefatos,root,INICIO,FIM,'',CNPJ))
            self.assertEqual({a['tipo'] for a in artefatos},set(TEXTOS))

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
                        'livros':{t:{'marcada':True} for t in TEXTOS},'outros':[{'marcada':False} for _ in range(13)]}
            stack.enter_context(patch.object(livros,'_ler_periodo',return_value=formulario['periodo']))
            stack.enter_context(patch.object(livros,'_ler_selecao',return_value=formulario))
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
