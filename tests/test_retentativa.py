"""Segunda chance da rotina no caminho clássico: só se falhou cedo, uma vez, sem interferência."""
import contextlib
import unittest
from unittest.mock import Mock, patch

from app import executor_servidor, otimizacoes, retentativa
from app.controle_execucao import ExecucaoInterrompida
from test_executor_servidor import TestExecutorServidor


def evento(etapa, status, rotina="livros_fiscais"):
    return {"routine_id": rotina, "step": etapa, "status": status}


class TestDecisao(unittest.TestCase):
    def test_livros_e_resumo_so_antes_do_pdf_ser_aceito(self):
        cedo = [evento("abrir_livros", "confirmado"), evento("preencher_periodo", "falha")]
        self.assertTrue(retentativa.pode_retentar("livros_fiscais", cedo))
        self.assertTrue(retentativa.pode_retentar("resumo_acumulador", cedo))
        exportando = cedo + [evento("exportar_pdf", "falha")]
        self.assertTrue(retentativa.pode_retentar("livros_fiscais", exportando))
        aceito = [evento("conferir_pdf", "confirmado"), evento("encerrar", "falha")]
        self.assertFalse(retentativa.pode_retentar("livros_fiscais", aceito))
        self.assertFalse(retentativa.pode_retentar("resumo_acumulador", aceito))

    def test_efd_nunca_depois_de_iniciar_a_geracao(self):
        antes = [evento("navegar_menu", "confirmado", "efd_contribuicoes"),
                 evento("preencher_periodo", "falha", "efd_contribuicoes")]
        self.assertTrue(retentativa.pode_retentar("efd_contribuicoes", antes))
        gerando = antes + [evento("gerar_documento", "inicio", "efd_contribuicoes")]
        self.assertFalse(retentativa.pode_retentar("efd_contribuicoes", gerando))
        self.assertFalse(retentativa.pode_retentar("sped_fiscal", gerando))

    def test_foco_perdido_ja_retentou_ou_sem_otimizacao_nao_repete(self):
        cedo = [evento("preencher_periodo", "falha")]
        self.assertFalse(retentativa.pode_retentar("livros_fiscais", cedo, foco_perdido=True))
        self.assertFalse(retentativa.pode_retentar("livros_fiscais", cedo, ja_retentou=True))
        self.assertFalse(retentativa.pode_retentar("livros_fiscais", cedo, otimizacoes_ativas=False))

    def test_foi_sucesso_aceita_os_dois_formatos(self):
        self.assertTrue(retentativa.foi_sucesso(True))
        self.assertTrue(retentativa.foi_sucesso((True, [])))
        self.assertFalse(retentativa.foi_sucesso(False))
        self.assertFalse(retentativa.foi_sucesso((False, [])))
        self.assertFalse(retentativa.foi_sucesso(None))


class TestModoSeguroTemporario(unittest.TestCase):
    def test_desliga_tudo_so_dentro_do_bloco_e_aninha(self):
        with patch.object(otimizacoes, "_forcado", True):
            self.assertTrue(otimizacoes.ativa("ocr_paralelo"))
        otimizacoes._forcado = None
        try:
            with patch.object(otimizacoes, "ARQUIVO", otimizacoes.ARQUIVO.with_name("inexistente.json")):
                self.assertTrue(otimizacoes.ativa("ocr_paralelo"))
                with otimizacoes.modo_seguro_temporario():
                    self.assertFalse(any(otimizacoes.estado().values()))
                    with otimizacoes.modo_seguro_temporario():
                        self.assertFalse(otimizacoes.ativa("ocr_paralelo"))
                    self.assertFalse(otimizacoes.ativa("ocr_paralelo"))
                self.assertTrue(otimizacoes.ativa("ocr_paralelo"))
        finally:
            otimizacoes.restaurar_para_testes()

    def test_excecao_dentro_do_bloco_nao_deixa_o_modo_seguro_preso(self):
        with patch.object(otimizacoes, "ARQUIVO", otimizacoes.ARQUIVO.with_name("inexistente.json")):
            otimizacoes._forcado = None
            try:
                with self.assertRaises(RuntimeError):
                    with otimizacoes.modo_seguro_temporario():
                        raise RuntimeError("x")
                self.assertTrue(otimizacoes.ativa("ocr_paralelo"))
            finally:
                otimizacoes.restaurar_para_testes()


