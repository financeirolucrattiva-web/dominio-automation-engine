"""Seletor medido em pixels sintéticos, sem supor campo de endereço."""
import unittest
from unittest.mock import Mock,patch
from PIL import Image,ImageDraw
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao
from app import seletor_pasta as seletor


def quadro(drive='Client C (M:\\)',pastas=('dominio-automation-engine','saida','LIVROS123456789012'),selecionar=False,selecionado_indice=None):
    imagem=Image.new('RGB',(600,400),'#eeeeee');d=ImageDraw.Draw(imagem)
    d.rectangle((100,76,480,100),fill='white',outline='black')
    d.rectangle((30,110,480,290),fill='white',outline='black')
    d.rectangle((345,310,395,342),outline='black')
    d.rectangle((405,310,480,342),outline='black')
    palavras=[]
    def linha(texto,x,y):
        for token in texto.split():
            palavras.append({'texto':token,'x':x,'y':y,'w':len(token)*7,'h':12});x+=len(token)*7+5
    linha('Procurar Pasta',30,30);linha('Unidade:',30,81);linha(drive,108,81)
    linha('OK',355,320);linha('Cancelar',415,320)
    for i,nome in enumerate(pastas):
        linha(nome,70+i*18,140+i*25)
    if (selecionar or selecionado_indice is not None) and pastas:
        i=len(pastas)-1 if selecionado_indice is None else selecionado_indice;nome=pastas[i]
        d.rectangle((70+i*18,140+i*25,70+i*18+len(nome)*7,152+i*25),fill='#0078d7')
    return imagem,palavras


class TestSeletor(unittest.TestCase):
    def test_mede_combo_e_arvore_sem_coordenadas_da_instalacao(self):
        imagem,palavras=quadro()
        with patch.object(seletor,'_palavras',return_value=palavras):dados=seletor.medir_dialogo(imagem)
        self.assertEqual(dados['combo'],(100,76,381,25))
        self.assertEqual(dados['arvore'],(30,110,451,181))
        self.assertEqual(dados['ok'],(362,326))

    def test_recusa_nome_reutilizavel(self):
        with self.assertRaises(ValueError):seletor.selecionar_pasta('M:\\saida',Mock(),Mock(),Mock())

    def test_medicao_sem_ok_global_permite_navegar_mas_nao_fornece_confirmacao(self):
        imagem, palavras = quadro()
        palavras = [p for p in palavras if p['texto'] != 'OK']
        with patch.object(seletor, '_palavras', return_value=palavras):
            detalhes = seletor.medir_dialogo(imagem)
        self.assertEqual(detalhes['arvore'], (30, 110, 451, 181))
        self.assertIsNone(detalhes['ok'])


FOLHA = 'LIVROS123456789012'
DESTINO = 'M:\\Users\\usuario\\dominio-automation-engine\\saida\\' + FOLHA


def pasta(nome, filhos=(), aberta=False):
    return {'nome': nome, 'filhos': list(filhos), 'aberta': aberta}


def arvore_destino():
    return [pasta('Arquivos'), pasta('Users', [
        pasta('Public'),
        pasta('usuario', [pasta('AppData'), pasta('Desktop'), pasta('Documents'),
                          pasta('Downloads'), pasta('dominio-automation-engine', [
                              pasta('app'), pasta('saida', [pasta(FOLHA)])])], aberta=True)
    ], aberta=True), pasta('Windows')]


