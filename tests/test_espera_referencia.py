"""Espera por estado: sem OCR enquanto a tela é a de antes da ação; leitura ao estabilizar."""
import itertools
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from app import estados


def tela(cor):
    return Image.new("RGB", (40, 30), cor)


class TestEsperaComReferencia(unittest.TestCase):
    def esperar(self, capturas, detector, **opcoes):
        sequencia = iter(capturas)
        relogio = itertools.count(0, 1)  # cada leitura do relogio = 1 s
        with patch.object(estados.tela, "capturar_tela", side_effect=lambda: next(sequencia)), \
                patch.object(estados.time, "sleep"), \
                patch.object(estados.time, "monotonic", side_effect=lambda: next(relogio)):
            return estados.esperar_por_estado([("alvo", detector)], espera_minima=0, intervalo=1, **opcoes)

    def test_nao_le_enquanto_a_tela_e_a_de_antes_do_clique_e_le_so_ao_estabilizar(self):
        antes, transicao, final = tela("red"), tela("yellow"), tela("blue")
        detector = Mock(return_value=(5, 6))
        # antes, antes, antes (nada mudou), transição (instável), final, final (estável) -> lê 1 vez
        capturas = [antes, antes, antes, transicao, final, final, final]
        imagem, estado, pos = self.esperar(capturas, detector, referencia_inicial=antes,
                                           aguardar_estabilidade=True, tentativas=5, limite_segundos=100)
        self.assertEqual((estado, pos), ("alvo", (5, 6)))
        detector.assert_called_once()
        self.assertEqual(imagem.getpixel((0, 0)), (0, 0, 255))  # leu a tela FINAL, não a de transição

    def test_sem_estabilidade_le_assim_que_a_tela_muda(self):
        antes, depois = tela("red"), tela("blue")
        detector = Mock(return_value=(1, 1))
        imagem, estado, _ = self.esperar([antes, antes, depois], detector, referencia_inicial=antes,
                                         tentativas=5, limite_segundos=100)
        self.assertEqual(estado, "alvo")
        self.assertEqual(imagem.getpixel((0, 0)), (0, 0, 255))
        detector.assert_called_once()

    def test_tela_que_nunca_muda_nao_roda_ocr_e_termina_pelo_prazo(self):
        antes = tela("red")
        detector = Mock(return_value=None)
        resultado = self.esperar(itertools.repeat(antes), detector, referencia_inicial=antes,
                                 aguardar_estabilidade=True, tentativas=3, limite_segundos=8)
        self.assertEqual(resultado, (None, None, None))
        detector.assert_not_called()

    def test_animacao_continua_nao_trava_a_leitura(self):
        antes = tela("red")
        cores = itertools.cycle(("yellow", "green", "blue", "white", "black", "gray"))
        detector = Mock(return_value=None)
        # Tela sempre diferente (spinner): após 4 capturas instáveis lê mesmo assim.
        self.esperar((tela(c) for c in itertools.chain([ "red" ], cores)), detector, referencia_inicial=antes,
                     aguardar_estabilidade=True, tentativas=1, limite_segundos=100)
        self.assertGreaterEqual(detector.call_count, 1)

    def test_sem_as_novas_opcoes_o_comportamento_e_o_de_sempre(self):
        antes = tela("red")
        detector = Mock(return_value=(2, 2))
        imagem, estado, _ = self.esperar([antes], detector, tentativas=3)
        self.assertEqual(estado, "alvo")
        detector.assert_called_once()


if __name__ == "__main__":
    unittest.main()
