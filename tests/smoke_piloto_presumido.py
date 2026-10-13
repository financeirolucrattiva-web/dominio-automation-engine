"""Chromium/HTTP/worker reais; Livros e emissão fiscal são sintéticos."""
from pathlib import Path
import json
import shutil
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import httpx
import uvicorn
from playwright.sync_api import sync_playwright, expect
from app.api_servidor import criar_app
from app.autenticacao import LoginRecusado
from app.servidor import RepositorioTarefas, ServicoExecucao
from app.formulario_livros import ler_formulario
from test_formulario_livros import formulario
from test_servidor import eventos_confirmados
from test_arquivos import criar_pdf


class LoginSintetico:
    falhar=False
    def revisar_livros(self,sessao):
        sessao.fase('lendo_formulario_livros')
        if self.falhar:raise LoginRecusado('formulario_livros_nao_reconhecido')
        imagem,dados,_=formulario(('registro_icms',))
        return ler_formulario(imagem,dados)
    def encerrar(self):pass


chamadas=[]
def fiscal(dados,receber):
    chamadas.append((dados['empresa_codigo'],dados['capacidade']))
    if getattr(fiscal,'falhar_periodo',False) and dados['capacidade']=='resumo_acumulador':
        base={'execution_id':dados['request_id'].replace('-',''),'routine_id':'resumo_acumulador','attempt':1,'elapsed_seconds':0}
        for passo in ('preencher_periodo','fim'):
            receber(base | {'step':passo,'status':'falha','evidence':'data_inicial_resumo_nao_confirmada'})
        return False
    eventos_confirmados(dados,receber)
    if dados['capacidade']=='livros_fiscais':
        saida=root/'saida';saida.mkdir(exist_ok=True)
        artefatos=[]
        for tipo,titulo in (('registro_entradas','REGISTRO DE ENTRADAS'),('registro_saidas','REGISTRO DE SAIDAS'),('registro_icms','REGISTRO DE APURACAO DO ICMS')):
            caminho=saida/(tipo+'_'+dados['request_id']+'.pdf')
            criar_pdf(caminho,titulo+' EMPRESA FICTICIA CNPJ: 12.345.678/0001-95 '+dados['inicio'].split('-')[2]+'/'+dados['inicio'].split('-')[1]+'/'+dados['inicio'].split('-')[0]+' a '+dados['fim'].split('-')[2]+'/'+dados['fim'].split('-')[1]+'/'+dados['fim'].split('-')[0])
            artefatos.append({'tipo':tipo,'caminho':str(caminho)})
        return True,artefatos
    return True


