"""Fila/SQLite/API reais; nenhum cadastro real ou ação de desktop."""

import json
import importlib.util
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid

WEB_DISPONIVEL = all(importlib.util.find_spec(nome) for nome in ("fastapi", "httpx"))
if WEB_DISPONIVEL:
    from fastapi.testclient import TestClient
    from app.api_servidor import criar_app
from app.controle_execucao import ponto_seguro
from app.servidor import RepositorioTarefas, ServicoExecucao, SessaoOcupada
from test_servidor import eventos_confirmados, pedido


class BaseLotes(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.repo = RepositorioTarefas(Path(self.pasta.name) / "tarefas.sqlite3")
        self.config = self.repo.configuracao
        self.regime = self.config.salvar_regime(None, "Simples Nacional sintético", ["efd_contribuicoes", "sped_fiscal"])
        self.config.salvar_empresa("52", "Empresa A sintética", self.regime["id"])
        self.config.salvar_empresa("53", "Empresa B sintética", self.regime["id"])
        self.selecao = {"empresas": ["52", "53"], "inicio": "2024-02-01", "fim": "2024-02-29"}

    def dados(self):
        plano = self.config.planejar(self.selecao)
        return {**self.selecao, "request_id": str(uuid.uuid4()), "apuracao_confirmada": True, "plano_hash": plano["hash"]}

    def iniciar(self, executor):
        servico = ServicoExecucao(self.repo, executor, modo="simulacao")
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        return servico

    def aguardar(self, identificador):
        for _ in range(300):
            lote = self.repo.obter_lote(identificador)
            if lote["status"] not in ("pendente", "executando") and all(t["status"] not in ("pendente", "executando") for t in lote["tarefas"]):
                return lote
            time.sleep(.01)
        self.fail("Lote não terminou no prazo.")


class TestConfiguracaoLotes(BaseLotes):
    def test_regime_nao_deduz_obrigacoes_e_ordem_e_do_usuario(self):
        plano = self.config.planejar(self.selecao)
        self.assertEqual(plano["quantidade_rotinas"], 4)
        self.assertEqual(plano["empresas"][0]["rotinas"], ["efd_contribuicoes", "sped_fiscal"])
        vazio = self.config.salvar_regime(None, "Outro regime", [])
        self.config.salvar_empresa("53", "Empresa B sintética", vazio["id"])
        with self.assertRaises(ValueError):
            self.config.planejar(self.selecao)

    def test_seletor_de_regime_muda_rotinas_da_empresa(self):
        outro = self.config.salvar_regime(None, "Lucro Real sintético", ["registro_entradas"])
        self.config.salvar_empresa("53", "Empresa B sintética", outro["id"])
        plano = self.config.planejar(self.selecao)
        self.assertEqual(plano["empresas"][1]["rotinas"], ["registro_entradas"])
        self.assertEqual(plano["quantidade_rotinas"], 3)

    def test_cadastro_persiste_sem_carregar_empresas_de_exemplo(self):
        nova = RepositorioTarefas(self.repo.caminho)
        self.assertEqual(nova.configuracao.listar(), self.config.listar())
        self.assertEqual(len(nova.configuracao.listar()["empresas"]), 2)
        self.config.salvar_empresa("00052", "Nome atualizado", self.regime["id"])
        self.assertEqual(len(self.config.listar()["empresas"]), 2)

    def test_recusa_rotina_livre_repetida_regime_ausente_e_empresas_repetidas(self):
        for rotinas in (["os.system"], ["sped_fiscal", "sped_fiscal"], [False]):
            with self.subTest(rotinas=rotinas), self.assertRaises(ValueError):
                self.config.salvar_regime(None, "Teste", rotinas)
        with self.assertRaises(ValueError):
            self.config.salvar_empresa("99", "Empresa", "a" * 32)
        for empresas in (["52", "052"], ["99"], [], [52]):
            with self.subTest(empresas=empresas), self.assertRaises(ValueError):
                self.config.planejar({**self.selecao, "empresas": empresas})

    def test_datas_sao_obrigatorias_mes_bissexto_preservado_e_sped_exige_mes_inteiro(self):
        self.assertEqual(self.config.planejar(self.selecao)["fim"], "2024-02-29")
        for valores in ({"inicio": ""}, {"fim": "2024-02-28"}, {"inicio": "2099-02-01", "fim": "2099-02-28"}):
            with self.subTest(valores=valores), self.assertRaises(ValueError):
                self.config.planejar({**self.selecao, **valores})

    def test_livros_aceitam_intervalo_passado_sem_sped(self):
        self.config.salvar_regime(self.regime["id"], self.regime["nome"], ["registro_entradas"])
        plano = self.config.planejar({**self.selecao, "inicio": "2024-02-12", "fim": "2024-02-20"})
        self.assertEqual(plano["inicio"], "2024-02-12")


class TestRepositorioLotes(BaseLotes):
    def test_ordem_agrupa_todas_as_rotinas_de_cada_empresa(self):
        lote, _ = self.repo.criar_lote(self.dados(), "simulacao")
        self.assertEqual([(t["pedido"]["empresa_codigo"], t["pedido"]["capacidade"]) for t in lote["tarefas"]],
                         [("52", "efd_contribuicoes"), ("52", "sped_fiscal"), ("53", "efd_contribuicoes"), ("53", "sped_fiscal")])

    def test_repeticao_e_reinicio_nao_reexecutam_mesmo_com_cadastro_editado(self):
        dados = self.dados()
        primeiro, novo = self.repo.criar_lote(dados, "simulacao")
        self.assertTrue(novo)
        self.config.salvar_regime(self.regime["id"], self.regime["nome"], ["sped_fiscal"])
        repetido, novo = self.repo.criar_lote(dados, "simulacao")
        self.assertFalse(novo)
        self.assertEqual(primeiro, repetido)
        self.repo.retomar()
        repetido, novo = self.repo.criar_lote(dados, "simulacao")
        self.assertEqual(repetido["status"], "interrompida")
        self.assertTrue(all(t["status"] == "interrompida" for t in repetido["tarefas"]))
        self.assertIsNone(self.repo.proxima())

    def test_revisao_desatualizada_nao_cria_tarefas(self):
        dados = self.dados()
        self.config.salvar_regime(self.regime["id"], self.regime["nome"], ["sped_fiscal"])
        with self.assertRaises(ValueError):
            self.repo.criar_lote(dados, "simulacao")
        self.assertEqual(self.repo.listar(), [])

    def test_sem_apuracao_nao_cria_tarefas(self):
        dados = self.dados()
        with self.assertRaises(ValueError):
            self.repo.criar_lote({**dados, "apuracao_confirmada": False}, "simulacao")
        self.assertEqual(self.repo.listar_lotes(), [])

    def test_lote_e_tarefa_individual_compartilham_exclusividade(self):
        self.repo.criar_lote(self.dados(), "simulacao")
        with self.assertRaises(SessaoOcupada):
            self.repo.criar(pedido())
        with self.assertRaises(SessaoOcupada):
            self.repo.criar_lote(self.dados(), "simulacao")

    def test_lotes_concorrentes_criam_um_unico_lote_completo(self):
        barreira = threading.Barrier(2)
        resultados = []
        def criar():
            dados = self.dados()
            barreira.wait()
            try:
                self.repo.criar_lote(dados, "simulacao")
                resultados.append("aceito")
            except SessaoOcupada:
                resultados.append("ocupado")
        threads = [threading.Thread(target=criar) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(resultados), ["aceito", "ocupado"])
        self.assertEqual(len(self.repo.listar()), 4)

    def test_ocupacao_nao_depende_do_limite_de_cem_linhas_do_historico(self):
        for codigo in range(100, 200):
            self.config.salvar_empresa(str(codigo), "Empresa sintética", self.regime["id"])
        self.selecao["empresas"] = [str(c) for c in range(100, 200)]
        lote, _ = self.repo.criar_lote(self.dados(), "simulacao")
        atual = self.repo.proxima()
        self.repo.cancelar_lote(lote["id"])
        self.assertTrue(all(t["status"] == "interrompida" for t in self.repo.listar()))
        self.assertTrue(self.repo.tem_pendentes())
        self.assertEqual(self.repo.obter(atual["id"])["status"], "executando")


class TestWorkerLotes(BaseLotes):
    def test_falha_recuperada_segue_proxima_e_finaliza_com_falhas(self):
        chamadas, recuperacoes = [], []
        def executar(dados, receber):
            chamadas.append((dados["empresa_codigo"], dados["capacidade"]))
            if len(chamadas) == 1:
                return False, "arquivo_sintetico.pdf"
            eventos_confirmados(dados, receber)
            return True
        def recuperar(dados):
            recuperacoes.append(dados["capacidade"])
            return True
        executar.recuperar_em_lote = recuperar
        lote = self.iniciar(executar).solicitar_lote(self.dados())
        final = self.aguardar(lote["id"])
        self.assertEqual(len(chamadas), 4)
        self.assertEqual(recuperacoes, ["efd_contribuicoes"])
        self.assertEqual(final["status"], "concluida_com_falhas")
        self.assertEqual(final["motivo"], "rotinas_com_falhas")
        self.assertEqual([t["status"] for t in final["tarefas"]], ["falha", "concluida", "concluida", "concluida"])
        self.assertFalse(final["tarefas"][0]["resultado"])
        self.assertTrue(final["tarefas"][0]["arquivo_disponivel"])
        self.assertEqual(self.repo.eventos(final["tarefas"][0]["id"])[-1]["evidence"], "tela_principal_reconhecida")

    def test_recuperacao_nao_confirmada_interrompe_inclusive_apos_falha_recuperada(self):
        chamadas = []
        def executar(dados, receber):
            chamadas.append(dados)
            return False
        executar.recuperar_em_lote = lambda dados: len(chamadas) == 1
        lote = self.iniciar(executar).solicitar_lote(self.dados())
        final = self.aguardar(lote["id"])
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(final["status"], "interrompida")
        self.assertEqual(final["motivo"], "rotina_nao_concluida")
        self.assertEqual([t["status"] for t in final["tarefas"]], ["falha", "falha", "interrompida", "interrompida"])

    def test_excecao_original_permanece_falha_depois_da_recuperacao(self):
        chamadas = []
        def executar(dados, receber):
            chamadas.append(dados)
            if len(chamadas) == 1:
                raise RuntimeError("Falha sintética")
            eventos_confirmados(dados, receber)
            return True
        executar.recuperar_em_lote = lambda dados: True
        with self.assertLogs("app.servidor", level="ERROR"):
            lote = self.iniciar(executar).solicitar_lote(self.dados())
            final = self.aguardar(lote["id"])
        self.assertEqual(len(chamadas), 4)
        self.assertEqual(final["tarefas"][0]["status"], "falha")
        self.assertEqual(final["tarefas"][0]["motivo"], "erro_execucao_consulte_servidor")

    def test_cancelar_durante_recuperacao_nao_retoma_proximas(self):
        entrou, liberar = threading.Event(), threading.Event()
        chamadas = []
        def executar(dados, receber):
            chamadas.append(dados)
            return False
        def recuperar(dados):
            entrou.set()
            self.assertTrue(liberar.wait(2))
            return True
        executar.recuperar_em_lote = recuperar
        servico = self.iniciar(executar)
        lote = servico.solicitar_lote(self.dados())
        self.assertTrue(entrou.wait(2))
        with self.assertLogs("app.servidor", level="ERROR"):
            servico.cancelar_lote(lote["id"]); liberar.set()
            final = self.aguardar(lote["id"])
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(final["status"], "interrompida")
        self.assertEqual(final["motivo"], "lote_cancelado")

    def test_executa_empresa_inteira_antes_da_proxima(self):
        chamadas = []
        def executar(dados, receber):
            chamadas.append((dados["empresa_codigo"], dados["capacidade"], dados["inicio"], dados["fim"]))
            eventos_confirmados(dados, receber)
            return True
        lote = self.iniciar(executar).solicitar_lote(self.dados())
        final = self.aguardar(lote["id"])
        self.assertEqual(final["status"], "concluida")
        self.assertEqual(chamadas, [(e, r, "2024-02-01", "2024-02-29") for e in ("52", "53") for r in ("efd_contribuicoes", "sped_fiscal")])

    def test_falha_ou_true_sem_retorno_interrompe_proximas(self):
        for resultado, esperado in ((False, "falha"), (True, "nao_confirmada")):
            with self.subTest(resultado=resultado):
                chamadas = []
                def executar(dados, receber):
                    chamadas.append(dados)
                    return resultado
                servico = self.iniciar(executar)
                lote = servico.solicitar_lote(self.dados())
                final = self.aguardar(lote["id"])
                self.assertEqual(len(chamadas), 1)
                self.assertEqual(final["status"], "interrompida")
                self.assertEqual(final["tarefas"][0]["status"], esperado)
                self.assertTrue(all(t["status"] == "interrompida" for t in final["tarefas"][1:]))
                servico.encerrar()

    def test_cancelamento_acorda_execucao_pausada_e_nao_roda_proxima(self):
        entrou, liberar = threading.Event(), threading.Event()
        def executar(dados, receber):
            entrou.set(); liberar.wait(2); ponto_seguro(); eventos_confirmados(dados, receber); return True
        servico = self.iniciar(executar)
        lote = servico.solicitar_lote(self.dados())
        self.assertTrue(entrou.wait(2))
        controle = servico.estado_controle()
        servico.controlar(controle["tarefa_id"], "pausar")
        liberar.set()
        for _ in range(100):
            if servico.estado_controle()["estado"] == "pausada": break
            time.sleep(.01)
        self.assertEqual(servico.estado_controle()["estado"], "pausada")
        servico.cancelar_lote(lote["id"])
        final = self.aguardar(lote["id"])
        self.assertEqual(final["motivo"], "lote_cancelado")
        self.assertTrue(all(t["status"] == "interrompida" for t in final["tarefas"]))

    def test_snapshot_do_lote_nao_muda_ao_editar_regime(self):
        lote, _ = self.repo.criar_lote(self.dados(), "simulacao")
        self.config.salvar_regime(self.regime["id"], "Nome novo", ["registro_saidas"])
        self.assertEqual(self.repo.obter_lote(lote["id"])["plano"], lote["plano"])

    def test_resultados_anteriores_sao_preservados_ao_falhar_na_empresa_seguinte(self):
        def executar(dados, receber):
            if dados["empresa_codigo"] == "53":
                return False
            eventos_confirmados(dados, receber)
            return True
        lote = self.iniciar(executar).solicitar_lote(self.dados())
        final = self.aguardar(lote["id"])
        self.assertEqual([t["status"] for t in final["tarefas"]], ["concluida", "concluida", "falha", "interrompida"])


@unittest.skipUnless(WEB_DISPONIVEL, "Componentes opcionais: requirements-dev-servidor.txt")
class TestApiLotes(BaseLotes):
    def test_cadastro_planejamento_auth_e_conflito_de_revisao(self):
        servico = ServicoExecucao(self.repo)
        client = TestClient(criar_app(servico, "x" * 48))
        headers = {"Authorization": "Bearer " + "x" * 48}
        for caminho in ("cadastros", "lotes"):
            self.assertEqual(client.get("/api/" + caminho).status_code, 401)
        self.assertEqual(client.get("/api/cadastros", headers=headers).json(), self.config.listar())
        plano = client.post("/api/lotes/planejar", json=self.selecao, headers=headers)
        self.assertEqual(plano.status_code, 200)
        self.assertEqual(plano.json()["quantidade_rotinas"], 4)
        self.assertEqual(client.post("/api/regimes", headers=headers, json={"nome": "Ruim", "rotinas": ["os.system"]}).status_code, 422)
        self.assertEqual(client.post("/api/lotes", headers=headers, json=self.dados()).status_code, 503)

    def test_api_lote_executa_e_expoe_ordem_sem_caminhos_privados(self):
        def executar(dados, receber):
            eventos_confirmados(dados, receber); return True
        servico = ServicoExecucao(self.repo, executar, modo="simulacao")
        with TestClient(criar_app(servico, "x" * 48)) as client:
            headers = {"Authorization": "Bearer " + "x" * 48}
            dados = self.dados()
            resposta = client.post("/api/lotes", headers=headers, json=dados)
            self.assertEqual(resposta.status_code, 202)
            lote = resposta.json()
            self.aguardar(lote["id"])
            self.assertEqual(client.get("/api/lotes/" + lote["id"], headers=headers).json()["status"], "concluida")
            self.assertEqual(client.post("/api/lotes", headers=headers, json=dados).json()["id"], lote["id"])
            resumo = client.get("/api/lotes", headers=headers).json()[0]
            self.assertNotIn("tarefas", resumo)
            self.assertNotIn(str(self.repo.caminho), json.dumps(lote))
