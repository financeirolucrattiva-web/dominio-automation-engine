"""Bootstrap do OCR escolhe intérprete compatível sem trocar o Python do SPED."""

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch
import contextlib
import io


def carregar():
    arquivo = Path(__file__).resolve().parents[1] / "scripts" / "instalar_ocr_paddle.py"
    spec = importlib.util.spec_from_file_location("instalador_selecao_teste", arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def ambiente(versao=(3, 12, 9), bits=64, implementacao="CPython"):
    return {"versao": list(versao), "bits": bits, "implementacao": implementacao,
            "plataforma": "win32", "maquina": "AMD64"}


class TestSelecaoPythonOCR(unittest.TestCase):
    def setUp(self):
        self.m = carregar()
        self.console = io.StringIO()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(self.console))

    def test_probe_aceita_cp312_e_rejeita_version_bitness_implementacao(self):
        for dados, esperado in ((ambiente(), True), (ambiente((3, 14, 7)), False),
                                (ambiente(bits=32), False), (ambiente(implementacao="PyPy"), False),
                                ({"versao": ["3", "12", "9"]}, False)):
            with self.subTest(dados=dados), patch.object(self.m.subprocess, "run", return_value=Mock(returncode=0, stdout=json.dumps(dados))) as executar:
                self.assertEqual(self.m.consultar_python("python com espaço.exe") is not None, esperado)
                chamada = executar.call_args
                self.assertEqual(chamada.args[0][:3], ["python com espaço.exe", "-I", "-c"])
                self.assertEqual(chamada.kwargs["timeout"], 3)
                self.assertNotIn("shell", chamada.kwargs)

    def test_probe_falha_ou_timeout_nao_aprova_executavel(self):
        for resultado in (Mock(returncode=1), Mock(returncode=0, stdout="saida inválida")):
            with patch.object(self.m.subprocess, "run", return_value=resultado):
                self.assertIsNone(self.m.consultar_python("python.exe"))
        with patch.object(self.m.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 3)):
            self.assertIsNone(self.m.consultar_python("python.exe"))

    def test_launcher_lista_existentes_e_prefere312_em_vez314_padrao(self):
        saida = "Installed Pythons:\n -V:3.14 * C:\\Python314\\python.exe\n -3.13-64 C:\\Python 313\\python.exe\n -V:3.12 C:\\Python 312\\python.exe\n"
        respostas = {"C:\\Python314\\python.exe": None,
                     "C:\\Python 313\\python.exe": ambiente((3, 13, 4)),
                     "C:\\Python 312\\python.exe": ambiente()}
        with patch.object(Path, "is_file", return_value=False), patch.object(self.m.shutil, "which", return_value="py.exe"), patch.object(self.m.subprocess, "run", return_value=Mock(returncode=0, stdout=saida)) as executar, patch.object(self.m, "consultar_python", side_effect=lambda exe: respostas[str(exe)]):
            encontrado = self.m.localizar_python_compativel()
        self.assertEqual(encontrado[0], "C:\\Python 312\\python.exe")
        executar.assert_called_once_with(["py.exe", "-0p"], capture_output=True, text=True, timeout=5, check=False)

    def test_ambiente_ocr_existente_compativel_tem_precedencia(self):
        with patch.object(Path, "is_file", return_value=True), patch.object(self.m, "consultar_python", return_value=ambiente()), patch.object(self.m.shutil, "which") as launcher:
            encontrado = self.m.localizar_python_compativel()
        self.assertEqual(encontrado[0], str(self.m.PASTA_AMBIENTE / "Scripts" / "python.exe"))
        launcher.assert_not_called()

    def test_python_instalado_sem_launcher_e_confirmado_no_diretorio_padrao(self):
        local = str(Path("python_local_teste"))
        esperado = Path(local) / "Programs" / "Python" / "Python313" / "python.exe"
        with patch.dict(self.m.os.environ, {"LOCALAPPDATA": local}), patch.object(Path, "is_file", lambda caminho: caminho == esperado), patch.object(self.m.shutil, "which", return_value=None), patch.object(self.m, "consultar_python", return_value=ambiente((3, 13, 7))) as consultar:
            encontrado = self.m.localizar_python_compativel()
        self.assertEqual(encontrado[0], str(esperado))
        consultar.assert_called_once_with(str(esperado))

    def test_diretorio_padrao_incompativel_nao_e_aceito_so_por_existir(self):
        local = str(Path("python_local_teste"))
        candidato = Path(local) / "Programs" / "Python" / "Python313" / "python.exe"
        with patch.dict(self.m.os.environ, {"LOCALAPPDATA": local}), patch.object(Path, "is_file", lambda caminho: caminho == candidato), patch.object(self.m.shutil, "which", return_value=None), patch.object(self.m, "consultar_python", return_value=None):
            self.assertIsNone(self.m.localizar_python_compativel())

    def test_sem_launcher_ou_listagem_falha_nao_instala_python(self):
        with patch.object(Path, "is_file", return_value=False), patch.object(self.m.shutil, "which", return_value=None), patch.object(self.m.subprocess, "run") as executar:
            self.assertIsNone(self.m.localizar_python_compativel())
            executar.assert_not_called()
        with patch.object(Path, "is_file", return_value=False), patch.object(self.m.shutil, "which", return_value="py.exe"), patch.object(self.m.subprocess, "run", side_effect=subprocess.TimeoutExpired("py", 5)):
            self.assertIsNone(self.m.localizar_python_compativel())

    def test_314_reinicia_com312_e_propaga_codigo_saida_sem_mutar_path(self):
        executavel = "C:\\Python 312\\python.exe"
        with patch.object(self.m.sys, "platform", "win32"), patch.object(self.m.sys, "version_info", (3, 14, 7)), patch.object(self.m, "ambiente_compativel", return_value=False), patch.object(Path, "is_file", return_value=False), patch.object(self.m, "localizar_python_compativel", return_value=(executavel, ambiente())), patch.object(self.m, "instalar") as instalar, patch.object(self.m.subprocess, "run", return_value=Mock(returncode=7)) as executar:
            self.assertEqual(self.m.main([]), 7)
        self.assertEqual(executar.call_args.args[0], [executavel, str(Path(self.m.__file__).resolve()), "--usar-python-atual"])
        self.assertEqual(executar.call_args.kwargs, {"check": False})
        instalar.assert_not_called()
        self.assertIn("Python detectado: 3.14.7", self.console.getvalue())
        self.assertIn("Usando Python 3.12.9", self.console.getvalue())
        self.assertNotIn(executavel, self.console.getvalue())

    def test_sem312_disponivel_explica_prerequisito_sem_criar_ambiente(self):
        with patch.object(self.m.sys, "platform", "win32"), patch.object(self.m, "ambiente_compativel", return_value=False), patch.object(Path, "is_file", return_value=False), patch.object(self.m, "localizar_python_compativel", return_value=None), patch.object(self.m, "instalar") as instalar, patch.object(self.m.subprocess, "run") as executar:
            self.assertEqual(self.m.main([]), 1)
        instalar.assert_not_called()
        executar.assert_not_called()
        self.assertIn("Nenhum Python compatível", self.console.getvalue())
        self.assertIn("lado a lado", self.console.getvalue())

    def test_python_atual_compativel_nao_depende_do_launcher(self):
        with patch.object(self.m.sys, "platform", "win32"), patch.object(Path, "is_file", return_value=False), patch.object(self.m, "ambiente_compativel", return_value=True), patch.object(self.m, "instalar", return_value=0) as instalar, patch.object(self.m, "localizar_python_compativel") as procurar:
            self.assertEqual(self.m.main([]), 0)
        instalar.assert_called_once_with()
        procurar.assert_not_called()

    def test_processo_delegado_nao_se_reinicia_em_loop(self):
        with patch.object(self.m, "instalar", return_value=0) as instalar, patch.object(self.m, "localizar_python_compativel") as procurar:
            self.assertEqual(self.m.main(["--usar-python-atual"]), 0)
        instalar.assert_called_once_with()
        procurar.assert_not_called()


