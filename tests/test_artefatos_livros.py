"""Três PDFs locais confirmados, resultados parciais e downloads por artefato."""
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from app.api_servidor import criar_app
from app.servidor import RepositorioTarefas, ServicoExecucao
from test_servidor import aguardar, eventos_confirmados


class TestArtefatosLivros(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.root = Path(pasta.name)
        self.saida = self.root / 'saida'
        self.saida.mkdir()
        self.repo = RepositorioTarefas(self.root / 'data' / 'banco.sqlite3')
        self.dados = {'request_id': str(uuid.uuid4()), 'capacidade': 'livros_fiscais',
                      'empresa_codigo': '52', 'inicio': '2024-08-01', 'fim': '2024-08-31',
                      'apuracao_confirmada': True}
        self.tipos = ['registro_entradas', 'registro_saidas', 'registro_icms']
        self.headers = {'Authorization': 'Bearer ' + 'x' * 48}

    def documentos(self, quantidade=3):
        itens = []
        for i, tipo in enumerate(self.tipos[:quantidade]):
            caminho = self.saida / (tipo + '.pdf')
            writer = PdfWriter()
            writer.add_blank_page(width=200 + i, height=300)
            writer.write(caminho)
            itens.append({'tipo': tipo, 'caminho': str(caminho)})
        return itens

    def executar(self, resultado, confirmar=True):
        def executor(dados, receber):
            if confirmar:
                eventos_confirmados(dados, receber)
            return resultado
        servico = ServicoExecucao(self.repo, executor, 'simulacao', pasta_saida=self.saida)
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        tarefa, _ = self.repo.criar(self.dados, 'simulacao')
        servico._acordar.set()
        final = aguardar(self.repo, tarefa['id'])
        return servico, final

    def test_tres_artefatos_sobrevivem_reinicio_e_nao_expoem_caminhos(self):
        itens = self.documentos()
        _, final = self.executar((True, itens))
        self.assertEqual(final['status'], 'concluida')
        self.assertEqual(len(final['artefatos']), 3)
        self.assertTrue(all(a['disponivel'] for a in final['artefatos']))
        self.assertNotIn(str(self.root), json.dumps(final))
        nova = RepositorioTarefas(self.repo.caminho)
        self.assertEqual(nova.obter(final['id'])['artefatos'], final['artefatos'])
        self.assertEqual(nova.listar()[0]['artefatos'], final['artefatos'])

    def test_false_com_dois_pdfs_permanece_falha_e_preserva_os_dois(self):
        _, final = self.executar((False, self.documentos(2)))
        self.assertEqual(final['status'], 'falha')
        self.assertFalse(final['resultado'])
        self.assertEqual(len(final['artefatos']), 2)
        self.assertTrue(final['arquivo_disponivel'])

    def test_true_incompleto_ou_sem_retorno_nao_vira_sucesso(self):
        _, final = self.executar((True, self.documentos(2)))
        self.assertEqual(final['status'], 'nao_confirmada')
        self.assertEqual(final['motivo'], 'livros_incompletos')
        self.assertEqual(len(final['artefatos']), 2)

    def test_pdfs_completos_sem_retorno_permanecem_disponiveis(self):
        _, final = self.executar((True, self.documentos()), confirmar=False)
        self.assertEqual(final['status'], 'nao_confirmada')
        self.assertEqual(len(final['artefatos']), 3)

    def test_documento_invalido_e_tipo_duplicado_nao_autorizados(self):
        itens = self.documentos()
        Path(itens[1]['caminho']).write_bytes(b'%PDF- INVALIDO')
        itens.append(itens[0].copy())
        with self.assertLogs('app.servidor', level='ERROR'):
            _, final = self.executar((True, itens))
        self.assertEqual(final['status'], 'nao_confirmada')
        self.assertEqual({a['tipo'] for a in final['artefatos']}, {'registro_entradas', 'registro_icms'})

    def test_falha_destino_preserva_origens_validadas(self):
        with patch.object(ServicoExecucao, '_nomear_arquivo', side_effect=OSError('sintetico')):
            with self.assertLogs('app.servidor', level='ERROR'):
                _, final = self.executar((True, self.documentos()))
        self.assertEqual(final['status'], 'nao_confirmada')
        self.assertEqual(final['motivo'], 'nome_arquivo_nao_confirmado')
        self.assertTrue(all(a['disponivel'] for a in final['artefatos']))

    def test_downloads_exigem_chave_tarefa_e_artefato_exatos(self):
        servico, final = self.executar((False, self.documentos(2)))
        cliente = TestClient(criar_app(servico, 'x' * 48, pasta_saida=self.saida))
        tarefa_id = final['id']
        for artefato in final['artefatos']:
            rota = f"/api/tarefas/{tarefa_id}/artefatos/{artefato['id']}/arquivo"
            self.assertEqual(cliente.get(rota).status_code, 401)
            resposta = cliente.get(rota, headers=self.headers)
            self.assertEqual(resposta.status_code, 200)
            self.assertTrue(resposta.content.startswith(b'%PDF-'))
            self.assertEqual(cliente.get(rota.replace(tarefa_id, 'outra'), headers=self.headers).status_code, 404)
        self.assertEqual(cliente.get(f'/api/tarefas/{tarefa_id}/arquivo', headers=self.headers).status_code, 200)
        self.assertEqual(cliente.get(f'/api/tarefas/{tarefa_id}/artefatos/inventado/arquivo', headers=self.headers).status_code, 404)

    def test_substituicao_ou_symlink_do_pdf_bloqueia_download(self):
        servico, final = self.executar((False, self.documentos(1)))
        artefato = final['artefatos'][0]
        privado = self.repo.obter_artefato(final['id'], artefato['id'])
        caminho = Path(privado['caminho'])
        caminho.write_bytes(b'%PDF- alterado')
        self.assertFalse(self.repo.obter(final['id'])['artefatos'][0]['disponivel'])
        cliente = TestClient(criar_app(servico, 'x' * 48, pasta_saida=self.saida))
        rota = f"/api/tarefas/{final['id']}/artefatos/{artefato['id']}/arquivo"
        self.assertEqual(cliente.get(rota, headers=self.headers).status_code, 404)
        outro = self.root / 'privado.pdf'
        outro.write_bytes(b'%PDF- alterado')
        caminho.unlink()
        caminho.symlink_to(outro)
        self.assertEqual(cliente.get(rota, headers=self.headers).status_code, 404)

    def test_nao_aceita_caminho_externo_mesmo_pdf_valido(self):
        itens = self.documentos(1)
        externo = self.root / 'externo.pdf'
        Path(itens[0]['caminho']).rename(externo)
        itens[0]['caminho'] = str(externo)
        with self.assertLogs('app.servidor', level='ERROR'):
            _, final = self.executar((False, itens))
        self.assertEqual(final['artefatos'], [])
        self.assertFalse(final['arquivo_disponivel'])

    def test_publicacao_nome_empresa_destino_mais_tres_autorizacoes_exatas(self):
        raiz = self.root / 'empresas'
        fiscal = raiz / 'EMPRESA_EXEMPLO' / '2024' / 'FISCAL'
        fiscal.mkdir(parents=True)
        (self.repo.caminho.parent / 'destino_livros.json').write_text(
            json.dumps({'raiz': str(raiz), 'subpasta_livros': 'RELATORIOS/LIVROS'}), encoding='utf-8')
        regime = self.repo.configuracao.salvar_regime(None, 'Lucro Presumido', ['registro_entradas'])
        self.repo.configuracao.salvar_empresa('52', 'Empresa Exemplo', regime['id'], 'EMPRESA_EXEMPLO')
        tarefa, _ = self.repo.criar(self.dados)
        servico = ServicoExecucao(self.repo, pasta_saida=self.saida)
        caminhos, completa, falhou = servico._publicar_livros(tarefa, self.dados, self.documentos())
        self.assertTrue(completa)
        self.assertFalse(falhou)
        self.assertEqual(len(caminhos), 3)
        destino = fiscal / '08' / 'RELATORIOS' / 'LIVROS'
        self.assertTrue(all(Path(p).parent == destino for p in caminhos))
        self.assertTrue(all('empresa_exemplo_2024-08' in Path(p).name for p in caminhos))
        self.assertEqual(len(self.repo.artefatos(tarefa['id'])), 3)
        self.assertTrue(all(self.repo.artefato_permitido(self.repo.obter_artefato(tarefa['id'], a['id']))
                            for a in self.repo.artefatos(tarefa['id'])))

    def test_presumido_inteiro_um_pedido_com_tres_rotinas_e_tres_downloads(self):
        self.repo.configuracao.preparar_piloto()
        regime = next(r for r in self.repo.configuracao.listar()['regimes'] if r['nome'] == 'Lucro Presumido')
        self.assertEqual(regime['rotinas'], ['resumo_acumulador', 'efd_contribuicoes', 'livros_fiscais'])
        self.repo.configuracao.salvar_empresa('52', 'Empresa Exemplo', regime['id'])
        selecao = {'empresas': ['52'], 'inicio': '2024-08-01', 'fim': '2024-08-31'}
        plano = self.repo.configuracao.planejar(selecao)
        chamadas = []
        def executor(dados, receber):
            chamadas.append(dados['capacidade'])
            eventos_confirmados(dados, receber)
            return (True, self.documentos()) if dados['capacidade'] == 'livros_fiscais' else True
        servico = ServicoExecucao(self.repo, executor, 'simulacao', pasta_saida=self.saida)
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        lote = servico.solicitar_lote({**selecao, 'request_id': str(uuid.uuid4()),
                                      'plano_hash': plano['hash'], 'apuracao_confirmada': True})
        limite = time.monotonic() + 3
        while time.monotonic() < limite:
            lote = self.repo.obter_lote(lote['id'])
            if lote['status'] not in ('pendente', 'executando'):
                break
            time.sleep(.01)
        self.assertEqual(lote['status'], 'concluida')
        self.assertEqual(chamadas, regime['rotinas'])
        diagnostico = self.repo.diagnostico_lote(lote['id'])
        self.assertEqual(len(diagnostico['rotinas']), 3)
        self.assertEqual(len(diagnostico['rotinas'][-1]['artefatos']), 3)
        self.assertTrue(all(a['disponivel'] for a in diagnostico['rotinas'][-1]['artefatos']))
        self.assertNotIn(str(self.root), json.dumps(diagnostico))


if __name__ == '__main__':
    unittest.main()