class TestRetentativaNoExecutor(unittest.TestCase):
    executar = TestExecutorServidor.executar

    def setUp(self):
        TestExecutorServidor.setUp(self)
        self.callbacks = []
        self.desktop["estados"].observar_eventos = self.observar
        patcher = patch.object(otimizacoes, "_forcado", True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.volta = patch.object(executor_servidor.ExecutorDominio, "_voltar_ao_inicio", return_value=True)
        self.volta.start()
        self.addCleanup(self.volta.stop)
        self.livros = self.desktop["dominio"].gerar_livros_fiscais
        self.dados["capacidade"] = "livros_fiscais"

    @contextlib.contextmanager
    def observar(self, callback):
        self.callbacks.append(callback)
        yield

    def emitir(self, *eventos):
        for e in eventos:
            self.callbacks[-1](e)

    def test_falha_cedo_repete_uma_vez_sem_otimizacoes_e_devolve_o_sucesso(self):
        estados = []

        def gerar(*args, **kwargs):
            estados.append(otimizacoes.ativa("ocr_paralelo"))
            if len(estados) == 1:
                self.emitir(evento("preencher_periodo", "falha"))
                return False, []
            return True, [{"tipo": "registro_icms"}]
        self.livros.side_effect = gerar
        resultado = self.executar(lote=True)
        self.assertEqual(resultado, (True, [{"tipo": "registro_icms"}]))
        self.assertEqual(estados, [True, False])  # 2a vez no caminho classico
        self.assertTrue(otimizacoes.ativa("ocr_paralelo"))  # e volta ao normal depois

    def test_excecao_inesperada_cedo_tambem_repete(self):
        chamadas = []

        def gerar(*args, **kwargs):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise NameError("otimizacao com defeito")
            return True, []
        self.livros.side_effect = gerar
        self.assertEqual(self.executar(lote=True), (True, []))
        self.assertEqual(len(chamadas), 2)

    def test_pdf_ja_aceito_nao_repete_nem_gera_duas_vezes(self):
        def gerar(*args, **kwargs):
            self.emitir(evento("conferir_pdf", "confirmado"), evento("encerrar", "falha"))
            return False, []
        self.livros.side_effect = gerar
        self.assertEqual(self.executar(lote=True), (False, []))
        self.assertEqual(self.livros.call_count, 1)

    def test_efd_depois_de_gerar_nao_repete(self):
        self.dados["capacidade"] = "efd_contribuicoes"
        efd = self.desktop["dominio"].gerar_efd_contribuicoes

        def gerar(*args, **kwargs):
            self.emitir(evento("gerar_documento", "inicio", "efd_contribuicoes"))
            return False
        efd.side_effect = gerar
        self.assertFalse(self.executar(lote=True))
        self.assertEqual(efd.call_count, 1)

    def test_so_repete_uma_vez_mesmo_se_a_segunda_tambem_falhar(self):
        self.livros.side_effect = lambda *a, **k: (False, [])
        self.assertEqual(self.executar(lote=True), (False, []))
        self.assertEqual(self.livros.call_count, 2)

    def test_sem_otimizacoes_ligadas_nao_repete(self):
        with patch.object(otimizacoes, "_forcado", False):
            self.livros.side_effect = lambda *a, **k: (False, [])
            self.executar(lote=True)
        self.assertEqual(self.livros.call_count, 1)

    def test_sem_tela_azul_ou_empresa_diferente_devolve_a_falha_original_sem_repetir(self):
        self.livros.side_effect = lambda *a, **k: (False, [])
        self.volta.stop()
        with patch.object(executor_servidor.ExecutorDominio, "_voltar_ao_inicio", return_value=False):
            self.assertEqual(self.executar(lote=True), (False, []))
        self.assertEqual(self.livros.call_count, 1)
        self.volta.start()
        self.livros.reset_mock()
        self.desktop["tela"].ler_empresa_selecionada.side_effect = [("EMPRESA", "52"), ("EMPRESA", "52"), ("OUTRA", "99")]
        self.livros.side_effect = lambda *a, **k: (False, [])
        self.assertEqual(self.executar(lote=True), (False, []))
        self.assertEqual(self.livros.call_count, 1)

    def test_parar_do_operador_nunca_vira_retentativa(self):
        self.livros.side_effect = ExecucaoInterrompida("parado")
        with self.assertRaises(ExecucaoInterrompida):
            self.executar(lote=True)
        self.assertEqual(self.livros.call_count, 1)

    def test_falha_original_sem_retentativa_continua_sendo_levantada(self):
        with patch.object(otimizacoes, "_forcado", False):
            self.livros.side_effect = NameError("defeito")
            with self.assertRaises(NameError):
                self.executar(lote=True)


if __name__ == "__main__":
    unittest.main()
