"""Cadastro independente de execução, com configurações sintéticas."""
import importlib.util
import tempfile
from pathlib import Path
import unittest
import uuid

from app.servidor import RepositorioTarefas, ServicoExecucao

WEB = all(importlib.util.find_spec(n) for n in ("fastapi", "httpx"))
if WEB:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app


class TestCadastroRotinas(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.repo = RepositorioTarefas(Path(self.pasta.name) / "teste.sqlite3")
        self.config = self.repo.configuracao
        self.dados = {"nome": "Relatório sintético", "passos": [{"tipo": "clicar", "valor": "Relatórios"}]}

    def test_piloto_prepara_dois_regimes_cinco_indicadores_sem_empresas(self):
        self.config.preparar_piloto()
        cad = self.config.listar()
        self.assertEqual([r["nome"] for r in cad["regimes"]], ["Lucro Presumido", "Lucro Real"])
        self.assertEqual(cad["empresas"], [])
        nomes = {r["id"]: r["nome"] for r in cad["rotinas"]}
        for regime in cad["regimes"]:
            self.assertEqual([nomes[r] for r in regime["rotinas"]],
                             ["Resumo por Acumulador", "Demonstrativo EFD Contribuições", "Registro de Entradas", "Registro de Saídas", "Livro Fiscal de ICMS"])
            self.assertNotIn("efd_contribuicoes", regime["rotinas"])
            self.assertNotIn("sped_fiscal", regime["rotinas"])
        self.assertEqual([r["status"] for r in cad["rotinas"] if r["status"] != "integrada"],
                         ["pendente_configuracao"] * 3)
        self.assertEqual(self.repo.listar(), [])

    def test_reinicio_nao_duplica_nem_restaura_configuracao_editada(self):
        self.config.preparar_piloto()
        regime = self.config.listar()["regimes"][0]
        self.config.salvar_regime(regime["id"], regime["nome"], ["registro_entradas"])
        anterior = self.config.listar()
        nova = RepositorioTarefas(self.repo.caminho)
        nova.configuracao.preparar_piloto()
        self.assertEqual(nova.configuracao.listar(), anterior)

    def test_piloto_preserva_regime_ja_existente(self):
        existente = self.config.salvar_regime(None, "LUCRO PRESUMIDO", ["sped_fiscal"])
        self.config.preparar_piloto()
        atualizado = self.config.listar()["regimes"][0]
        self.assertEqual(atualizado["id"], existente["id"])
        self.assertEqual(atualizado["rotinas"][0], "sped_fiscal")
        self.assertEqual(len(atualizado["rotinas"]), 2)
        self.assertEqual(len(self.config.listar()["regimes"]), 2)

    def test_icms_acrescenta_ao_piloto_anterior_sem_recriar_demais_rotinas(self):
        self.config.preparar_piloto()
        icms = next(r for r in self.config.listar()["rotinas"] if r["nome"] == "Livro Fiscal de ICMS")
        with self.repo.conectar() as banco:
            banco.execute("DELETE FROM marcos_cadastro WHERE id='piloto_lp_lr_icms_v2'")
            for regime in self.config.listar(banco)["regimes"]:
                import json
                banco.execute("UPDATE regimes SET rotinas=? WHERE id=?",
                              (json.dumps([r for r in regime["rotinas"] if r != icms["id"]]), regime["id"]))
            banco.execute("DELETE FROM rotinas_cadastradas WHERE id=?", (icms["id"],))
        anterior = self.config.listar()
        self.config.preparar_piloto()
        atual = self.config.listar()
        self.assertEqual([r["id"] for r in anterior["regimes"]], [r["id"] for r in atual["regimes"]])
        for antes, depois in zip(anterior["regimes"], atual["regimes"]):
            self.assertEqual(antes["rotinas"], depois["rotinas"][:-1])
        self.assertEqual(len(atual["rotinas"]), len(anterior["rotinas"]) + 1)

    def test_cadastro_sem_passos_pode_ser_vinculado_antes_de_configurar(self):
        rotina = self.config.cadastrar_rotina(self.dados["nome"])
        self.assertEqual(rotina["status"], "pendente_configuracao")
        self.assertEqual(rotina["passos"], [])
        regime = self.config.salvar_regime(None, "Regime sintético", [rotina["id"]])
        self.assertEqual(regime["rotinas"], [rotina["id"]])
        self.assertEqual(self.repo.listar(), [])

    def test_ciclo_configurar_enviar_reeditar_revoga_envio(self):
        rotina = self.config.cadastrar_rotina(self.dados["nome"])
        with self.assertRaises(ValueError):
            self.config.enviar_validacao(rotina["id"])
        configurada = self.config.configurar_rotina(rotina["id"], self.dados)
        self.assertEqual(configurada["status"], "rascunho")
        self.assertEqual(configurada["passos"], self.dados["passos"])
        self.assertEqual(self.config.enviar_validacao(rotina["id"])["status"], "aguardando_validacao")
        self.assertEqual(self.config.enviar_validacao(rotina["id"])["status"], "aguardando_validacao")
        self.assertEqual(self.config.configurar_rotina(rotina["id"], self.dados)["status"], "rascunho")
        self.assertEqual(len(self.config.listar()["rotinas"]), 5)

    def test_nome_duplicado_e_passos_invalidos_nao_alteram_cadastro(self):
        rotina = self.config.cadastrar_rotina(self.dados["nome"])
        for nome in (self.dados["nome"].upper(), "SPED Fiscal", " "):
            with self.assertRaises(ValueError):
                self.config.cadastrar_rotina(nome)
        for dados in ({"nome": "X", "passos": []},
                      {"nome": "X", "passos": [{"tipo": "clicar", "valor": "Transmitir"}]},
                      {**self.dados, "status": "aprovada"},
                      {**self.dados, "nome": "SPED Fiscal"}):
            with self.assertRaises(ValueError):
                self.config.configurar_rotina(rotina["id"], dados)
        self.assertEqual(self.config.obter_rotina(rotina["id"]), rotina)

    def test_aguardando_validacao_nao_libera_lote_ou_execucao(self):
        rotina = self.config.cadastrar_rotina(self.dados["nome"])
        regime = self.config.salvar_regime(None, "Regime sintético", [rotina["id"]])
        self.config.salvar_empresa("9001", "Empresa sintética", regime["id"])
        selecao = {"empresas": ["9001"], "inicio": "2024-02-01", "fim": "2024-02-29"}
        for etapa in (lambda: None, lambda: self.config.configurar_rotina(rotina["id"], self.dados),
                      lambda: self.config.enviar_validacao(rotina["id"])):
            etapa()
            with self.assertRaises(ValueError):
                self.config.planejar(selecao)
        self.assertEqual(self.repo.listar_lotes(), [])

    @unittest.skipUnless(WEB, "Dependências da API ausentes")
    def test_api_exige_auth_e_nao_aceita_aprovacao_ou_execucao_de_cadastro(self):
        cliente = TestClient(criar_app(ServicoExecucao(self.repo), "d" * 48))
        headers = {"Authorization": "Bearer " + "d" * 48}
        self.assertEqual(cliente.post("/api/rotinas/cadastros", json={"nome": "Teste"}).status_code, 401)
        rotina = cliente.post("/api/rotinas/cadastros", json={"nome": self.dados["nome"]}, headers=headers).json()
        base = "/api/rotinas/cadastros/" + rotina["id"]
        for metodo, caminho, dados in (("get", base, None), ("put", base, self.dados), ("post", base + "/validacao", None)):
            resposta = cliente.request(metodo, caminho, json=dados)
            self.assertEqual(resposta.status_code, 401)
        self.assertEqual(cliente.put(base, json={**self.dados, "status": "aprovada"}, headers=headers).status_code, 422)
        self.assertEqual(cliente.post(base + "/validacao", headers=headers).status_code, 422)
        self.assertEqual(cliente.put(base, json=self.dados, headers=headers).json()["status"], "rascunho")
        self.assertEqual(cliente.post(base + "/validacao", headers=headers).json()["status"], "aguardando_validacao")
        self.assertEqual(cliente.get(base, headers=headers).json()["passos"], self.dados["passos"])
        self.assertEqual(cliente.get("/api/rotinas", headers=headers).json(), [])
        self.assertEqual(cliente.get("/api/capacidades", headers=headers).json().__len__(), 4)
        self.assertEqual(cliente.get("/api/rotinas/cadastros/inexistente", headers=headers).status_code, 404)
        with self.assertRaises(ValueError):
            from app.servidor import validar_pedido
            validar_pedido({"request_id": str(uuid.uuid4()), "capacidade": rotina["id"], "empresa_codigo": "9001",
                           "inicio": "2024-02-01", "fim": "2024-02-29", "apuracao_confirmada": True})
