"""Saída resumida não altera etapas, erros, threads nem execução fiscal."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.console_servidor import ConsoleServidor, saida_servidor


class TestConsoleServidor(unittest.TestCase):
    def setUp(self):
        pasta=tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta=Path(pasta.name)
        self.saida=io.StringIO()

    def console(self,**kwargs):
        console=ConsoleServidor(self.saida,self.pasta,**kwargs)
        self.addCleanup(console.encerrar)
        return console

    def log(self):
        return (self.pasta/'servidor_detalhes.log').read_text(encoding='utf-8')

    def test_oculta_ocr_mas_mantem_etapas_e_falhas_com_detalhe_local(self):
        console=self.console()
        texto=('RESUMO_RECORTE {"confirmado": false}\n'
               'Nenhum estado esperado reconhecido ainda (tentativa 1/90)\n'
               '[estado] preencher_periodo: inicio\n'
               '[estado] preencher_periodo: falha (periodo_nao_confirmado)\n'
               'Destino dos livros não confirmado.\n')
        self.assertEqual(console.write(texto),len(texto))
        self.assertNotIn('RESUMO_RECORTE',self.saida.getvalue())
        self.assertNotIn('tentativa 1/90',self.saida.getvalue())
        self.assertIn('[estado] preencher_periodo: falha',self.saida.getvalue())
        self.assertIn('Destino dos livros não confirmado.',self.saida.getvalue())
        self.assertIn('RESUMO_RECORTE {"confirmado": false}',self.log())
        self.assertIn('[estado] preencher_periodo: falha',self.log())

    def test_tempos_perfil_e_otimizacoes_ficam_no_diagnostico_local_e_no_console(self):
        console=self.console()
        linhas=['[tempo] resumo_acumulador: total 120s | abrir_resumo 10s',
                '[perfil] gerar_previa: ocr 12x 31s-cpu (tesseract 8x/25s, windows 4x/6s)',
                'OTIMIZACOES {"ocr_paralelo": true}',
                'OTIMIZACAO_DESLIGADA {"nome": "ocr_paralelo", "motivo": "RuntimeError"}',
                'LIVROS_CONFERENCIA {"arquivo": "a.pdf", "paginas": 1, "tipos": ["registro_icms"], "motivos": {}}',
                'FOCO_PERDIDO janela em foco: classe Chrome_WidgetWin_1']
        console.write('\n'.join(linhas)+'\n')
        for linha in linhas:
            self.assertIn(linha,self.saida.getvalue())
            self.assertIn(linha,self.log())

    def test_opcao_detalhada_mostra_tambem_diagnostico(self):
        console=self.console(detalhado=True)
        console.write('PASTA_NAVEGACAO {"fase":"proximo_no"}\n')
        self.assertIn('PASTA_NAVEGACAO',self.saida.getvalue())
        self.assertIn('PASTA_NAVEGACAO',self.log())

    def test_flush_no_meio_do_json_nao_vaza_detalhe(self):
        console=self.console()
        console.write('LIVROS_OK ')
        console.flush()
        console.write('{"confirmado":true}')
        console.flush()
        self.assertEqual(self.saida.getvalue(),'')
        console.write('\n')
        self.assertIn('LIVROS_OK {"confirmado":true}',self.log())
        console.write('Digite: ')
        console.flush()
        self.assertEqual(self.saida.getvalue(),'Digite: ')

    def test_mensagens_de_threads_nao_se_misturam(self):
        console=self.console()
        barreira=threading.Barrier(2)
        def emitir(prefixo):
            console.write(prefixo)
            barreira.wait(timeout=3)
            console.write('{"confirmado":true}\n')
        threads=[threading.Thread(target=emitir,args=(prefixo,))
                 for prefixo in ('LIVROS_OK ','PASTA_NAVEGACAO ')]
        for thread in threads:thread.start()
        for thread in threads:thread.join(4)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(self.saida.getvalue(),'')
        self.assertIn('LIVROS_OK {"confirmado":true}',self.log())
        self.assertIn('PASTA_NAVEGACAO {"confirmado":true}',self.log())

    def test_aviso_de_atividade_limitado_a_dez_segundos(self):
        agora=[0]
        with patch('app.console_servidor.time.monotonic',side_effect=lambda:agora[0]):
            console=self.console()
            agora[0]=11
            console.write('RESUMO_RECORTE {}\n')
            agora[0]=12
            console.write('RESUMO_RECORTE {}\n')
            self.assertEqual(self.saida.getvalue().count('Reconhecendo a tela'),1)
            console.write('[estado] gerar_previa: inicio\n')
            agora[0]=19
            console.write('RESUMO_RECORTE {}\n')
            self.assertEqual(self.saida.getvalue().count('Reconhecendo a tela'),1)
            agora[0]=23
            console.write('RESUMO_RECORTE {}\n')
            self.assertEqual(self.saida.getvalue().count('Reconhecendo a tela'),2)

    def test_rotacao_limita_numero_de_arquivos(self):
        console=self.console(max_bytes=220)
        for numero in range(20):
            console.write('PASTA_NAVEGACAO '+str(numero)+' '+('x'*80)+'\n')
        console.encerrar()
        arquivos=list(self.pasta.glob('servidor_detalhes.log*'))
        self.assertEqual(len(arquivos),4)
        self.assertTrue(all(p.stat().st_size<=220 for p in arquivos))
        self.assertIn('PASTA_NAVEGACAO 19',self.log())

    def test_sem_permissao_para_log_preserva_saida_completa(self):
        with patch('app.console_servidor._ArquivoDiagnostico',side_effect=PermissionError):
            console=self.console()
        console.write('LIVROS_OK {"confirmado":false}\n')
        self.assertIn('logs completos no terminal',self.saida.getvalue())
        self.assertIn('LIVROS_OK',self.saida.getvalue())

    def test_erro_de_gravacao_no_meio_do_ciclo_nao_perde_erro(self):
        console=self.console()
        with patch.object(console._arquivo,'handle',side_effect=OSError):
            console.write('LIVROS_OK {"confirmado":false}\n')
        console.write('[estado] gerar_previa: falha\n')
        self.assertIn('LIVROS_OK',self.saida.getvalue())
        self.assertIn('[estado] gerar_previa: falha',self.saida.getvalue())
        self.assertEqual(self.saida.getvalue().count('logs completos no terminal'),1)

    def test_contexto_restaura_stdout_e_nao_filtra_stderr_ou_excecoes(self):
        erros=io.StringIO()
        with redirect_stdout(self.saida),redirect_stderr(erros):
            import sys
            original=sys.stdout
            with self.assertRaisesRegex(RuntimeError,'falha sintética'):
                with saida_servidor(self.pasta):
                    print('RESUMO_RECORTE {}',flush=True)
                    print('Aviso no stderr',file=sys.stderr)
                    raise RuntimeError('falha sintética')
            self.assertIs(sys.stdout,original)
        self.assertEqual(erros.getvalue(),'Aviso no stderr\n')
        self.assertNotIn('RESUMO_RECORTE',self.saida.getvalue())
        self.assertIn('RESUMO_RECORTE',self.log())

    def test_atalho_padrao_resumido_e_opcao_cli_detalhada(self):
        from scripts import servidor
        def servidor_simulado(*args,**kwargs):
            print('RESUMO_RECORTE {"confirmado":true}',flush=True)
            print('[estado] fim: concluido',flush=True)
        for detalhado in (False,True):
            with self.subTest(detalhado=detalhado):
                saida=io.StringIO()
                with patch.object(servidor,'ROOT',self.pasta), \
                     patch('app.api_servidor.obter_chave',return_value='d'*48), \
                     patch.object(servidor.logging,'basicConfig'), \
                     patch('uvicorn.run',side_effect=servidor_simulado) as iniciar,redirect_stdout(saida):
                    resultado=servidor.main(['--simular']+(['--logs-detalhados'] if detalhado else []))
                self.assertEqual(resultado,0)
                iniciar.assert_called_once()
                self.assertIn('[estado] fim: concluido',saida.getvalue())
                self.assertEqual('RESUMO_RECORTE' in saida.getvalue(),detalhado)
