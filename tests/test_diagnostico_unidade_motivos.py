"""Diagnóstico local não altera decisões e não publica texto OCR livre."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from app import seletor_pasta as seletor, tela
from app.controle_execucao import ExecucaoInterrompida
from test_seletor_pasta_ocr import dialogo
from test_unidade_pasta_ocr_nativo import dados_unidade


def carregar_script():
    caminho=Path(__file__).resolve().parents[1]/'scripts'/'revisar_seletor_pasta.py'
    spec=importlib.util.spec_from_file_location('diagnostico_unidade_motivos',caminho)
    modulo=importlib.util.module_from_spec(spec); spec.loader.exec_module(modulo)
    return modulo


class TestMotivosUnidade(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.saida=io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.saida))
        self.vazio={k:[] for k in ('text','left','top','width','height')}
        self.tesseract=self.stack.enter_context(patch.object(
            tela,'ler_dados_ocr_linha_rotulo',return_value=self.vazio))
        self.nativo=self.stack.enter_context(patch.object(tela,'ler_dados_ocr_windows',return_value=None))
        self.imagem=dialogo(); self.combo=(105,60,456,27); self.observacoes=[]

    def ler(self,palavras=None):
        return seletor._refinar_unidade(self.imagem,palavras or [],self.combo,
                                        registrar=self.observacoes.append)

    def motivos(self,motor):
        return [o['motivo'] for o in self.observacoes if o['motor']==motor]

    def test_ocr_vazio_e_sem_resultado_nativo_sao_distintos(self):
        self.assertEqual(self.ler(),[])
        self.assertEqual(self.motivos('tesseract'),['sem_palavras']*4)
        self.assertEqual(self.motivos('windows'),['sem_resultado_do_leitor'])
        final=self.observacoes[-1]
        self.assertEqual(final['area'],[107,62,534,85])
        self.assertEqual(final['dimensoes'],[427,23])
        self.assertEqual(final['opinioes'],0)

    def test_palavras_com_identidade_rejeitada_nao_sao_contadas_como_vazias(self):
        self.tesseract.side_effect=lambda im,escala,preparo:dados_unidade('Client C (Mj)',escala)
        self.assertEqual(self.ler(),[])
        self.assertEqual(self.motivos('tesseract'),['identidade_nao_reconhecida']*4)
        self.assertTrue(all(o['palavras']==3 and o['linhas']==1
                            for o in self.observacoes if o['motor']=='tesseract'))

    def test_caixa_fora_do_recorte_e_distinta_de_identidade_invalida(self):
        def fora(im,escala,preparo):
            dados=dados_unidade('Client C (M:)',escala)
            dados['left'][0]=im.width*escala
            return dados
        self.tesseract.side_effect=fora
        self.assertEqual(self.ler(),[])
        self.assertEqual(self.motivos('tesseract'),['caixas_fora_do_recorte']*4)

    def test_multiplas_linhas_sao_distintas_de_identidade_invalida(self):
        def duas(im,escala,preparo):
            dados=dados_unidade('Client C (M:)',escala)
            dados['height']=[4*escala]*3
            dados['top'][-1]=12*escala
            return dados
        self.tesseract.side_effect=duas
        self.assertEqual(self.ler(),[])
        self.assertEqual(self.motivos('tesseract'),['linhas_ambiguas']*4)

    def test_erro_de_leitura_nao_expoe_mensagem_ou_texto_ocr(self):
        segredo='EMPRESA_PRIVADA_12345'
        self.tesseract.side_effect=RuntimeError(segredo)
        self.assertEqual(self.ler(),[])
        self.assertEqual(self.motivos('tesseract'),['erro_leitura']*4)
        self.assertNotIn(segredo,json.dumps(self.observacoes)+self.saida.getvalue())
        self.assertEqual(self.observacoes[0]['tipo_erro'],'RuntimeError')

    def test_identidades_contraditorias_continuam_recusadas_e_diagnosticadas(self):
        self.tesseract.side_effect=[dados_unidade('Client C (M:)',4),
            dados_unidade('Client Z (M:)',4),self.vazio,self.vazio]
        self.assertEqual(self.ler(),[])
        final=self.observacoes[-1]
        self.assertEqual(final['opinioes'],2)
        self.assertEqual(final['identidades_distintas'],2)
        self.assertEqual(final['motivo'],'nao_confirmado')

    def test_ativar_observador_nao_muda_palavras_aceitas(self):
        self.tesseract.side_effect=lambda im,escala,preparo:dados_unidade('Client C (M:)',escala)
        sem=seletor._refinar_unidade(self.imagem,[],self.combo)
        self.assertEqual(self.ler(),sem)
        self.assertEqual(self.observacoes[-1]['motivo'],'confirmado')
        self.nativo.assert_not_called()

    def test_cancelamento_propaga_sem_virar_diagnostico_de_erro(self):
        self.tesseract.side_effect=ExecucaoInterrompida('teste')
        with self.assertRaises(ExecucaoInterrompida):self.ler()
        self.assertEqual(self.observacoes,[])

    def test_texto_ocr_livre_nao_aparece_em_observacoes(self):
        privado='CAMINHO_PRIVADO_NAO_PUBLICAR'
        self.tesseract.side_effect=lambda im,escala,preparo:dados_unidade(privado,escala)
        self.assertEqual(self.ler(),[])
        self.assertNotIn(privado,json.dumps(self.observacoes)+self.saida.getvalue())

    def test_global_ja_lido_nao_gera_novas_passadas(self):
        palavras=[{'texto':'Client C (M:)','x':112,'y':65,'w':110,'h':12}]
        self.assertEqual(self.ler(palavras),palavras)
        self.tesseract.assert_not_called(); self.nativo.assert_not_called()
        self.assertEqual(self.motivos('global'),['client_c_reconhecido'])


class TestScriptDetalharUnidade(unittest.TestCase):
    def test_flag_detalhar_exige_somente_unidade_antes_de_ler_imagem(self):
        modulo=carregar_script()
        with contextlib.redirect_stderr(io.StringIO()),patch.object(seletor,'medir_dialogo') as medir:
            with self.assertRaises(SystemExit) as erro:
                modulo.main(['--imagem','inexistente.png','--detalhar-unidade'])
        self.assertEqual(erro.exception.code,2); medir.assert_not_called()

    def test_imagem_salva_contem_so_campo_e_diagnostico_nao_le_arvore_ou_ok(self):
        modulo=carregar_script()
        imagem=Image.new('RGB',(1440,900),'magenta')
        combo=(559,321,380,20)
        ImageDraw.Draw(imagem).rectangle((559,321,938,340),fill='white',outline='black')
        detalhes={'combo':combo,'lista':None,'palavras':[]}
        def medir(*args,**kwargs):
            kwargs['registrar_unidade']({'motor':'tesseract','motivo':'sem_palavras','palavras':0})
            return detalhes
        with tempfile.TemporaryDirectory() as pasta:
            raiz=Path(pasta); png=raiz/'fonte.png'; imagem.save(png)
            saida=io.StringIO()
            with patch.object(modulo,'ROOT',raiz),contextlib.redirect_stdout(saida), \
                 patch.object(seletor,'medir_dialogo',side_effect=medir), \
                 patch.object(seletor,'_completar_dialogo') as arvore, \
                 patch.object(seletor,'_ok_final') as ok:
                self.assertEqual(modulo.main(['--imagem',str(png),'--somente-unidade',
                                              '--detalhar-unidade']),0)
            arvore.assert_not_called(); ok.assert_not_called()
            linhas=saida.getvalue().splitlines()
            diagnostico=json.loads(next(l.removeprefix('PASTA_DIAGNOSTICO ') for l in linhas
                                        if l.startswith('PASTA_DIAGNOSTICO ')))
            self.assertEqual(diagnostico['client_c_letras_no_campo'],[])
            arquivo=raiz/diagnostico['recorte_local']
            self.assertEqual(arquivo.parent,raiz/'capturas')
            with Image.open(arquivo) as salvo:
                self.assertEqual(salvo.width,380*4+16)
                cores=salvo.convert('RGB').getcolors(salvo.width*salvo.height)
                self.assertNotIn((255,0,255),{cor for _,cor in cores})
            self.assertEqual(len(list((raiz/'capturas').glob('*.png'))),1)
            self.assertTrue(any(l.startswith('PASTA_UNIDADE_OCR ') for l in linhas))

    def test_combo_fora_da_imagem_nao_cria_recorte(self):
        modulo=carregar_script()
        with tempfile.TemporaryDirectory() as pasta,patch.object(modulo,'ROOT',Path(pasta)):
            for combo in ((-1,10,100,20),(550,10,100,20),(10,410,100,20)):
                with self.subTest(combo=combo),self.assertRaises(ValueError):
                    modulo.salvar_recorte_unidade(dialogo(),combo)
            self.assertFalse((Path(pasta)/'capturas').exists())


if __name__=='__main__':unittest.main()
