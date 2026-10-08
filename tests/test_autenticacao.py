"""Código humano, exclusividade e segredos fora do banco/API/logs."""

import json
import threading
import unittest
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw

from app.autenticacao import SessaoLogin, CredenciaisLogin, LoginRecusado
from app.login_windows import LoginWindows, conferir_destino, localizar_campos
from app.servidor import ServicoExecucao, SessaoOcupada
from test_servidor import BaseRepositorio, pedido, aguardar
from test_controle_execucao import esperar


class TestAutenticacao(unittest.TestCase):
    def test_codigo_entrega_unica_com_id_da_solicitacao_e_limpeza(self):
        sessao = SessaoLogin()
        sessao.iniciar()
        recebidos = []
        thread = threading.Thread(target=lambda: recebidos.append(sessao.aguardar_codigo(3)))
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(sessao.cancelar)
        esperar(lambda: sessao.publico()["estado"] == "aguardando_codigo")
        id_codigo = sessao.publico()["solicitacao_id"]
        with self.assertRaises(LoginRecusado):
            sessao.fornecer_codigo("outro", "123456")
        sessao.fornecer_codigo(id_codigo, "123456")
        thread.join(3)
        self.assertEqual(recebidos, ["123456"])
        self.assertIsNone(sessao.publico()["solicitacao_id"])
        self.assertNotIn("123456", json.dumps(sessao.publico()))
        with self.assertRaises(LoginRecusado):
            sessao.fornecer_codigo(id_codigo, "123456")

    def test_cancelamento_desbloqueia_codigo_sem_retomar_login(self):
        sessao = SessaoLogin()
        erros = []
        def aguardar_codigo():
            try:
                sessao.aguardar_codigo(3)
            except LoginRecusado as erro:
                erros.append(str(erro))
        thread = threading.Thread(target=aguardar_codigo)
        thread.start()
        esperar(lambda: sessao.publico()["solicitacao_id"] is not None)
        sessao.cancelar()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(erros, ["login_cancelado"])

    def test_codigo_expirado_nao_e_entregue(self):
        sessao = SessaoLogin()
        with self.assertRaisesRegex(LoginRecusado, "codigo_expirado"):
            sessao.aguardar_codigo(0)
        self.assertIsNone(sessao.publico()["solicitacao_id"])

    def test_segredos_nao_entram_no_repr(self):
        dados = CredenciaisLogin("teste@example.invalid", "SENHA-ONVIO-PRIVADA", "GERENTE", "SENHA-FISCAL-PRIVADA")
        self.assertNotIn("PRIVADA", repr(dados))
        dados.limpar()
        self.assertEqual(dados.senha_onvio, "")

    def test_segredo_so_vai_para_host_https_explicitamente_conhecido(self):
        conferir_destino("https://auth.thomsonreuters.com/u/login")
        for destino in ("http://auth.thomsonreuters.com", "https://auth.thomsonreuters.com.evil.invalid", "https://evil.invalid", "https://usuario@onvio.com.br", "https://auth.thomsonreuters.com:8080"):
            with self.subTest(destino=destino), self.assertRaises(LoginRecusado):
                conferir_destino(destino)

    def test_falha_preserva_a_etapa_sem_expor_excecao_privada(self):
        sessao = SessaoLogin()
        sessao.iniciar()
        sessao.fase("abrir_escrita_fiscal")
        sessao.fase("falha", "tela_login_nao_reconhecida")
        self.assertEqual(sessao.publico()["etapa"], "abrir_escrita_fiscal")

    def test_campos_sao_medidos_na_imagem_e_ambiguidade_recusa(self):
        imagem = Image.new("RGB", (400, 220), "#c0c0c0")
        desenho = ImageDraw.Draw(imagem)
        rotulos = [(65, 60), (35, 95), (55, 130)]
        for y in (50, 85, 120):
            desenho.rectangle((140, y, 315, y + 20), fill="white", outline="black", width=1)
        posicoes = localizar_campos(imagem, rotulos)
        self.assertTrue(all(abs(x - 227) <= 2 for x, _ in posicoes))
        desenho.rectangle((330, 50, 399, 70), fill="white", outline="black")
        with self.assertRaises(LoginRecusado):
            localizar_campos(imagem, rotulos)

    def test_captura_janela_maximizada_recorta_so_a_parte_visivel(self):
        api, tela, interacao = Mock(), Mock(), Mock()
        interacao._api_janelas.return_value = (api, None)
        imagem = Image.new("RGB", (400, 220), "blue")
        tela.capturar_tela.return_value = imagem
        api.GetForegroundWindow.return_value = 123
        def geometria(hwnd, ponteiro):
            retangulo = ponteiro._obj
            retangulo.left, retangulo.top, retangulo.right, retangulo.bottom = -8, -8, 408, 228
            return True
        api.GetWindowRect.side_effect = geometria
        login = LoginWindows()
        with patch.multiple("app", create=True, tela=tela, interacao=interacao), patch.object(login, "_focar"):
            captura, origem = login._capturar({"hwnd": 123})
            self.assertEqual(captura.size, imagem.size)
            self.assertEqual(origem, (0, 0))
            api.GetForegroundWindow.return_value = 999
            with self.assertRaises(LoginRecusado):
                login._capturar({"hwnd": 123})


class TestLoginWorker(BaseRepositorio, unittest.TestCase):
    def test_login_bloqueia_rotina_e_limpa_senhas_sem_persistir(self):
        login = Mock()
        inicio, liberar = threading.Event(), threading.Event()
        def executar(dados, sessao):
            inicio.set()
            liberar.wait(3)
            sessao.fase("tela_principal_confirmada")
        login.executar.side_effect = executar
        servico = ServicoExecucao(self.repo, lambda dados, receber: False, "simulacao", login=login)
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        self.addCleanup(liberar.set)
        dados = CredenciaisLogin("teste@example.invalid", "PRIVADO", "GERENTE", "PRIVADO")
        servico.solicitar_login(dados)
        self.assertTrue(inicio.wait(3))
        with self.assertRaises(SessaoOcupada):
            servico.solicitar(pedido())
        liberar.set()
        esperar(lambda: not servico.ocupado)
        self.assertEqual(self.repo.listar(), [])
        self.assertEqual(dados.senha_onvio, "")
        self.assertNotIn("PRIVADO", json.dumps(servico.estado_login()))

    def test_reiniciar_aguarda_checkpoint_e_nao_repete_tarefa(self):
        from app.controle_execucao import ponto_seguro
        inicio, liberar = threading.Event(), threading.Event()
        def executar(dados, receber):
            inicio.set()
            liberar.wait(3)
            ponto_seguro()
            raise AssertionError("Não pode continuar depois do reinício.")
        login = Mock()
        login.executar.side_effect = lambda dados, sessao: sessao.fase("tela_principal_confirmada")
        servico = ServicoExecucao(self.repo, executar, "simulacao", login=login)
        servico.iniciar()
        self.addCleanup(servico.encerrar)
        self.addCleanup(liberar.set)
        tarefa = servico.solicitar(pedido())
        self.assertTrue(inicio.wait(3))
        servico.solicitar_login(CredenciaisLogin("teste@example.invalid", "PRIVADO", "GERENTE", "PRIVADO"), reiniciar=True)
        login.reiniciar.assert_not_called()
        liberar.set()
        final = aguardar(self.repo, tarefa["id"])
        self.assertEqual(final["motivo"], "reinicio_solicitado")
        esperar(lambda: not servico.ocupado)
        login.reiniciar.assert_called_once()
        login.executar.assert_called_once()
