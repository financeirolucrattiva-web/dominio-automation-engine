import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import otimizacoes, seletor_pasta as seletor, tela


class TestInterruptores(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.arquivo = Path(self.pasta.name) / 'otimizacoes.json'
        for alvo, valor in (('ARQUIVO', self.arquivo), ('_forcado', None)):
            patcher = patch.object(otimizacoes, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, {'DOMINIO_MODO_SEGURO': ''})
        patcher.start()
        self.addCleanup(patcher.stop)
        otimizacoes.restaurar_para_testes()
        otimizacoes._forcado = None
        self.addCleanup(otimizacoes.restaurar_para_testes)

    def escrever(self, conteudo):
        self.arquivo.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo), encoding='utf-8')
        os.utime(self.arquivo, ns=(os.stat(self.arquivo).st_atime_ns, os.stat(self.arquivo).st_mtime_ns + 10**9))

    def test_sem_arquivo_tudo_ligado(self):
        self.assertTrue(all(otimizacoes.estado().values()))

    def test_modo_seguro_no_arquivo_desliga_tudo(self):
        self.escrever({'modo_seguro': True})
        self.assertFalse(any(otimizacoes.estado().values()))

    def test_uma_otimizacao_desligada_e_as_outras_continuam(self):
        self.escrever({'ocr_paralelo': False})
        estado = otimizacoes.estado()
        self.assertFalse(estado['ocr_paralelo'])
        self.assertTrue(all(v for k, v in estado.items() if k != 'ocr_paralelo'))

    def test_mudanca_no_arquivo_vale_sem_reiniciar(self):
        self.escrever({'modo_seguro': True})
        self.assertFalse(otimizacoes.ativa('ocr_paralelo'))
        self.escrever({'modo_seguro': False})
        self.assertTrue(otimizacoes.ativa('ocr_paralelo'))

    def test_arquivo_invalido_cai_no_modo_seguro(self):
        for conteudo in ('{quebrado', '[1, 2]', '{"ocr_paralelo": "nao"}', '{"inexistente": true}'):
            with self.subTest(conteudo=conteudo):
                self.escrever(conteudo)
                otimizacoes._cache.update(mtime=None, config=None, aviso=False)
                self.assertFalse(otimizacoes.ativa('ocr_paralelo'))

    def test_variavel_de_ambiente_desliga_tudo(self):
        with patch.dict(os.environ, {'DOMINIO_MODO_SEGURO': '1'}):
            self.assertFalse(any(otimizacoes.estado().values()))

    def test_desligar_vale_pelo_resto_do_processo_e_so_para_ela(self):
        otimizacoes.desligar('geometria_lembrada', 'teste')
        self.assertFalse(otimizacoes.ativa('geometria_lembrada'))
        self.assertTrue(otimizacoes.ativa('ocr_paralelo'))

    def test_nome_desconhecido_e_erro(self):
        with self.assertRaises(KeyError):
            otimizacoes.ativa('inventada')
        with self.assertRaises(KeyError):
            otimizacoes.desligar('inventada', 'x')

    def test_falha_do_proprio_pre_aquecimento_o_desliga_e_nao_derruba_a_rotina(self):
        imagem = Image.new('RGB', (30, 20), 'white')
        with patch('app.tela.ThreadPoolExecutor', side_effect=RuntimeError('sem threads')), tela.reutilizar_ocr():
            tela.pre_aquecer_ocr((imagem, [('tesseract', 2), ('tesseract', 4)]))
        self.assertFalse(otimizacoes.ativa('ocr_paralelo'))


