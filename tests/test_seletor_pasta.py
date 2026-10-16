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
    def __init__(self, raizes=None, drive='Client C (M:\\)', unidades=None, ocultar_lista_ocr=False):
        self.raizes = arvore_destino() if raizes is None else raizes
        self.drive = drive
        self.unidades = list(unidades if unidades is not None else
                             ('Servidor (C:\\)', 'Client C (M:\\)', 'Client Z (Z:\\)'))
        self.indice_combo = self.unidades.index(drive) if drive in self.unidades else 0
        self.ocultar_lista_ocr = ocultar_lista_ocr
        self.foco_combo = False
        self.teclas_combo = []
        self.cliques_combo = 0
        self.inicio_arvore_drives = []
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
        texto_combo = self.unidades[self.indice_combo] if self.foco_combo else self.drive
        imagem, palavras = quadro(drive=texto_combo, pastas=())
        desenho = ImageDraw.Draw(imagem)
        # A estabilidade compara pixels do combo, não apenas os dados OCR simulados.
        desenho.text((108, 81), texto_combo, fill='black')
        if self.combo_aberto:
            desenho.rectangle((100, 101, 480, min(398,111+len(self.unidades[:4])*25)),
                               fill='white', outline='black')
            if self.indice_combo<4:
                y=110+self.indice_combo*25
                desenho.rectangle((110,y,280,y+12),fill='#0078d7')
            if not self.ocultar_lista_ocr:
                for i, texto in enumerate(self.unidades[:4]):
                    palavras.append({'texto': texto, 'x': 110, 'y': 110 + i*25, 'w': 170, 'h': 12})
        else:
            for i, (no, nivel, _) in enumerate(self.linhas()[self.topo:self.topo+4]):
                x, y = 70 + nivel*18, 140 + i*25
                if no is self.selecao:
                    desenho.rectangle((x, y, x + len(no['nome'])*7, y + 12), fill='#0078d7')
                desenho.text((x, y), no['nome'], fill='white' if no is self.selecao else 'black')
                palavras.append({'texto': no['nome'], 'x': x, 'y': y,
                                 'w': len(no['nome'])*7, 'h': 12})
        imagem.info['palavras_sinteticas'] = palavras
        if self.ao_capturar:
            self.ao_capturar()
        return imagem

    def clicar(self, x, y):
        if 345 <= x <= 390 and 310 <= y <= 340:
            self.cliques_ok.append((self.drive, self.caminho_selecionado()))
        elif 100 < x < 480 and 76 < y < 101:
            self.cliques_combo += 1
            self.combo_aberto = not self.combo_aberto
            self.foco_combo = True
            self.foco_arvore = False
        elif self.combo_aberto:
            indice = int((y - 110) // 25)
            if 0 <= indice < len(self.unidades):
                self.indice_combo = indice
                self._aplicar_unidade()
                self.combo_aberto = False
                self.foco_arvore = False
        elif 30 < x < 480 and 110 < y < 290:
            visiveis = self.linhas()[self.topo:self.topo+4]
            candidatos = [(no, linha) for linha, (no, _, _) in enumerate(visiveis)
                          if 135 + linha*25 <= y < 160 + linha*25]
            if candidatos:
                self.selecao = candidatos[0][0]
                self.foco_arvore = True
                self.foco_combo = False
                self.inicio_arvore_drives.append(self.drive)
                self._mostrar_selecao()

    def _aplicar_unidade(self):
        atual = self.unidades[self.indice_combo]
        if atual != self.drive:
            self.unidades_escolhidas.append(atual)
        self.drive = atual

    def tecla(self, tecla):
        if self.foco_combo:
            if tecla not in ('home', 'down', 'tab'):
                raise AssertionError('Combo permite Home/Down/Tab; nunca Enter/Esc/caminho.')
            self.teclas.append(tecla)
            self.teclas_combo.append(tecla)
            if tecla == 'home':
                self.indice_combo = 0
            elif tecla == 'down':
                self.indice_combo = min(self.indice_combo + 1, len(self.unidades)-1)
            else:
                self._aplicar_unidade()
                self.combo_aberto = False
                self.foco_combo = False
                self.foco_arvore = True
            return
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
    def executar(self, arvore, destino=DESTINO):
        with patch.object(seletor, '_palavras', side_effect=lambda imagem: imagem.info['palavras_sinteticas']), \
             patch.object(seletor.time, 'sleep'):
            return seletor.selecionar_pasta(destino, arvore.capturar, arvore.clicar, arvore.tecla)

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
        self.assertGreater(arvore.teclas.count('down'), 0)  # projeto ainda começa fora do viewport
        self.assertIn('right', arvore.teclas)

    def test_perfil_ja_expandido_e_destino_abaixo_da_tela(self):
        arvore = ArvoreSintetica()
        perfil = arvore.raizes[1]['filhos'][1]
        arvore.selecao = perfil
        self.assertTrue(perfil['aberta'])
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)

    def test_users_visivel_na_raiz_dispensa_down_ate_confirmar_users(self):
        arvore = ArvoreSintetica()
        clicar, tecla = arvore.clicar, arvore.tecla
        users_confirmado = [False]
        def selecionar(x, y):
            clicar(x, y)
            if arvore.caminho_selecionado() == ('Users',):
                users_confirmado[0] = True
        def navegar(tecla_enviada):
            if tecla_enviada == 'down' and not users_confirmado[0]:
                raise AssertionError('Down não responde antes de selecionar Users visível.')
            tecla(tecla_enviada)
        arvore.clicar, arvore.tecla = selecionar, navegar
        self.assertTrue(self.executar(arvore))
        self.assertTrue(users_confirmado[0])
        self.assert_destino_unico(arvore)
        self.assertIn('down', arvore.teclas)  # rolagem ainda necessária dentro do perfil

    def test_homonimo_visivel_apos_outro_ancestral_nao_recebe_clique(self):
        falso = pasta('Outro', [pasta('usuario', [pasta('dominio-automation-engine', [
            pasta('saida', [pasta(FOLHA)])])])], aberta=True)
        arvore = ArvoreSintetica([pasta('Users', [pasta('Public')], aberta=True), falso])
        clicar = arvore.clicar
        selecionadas = []
        def selecionar(x, y):
            clicar(x, y)
            selecionadas.append(arvore.caminho_selecionado())
        arvore.clicar = selecionar
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertNotIn(('Outro', 'usuario'), selecionadas)
        self.assertEqual(arvore.cliques_ok, [])

    def test_clique_users_ignorado_nao_envia_right_nem_ok(self):
        arvore = ArvoreSintetica()
        clicar = arvore.clicar
        ignorados = []
        def selecionar(x, y):
            visiveis = arvore.linhas()[arvore.topo:arvore.topo+4]
            if any(caminho == ('Users',) and 135+i*25 <= y < 160+i*25
                   for i, (_, _, caminho) in enumerate(visiveis)):
                ignorados.append((x, y))
                return
            clicar(x, y)
        arvore.clicar = selecionar
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(len(ignorados), 1)
        self.assertNotIn('right', arvore.teclas)
        self.assertEqual(arvore.cliques_ok, [])

    def test_alvo_visivel_rele_posicao_atual_antes_do_clique(self):
        arvore = ArvoreSintetica()
        clicar = Mock(wraps=arvore.clicar)
        with patch.object(seletor, '_palavras', side_effect=lambda imagem: imagem.info['palavras_sinteticas']), \
             patch.object(seletor.time, 'sleep'):
            imagem = arvore.capturar()
            detalhes = seletor.medir_dialogo(imagem)
            atual = seletor._no_selecionado(imagem, detalhes)
            antigo = seletor._alvo_visivel(detalhes, atual, 'Users')['posicao']
            arvore.raizes.insert(1, pasta('Pasta nova'))
            resultado = seletor._selecionar_visivel(arvore.capturar, clicar, 'M',
                                                   (imagem, detalhes, atual), 'Users', 0)
        self.assertIsNotNone(resultado)
        clicar.assert_called_once()
        self.assertNotEqual(clicar.call_args.args, antigo)
        self.assertEqual(arvore.caminho_selecionado(), ('Users',))

    def test_cancelamento_apos_reler_alvo_visivel_impede_clique(self):
        arvore = ArvoreSintetica()
        controle = ControleExecucao()
        clicar = Mock(wraps=arvore.clicar)
        with patch.object(seletor, '_palavras', side_effect=lambda imagem: imagem.info['palavras_sinteticas']):
            imagem = arvore.capturar()
            detalhes = seletor.medir_dialogo(imagem)
            atual = seletor._no_selecionado(imagem, detalhes)
            alvo = seletor._alvo_visivel
            chamadas = [0]
            def cancelar_na_releitura(*args):
                resultado = alvo(*args)
                chamadas[0] += 1
                if chamadas[0] == 2:
                    controle.interromper('teste')
                return resultado
            with patch.object(seletor, '_alvo_visivel', side_effect=cancelar_na_releitura), \
                 controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
                seletor._selecionar_visivel(arvore.capturar, clicar, 'M',
                                           (imagem, detalhes, atual), 'Users', 0)
        clicar.assert_not_called()
        self.assertEqual(arvore.cliques_ok, [])

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

    def test_combo_teclado_sem_ocr_da_lista_aplica_client_c_antes_da_arvore(self):
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True)
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertIn('home', arvore.teclas_combo)
        self.assertIn('down', arvore.teclas_combo)
        self.assertIn('tab', arvore.teclas_combo)
        self.assertTrue(arvore.inicio_arvore_drives)
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})

    def test_client_c_ja_correto_nao_reabre_combo(self):
        arvore = ArvoreSintetica(ocultar_lista_ocr=True)
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertEqual(arvore.cliques_combo, 0)
        self.assertEqual(arvore.teclas_combo, [])

    def test_client_z_com_letra_esperada_nao_substitui_client_c(self):
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True,
            unidades=('Servidor (C:\\)', 'Client Z (M:\\)', 'Client C (M:\\)'))
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})
        self.assertGreaterEqual(arvore.teclas_combo.count('down'), 2)

    def test_unidade_ausente_bloqueia_sem_explorar_arvore_ou_clicar_ok(self):
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True,
            unidades=('Servidor (C:\\)', 'Client Z (Z:\\)'))
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertLessEqual(arvore.teclas_combo.count('down'), 40)

    def test_combo_tem_limite_antes_de_client_c_fora_do_limite(self):
        unidades = ['Servidor (C:\\)'] + [f'Volume {i}' for i in range(45)] + ['Client C (M:\\)']
        arvore = ArvoreSintetica(drive=unidades[0], unidades=unidades, ocultar_lista_ocr=True)
        # OCR está simulado neste TreeView; não acionar Tesseract para os
        # nomes fictícios Volume, usados somente para testar o limite.
        with patch.object(seletor,'_refinar_unidade',side_effect=lambda img,ps,combo:ps), \
             self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_ok, [])
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertLessEqual(arvore.teclas_combo.count('down'), 40)

    def test_letra_configurada_nao_e_substituida_pelo_padrao_m(self):
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True,
            unidades=('Servidor (C:\\)', 'Client C (M:\\)', 'Client C (Q:\\)'))
        self.assertTrue(self.executar(arvore, destino=DESTINO.replace('M:', 'Q:', 1)))
        self.assertEqual(arvore.cliques_ok, [('Client C (Q:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (Q:\\)'})

    def test_cancelamento_apos_down_do_combo_nao_aplica_nem_clica_ok(self):
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True)
        controle = ControleExecucao()
        tecla = arvore.tecla
        def interromper(tecla_enviada):
            era_combo = arvore.foco_combo
            tecla(tecla_enviada)
            if era_combo and tecla_enviada == 'down':
                controle.interromper('teste')
        arvore.tecla = interromper
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar(arvore)
        self.assertEqual(arvore.teclas_combo[-1], 'down')
        self.assertEqual(arvore.drive, 'Servidor (C:\\)')
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_captura_atrasada_do_combo_nao_repete_down_nem_pula_client_c(self):
        referencia = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True)
        self.assertTrue(self.executar(referencia))
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True)
        capturar, tecla = arvore.capturar, arvore.tecla
        pendentes = []
        def enviar(tecla_enviada):
            era_combo = arvore.foco_combo
            anterior = capturar()
            tecla(tecla_enviada)
            if era_combo and tecla_enviada == 'down':
                pendentes.extend((anterior, anterior.copy()))
        def captura_atrasada():
            return pendentes.pop(0) if pendentes else capturar()
        arvore.tecla, arvore.capturar = enviar, captura_atrasada
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertEqual(arvore.teclas_combo, referencia.teclas_combo)

    def test_tokenizacao_ocr_diferente_sem_mudar_pixels_nao_prova_down_aplicado(self):
        referencia = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True)
        self.assertTrue(self.executar(referencia))
        arvore = ArvoreSintetica(drive='Servidor (C:\\)', ocultar_lista_ocr=True)
        capturar, clicar, tecla = arvore.capturar, arvore.clicar, arvore.tecla
        anterior_fechado, pendentes = [], []

        def focar(x, y):
            if 100 < x < 480 and 76 < y < 101:
                anterior_fechado[:] = [capturar()]
            clicar(x, y)

        def enviar(tecla_enviada):
            era_combo = arvore.foco_combo
            tecla(tecla_enviada)
            if era_combo and tecla_enviada == 'down':
                original = anterior_fechado[0]
                atrasada = original.copy()
                palavras = original.info['palavras_sinteticas']
                dentro = [p for p in palavras if 100 < p['x'] < 480 and 76 < p['y'] < 101]
                # A mesma legenda passa de dois tokens para um token. A imagem
                # continua sendo o quadro antigo do combo fechado, pixel a pixel.
                self.assertGreater(len(dentro), 1)
                atrasada.info['palavras_sinteticas'] = [p for p in palavras if p not in dentro] + [{
                    'texto': ' '.join(p['texto'] for p in dentro), 'x': 108, 'y': 81,
                    'w': 170, 'h': 12}]
                self.assertEqual(atrasada.tobytes(), original.tobytes())
                pendentes.extend((atrasada, atrasada.copy()))

        def captura_atrasada():
            return pendentes.pop(0) if pendentes else capturar()

        arvore.clicar, arvore.tecla, arvore.capturar = focar, enviar, captura_atrasada
        self.assertTrue(self.executar(arvore))
        self.assert_destino_unico(arvore)
        self.assertEqual(arvore.teclas_combo, referencia.teclas_combo)

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


