"""Ponto de foco medido na árvore, sem mouse ou desktop real."""
import unittest
from PIL import Image,ImageDraw
from app.foco_seletor import localizar_vazio,confirmar_vazio


class TestFocoSeletor(unittest.TestCase):
    def setUp(self):
        self.imagem=Image.new('RGB',(640,420),'#eeeeee')
        self.detalhes={'combo':(100,50,470,20),'arvore':(30,90,540,240),'lista':None}
        d=ImageDraw.Draw(self.imagem)
        d.rectangle((31,91,549,328),fill='white')
        d.rectangle((550,91,569,328),fill='#cccccc')
        for y in range(100,300,18):d.text((70,y),'Pasta da arvore',fill='black')

    def test_ponto_atual_e_branco_e_fica_fora_da_barra_bordas_e_texto(self):
        c=localizar_vazio(self.imagem,self.detalhes)
        self.assertIsNotNone(c)
        self.assertTrue(confirmar_vazio(self.imagem,self.detalhes,c))
        self.assertLess(c['area'][2],550)
        self.assertGreater(c['posicao'][0],150)
        self.assertGreater(c['area'][1],90)
        self.assertLess(c['area'][3],330)

    def test_texto_que_apareceu_na_area_invalida_coordenada_anterior(self):
        c=localizar_vazio(self.imagem,self.detalhes)
        ImageDraw.Draw(self.imagem).point(c['posicao'],fill='black')
        self.assertFalse(confirmar_vazio(self.imagem,self.detalhes,c))

    def test_movimento_da_arvore_invalida_coordenada_anterior(self):
        c=localizar_vazio(self.imagem,self.detalhes)
        self.detalhes['arvore']=(31,90,540,240)
        self.assertFalse(confirmar_vazio(self.imagem,self.detalhes,c))

    def test_movimento_do_combo_invalida_coordenada_anterior(self):
        c=localizar_vazio(self.imagem,self.detalhes)
        self.detalhes['combo']=(101,50,470,20)
        self.assertFalse(confirmar_vazio(self.imagem,self.detalhes,c))

    def test_lista_aberta_impede_focar_arvore(self):
        self.detalhes['lista']=(100,70,470,80)
        self.assertIsNone(localizar_vazio(self.imagem,self.detalhes))

    def test_arvore_sem_area_branca_suficiente_impede_clique(self):
        ImageDraw.Draw(self.imagem).rectangle((30,90,569,329),fill='#cccccc')
        self.assertIsNone(localizar_vazio(self.imagem,self.detalhes))

    def test_linha_branca_fina_nao_e_area_suficiente(self):
        d=ImageDraw.Draw(self.imagem)
        d.rectangle((30,90,569,329),fill='black')
        d.line((50,140,520,140),fill='white',width=2)
        self.assertIsNone(localizar_vazio(self.imagem,self.detalhes))

    def test_arvore_fora_da_imagem_e_rejeitada(self):
        self.detalhes['arvore']=(30,90,700,240)
        self.assertIsNone(localizar_vazio(self.imagem,self.detalhes))


if __name__=='__main__':unittest.main()
