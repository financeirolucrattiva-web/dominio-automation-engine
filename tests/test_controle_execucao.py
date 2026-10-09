"""Pausa real em thread: não retoma sozinha, nem aceita tela divergente."""

import threading
import time
import unittest
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao, ponto_seguro, verificar_retomada, verificar_antes_de_agir
from test_servidor import BaseRepositorio, aguardar, eventos_confirmados, pedido
from app.servidor import ServicoExecucao, SessaoOcupada


def esperar(condicao):
    limite = time.monotonic() + 3
    while time.monotonic() < limite:
        if condicao():
            return
        threading.Event().wait(0.005)
    raise AssertionError("Condição não observada no prazo do teste.")


class TestControle(unittest.TestCase):
    def test_verificacao_antes_de_agir_bloqueia_e_nao_vaza_contexto(self):
        chamadas = []
        def recusar():
            chamadas.append("verificou")
            raise ValueError("sessao divergente")
        with self.assertRaisesRegex(ValueError, "sessao divergente"):
            with verificar_antes_de_agir(recusar):
                ponto_seguro()
                chamadas.append("acao indevida")
        ponto_seguro()
        self.assertEqual(chamadas, ["verificou"])

    def executar_pausa(self, verificar=lambda: True):
        controle, saiu, erros = ControleExecucao(), threading.Event(), []
        controle.pausar()
        def executar():
            try:
                with controlar_execucao(controle), verificar_retomada(lambda: verificar):
                    ponto_seguro()
            except ExecucaoInterrompida as erro:
                erros.append(str(erro))
            finally:
                saiu.set()
        thread = threading.Thread(target=executar)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(controle.interromper)
        esperar(lambda: controle.estado == "pausada")
        self.assertFalse(saiu.is_set())
        return controle, saiu, erros

    def test_pausa_bloqueia_ate_continuar_e_valida_retomada(self):
        controle, saiu, erros = self.executar_pausa()
        controle.continuar()
        self.assertTrue(saiu.wait(3))
        self.assertEqual(erros, [])
        self.assertEqual(controle.estado, "executando")

    def test_tela_divergente_interrompe_inclusive_se_chamador_engole_excecao(self):
        controle, saiu, erros = self.executar_pausa(lambda: False)
        controle.continuar()
        self.assertTrue(saiu.wait(3))
        self.assertEqual(erros, ["retomada_nao_confirmada"])
        with self.assertRaises(ExecucaoInterrompida):
            controle.verificar_interrupcao()

    def test_encerrar_servidor_nao_retoma_pausa(self):
        controle, saiu, erros = self.executar_pausa()
        controle.encerrar()
        self.assertTrue(saiu.wait(3))
        self.assertEqual(erros, ["servidor_encerrado_durante_pausa"])

    def test_reinicio_interrompe_sem_pausa_previa(self):
        controle = ControleExecucao()
        controle.interromper()
        with self.assertRaisesRegex(ExecucaoInterrompida, "reinicio_solicitado"):
            controle.ponto_seguro()

    def test_contexto_nao_vaza_para_outra_execucao(self):
        controle = ControleExecucao()
        controle.interromper()
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            ponto_seguro()
        ponto_seguro()


class TestWorkerPausa(BaseRepositorio, unittest.TestCase):
    def test_pausa_impede_nova_tarefa_e_fecha_worker_sem_deadlock(self):
        comecou, liberar = threading.Event(), threading.Event()
        def executar(dados, receber):
            comecou.set()
            liberar.wait(3)
            ponto_seguro()
            eventos_confirmados(dados, receber)
            return True
        servico = ServicoExecucao(self.repo, executar, modo="simulacao")
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        tarefa = servico.solicitar(pedido())
        self.assertTrue(comecou.wait(3))
        self.assertEqual(servico.controlar(tarefa["id"], "pausar")["estado"], "pausa_solicitada")
        liberar.set()
        esperar(lambda: servico.estado_controle()["estado"] == "pausada")
        with self.assertRaises(SessaoOcupada):
            servico.solicitar(pedido())
        with self.assertRaises(SessaoOcupada):
            servico.controlar("outra", "continuar")
        servico.encerrar()
        self.assertEqual(self.repo.obter(tarefa["id"])["status"], "interrompida")
        self.assertIsNone(servico.estado_controle())

    def test_retomada_conclui_a_mesma_tarefa_uma_unica_vez(self):
        comecou, liberar = threading.Event(), threading.Event()
        chamadas = []
        def executar(dados, receber):
            chamadas.append(dados["request_id"])
            comecou.set()
            liberar.wait(3)
            ponto_seguro()
            eventos_confirmados(dados, receber)
            return True
        servico = ServicoExecucao(self.repo, executar, modo="simulacao")
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        tarefa = servico.solicitar(pedido())
        self.assertTrue(comecou.wait(3))
        servico.controlar(tarefa["id"], "pausar")
        liberar.set()
        esperar(lambda: servico.estado_controle()["estado"] == "pausada")
        servico.controlar(tarefa["id"], "continuar")
        self.assertEqual(aguardar(self.repo, tarefa["id"])["status"], "concluida")
        self.assertEqual(len(chamadas), 1)
