"""Barra e raiz em pixels sintéticos; nunca opera o desktop do Domínio."""
import contextlib
import io
import unittest
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw
from app import arvore_raiz as raiz, seletor_pasta as seletor
from app.controle_execucao import (ControleExecucao, ExecucaoInterrompida,
                                  controlar_execucao, verificar_antes_de_agir)


def figura(escura=False, trilho=True, seta='baixo', fator=1):
    imagem = Image.new('RGB', (340, 320), 'white')
    d = ImageDraw.Draw(imagem)
    arvore = (30, 60, 250, 220)
    d.rectangle((30, 60, 279, 279), outline='black')
    if trilho:
        d.rectangle((260, 61, 278, 278), fill='#eeeeee', outline='#808080')
    d.rectangle((260, 260, 278, 278), fill='#444444' if escura else '#eeeeee', outline='#808080')
    if seta in ('baixo', 'vbaixo'):
        pontos = ((265, 267), (273, 267), (269, 272))
    elif seta in ('cima', 'vcima'):
        pontos = ((265, 272), (273, 272), (269, 267))
    else:
        pontos = ()
    if pontos:
        cor = 'white' if escura else 'black'
        if seta.startswith('v'):
            d.line((pontos[0], pontos[2], pontos[1]), fill=cor, width=2)
        else:
            d.polygon(pontos, fill=cor)
    if fator != 1:
        imagem = imagem.resize((imagem.width*fator, imagem.height*fator), Image.Resampling.NEAREST)
        arvore = tuple(v*fator for v in arvore)
    return imagem, arvore


class TestMedirBarra(unittest.TestCase):
    def test_triangulo_e_trilho_medidos_nas_duas_polaridades_e_escalas(self):
        for escura in (False, True):
            for fator in (1, 2):
                with self.subTest(escura=escura, fator=fator):
                    imagem, arvore = figura(escura=escura, fator=fator)
                    barra = raiz.medir_seta_baixo(imagem, arvore, 12*fator)
                    self.assertIsNotNone(barra)
                    self.assertTrue(260*fator < barra['posicao'][0] < 279*fator)
                    self.assertTrue(260*fator < barra['posicao'][1] < 279*fator)

    def test_chevron_v_para_baixo_exige_os_dois_bracos_e_trilho(self):
        for escura in (False, True):
            for fator in (1, 2):
                with self.subTest(escura=escura, fator=fator):
                    imagem, arvore = figura(escura=escura, seta='vbaixo', fator=fator)
                    self.assertIsNotNone(raiz.medir_seta_baixo(imagem, arvore, 12*fator))
        imagem, arvore = figura(escura=True, seta='vcima')
        self.assertIsNone(raiz.medir_seta_baixo(imagem, arvore, 12))

    def test_sem_trilho_sem_seta_ou_sentido_errado_recusa(self):
        for opcoes in ({'trilho': False}, {'seta': 'nenhuma'}, {'seta': 'cima'}):
            with self.subTest(opcoes=opcoes):
                imagem, arvore = figura(**opcoes)
                self.assertIsNone(raiz.medir_seta_baixo(imagem, arvore, 12))


class TestRecorteRaiz(unittest.TestCase):
    def test_duas_opinioes_localizam_users_literal_com_variacao_pequena_da_fonte(self):
        imagem, arvore = figura()
        dados = {'text': ['Users'], 'left': [(73-30)*4], 'top': [(150-60)*4],
                 'width': [35*4], 'height': [12*4]}
        with patch.object(raiz.tela, 'ler_dados_ocr_formulario', return_value=dados), \
             patch.object(raiz.tela, 'ler_dados_ocr_windows', return_value=None):
            alvo = raiz.localizar_raiz(imagem, {'arvore': arvore}, 'Users', 70, 12)
        self.assertEqual(alvo['nome'], 'users')
        self.assertEqual(alvo['x'], 73)

    def test_homonimo_descendente_ou_duas_raizes_nao_autorizam_alvo(self):
        imagem, arvore = figura()
        for xs, ys in (([88], [150]), ([70, 70], [150, 180])):
            dados = {'text': ['Users']*len(xs), 'left': [(x-30)*4 for x in xs],
                     'top': [(y-60)*4 for y in ys], 'width': [35*4]*len(xs), 'height': [12*4]*len(xs)}
            with self.subTest(xs=xs), patch.object(raiz.tela, 'ler_dados_ocr_formulario', return_value=dados), \
                 patch.object(raiz.tela, 'ler_dados_ocr_windows', return_value=None):
                self.assertIsNone(raiz.localizar_raiz(imagem, {'arvore': arvore}, 'Users', 70, 12))


