"""Fechar literal da EFD em capturas sintéticas, sem backend Windows."""
import contextlib
import importlib.util
import io
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao


class TestEncerramentoEFD(unittest.TestCase):
    def setUp(self):
        with patch('ctypes.windll', Mock(), create=True), \
             patch.dict('sys.modules', {'app.interacao': types.ModuleType('app.interacao')}):
            spec = importlib.util.spec_from_file_location('app._encerramento_efd_teste',
                Path(__file__).resolve().parents[1] / 'app' / 'dominio.py')
            self.d = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.d)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.interacao = Mock()
        self.interacao.janela_dominio_em_foco.return_value = True
        self.interacao.janela_dominio_ou_remota_em_foco.return_value = True
        self.stack.enter_context(patch.object(self.d, 'interacao', self.interacao))
        self.stack.enter_context(patch.object(self.d.time, 'sleep'))
        self.salvar = self.stack.enter_context(patch.object(self.d, 'salvar'))
        self.frame = Image.new('RGB', (400, 300), 'white')
        self.area = Image.new('RGB', (200, 150), 'white')
        self.capturar = self.stack.enter_context(patch.object(self.d.tela, 'capturar_tela', return_value=self.frame))
        self.titulo = self.stack.enter_context(patch.object(self.d, '_achar_texto_reforcado', return_value=(30, 40)))
        self.stack.enter_context(patch.object(self.d.tela, 'recortar_a_partir_de', return_value=(self.area, 20, 30)))
        self.ocr = self.stack.enter_context(patch.object(self.d.tela, 'ler_dados_ocr_formulario',
            return_value=self.leitura()))
        self.azul = self.stack.enter_context(patch.object(self.d, '_verificar_retorno_tela_principal',
            return_value='tela_principal_reconhecida'))
        self.legado = self.stack.enter_context(patch.object(self.d, '_fechar_tela_geracao'))
        self.acompanhamento = types.SimpleNamespace(janela_dominio={'hwnd': 42})

    @staticmethod
    def leitura(textos=('Fechar',)):
        return {'text': list(textos), 'left': [320] * len(textos),
                'top': [160 + i*80 for i in range(len(textos))],
                'width': [160] * len(textos), 'height': [48] * len(textos)}

    def executar(self):
        return self.d._fechar_formulario_efd(self.acompanhamento, 'sintetico_')

    def sem_teclas(self):
        self.interacao.pressionar_enter.assert_not_called()
        self.interacao.pressionar_esc_repetidas.assert_not_called()
        self.interacao.pressionar_esc_no_dominio.assert_not_called()
        self.interacao.pressionar_atalho.assert_not_called()
        self.legado.assert_not_called()

    def test_clica_fechar_atual_uma_vez_e_so_entao_confirma_azul(self):
        ordem = Mock()
        ordem.attach_mock(self.interacao.clicar, 'fechar')
        ordem.attach_mock(self.azul, 'conferir_azul')
        self.assertTrue(self.executar())
        self.interacao.clicar.assert_called_once_with(120, 76)
        self.assertEqual([c[0] for c in ordem.mock_calls], ['fechar', 'conferir_azul'])
        self.sem_teclas()

    def test_foco_remoto_sem_hwnd_principal_nao_autoriza_fechar_formulario(self):
        self.interacao.janela_dominio_em_foco.return_value = False
        self.assertFalse(self.executar())
        self.capturar.assert_not_called()
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_botao_ausente_nao_usa_posicao_antiga_nem_esc(self):
        self.ocr.return_value = self.leitura(('FecharTudo',))
        self.assertFalse(self.executar())
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_outro_aviso_impede_fechar_formulario(self):
        self.ocr.return_value = self.leitura(('Aviso', 'Fechar'))
        self.assertFalse(self.executar())
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_clique_fechar_sem_painel_azul_nao_vira_sucesso(self):
        self.azul.return_value = 'tela_principal_nao_reconhecida'
        self.assertFalse(self.executar())
        self.interacao.clicar.assert_called_once()
        self.sem_teclas()

    def test_formulario_ja_fechado_exige_azul_sem_outro_clique(self):
        self.titulo.return_value = None
        self.assertTrue(self.executar())
        self.interacao.clicar.assert_not_called()
        self.azul.assert_called_once_with(self.acompanhamento)
        self.sem_teclas()

    def test_titulo_ilegivel_sem_azul_nao_equivale_a_fechado(self):
        self.titulo.return_value = None
        self.azul.return_value = 'tela_principal_nao_reconhecida'
        self.assertFalse(self.executar())
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_perda_de_foco_durante_ocr_impede_clique(self):
        def ler(*args, **kwargs):
            self.interacao.janela_dominio_em_foco.return_value = False
            return self.leitura()
        self.ocr.side_effect = ler
        self.assertFalse(self.executar())
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_cancelamento_durante_ocr_e_propagado(self):
        self.ocr.side_effect = ExecucaoInterrompida('teste')
        with self.assertRaises(ExecucaoInterrompida):
            self.executar()
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_cancelamento_depois_da_leitura_impede_fechar(self):
        controle = ControleExecucao()
        def ler(*args, **kwargs):
            controle.interromper('teste')
            return self.leitura()
        self.ocr.side_effect = ler
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar()
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_espera_aviso_remoto_sumir_sem_reenviar_enter(self):
        aviso, formulario = self.frame, self.frame.copy()
        self.interacao.janela_dominio_em_foco.return_value = False
        def capturar():
            imagem = sequencia.pop(0)
            if imagem is formulario:
                self.interacao.janela_dominio_em_foco.return_value = True
            return imagem
        sequencia = [aviso, aviso, formulario]
        self.capturar.side_effect = capturar
        self.titulo.side_effect = lambda imagem, texto, **kw: (
            (20, 30) if imagem is aviso and texto == 'Arquivo gerado com sucesso' else
            (30, 40) if imagem is formulario and texto == 'Contribui' else None)
        self.assertTrue(self.d._confirmar_saida_aviso_efd('Contribui', {'hwnd': 42},
                                                       'Arquivo gerado com sucesso'))
        self.assertEqual(self.capturar.call_count, 3)
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_f_sublinhado_lido_como_eechar_ainda_acha_o_botao_e_clica_uma_vez(self):
        # Captura real de 20/10: o tesseract leu "Fechar" como "Eechar" nas duas preparações.
        self.ocr.return_value = self.leitura(('Eechar',))
        self.assertTrue(self.executar())
        self.interacao.clicar.assert_called_once_with(120, 76)
        self.sem_teclas()

    def test_dois_candidatos_terminados_em_echar_sao_ambiguos_e_nao_clicam(self):
        self.ocr.return_value = self.leitura(('Eechar', 'Pechar'))
        self.assertFalse(self.executar())
        self.interacao.clicar.assert_not_called()
        self.sem_teclas()

    def test_rotulo_fechar_so_aceita_letra_inicial_diferente_de_um_unico_caractere(self):
        def palavra(texto, y):
            return {'texto': texto, 'x': 400.0, 'y': float(y), 'w': 40.0, 'h': 10.0}
        # palavras da coluna de botões da captura real (EFD Contribuições)
        reais = [palavra(t, 20 + 30 * i) for i, t in enumerate(
            ['Eechar', 'Empresas...', 'Outros', 'dados...', 'Suditar', 'Arquivo...', 'Visualizar',
             'Concluir', 'Atigidade...l', 'Conteúdo...', 'Soluções'])]
        self.assertEqual(self.d._rotulo_fechar(reais)['y'], 20.0)
        for texto in ('FecharTudo', 'echar', 'Fechar2'):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                self.d._rotulo_fechar([palavra(texto, 20), palavra('Empresas...', 50)])
        # o rótulo exato continua tendo prioridade sobre a variação
        exato = [palavra('Eechar', 20), palavra('Fechar', 60)]
        self.assertEqual(self.d._rotulo_fechar(exato)['y'], 60.0)


if __name__ == '__main__':
    unittest.main()
