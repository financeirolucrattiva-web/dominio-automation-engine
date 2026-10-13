"""Recuperação com clones Git reais locais; nenhum arquivo do escritório."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import recuperar_instalacao as recuperacao
from app.trava_execucao import TravaExecucao


class TestRecuperacaoInstalacao(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.fonte = self.root / "clone"
        self.destino = self.root / "instalacao"
        self.fonte.mkdir(); self.destino.mkdir()
        self.git(self.fonte, "init", "-qb", "main")
        self.git(self.fonte, "remote", "add", "origin", recuperacao.REPOSITORIO + ".git")
        (self.fonte / "web").mkdir(); (self.destino / "web").mkdir()
        (self.fonte / "data").mkdir(); (self.destino / "data").mkdir()
        (self.fonte / "web/index.html").write_bytes(b'<!doctype html><form id="form-login"></form>')
        (self.fonte / "codigo.py").write_bytes(b'VERSAO = "nova"\n')
        (self.fonte / "data/empresas.exemplo.csv").write_bytes(b'EXEMPLO DA FONTE')
        self.git(self.fonte, "add", ".")
        self.git(self.fonte, "-c", "user.name=Teste local", "-c", "user.email=teste@example.invalid",
                 "commit", "-qm", "codigo sintético")
        self.git(self.destino, "init", "-q")
        (self.destino / ".git/HEAD").write_bytes(b'\0'*23)
        (self.destino / "web/index.html").write_bytes(b'\0'*100)
        (self.destino / "codigo.py").write_bytes(b'VERSAO = "local anterior"\n')
        self.protegidos = {"data/servidor.sqlite3": b'EMPRESAS-CADASTRADAS',
                          "data/empresas.exemplo.csv": b'EXEMPLO-LOCAL',
                          "data/rede_local/autoridade/ca-key.pem": b'CHAVE-LOCAL-SINTETICA',
                          "saida/documento.pdf": b'DOCUMENTO-LOCAL',
                          "capturas/tela.png": b'CAPTURA-LOCAL',
                          ".env": b'CONFIGURACAO-LOCAL', "funcao_local.py": b'CUSTOMIZACAO-NAO-VERSIONADA'}
        for rel, dados in self.protegidos.items():
            caminho = self.destino / rel
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_bytes(dados)

    @staticmethod
    def git(pasta, *args):
        return subprocess.check_output(["git", "-C", str(pasta), *args], stderr=subprocess.STDOUT)

    def verificar_protegidos(self):
        for rel, dados in self.protegidos.items():
            self.assertEqual((self.destino / rel).read_bytes(), dados)

    def test_recupera_html_e_head_com_backup_e_preserva_dados_e_arquivos_nao_versionados(self):
        resultado = recuperacao.recuperar(self.destino, self.fonte)
        self.assertEqual(self.git(self.destino, "rev-parse", "HEAD"), self.git(self.fonte, "rev-parse", "HEAD"))
        self.assertEqual(self.git(self.destino, "branch", "--show-current").strip(), b'main')
        self.assertEqual((self.destino / "web/index.html").read_bytes(), (self.fonte / "web/index.html").read_bytes())
        self.assertEqual((self.destino / "codigo.py").read_bytes(), b'VERSAO = "nova"\n')
        self.assertEqual((resultado["backup"] / "codigo_anterior/codigo.py").read_bytes(), b'VERSAO = "local anterior"\n')
        self.assertEqual((resultado["backup"] / "codigo_anterior/web/index.html").read_bytes(), b'\0'*100)
        self.assertEqual((resultado["backup"] / "git_anterior/HEAD").read_bytes(), b'\0'*23)
        self.verificar_protegidos()

    def test_servidor_ativo_impede_substituicao_de_git_e_codigo(self):
        trava = TravaExecucao(self.destino / "data/sessao_executor.lock")
        trava.adquirir()
        try:
            with self.assertRaisesRegex(ValueError, "Pare o servidor"):
                recuperacao.recuperar(self.destino, self.fonte)
        finally:
            trava.liberar()
        self.assertEqual((self.destino / ".git/HEAD").read_bytes(), b'\0'*23)
        self.assertEqual((self.destino / "web/index.html").read_bytes(), b'\0'*100)
        self.assertEqual(list((self.destino / "data").glob('recuperacao_codigo_*')), [])
        self.verificar_protegidos()

    def test_erro_durante_escrita_restaura_codigo_anterior_e_git(self):
        original = recuperacao._gravar
        def gravar(caminho, dados):
            if Path(caminho).name == 'index.html' and b'form-login' in dados:
                raise OSError('falha sintética de escrita')
            original(caminho, dados)
        with patch.object(recuperacao, '_gravar', side_effect=gravar), self.assertRaises(OSError):
            recuperacao.recuperar(self.destino, self.fonte)
        self.assertEqual((self.destino / 'codigo.py').read_bytes(), b'VERSAO = "local anterior"\n')
        self.assertEqual((self.destino / 'web/index.html').read_bytes(), b'\0'*100)
        self.assertEqual((self.destino / '.git/HEAD').read_bytes(), b'\0'*23)
        self.verificar_protegidos()

    def test_falha_apos_troca_do_git_tambem_reverte_codigo_e_git(self):
        original = recuperacao._git
        def git(fonte, *args):
            if fonte == self.destino and args[0] == 'fsck':
                raise ValueError('falha sintética de conferência')
            return original(fonte, *args)
        with patch.object(recuperacao, '_git', side_effect=git), self.assertRaises(ValueError):
            recuperacao.recuperar(self.destino, self.fonte)
        self.assertEqual((self.destino / 'codigo.py').read_bytes(), b'VERSAO = "local anterior"\n')
        self.assertEqual((self.destino / '.git/HEAD').read_bytes(), b'\0'*23)
        self.verificar_protegidos()

    def test_recusa_fonte_sem_html_valido_ou_de_outro_repositorio(self):
        self.git(self.fonte, 'remote', 'set-url', 'origin', 'https://example.invalid/outro.git')
        with self.assertRaisesRegex(ValueError, 'repositório'):
            recuperacao.recuperar(self.destino, self.fonte)
        self.git(self.fonte, 'remote', 'set-url', 'origin', recuperacao.REPOSITORIO)
        (self.fonte / 'web/index.html').write_bytes(b'\0'*100)
        self.git(self.fonte, 'add', '.')
        self.git(self.fonte, '-c', 'user.name=Teste', '-c', 'user.email=teste@example.invalid', 'commit', '-qm', 'HTML inválido sintético')
        with self.assertRaisesRegex(ValueError, 'HTML'):
            recuperacao.recuperar(self.destino, self.fonte)
        self.assertEqual((self.destino / '.git/HEAD').read_bytes(), b'\0'*23)
        self.verificar_protegidos()

    def test_recusa_fonte_igual_aninhada_e_pasta_no_lugar_de_arquivo(self):
        for fonte in (self.destino, self.destino / 'data/clone', self.root):
            with self.subTest(fonte=fonte), self.assertRaises(ValueError):
                recuperacao.recuperar(self.destino, fonte)
        (self.destino / 'codigo.py').unlink(); (self.destino / 'codigo.py').mkdir()
        with self.assertRaisesRegex(ValueError, 'pasta no lugar'):
            recuperacao.recuperar(self.destino, self.fonte)
        self.assertEqual((self.destino / '.git/HEAD').read_bytes(), b'\0'*23)

    def test_recusa_link_que_levaria_a_escrita_fora_da_instalacao(self):
        (self.destino / 'codigo.py').unlink()
        fora = self.root / 'fora.py'; fora.write_bytes(b'ARQUIVO-EXTERNO')
        try:
            (self.destino / 'codigo.py').symlink_to(fora)
        except OSError:
            self.skipTest('Sistema não permite criar symlink para o teste.')
        with self.assertRaisesRegex(ValueError, 'link'):
            recuperacao.recuperar(self.destino, self.fonte)
        self.assertEqual(fora.read_bytes(), b'ARQUIVO-EXTERNO')
        self.assertEqual((self.destino / '.git/HEAD').read_bytes(), b'\0'*23)
