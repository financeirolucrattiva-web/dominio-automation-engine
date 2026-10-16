"""Percurso público sintético: unidade, barra física, cadeia e OK exclusivo."""
import contextlib
import io
import unittest
from unittest.mock import patch
from PIL import ImageDraw

from app import arvore_raiz as raiz, seletor_pasta as seletor
from app.controle_execucao import ControleExecucao, ExecucaoInterrompida, controlar_execucao
from test_seletor_pasta import DESTINO, FOLHA, arvore_destino, pasta
from test_unidade_pasta_sincronizacao import ArvoreAssincrona


class PercursoComBarra(ArvoreAssincrona):
    def __init__(self, **kwargs):
        raizes = [pasta('Raiz ' + str(i)) for i in range(5)] + arvore_destino()[1:]
        self.rolagem_manual = False
        self.users_confirmado = False
        self.cliques_barra = []
        super().__init__(raizes=raizes, **kwargs)

    def _mostrar_selecao(self):
        if not self.rolagem_manual:
            super()._mostrar_selecao()

    def capturar(self):
        imagem = super().capturar()
        if not self.combo_aberto:
            d = ImageDraw.Draw(imagem)
            d.rectangle((460, 111, 478, 289), fill='#eeeeee', outline='#808080')
            d.rectangle((460, 269, 478, 289), fill='#eeeeee', outline='#808080')
            d.polygon((465, 276, 473, 276, 469, 282), fill='black')
        return imagem

    def clicar(self, x, y):
        if 460 <= x <= 478 and 269 <= y <= 289:
            if self.drive != 'Client C (M:\\)' or self.combo_aberto:
                raise AssertionError('Barra antes de confirmar a unidade fechada.')
            anterior = self.selecao
            self.cliques_barra.append((self.drive, x, y))
            self.rolagem_manual = True
            self.topo += 2
            assert self.selecao is anterior  # Rolar não seleciona a pasta visível.
            return
        if self.rolagem_manual and 30 < x < 450 and 110 < y < 290:
            self.rolagem_manual = False
        super().clicar(x, y)
        if self.selecao is not None and self.selecao['nome'] == 'Users':
            self.users_confirmado = True

    def tecla(self, tecla):
        if not self.foco_combo and tecla == 'down' and not self.users_confirmado:
            raise AssertionError('Down na árvore antes de localizar Users pela barra.')
        super().tecla(tecla)


class TestPercursoUnidadeBarra(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(seletor.time, 'sleep'))
        self.stack.enter_context(patch.object(seletor, '_palavras',
            side_effect=lambda imagem: imagem.info['palavras_sinteticas']))
        self.stack.enter_context(patch.object(raiz, 'localizar_raiz', side_effect=self.users_visivel))

    @staticmethod
    def users_visivel(imagem, detalhes, nome, coluna, altura):
        alvos = [n for n in seletor._nos(detalhes)
                 if n['nome'] == 'users' and abs(n['x'] - coluna) <= 2]
        return dict(alvos[0], tolerancia=4.8) if len(alvos) == 1 else None

    def executar(self, arvore):
        return seletor.selecionar_pasta(DESTINO, arvore.capturar, arvore.clicar, arvore.tecla)

    def test_servidor_client_m_barra_users_cadeia_e_um_ok(self):
        arvore = PercursoComBarra()
        self.assertNotIn('Users', [p['texto'] for p in arvore.capturar().info['palavras_sinteticas']])
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.prematuros, [])
        self.assertEqual(len(arvore.cliques_barra), 1)
        self.assertEqual(arvore.cliques_barra[0][0], 'Client C (M:\\)')
        self.assertTrue(arvore.users_confirmado)
        self.assertIn('down', arvore.enviados_combo)
        self.assertEqual(arvore.cliques_ok, [('Client C (M:\\)',
            ('Users', 'usuario', 'dominio-automation-engine', 'saida', FOLHA))])

    def test_unidade_sem_abrir_nao_clica_barra_arvore_ou_ok(self):
        arvore = PercursoComBarra(abre=False)
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_barra, [])
        self.assertEqual(arvore.inicio_arvore_drives, [])
        self.assertEqual(arvore.cliques_ok, [])

    def test_cancelamento_apos_medicao_real_da_seta_impede_clique(self):
        arvore = PercursoComBarra()
        controle = ControleExecucao()
        medir = raiz.medir_seta_baixo
        def medir_e_cancelar(*args, **kwargs):
            barra = medir(*args, **kwargs)
            self.assertIsNotNone(barra)
            controle.interromper('teste')
            return barra
        with patch.object(raiz, 'medir_seta_baixo', side_effect=medir_e_cancelar), \
             controlar_execucao(controle), self.assertRaises(ExecucaoInterrompida):
            self.executar(arvore)
        self.assertEqual(arvore.cliques_barra, [])
        self.assertFalse(arvore.users_confirmado)
        self.assertEqual(arvore.cliques_ok, [])


if __name__ == '__main__':
    unittest.main()