class TestCacheLeituraDialogo(unittest.TestCase):
    def test_pixels_iguais_leem_ocr_uma_vez_e_nova_espera_rele(self):
        for tipo in ('dialogo', 'unidade'):
            with self.subTest(tipo=tipo):
                imagem, palavras = quadro()
                capturar = Mock(return_value=imagem)
                with patch.object(seletor, '_palavras', return_value=palavras) as ocr, \
                     patch.object(seletor.time, 'sleep'):
                    def esperar():
                        if tipo == 'dialogo':
                            return seletor._aguardar_dialogo(capturar, estavel=True)
                        return seletor._aguardar_unidade(capturar)
                    esperar()
                    self.assertEqual(capturar.call_count, 2)
                    self.assertEqual(ocr.call_count, 1)
                    esperar()
                    self.assertEqual(capturar.call_count, 4)
                    self.assertEqual(ocr.call_count, 2)

    def test_pixels_mudaram_reavaliam_dialogo_mesmo_sem_mudar_rotulos(self):
        imagem, palavras = quadro()
        diferente = imagem.copy()
        diferente.putpixel((35, 115), (0, 0, 0))  # área da árvore também deve estabilizar
        capturar = Mock(side_effect=[imagem, diferente, diferente])
        with patch.object(seletor, '_palavras', return_value=palavras) as ocr, \
             patch.object(seletor.time, 'sleep'):
            final, _ = seletor._aguardar_dialogo(capturar, estavel=True)
        self.assertIs(final, diferente)
        self.assertEqual(capturar.call_count, 3)
        self.assertEqual(ocr.call_count, 2)


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
