"""Correções apontadas pela revisão adversarial das otimizações (21/10/2026)."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from app import arquivos, interacao, livros_conjuntos as livros, otimizacoes
from app.trava_execucao import TravaExecucao
from scripts.atualizar_projeto import AtualizacaoRecusada
from scripts.voltar_versao import voltar

CNPJ_A, CNPJ_B = '12.345.678/0001-95', '98.765.432/0001-10'
INICIO, FIM = '01/08/2026', '31/08/2026'


def cabecalho(cnpj):
    return ('R E G I S T R O  D E  S A I D A S\nEMPRESA: X LTDA\nINSC.EST.: 1  CNPJ: ' + cnpj +
            '\nMES OU PERIODO/ANO: ' + INICIO + ' a ' + FIM + '\nDOCUMENTOS FISCAIS CODIFICACAO\n')


class TestCnpjDivergenteTemVeto(unittest.TestCase):
    def test_layout_com_outro_cnpj_nao_e_salvo_pela_segunda_leitura(self):
        textos = [cabecalho(CNPJ_B), cabecalho(CNPJ_A)]  # layout (B) e plain (A)
        with self.assertRaises(ValueError) as erro:
            arquivos.validar_livro_dos_textos(textos, 'registro_saidas', INICIO, FIM, '12345678000195')
        self.assertIn('CNPJ do PDF não corresponde', str(erro.exception))

    def test_falha_de_titulo_no_layout_ainda_pode_ser_salva_pela_segunda_leitura(self):
        textos = ['texto sem titulo', cabecalho(CNPJ_A)]
        self.assertEqual(arquivos.validar_livro_dos_textos(textos, 'registro_saidas', INICIO, FIM, '12345678000195'),
                         '12345678000195')


class TestLogDaConferenciaNaoInfluencia(unittest.TestCase):
    def test_print_que_falha_nao_derruba_nem_muda_a_classificacao(self):
        with patch('builtins.print', side_effect=UnicodeEncodeError('cp437', 'x', 0, 1, 'sem mapa')):
            livros._registrar_conferencia({'arquivo': 'SAÍDA.pdf', 'tipos': []})  # nao levanta

    def test_log_sai_em_ascii(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            livros._registrar_conferencia({'arquivo': '082026 LIVRO DE SAÍDA.pdf'})
        self.assertTrue(saida.getvalue().isascii())
        self.assertIn('SA\\u00cdDA', saida.getvalue())


class TestInterruptoresMaisRobustos(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.arquivo = Path(pasta.name) / 'otimizacoes.json'
        for alvo, valor in (('ARQUIVO', self.arquivo), ('_forcado', None)):
            patcher = patch.object(otimizacoes, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        otimizacoes.restaurar_para_testes()
        otimizacoes._forcado = None
        self.addCleanup(otimizacoes.restaurar_para_testes)

    def test_json_com_bom_do_bloco_de_notas_e_lido(self):
        self.arquivo.write_bytes(b'\xef\xbb\xbf' + json.dumps({'ocr_paralelo': False}).encode('utf-8'))
        estado = otimizacoes.estado()
        self.assertFalse(estado['ocr_paralelo'])
        self.assertTrue(all(v for k, v in estado.items() if k != 'ocr_paralelo'))

    def test_variavel_de_ambiente_so_nao_liga_o_seguro_com_valor_de_negacao(self):
        for valor in ('1', 'true', 'sim', 'on', 's', 'ligado'):
            with self.subTest(valor=valor), patch.dict(os.environ, {'DOMINIO_MODO_SEGURO': valor}):
                self.assertFalse(any(otimizacoes.estado().values()))
        for valor in ('', '0', 'false', 'nao', 'no', 'off'):
            with self.subTest(valor=valor), patch.dict(os.environ, {'DOMINIO_MODO_SEGURO': valor}):
                self.assertTrue(all(otimizacoes.estado().values()))

    def test_rapido_apaga_tambem_os_desligamentos_individuais(self):
        from scripts import modo_otimizacoes
        modo_otimizacoes.definir('ocr_paralelo', False)
        modo_otimizacoes.modo_seguro(True)
        modo_otimizacoes.modo_seguro(False)
        self.assertFalse(self.arquivo.exists())
        self.assertTrue(all(otimizacoes.estado().values()))


@unittest.skipUnless(shutil.which('git'), 'Git nao instalado')
class TestVoltarVersaoSeguranca(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.repo = Path(temporario.name) / 'inst'
        self.repo.mkdir()
        ambiente = dict(os.environ, GIT_AUTHOR_NAME='T', GIT_AUTHOR_EMAIL='t@e.invalid',
                        GIT_COMMITTER_NAME='T', GIT_COMMITTER_EMAIL='t@e.invalid',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        remendo = patch.dict(os.environ, ambiente)
        remendo.start()
        self.addCleanup(remendo.stop)
        self.git('init', '--initial-branch=main')
        (self.repo / 'a.txt').write_text('1', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-m', 'um')
        self.git('tag', '-a', 'estavel-x', '-m', 'estavel')
        (self.repo / 'a.txt').write_text('2', encoding='utf-8')
        self.git('commit', '-am', 'dois')

    def git(self, *args):
        r = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_recusa_enquanto_o_servidor_ou_a_rotina_seguram_a_trava(self):
        trava = TravaExecucao(self.repo / 'data' / 'sessao_executor.lock')
        trava.adquirir()
        self.addCleanup(trava.liberar)
        with self.assertRaises(AtualizacaoRecusada) as erro, contextlib.redirect_stdout(io.StringIO()):
            voltar(self.repo, 'estavel-x')
        self.assertIn('Pare o servidor', str(erro.exception))
        self.assertEqual((self.repo / 'a.txt').read_text(encoding='utf-8'), '2')  # nada foi trocado

    def test_trava_e_liberada_depois_de_voltar(self):
        with contextlib.redirect_stdout(io.StringIO()):
            voltar(self.repo, 'estavel-x')
        trava = TravaExecucao(self.repo / 'data' / 'sessao_executor.lock')
        trava.adquirir()  # nao levanta: foi liberada
        trava.liberar()

    def test_head_destacado_com_commit_fora_de_branch_e_recusado(self):
        self.git('checkout', '--detach')
        (self.repo / 'a.txt').write_text('3', encoding='utf-8')
        self.git('commit', '-am', 'solto')
        with self.assertRaises(AtualizacaoRecusada) as erro, contextlib.redirect_stdout(io.StringIO()):
            voltar(self.repo, 'estavel-x')
        self.assertIn('HEAD destacado', str(erro.exception))


class TestPerguntaDeGuiasDoAcrobat(unittest.TestCase):
    @staticmethod
    def dados(linhas):
        d = {'text': [], 'left': [], 'top': [], 'width': [], 'height': []}
        for y, palavras in linhas:
            x = 100
            for p in palavras.split():
                d['text'].append(p)
                d['left'].append(x)
                d['top'].append(y)
                d['width'].append(60)
                d['height'].append(20)
                x += 70
        return d

    def test_so_o_botao_com_vizinho_fechar_a_guia_atual_conta(self):
        pergunta = (10, 'Deseja fechar todas as guias ou a guia atual?')
        so_caixa = self.dados([pergunta, (60, 'fechar todas as guias')])  # OCR perdeu o "Sempre"
        self.assertIsNone(interacao._posicao_fechar_todas_as_guias(so_caixa, 1))
        com_botao = self.dados([pergunta, (60, 'fechar todas as guias'),
                                (100, 'Fechar todas as guias Fechar a guia atual Cancelar')])
        self.assertEqual(interacao._posicao_fechar_todas_as_guias(com_botao, 1)[1], 110)

    def preparar(self, antes, depois):
        imagens = iter([antes, depois])
        fake_tela = Mock()
        fake_tela.capturar_tela.side_effect = lambda: next(imagens)
        fake_tela.LIMITE_TESSERACT = 8
        return fake_tela

    def executar(self, antes, depois):
        fake_tela = self.preparar(antes, depois)
        clique = Mock()
        with patch.dict('sys.modules', {'pytesseract': Mock(image_to_data=Mock(return_value=object()),
                                                            Output=Mock(DICT='dict'))}), \
                patch('app.tela.capturar_tela', fake_tela.capturar_tela), \
                patch('app.tela._preparar_para_ocr', return_value='x'), \
                patch.object(interacao, '_posicao_fechar_todas_as_guias', return_value=(300, 200)), \
                patch.object(interacao, 'ponto_seguro_sem_foco'), \
                patch.object(interacao.pyautogui, 'moveTo'), patch.object(interacao.pyautogui, 'click', clique):
            interacao._ultimo_clique_guias = -10.0
            resultado = interacao.fechar_pergunta_de_guias_do_acrobat()
        return resultado, clique

    def test_clica_se_o_recorte_continua_igual_e_nao_clica_se_a_tela_mudou(self):
        igual = Image.new('RGB', (800, 600), 'white')
        resultado, clique = self.executar(igual, igual.copy())
        self.assertTrue(resultado)
        clique.assert_called_once_with(300, 200)
        mudada = igual.copy()
        mudada.paste('black', (250, 190, 350, 210))
        resultado, clique = self.executar(igual, mudada)
        self.assertFalse(resultado)
        clique.assert_not_called()

    def test_nao_clica_duas_vezes_em_menos_de_tres_segundos(self):
        igual = Image.new('RGB', (800, 600), 'white')
        fake_tela = self.preparar(igual, igual.copy())
        with patch.dict('sys.modules', {'pytesseract': Mock(image_to_data=Mock(return_value=object()),
                                                            Output=Mock(DICT='dict'))}), \
                patch('app.tela.capturar_tela', side_effect=[igual, igual.copy(), igual, igual.copy()]), \
                patch('app.tela._preparar_para_ocr', return_value='x'), \
                patch.object(interacao, '_posicao_fechar_todas_as_guias', return_value=(300, 200)), \
                patch.object(interacao, 'ponto_seguro_sem_foco'), \
                patch.object(interacao.pyautogui, 'moveTo'), \
                patch.object(interacao.pyautogui, 'click') as clique:
            interacao._ultimo_clique_guias = -10.0
            self.assertTrue(interacao.fechar_pergunta_de_guias_do_acrobat())
            self.assertFalse(interacao.fechar_pergunta_de_guias_do_acrobat())
        self.assertEqual(clique.call_count, 1)


if __name__ == '__main__':
    unittest.main()