class TestInstalacaoPythonOCR(unittest.TestCase):
    def setUp(self):
        self.m = carregar()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.console = io.StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.console))
        self.stack.enter_context(patch.object(self.m.sys, "platform", "win32"))
        self.stack.enter_context(patch.object(self.m.platform, "machine", return_value="AMD64"))
        self.stack.enter_context(patch.object(self.m.struct, "calcsize", return_value=8))
        self.stack.enter_context(patch.object(self.m, "ambiente_compativel", return_value=False))
        self.stack.enter_context(patch.object(Path, "is_file", return_value=False))
        self.compativel = ("Python313/python.exe", ambiente((3, 13, 7)))

    def test_atalho_reutiliza_compatibilidade_existente_sem_instalar_python(self):
        with patch.object(self.m, "localizar_python_compativel", return_value=self.compativel), patch.object(self.m.shutil, "which") as procurar, patch.object(self.m.subprocess, "run", return_value=Mock(returncode=0)) as executar:
            self.assertEqual(self.m.main(["--instalar-python"]), 0)
        procurar.assert_not_called()
        self.assertEqual(executar.call_args.args[0][0], self.compativel[0])

    def test_winget_instala_x64_por_usuario_sem_path_launcher_ou_associacoes(self):
        anterior = dict(self.m.os.environ)
        with patch.object(self.m, "localizar_python_compativel", side_effect=[None, self.compativel]), patch.object(self.m.shutil, "which", return_value="winget.exe"), patch.object(self.m.subprocess, "run", side_effect=[Mock(returncode=0), Mock(returncode=9)]) as executar:
            self.assertEqual(self.m.main(["--instalar-python"]), 9)
        comando = executar.call_args_list[0].args[0]
        self.assertEqual(comando[:4], ["winget.exe", "install", "--id", "Python.Python.3.13"])
        self.assertIn("--architecture", comando)
        self.assertEqual(comando[comando.index("--architecture") + 1], "x64")
        self.assertEqual(comando[comando.index("--scope") + 1], "user")
        opcoes = comando[comando.index("--override") + 1].split()
        for opcao in ("InstallAllUsers=0", "PrependPath=0", "AppendPath=0", "Include_launcher=0", "AssociateFiles=0"):
            self.assertIn(opcao, opcoes)
        self.assertEqual(executar.call_args_list[1].args[0][0], self.compativel[0])
        self.assertEqual(dict(self.m.os.environ), anterior)
        self.assertTrue(all("shell" not in chamada.kwargs for chamada in executar.call_args_list))

    def test_winget_ausente_explica_alternativa_sem_criar_ocr(self):
        with patch.object(self.m, "localizar_python_compativel", return_value=None), patch.object(self.m.shutil, "which", return_value=None), patch.object(self.m.subprocess, "run") as executar:
            self.assertEqual(self.m.main(["--instalar-python"]), 1)
        executar.assert_not_called()
        self.assertIn("winget não encontrado", self.console.getvalue())
        self.assertIn("https://www.python.org/downloads/windows/", self.console.getvalue())

    def test_falha_do_winget_interrompe_sem_instalar_ocr(self):
        for falha in (Mock(returncode=1), OSError("indisponivel")):
            with self.subTest(falha=falha), patch.object(self.m, "localizar_python_compativel", return_value=None) as procurar, patch.object(self.m.shutil, "which", return_value="winget.exe"), patch.object(self.m.subprocess, "run", side_effect=[falha]) as executar:
                self.assertEqual(self.m.main(["--instalar-python"]), 1)
            self.assertEqual(executar.call_count, 1)
            self.assertEqual(procurar.call_count, 1)

    def test_sucesso_winget_sem_python_confirmado_nao_declara_instalacao_ocr(self):
        with patch.object(self.m, "localizar_python_compativel", return_value=None), patch.object(self.m.shutil, "which", return_value="winget.exe"), patch.object(self.m.subprocess, "run", return_value=Mock(returncode=0)) as executar:
            self.assertEqual(self.m.main(["--instalar-python"]), 1)
        self.assertEqual(executar.call_count, 1)
        self.assertIn("nenhum Python compatível foi confirmado", self.console.getvalue())

    def test_linux_ou_arm_nao_executa_winget(self):
        for sistema, arquitetura in (("linux", "AMD64"), ("win32", "ARM64")):
            with self.subTest(sistema=sistema), patch.object(self.m.sys, "platform", sistema), patch.object(self.m.platform, "machine", return_value=arquitetura), patch.object(self.m.subprocess, "run") as executar:
                self.assertEqual(self.m.main(["--instalar-python"]), 1)
            executar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
