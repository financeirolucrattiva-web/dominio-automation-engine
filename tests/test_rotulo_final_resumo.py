"""Fallback de rótulo: captura atual, leitura literal e bordas obrigatórias."""
import copy
import json
import shutil
import unittest
from unittest.mock import Mock,patch

from PIL import Image,ImageDraw
from app.leitura_resumo import resolver_rotulos_resumo,medir_campos
from test_leitura_recortes_resumo import formulario


def sem_final(dados):
    return {k:[v for i,v in enumerate(valores) if i!=3] for k,valores in dados.items()}


def linha_rotulo(escala,texto='Data final:'):
    # Caixas de uma linha local; não são coordenadas do desktop.
    tokens=texto.split()
    return {'text':tokens,'left':[i*32*escala for i in range(len(tokens))],
            'top':[3*escala]*len(tokens),'width':[30*escala]*len(tokens),
            'height':[9*escala]*len(tokens)}


class TestRotuloFinalResumo(unittest.TestCase):
    def setUp(self):
        self.imagem,self.dados=formulario(None,dx=100,dy=50)
        self.incompletos=sem_final(self.dados)
        self.tela=Mock()
        self.tela.ler_dados_ocr_linha_rotulo.side_effect=lambda im,escala,preparo:linha_rotulo(escala)

    def resolver(self,dados=None,**kwargs):
        with patch.multiple('app',create=True,tela=self.tela):
            return resolver_rotulos_resumo(self.imagem,dados or self.incompletos,2,
                titulo_confirmado=True,**kwargs)

    def test_duas_leituras_literais_medem_campo_atual_sem_digitar(self):
        antes=self.imagem.tobytes(); detalhes=[]
        rotulos=self.resolver(registrar=detalhes.append)
        campos=medir_campos(self.imagem,rotulos)
        self.assertGreater(campos['final']['retangulo'][1],campos['inicial']['retangulo'][1])
        self.assertEqual(self.imagem.tobytes(),antes)
        self.assertTrue(detalhes[-1]['confirmado'])
        area=detalhes[-1]['area']
        self.assertEqual(rotulos['final']['x'],area[0])
        self.assertEqual(rotulos['final']['y'],area[1]+3)
        self.assertEqual(self.tela.ler_dados_ocr_linha_rotulo.call_count,4)

    def test_uma_leitura_so_e_texto_incompleto_extra_ou_alias_nao_confirmam(self):
        for texto in ('Data','final','Data Finai:','Data final: PRIVADO','Data final 31082026'):
            self.tela.ler_dados_ocr_linha_rotulo.side_effect=lambda im,escala,preparo:linha_rotulo(escala,texto)
            detalhes=[]
            with self.subTest(texto=texto),self.assertRaises(ValueError):
                self.resolver(registrar=detalhes.append)
            self.assertNotIn('PRIVADO',json.dumps(detalhes))
        self.tela.ler_dados_ocr_linha_rotulo.side_effect=[linha_rotulo(4),
                                                       linha_rotulo(6,'Data'),None,None]
        with self.assertRaises(ValueError):self.resolver()

    def test_leitura_inicial_contraditoria_nao_vira_final(self):
        self.tela.ler_dados_ocr_linha_rotulo.side_effect=[linha_rotulo(4),linha_rotulo(6),
                                                       linha_rotulo(4,'Data inicial:')]
        with self.assertRaises(ValueError):self.resolver()

    def test_caixas_fora_da_roi_duas_linhas_ou_data_sem_sobreposicao_recusam(self):
        for variante in ('fora','linhas','deslocada'):
            def ler(imagem,escala,preparo):
                dados=linha_rotulo(escala)
                if variante=='fora':dados['left'][1]=imagem.width*escala
                elif variante=='linhas':dados['top'][1]+=12*escala
                else:dados['top']=[0,0]; dados['height']=[escala,escala]
                return dados
            self.tela.ler_dados_ocr_linha_rotulo.side_effect=ler
            with self.subTest(variante=variante),self.assertRaises(ValueError):self.resolver()

    def test_erro_tecnico_na_primeira_opiniao_nao_descarta_duas_leituras_validas(self):
        self.tela.ler_dados_ocr_linha_rotulo.side_effect=[ValueError('PRIVADO'),
            linha_rotulo(6),linha_rotulo(4),linha_rotulo(6)]
        self.assertIn('final',self.resolver())

    def test_data_orfa_ausente_ou_duas_candidatas_nao_leem_roi(self):
        ausente={k:v[:2] for k,v in self.incompletos.items()}
        duplicado=copy.deepcopy(self.incompletos)
        for k in duplicado:
            duplicado[k].append(duplicado[k][-1]+60 if k=='top' else duplicado[k][-1])
        for dados in (ausente,duplicado):
            with self.subTest(dados=dados),self.assertRaises(ValueError):self.resolver(dados)
        self.tela.ler_dados_ocr_linha_rotulo.assert_not_called()

    def test_final_ambiguo_nao_e_substituido_pelo_recorte(self):
        duplicado={k:v+[v[3]] for k,v in self.dados.items()}
        with self.assertRaises(ValueError):self.resolver(duplicado)
        self.tela.ler_dados_ocr_linha_rotulo.assert_not_called()

    def test_titulo_ausente_bloqueia_recorte(self):
        self.tela.achar_texto_ou_no_centro.return_value=None
        self.tela.achar_texto_windows.return_value=None
        with patch.multiple('app',create=True,tela=self.tela),self.assertRaises(ValueError):
            resolver_rotulos_resumo(self.imagem,self.incompletos,2)
        self.tela.ler_dados_ocr_linha_rotulo.assert_not_called()

    def test_data_em_outra_coluna_nao_e_candidata(self):
        dados=copy.deepcopy(self.incompletos); dados['left'][-1]+=400
        with self.assertRaises(ValueError):self.resolver(dados)
        self.tela.ler_dados_ocr_linha_rotulo.assert_not_called()

    def test_rotulo_reconhecido_sem_borda_ainda_bloqueia(self):
        rotulos=self.resolver()
        ImageDraw.Draw(self.imagem).rectangle((210,160,320,190),fill='#eeeeee')
        with self.assertRaises(ValueError):medir_campos(self.imagem,rotulos)

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract indisponível.')
    def test_ocr_real_em_pixels_sinteticos_le_final_com_global_incompleto(self):
        for fator in (1,2):
            imagem,dados=formulario(None,dx=80,dy=50,fator=fator)
            rotulos=resolver_rotulos_resumo(imagem,sem_final(dados),2,titulo_confirmado=True)
            campos=medir_campos(imagem,rotulos)
            self.assertGreater(campos['final']['retangulo'][1],campos['inicial']['retangulo'][1])


if __name__=='__main__':unittest.main()
