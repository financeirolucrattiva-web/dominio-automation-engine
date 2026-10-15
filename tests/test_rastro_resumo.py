"""Somente imagens/ações sintéticas e diretório temporário."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PIL import Image
from app.rastro_resumo import RastroResumo,PROTOCOLO


class TestRastroResumo(unittest.TestCase):
    def setUp(self):
        pasta=tempfile.TemporaryDirectory();self.addCleanup(pasta.cleanup)
        self.raiz=Path(pasta.name)
        self.saida=io.StringIO()
        self.console=contextlib.redirect_stdout(self.saida);self.console.__enter__()
        self.addCleanup(self.console.__exit__,None,None,None)
        self.git=patch('app.rastro_resumo.subprocess.check_output',return_value='head_teste')
        self.git.start();self.addCleanup(self.git.stop)

    def test_capturas_antes_depois_e_marcador_nao_modificam_imagens(self):
        r=RastroResumo(self.raiz)
        antes=Image.new('RGB',(100,80),'white');depois=Image.new('RGB',(100,80),'blue')
        capturar=Mock(side_effect=[antes,depois]);agir=Mock()
        r.acao('resumo_acumulador','clique',(30,20),capturar,agir,mouse=lambda:(30,20))
        agir.assert_called_once();self.assertEqual(capturar.call_count,2)
        dados=json.loads((r.pasta/'rastro.json').read_text())
        self.assertEqual(dados['eventos'][0]['posicao'],[30,20])
        self.assertNotEqual(dados['eventos'][0]['sha256'],dados['eventos'][1]['sha256'])
        self.assertEqual(Image.open(r.pasta/'000.png').getpixel((30,20)),(255,255,255))
        self.assertIn('left:30.0%;top:25.0%',(r.pasta/'indice.html').read_text())

    def test_melhor_formulario_nao_e_sobrescrito_pelo_painel_azul(self):
        r=RastroResumo(self.raiz)
        r.leitura(Image.new('RGB',(20,20),'white'),{'titulo':True,'controles':2})
        r.leitura(Image.new('RGB',(20,20),'blue'),{'titulo':False,'controles':0})
        self.assertEqual(Image.open(r.pasta/'melhor_formulario.png').getpixel((0,0)),(255,255,255))

    def test_manifesto_identifica_codigo_em_memoria_e_protocolo(self):
        def primeira():return 1
        def segunda():return 2
        r=RastroResumo(self.raiz,(primeira,segunda))
        self.assertEqual(r.manifesto['protocolo'],PROTOCOLO)
        codigos=r.manifesto['funcoes_carregadas']
        self.assertNotEqual(codigos['primeira']['codigo_memoria'],codigos['segunda']['codigo_memoria'])
        self.assertNotIn(str(self.raiz),self.saida.getvalue())

    def test_falha_de_gravacao_nao_repete_nem_impede_acao_validada(self):
        with patch.object(Path,'mkdir',side_effect=PermissionError('privado')):
            r=RastroResumo(self.raiz);agir=Mock()
            r.acao('ok','clique',(10,10),lambda:Image.new('RGB',(20,20)),agir)
        agir.assert_called_once()
        self.assertNotIn('privado',self.saida.getvalue())

    def test_erro_na_acao_nao_e_ocultado_ou_repetido(self):
        r=RastroResumo(self.raiz);agir=Mock(side_effect=RuntimeError('mensagem privada'))
        with self.assertRaises(RuntimeError):
            r.acao('ok','clique',(10,10),lambda:Image.new('RGB',(20,20)),agir)
        agir.assert_called_once()
        texto=(r.pasta/'rastro.json').read_text()
        self.assertIn('RuntimeError',texto);self.assertNotIn('mensagem privada',texto)


if __name__=='__main__':unittest.main()
