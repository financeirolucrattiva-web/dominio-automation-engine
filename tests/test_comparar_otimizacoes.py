"""Funcoes puras do comparador de otimizacoes: escolha de capturas, normalizacao e comparacao.

Nenhum teste aqui executa OCR nem abre captura real: so imagens em branco geradas na hora.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from scripts import comparar_otimizacoes as comp


def execucao(chave='{}', excecao='', duracao=1.0, positivo=False, desligadas=(), contadores=None):
    return comp.Execucao(chave, excecao, duracao, positivo, desligadas, contadores or {})


def registro(linha='leitura', imagem='a.png', classico=None, otimizado=None, **extra):
    classico = classico or execucao('{"x": 1}')
    otimizado = otimizado or execucao('{"x": 1}')
    return comp.Registro(linha, imagem, classico, otimizado, comp.comparar(classico, otimizado),
                         classico.positivo, **extra)


class TestEscolhaDeImagens(unittest.TestCase):
    def test_tamanho_minimo_de_tela_inteira(self):
        self.assertTrue(comp.tamanho_suficiente(1000, 600))
        self.assertFalse(comp.tamanho_suficiente(999, 600))
        self.assertFalse(comp.tamanho_suficiente(1000, 599))
        self.assertFalse(comp.tamanho_suficiente(670, 440))

    def test_com_poucas_imagens_usa_todas_em_ordem_de_nome(self):
        self.assertEqual(comp.escolher_imagens(['c.png', 'a.png', 'b.png'], 12), ['a.png', 'b.png', 'c.png'])

    def test_espacadas_incluem_primeira_e_ultima_sem_repetir(self):
        nomes = [f'img{i:03d}.png' for i in range(151)]
        escolhidas = comp.escolher_imagens(nomes, 12, obrigatoria='nao_existe.png')
        self.assertEqual(len(escolhidas), 12)
        self.assertEqual(escolhidas[0], nomes[0])
        self.assertEqual(escolhidas[-1], nomes[-1])
        self.assertEqual(escolhidas, sorted(set(escolhidas)))
        passos = {int(b[3:6]) - int(a[3:6]) for a, b in zip(escolhidas, escolhidas[1:])}
        self.assertLessEqual(max(passos) - min(passos), 1)  # espacamento uniforme (+-1 por arredondamento)

    def test_obrigatoria_entra_sempre_e_o_total_respeita_o_maximo(self):
        nomes = [f'img{i:03d}.png' for i in range(50)] + [comp.OBRIGATORIA]
        escolhidas = comp.escolher_imagens(nomes, 5)
        self.assertIn(comp.OBRIGATORIA, escolhidas)
        self.assertEqual(len(escolhidas), 5)

    def test_obrigatoria_ausente_nao_e_inventada(self):
        escolhidas = comp.escolher_imagens([f'img{i:03d}.png' for i in range(50)], 5)
        self.assertNotIn(comp.OBRIGATORIA, escolhidas)
        self.assertEqual(len(escolhidas), 5)

    def test_maximo_um(self):
        nomes = ['a.png', 'b.png', comp.OBRIGATORIA]
        self.assertEqual(comp.escolher_imagens(nomes, 1), [comp.OBRIGATORIA])
        self.assertEqual(comp.escolher_imagens(['a.png', 'b.png', 'c.png'], 1), ['a.png'])

    def test_listar_candidatas_ignora_pequenas_ilegiveis_e_subpastas(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            Image.new('RGB', (1000, 600)).save(raiz / 'grande.png')
            Image.new('RGB', (999, 900)).save(raiz / 'estreita.png')
            Image.new('RGB', (1440, 300)).save(raiz / 'baixa.png')
            (raiz / 'quebrada.png').write_bytes(b'nao e uma imagem')
            (raiz / 'sub').mkdir()
            Image.new('RGB', (1440, 900)).save(raiz / 'sub' / 'dentro.png')
            nomes, ignorados = comp.listar_candidatas(raiz)
            self.assertEqual(nomes, ['grande.png'])
            self.assertEqual(ignorados, 1)
            self.assertEqual(comp.listar_candidatas(raiz, ['GRAN'])[0], ['grande.png'])
            self.assertEqual(comp.listar_candidatas(raiz, ['outra'])[0], [])


class TestNormalizacao(unittest.TestCase):
    def test_ordem_das_chaves_e_tupla_x_lista_nao_importam(self):
        a = {'b': (1, 2), 'a': {'y': 1.5, 'x': None}}
        b = {'a': {'x': None, 'y': 1.5}, 'b': [1, 2]}
        self.assertEqual(comp.normalizar_resultado(a), comp.normalizar_resultado(b))

    def test_valor_estranho_vira_texto_em_vez_de_quebrar(self):
        class Estranho:
            def __str__(self):
                return 'estranho'
        self.assertIn('estranho', comp.normalizar_resultado({'k': Estranho()}))

    def test_chaves_de_tipos_misturados_nao_quebram(self):
        self.assertEqual(comp.normalizar_resultado({1: 'a', 'b': 2}), comp.normalizar_resultado({'b': 2, 1: 'a'}))

    def test_excecao_vale_so_pela_classe(self):
        self.assertEqual(comp.normalizar_excecao(ValueError('uma mensagem')),
                         comp.normalizar_excecao(ValueError('outra bem diferente')))
        self.assertNotEqual(comp.normalizar_excecao(ValueError('x')), comp.normalizar_excecao(RuntimeError('x')))
        self.assertNotIn('mensagem', comp.normalizar_excecao(ValueError('uma mensagem')))

    def test_nomes_mostrados_na_tabela_saem_sem_acento(self):
        self.assertEqual(comp.sem_acentos('EFD Contribuições'), 'EFD Contribuicoes')
        self.assertEqual(comp.sem_acentos('Livros Fiscais'), 'Livros Fiscais')

    def test_seletor_ignora_palavras_e_ordena_botoes(self):
        detalhes = {'combo': (1, 2, 3, 4), 'arvore': (5, 6, 7, 8), 'ok': (9, 10), 'palavras': [{'texto': 'segredo'}],
                    'botoes_ok': [(30, 1, 1, 1), (10, 1, 1, 1)], 'lista': None}
        resultado = comp.selecionar_seletor(detalhes)
        self.assertEqual(set(resultado), {'combo', 'arvore', 'ok', 'botoes_ok'})
        self.assertEqual(resultado['botoes_ok'], [(10, 1, 1, 1), (30, 1, 1, 1)])
        self.assertNotIn('segredo', comp.normalizar_resultado(resultado))
        sem_ok = comp.selecionar_seletor({'combo': (1, 2, 3, 4), 'arvore': (5, 6, 7, 8)})
        self.assertIsNone(sem_ok['ok'])
        self.assertIsNone(sem_ok['botoes_ok'])


class TestComparacao(unittest.TestCase):
    def test_iguais(self):
        c = comp.comparar(execucao('{"a": 1}'), execucao('{"a": 1}', duracao=9.0))
        self.assertTrue(c.identico)
        self.assertEqual(c.tipo, 'identico')

    def test_excecoes_da_mesma_classe_sao_iguais_e_de_classes_diferentes_nao(self):
        mesma = comp.comparar(execucao(comp.normalizar_excecao(ValueError('a')), 'ValueError'),
                              execucao(comp.normalizar_excecao(ValueError('b')), 'ValueError'))
        self.assertTrue(mesma.identico)
        outra = comp.comparar(execucao(comp.normalizar_excecao(ValueError('a')), 'ValueError'),
                              execucao(comp.normalizar_excecao(RuntimeError('a')), 'RuntimeError'))
        self.assertFalse(outra.identico)
        self.assertEqual(outra.tipo, 'excecao_diferente')

    def test_valor_contra_excecao(self):
        c = comp.comparar(execucao('{"a": 1}'), execucao(comp.normalizar_excecao(ValueError()), 'ValueError'))
        self.assertFalse(c.identico)
        self.assertEqual(c.tipo, 'valor_x_excecao')

    def test_diferenca_so_numerica_informa_o_tamanho(self):
        c = comp.comparar(execucao('{"ok": [10, 20], "nome": "a"}'), execucao('{"ok": [11, 20], "nome": "a"}'))
        self.assertFalse(c.identico)
        self.assertEqual(c.tipo, 'numerico')
        self.assertEqual(c.delta, 1)
        self.assertEqual(c.caminhos, ('ok[0]',))

    def test_diferenca_de_texto_nao_vaza_o_valor(self):
        c = comp.comparar(execucao('{"inicial": {"valor": "01/01/2026"}}'),
                          execucao('{"inicial": {"valor": "01/07/2026"}}'))
        self.assertEqual(c.tipo, 'estrutura_ou_texto')
        self.assertIsNone(c.delta)
        self.assertEqual(c.caminhos, ('inicial.valor',))
        self.assertNotIn('2026', repr(c))

    def test_delta_numerico_max(self):
        self.assertEqual(comp.delta_numerico_max({'a': [1, 5], 'b': 2.5}, {'a': [3, 5], 'b': 1.5}), 2)
        self.assertEqual(comp.delta_numerico_max([], []), 0.0)
        self.assertIsNone(comp.delta_numerico_max([1, 2], [1]))
        self.assertIsNone(comp.delta_numerico_max({'a': 1}, {'b': 1}))
        self.assertIsNone(comp.delta_numerico_max({'a': 'x'}, {'a': 'y'}))
        self.assertEqual(comp.delta_numerico_max({'a': 'x', 'n': 1}, {'a': 'x', 'n': 4}), 3)
        self.assertIsNone(comp.delta_numerico_max(True, 1))  # booleano nao e numero
        self.assertEqual(comp.delta_numerico_max(None, None), 0.0)

    def test_caminhos_so_com_nomes_do_codigo_e_com_limite(self):
        a = {'campo_ok': 'x', 'Texto Livre 123': 'x', 'lista': [1, 2, 3]}
        b = {'campo_ok': 'y', 'Texto Livre 123': 'y', 'lista': [1, 9, 3]}
        self.assertEqual(comp.caminhos_diferentes(a, b), ['*', 'campo_ok', 'lista[1]'])  # em ordem de chave
        grande_a = {f'k{i}': 0 for i in range(20)}
        grande_b = {f'k{i}': 1 for i in range(20)}
        self.assertEqual(len(comp.caminhos_diferentes(grande_a, grande_b)), 6)
        self.assertEqual(comp.caminhos_diferentes({'a': 1}, {'b': 1}), ['{chaves}'])
        self.assertEqual(comp.caminhos_diferentes([1], [1, 2]), ['[tamanho]'])
        self.assertEqual(comp.caminhos_diferentes(1, 2), ['<raiz>'])


class TestExecutar(unittest.TestCase):
    def setUp(self):
        self.otimizacoes = SimpleNamespace(_forcado=None, _desligadas={})

    def rodar(self, chamar, modo=comp.CLASSICO, **opcoes):
        return comp.executar(chamar, modo, modulo_otimizacoes=self.otimizacoes, esperar_leitor=lambda: True, **opcoes)

    def test_o_modo_liga_ou_desliga_todas_as_otimizacoes(self):
        vistos = []
        self.rodar(lambda: vistos.append(self.otimizacoes._forcado), comp.CLASSICO)
        self.rodar(lambda: vistos.append(self.otimizacoes._forcado), comp.OTIMIZADO)
        self.assertEqual(vistos, [False, True])

    def test_devolve_valor_normalizado_e_duracao(self):
        r = self.rodar(lambda: {'b': (1, 2)}, positivo=lambda v: isinstance(v, dict))
        self.assertEqual(r.chave, '{"b": [1, 2]}')
        self.assertEqual(r.excecao, '')
        self.assertTrue(r.positivo)
        self.assertGreaterEqual(r.duracao, 0)

    def test_excecao_vira_so_a_classe(self):
        def falha():
            raise ValueError('texto lido da tela')
        r = self.rodar(falha)
        self.assertEqual(r.excecao, 'ValueError')
        self.assertNotIn('texto lido', r.chave)
        self.assertFalse(r.positivo)

    def test_keyboardinterrupt_nao_e_engolido(self):
        def interrompe():
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.rodar(interrompe)

    def test_nada_do_que_a_aplicacao_imprime_chega_ao_console(self):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            self.rodar(lambda: print('SEGREDO da captura') or 1)
        self.assertEqual(saida.getvalue(), '')

    def test_otimizacao_desligada_sozinha_e_informada_e_limpa(self):
        def desliga():
            self.otimizacoes._desligadas['ocr_paralelo'] = 'RuntimeError'
            self.otimizacoes._desligadas['outra'] = 'mensagem com espaco e texto livre'
            return 1
        r = self.rodar(desliga, comp.OTIMIZADO)
        self.assertEqual(r.desligadas, (('ocr_paralelo', 'RuntimeError'), ('outra', '?')))
        self.assertEqual(self.otimizacoes._desligadas, {})

    def test_preparar_roda_antes_e_contadores_sao_zerados_e_copiados(self):
        contadores = comp.Contadores()
        contadores.somar('tesseract')
        ordem = []

        def chamar():
            ordem.append('chamar')
            contadores.somar('windows')
            return 1
        r = self.rodar(chamar, preparar=lambda: ordem.append('preparar'), contadores=contadores)
        self.assertEqual(ordem, ['preparar', 'chamar'])
        self.assertEqual(r.contadores['tesseract'], 0)
        self.assertEqual(r.contadores['windows'], 1)

    def test_defeito_do_proprio_comparador_fica_visivel(self):
        r = self.rodar(lambda: 1, simplificar=lambda v: v['chave_que_nao_existe'])
        self.assertEqual(r.excecao, 'ErroDoComparador:TypeError')

    def test_extras_ficam_em_memoria(self):
        r = self.rodar(lambda: 5, extras=lambda v: {'n': v})
        self.assertEqual(r.extras, {'n': 5})


class TestRodarCaso(unittest.TestCase):
    def fazer_rodar(self, respostas, chamadas):
        def rodar(caso, imagem, modo, contadores):
            chamadas.append(modo)
            return respostas[modo].pop(0)
        return rodar

    def test_identicos_rodam_uma_vez_de_cada_e_a_ordem_alterna(self):
        caso = comp.Caso('leitura', None)
        for indice, esperado in ((0, [comp.CLASSICO, comp.OTIMIZADO]), (1, [comp.OTIMIZADO, comp.CLASSICO])):
            chamadas = []
            respostas = {comp.CLASSICO: [execucao('1')], comp.OTIMIZADO: [execucao('1')]}
            r = comp.rodar_caso(caso, None, 'a.png', indice, None, True, self.fazer_rodar(respostas, chamadas))
            self.assertEqual(chamadas, esperado)
            self.assertTrue(r.comparacao.identico)
            self.assertIsNone(r.repeticao)

    def test_divergencia_repete_cada_modo_e_separa_ruido_de_defeito(self):
        caso = comp.Caso('leitura', None)
        chamadas = []
        respostas = {comp.CLASSICO: [execucao('1'), execucao('1')],
                     comp.OTIMIZADO: [execucao('2'), execucao('2')]}
        r = comp.rodar_caso(caso, None, 'a.png', 0, None, True, self.fazer_rodar(respostas, chamadas))
        self.assertFalse(r.comparacao.identico)
        self.assertEqual(chamadas.count(comp.CLASSICO), 2)
        self.assertEqual(chamadas.count(comp.OTIMIZADO), 2)
        self.assertEqual(r.repeticao, {'ruido_classico': False, 'ruido_otimizado': False})
        respostas = {comp.CLASSICO: [execucao('1'), execucao('3')], comp.OTIMIZADO: [execucao('2'), execucao('2')]}
        r = comp.rodar_caso(caso, None, 'a.png', 0, None, True, self.fazer_rodar(respostas, []))
        self.assertEqual(r.repeticao, {'ruido_classico': True, 'ruido_otimizado': False})

    def test_sem_repeticao_quando_desligada(self):
        caso = comp.Caso('leitura', None)
        chamadas = []
        respostas = {comp.CLASSICO: [execucao('1')], comp.OTIMIZADO: [execucao('2')]}
        r = comp.rodar_caso(caso, None, 'a.png', 0, None, False, self.fazer_rodar(respostas, chamadas))
        self.assertEqual(len(chamadas), 2)
        self.assertIsNone(r.repeticao)

    def test_linha_do_dialogo_depende_do_resultado_do_classico(self):
        caso = comp.Caso('medir_dialogo', None, separar_dialogo=True)
        respostas = {comp.CLASSICO: [execucao('1', positivo=True)], comp.OTIMIZADO: [execucao('1')]}
        com = comp.rodar_caso(caso, None, 'a.png', 0, None, True, self.fazer_rodar(respostas, []))
        self.assertEqual(com.linha, 'medir_dialogo [com dialogo]')
        respostas = {comp.CLASSICO: [execucao('1')], comp.OTIMIZADO: [execucao('1')]}
        sem = comp.rodar_caso(caso, None, 'a.png', 0, None, True, self.fazer_rodar(respostas, []))
        self.assertEqual(sem.linha, 'medir_dialogo [sem dialogo]')


class TestRelatorio(unittest.TestCase):
    def test_tabela_conta_identicos_diferentes_tempos_e_aceleracao(self):
        registros = [
            registro('leitura A', 'um.png', execucao('1', duracao=10.0, positivo=True), execucao('1', duracao=4.0)),
            registro('leitura A', 'dois.png', execucao('1', duracao=6.0), execucao('2', duracao=2.0)),
            registro('leitura B', 'um.png', execucao('1', duracao=3.0), execucao('1', duracao=3.0)),
        ]
        texto = '\n'.join(comp.formatar_relatorio(registros))
        linha_a = next(l for l in texto.splitlines() if l.startswith('leitura A') and '2.67x' in l)
        self.assertEqual(linha_a.split()[-6:], ['2', '1', '1', '16.0', '6.0', '2.67x'])
        self.assertIn('TOTAL', texto)
        self.assertIn('leitura A :: dois.png', texto)
        self.assertIn('DIVERGENCIA', texto)

    def test_tudo_identico(self):
        texto = '\n'.join(comp.formatar_relatorio([registro(), registro(imagem='b.png')]))
        self.assertIn('RESULTADO: TUDO IDENTICO em 2 comparacoes.', texto)
        self.assertIn('nenhuma', texto)

    def test_relatorio_nunca_traz_conteudo_da_captura(self):
        classico = execucao('{"inicial": {"valor": "SEGREDO-1"}}')
        otimizado = execucao('{"inicial": {"valor": "SEGREDO-2"}}')
        texto = '\n'.join(comp.formatar_relatorio([registro('ler_campos', 'x.png', classico, otimizado)]))
        self.assertNotIn('SEGREDO', texto)
        self.assertIn('campos=inicial.valor', texto)

    def test_excecoes_aparecem_so_pela_classe(self):
        classico = execucao(comp.normalizar_excecao(ValueError('SEGREDO')), 'ValueError')
        otimizado = execucao(comp.normalizar_excecao(RuntimeError('SEGREDO')), 'RuntimeError')
        texto = '\n'.join(comp.formatar_relatorio([registro('leitura', 'x.png', classico, otimizado)]))
        self.assertIn('excecao_classico=ValueError excecao_otimizado=RuntimeError', texto)
        self.assertNotIn('SEGREDO', texto)

    def test_ruido_aparece_quando_a_repeticao_muda(self):
        r = registro('leitura', 'x.png', execucao('1'), execucao('2'), repeticao={'ruido_classico': True, 'ruido_otimizado': False})
        texto = '\n'.join(comp.formatar_relatorio([r]))
        self.assertIn('ruido_classico=True ruido_otimizado=False', texto)
        self.assertIn('1 com ruido do proprio OCR', texto)

    def test_memoria_tem_tabela_propria(self):
        r = registro('ler_campos(livros=True) 2a chamada com memoria', 'x.png', execucao('1', duracao=9.0),
                     execucao('1', duracao=1.0), memoria={'gravou': True, 'usou': True})
        texto = '\n'.join(comp.formatar_relatorio([r]))
        self.assertIn('SEGUNDA CHAMADA COM MEMORIA', texto)
        self.assertIn('Memoria gravada pela 1a chamada em 1 de 1 casos; usada pela 2a em 1', texto)
        self.assertNotIn('EQUIVALENCIA E TEMPO POR FUNCAO', texto)

    def test_dialogo_conta_imagens_e_mostra_informativos(self):
        com = registro('medir_dialogo(centro=True) [com dialogo]', 'a.png', execucao('1', positivo=True), execucao('1'),
                       informativos=['arvore_fora_do_recorte_central'])
        sem = registro('medir_dialogo(centro=True) [sem dialogo]', 'b.png')
        texto = '\n'.join(comp.formatar_relatorio([com, sem]))
        self.assertIn('dialogo reconhecido pelo classico em 1 de 2 imagens', texto)
        self.assertIn('arvore inteira dentro do recorte central em 0 de 1', texto)
        self.assertIn('INFORMATIVOS', texto)

    def test_codigo_de_saida(self):
        self.assertEqual(comp.codigo_de_saida([registro()]), 0)
        self.assertEqual(comp.codigo_de_saida([registro(), registro(otimizado=execucao('2'))]), 1)
        desligada = registro(otimizado=execucao('{"x": 1}', desligadas=(('ocr_paralelo', 'RuntimeError'),)))
        self.assertEqual(comp.codigo_de_saida([desligada]), 1)
        self.assertIn('DESLIGADA SOZINHA', '\n'.join(comp.formatar_relatorio([desligada])))

    def test_aceleracao_sem_divisao_por_zero(self):
        self.assertIsNone(comp.aceleracao(5.0, 0.0))
        self.assertEqual(comp.aceleracao(6.0, 3.0), 2.0)


class TestArgumentos(unittest.TestCase):
    def test_padroes(self):
        args = comp.ler_argumentos([])
        self.assertEqual(args.maximo, 12)
        self.assertEqual(args.capturas, comp.CAPTURAS_PADRAO)
        self.assertEqual(args.grupos, list(comp.GRUPOS))
        self.assertFalse(args.sem_repeticao)

    def test_funcoes_aceita_espaco_e_virgula_e_mantem_a_ordem_dos_grupos(self):
        self.assertEqual(comp.ler_argumentos(['--funcoes', 'texto,selecao', 'campos']).grupos,
                         ['selecao', 'campos', 'texto'])
        self.assertEqual(comp.ler_argumentos(['--funcoes', 'todas']).grupos, list(comp.GRUPOS))

    def test_grupo_inexistente_e_maximo_invalido_sao_recusados(self):
        for argumentos in (['--funcoes', 'inexistente'], ['--max', '0']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                comp.ler_argumentos(argumentos)


if __name__ == '__main__':
    unittest.main()
