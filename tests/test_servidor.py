"""Persistência/worker reais; nenhum teste opera mouse, teclado ou Domínio."""

import datetime as dt
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from app.servidor import (PrecondicaoRecusada, RepositorioTarefas, ServicoExecucao,
                          SessaoOcupada, periodo_anterior, validar_pedido)


def pedido():
    inicio, fim = periodo_anterior()
    return {"request_id": str(uuid.uuid4()), "capacidade": "sped_fiscal", "empresa_codigo": "52",
            "inicio": inicio, "fim": fim, "apuracao_confirmada": True}


def eventos_confirmados(dados, receber):
    for etapa in ("navegar_menu", "preencher_periodo", "identificar_formulario", "gerar_documento", "encerrar", "fim"):
        receber({"execution_id": dados["request_id"].replace("-", ""), "routine_id": dados["capacidade"],
                 "attempt": 1, "step": etapa, "status": "concluido" if etapa == "fim" else "confirmado",
                 "elapsed_seconds": 0.5, "evidence": "tela_principal_reconhecida" if etapa == "encerrar" else None})


def aguardar(repositorio, identificador):
    limite = time.monotonic() + 3
    while time.monotonic() < limite:
        tarefa = repositorio.obter(identificador)
        if tarefa["status"] not in ("pendente", "executando"):
            return tarefa
        threading.Event().wait(0.01)
    raise AssertionError("Worker não concluiu a tarefa no prazo do teste.")


class TestValidacaoServidor(unittest.TestCase):
    def test_calendario_anterior_inclui_virada_de_ano(self):
        self.assertEqual(periodo_anterior(dt.date(2026, 1, 4)), ("2025-12-01", "2025-12-31"))

    def test_recusa_codigo_livre_campos_extras_datas_atuais_e_sem_apuracao(self):
        for extra in ({"capacidade": "os.system"}, {"comando": "qualquer"}, {"empresa_codigo": "52; comando"},
                      {"request_id": "qualquer"}, {"apuracao_confirmada": False}, {"apuracao_confirmada": 1},
                      {"inicio": "2026-10-01", "fim": "2026-10-07"}, {"fim": "2026-02-30"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validar_pedido({**pedido(), **extra}, hoje=dt.date(2026, 10, 7))

    def test_sped_recusa_periodo_diferente_do_mes_anterior(self):
        with self.assertRaises(ValueError):
            validar_pedido({**pedido(), "inicio": "2026-08-01", "fim": "2026-08-31"}, hoje=dt.date(2026, 10, 7))

    def test_livro_aceita_periodo_passado_escolhido(self):
        dados = {**pedido(), "capacidade": "registro_saidas", "inicio": "2026-08-01", "fim": "2026-08-31"}
        self.assertEqual(validar_pedido(dados, hoje=dt.date(2026, 10, 7)), dados)


class BaseRepositorio:
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.caminho = Path(pasta.name) / "tarefas.sqlite3"
        self.repo = RepositorioTarefas(self.caminho)


class TestRepositorioServidor(BaseRepositorio, unittest.TestCase):
    def test_pedido_duplicado_nao_cria_outra_tarefa(self):
        dados = pedido()
        primeira, nova = self.repo.criar(dados)
        repetida, nova_repetida = self.repo.criar(dados)
        self.assertTrue(nova)
        self.assertFalse(nova_repetida)
        self.assertEqual(primeira["id"], repetida["id"])
        self.assertEqual(len(self.repo.listar()), 1)
        with self.assertRaises(SessaoOcupada):
            self.repo.criar({**dados, "empresa_codigo": "99"})

    def test_solicitacoes_concorrentes_aceitam_uma_unica_execucao(self):
        respostas = []
        barreira = threading.Barrier(4)
        def enviar():
            barreira.wait()
            try:
                self.repo.criar(pedido())
                respostas.append("aceita")
            except SessaoOcupada:
                respostas.append("ocupada")
        threads = [threading.Thread(target=enviar) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(respostas.count("aceita"), 1)
        self.assertEqual(respostas.count("ocupada"), 3)

    def test_reinicio_preserva_tarefa_sem_reexecutar(self):
        tarefa, _ = self.repo.criar(pedido())
        self.repo.proxima()
        repo_novo = RepositorioTarefas(self.caminho)
        repo_novo.retomar()
        self.assertEqual(repo_novo.obter(tarefa["id"])["status"], "interrompida")
        self.assertIsNone(repo_novo.proxima())

    def test_eventos_nao_publicam_evidencia_livre_ou_campos_privados(self):
        dados = pedido()
        tarefa, _ = self.repo.criar(dados)
        self.repo.registrar_evento(tarefa["id"], {"execution_id": "a" * 32, "routine_id": "sped_fiscal", "attempt": 1,
                                                "step": "navegar_menu", "status": "inicio", "elapsed_seconds": 0,
                                                "evidence": "TEXTO PRIVADO", "ocr": "CLIENTE PRIVADO"})
        texto = json.dumps(self.repo.eventos(tarefa["id"]))
        self.assertNotIn("PRIVADO", texto)


class TestWorkerServidor(BaseRepositorio, unittest.TestCase):
    def iniciar(self, executor):
        servico = ServicoExecucao(self.repo, executor, modo="simulacao")
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        return servico

    def test_true_sem_evidencias_nao_confirma_tarefa(self):
        servico = self.iniciar(lambda dados, receber: True)
        tarefa = servico.solicitar(pedido())
        self.assertEqual(aguardar(self.repo, tarefa["id"])["status"], "nao_confirmada")

    def test_conclusao_exige_resultado_e_fim_e_retorno(self):
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return True
        tarefa = self.iniciar(executar).solicitar(pedido())
        final = aguardar(self.repo, tarefa["id"])
        self.assertEqual(final["status"], "concluida")
        self.assertEqual(final["modo"], "simulacao")

    def test_false_permanece_falha_mesmo_com_retorno_confirmado(self):
        def executar(dados, receber):
            eventos_confirmados(dados, receber)
            return False
        tarefa = self.iniciar(executar).solicitar(pedido())
        self.assertEqual(aguardar(self.repo, tarefa["id"])["status"], "falha")

    def test_excecao_privada_nao_sai_na_resposta_publica(self):
        def executar(dados, receber):
            raise RuntimeError("CLIENTE PRIVADO")
        with self.assertLogs("app.servidor", level="ERROR"):
            tarefa = self.iniciar(executar).solicitar(pedido())
            final = aguardar(self.repo, tarefa["id"])
        self.assertEqual(final["status"], "falha")
        self.assertNotIn("PRIVADO", json.dumps(final))

    def test_precondicao_recusada_nao_e_resultado_confirmado(self):
        def executar(dados, receber):
            raise PrecondicaoRecusada("empresa_nao_confirmada")
        tarefa = self.iniciar(executar).solicitar(pedido())
        self.assertEqual(aguardar(self.repo, tarefa["id"])["status"], "recusada")

    def test_sem_executor_recusa_comando(self):
        servico = ServicoExecucao(self.repo)
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        with self.assertRaises(PrecondicaoRecusada):
            servico.solicitar(pedido())

    def test_segundo_processo_nao_reinicia_ou_roda_o_primeiro(self):
        primeiro = self.iniciar(lambda dados, receber: False)
        segundo = ServicoExecucao(self.repo, lambda dados, receber: True, modo="simulacao")
        with self.assertRaises(OSError):
            segundo.iniciar()
        self.assertTrue(primeiro.disponivel)


if __name__ == "__main__":
    unittest.main()
