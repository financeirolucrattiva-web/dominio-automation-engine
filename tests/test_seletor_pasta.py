"""Seletor medido em pixels sintéticos, sem supor campo de endereço."""
import unittest
from unittest.mock import Mock,patch
from PIL import Image,ImageDraw
from app import seletor_pasta as seletor


def quadro(drive='Client C (M:\\)',pastas=('dominio-automation-engine','saida','LIVROS123456789012'),selecionar=False,selecionado_indice=None):
    imagem=Image.new('RGB',(600,400),'#eeeeee');d=ImageDraw.Draw(imagem)
    d.rectangle((100,76,480,100),fill='white',outline='black')
    d.rectangle((30,110,480,290),fill='white',outline='black')
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

    def test_folha_exclusiva_precisa_selecao_azul_e_so_entao_ok(self):
        imagem,palavras=quadro(selecionar=True)
        clicar=Mock();tecla=Mock()
        with patch.object(seletor,'_palavras',return_value=palavras):
            self.assertTrue(seletor.selecionar_pasta('M:\\Users\\usuario\\dominio-automation-engine\\saida\\LIVROS123456789012',lambda:imagem,clicar,tecla))
        tecla.assert_not_called();self.assertEqual(clicar.call_args_list[-1].args,(362,326))

    def test_sem_folha_marcada_nao_confirma_pasta_e_nao_digita_caminho(self):
        imagem,palavras=quadro();clicar=Mock();tecla=Mock()
        with patch.object(seletor,'_palavras',return_value=palavras),patch.object(seletor.time,'sleep'),self.assertRaises(ValueError):
            seletor.selecionar_pasta('M:\\Users\\usuario\\dominio-automation-engine\\saida\\LIVROS123456789012',lambda:imagem,clicar,tecla)
        self.assertNotIn((362,326),[c.args for c in clicar.call_args_list])
        tecla.assert_not_called()

    def test_drive_servidor_nao_compensa_client_inexistente(self):
        imagem,palavras=quadro(drive='Servidor (C:\\)');clicar=Mock()
        with patch.object(seletor,'_palavras',return_value=palavras),patch.object(seletor.time,'sleep'),self.assertRaises(ValueError):
            seletor.selecionar_pasta('M:\\Users\\usuario\\dominio-automation-engine\\saida\\LIVROS123456789012',lambda:imagem,clicar,Mock())
        self.assertNotIn((362,326),[c.args for c in clicar.call_args_list])

    def test_arvore_expande_ancestral_e_confere_filhos_por_indentacao(self):
        partes=('dominio-automation-engine','saida','LIVROS123456789012')
        fases=[quadro(pastas=partes[:1],selecionar=True),quadro(pastas=partes[:2],selecionar=True),quadro(pastas=partes,selecionar=True)]
        estado=[0];clicar=Mock()
        def tecla(tecla):
            self.assertEqual(tecla,'right');estado[0]+=1
        with patch.object(seletor,'_palavras',side_effect=lambda img:fases[estado[0]][1]):
            self.assertTrue(seletor.selecionar_pasta('M:\\Users\\usuario\\dominio-automation-engine\\saida\\LIVROS123456789012',lambda:fases[estado[0]][0],clicar,tecla))
        self.assertEqual(estado[0],2);self.assertEqual(clicar.call_args_list[-1].args,(362,326))

    def test_recusa_nome_reutilizavel_e_no_ambiguo(self):
        with self.assertRaises(ValueError):seletor.selecionar_pasta('M:\\saida',Mock(),Mock(),Mock())
        imagem,palavras=quadro(pastas=('LIVROS123456789012','LIVROS123456789012'))
        with patch.object(seletor,'_palavras',return_value=palavras),self.assertRaises(ValueError):
            seletor.selecionar_pasta('M:\\Users\\LIVROS123456789012',lambda:imagem,Mock(),Mock())


if __name__=='__main__':unittest.main()
