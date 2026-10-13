"""Migração real de SQLite, sem emissão, desktop ou dados do escritório."""
import json
from pathlib import Path
import tempfile
import unittest

from app import capacidades
from app.configuracao_lotes import NOME_LIVROS_CONJUNTOS
from app.servidor import RepositorioTarefas
from test_servidor import pedido


class TestCadastroConjunto(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = RepositorioTarefas(Path(temp.name) / "banco.sqlite3")
        self.config = self.repo.configuracao
        # Banco legado com as migrações anteriores já concluídas.
        with self.repo.conectar() as banco:
            for marco in ("piloto_lp_lr_v1", "piloto_lp_lr_icms_v2",
                          "piloto_lp_lr_efd_integrada_v3", "piloto_lp_lr_resumo_integrado_v4"):
                banco.execute("INSERT INTO marcos_cadastro VALUES (?)", (marco,))
        self.icms = self.config.cadastrar_rotina("Livro Fiscal de ICMS")

    def conjunta(self):
        return next(r for r in self.config.listar()["rotinas"] if r["nome"] == NOME_LIVROS_CONJUNTOS)

    def test_agrupa_no_primeiro_livro_e_preserva_empresa_historico_e_roteiro_anterior(self):
        passos = [{"tipo": "clicar", "valor": "Relatórios"}]
        self.config.configurar_rotina(self.icms["id"], {"nome": self.icms["nome"], "passos": passos})
        self.config.enviar_validacao(self.icms["id"])
        sequencia = ["resumo_acumulador", "registro_saidas", "efd_contribuicoes", self.icms["id"], "registro_entradas"]
        presumido = self.config.salvar_regime(None, "Lucro Presumido", sequencia)
        self.config.salvar_regime(None, "Lucro Real", list(reversed(sequencia)))
        self.config.salvar_empresa("52", "Empresa sintética", presumido["id"], "EMPRESA", "LIVROS")
        empresas = self.config.listar()["empresas"]
        tarefa, _ = self.repo.criar(pedido(), "simulacao")
        self.repo.concluir(tarefa["id"], "falha", False)
        historico = self.repo.listar()
        self.config.preparar_piloto()
        conjunta = self.conjunta()
        self.assertEqual(conjunta["status"], "integrada")
        sequencias = [r["rotinas"] for r in self.config.listar()["regimes"]]
        self.assertEqual(sequencias, [["resumo_acumulador", conjunta["id"], "efd_contribuicoes"],
                                     [conjunta["id"], "efd_contribuicoes", "resumo_acumulador"]])
        self.assertEqual(self.config.listar()["empresas"], empresas)
        self.assertEqual(self.repo.listar(), historico)
        with self.repo.conectar() as banco:
            arquivada = banco.execute("SELECT * FROM rotinas_cadastradas_arquivo WHERE id=?", (self.icms["id"],)).fetchone()
        self.assertEqual(json.loads(arquivada["passos"]), passos)
        self.assertEqual(arquivada["status"], "aguardando_validacao")
        plano = self.config.planejar({"empresas": ["52"], "inicio": "2024-02-01", "fim": "2024-02-29"})
        self.assertEqual(plano['empresas'][0]['rotinas'], ["resumo_acumulador", 'livros_fiscais', "efd_contribuicoes"])
        self.assertIn(conjunta["id"], [c.id for c in capacidades.listar_capacidades()])

    def test_preserva_sequencia_parcial_e_regimes_fora_do_piloto(self):
        parcial = self.config.salvar_regime(None, "Lucro Presumido", ["registro_entradas", self.icms["id"]])
        outro = self.config.salvar_regime(None, "Outro regime", ["registro_saidas", self.icms["id"], "registro_entradas"])
        self.config.preparar_piloto()
        regimes = {r["id"]: r for r in self.config.listar()["regimes"]}
        for original in (parcial, outro):
            self.assertEqual(regimes[original["id"]], original)
        self.assertEqual(self.config.obter_rotina(self.icms["id"])["status"], "pendente_configuracao")

    def test_reutiliza_cadastro_conjunto_configurado_e_remove_duplicacao(self):
        conjunta = {'id': 'a' * 32}
        with self.repo.conectar() as banco:
            banco.execute('INSERT INTO rotinas_cadastradas VALUES (?,?,?,?)',
                          (conjunta['id'], NOME_LIVROS_CONJUNTOS, '[]', 'pendente_configuracao'))
        dados = {"nome": NOME_LIVROS_CONJUNTOS, "passos": [{"tipo": "hover", "valor": "Livros"}]}
        with self.repo.conectar() as banco:
            banco.execute('UPDATE rotinas_cadastradas SET passos=?,status=? WHERE id=?',
                          (json.dumps(dados['passos']), 'rascunho', conjunta['id']))
        self.config.salvar_regime(None, "LUCRO REAL", [conjunta["id"], "registro_saidas", self.icms["id"], "registro_entradas"])
        self.config.preparar_piloto()
        self.assertEqual(self.config.listar()["regimes"][0]["rotinas"], ['livros_fiscais'])
        with self.repo.conectar() as banco:
            arquivo = banco.execute('SELECT * FROM rotinas_cadastradas_arquivo WHERE id=?',
                                    (conjunta['id'],)).fetchone()
        self.assertEqual(json.loads(arquivo['passos']), dados['passos'])
        self.assertEqual(arquivo['status'], 'rascunho')
        self.assertEqual(self.conjunta()["status"], "integrada")

    def test_reinicio_nao_restaura_livros_removidos_nem_duplica_cadastro(self):
        regime = self.config.salvar_regime(None, "Lucro Presumido", ["registro_entradas", "registro_saidas", self.icms["id"]])
        self.config.preparar_piloto()
        self.config.salvar_regime(regime["id"], regime["nome"], ["resumo_acumulador"])
        antes = self.config.listar()
        nova = RepositorioTarefas(self.repo.caminho)
        nova.configuracao.preparar_piloto()
        self.assertEqual(nova.configuracao.listar(), antes)

    def test_v6_substitui_so_nome_exato_lp_lr_e_preserva_outro_regime(self):
        self.config.salvar_regime(None, 'Lucro Presumido', ['livros_fiscais'])
        self.config.preparar_piloto()
        antigo, parecido = 'b' * 32, 'c' * 32
        with self.repo.conectar() as banco:
            banco.execute("DELETE FROM marcos_cadastro WHERE id='piloto_lp_lr_livros_integrados_v6'")
            for identificador, nome in ((antigo, NOME_LIVROS_CONJUNTOS),
                                       (parecido, NOME_LIVROS_CONJUNTOS + ' extra')):
                banco.execute('INSERT INTO rotinas_cadastradas VALUES (?,?,?,?)',
                              (identificador, nome, '[]', 'rascunho'))
        lp = next(r for r in self.config.listar()['regimes'] if r['nome'] == 'Lucro Presumido')
        self.config.salvar_regime(lp['id'], lp['nome'], ['efd_contribuicoes', antigo, parecido, 'livros_fiscais'])
        outro = self.config.salvar_regime(None, 'Outro regime', [antigo])
        self.config.preparar_piloto()
        regimes = {r['id']: r for r in self.config.listar()['regimes']}
        self.assertEqual(regimes[lp['id']]['rotinas'], ['efd_contribuicoes', 'livros_fiscais', parecido])
        self.assertEqual(regimes[outro['id']]['rotinas'], [antigo])
        self.assertEqual(self.config.obter_rotina(antigo)['status'], 'rascunho')
        self.assertEqual(self.config.obter_rotina(parecido)['status'], 'rascunho')
