"""Consulta preparatória não executa backend nem promove evidência antiga."""

import ast
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys
import unittest

from app.capacidades import listar_capacidades, obter_capacidade


RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "listar_capacidades.py"


class TestCapacidades(unittest.TestCase):
    def test_parametros_correspondem_as_assinaturas_reais_sem_importar_backend(self):
        arvore = ast.parse((RAIZ / "app" / "dominio.py").read_text(encoding="utf-8"))
        funcoes = {item.name: item for item in arvore.body if isinstance(item, ast.FunctionDef)}
        for capacidade in listar_capacidades():
            with self.subTest(id=capacidade.id):
                funcao = funcoes[capacidade.funcao.rsplit(".", 1)[-1]]
                nomes = [arg.arg for arg in funcao.args.args]
                obrigatorios = len(nomes) - len(funcao.args.defaults)
                self.assertEqual([p.nome for p in capacidade.parametros], nomes)
                self.assertEqual([p.obrigatorio for p in capacidade.parametros],
                                 [indice < obrigatorios for indice in range(len(nomes))])

    def test_evidencia_historica_nao_habilita_agentes_nem_aprova_versao_atual(self):
        for capacidade in listar_capacidades():
            with self.subTest(id=capacidade.id):
                self.assertFalse(capacidade.agentes_habilitados)
                self.assertEqual(capacidade.status, "preparatoria")
                self.assertEqual(set(capacidade.operacoes_permitidas), {"gerar", "ler"})
                self.assertTrue(capacidade.pendencias)
        saidas = obter_capacidade("registro_saidas")
        self.assertIn("recusou o período", saidas.validacao.versao_atual)
        entradas = obter_capacidade("registro_entradas")
        self.assertIn("0.60", entradas.validacao.referencias)
        self.assertIn("revalidação", entradas.validacao.versao_atual)
        for identificador in ("sped_fiscal", "efd_contribuicoes"):
            self.assertIn("pendente", obter_capacidade(identificador).validacao.conteudo_historico)

    def test_ids_exatos_e_copias_sem_promocao_por_mutacao(self):
        original = obter_capacidade("registro_saidas")
        with self.assertRaises(FrozenInstanceError):
            original.agentes_habilitados = True
        copia = original.como_dict()
        copia["agentes_habilitados"] = True
        copia["validacao"]["versao_atual"] = "aprovada"
        self.assertFalse(original.agentes_habilitados)
        self.assertIn("recusou o período", original.validacao.versao_atual)
        for desconhecido in ("gerar_registro_saidas", "app.dominio.gerar_sped_fiscal", "transmitir"):
            with self.subTest(id=desconhecido), self.assertRaises(ValueError):
                obter_capacidade(desconhecido)

    def test_importacao_e_listagem_nao_carregam_backend_nem_leem_dados_locais(self):
        codigo = """
import importlib.abc
from pathlib import Path
import sys
from unittest.mock import patch

class Proibido(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {
            'app.dominio', 'app.tela', 'app.interacao', 'app.empresas',
            'app.ia', 'app.visao', 'tkinter', 'ttkbootstrap', 'pyautogui',
            'pytesseract', 'pynput',
        }:
            raise AssertionError('Backend carregado: ' + fullname)

sys.meta_path.insert(0, Proibido())
with patch.object(Path, 'read_text', side_effect=AssertionError('Leitura local')):
    with patch.object(Path, 'open', side_effect=AssertionError('Arquivo local')):
        from app.capacidades import listar_capacidades
        assert len(listar_capacidades()) == 5
print('consulta isolada OK')
"""
        resultado = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ,
                                   capture_output=True, text=True, check=False)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(resultado.stdout.strip(), "consulta isolada OK")

    def test_cli_json_texto_e_id_desconhecido(self):
        resultado = subprocess.run([sys.executable, str(SCRIPT), "--json"], cwd=RAIZ,
                                   capture_output=True, text=True, check=False)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        documento = json.loads(resultado.stdout)
        self.assertFalse(documento["executavel"])
        self.assertEqual({c["id"] for c in documento["capacidades"]},
                         {"sped_fiscal", "efd_contribuicoes", "registro_saidas", "registro_entradas", "resumo_acumulador"})
        self.assertTrue(all(not c["agentes_habilitados"] for c in documento["capacidades"]))
        texto = subprocess.run([sys.executable, str(SCRIPT), "--id", "registro_entradas"],
                               cwd=RAIZ, capture_output=True, text=True, check=False)
        self.assertEqual(texto.returncode, 0, texto.stderr)
        self.assertIn("Registro de Entradas", texto.stdout)
        self.assertIn("catálogo preparatório", texto.stdout)
        self.assertNotIn("Registro de Saídas", texto.stdout)
        invalido = subprocess.run([sys.executable, str(SCRIPT), "--id", "transmitir", "--json"],
                                 cwd=RAIZ, capture_output=True, text=True, check=False)
        self.assertEqual(invalido.returncode, 2)
        self.assertEqual(invalido.stdout, "")


if __name__ == "__main__":
    unittest.main()
