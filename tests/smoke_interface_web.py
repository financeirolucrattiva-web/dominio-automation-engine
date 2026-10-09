"""Navegador/API/worker reais, fiscal e autenticação externos simulados."""
import io
import os
import shutil
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
import httpx
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from app.api_servidor import criar_app
from app.servidor import RepositorioTarefas, ServicoExecucao
from app.controle_execucao import ponto_seguro


class LoginSimulado:
    imagem = None
    def executar(self, dados, sessao):
        sessao.fase('abrir_onvio')
        codigo = sessao.aguardar_codigo(30)
        assert codigo == '654321'
        sessao.fase('tela_principal_confirmada')
    def reiniciar(self, sessao):
        sessao.fase('fechando_ciclo')
    def calibrar(self, sessao):
        sessao.fase('calibracao_confirmada')
    def capturar(self, sessao):
        buffer=io.BytesIO(); Image.new('RGB',(400,250),'#295cb3').save(buffer,format='PNG')
        self.imagem=buffer.getvalue(); sessao.fase('captura_pronta')
    def obter_captura(self):
        return self.imagem
    def encerrar(self):
        pass


def fiscal(dados, receber):
    if getattr(fiscal,'falhar_proxima',False):
        fiscal.falhar_proxima=False
        receber({'execution_id':dados['request_id'].replace('-',''),'routine_id':dados['capacidade'],
                 'attempt':1,'step':'fim','status':'falha','elapsed_seconds':0,'evidence':None})
        return False
    for etapa in ('navegar_menu','preencher_periodo','identificar_formulario','gerar_documento','encerrar','fim'):
        ponto_seguro()
        time.sleep(.7)
        receber({'execution_id':dados['request_id'].replace('-',''),'routine_id':dados['capacidade'],
                 'attempt':1,'step':etapa,'status':'concluido' if etapa=='fim' else 'confirmado',
                 'elapsed_seconds':.7,'evidence':'tela_principal_reconhecida' if etapa=='encerrar' else None})
    return True


# O navegador exercita o mesmo contrato do adapter de lote, sem desktop.
fiscal.executar_em_lote = fiscal
fiscal.recuperar_em_lote = lambda dados: True  # confirmação sintética, sem desktop


executavel = os.environ.get('DOMINIO_BROWSER_BIN') or shutil.which('chromium') or shutil.which('chromium-browser')
if not executavel:
    raise SystemExit('Chromium não encontrado. Configure DOMINIO_BROWSER_BIN com o executável instalado; teste não executado.')

