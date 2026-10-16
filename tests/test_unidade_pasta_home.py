"""Home idempotente: repintura do realce não troca a unidade lógica."""
import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

from app import seletor_pasta as seletor
from test_seletor_pasta import DESTINO, FOLHA
from test_unidade_pasta_sincronizacao import ArvoreAssincrona


class ArvoreHomeRepintado(ArvoreAssincrona):
    """A primeira opção continua Servidor C; Home apenas repinta um pixel."""
    def capturar(self):
        imagem = super().capturar()
        if self.combo_aberto and 'home' in self.enviados_combo:
            # Dentro do realce, preservando caixa, opção, letra e metadados OCR.
            imagem.putpixel((120, 115), (255, 255, 255))
        return imagem


class TestHomeIdempotente(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.saida = io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.saida))
        self.stack.enter_context(patch.object(seletor.time, 'sleep'))
        self.stack.enter_context(patch.object(seletor, '_palavras',
            side_effect=lambda imagem: imagem.info['palavras_sinteticas']))

    def test_hash_do_realce_pode_mudar_sem_mudar_unidade_nem_posicao(self):
        arvore = ArvoreHomeRepintado()
        arvore.clicar(468, 88)
        for _ in range(3):
            antes = arvore.capturar()
        detalhes_antes = seletor.medir_dialogo(antes, somente_unidade=True)
        arvore.tecla('home')
        depois = arvore.capturar()
        detalhes_depois = seletor.medir_dialogo(depois, somente_unidade=True)
        self.assertEqual(arvore.drive, 'Servidor (C:\\)')
        self.assertEqual(arvore.indice_combo, 0)
        self.assertEqual(seletor._realce_unidade(antes, detalhes_antes),
                         seletor._realce_unidade(depois, detalhes_depois))
        self.assertEqual(seletor._assinatura_unidade(antes, detalhes_antes),
                         seletor._assinatura_unidade(depois, detalhes_depois))
        self.assertNotEqual(seletor._opcao_unidade(antes, detalhes_antes),
                            seletor._opcao_unidade(depois, detalhes_depois))

    def test_home_na_primeira_opcao_aceita_mesmo_campo_apos_tab_e_prossegue_para_client_c(self):
        arvore = ArvoreHomeRepintado()
        self.assertTrue(seletor.selecionar_pasta(
            DESTINO, arvore.capturar, arvore.clicar, arvore.tecla))
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])

    def test_primeiro_ocr_consumiu_prazo_mas_quadro_identico_pode_confirmar_pelo_cache(self):
        imagem = ArvoreAssincrona().capturar()
        capturar = Mock(side_effect=[imagem, imagem.copy()])
        relogio = [0.0]
        medir = seletor.medir_dialogo
        def medir_lento(*args, **kwargs):
            detalhes = medir(*args, **kwargs)
            relogio[0] += 11.0  # Tempo virtual, sem aguardar nem executar OCR real.
            return detalhes
        with patch.object(seletor.time, 'monotonic', side_effect=lambda: relogio[0]), \
             patch.object(seletor, 'medir_dialogo', side_effect=medir_lento) as medicao, \
             patch.object(seletor.time, 'sleep') as dormir:
            _, detalhes = seletor._aguardar_estado_unidade(capturar,
                aberta=False, fase='fechar_unidade')
        self.assertFalse(detalhes['lista'])
        self.assertEqual(capturar.call_count, 2)
        self.assertEqual(medicao.call_count, 1)  # Segunda imagem idêntica não repete OCR.
        dormir.assert_not_called()

    def test_confirmacao_extra_divergente_nao_abre_novo_prazo_nem_terceira_tentativa(self):
        primeira = ArvoreAssincrona().capturar()
        segunda = ArvoreAssincrona(drive='Client C (M:\\)').capturar()
        capturar = Mock(side_effect=[primeira, segunda])
        relogio = [0.0]
        medir = seletor.medir_dialogo
        def medir_lento(*args, **kwargs):
            detalhes = medir(*args, **kwargs)
            relogio[0] += 11.0
            return detalhes
        with patch.object(seletor.time, 'monotonic', side_effect=lambda: relogio[0]), \
             patch.object(seletor, 'medir_dialogo', side_effect=medir_lento) as medicao, \
             patch.object(seletor.time, 'sleep') as dormir:
            with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
                seletor._aguardar_estado_unidade(capturar,
                    aberta=False, fase='fechar_unidade')
        self.assertEqual(capturar.call_count, 2)
        self.assertEqual(medicao.call_count, 2)
        dormir.assert_not_called()

    def test_confirmacao_extra_tolere_mudanca_de_background_com_mesmo_estado(self):
        primeira = ArvoreAssincrona().capturar()
        segunda = primeira.copy()
        segunda.putpixel((55, 270), (1, 0, 0))
        capturar = Mock(side_effect=[primeira, segunda])
        relogio = [0.0]
        medir = seletor.medir_dialogo
        def medir_lento(*args, **kwargs):
            detalhes = medir(*args, **kwargs)
            relogio[0] += 11.0
            return detalhes
        with patch.object(seletor.time, 'monotonic', side_effect=lambda: relogio[0]), \
             patch.object(seletor, 'medir_dialogo', side_effect=medir_lento) as medicao, \
             patch.object(seletor.time, 'sleep') as dormir:
            _, detalhes = seletor._aguardar_estado_unidade(capturar,
                aberta=False, fase='fechar_unidade')
        self.assertFalse(detalhes['lista'])
        self.assertEqual(capturar.call_count, 2)
        self.assertEqual(medicao.call_count, 2)
        dormir.assert_not_called()

    def test_primeiro_estado_invalido_apos_prazo_nao_ganha_captura_extra(self):
        arvore = ArvoreAssincrona()
        arvore.clicar(468, 88)
        for _ in range(3):
            imagem = arvore.capturar()
        self.assertTrue(arvore.combo_aberto)
        capturar = Mock(side_effect=[imagem])
        relogio = [0.0]
        medir = seletor.medir_dialogo
        def medir_lento(*args, **kwargs):
            detalhes = medir(*args, **kwargs)
            relogio[0] += 11.0
            return detalhes
        with patch.object(seletor.time, 'monotonic', side_effect=lambda: relogio[0]), \
             patch.object(seletor, 'medir_dialogo', side_effect=medir_lento) as medicao, \
             patch.object(seletor.time, 'sleep') as dormir:
            with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
                seletor._aguardar_estado_unidade(capturar,
                    aberta=False, fase='fechar_unidade')
        self.assertEqual(capturar.call_count, 1)
        self.assertEqual(medicao.call_count, 1)
        dormir.assert_not_called()

    def test_erro_na_medicao_extra_nao_reutiliza_flags_da_primeira_captura_valida(self):
        primeira = ArvoreAssincrona().capturar()
        segunda = primeira.copy()
        segunda.putpixel((55, 270), (1, 0, 0))
        capturar = Mock(side_effect=[primeira, segunda])
        relogio = [0.0]
        medir = seletor.medir_dialogo
        chamadas = [0]
        def medir_lento_depois_falha(*args, **kwargs):
            chamadas[0] += 1
            if chamadas[0] == 2:
                raise ValueError('medicao_sintetica_indisponivel')
            detalhes = medir(*args, **kwargs)
            relogio[0] += 11.0
            return detalhes
        with patch.object(seletor.time, 'monotonic', side_effect=lambda: relogio[0]), \
             patch.object(seletor, 'medir_dialogo', side_effect=medir_lento_depois_falha), \
             patch.object(seletor.time, 'sleep') as dormir:
            with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
                seletor._aguardar_estado_unidade(capturar,
                    aberta=False, fase='fechar_unidade')
        eventos = [json.loads(linha.removeprefix('PASTA_NAVEGACAO '))
                   for linha in self.saida.getvalue().splitlines()
                   if linha.startswith('PASTA_NAVEGACAO ')]
        evento = eventos[-1]
        self.assertEqual(evento['fase'], 'fechar_unidade')
        self.assertFalse(evento['confirmado'])
        self.assertFalse(evento['dialogo_lido'])
        self.assertFalse(evento['opcao_lida'])
        self.assertFalse(evento['opcao_mudou'])
        self.assertEqual(evento['capturas'], 2)
        self.assertTrue(evento['confirmacao_extra'])
        self.assertEqual(capturar.call_count, 2)
        dormir.assert_not_called()


if __name__ == '__main__':
    unittest.main()