class TestOcrCentroDoSeletor(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(otimizacoes, '_forcado', True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.imagem = Image.new('RGB', (1000, 600), 'white')

    def test_palavras_do_centro_voltam_para_o_referencial_da_tela_inteira(self):
        dados = {'text': ['Unidade'], 'left': [40], 'top': [80], 'width': [100], 'height': [40]}
        with patch.object(tela, '_ler_dados_ocr', return_value=dados) as ocr:
            palavras = seletor._palavras(self.imagem, True)
            recorte = ocr.call_args.args[0]
        # centro = 60% x 60%: margem de 200 x 120 px; palavra em (40/4, 80/4) no recorte
        self.assertEqual(recorte.size, (600, 360))
        self.assertEqual((palavras[0]['x'], palavras[0]['y']), (10 + 200, 20 + 120))
        with patch.object(tela, '_ler_dados_ocr', return_value=dados):
            inteira = seletor._palavras(self.imagem)
        self.assertEqual((inteira[0]['x'], inteira[0]['y']), (10, 20))

    def test_leitor_usa_o_centro_e_volta_a_tela_inteira_se_o_dialogo_nao_aparece_la(self):
        chamadas = []

        def medir(imagem, **kw):
            chamadas.append(kw.get('centro', False))
            if kw.get('centro'):
                raise seletor.SeletorPastaNaoConfirmado('fora do centro')
            return {'combo': (1, 2, 3, 4), 'ok': (9, 9)}
        with patch.object(seletor, 'medir_dialogo', side_effect=medir):
            self.assertEqual(seletor._LeitorDialogo().ler(self.imagem), {'combo': (1, 2, 3, 4), 'ok': (9, 9)})
        self.assertEqual(chamadas, [True, False])

    def test_centro_que_funciona_nao_repete_a_leitura(self):
        with patch.object(seletor, 'medir_dialogo', return_value={'combo': (1, 2, 3, 4), 'ok': (9, 9)}) as medir:
            leitor = seletor._LeitorDialogo()
            leitor.ler(self.imagem)
            leitor.ler(self.imagem)  # mesma captura: cache
        self.assertEqual(medir.call_count, 1)

    def test_navegacao_aceita_o_centro_mesmo_sem_o_ok_medido(self):
        # Captura real: no recorte central o OCR perde OK/Cancelar; a navegação não precisa do OK.
        with patch.object(seletor, 'medir_dialogo', return_value={'combo': (1, 2, 3, 4), 'ok': None}) as chamada:
            detalhes = seletor._LeitorDialogo().ler(self.imagem)
        self.assertIsNone(detalhes['ok'])
        self.assertEqual(chamada.call_count, 1)
        self.assertTrue(chamada.call_args.kwargs.get('centro'))

    def test_leitura_completa_para_a_confirmacao_final_mede_a_tela_inteira_e_acha_o_ok(self):
        def medir(imagem, **kw):
            return {'combo': (1, 2, 3, 4), 'ok': None if kw.get('centro') else (833, 560)}
        with patch.object(seletor, 'medir_dialogo', side_effect=medir) as chamada:
            detalhes = seletor._LeitorDialogo(completo=True).ler(self.imagem)
        self.assertEqual(detalhes['ok'], (833, 560))
        self.assertEqual([c.kwargs.get('centro', False) for c in chamada.call_args_list], [False])

    def test_aguardar_dialogo_repassa_completo_ao_leitor(self):
        with patch.object(seletor, '_LeitorDialogo') as leitor:
            leitor.return_value.ler.return_value = {'arvore': (0, 0, 1, 1)}
            seletor._aguardar_dialogo(lambda: self.imagem, fase='confirmar_destino_e_ok', completo=True)
        leitor.assert_called_once_with(completo=True)

    def test_confirmacoes_finais_do_seletor_pedem_leitura_completa(self):
        import inspect
        codigo = inspect.getsource(seletor.selecionar_pasta)
        self.assertEqual(codigo.count("fase='confirmar_destino_e_ok',completo=True"), 3)

    def test_fase_so_da_unidade_aceita_o_centro_sem_ok(self):
        with patch.object(seletor, 'medir_dialogo', return_value={'combo': (1, 2, 3, 4)}) as chamada:
            seletor._LeitorDialogo(somente_unidade=True).ler(self.imagem)
        self.assertEqual(chamada.call_count, 1)

    def test_com_a_otimizacao_desligada_usa_so_a_tela_inteira(self):
        with patch.object(otimizacoes, '_forcado', False), \
                patch.object(seletor, 'medir_dialogo', return_value={'combo': (1, 2, 3, 4)}) as medir:
            seletor._LeitorDialogo().ler(self.imagem)
        self.assertEqual(medir.call_args.kwargs.get('centro', False), False)


if __name__ == '__main__':
    unittest.main()
