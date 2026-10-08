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
    for etapa in ('navegar_menu','preencher_periodo','identificar_formulario','gerar_documento','encerrar','fim'):
        ponto_seguro()
        time.sleep(.7)
        receber({'execution_id':dados['request_id'].replace('-',''),'routine_id':dados['capacidade'],
                 'attempt':1,'step':etapa,'status':'concluido' if etapa=='fim' else 'confirmado',
                 'elapsed_seconds':.7,'evidence':'tela_principal_reconhecida' if etapa=='encerrar' else None})
    return True


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
        print('Chromium passou: calendário obrigatório/bissexto, pausa/retomada, código único, senhas limpas, calibração/captura simuladas, rascunho, reinício/cancelamento, responsividade, logout e offline.')
    finally:
        server.should_exit=True; thread.join(15)
        assert not thread.is_alive(), 'Servidor precisa encerrar sem travamento'