class ArvoreSintetica:
    """TreeView de quatro linhas: teclado e rolagem só mudam o estado sintético."""
    def __init__(self, raizes=None, drive='Client C (M:\\)'):
        self.raizes = arvore_destino() if raizes is None else raizes
        self.drive = drive
        self.selecao = self.raizes[0] if self.raizes else None
        self.topo = 0
        self.combo_aberto = False
        self.foco_arvore = False
        self.teclas = []
        self.cliques_ok = []
        self.unidades_escolhidas = []
        self.capturas = 0
        self.ao_capturar = None

    def linhas(self):
        resultado = []
        def visitar(nos, profundidade, caminho):
            for no in nos:
                atual = caminho + (no['nome'],)
                resultado.append((no, profundidade, atual))
                if no['aberta']:
                    visitar(no['filhos'], profundidade + 1, atual)
        visitar(self.raizes, 0, ())
        return resultado

    def caminho_selecionado(self):
        return next((c for no, _, c in self.linhas() if no is self.selecao), None)

    def _mostrar_selecao(self):
        linhas = self.linhas()
        indice = next((i for i, (no, _, _) in enumerate(linhas) if no is self.selecao), 0)
        if indice < self.topo:
            self.topo = indice
        elif indice >= self.topo + 4:
            self.topo = indice - 3

    def capturar(self):
        self.capturas += 1
        self._mostrar_selecao()
        imagem, palavras = quadro(drive=self.drive, pastas=())
        desenho = ImageDraw.Draw(imagem)
        if self.combo_aberto:
            desenho.rectangle((100, 101, 480, 160), fill='white', outline='black')
            for i, texto in enumerate(('Servidor (C:\\)', 'Client C (M:\\)')):
                palavras.append({'texto': texto, 'x': 110, 'y': 110 + i*25, 'w': 170, 'h': 12})
        else:
            for i, (no, nivel, _) in enumerate(self.linhas()[self.topo:self.topo+4]):
                x, y = 70 + nivel*18, 140 + i*25
                if no is self.selecao:
                    desenho.rectangle((x, y, x + len(no['nome'])*7, y + 12), fill='#0078d7')
                palavras.append({'texto': no['nome'], 'x': x, 'y': y,
                                 'w': len(no['nome'])*7, 'h': 12})
        imagem.info['palavras_sinteticas'] = palavras
        if self.ao_capturar:
            self.ao_capturar()
        return imagem

    def clicar(self, x, y):
        if 345 <= x <= 390 and 310 <= y <= 340:
            self.cliques_ok.append((self.drive, self.caminho_selecionado()))
        elif self.combo_aberto:
            if 130 <= y <= 155:
                self.drive = 'Client C (M:\\)'
                self.unidades_escolhidas.append(self.drive)
                self.combo_aberto = False
                self.foco_arvore = False
        elif 100 < x < 480 and 76 < y < 101:
            self.combo_aberto = True
            self.foco_arvore = False
        elif 30 < x < 480 and 110 < y < 290:
            visiveis = self.linhas()[self.topo:self.topo+4]
            candidatos = [(no, linha) for linha, (no, _, _) in enumerate(visiveis)
                          if 135 + linha*25 <= y <= 160 + linha*25]
            if candidatos:
                self.selecao = candidatos[0][0]
                self.foco_arvore = True
                self._mostrar_selecao()

    def tecla(self, tecla):
        if tecla not in ('home', 'down', 'right', 'left'):
            raise AssertionError('Somente as setas observadas e Home são permitidos.')
        if not self.foco_arvore:
            raise AssertionError('Teclado só depois de confirmar foco na árvore.')
        self.teclas.append(tecla)
        linhas = self.linhas()
        indice = next(i for i, (no, _, _) in enumerate(linhas) if no is self.selecao)
        if tecla == 'home':
            self.selecao = linhas[0][0]
        elif tecla == 'down':
            self.selecao = linhas[min(indice + 1, len(linhas)-1)][0]
        elif tecla == 'right':
            if self.selecao['filhos']:
                if self.selecao['aberta']:
                    self.selecao = self.selecao['filhos'][0]
                else:
                    self.selecao['aberta'] = True
        elif tecla == 'left':
            if self.selecao['aberta'] and self.selecao['filhos']:
                self.selecao['aberta'] = False
            else:
                profundidade = linhas[indice][1]
                for no, nivel, _ in reversed(linhas[:indice]):
                    if nivel < profundidade:
                        self.selecao = no
                        break
        self._mostrar_selecao()


