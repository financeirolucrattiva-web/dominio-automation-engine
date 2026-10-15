"""Recortes de captura sintética; nenhum dado ou clique no Domínio."""
import copy
import shutil
import unittest
from unittest.mock import patch
from app import tela
from app.leitura_resumo import formulario_resumo_reconhecido
from test_botoes_formulario import tela_resumo


class TestResumoROI(unittest.TestCase):
    def preparar(self):
        imagem,dados=tela_resumo(dx=200,dy=140)
        centro,dx,dy=tela.recortar_centro(imagem)
        roi=copy.deepcopy(dados)
        for k in ('left','top','width','height'):
            origem=dx if k=='left' else dy if k=='top' else 0
            roi[k]=[(v/2-origem)*4 for v in roi[k]]
        for texto,x,w in (('Resumo',220,45),('por',270,20),('acumulador',295,65)):
            for k,v in zip(roi,(texto,(x-dx)*4,(160-dy)*4,w*4,12*4)):roi[k].append(v)
        return imagem,centro,roi

    def test_titulo_e_campos_no_recorte_recuperam_leitura_global_incompleta(self):
        imagem,centro,roi=self.preparar();detalhes=[]
        with patch.object(tela,'achar_texto_ou_no_centro',return_value=None), \
             patch.object(tela,'achar_texto_windows',return_value=None), \
             patch.object(tela,'ler_dados_ocr_formulario',side_effect=lambda area,**kw:roi if area.size==centro.size else {}):
            pos=formulario_resumo_reconhecido(imagem,detalhes.append)
        self.assertIsNotNone(pos)
        self.assertTrue(220<=pos[0]<=360 and 160<=pos[1]<=172)
        self.assertEqual(detalhes[-1]['controles'],2)
        self.assertGreaterEqual(detalhes[-1]['campos']['inicial'][0],300)

    def test_titulo_de_previa_ou_menu_sem_dois_controles_nao_e_formulario(self):
        imagem,centro,roi=self.preparar()
        roi={k:valores[-3:] for k,valores in roi.items()}
        with patch.object(tela,'achar_texto_ou_no_centro',return_value=None), \
             patch.object(tela,'achar_texto_windows',return_value=None), \
             patch.object(tela,'ler_dados_ocr_formulario',return_value=roi):
            self.assertIsNone(formulario_resumo_reconhecido(imagem))

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract indisponível.')
    def test_ocr_real_no_recorte_sintetico_confirma_titulo_e_dois_campos(self):
        imagem,_,_=self.preparar()
        with patch.object(tela,'achar_texto_ou_no_centro',return_value=None), \
             patch.object(tela,'achar_texto_windows',return_value=None):
            self.assertIsNotNone(formulario_resumo_reconhecido(imagem))


if __name__=='__main__':unittest.main()
