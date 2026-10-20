"""Integração do foco com captura sintética; percepção do vazio usa CV real."""
import contextlib
import io
import unittest
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw

from app import foco_seletor as foco, seletor_pasta as seletor
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao


def quadro_unidade(texto='lient C (M:N)', azul=True, obstruido=False, aviso=False):
    imagem = Image.new('RGB', (640, 420), '#eeeeee')
    d = ImageDraw.Draw(imagem)
    combo = (100, 50, 470, 20)
    arvore = (30, 90, 540, 240)
    d.rectangle((100, 50, 569, 69), fill='white', outline='black')
    if azul:
        d.rectangle((103, 52, 230, 67), fill='#0078d7')
    d.text((112, 54), texto, fill='white' if azul else 'black')
    d.rectangle((30, 90, 569, 329), fill='white', outline='black')
    d.rectangle((550, 91, 568, 328), fill='#cccccc')
    for y in range(100, 300, 18):
        d.text((70, y), 'Pasta', fill='black')
    if obstruido:
        d.rectangle((31, 91, 549, 328), fill='#cccccc')
    palavras = [{'texto': texto, 'x': 112, 'y': 54, 'w': 110, 'h': 12}]
    if aviso:
        palavras.append({'texto': 'Aviso', 'x': 200, 'y': 140, 'w': 50, 'h': 12})
    detalhes = {'combo': combo, 'arvore': arvore, 'lista': None, 'palavras': palavras}
    imagem.info['detalhes'] = detalhes
    return imagem


class TestFocoNaEspera(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(seletor.time, 'sleep'))
        self.stack.enter_context(patch.object(seletor._LeitorDialogo, 'ler',
            side_effect=lambda imagem: imagem.info['detalhes']))
        self.stack.enter_context(patch.object(seletor, '_completar_dialogo', side_effect=lambda d: d))

    def esperar(self, capturar, clicar):
        return seletor._aguardar_estado_unidade(capturar, aberta=False,
            fase='fechar_unidade', letra_aplicada='M', clicar_foco=clicar)

    def percurso_foco(self, depois):
        antes = quadro_unidade()
        estado = {'clicou': False, 'capturas': 0, 'capturas_no_clique': None}
        def capturar():
            estado['capturas'] += 1
            return depois if estado['clicou'] else antes
        def clicar(x, y):
            candidato = foco.localizar_vazio(antes, antes.info['detalhes'])
            self.assertTrue(foco.confirmar_vazio(antes, antes.info['detalhes'], candidato))
            self.assertEqual((x, y), candidato['posicao'])
            estado['clicou'] = True
            estado['capturas_no_clique'] = estado['capturas']
        return capturar, Mock(side_effect=clicar), estado

    def test_dois_quadros_antes_um_clique_cv_e_duas_leituras_m_sem_realce(self):
        capturar, clicar, estado = self.percurso_foco(quadro_unidade('Client C (M:)', azul=False))
        _, detalhes = self.esperar(capturar, clicar)
        self.assertTrue(seletor._drive_selecionado(detalhes, 'M'))
        clicar.assert_called_once()
        self.assertEqual(estado['capturas_no_clique'], 2)
        self.assertEqual(estado['capturas'], 4)

    def test_clique_que_nao_remove_realce_nao_e_repetido(self):
        capturar, clicar, _ = self.percurso_foco(quadro_unidade('Client C (M:)', azul=True))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.esperar(capturar, clicar)
        clicar.assert_called_once()

    def test_blur_com_client_z_nao_confirma_o_destino_m(self):
        capturar, clicar, _ = self.percurso_foco(quadro_unidade('Client Z (M:)', azul=False))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.esperar(capturar, clicar)
        clicar.assert_called_once()

    def test_blur_com_leitura_malformada_nao_e_repetido_nem_confirmado(self):
        capturar, clicar, _ = self.percurso_foco(quadro_unidade(azul=False))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.esperar(capturar, clicar)
        clicar.assert_called_once()

    def test_dialogo_perdido_apos_foco_nao_repete_clique(self):
        antes = quadro_unidade()
        estado = {'clicou': False}
        def ler(imagem):
            if estado['clicou']:
                raise ValueError('dialogo_sintetico_nao_reconhecido')
            return imagem.info['detalhes']
        clicar = Mock(side_effect=lambda *args: estado.update(clicou=True))
        with patch.object(seletor._LeitorDialogo, 'ler', side_effect=ler), \
             self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.esperar(lambda: antes, clicar)
        clicar.assert_called_once()

    def test_aviso_impede_clique_de_foco(self):
        imagem = quadro_unidade(aviso=True)
        clicar = Mock()
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.esperar(lambda: imagem, clicar)
        clicar.assert_not_called()

    def test_patch_obstruido_no_segundo_quadro_impede_clique(self):
        antes, depois = quadro_unidade(), quadro_unidade(obstruido=True)
        contagem = [0]
        def capturar():
            contagem[0] += 1
            return antes if contagem[0] == 1 else depois
        clicar = Mock()
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.esperar(capturar, clicar)
        clicar.assert_not_called()

    def test_cancelamento_no_segundo_quadro_impede_clique(self):
        imagem = quadro_unidade()
        controle = ControleExecucao()
        contagem = [0]
        def capturar():
            contagem[0] += 1
            if contagem[0] == 2:
                controle.interromper('teste')
            return imagem
        clicar = Mock()
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.esperar(capturar, clicar)
        clicar.assert_not_called()

    def test_servidor_c_azul_down_unico_confirma_m_sem_abrir_lista(self):
        inicial = quadro_unidade('Servidor (C:)', azul=True)
        aplicada = quadro_unidade('Client C (M:)', azul=False)
        estado = {'down': False}
        tecla = Mock(side_effect=lambda k: estado.update(down=True))
        clicar = Mock()
        imagem, detalhes = seletor._selecionar_unidade(
            lambda: aplicada if estado['down'] else inicial, clicar, tecla, 'M',
            inicial, inicial.info['detalhes'])
        tecla.assert_called_once_with('down')
        clicar.assert_not_called()
        self.assertTrue(seletor._drive_selecionado(detalhes, 'M'))

    def test_client_m_ja_confirmado_nao_envia_down_nem_clique(self):
        imagem = quadro_unidade('Client C (M:)', azul=False)
        capturar, clicar, tecla = Mock(), Mock(), Mock()
        _, detalhes = seletor._selecionar_unidade(capturar, clicar, tecla,
            'M', imagem, imagem.info['detalhes'])
        capturar.assert_not_called(); clicar.assert_not_called(); tecla.assert_not_called()
        self.assertTrue(seletor._drive_selecionado(detalhes, 'M'))


if __name__ == '__main__':
    unittest.main()