class TestRecuperarRaiz(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(seletor.time, 'sleep'))
        self.imagem, arvore = figura()
        self.detalhes = {'arvore': arvore, 'palavras': [], 'combo': (30, 20, 250, 25)}
        self.no = {'nome': 'mit', 'x': 70, 'y': 100, 'linha': [{'h': 12}]}
        self.alvo = {'nome': 'users', 'x': 73, 'y': 150, 'posicao': (90, 156),
                     'linha': [{'h': 12}], 'tolerancia': 4.8}
        self.selecionado = dict(self.alvo)
        self.stack.enter_context(patch.object(seletor, 'medir_dialogo', return_value=self.detalhes))
        self.drive = self.stack.enter_context(patch.object(seletor, '_drive_selecionado', return_value=True))
        self.stack.enter_context(patch.object(seletor, '_no_selecionado', return_value=self.no))
        self.localizar = self.stack.enter_context(patch.object(raiz, 'localizar_raiz', return_value=None))
        self.ata = self.stack.enter_context(patch.object(seletor, '_ler_selecao',
            return_value=(self.imagem, self.detalhes, self.selecionado)))
        self.clicar = Mock()

    def executar(self, capturar=None, limite=8):
        return seletor._recuperar_raiz_sem_avanco(capturar or (lambda: self.imagem), self.clicar,
            'M', (self.imagem, self.detalhes, self.no), 'Users', max_rolagens=limite)

    def test_users_local_visivel_nao_precisa_rolar(self):
        self.localizar.return_value = self.alvo
        self.assertEqual(self.executar()[2]['nome'], 'users')
        self.clicar.assert_called_once_with(90, 156)

    def test_barra_clica_uma_vez_espera_mudanca_e_so_entao_seleciona_users(self):
        depois = self.imagem.copy(); depois.putpixel((80, 180), (0, 0, 0))
        estado = {'rolou': False}
        self.localizar.side_effect = lambda imagem, *args: self.alvo if imagem is depois else None
        def clicar(x, y):
            if y > 250:estado['rolou'] = True
        self.clicar.side_effect = clicar
        self.assertEqual(self.executar(lambda: depois if estado['rolou'] else self.imagem)[2]['nome'], 'users')
        self.assertEqual(self.clicar.call_count, 2)
        self.assertTrue(self.clicar.call_args_list[0].args[1] > 250)
        self.assertEqual(self.clicar.call_args_list[1].args, (90, 156))

    def test_barra_sem_mudanca_nao_repete_clique(self):
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar()
        self.clicar.assert_called_once()
        self.ata.assert_not_called()

    def test_sem_seta_medida_nao_clica(self):
        self.imagem, _ = figura(seta='cima')
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar()
        self.clicar.assert_not_called()

    def test_unidade_mudou_nao_clica(self):
        self.drive.return_value = False
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar()
        self.clicar.assert_not_called()

    def test_unidade_muda_durante_ocr_nao_clica_no_alvo_antigo(self):
        def localizar(*args):
            self.drive.return_value = False
            return self.alvo
        self.localizar.side_effect = localizar
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar()
        self.clicar.assert_not_called()

    def test_perda_de_foco_apos_medir_seta_bloqueia_acao(self):
        medir = raiz.medir_seta_baixo
        foco = [True]
        def verificar():
            if not foco[0]:raise RuntimeError('foco_nao_confirmado')
        def perder_foco(*args):
            barra = medir(*args)
            foco[0] = False
            return barra
        with verificar_antes_de_agir(verificar), \
             patch.object(raiz, 'medir_seta_baixo', side_effect=perder_foco), \
             self.assertRaisesRegex(RuntimeError, 'foco_nao_confirmado'):
            self.executar()
        self.clicar.assert_not_called()

    def test_rolagem_de_recuperacao_nao_e_usada_em_descendentes_ou_outro_destino(self):
        erro = seletor.SeletorPastaNaoConfirmado('sem_avanco')
        for nivel, nome in ((1, 'Users'), (0, 'Outra')):
            with self.subTest(nivel=nivel, nome=nome), \
                 patch.object(seletor, '_selecionar_visivel', return_value=None), \
                 patch.object(seletor, '_avancar_irmao', side_effect=erro), \
                 patch.object(seletor, '_recuperar_raiz_sem_avanco') as recuperar, \
                 self.assertRaises(seletor.SeletorPastaNaoConfirmado):
                seletor._buscar_irmao(lambda: self.imagem, Mock(), 'M',
                    (self.imagem, self.detalhes, self.no), nome, nivel, clicar=self.clicar)
            recuperar.assert_not_called()

    def test_limite_de_rolagem_nao_vira_busca_indefinida(self):
        quadros = [self.imagem.copy() for _ in range(4)]
        for i, quadro in enumerate(quadros):quadro.putpixel((80, 180), (i, i, i))
        indice = [0]
        self.clicar.side_effect = lambda *args: indice.__setitem__(0, indice[0]+1)
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(lambda: quadros[indice[0]], limite=2)
        self.assertEqual(self.clicar.call_count, 2)

    def test_cancelamento_depois_da_medicao_impede_clique(self):
        controle = ControleExecucao()
        medir = raiz.medir_seta_baixo
        def cancelar(*args):
            barra = medir(*args)
            controle.interromper('teste')
            return barra
        with patch.object(raiz, 'medir_seta_baixo', side_effect=cancelar), \
             controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar()
        self.clicar.assert_not_called()


if __name__ == '__main__':unittest.main()
