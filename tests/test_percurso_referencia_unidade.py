"""Percurso público com OCR malformado no campo e referência RGB local."""
import contextlib
import io
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest.mock import patch
from PIL import ImageDraw

from app import referencia_unidade as ref, seletor_pasta as seletor
from test_seletor_pasta import ArvoreSintetica, FOLHA, pasta


class ArvoreComCampoIlegivel(ArvoreSintetica):
    def __init__(self, drive='Servidor (C:\\)'):
        # Quantidades diferentes das observadas pelo operador: o alvo é
        # encontrado por nome/nível, nunca pelo número de eventos Down.
        raizes=[pasta('Arquivo%02d'%i) for i in range(19)]+[
            pasta('Users',[pasta('Public'),pasta('perfil-novo',[
                *[pasta('Pasta%02d'%i) for i in range(33)],
                pasta('ProjetoNovo',[pasta('outros'),pasta('destino',[pasta(FOLHA)])])])]),
            pasta('Windows')]
        super().__init__(raizes=raizes,drive=drive)
        self.foco_combo=True
        self.cliques_vazio=0

    def capturar(self):
        im=super().capturar()
        if self.drive!='Servidor (C:\\)':
            ps=[p for p in im.info['palavras_sinteticas']
                if not (100<p['x']<481 and 76<p['y']<101)]
            ps.append({'texto':'lient C (M:N)','x':108,'y':81,'w':110,'h':12})
            im.info['palavras_sinteticas']=ps
        if self.foco_combo:
            d=ImageDraw.Draw(im)
            d.rectangle((108,80,250,96),fill='#0078d7')
            d.text((108,81),self.drive,fill='white')
        return im

    def clicar(self,x,y):
        if 30<x<480 and 110<y<290 and self.foco_combo:
            self.cliques_vazio+=1
            self.foco_combo=False; self.foco_arvore=True
        super().clicar(x,y)

    def tecla(self,tecla):
        if self.foco_combo and not self.combo_aberto and tecla=='down':
            # Atalho real observado: Down aplica no combo fechado.
            self.teclas.append(tecla); self.teclas_combo.append(tecla)
            self.indice_combo=min(self.indice_combo+1,len(self.unidades)-1)
            self._aplicar_unidade()
            return
        super().tecla(tecla)


DESTINO='M:\\Users\\perfil-novo\\ProjetoNovo\\destino\\'+FOLHA


class TestPercursoReferencia(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        tmp=self.stack.enter_context(tempfile.TemporaryDirectory())
        self.arquivo=Path(tmp)/'referencia.json'
        self.stack.enter_context(patch.object(ref,'ARQUIVO',self.arquivo))
        self.stack.enter_context(patch.object(seletor,'_palavras',
            side_effect=lambda im:im.info['palavras_sinteticas']))
        self.stack.enter_context(patch.object(seletor,'_refinar_unidade',side_effect=lambda im,ps,c:ps))
        self.stack.enter_context(patch.object(seletor.time,'sleep'))
        self.saida=io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.saida))
        fonte=ArvoreComCampoIlegivel('Client C (M:\\)'); fonte.foco_combo=False
        ref.gravar(fonte.capturar(),(100,76,381,25),'M')

    def executar(self,arvore):
        return seletor.selecionar_pasta(DESTINO,arvore.capturar,arvore.clicar,arvore.tecla)

    def test_servidor_down_foco_referencia_pastas_configuradas_e_ok_unico(self):
        arvore=ArvoreComCampoIlegivel()
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.teclas_combo,['down'])
        self.assertEqual(arvore.cliques_vazio,1)
        self.assertEqual(arvore.cliques_combo,0)
        self.assertEqual(arvore.cliques_ok,[('Client C (M:\\)',PureWindowsPath(DESTINO).parts[1:])])
        self.assertIn('calibracao_visual_local',self.saida.getvalue())

    def test_m_visual_ja_aplicado_exige_duas_capturas_novas_sem_down_no_combo(self):
        arvore=ArvoreComCampoIlegivel('Client C (M:\\)'); arvore.foco_combo=False
        self.assertTrue(self.executar(arvore))
        self.assertEqual(arvore.teclas_combo,[])
        self.assertEqual(arvore.cliques_vazio,0)
        self.assertIn('"capturas": 2',self.saida.getvalue())
        self.assertEqual(len(arvore.cliques_ok),1)

    def test_m_visual_em_uma_captura_nao_libera_arvore_quando_unidade_muda(self):
        arvore=ArvoreComCampoIlegivel('Client C (M:\\)'); arvore.foco_combo=False
        def mudar():
            if arvore.capturas==1:
                arvore.drive='Client C (Q:\\)'
        arvore.ao_capturar=mudar
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):self.executar(arvore)
        self.assertEqual(arvore.inicio_arvore_drives,[])
        self.assertEqual(arvore.teclas,[])
        self.assertEqual(arvore.cliques_ok,[])

    def test_sem_referencia_nao_repete_clique_nem_navega_apos_campo_ilegivel(self):
        self.arquivo.unlink()
        arvore=ArvoreComCampoIlegivel()
        with self.assertRaises(seletor.SeletorPastaNaoConfirmado):self.executar(arvore)
        self.assertEqual(arvore.teclas_combo,['down'])
        self.assertEqual(arvore.cliques_vazio,1)
        self.assertEqual(arvore.cliques_ok,[])
        self.assertNotIn('home',arvore.teclas)


if __name__=='__main__':unittest.main()
