"""API real com banco/worker locais e executor fiscal substituído."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

from app.servidor import RepositorioTarefas, ServicoExecucao
from test_servidor import aguardar, eventos_confirmados, pedido

WEB_DISPONIVEL = all(importlib.util.find_spec(nome) for nome in ("fastapi", "httpx"))
if WEB_DISPONIVEL:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app, obter_chave


@unittest.skipUnless(WEB_DISPONIVEL, "Componentes opcionais: requirements-dev-servidor.txt")
class TestApiServidor(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.saida = self.pasta / "saida"
        self.saida.mkdir()
        self.repo = RepositorioTarefas(self.pasta / "banco.sqlite3")
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True
        self.servico = ServicoExecucao(self.repo, executar, modo="simulacao")
        self.chave = "x" * 48
        self.client = TestClient(criar_app(self.servico, self.chave, self.saida, pasta_rotinas=self.pasta / "rotinas"))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {"Authorization": f"Bearer {self.chave}"}

    def test_autenticacao_exigida_em_todos_os_dados_e_comandos(self):
        for rota in ("estado", "capacidades", "tarefas", "tarefas/x", "tarefas/x/arquivo", "cadastros", "lotes", "lotes/x"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get("/api/" + rota).status_code, 401)
        self.assertEqual(self.client.post("/api/tarefas", json=pedido()).status_code, 401)
        for rota in ("login/iniciar", "login/reiniciar", "login/codigo", "login/cancelar", "sessao/calibrar", "sessao/capturar", "rotinas", "tarefas/x/pausar", "tarefas/x/continuar", "regimes", "empresas", "lotes/planejar", "lotes", "lotes/x/cancelar"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.post("/api/" + rota, json={}).status_code, 401)
        for rota in ("sessao/captura", "rotinas"):
            self.assertEqual(self.client.get("/api/" + rota).status_code, 401)
        self.assertEqual(self.client.get("/api/estado", headers={"Authorization": "Bearer errado"}).status_code, 401)

    def test_interface_e_manifesto_sem_segredos(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Conectar ao servidor", resposta.text)
        self.assertNotIn(self.chave, resposta.text)
        self.assertEqual(self.client.get("/static/manifest.webmanifest").json()["display"], "standalone")
        self.assertEqual(self.client.get("/sw.js").status_code, 200)

    def test_pedido_estado_eventos_e_consulta_concluem_por_http(self):
        resposta = self.client.post("/api/tarefas", json=pedido(), headers=self.headers)
        self.assertEqual(resposta.status_code, 202)
        identificador = resposta.json()["id"]
        aguardar(self.repo, identificador)
        final = self.client.get("/api/tarefas/" + identificador, headers=self.headers)
        self.assertEqual(final.json()["status"], "concluida")
        self.assertEqual(len(final.json()["eventos"]), 6)
        self.assertEqual(final.headers["cache-control"], "no-store")
        self.assertEqual(len(self.client.get("/api/tarefas", headers=self.headers).json()), 1)

    def test_duplicacao_de_requisicao_nao_reexecuta(self):
        dados = pedido()
        primeira = self.client.post("/api/tarefas", json=dados, headers=self.headers).json()
        aguardar(self.repo, primeira["id"])
        repetida = self.client.post("/api/tarefas", json=dados, headers=self.headers).json()
        self.assertEqual(primeira["id"], repetida["id"])
        self.assertEqual(len(self.repo.listar()), 1)

    def test_validacao_nao_repete_input_privado_no_erro(self):
        dados = {**pedido(), "arquivo": "SEGREDO PRIVADO", "apuracao_confirmada": "PRIVADO"}
        resposta = self.client.post("/api/tarefas", json=dados, headers=self.headers)
        self.assertEqual(resposta.status_code, 422)
        self.assertNotIn("PRIVADO", resposta.text)
        self.assertEqual(self.repo.listar(), [])

    def test_login_invalido_nao_publica_senha_ou_codigo(self):
        dados = {"email": "teste@example.invalid", "senha_onvio": "SENHA-PRIVADA", "usuario_dominio": "GERENTE", "senha_dominio": "PRIVADA", "comando": "livre"}
        resposta = self.client.post("/api/login/iniciar", json=dados, headers=self.headers)
        self.assertEqual(resposta.status_code, 422)
        self.assertNotIn("PRIVADA", resposta.text)
        self.assertNotIn("PRIVADA", self.client.get("/api/estado", headers=self.headers).text)
        self.assertEqual(self.client.post("/api/login/codigo", json={"solicitacao_id": "x", "codigo": "PRIVADO"}, headers=self.headers).status_code, 422)

    def test_login_no_modo_consulta_ou_simulacao_sem_adapter_recusa(self):
        dados = {"email": "teste@example.invalid", "senha_onvio": "privada", "usuario_dominio": "GERENTE", "senha_dominio": "privada"}
        self.assertEqual(self.client.post("/api/login/iniciar", json=dados, headers=self.headers).status_code, 503)
        self.assertEqual(self.client.post("/api/login/reiniciar", json=dados, headers=self.headers).status_code, 422)
        self.assertEqual(self.repo.listar(), [])

    def test_codigo_expirado_e_controle_de_tarefa_antiga_sao_recusados(self):
        self.assertEqual(self.client.post("/api/login/codigo", json={"solicitacao_id": "a"*32, "codigo": "123456"}, headers=self.headers).status_code, 409)
        for acao in ("pausar", "continuar"):
            self.assertEqual(self.client.post("/api/tarefas/antiga/" + acao, headers=self.headers).status_code, 409)

    def test_rotina_configurada_e_rascunho_e_nao_entra_no_catalogo_fiscal(self):
        dados = {"nome": "Roteiro de teste", "passos": [{"tipo": "clicar", "valor": "Relatórios"}]}
        resposta = self.client.post("/api/rotinas", json=dados, headers=self.headers)
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json()["status"], "rascunho")
        self.assertEqual(len(self.client.get("/api/rotinas", headers=self.headers).json()), 1)
        self.assertEqual(len(self.client.get("/api/capacidades", headers=self.headers).json()), 5)

    def test_calibracao_exige_confirmacao_humana_e_captura_expira(self):
        self.assertEqual(self.client.post("/api/sessao/calibrar", json={"tela_principal_confirmada": False}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.get("/api/sessao/captura", headers=self.headers).status_code, 404)

    def test_arquivo_so_pode_vir_da_pasta_de_saida(self):
        tarefa, _ = self.repo.criar(pedido())
        fora = self.pasta / "fora.txt"
        fora.write_text("PRIVADO")
        self.repo.concluir(tarefa["id"], "falha", False, arquivo=fora)
        resposta = self.client.get(f"/api/tarefas/{tarefa['id']}/arquivo", headers=self.headers)
        self.assertEqual(resposta.status_code, 404)
        self.assertNotIn("PRIVADO", resposta.text)
        dentro = self.saida / "documento.pdf"
        dentro.write_bytes(b"%PDF-simulado")
        self.repo.concluir(tarefa["id"], "concluida", True, arquivo=dentro)
        resposta = self.client.get(f"/api/tarefas/{tarefa['id']}/arquivo", headers=self.headers)
        self.assertEqual(resposta.content, b"%PDF-simulado")

    def test_download_usa_nome_empresa_cadastrada_e_preserva_conteudo(self):
        regime = self.repo.configuracao.salvar_regime(None, "Lucro Presumido sintético", ["registro_entradas"])
        self.repo.configuracao.salvar_empresa("52", "Empresa Fictícia", regime["id"])
        origem = self.saida / "exportacao_sintetica.pdf"
        origem.write_bytes(b"%PDF-sintetico")
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True, str(origem)
        self.servico.executor = executar
        dados = {**pedido(), "capacidade": "registro_entradas", "inicio": "2026-08-01", "fim": "2026-08-31"}
        tarefa = self.client.post("/api/tarefas", json=dados, headers=self.headers).json()
        self.assertEqual(aguardar(self.repo, tarefa["id"])["status"], "concluida")
        resposta = self.client.get(f"/api/tarefas/{tarefa['id']}/arquivo", headers=self.headers)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b"%PDF-sintetico")
        self.assertIn('filename="registro_entradas_empresa_ficticia_2026-08.pdf"', resposta.headers["content-disposition"])
        self.assertFalse(origem.exists())

    def test_chave_existente_nao_e_trocada_ou_impressa(self):
        caminho = self.pasta / "chave.txt"
        primeira = obter_chave(caminho)
        self.assertEqual(obter_chave(caminho), primeira)
        caminho.write_text("invalida")
        with self.assertRaises(ValueError):
            obter_chave(caminho)
        self.assertEqual(caminho.read_text(), "invalida")

    def test_resumo_catalogo_datas_nome_cadastrado_e_download(self):
        regime = self.repo.configuracao.salvar_regime(None, "Lucro Presumido", ["resumo_acumulador"])
        self.repo.configuracao.salvar_empresa("52", "Empresa Cadastrada", regime["id"])
        origem = self.saida / "nome_lido.pdf"
        origem.write_bytes(b"%PDF-sintetico-resumo")
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True, str(origem)
        self.servico.executor = executar
        capacidades = self.client.get("/api/capacidades", headers=self.headers).json()
        resumo = next(c for c in capacidades if c["id"] == "resumo_acumulador")
        self.assertEqual(resumo["tipo_periodo"], "datas")
        dados = {**pedido(), "capacidade": "resumo_acumulador", "inicio": "2026-08-01", "fim": "2026-08-31"}
        tarefa = self.client.post("/api/tarefas", json=dados, headers=self.headers).json()
        self.assertEqual(aguardar(self.repo, tarefa["id"])["status"], "concluida")
        resposta = self.client.get(f"/api/tarefas/{tarefa['id']}/arquivo", headers=self.headers)
        self.assertEqual(resposta.content, b"%PDF-sintetico-resumo")
        self.assertIn('filename="acumulador_empresa_cadastrada_2026-08.pdf"', resposta.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
