"""Latência remota sintética do combo; nenhuma interação com desktop real."""
import contextlib
import io
import unittest
from unittest.mock import patch
from PIL import ImageDraw

from app import seletor_pasta as seletor
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao
from test_seletor_pasta import ArvoreSintetica, DESTINO, FOLHA, quadro


class ArvoreAssincrona(ArvoreSintetica):
    """Foco, valor e fechamento só aparecem após novas capturas remotas."""
    def __init__(self, *, abre=True, fecha=True, oscilar_arvore=False,
                 cancelar_apos_down=None, drive='Servidor (C:\\)', atraso_home=0,
                 **kwargs):
        super().__init__(drive=drive, ocultar_lista_ocr=True, **kwargs)
        self.abre, self.fecha = abre, fecha
        self.oscilar_arvore = oscilar_arvore
        self.cancelar_apos_down = cancelar_apos_down
        self.atraso_home = atraso_home
        self.pendentes = []
        self.prematuros = []
        self.aplicados = []
        self.enviados_combo = []
        self.frames_antigos = {'abrir': 0, 'home': 0, 'down': 0, 'fechar': 0}

    def agendar(self, nome, atraso, acao):
        self.pendentes.append([nome, atraso, acao])

    def capturar(self):
        for evento in list(self.pendentes):
            nome, restante, acao = evento
            if restante:
                evento[1] -= 1
                self.frames_antigos[nome] += 1
            else:
                self.pendentes.remove(evento)
                acao()
                self.aplicados.append(nome)
        imagem = super().capturar()
        if self.oscilar_arvore:
            imagem.putpixel((55, 270), (self.capturas % 2, 0, 0))
        return imagem

    def clicar(self, x, y):
        if 100 < x < 480 and 76 < y < 101:
            if self.pendentes:
                self.prematuros.append('clique_combo_com_acao_pendente')
                return
            if self.abre:
                clicar_base = super().clicar
                self.agendar('abrir', 2, lambda: clicar_base(x, y))
            return
        if self.combo_aberto or self.pendentes:
            self.prematuros.append('clique_fora_com_lista_aberta_ou_acao_pendente')
            return
        super().clicar(x, y)

    def tecla(self, tecla):
        aguardando_abertura = any(e[0] == 'abrir' for e in self.pendentes)
        if aguardando_abertura or (not self.abre and not self.foco_arvore):
            self.prematuros.append('tecla_antes_da_abertura:' + tecla)
            return
        if self.foco_combo:
            self.enviados_combo.append(tecla)
            if self.pendentes:
                self.prematuros.append('tecla_com_acao_pendente:' + tecla)
                return
            enviar_base = super().tecla
            if tecla == 'home' and self.atraso_home:
                self.agendar('home', self.atraso_home, lambda: enviar_base(tecla))
            elif tecla == 'down':
                self.agendar('down', 3, lambda: enviar_base(tecla))
                if self.cancelar_apos_down:
                    self.cancelar_apos_down.interromper('teste')
            elif tecla == 'tab':
                if self.fecha:
                    self.agendar('fechar', 3, lambda: enviar_base(tecla))
            else:
                enviar_base(tecla)
            return
        super().tecla(tecla)


class ArvoreCampoAplicadoDepois(ArvoreAssincrona):
    """Realce muda no popup; o campo só atualiza depois de Tab + dois frames."""
    def __init__(self):
        super().__init__()
        self.campo_exibido = self.drive
        self.atraso_campo = 0
        self.frames_campo_antigo = 0

    def agendar(self, nome, atraso, acao):
        if nome == 'fechar':
            aplicar = acao
            def acao():
                aplicar()
                self.atraso_campo = 2 if self.campo_exibido != self.drive else 0
        super().agendar(nome, atraso, acao)

    def capturar(self):
        imagem = super().capturar()
        desenho = ImageDraw.Draw(imagem)
        desenho.rectangle((101, 77, 479, 99), fill='white')
        desenho.text((108, 81), self.campo_exibido, fill='black')
        _, palavras_campo = quadro(drive=self.campo_exibido, pastas=())
        dentro = lambda p: 100 < p['x'] < 481 and 76 < p['y'] < 101
        imagem.info['palavras_sinteticas'] = [p for p in imagem.info['palavras_sinteticas']
            if not dentro(p)] + [p for p in palavras_campo if dentro(p)]
        if not self.combo_aberto and self.atraso_campo:
            self.frames_campo_antigo += 1
            self.atraso_campo -= 1
            if not self.atraso_campo:
                self.campo_exibido = self.drive
        return imagem

    def clicar(self, x, y):
        if not (100 < x < 480 and 76 < y < 101) and self.campo_exibido != self.drive:
            self.prematuros.append('clique_antes_do_campo_atualizar')
            return
        super().clicar(x, y)


class ArvorePopupRolavel(ArvoreAssincrona):
    """Quatro opções visíveis; ao rolar, o realce permanece na última linha."""
    def capturar(self):
        imagem = super().capturar()
        if self.combo_aberto:
            d = ImageDraw.Draw(imagem)
            d.rectangle((100, 101, 480, 211), fill='white', outline='black')
            inicio = max(0, self.indice_combo - 3)
            for linha, indice in enumerate(range(inicio, min(inicio+4, len(self.unidades)))):
                y = 110 + linha*25
                selecionada = indice == self.indice_combo
                if selecionada:
                    d.rectangle((110, y, 280, y+12), fill='#0078d7')
                d.text((110, y), self.unidades[indice],
                       fill='white' if selecionada else 'black')
        return imagem