class TestNavegacaoTeclado(unittest.TestCase):
    def executar(self, arvore):
        with patch.object(seletor, '_palavras', side_effect=lambda imagem: imagem.info['palavras_sinteticas']), \
             patch.object(seletor.time, 'sleep'):
            return seletor.selecionar_pasta(DESTINO, arvore.capturar, arvore.clicar, arvore.tecla)

    def assert_destino_unico(self, arvore):
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])
        self.assertIn('home', arvore.teclas)

    def test_destino_fora_da_area_visivel_percorre_teclado_e_confirma_cadeia(self):
        arvore = ArvoreSintetica()
        inicial = arvore.capturar()
        self.assertNotIn('dominio-automation-engine', [p['texto'] for p in inicial.info['palavras_sinteticas']])
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertGreater(arvore.teclas.count('down'), 3)
        self.assertIn('right', arvore.teclas)

    def test_perfil_ja_expandido_e_destino_abaixo_da_tela(self):
        arvore = ArvoreSintetica()
        perfil = arvore.raizes[1]['filhos'][1]
        arvore.selecao = perfil
        self.assertTrue(perfil['aberta'])
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)

    def test_homonimo_em_ramo_expandido_errado_nao_comprova_caminho(self):
        arvore = ArvoreSintetica()
        falso = pasta('Public', [pasta('usuario', [pasta('dominio-automation-engine', [
            pasta('saida', [pasta(FOLHA)], aberta=True)], aberta=True)], aberta=True)], aberta=True)
        arvore.raizes[1]['filhos'][0] = falso
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertIn('left', arvore.teclas)

    def test_ancestral_ausente_nao_usa_users_aninhado_em_outra_raiz(self):
        arvore = ArvoreSintetica([pasta('Arquivo', arvore_destino(), aberta=True), pasta('Windows')])
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])
        self.assertLessEqual(len(arvore.teclas), 500)

    def test_filho_ausente_recusa_pasta_homonima_de_nivel_mais_profundo(self):
        arvore = ArvoreSintetica()
        perfil = arvore.raizes[1]['filhos'][1]
        perfil['filhos'] = [pasta('arquivo', [pasta('dominio-automation-engine', [
            pasta('saida', [pasta(FOLHA)], aberta=True)], aberta=True)], aberta=True)]
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])
        self.assertLessEqual(len(arvore.teclas), 500)

    def test_seleciona_client_c_antes_de_navegar(self):
        arvore = ArvoreSintetica(drive='Servidor (C:\\)')
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.unidades_escolhidas, ['Client C (M:\\)'])
        self.assert_destino_unico(arvore)

    def test_folha_ausente_nao_envia_ok_no_pai(self):
        arvore = ArvoreSintetica()
        projeto = arvore.raizes[1]['filhos'][1]['filhos'][-1]
        projeto['filhos'][-1]['filhos'] = [pasta('LIVROS000000000000')]
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])

    def test_sem_ok_lido_navega_mas_nao_confirma_pasta_as_cegas(self):
        arvore = ArvoreSintetica()
        with patch.object(seletor, '_palavras', side_effect=lambda imagem: [
                p for p in imagem.info['palavras_sinteticas'] if p['texto'] != 'OK']), \
             patch.object(seletor.time, 'sleep'):
            with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
                seletor.selecionar_pasta(DESTINO, arvore.capturar, arvore.clicar, arvore.tecla)
        self.assertIn('home', arvore.teclas)
        self.assertEqual(arvore.caminho_selecionado(),
                         ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))
        self.assertEqual(arvore.cliques_ok, [])

    def test_cancelamento_apos_selecionar_folha_nao_envia_ok(self):
        arvore = ArvoreSintetica()
        controle = ControleExecucao()
        def interromper_na_folha():
            if arvore.caminho_selecionado() == ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA):
                controle.interromper('teste')
        arvore.ao_capturar = interromper_na_folha
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])

    def test_sem_selecao_azul_nao_navega_ou_confirma(self):
        arvore = ArvoreSintetica()
        capturar = arvore.capturar
        def sem_azul():
            imagem = capturar()
            desenho = ImageDraw.Draw(imagem)
            desenho.rectangle((31, 111, 479, 289), fill='white')
            return imagem
        arvore.capturar = sem_azul
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])

    def test_capturas_transitorias_repetem_leitura_sem_repetir_tecla(self):
        referencia = ArvoreSintetica()
        self.assertTrue(self.executar(referencia))
        arvore = ArvoreSintetica()
        capturar, tecla = arvore.capturar, arvore.tecla
        pendentes = [0]

        def enviar(tecla_enviada):
            tecla(tecla_enviada)
            pendentes[0] = 2

        def captura_transitoria():
            imagem = capturar()
            if pendentes[0]:
                pendentes[0] -= 1
                ImageDraw.Draw(imagem).rectangle((31, 111, 479, 289), fill='white')
            return imagem

        arvore.tecla, arvore.capturar = enviar, captura_transitoria
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertEqual(arvore.teclas, referencia.teclas)
        self.assertGreater(arvore.capturas, referencia.capturas)

    def test_captura_anterior_apos_right_nao_pula_primeiro_filho(self):
        arvore = ArvoreSintetica()
        users = arvore.raizes[1]
        perfil = users['filhos'][1]
        users['filhos'] = [perfil, pasta('zz-outro-perfil')]
        capturar, tecla = arvore.capturar, arvore.tecla
        pendentes = []

        def enviar(tecla_enviada):
            anterior = capturar()
            tecla(tecla_enviada)
            if tecla_enviada == 'right':
                pendentes.append(anterior)

        def captura_atrasada():
            return pendentes.pop(0) if pendentes else capturar()

        arvore.tecla, arvore.capturar = enviar, captura_atrasada
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)

    def test_glyph_da_arvore_fora_da_selecao_nao_entra_no_nome_azul(self):
        arvore = ArvoreSintetica()
        capturar = arvore.capturar

        def captura_com_glyph():
            imagem = capturar()
            palavras = imagem.info['palavras_sinteticas']
            palavras.extend({'texto': '+', 'x': p['x'] - 12, 'y': p['y'], 'w': 8, 'h': p['h']}
                            for p in list(palavras) if 110 < p['y'] < 290)
            return imagem

        arvore.capturar = captura_com_glyph
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)

    def test_limite_por_nivel_interrompe_antes_de_pasta_fora_do_limite(self):
        arvore = ArvoreSintetica([pasta('pasta' + str(i)) for i in range(170)] + arvore_destino())
        with self.assertRaisesRegex(seletor.SeletorPastaNaoConfirmado, 'Limite'):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])
        self.assertLessEqual(len(arvore.teclas), 162)

    def test_cancelamento_no_checkpoint_final_impede_clique_ok(self):
        arvore = ArvoreSintetica()
        controle = ControleExecucao()
        localizar_ok = seletor._ok_final

        def cancelar_apos_conferir_botao(imagem, detalhes):
            posicao = localizar_ok(imagem, detalhes)
            if posicao is not None:
                controle.interromper('teste')
            return posicao

        with patch.object(seletor, '_ok_final', side_effect=cancelar_apos_conferir_botao), \
             controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar(arvore)
        self.assertEqual(arvore.caminho_selecionado(),
                         ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))
        self.assertEqual(arvore.cliques_ok, [])


class TestUnidadeClientC(unittest.TestCase):
    def test_lista_de_unidades_real_so_casa_client_c_mesmo_com_barra_mal_lida(self):
        def linhas(*textos):
            return [{'texto': t, 'x': 10.0, 'y': 20.0 + 25*i, 'w': 40.0, 'h': 10.0} for i, t in enumerate(textos)]
        for lida in (r'Client C (M:\)', 'Client C (M:/)', 'Client C (M:|)', 'Client C (M:)', r'client c (m :\ )'):
            with self.subTest(lida):
                palavras = linhas(r'Servidor (C:\)', lida, r'Client Z \server\LUCRATTIVA\ (Z:\)')
                self.assertIsNotNone(seletor._drive(palavras, 'M'))
        # Sem Client C (só Servidor e Client Z), não escolhe nenhuma.
        self.assertIsNone(seletor._drive(linhas(r'Servidor (C:\)', r'Client Z \server\LUCRATTIVA\ (Z:\)'), 'M'))


if __name__=='__main__':unittest.main()
