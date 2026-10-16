"""Unidade literal já aplicada: fixtures sintéticas, sem GUI fiscal."""
import contextlib
import io
import unittest
from unittest.mock import patch
from PIL import ImageDraw

from app import arvore_raiz as raiz, seletor_pasta as seletor, tela
from test_seletor_pasta import DESTINO, FOLHA, quadro
from test_percurso_unidade_barra import PercursoComBarra
from test_unidade_pasta_ocr_nativo import dados_unidade


class UnidadeFechaAposDown(PercursoComBarra):
    def agendar(self, nome, atraso, acao):
        if nome == 'down':
            aplicar = acao
            def acao():
                aplicar()
                self._aplicar_unidade()
                self.combo_aberto = False
                self.foco_combo = False
                self.foco_arvore = True
        super().agendar(nome, atraso, acao)


class UnidadeLiteralRealceOscila(PercursoComBarra):
    def capturar(self):
        imagem = super().capturar()
        if self.combo_aberto and self.indice_combo == 1:
            cor = (255, 255, 255) if self.capturas % 2 else (0, 120, 215)
            imagem.putpixel((120, 140), cor)
        return imagem


class UnidadeFechadaCampoOmitido(UnidadeFechaAposDown):
    def capturar(self):
        imagem = super().capturar()
        if self.drive == 'Client C (M:\\)' and not self.combo_aberto:
            imagem.info['palavras_sinteticas'] = [
                p for p in imagem.info['palavras_sinteticas']
                if not (100 < p['x'] < 481 and 76 < p['y'] < 101)]
        return imagem


class UnidadeLiteralRealceAmbiguo(PercursoComBarra):
    def capturar(self):
        imagem = super().capturar()
        if self.combo_aberto and self.indice_combo == 1:
            ImageDraw.Draw(imagem).rectangle((410, 110, 450, 122), fill='#0078d7')
        return imagem


class UnidadeLiteralListaOscila(PercursoComBarra):
    def capturar(self):
        original = self.combo_aberto
        if self.foco_combo and self.indice_combo == 1:
            self.combo_aberto = bool(self.capturas % 2)
        imagem = super().capturar()
        self.combo_aberto = original
        return imagem


class UnidadeLiteralUmaCaptura(UnidadeFechaAposDown):
    def __init__(self):
        super().__init__()
        self.capturas_m_fechado = 0

    def capturar(self):
        imagem = super().capturar()
        if self.drive == 'Client C (M:\\)' and not self.combo_aberto:
            self.capturas_m_fechado += 1
            if self.capturas_m_fechado > 1:
                desenho = ImageDraw.Draw(imagem)
                desenho.rectangle((101, 77, 479, 99), fill='white')
                desenho.text((108, 81), 'Servidor (C:\\)', fill='black')
                _, palavras = quadro(drive='Servidor (C:\\)', pastas=())
                dentro = lambda p: 100 < p['x'] < 481 and 76 < p['y'] < 101
                imagem.info['palavras_sinteticas'] = [
                    p for p in imagem.info['palavras_sinteticas'] if not dentro(p)] + [
                    p for p in palavras if dentro(p)]
        return imagem


class TestUnidadeAplicada(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(seletor.time, 'sleep'))
        self.stack.enter_context(patch.object(seletor, '_palavras',
            side_effect=lambda imagem: imagem.info['palavras_sinteticas']))
        self.stack.enter_context(patch.object(raiz, 'localizar_raiz', side_effect=self.users_visivel))

    @staticmethod
    def users_visivel(imagem, detalhes, nome, coluna, altura):
        alvos = [n for n in seletor._nos(detalhes)
                 if n['nome'] == 'users' and abs(n['x'] - coluna) <= 2]
        return dict(alvos[0], tolerancia=4.8) if len(alvos) == 1 else None

    def executar(self, arvore):
        return seletor.selecionar_pasta(DESTINO, arvore.capturar, arvore.clicar, arvore.tecla)

    def assert_destino_e_barra(self, arvore):
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(len(arvore.cliques_barra), 1)
        self.assertEqual(arvore.cliques_barra[0][0], 'Client C (M:\\)')
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])

    def test_down_aplica_m_e_fecha_lista_sem_enviar_tab_extra(self):
        arvore = UnidadeFechaAposDown()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down'])
        self.assert_destino_e_barra(arvore)

    def test_campo_m_fechado_omitido_no_global_e_recuperado_por_duas_leituras_nativas(self):
        arvore = UnidadeFechadaCampoOmitido()
        vazio = {k: [] for k in ('text', 'left', 'top', 'width', 'height')}
        with patch.object(tela, 'ler_dados_ocr_linha_rotulo', return_value=vazio) as tesseract, \
             patch.object(tela, 'ler_dados_ocr_windows',
                side_effect=lambda imagem, escala: dados_unidade('Client C (M:)', escala)) as nativo:
            self.assertTrue(self.executar(arvore))
        self.assertGreaterEqual(tesseract.call_count, 4)
        self.assertGreaterEqual(nativo.call_count, 2)
        self.assertEqual([c.kwargs['escala'] for c in nativo.call_args_list[:2]], [4, 6])
        self.assertTrue(all(c.args[0].size == (354, 21) for c in nativo.call_args_list))
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down'])
        self.assert_destino_e_barra(arvore)

    def test_m_literal_aberto_com_realce_oscilando_confirma_e_fecha_com_tab_unico(self):
        arvore = UnidadeLiteralRealceOscila()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])
        self.assert_destino_e_barra(arvore)

    def test_campo_m_literal_dispensa_realce_ambiguo_do_popup(self):
        sonda = UnidadeLiteralRealceAmbiguo()
        sonda.indice_combo = 1
        sonda.foco_combo = True
        sonda.combo_aberto = True
        imagem = sonda.capturar()
        detalhes = seletor.medir_dialogo(imagem, somente_unidade=True)
        self.assertTrue(seletor._drive_selecionado(detalhes, 'M'))
        with self.assertRaisesRegex(seletor.SeletorPastaNaoConfirmado, 'Realce da unidade ambíguo'):
            seletor._realce_unidade(imagem, detalhes)
        arvore = UnidadeLiteralRealceAmbiguo()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])
        self.assert_destino_e_barra(arvore)

    def test_client_z_com_letra_m_nao_libera_barra_ou_ok(self):
        arvore = UnidadeLiteralRealceOscila(unidades=('Servidor (C:\\)', 'Client Z (M:\\)'))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_barra, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_client_c_com_letra_q_nao_libera_barra_ou_ok_do_destino_m(self):
        arvore = UnidadeLiteralRealceOscila(unidades=('Servidor (C:\\)', 'Client C (Q:\\)'))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_barra, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_literal_m_com_lista_aberta_fechada_alternando_nao_tem_duas_confirmacoes(self):
        arvore = UnidadeLiteralListaOscila()
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_barra, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_m_literal_fechado_em_um_unico_quadro_nao_autoriza_barra_nem_ok(self):
        arvore = UnidadeLiteralUmaCaptura()
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertGreater(arvore.capturas_m_fechado, 1)
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down'])
        self.assertEqual(arvore.cliques_barra, [])
        self.assertEqual(arvore.cliques_ok, [])


if __name__ == '__main__':
    unittest.main()
