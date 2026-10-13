"""Raiz/empresa por restante ou caminho completo; pastas sintéticas locais."""
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest

from app import destinos_livros
from app.servidor import RepositorioTarefas, ServicoExecucao

WEB = all(importlib.util.find_spec(n) for n in ('fastapi','httpx'))
if WEB:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app


class TestRaizCompartilhada(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.dados=self.root/'data'; self.dados.mkdir()
        self.raiz=self.root/'Empresas'/'Grupo compartilhado'; self.raiz.mkdir(parents=True)
        self.empresa=self.raiz/'1.6 EMPRESA FICTICIA'
        (self.empresa/'2026/FISCAL').mkdir(parents=True)
        (self.dados/'destino_livros.json').write_text(json.dumps({'raiz':str(self.raiz)}))

    def test_nome_curto_e_caminho_completo_entre_aspas_produzem_mesmo_destino(self):
        curta=destinos_livros.pasta_empresa('1.6 EMPRESA FICTICIA',self.dados)
        completa=destinos_livros.pasta_empresa(f'"{self.empresa}"',self.dados)
        self.assertEqual(curta,completa)
        self.assertEqual(completa,'1.6 EMPRESA FICTICIA')
        for valor in (curta,str(self.empresa)):
            p=destinos_livros.planejar_destino({'codigo':'52','nome':'Empresa Fictícia','pasta_relativa':valor},
                                              'Lucro Presumido','2026-08',self.dados)
            self.assertEqual(Path(p['caminho_local']),self.empresa/'2026/FISCAL/08/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS')
        self.assertFalse((self.empresa/'2026/FISCAL/08').exists())

    def test_caminho_windows_respeita_limite_da_pasta_e_case_insensitive(self):
        raiz=PureWindowsPath(r'C:\Empresas\Grupo')
        self.assertEqual(destinos_livros._relativa_do_caminho_completo(r'c:\EMPRESAS\grupo\Empresa Ficticia',raiz),'Empresa Ficticia')
        for valor in (r'C:\Empresas\Grupo2\Empresa Ficticia',r'D:\Empresas\Grupo\Empresa Ficticia',
                      r'C:\Empresas\Grupo\..\Outra',r'C:\Empresas\Grupo'):
            with self.subTest(valor=valor),self.assertRaises(ValueError):
                destinos_livros._relativa_do_caminho_completo(valor,raiz)

    def test_preserva_mapa_antigo_com_prefixo_da_raiz_estreitada(self):
        for relativa in ('Grupo compartilhado/1.6 EMPRESA FICTICIA','Empresas/Grupo compartilhado/1.6 EMPRESA FICTICIA'):
            self.assertEqual(destinos_livros.pasta_empresa(relativa,self.dados),'1.6 EMPRESA FICTICIA')
        mapa=self.dados/'mapa_pastas_empresas.csv'
        mapa.write_text('codigo_dominio;pasta_relativa_a_raiz\n52;Empresas/Grupo compartilhado/1.6 EMPRESA FICTICIA\n')
        antes=mapa.read_bytes()
        p=destinos_livros.planejar_destino({'codigo':'52','nome':'Empresa Fictícia','pasta_relativa':''},'Lucro Real','2026-08',self.dados)
        self.assertEqual(Path(p['caminho_local']),self.empresa/'2026/FISCAL/08/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS')
        self.assertEqual(mapa.read_bytes(),antes)

    def test_nao_adivinha_uma_pasta_inexistente_ou_duas_abreviacoes_possiveis(self):
        self.assertEqual(destinos_livros.pasta_empresa('Grupo compartilhado/Empresa Ausente',self.dados),
                         'Grupo compartilhado/Empresa Ausente')
        raiz=self.root/'Grupo'/'Grupo'; raiz.mkdir(parents=True)
        (raiz/'Grupo/Empresa').mkdir(parents=True); (raiz/'Empresa').mkdir()
        with self.assertRaisesRegex(ValueError,'ambíguo'):
            destinos_livros.pasta_empresa('Grupo/Grupo/Empresa',self.dados,raiz)

    def test_recusa_caminho_fora_da_raiz_e_links_externos(self):
        for valor in (str(self.root/'outro'),str(self.raiz),'../outra','1.6 EMPRESA FICTICIA/../outra'):
            with self.subTest(valor=valor),self.assertRaises(ValueError):destinos_livros.pasta_empresa(valor,self.dados)
        fora=self.root/'fora'; fora.mkdir()
        try:(self.raiz/'link').symlink_to(fora,target_is_directory=True)
        except OSError:self.skipTest('Symlink indisponível.')
        with self.assertRaisesRegex(ValueError,'fora da raiz'):
            destinos_livros.pasta_empresa(str(self.raiz/'link'),self.dados)

    def test_raiz_visivel_no_cadastro_e_completa_armazenada_como_relativa(self):
        repo=RepositorioTarefas(self.dados/'banco.sqlite3')
        regime=repo.configuracao.salvar_regime(None,'Lucro Presumido',['registro_entradas'])
        empresa=repo.configuracao.salvar_empresa('52','Empresa Fictícia',regime['id'],str(self.empresa))
        self.assertEqual(empresa['pasta_relativa'],'1.6 EMPRESA FICTICIA')
        c=repo.configuracao.listar()['destino_livros']
        self.assertTrue(c['configurada']); self.assertEqual(c['raiz'],str(self.raiz))
        (self.dados/'destino_livros.json').unlink()
        self.assertEqual(repo.configuracao.listar()['destino_livros']['raiz'],'')
        self.assertFalse(repo.configuracao.listar()['destino_livros']['configurada'])

    def test_configurador_grava_raiz_uma_vez_no_arquivo_local(self):
        import contextlib,io
        from unittest.mock import patch
        from scripts import configurar_destino_livros
        with patch.object(configurar_destino_livros,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(configurar_destino_livros.main(['--raiz',str(self.raiz)]),0)
        self.assertEqual(destinos_livros.configuracao_para_painel(self.dados)['raiz'],str(self.raiz))
        self.assertEqual(list(self.empresa.iterdir()),[self.empresa/'2026'])

    def test_mudar_raiz_preserva_subpasta_e_nao_sobrescreve_json_invalido(self):
        import contextlib,io
        from unittest.mock import patch
        from scripts import configurar_destino_livros
        arquivo=self.dados/'destino_livros.json'
        arquivo.write_text(json.dumps({'raiz':str(self.root/'raiz_antiga_ausente'),'subpasta_livros':'RELATORIOS/LIVROS'}))
        with patch.object(configurar_destino_livros,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            configurar_destino_livros.main(['--raiz',str(self.raiz)])
            self.assertEqual(json.loads(arquivo.read_text())['subpasta_livros'],'RELATORIOS/LIVROS')
            arquivo.write_text('invalido')
            with self.assertRaises(SystemExit):configurar_destino_livros.main(['--raiz',str(self.raiz)])
            self.assertEqual(arquivo.read_text(),'invalido')
            configurar_destino_livros.main(['--raiz',str(self.raiz),'--subpasta','NOVO/LIVROS'])
            self.assertEqual(json.loads(arquivo.read_text())['subpasta_livros'],'NOVO/LIVROS')

    @unittest.skipUnless(WEB,'API indisponível.')
    def test_api_raiz_e_caminho_completo_exigem_autenticacao_e_nao_emitem(self):
        repo=RepositorioTarefas(self.dados/'banco.sqlite3')
        regime=repo.configuracao.salvar_regime(None,'Lucro Real',['registro_entradas'])
        chave='d'*48; headers={'Authorization':'Bearer '+chave}
        servico=ServicoExecucao(repo)
        empresa={'codigo':'52','nome':'Empresa Fictícia','regime_id':regime['id'],'pasta_relativa':str(self.empresa)}
        with TestClient(criar_app(servico,chave)) as cliente:
            self.assertEqual(cliente.get('/api/cadastros').status_code,401)
            self.assertEqual(cliente.post('/api/empresas',json=empresa).status_code,401)
            cad=cliente.get('/api/cadastros',headers=headers).json()
            self.assertEqual(cad['destino_livros']['raiz'],str(self.raiz))
            resposta=cliente.post('/api/empresas',json=empresa,headers=headers)
            self.assertEqual(resposta.status_code,200)
            self.assertEqual(resposta.json()['pasta_relativa'],'1.6 EMPRESA FICTICIA')
            self.assertEqual(repo.listar(),[])
            fora=cliente.post('/api/empresas',json={**empresa,'pasta_relativa':str(self.root/'fora')},headers=headers)
            self.assertEqual(fora.status_code,422)
            self.assertNotIn(str(self.root),fora.text)
            self.assertEqual(repo.configuracao.listar()['empresas'][0]['pasta_relativa'],'1.6 EMPRESA FICTICIA')