class TestSincronizacaoUnidade(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(seletor.time, 'sleep'))
        self.stack.enter_context(patch.object(seletor, '_palavras',
            side_effect=lambda imagem: imagem.info['palavras_sinteticas']))

    def executar(self, arvore):
        return seletor.selecionar_pasta(DESTINO, arvore.capturar, arvore.clicar, arvore.tecla)

    def test_opcao_muda_com_novos_pixels_no_mesmo_realce_sem_ocr_das_opcoes(self):
        imagens = []
        for texto in ('Client Z (M:\\)', 'Client C (M:\\)'):
            imagem, palavras = quadro(drive='Servidor (C:\\)', pastas=())
            d = ImageDraw.Draw(imagem)
            d.rectangle((100, 101, 480, 211), fill='white', outline='black')
            d.rectangle((110, 185, 280, 197), fill='#0078d7')
            d.text((110, 185), texto, fill='white')
            imagens.append(imagem)
        detalhes = {'combo': (100, 76, 381, 25), 'lista': (100, 101, 381, 111),
                    'palavras': palavras}
        self.assertEqual(seletor._realce_unidade(imagens[0], detalhes),
                         seletor._realce_unidade(imagens[1], detalhes))
        primeira = seletor._opcao_unidade(imagens[0], detalhes)
        self.assertEqual(primeira, seletor._opcao_unidade(imagens[0].copy(), detalhes))
        self.assertNotEqual(primeira, seletor._opcao_unidade(imagens[1], detalhes))

    def test_popup_rola_com_realce_na_mesma_linha_e_so_libera_arvore_em_client_c(self):
        unidades = ('Servidor (C:\\)', 'Volume 0', 'Volume 1', 'Volume 2',
                    'Volume 3', 'Volume 4', 'Client C (M:\\)')
        arvore = ArvorePopupRolavel(unidades=unidades)
        # Os textos do campo vêm do emulador; a lista continua sem OCR.
        with patch.object(seletor, '_refinar_unidade', side_effect=lambda imagem, ps, combo: ps):
            self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.enviados_combo.count('down'), len(unidades)-1)
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])

    def test_abertura_mudanca_e_fechamento_atrasados_preservam_ordem_e_destino(self):
        arvore = ArvoreAssincrona()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])
        self.assertGreaterEqual(arvore.frames_antigos['abrir'], 4)
        self.assertEqual(arvore.frames_antigos['down'], 3)
        self.assertGreaterEqual(arvore.frames_antigos['fechar'], 6)
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})

    def test_abertura_sem_resposta_nao_envia_tecla_nem_explora_arvore(self):
        arvore = ArvoreAssincrona(abre=False)
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.enviados_combo, [])
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_realce_do_popup_muda_mas_campo_antigo_persiste_apos_fechar(self):
        arvore = ArvoreCampoAplicadoDepois()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.frames_campo_antigo, 2)
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})

    def test_home_atrasado_partindo_de_client_z_aguarda_realce_na_primeira_opcao(self):
        arvore = ArvoreAssincrona(drive='Client Z (Z:\\)', atraso_home=3)
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.frames_antigos['home'], 3)
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})

    def test_tab_ignorado_nao_inicia_arvore_nem_envia_ok(self):
        arvore = ArvoreAssincrona(fecha=False)
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertTrue(arvore.combo_aberto)
        self.assertEqual(arvore.enviados_combo, ['home', 'tab'])
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_arvore_com_pixel_oscilando_nao_impede_confirmar_unidade_estavel(self):
        arvore = ArvoreAssincrona(oscilar_arvore=True)
        imagem = arvore.capturar()
        detalhes = seletor.medir_dialogo(imagem)
        imagem, detalhes = seletor._selecionar_unidade(arvore.capturar,
            arvore.clicar, arvore.tecla, 'M', imagem, detalhes)
        self.assertTrue(seletor._drive_selecionado(detalhes, 'M'))
        self.assertFalse(arvore.combo_aberto)
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down', 'tab'])

    def test_client_z_com_mesma_letra_nao_e_confirmado_como_client_c(self):
        arvore = ArvoreAssincrona(unidades=(
            'Servidor (C:\\)', 'Client Z (M:\\)', 'Client C (M:\\)'))
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(set(arvore.inicio_arvore_drives), {'Client C (M:\\)'})
        self.assertEqual(arvore.enviados_combo.count('down'), 2)

    def test_cancelamento_apos_down_nao_aplica_tab_nem_clica_arvore(self):
        controle = ControleExecucao()
        arvore = ArvoreAssincrona(cancelar_apos_down=controle)
        with controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar(arvore)
        self.assertEqual(arvore.enviados_combo, ['home', 'tab', 'down'])
        self.assertEqual(arvore.drive, 'Servidor (C:\\)')
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertEqual(arvore.cliques_ok, [])


if __name__ == '__main__':
    unittest.main()
