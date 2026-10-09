"""Atualizador contra repositórios Git reais locais, sem identidade configurada."""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.atualizar_projeto import AtualizacaoRecusada, atualizar


@unittest.skipUnless(shutil.which("git"), "Git nao instalado")
class TestAtualizarProjeto(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.pasta = Path(temporario.name)
        config_vazia = self.pasta / "gitconfig"
        config_vazia.write_text("", encoding="utf-8")
        ambiente = dict(os.environ)
        for chave in list(ambiente):
            if chave.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_", "GIT_CONFIG_")):
                del ambiente[chave]
        ambiente.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(config_vazia),
                        GIT_TERMINAL_PROMPT="0")
        remendo = patch.dict(os.environ, ambiente, clear=True)
        remendo.start()
        self.addCleanup(remendo.stop)
        self.origem = self.pasta / "origem.git"
        self.publicador = self.pasta / "publicador"
        self.instalacao = self.pasta / "instalacao"
        self.git(self.pasta, "init", "--bare", "--initial-branch=main", str(self.origem))
        self.git(self.pasta, "clone", str(self.origem), str(self.publicador))
        (self.publicador / ".gitignore").write_text("data/\nsaida/\n", encoding="utf-8")
        self.commit(self.publicador, "motor.txt", "versao 1\n")
        self.git(self.publicador, "push", "origin", "main")
        self.git(self.pasta, "clone", str(self.origem), str(self.instalacao))
        self.inicial = self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip()
        self.commit(self.publicador, "motor.txt", "versao 2\n")
        self.git(self.publicador, "push", "origin", "main")
        self.nova = self.git(self.publicador, "rev-parse", "HEAD").stdout.strip()

    def git(self, pasta, *args, conferir=True):
        resultado = subprocess.run(["git", *args], cwd=pasta, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        if conferir and resultado.returncode != 0:
            self.fail(resultado.stderr or resultado.stdout)
        return resultado

    def commit(self, pasta, nome, texto):
        (pasta / nome).write_text(texto, encoding="utf-8")
        self.git(pasta, "add", "--all")
        self.git(pasta, "-c", "user.name=Teste Sintetico", "-c", "user.email=teste@example.invalid",
                 "commit", "--message", "Atualizacao sintetica")

    def executar(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return atualizar(self.instalacao)

    def confirmar_main(self):
        self.assertEqual(self.git(self.instalacao, "branch", "--show-current").stdout.strip(), "main")
        self.assertEqual(self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip(), self.nova)
        self.assertFalse((self.instalacao / ".git/MERGE_HEAD").exists())

    def test_main_atualiza_sem_nome_email_ou_commit_novo(self):
        for chave in ("user.name", "user.email"):
            self.assertNotEqual(self.git(self.instalacao, "config", "--get", chave, conferir=False).returncode, 0)
        revisao = self.executar()
        self.confirmar_main()
        self.assertTrue(self.nova.startswith(revisao))
        self.assertEqual((self.instalacao / "motor.txt").read_text(), "versao 2\n")
        self.executar()  # Segunda atualização não cria commits nem pede identidade.
        self.confirmar_main()

    def test_sai_da_branch_documento_sem_perder_seu_commit(self):
        self.git(self.instalacao, "switch", "--create", "documento")
        self.commit(self.instalacao, "esquema.md", "Esquema sintetico\n")
        documento = self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip()
        self.executar()
        self.confirmar_main()
        self.assertEqual(self.git(self.instalacao, "rev-parse", "documento").stdout.strip(), documento)
        self.assertEqual(self.git(self.instalacao, "show", "documento:esquema.md").stdout, "Esquema sintetico\n")
        self.assertFalse((self.instalacao / "esquema.md").exists())

    def test_main_divergente_preserva_branch_e_commits(self):
        self.commit(self.instalacao, "local.md", "Trabalho local\n")
        local = self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip()
        self.git(self.instalacao, "switch", "--create", "documento")
        with self.assertRaisesRegex(AtualizacaoRecusada, "main local tem commits"):
            self.executar()
        self.assertEqual(self.git(self.instalacao, "branch", "--show-current").stdout.strip(), "documento")
        self.assertEqual(self.git(self.instalacao, "rev-parse", "main").stdout.strip(), local)
        self.assertEqual((self.instalacao / "local.md").read_text(), "Trabalho local\n")

    def test_alteracoes_locais_no_indice_ou_worktree_sao_preservadas(self):
        for no_indice in (False, True):
            with self.subTest(no_indice=no_indice):
                (self.instalacao / "motor.txt").write_text("Edicao local\n", encoding="utf-8")
                if no_indice:
                    self.git(self.instalacao, "add", "motor.txt")
                estado = self.git(self.instalacao, "status", "--porcelain=v1").stdout
                with self.assertRaisesRegex(AtualizacaoRecusada, "alteracoes locais"):
                    self.executar()
                self.assertEqual(self.git(self.instalacao, "status", "--porcelain=v1").stdout, estado)
                self.assertEqual(self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip(), self.inicial)
                self.assertEqual((self.instalacao / "motor.txt").read_text(), "Edicao local\n")

    def test_dados_ignorados_e_arquivos_novos_nao_sao_apagados(self):
        for nome in ("data/servidor.sqlite3", "saida/relatorio.pdf", "anotacoes.txt"):
            arquivo = self.instalacao / nome
            arquivo.parent.mkdir(exist_ok=True)
            arquivo.write_bytes(b"conteudo local sintetico")
        self.executar()
        self.confirmar_main()
        for nome in ("data/servidor.sqlite3", "saida/relatorio.pdf", "anotacoes.txt"):
            self.assertEqual((self.instalacao / nome).read_bytes(), b"conteudo local sintetico")

    def test_integracao_pendente_nao_e_concluida_nem_cancelada(self):
        self.git(self.instalacao, "switch", "--create", "documento")
        self.commit(self.instalacao, "motor.txt", "Versao divergente\n")
        self.git(self.instalacao, "fetch", "origin")
        conflito = self.git(self.instalacao, "-c", "user.name=Teste", "-c", "user.email=teste@example.invalid",
                            "merge", "origin/main", conferir=False)
        self.assertNotEqual(conflito.returncode, 0)
        estado = self.git(self.instalacao, "status", "--porcelain=v1").stdout
        conteudo = (self.instalacao / "motor.txt").read_bytes()
        with self.assertRaisesRegex(AtualizacaoRecusada, "operacao Git em andamento"):
            self.executar()
        self.assertEqual(self.git(self.instalacao, "status", "--porcelain=v1").stdout, estado)
        self.assertEqual((self.instalacao / "motor.txt").read_bytes(), conteudo)
        self.assertTrue((self.instalacao / ".git/MERGE_HEAD").exists())

    def test_sem_main_local_cria_main_a_partir_da_publicada(self):
        self.git(self.instalacao, "switch", "--create", "documento")
        self.git(self.instalacao, "branch", "--delete", "main")
        self.executar()
        self.confirmar_main()

    def test_fetch_restrito_a_outra_branch_ainda_atualiza_main(self):
        self.git(self.instalacao, "config", "remote.origin.fetch", "+refs/heads/documento:refs/remotes/origin/documento")
        self.executar()
        self.confirmar_main()

    def test_sem_main_local_e_com_fetch_restrito_cria_main_publicada(self):
        self.git(self.instalacao, "switch", "--create", "documento")
        self.git(self.instalacao, "branch", "--delete", "main")
        self.git(self.instalacao, "config", "remote.origin.fetch", "+refs/heads/documento:refs/remotes/origin/documento")
        self.executar()
        self.confirmar_main()

    def test_head_destacado_com_commit_local_nao_e_movido(self):
        self.git(self.instalacao, "switch", "--detach")
        self.commit(self.instalacao, "local.md", "Trabalho local destacado\n")
        local = self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip()
        with self.assertRaisesRegex(AtualizacaoRecusada, "HEAD destacado"):
            self.executar()
        self.assertEqual(self.git(self.instalacao, "branch", "--show-current").stdout.strip(), "")
        self.assertEqual(self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip(), local)

    def test_arquivo_novo_que_colidiria_na_atualizacao_nao_e_sobrescrito(self):
        self.commit(self.publicador, "novo.txt", "Versao publicada\n")
        self.git(self.publicador, "push", "origin", "main")
        (self.instalacao / "novo.txt").write_text("Rascunho local\n", encoding="utf-8")
        with self.assertRaises(AtualizacaoRecusada):
            self.executar()
        self.assertEqual((self.instalacao / "novo.txt").read_text(), "Rascunho local\n")
        self.assertEqual(self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip(), self.inicial)

    def test_origem_indisponivel_preserva_instalacao(self):
        self.git(self.instalacao, "remote", "set-url", "origin", str(self.pasta / "inexistente.git"))
        with self.assertRaises(AtualizacaoRecusada):
            self.executar()
        self.assertEqual(self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip(), self.inicial)
        self.assertEqual((self.instalacao / "motor.txt").read_text(), "versao 1\n")

    def test_dado_ignorado_que_colidiria_no_avanco_nao_e_sobrescrito(self):
        (self.publicador / "data").mkdir()
        (self.publicador / "data/local.txt").write_text("Arquivo publicado sintetico\n", encoding="utf-8")
        self.git(self.publicador, "add", "--force", "data/local.txt")
        self.git(self.publicador, "-c", "user.name=Teste", "-c", "user.email=teste@example.invalid",
                 "commit", "--message", "Colisao sintetica")
        self.git(self.publicador, "push", "origin", "main")
        (self.instalacao / "data").mkdir()
        (self.instalacao / "data/local.txt").write_text("Dado local sintetico\n", encoding="utf-8")
        with self.assertRaises(AtualizacaoRecusada):
            self.executar()
        self.assertEqual((self.instalacao / "data/local.txt").read_text(), "Dado local sintetico\n")
        self.assertEqual(self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip(), self.inicial)

    def test_dado_ignorado_que_colidiria_na_troca_de_branch_nao_e_sobrescrito(self):
        self.git(self.instalacao, "switch", "--create", "documento")
        (self.publicador / "data").mkdir()
        (self.publicador / "data/local.txt").write_text("Arquivo publicado sintetico\n", encoding="utf-8")
        self.git(self.publicador, "add", "--force", "data/local.txt")
        self.git(self.publicador, "-c", "user.name=Teste", "-c", "user.email=teste@example.invalid",
                 "commit", "--message", "Colisao sintetica")
        self.git(self.publicador, "push", "origin", "main")
        self.git(self.instalacao, "fetch", "origin")
        self.git(self.instalacao, "branch", "--force", "main", "origin/main")
        (self.instalacao / "data").mkdir()
        (self.instalacao / "data/local.txt").write_text("Dado local sintetico\n", encoding="utf-8")
        with self.assertRaises(AtualizacaoRecusada):
            self.executar()
        self.assertEqual((self.instalacao / "data/local.txt").read_text(), "Dado local sintetico\n")
        self.assertEqual(self.git(self.instalacao, "branch", "--show-current").stdout.strip(), "documento")


if __name__ == "__main__":
    unittest.main()
