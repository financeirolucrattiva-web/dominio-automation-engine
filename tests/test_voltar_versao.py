"""Volta de versão e modo seguro contra repositórios Git reais locais, sem identidade configurada."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app import otimizacoes
from scripts import modo_otimizacoes
from scripts.atualizar_projeto import AtualizacaoRecusada, atualizar
from scripts.voltar_versao import tags_estaveis, voltar


@unittest.skipUnless(shutil.which("git"), "Git nao instalado")
class TestVoltarVersao(unittest.TestCase):
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
                        GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="Teste", GIT_AUTHOR_EMAIL="t@example.invalid",
                        GIT_COMMITTER_NAME="Teste", GIT_COMMITTER_EMAIL="t@example.invalid")
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
        self.git(self.publicador, "tag", "-a", "estavel-2026-10-21", "-m", "Lote completo rodou")
        self.git(self.publicador, "push", "origin", "main", "--tags")
        self.git(self.pasta, "clone", str(self.origem), str(self.instalacao))
        self.estavel = self.git(self.instalacao, "rev-parse", "HEAD").stdout.strip()
        self.commit(self.publicador, "motor.txt", "versao 2 (otimizada)\n")
        self.git(self.publicador, "push", "origin", "main")
        with contextlib.redirect_stdout(io.StringIO()):
            atualizar(self.instalacao)

    def git(self, pasta, *args, conferir=True):
        resultado = subprocess.run(["git", *args], cwd=pasta, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
        if conferir and resultado.returncode != 0:
            self.fail(resultado.stderr or resultado.stdout)
        return resultado

    def commit(self, pasta, nome, texto):
        (pasta / nome).write_text(texto, encoding="utf-8")
        self.git(pasta, "add", "--all")
        self.git(pasta, "commit", "--message", "Mudanca sintetica")

    def motor(self):
        return (self.instalacao / "motor.txt").read_text(encoding="utf-8")

    def test_lista_as_tags_estaveis_com_data_e_assunto(self):
        tags = tags_estaveis(self.instalacao)
        self.assertEqual([t[0] for t in tags], ["estavel-2026-10-21"])
        self.assertEqual(tags[0][2], "Lote completo rodou")

    def test_volta_para_a_estavel_numa_branch_local_sem_apagar_a_main(self):
        self.assertIn("versao 2", self.motor())
        main_antes = self.git(self.instalacao, "rev-parse", "main").stdout.strip()
        with contextlib.redirect_stdout(io.StringIO()):
            voltar(self.instalacao)
        self.assertEqual(self.motor(), "versao 1\n")
        self.assertEqual(self.git(self.instalacao, "branch", "--show-current").stdout.strip(),
                         "voltar-estavel-2026-10-21")
        self.assertEqual(self.git(self.instalacao, "rev-parse", "main").stdout.strip(), main_antes)

    def test_atualizar_bat_traz_a_versao_nova_de_volta(self):
        with contextlib.redirect_stdout(io.StringIO()):
            voltar(self.instalacao)
            atualizar(self.instalacao)
        self.assertIn("versao 2", self.motor())
        self.assertEqual(self.git(self.instalacao, "branch", "--show-current").stdout.strip(), "main")

    def test_voltar_de_novo_reutiliza_a_branch(self):
        with contextlib.redirect_stdout(io.StringIO()):
            voltar(self.instalacao)
            atualizar(self.instalacao)
            voltar(self.instalacao)
        self.assertEqual(self.motor(), "versao 1\n")

    def test_alteracao_local_em_arquivo_versionado_bloqueia_sem_perder_nada(self):
        (self.instalacao / "motor.txt").write_text("ajuste manual\n", encoding="utf-8")
        with self.assertRaises(AtualizacaoRecusada), contextlib.redirect_stdout(io.StringIO()):
            voltar(self.instalacao)
        self.assertEqual(self.motor(), "ajuste manual\n")

    def test_dados_locais_ignorados_ficam_intactos(self):
        (self.instalacao / "data").mkdir()
        (self.instalacao / "data" / "config.txt").write_text("minha configuracao", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            voltar(self.instalacao)
        self.assertEqual((self.instalacao / "data" / "config.txt").read_text(encoding="utf-8"),
                         "minha configuracao")

    def test_tag_inexistente_ou_fora_do_padrao_e_recusada(self):
        for tag in ("estavel-nao-existe", "v1.0"):
            with self.subTest(tag=tag), self.assertRaises(AtualizacaoRecusada), \
                    contextlib.redirect_stdout(io.StringIO()):
                voltar(self.instalacao, tag)
        self.assertIn("versao 2", self.motor())

    def test_sem_nenhuma_tag_estavel_diz_claramente(self):
        self.git(self.origem, "tag", "-d", "estavel-2026-10-21")
        self.git(self.instalacao, "tag", "-d", "estavel-2026-10-21")
        with self.assertRaises(AtualizacaoRecusada) as erro, contextlib.redirect_stdout(io.StringIO()):
            voltar(self.instalacao)
        self.assertIn("Nenhuma versao estavel", str(erro.exception))


class TestModoOtimizacoes(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.arquivo = Path(pasta.name) / "data" / "otimizacoes.json"
        for alvo, valor in (("ARQUIVO", self.arquivo), ("_forcado", None)):
            patcher = patch.object(otimizacoes, alvo, valor)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, {"DOMINIO_MODO_SEGURO": ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        otimizacoes.restaurar_para_testes()
        otimizacoes._forcado = None
        self.addCleanup(otimizacoes.restaurar_para_testes)

    def executar(self, *argumentos):
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = modo_otimizacoes.main(list(argumentos))
        return codigo, saida.getvalue()

    def test_seguro_e_rapido_alternam_o_arquivo_e_o_estado(self):
        codigo, texto = self.executar("seguro")
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(self.arquivo.read_text(encoding="utf-8")), {"modo_seguro": True})
        self.assertNotIn("  LIGADA ", texto)
        codigo, texto = self.executar("rapido")
        self.assertFalse(self.arquivo.exists())
        self.assertNotIn("desligada", texto)

    def test_desligar_e_ligar_uma_so(self):
        self.executar("desligar", "ocr_paralelo")
        self.assertEqual(json.loads(self.arquivo.read_text(encoding="utf-8")), {"ocr_paralelo": False})
        self.assertFalse(otimizacoes.ativa("ocr_paralelo"))
        self.assertTrue(otimizacoes.ativa("geometria_lembrada"))
        self.executar("ligar", "ocr_paralelo")
        self.assertFalse(self.arquivo.exists())

    def test_nome_desconhecido_e_recusado_sem_gravar(self):
        with contextlib.redirect_stderr(io.StringIO()):
            codigo, _ = self.executar("desligar", "inventada")
        self.assertEqual(codigo, 1)
        self.assertFalse(self.arquivo.exists())

    def test_status_nao_altera_nada(self):
        codigo, texto = self.executar("status")
        self.assertEqual(codigo, 0)
        self.assertIn("ocr_paralelo", texto)
        self.assertFalse(self.arquivo.exists())


if __name__ == "__main__":
    unittest.main()