fiscal.executar_em_lote=fiscal
fiscal.recuperar_em_lote=lambda dados:True
with tempfile.TemporaryDirectory() as pasta:
    root=Path(pasta); repo=RepositorioTarefas(root/'data/banco.sqlite3')
    repo.configuracao.preparar_piloto(); cadastro=repo.configuracao.listar()
    presumido=next(r for r in cadastro['regimes'] if r['nome']=='Lucro Presumido')
    real=next(r for r in cadastro['regimes'] if r['nome']=='Lucro Real')
    # Mantém a cobertura de teste parcial com uma rotina custom realmente pendente.
    pendente=repo.configuracao.cadastrar_rotina('ICMS extra em configuração')
    repo.configuracao.salvar_regime(presumido['id'],presumido['nome'],['resumo_acumulador','efd_contribuicoes',pendente['id']])
    for codigo in ('52','53'):repo.configuracao.salvar_empresa(codigo,'Empresa Fictícia '+codigo,presumido['id'])
    repo.configuracao.salvar_empresa('54','Empresa Fictícia Real',real['id'])
    login=LoginSintetico(); servico=ServicoExecucao(repo,fiscal,'windows',login=login)
    chave='d'*48
    with socket.socket() as sock:sock.bind(('127.0.0.1',0)); porta=sock.getsockname()[1]
    url=f'http://127.0.0.1:{porta}'
    server=uvicorn.Server(uvicorn.Config(criar_app(servico,chave,root/'saida'),host='127.0.0.1',port=porta,log_level='error',access_log=False))
    thread=threading.Thread(target=server.run); thread.start()
    try:
        for _ in range(100):
            try:
                if httpx.get(url).status_code==200:break
            except httpx.ConnectError:pass
            time.sleep(.05)
        else:raise AssertionError('API não iniciou.')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True)
            contexto=browser.new_context(viewport={'width':1440,'height':1000},locale='pt-BR')
            pagina=contexto.new_page(); erros=[]; pagina.on('pageerror',lambda erro:erros.append(str(erro)))
            pagina.goto(url); pagina.locator('#chave').fill(chave); pagina.locator('#form-login button').click()
            expect(pagina.locator('#conteudo')).to_be_visible()
            expect(pagina.locator('#piloto-empresa option')).to_have_count(3)
            assert 'Real' not in pagina.locator('#piloto-empresa').inner_text()
            pagina.locator('#conferir-livros').click()
            expect(pagina.locator('#livros-diagnostico')).to_contain_text('Leitura confirmada',timeout=8000)
            expect(pagina.locator('#livros-diagnostico')).to_contain_text('ICMS: marcado')
            expect(pagina.locator('#livros-diagnostico')).to_contain_text('Nenhum PDF foi emitido')
            expect(pagina.locator('#livros-medidas')).to_contain_text('Caixas medidas')
            assert chamadas==[] and repo.listar()==[]
            login.falhar=True; pagina.locator('#conferir-livros').click()
            expect(pagina.locator('#livros-diagnostico')).to_contain_text('Não reconheci',timeout=8000)
            expect(pagina.locator('#livros-medidas')).to_have_text('')
            login.falhar=False; pagina.locator('#conferir-livros').click()
            expect(pagina.locator('#livros-diagnostico')).to_contain_text('Leitura confirmada',timeout=8000)
            pagina.locator('#piloto-empresa').select_option('52')
            pagina.locator('#piloto-competencia').fill('2024-02')
            expect(pagina.locator('#piloto-resumo')).to_contain_text('2 rotinas disponíveis; 1 pendentes')
            expect(pagina.locator('#piloto-executar')).to_be_disabled()
            expect(pagina.locator('#piloto-rotinas')).to_contain_text('ICMS extra em configuração · Pendente')
            pagina.locator('#piloto-parcial').check(); pagina.locator('#piloto-apuracao').check()
            with pagina.expect_response(lambda r:r.url.endswith('/api/piloto-presumido') and r.request.method=='POST') as resposta:
                pagina.locator('#piloto-executar').click()
            lote=resposta.value.json(); assert lote['plano']['empresas'][0]['codigo']=='52'
            assert lote['plano']['inicio']=='2024-02-01' and lote['plano']['fim']=='2024-02-29'
            expect(pagina.locator('#lote-resultado')).to_contain_text('Teste parcial finalizado',timeout=8000)
            expect(pagina.locator('#lote-tarefas tr')).to_have_count(3)
            expect(pagina.locator('#lote-tarefas')).to_contain_text('Não executada · integração pendente')
            assert chamadas==[('52','resumo_acumulador'),('52','efd_contribuicoes')]
            with pagina.expect_download() as transferencia:
                pagina.locator('#lote-diagnostico').click()
            arquivo=transferencia.value.path(); relatorio=json.loads(Path(arquivo).read_text())
            assert len(relatorio['rotinas'])==2 and len(relatorio['pendencias_nao_executadas'])==1
            assert relatorio['homologacao_fiscal'] is False and 'pasta_relativa' not in json.dumps(relatorio)
            # Mesmo pedido após resposta perdida/duplo envio não repete o fiscal.
            pagina.locator('#piloto-apuracao').check(); pagina.locator('#piloto-executar').click()
            expect(pagina.locator('#piloto-apuracao')).not_to_be_checked()
            assert len(chamadas)==2 and len(repo.listar_lotes())==1
            # Atualização durante digitação parcial preserva ano e calendário.
            campo=pagina.locator('#piloto-competencia'); campo.fill('2001-02'); campo.click(position={'x':18,'y':18})
            pagina.keyboard.press('ArrowRight'); pagina.keyboard.press('Backspace')
            assert campo.input_value()=='' and campo.evaluate('c=>c.validity.badInput')
            pagina.evaluate('atualizar()'); pagina.keyboard.type('20'); pagina.evaluate('atualizar()'); pagina.keyboard.type('24')
            expect(campo).to_have_value('2024-02'); expect(pagina.locator('#piloto-apuracao')).not_to_be_checked()
            pagina.locator('#lote-filtro').select_option(presumido['id']); pagina.locator('#lote-selecionar').click()
            pagina.locator('#lote-competencia').fill('2024-03'); pagina.locator('#lote-piloto').check()
            pagina.locator('#lote-planejar').click()
            expect(pagina.locator('#lote-plano-resumo')).to_contain_text('Teste parcial: 2 pendências')
            pagina.locator('#lote-apuracao').check(); pagina.locator('#lote-executar').click()
            expect(pagina.locator('#lote-resultado')).to_contain_text('2 pendências não executadas',timeout=8000)
            assert chamadas[2:]==[('52','resumo_acumulador'),('52','efd_contribuicoes'),('53','resumo_acumulador'),('53','efd_contribuicoes')]
            assert len(repo.listar_lotes())==2
            fiscal.falhar_periodo=True
            pagina.locator('#piloto-empresa').select_option('53'); pagina.locator('#piloto-competencia').fill('2024-04')
            expect(pagina.locator('#piloto-resumo')).to_contain_text('2 rotinas disponíveis')
            pagina.locator('#piloto-parcial').check(); pagina.locator('#piloto-apuracao').check(); pagina.locator('#piloto-executar').click()
            expect(pagina.locator('#lote-resultado')).to_contain_text('Finalizada com falhas',timeout=8000)
            expect(pagina.locator('#lote-tarefas')).to_contain_text('data inicial não confirmou o valor solicitado')
            linha=pagina.locator('#lote-tarefas tr').filter(has_text='Resumo por Acumulador')
            linha.get_by_role('button',name='Ver etapas').click()
            expect(pagina.locator('#motivo-tarefa')).to_contain_text('Não enviei OK')
            # Sequência nativa completa: um envio por empresa, 3 tarefas e 3 PDFs.
            fiscal.falhar_periodo=False
            repo.configuracao.salvar_regime(presumido['id'],presumido['nome'],['resumo_acumulador','efd_contribuicoes','livros_fiscais'])
            pagina.evaluate('atualizar()')
            pagina.locator('#piloto-empresa').select_option('52');pagina.locator('#piloto-competencia').fill('2024-05')
            expect(pagina.locator('#piloto-resumo')).to_contain_text('3 rotinas disponíveis; 0 pendentes')
            pagina.locator('#preparar-livros').click()
            expect(pagina.locator('#capacidade')).to_have_value('livros_fiscais')
            expect(pagina.locator('#empresa')).to_have_value('52')
            expect(pagina.locator('#competencia')).to_have_value('2024-05')
            expect(pagina.locator('#apuracao')).not_to_be_checked()
            pagina.locator('#piloto-parcial').uncheck();pagina.locator('#piloto-apuracao').check()
            pagina.locator('#piloto-executar').click()
            expect(pagina.locator('#lote-resultado')).to_contain_text('3/3 rotinas concluídas',timeout=10000)
            expect(pagina.locator('#lote-tarefas tr')).to_have_count(3)
            livros=pagina.locator('#lote-tarefas tr').filter(has_text='Livros Fiscais')
            livros.get_by_role('button',name='Ver etapas').click()
            expect(pagina.locator('#arquivos-tarefa button')).to_have_count(3)
            for tipo in ('registro_entradas','registro_saidas','livro_icms'):
                with pagina.expect_download() as download:
                    pagina.locator('#arquivos-tarefa button').filter(has_text=tipo).click()
                assert download.value.suggested_filename.startswith(tipo+'_empresa_ficticia_52_2024-05')
                assert Path(download.value.path()).read_bytes().startswith(b'%PDF-')
            assert chamadas[-3:]==[('52','resumo_acumulador'),('52','efd_contribuicoes'),('52','livros_fiscais')]
            for largura in (1440,768,390):
                pagina.set_viewport_size({'width':largura,'height':900})
                assert pagina.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            contexto.set_offline(True)
            expect(pagina.locator('#piloto-executar')).to_be_disabled(); expect(pagina.locator('#conferir-livros')).to_be_disabled()
            contexto.set_offline(False); pagina.locator('#sair').click()
            expect(pagina.locator('#livros-medidas')).to_have_text(''); expect(pagina.locator('#piloto-rotinas')).to_have_count(1)
            assert pagina.locator('#piloto-rotinas').inner_text()=='' and not erros,erros
            browser.close()
        print('OK: diagnóstico sem emissão, falha sem resultado antigo, Presumido individual em um envio, idempotência, pendências explícitas, lote por empresa, digitação, três larguras e logout; fiscal simulado.')
    finally:
        server.should_exit=True; thread.join(10)
