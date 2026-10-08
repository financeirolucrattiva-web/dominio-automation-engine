import json
from pathlib import Path
import tempfile
import unittest
from app import configuracao_rotinas as rotinas


class TestConfiguracaoRotinas(unittest.TestCase):
    def dados(self):
        return {"nome": "Relatório de teste", "passos": [{"tipo": "clicar", "valor": "Relatórios"},
                {"tipo": "digitar", "valor": "inicio"}, {"tipo": "tecla", "valor": "tab"}]}

    def test_salva_formato_do_gravador_sem_aprovar_ou_executar(self):
        with tempfile.TemporaryDirectory() as pasta:
            resultado = rotinas.salvar(self.dados(), pasta)
            arquivo = Path(pasta) / (resultado["id"] + ".json")
            dados = json.loads(arquivo.read_text())
            self.assertEqual(dados["status"], "rascunho")
            self.assertEqual(dados["parametros"], ["inicio"])
            self.assertEqual(dados["passos"][0]["texto_adivinhado"], "Relatórios")
            self.assertEqual(dados["passos"][1]["parametro"], "inicio")
            self.assertNotIn("caminho", rotinas.listar(pasta)[0])

    def test_recusa_execucao_codigo_caminhos_transmissao_e_senhas_literais(self):
        for passo in ({"tipo": "python", "valor": "exec(...)"}, {"tipo": "clicar", "valor": "Transmitir"},
                      {"tipo": "clicar", "valor": "Exclusão"}, {"tipo": "digitar", "valor": "senha privada"},
                      {"tipo": "clicar", "valor": "Relatórios", "arquivo": "C:/qualquer"},
                      {"tipo": "tecla", "valor": "win"}):
            with self.subTest(passo=passo), self.assertRaises(ValueError):
                rotinas.validar_rotina({"nome": "Teste", "passos": [passo]})

    def test_salvar_nao_sobrescreve_gravacao_existente(self):
        with tempfile.TemporaryDirectory() as pasta:
            anterior = Path(pasta) / "rotina.json"
            anterior.write_text(json.dumps({"nome_exibicao": "Anterior", "passos": [], "status": "aprovada"}))
            rotinas.salvar(self.dados(), pasta)
            self.assertEqual(len(rotinas.listar(pasta)), 2)
            self.assertEqual(json.loads(anterior.read_text())["status"], "aprovada")