with tempfile.TemporaryDirectory() as pasta:
    root=Path(pasta); repo=RepositorioTarefas(root/'tarefas.sqlite3')
    servico=ServicoExecucao(repo,fiscal,'windows',login=LoginSimulado())
    key='d'*48
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); porta=sock.getsockname()[1]
    url=f'http://127.0.0.1:{porta}'
    server=uvicorn.Server(uvicorn.Config(criar_app(servico,key,root/'saida',root/'rotinas'),host='127.0.0.1',port=porta,log_level='error',access_log=False))
    thread=threading.Thread(target=server.run); thread.start()
    try:
        for _ in range(100):
            try:
                if httpx.get(url).status_code==200: break
            except httpx.ConnectError:
                pass
            time.sleep(.05)
        else: raise AssertionError('API não iniciou')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=executavel,headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000},locale='pt-BR')
            page=context.new_page(); erros=[]
            page.on('pageerror',lambda erro:erros.append(str(erro)))
            page.goto(url)
            page.locator('#chave').fill('invalida-0000000000000000000000000')
            page.locator('#form-login button').click()
            expect(page.locator('#aviso')).to_contain_text('Acesso não autorizado')
            page.locator('#chave').fill(key); page.locator('#form-login button').click()
            expect(page.locator('#conteudo')).to_be_visible()
            page.locator('#empresa').fill('9001'); page.locator('#apuracao').check()
            page.locator('#executar').click()
            assert repo.listar()==[], 'Execução sem período precisa ser recusada pelo formulário'
            page.locator('#competencia').fill('2024-02')
            expect(page.locator('#periodo-competencia')).to_contain_text('29/02/2024')
            page.locator('#apuracao').check()
            with page.expect_response(lambda r:r.url.endswith('/api/tarefas') and r.request.method=='POST') as resposta:
                page.locator('#executar').click()
            tarefa=resposta.value.json()
            assert tarefa['pedido']['inicio']=='2024-02-01' and tarefa['pedido']['fim']=='2024-02-29'
            expect(page.locator('#competencia')).to_have_value('')
            expect(page.locator('#pausar')).to_be_visible(timeout=4000)
            page.locator('#pausar').click()
            expect(page.locator('#pausar')).to_have_text('Continuar execução',timeout=5000)
            expect(page.locator('#resultado')).to_have_text('Execução pausada')
            time.sleep(.2)
            assert repo.obter(tarefa['id'])['status']=='executando'
            page.locator('#pausar').click()
            expect(page.locator('#resultado')).to_have_text('Concluída pela rotina',timeout=12000)
            page.locator('#config-empresas summary').click()
            page.locator('#regime-nome').fill('Simples sintético')
            page.locator('#regime-rotina').select_option('efd_contribuicoes')
            page.locator('#regime-adicionar').click()
            page.locator('#regime-rotina').select_option('sped_fiscal')
            page.locator('#regime-adicionar').click()
            page.locator('#salvar-regime').click()
            expect(page.locator('#empresa-regime option')).to_have_count(2)
            regime=repo.configuracao.listar()['regimes'][0]['id']
            for codigo,nome in [('9001','Empresa A sintética'),('9002','Empresa B sintética')]:
                page.locator('#empresa-codigo').fill(codigo); page.locator('#empresa-nome').fill(nome)
                page.locator('#empresa-regime').select_option(regime)
                with page.expect_response(lambda r:r.url.endswith('/api/empresas') and r.request.method=='POST'):
                    page.locator('#salvar-empresa').click()
                expect(page.locator('#empresa-codigo')).to_have_value('')
            page.locator('#config-lotes summary').click()
            expect(page.locator('#lote-empresas tr')).to_have_count(2)
            page.locator('#lote-selecionar').click()
            page.locator('#lote-planejar').click()
            expect(page.locator('#lote-aviso')).to_contain_text('informe a competência')
            page.locator('#lote-competencia').fill('2024-02')
            page.locator('#lote-planejar').click()
            expect(page.locator('#lote-plano tr')).to_have_count(4)
            assert [row.locator('td').nth(1).inner_text().split(' · ')[0] for row in page.locator('#lote-plano tr').all()]==['9001','9001','9002','9002']
            assert page.locator('#lote-plano tr').first.locator('td').nth(2).inner_text()=='EFD Contribuições'
            page.locator('#lote-apuracao').check()
            with page.expect_response(lambda r:r.url.endswith('/api/lotes') and r.request.method=='POST') as resposta:
                page.locator('#lote-executar').click()
            lote=resposta.value.json()
            assert lote['plano']['fim']=='2024-02-29'
            expect(page.locator('#lote-competencia')).to_have_value('')
            expect(page.locator('#lote-pausar')).to_be_visible(timeout=4000)
            page.locator('#lote-pausar').click()
            expect(page.locator('#lote-pausar')).to_have_text('Continuar execução',timeout=5000)
            page.locator('#lote-pausar').click()
            expect(page.locator('#lote-resultado')).to_contain_text('4/4 rotinas concluídas',timeout=25000)
            assert repo.obter_lote(lote['id'])['status']=='concluida'
            if os.environ.get('DOMINIO_SMOKE_PREVIEW'):
                page.locator('#config-empresas').evaluate('(el)=>el.open=false')
                aviso_anterior=page.locator('#aviso').inner_text()
                page.locator('#aviso').evaluate('(el)=>el.textContent="Prévia de desenvolvimento: empresas, execução fiscal e login simulados. Esta tela não comprova uma execução no Domínio real."')
                page.screenshot(path=os.environ['DOMINIO_SMOKE_PREVIEW'],full_page=True)
                page.locator('#aviso').evaluate('(el,texto)=>el.textContent=texto',aviso_anterior)
                page.locator('#config-empresas').evaluate('(el)=>el.open=true')
            # Cada linha tem um seletor de regime. Editar revoga a revisão.
            page.locator('#regime-nome').fill('Livros sintéticos')
            page.locator('#regime-sequencia button').filter(has_text='Remover').first.click()
            page.locator('#regime-sequencia button').filter(has_text='Remover').first.click()
            page.locator('#regime-rotina').select_option('registro_entradas'); page.locator('#regime-adicionar').click()
            page.locator('#salvar-regime').click()
            expect(page.locator('#empresa-regime option')).to_have_count(3)
            outro=repo.configuracao.listar()['regimes'][1]['id']
            page.locator('#lote-empresas tr').nth(1).locator('select').select_option(outro)
            expect(page.locator('#cadastro-aviso')).to_contain_text('Cadastro salvo')
            # Espera a gravação antes da próxima revisão.
            for _ in range(50):
                if repo.configuracao.listar()['empresas'][1]['regime_id']==outro: break
                time.sleep(.05)
            assert repo.configuracao.listar()['empresas'][1]['regime_id']==outro
            page.locator('#lote-competencia').fill('2024-02'); page.locator('#lote-planejar').click()
            expect(page.locator('#lote-plano tr')).to_have_count(3)
            page.locator('#lote-apuracao').check(); page.locator('#lote-executar').click()
            expect(page.locator('#lote-cancelar')).to_be_visible(timeout=4000)
            page.locator('#lote-cancelar').click()
            expect(page.locator('#lote-resultado')).to_contain_text('Interrompida',timeout=6000)
            expect(page.locator('#lote-cancelar')).to_be_hidden()
            fiscal.falhar_proxima=True
            page.locator('#lote-competencia').fill('2024-02'); page.locator('#lote-planejar').click()
            expect(page.locator('#lote-plano tr')).to_have_count(3)
            page.locator('#lote-apuracao').check(); page.locator('#lote-executar').click()
            expect(page.locator('#lote-resultado')).to_contain_text('Finalizada com falhas',timeout=18000)
            expect(page.locator('#lote-resultado')).to_contain_text('2/3 rotinas concluídas')
            expect(page.locator('#lote-tarefas tr').first).to_contain_text('Falhou')
            page.locator('#capacidade').select_option('registro_saidas')
            expect(page.locator('#campo-datas')).to_be_visible()
            expect(page.locator('#competencia')).to_be_disabled()
            expect(page.locator('#inicio')).to_be_enabled()
            page.locator('#config-login summary').click()
            for campo,valor in [('onvio-email','teste@example.invalid'),('onvio-senha','senha-simulada'),('dominio-usuario','GERENTE'),('dominio-senha','senha-simulada')]:
                page.locator('#'+campo).fill(valor)
            page.locator('#entrar-dominio').click()
            expect(page.locator('#form-codigo')).to_be_visible(timeout=5000)
            assert page.locator('#onvio-senha').input_value()==''
            assert page.locator('#dominio-senha').input_value()==''
            page.locator('#codigo').fill('654321'); page.locator('#form-codigo button').click()
            expect(page.locator('#login-estado')).to_have_text('Tela principal do Domínio confirmada',timeout=5000)
            expect(page.locator('#form-codigo')).to_be_hidden()
            page.locator('#confirmar-calibracao').check(); page.locator('#calibrar-servidor').click()
            expect(page.locator('#login-estado')).to_have_text('Referência da tela principal salva',timeout=5000)
            page.locator('#capturar-servidor').click()
            expect(page.locator('#captura-servidor')).to_be_visible(timeout=5000)
            assert page.locator('#captura-servidor').evaluate('(im)=>im.naturalWidth')==400
            page.locator('#ocultar-captura').click(); expect(page.locator('#captura-servidor')).to_be_hidden()
            page.locator('#config-rotinas summary').click()
            page.locator('#rotina-nome').fill('Roteiro simulado')
            page.locator('.passo-rotina input').fill('Relatórios')
            page.locator('#adicionar-passo').click()
            page.locator('.passo-rotina').nth(1).locator('select').first.select_option('digitar')
            page.locator('#salvar-rotina').click()
            expect(page.locator('#rotina-aviso')).to_contain_text('rascunho salvo',timeout=5000)
            expect(page.locator('#rotinas-configuradas')).to_contain_text('Roteiro simulado')
            assert len(list((root/'rotinas').glob('*.json')))==1
            # Pré-cadastro pedido: metadados, sem promover rotinas ou executar.
            repo.configuracao.preparar_piloto()
            expect(page.locator('#empresa-regime option')).to_have_count(5,timeout=6000)
            resumo=page.locator('#rotinas-cadastradas tr').filter(has_text='Resumo por Acumulador')
            expect(resumo).to_contain_text('Lucro Presumido, Lucro Real')
            expect(resumo).to_contain_text('Pendente de configuração')
            resumo.get_by_role('button',name='Configurar',exact=True).click()
            expect(page.locator('#rotina-nome')).to_have_value('Resumo por Acumulador')
            page.locator('.passo-rotina input').fill('Relatórios')
            page.locator('#salvar-rotina').click()
            expect(page.locator('#rotina-aviso')).to_contain_text('configuração salva como rascunho')
            resumo.get_by_role('button',name='Enviar para validação',exact=True).click()
            expect(resumo).to_contain_text('Enviada para validação · execução bloqueada')
            resumo.get_by_role('button',name='Configurar',exact=True).click()
            expect(page.locator('.passo-rotina input')).to_have_value('Relatórios')
            page.locator('#salvar-rotina').click()
            expect(resumo).to_contain_text('Rascunho · revisar e testar')
            page.locator('#cadastro-rotina-nome').fill('Indicador sintético sem passos')
            page.locator('#cadastrar-rotina').click()
            expect(page.locator('#rotinas-cadastradas')).to_contain_text('Indicador sintético sem passos')
            presumido=next(r for r in repo.configuracao.listar()['regimes'] if r['nome']=='Lucro Presumido')
            page.locator('#regime-editar').select_option(presumido['id'])
            expect(page.locator('#regime-sequencia li')).to_have_count(5)
            expect(page.locator('#regime-sequencia')).to_contain_text('Livro Fiscal de ICMS')
            if os.environ.get('DOMINIO_CADASTRO_PREVIEW'):
                page.locator('#config-empresas').screenshot(path=os.environ['DOMINIO_CADASTRO_PREVIEW'])
            for campo,valor in [('onvio-senha','senha-simulada'),('dominio-senha','senha-simulada')]:page.locator('#'+campo).fill(valor)
            page.locator('#confirmar-reinicio').check(); page.locator('#reiniciar-ciclo').click()
            expect(page.locator('#form-codigo')).to_be_visible(timeout=5000)
            page.locator('#cancelar-login').click()
            expect(page.locator('#login-estado')).to_contain_text('Login cancelado',timeout=5000)
            for width in (1440,900,390):
                page.set_viewport_size({'width':width,'height':1000})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
            page.locator('#sair').click()
            expect(page.locator('#conteudo')).to_be_hidden()
            assert page.locator('#onvio-email').input_value()==''
            assert page.locator('#codigo').input_value()==''
            context.set_offline(True); page.reload()
            expect(page.locator('#login')).to_be_visible()
            assert not erros,erros
            browser.close()
        print('Chromium passou: pré-cadastro Lucro Presumido/Real, configuração individual e envio à validação sem liberar execução, regimes/empresas/sequência por empresa, calendário, lote, pausa/retomada/interrupção, login/captura simulados, responsividade, logout e offline.')
    finally:
        server.should_exit=True; thread.join(15)
        assert not thread.is_alive(), 'Servidor precisa encerrar sem travamento'
