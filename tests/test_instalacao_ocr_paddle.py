"""Instalação opcional e download fixo simulados, sem pacote/modelo real."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


ROOT_REPO = Path(__file__).resolve().parents[1]


def carregar_script(nome):
    spec = importlib.util.spec_from_file_location(f"_{nome}_teste", ROOT_REPO / "scripts" / f"{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class TestInstalacaoOpcional(unittest.TestCase):
    def setUp(self):
        self.m = carregar_script("instalar_ocr_paddle")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.ambiente = self.raiz / ".venv-ocr-paddle"
        self.marcador = self.raiz / "data" / "ocr_paddle_instalado.json"
        self.baseline = self.raiz / "requirements.txt"
        self.baseline.write_text("DEPENDENCIA_BASELINE_FIXTICIA==1.0\n", encoding="utf-8")
        self.cfg_baseline = self.raiz / ".venv" / "pyvenv.cfg"
        self.cfg_baseline.parent.mkdir()
        self.cfg_baseline.write_text("ambiente de produção fictício\n", encoding="utf-8")
        self.requirements = self.raiz / "requirements-ocr-paddle.txt"
        self.requirements.write_bytes((ROOT_REPO / "requirements-ocr-paddle.txt").read_bytes())
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.console = io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.console))
        self.stack.enter_context(patch.object(self.m, "ROOT", self.raiz))
        self.stack.enter_context(patch.object(self.m, "PASTA_AMBIENTE", self.ambiente))
        self.stack.enter_context(patch.object(self.m, "MARCADOR_INSTALACAO", self.marcador))
        self.builder = self.stack.enter_context(patch.object(self.m.venv, "EnvBuilder"))
        self.run = self.stack.enter_context(patch.object(self.m.subprocess, "run"))
        self.compatibilidade = self.stack.enter_context(patch.object(self.m, "ambiente_compativel", return_value=True))

    def test_incompativel_rejeita_antes_de_venv_subprocess_ou_filesystem(self):
        self.compatibilidade.return_value = False
        with patch.object(Path, "is_file") as is_file, patch.object(Path, "mkdir") as mkdir, patch.object(Path, "write_text") as write_text, patch.object(Path, "replace") as replace:
            self.assertEqual(self.m.instalar(), 1)
        self.builder.assert_not_called()
        self.run.assert_not_called()
        for operacao in (is_file, mkdir, write_text, replace):
            operacao.assert_not_called()
        self.assertFalse(self.ambiente.exists())
        self.assertFalse(self.marcador.exists())

    def test_sucesso_usa_argv_lista_requirements_pinados_e_preserva_baseline(self):
        antes = {arquivo: arquivo.read_bytes() for arquivo in (self.baseline, self.cfg_baseline, self.requirements)}
        self.assertEqual(self.m.instalar(), 0)
        self.builder.assert_called_once_with(with_pip=True)
        self.builder.return_value.create.assert_called_once_with(self.ambiente)
        comandos = [chamada.args[0] for chamada in self.run.call_args_list]
        python = str(self.ambiente / "Scripts" / "python.exe")
        self.assertEqual(comandos, [
            [python, "-m", "pip", "install", "-r", str(self.requirements)],
            [python, "-m", "pip", "check"],
            [python, str(self.raiz / "scripts" / "preparar_modelos_ocr.py")],
        ])
        for chamada in self.run.call_args_list:
            self.assertIsInstance(chamada.args[0], list)
            self.assertEqual(chamada.kwargs, {"check": True})
        for linha in self.requirements.read_text().splitlines():
            if linha and not linha.startswith("#"):
                self.assertRegex(linha, r"^[A-Za-z0-9_.-]+==[^=]+$")
        self.assertEqual(json.loads(self.marcador.read_text()), {"versao": 1, "uso": "avaliacao_cpu"})
        self.assertEqual({arquivo: arquivo.read_bytes() for arquivo in antes}, antes)

    def test_ambiente_opcional_existente_nao_e_recriado(self):
        python = self.ambiente / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True)
        python.write_bytes(b"executavel ficticio")
        self.assertEqual(self.m.instalar(), 0)
        self.builder.assert_not_called()
        self.assertEqual(python.read_bytes(), b"executavel ficticio")

    def test_pip_falha_nao_baixa_modelos_nem_escreve_marcador(self):
        self.run.side_effect = subprocess.CalledProcessError(1, ["pip"])
        self.assertEqual(self.m.instalar(), 1)
        self.assertEqual(self.run.call_count, 1)
        self.assertFalse(self.marcador.exists())
        self.assertNotIn("Instalação opcional preparada", self.console.getvalue())

    def test_pip_check_falha_nao_baixa_modelos_nem_escreve_marcador(self):
        self.run.side_effect = [None, subprocess.CalledProcessError(1, ["pip", "check"])]
        self.assertEqual(self.m.instalar(), 1)
        self.assertEqual(self.run.call_count, 2)
        self.assertFalse(self.marcador.exists())

    def test_preparacao_modelos_falha_nao_anuncia_instalacao_preparada(self):
        self.run.side_effect = [None, None, subprocess.CalledProcessError(1, ["preparar_modelos"])]
        self.assertEqual(self.m.instalar(), 1)
        self.assertEqual(self.run.call_count, 3)
        self.assertFalse(self.marcador.exists())

    def test_excecao_do_setup_nao_imprime_conteudo_privado(self):
        self.builder.return_value.create.side_effect = RuntimeError("CAMINHO_PRIVADO_FICTICIO/SEGREDO_FICTICIO")
        self.assertEqual(self.m.instalar(), 1)
        self.assertIn("RuntimeError", self.console.getvalue())
        self.assertNotIn("CAMINHO_PRIVADO", self.console.getvalue())
        self.assertNotIn("SEGREDO_FICTICIO", self.console.getvalue())


class TestRequisitosAmbiente(unittest.TestCase):
    def test_matriz_windows_python_arquitetura(self):
        m = carregar_script("instalar_ocr_paddle")
        casos = (
            ("win32", "AMD64", 8, (3, 10), True),
            ("win32", "x86_64", 8, (3, 13), True),
            ("win32", "AMD64", 8, (3, 12), True),
            ("linux", "AMD64", 8, (3, 12), False),
            ("win32", "ARM64", 8, (3, 12), False),
            ("win32", "AMD64", 4, (3, 12), False),
            ("win32", "AMD64", 8, (3, 9), False),
            ("win32", "AMD64", 8, (3, 14), False),
        )
        for plataforma, maquina, ponteiro, versao, esperado in casos:
            with self.subTest(plataforma=plataforma, maquina=maquina, ponteiro=ponteiro, versao=versao):
                with patch.object(m.sys, "platform", plataforma), patch.object(m.sys, "version_info", versao), patch.object(m.platform, "machine", return_value=maquina), patch.object(m.struct, "calcsize", return_value=ponteiro):
                    self.assertEqual(m.ambiente_compativel(), esperado)

    def test_venv_opcional_e_marcador_estao_gitignored(self):
        resultado = subprocess.run(["git", "check-ignore", "--no-index", ".venv-ocr-paddle/Scripts/python.exe", "data/ocr_paddle_instalado.json"], cwd=ROOT_REPO, text=True, capture_output=True, check=False)
        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(set(resultado.stdout.splitlines()), {".venv-ocr-paddle/Scripts/python.exe", "data/ocr_paddle_instalado.json"})


class TestPreparacaoModelos(unittest.TestCase):
    def setUp(self):
        self.m = carregar_script("preparar_modelos_ocr")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name) / "modelos"
        self.console, self.stderr = io.StringIO(), io.StringIO()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(self.console))
        self.stack.enter_context(contextlib.redirect_stderr(self.stderr))

    def preencher(self, argumentos, conteudo=b"MODELO_FICTICIO"):
        destino = Path(argumentos["local_dir"])
        destino.mkdir(parents=True, exist_ok=True)
        for arquivo in self.m.ARQUIVOS:
            (destino / arquivo).write_bytes(conteudo)

    def preparar_cache(self, revisao_correta=True):
        for nome, revisao in self.m.MODELOS:
            destino = self.pasta / nome
            self.preencher({"local_dir": str(destino)}, b"ARQUIVO_ANTIGO_FICTICIO")
            (destino / "revisao.json").write_text(json.dumps({"repositorio": f"PaddlePaddle/{nome}", "revisao": revisao if revisao_correta else "revisao_antiga_ficticia"}), encoding="utf-8")

    def test_download_somente_dois_ids_revisoes_fixas_e_allowlist(self):
        self.assertEqual(self.m.MODELOS, (
            ("PP-OCRv5_mobile_det", "0d63e78e2b680928f6b1747d76a08db6e645efb7"),
            ("latin_PP-OCRv5_mobile_rec", "ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57"),
        ))
        chamadas = []
        def baixar(**argumentos):
            chamadas.append(argumentos)
            print("CONTEUDO_PRIVADO_FICTICIO", file=sys.stderr)
            print("CAMINHO_PRIVADO_FICTICIO")
            self.preencher(argumentos)
        abrir_original = Path.open
        acessos = []
        def abrir(caminho, *args, **kwargs):
            self.assertTrue(caminho.is_relative_to(self.pasta), "Downloader não deve ler capturas ou documentos fora da pasta de modelos.")
            acessos.append(caminho)
            return abrir_original(caminho, *args, **kwargs)
        with patch.object(Path, "open", new=abrir):
            self.m.preparar(baixar, self.pasta)
        self.assertTrue(acessos)
        self.assertEqual(len(chamadas), 2)
        for argumentos, (nome, revisao) in zip(chamadas, self.m.MODELOS):
            self.assertEqual(set(argumentos), {"repo_id", "revision", "allow_patterns", "local_dir"})
            self.assertEqual(argumentos["repo_id"], f"PaddlePaddle/{nome}")
            self.assertEqual(argumentos["revision"], revisao)
            self.assertRegex(revisao, r"^[0-9a-f]{40}$")
            self.assertEqual(argumentos["allow_patterns"], ["inference.json", "inference.pdiparams", "inference.yml"])
            self.assertTrue(Path(argumentos["local_dir"]).is_relative_to(self.pasta))
            marcador = json.loads((self.pasta / nome / "revisao.json").read_text())
            self.assertEqual(marcador, {"repositorio": argumentos["repo_id"], "revisao": revisao})
        self.assertNotIn("PRIVADO_FICTICIO", self.console.getvalue() + self.stderr.getvalue())
        self.assertFalse(any(path.name in ("capturas", "saida", "screenshots") for path in self.pasta.rglob("*")))

    def test_revisao_valida_com_tres_arquivos_reutiliza_cache_sem_download(self):
        self.preparar_cache()
        antes = {path.relative_to(self.pasta): path.read_bytes() for path in self.pasta.rglob("*") if path.is_file()}
        baixar = Mock()
        self.m.preparar(baixar, self.pasta)
        baixar.assert_not_called()
        self.assertEqual({path.relative_to(self.pasta): path.read_bytes() for path in self.pasta.rglob("*") if path.is_file()}, antes)

    def test_download_incompleto_nao_escreve_revisao_valida(self):
        def baixar(**argumentos):
            destino = Path(argumentos["local_dir"])
            for arquivo in self.m.ARQUIVOS[:2]:
                (destino / arquivo).write_bytes(b"ARQUIVO_FICTICIO")
        with self.assertRaises(ValueError):
            self.m.preparar(baixar, self.pasta)
        self.assertFalse(any(self.pasta.rglob("revisao.json")))
        self.assertNotIn("Modelo local preparado", self.console.getvalue())

    def test_arquivo_vazio_nao_valida_modelo(self):
        def baixar(**argumentos):
            self.preencher(argumentos)
            (Path(argumentos["local_dir"]) / "inference.pdiparams").write_bytes(b"")
        with self.assertRaises(ValueError):
            self.m.preparar(baixar, self.pasta)
        self.assertFalse(any(self.pasta.rglob("revisao.json")))

    def test_revisao_antiga_e_download_parcial_preservam_cache_sem_marcar_nova(self):
        self.preparar_cache(revisao_correta=False)
        antes = {path.relative_to(self.pasta): path.read_bytes() for path in self.pasta.rglob("*") if path.is_file()}
        def baixar(**argumentos):
            destino = Path(argumentos["local_dir"])
            for arquivo in self.m.ARQUIVOS[:2]:
                (destino / arquivo).write_bytes(b"ARQUIVO_NOVO_FICTICIO")
        with self.assertRaises(ValueError):
            self.m.preparar(baixar, self.pasta)
        self.assertEqual({path.relative_to(self.pasta): path.read_bytes() for path in self.pasta.rglob("*") if path.is_file()}, antes)

    def test_main_falha_nao_expoe_imagem_conteudo_ou_caminho_do_erro(self):
        def baixar(**argumentos):
            print("TEXTO_PRIVADO_FICTICIO")
            print("C:/CAMINHO_PRIVADO_FICTICIO", file=sys.stderr)
            raise RuntimeError("IMAGEM_CLIENTE_FICTICIA C:/OUTRO_CAMINHO_PRIVADO")
        hf = types.ModuleType("huggingface_hub")
        hf.snapshot_download = baixar
        preparar_real = self.m.preparar
        with patch.dict(sys.modules, {"huggingface_hub": hf}), patch.object(sys, "argv", ["preparar_modelos_ocr.py"]), patch.object(self.m, "preparar", side_effect=lambda callback: preparar_real(callback, self.pasta)):
            self.assertEqual(self.m.main(), 1)
        texto = self.console.getvalue() + self.stderr.getvalue()
        self.assertIn("RuntimeError", texto)
        for segredo in ("TEXTO_PRIVADO", "CAMINHO_PRIVADO", "IMAGEM_CLIENTE", str(self.pasta)):
            self.assertNotIn(segredo, texto)
        self.assertFalse(any(self.pasta.rglob("revisao.json")))
        self.assertNotIn("Dois modelos PP-OCRv5 preparados", texto)

    def test_cache_local_configurado_antes_do_hub_preserva_override_operador(self):
        hf = types.ModuleType("huggingface_hub")
        hf.snapshot_download = Mock()
        for configurado in (None, str(self.pasta / "cache_operador")):
            with self.subTest(override=configurado):
                variaveis = {} if configurado is None else {"HF_HOME": configurado}
                with patch.dict(os.environ, variaveis, clear=True), patch.dict(sys.modules, {"huggingface_hub": hf}), patch.object(sys, "argv", ["preparar_modelos_ocr.py"]):
                    def conferir(callback):
                        self.assertIs(callback, hf.snapshot_download)
                        esperado = configurado or str(self.m.ROOT / "data" / "huggingface_cache")
                        self.assertEqual(os.environ["HF_HOME"], esperado)
                    with patch.object(self.m, "preparar", side_effect=conferir):
                        self.assertEqual(self.m.main(), 0)
                hf.snapshot_download.assert_not_called()

    def test_falha_na_promocao_restaura_modelos_anteriores(self):
        self.preparar_cache(revisao_correta=False)
        antes = {path.relative_to(self.pasta): path.read_bytes() for path in self.pasta.rglob("*") if path.is_file()}
        substituir_original = Path.replace
        def substituir(caminho, destino):
            if caminho.name.startswith(".download-"):
                raise PermissionError("Falha de promoção fictícia")
            return substituir_original(caminho, destino)
        with patch.object(Path, "replace", new=substituir):
            with self.assertRaises(PermissionError):
                self.m.preparar(lambda **argumentos: self.preencher(argumentos), self.pasta)
        self.assertEqual({path.relative_to(self.pasta): path.read_bytes() for path in self.pasta.rglob("*") if path.is_file()}, antes)
        self.assertFalse(any(path.name.startswith((".download-", ".anterior-")) for path in self.pasta.iterdir()))

    def test_download_completo_troca_revisao_sem_misturar_cache_antigo(self):
        self.preparar_cache(revisao_correta=False)
        self.m.preparar(lambda **argumentos: self.preencher(argumentos, b"NOVA_REVISAO_FICTICIA"), self.pasta)
        for nome, revisao in self.m.MODELOS:
            destino = self.pasta / nome
            self.assertEqual(json.loads((destino / "revisao.json").read_text())["revisao"], revisao)
            for arquivo in self.m.ARQUIVOS:
                self.assertEqual((destino / arquivo).read_bytes(), b"NOVA_REVISAO_FICTICIA")
        self.assertFalse(any(path.name.startswith((".download-", ".anterior-")) for path in self.pasta.iterdir()))


if __name__ == "__main__":
    unittest.main()
