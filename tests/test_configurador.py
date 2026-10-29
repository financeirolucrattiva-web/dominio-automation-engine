"""Configurador visual de rotinas: validação, recorte dos modelos, execução com dispositivos falsos, teste
supervisionado, aprovação e a API completa. Nenhum desktop é tocado."""
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app import configurador
from app.configurador import Configurador, ConfiguradorErro, Dispositivos, validar_parametros_teste, validar_passos

WEB_DISPONIVEL = all(importlib.util.find_spec(nome) for nome in ("fastapi", "httpx"))


def imagem_de_teste():
    imagem = Image.new("RGB", (400, 300), "white")
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle((50, 40, 150, 80), fill="red")      # alvo A
    desenho.rectangle((200, 100, 300, 140), fill="blue")  # alvo B
    return imagem


class Falsos:
    """Dispositivos falsos: guardam as ações e devolvem posições programadas por modelo."""

    def __init__(self, achados=None, foco=True):
        self.acoes, self.achados, self.foco = [], achados or {}, foco
        self.imagem = imagem_de_teste()
        self.mudancas = 0

    def dispositivos(self):
        def achar(img, caminho):
            return self.achados.get(Path(caminho).name)

        def assinatura(img):
            self.mudancas += 1
            return self.mudancas  # cada leitura "muda" a tela

        return Dispositivos(
            capturar=lambda: self.imagem, achar_template=achar,
            clicar=lambda x, y: self.acoes.append(("clicar", x, y)),
            clicar_duplo=lambda x, y: self.acoes.append(("duplo", x, y)),
            passar_mouse=lambda x, y: self.acoes.append(("hover", x, y)),
            tecla=lambda t: self.acoes.append(("tecla", t)),
            digitar=lambda t: self.acoes.append(("digitar", t)),
            assinatura=assinatura, mudou=lambda a, b: a != b,
            janela_ok=lambda: self.foco, dormir=lambda s: self.acoes.append(("dormir", s)))


class Base(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.falsos = Falsos()
        self.c = Configurador(self.pasta / "cfg", self.falsos.dispositivos(), pasta_falhas=self.pasta / "falhas")
        self.captura = self.c.capturar()

    def passo(self, tipo="clicar", **extra):
        base = {"tipo": tipo}
        if tipo in configurador.TIPOS_ALVO:
            base.update(rotulo="Botão vermelho", captura_id=self.captura, x=50, y=40, largura=100, altura=40)
        base.update(extra)
        return base


class TestValidacao(Base):
    def validar(self, *passos):
        return validar_passos(list(passos), self.c._tamanho_captura)

    def test_passo_valido_de_cada_tipo(self):
        limpos = self.validar(self.passo("clicar"), self.passo("duplo_clique"), self.passo("hover"),
                              self.passo("esperar_imagem", segundos=5), {"tipo": "tecla", "tecla": "enter"},
                              {"tipo": "digitar", "parametro": "inicio"}, {"tipo": "digitar", "texto": "Contribui"},
                              {"tipo": "esperar_segundos", "segundos": 3})
        self.assertEqual([p["indice"] for p in limpos], list(range(1, 9)))

    def test_recusa_acoes_perigosas_e_entradas_ruins(self):
        ruins = [
            self.passo("clicar", rotulo="Transmitir declaração"),
            self.passo("clicar", rotulo="Excluir lançamento"),
            self.passo("hover", rotulo="Retificar arquivo"),
            self.passo("clicar", rotulo="ab"),
            self.passo("clicar", x=350),                       # sai da imagem
            self.passo("clicar", largura=4),                   # pequeno demais
            self.passo("clicar", captura_id="0" * 32),         # captura inexistente
            self.passo("clicar", x="50"),
            {"tipo": "tecla", "tecla": "delete"},
            {"tipo": "tecla", "tecla": "alt+f4"},
            {"tipo": "digitar", "parametro": "senha"},
            {"tipo": "digitar", "texto": "rm -rf *;"},
            {"tipo": "digitar", "texto": "a", "parametro": "inicio"},
            {"tipo": "esperar_segundos", "segundos": 99},
            {"tipo": "comando", "valor": "x"},
        ]
        for passo in ruins:
            with self.subTest(passo=passo), self.assertRaises(ConfiguradorErro):
                self.validar(passo)
        with self.assertRaises(ConfiguradorErro):
            self.validar()

    def test_parametros_do_teste_exigem_periodo_passado(self):
        passos = self.validar({"tipo": "digitar", "parametro": "inicio"}, {"tipo": "digitar", "parametro": "empresa_codigo"})
        hoje = __import__("datetime").date(2026, 10, 28)
        self.assertEqual(validar_parametros_teste(passos, {"inicio": "2026-09-01", "empresa_codigo": "70"}, hoje),
                         {"inicio": "01/09/2026", "empresa_codigo": "70"})
        for ruim in ({"inicio": "2026-10-01", "empresa_codigo": "70"},   # mês corrente
                     {"inicio": "2026-09-01"},                          # faltou empresa
                     {"inicio": "2026-09-01", "empresa_codigo": "7a"},
                     {"inicio": "2026-09-01", "empresa_codigo": "70", "fim": "2026-09-30"},  # parâmetro que não usa
                     {"inicio": "01/09/2026", "empresa_codigo": "70"}):
            with self.subTest(ruim=ruim), self.assertRaises(ConfiguradorErro):
                validar_parametros_teste(passos, ruim, hoje)


class TestRotinas(Base):
    def test_salvar_recorta_o_modelo_da_captura_guardada(self):
        salva = self.c.salvar("Abrir relatório", [self.passo("clicar")])
        modelo = self.c.modelo(salva["id"], 1)
        with Image.open(__import__("io").BytesIO(modelo)) as recorte:
            self.assertEqual(recorte.size, (100, 40))
            self.assertEqual(recorte.getpixel((50, 20)), (255, 0, 0))  # o vermelho do alvo A
        self.assertEqual(salva["status"], "rascunho")
        self.assertTrue(salva["passos"][0]["tem_modelo"])

    def test_nome_repetido_e_edicao(self):
        a = self.c.salvar("Rotina A", [self.passo("clicar")])
        with self.assertRaises(ConfiguradorErro):
            self.c.salvar("rotina a", [self.passo("clicar")])
        editada = self.c.salvar("Rotina A", [self.passo("clicar"), {"tipo": "tecla", "tecla": "enter"}], a["id"])
        self.assertEqual(editada["quantidade_passos"], 2)
        self.assertEqual(len(self.c.listar()), 1)

    def test_excluir(self):
        a = self.c.salvar("Rotina A", [self.passo("clicar")])
        self.c.excluir(a["id"])
        self.assertEqual(self.c.listar(), [])
        with self.assertRaises(ConfiguradorErro):
            self.c.obter(a["id"])
        with self.assertRaises(ConfiguradorErro):
            self.c.obter("../../etc")

    def test_captura_fora_do_dominio_e_recusada(self):
        self.falsos.foco = False
        with self.assertRaisesRegex(ConfiguradorErro, "dominio_fora_de_foco"):
            self.c.capturar()


class TestExecucao(Base):
    def rotina(self):
        return self.c.salvar("Gerar relatório", [
            self.passo("clicar", rotulo="Botão vermelho"),
            {"tipo": "digitar", "parametro": "inicio"},
            self.passo("duplo_clique", rotulo="Item azul", x=200, y=100, largura=100, altura=40),
            {"tipo": "tecla", "tecla": "enter"},
            self.passo("esperar_imagem", rotulo="Aviso azul", x=200, y=100, largura=100, altura=40, segundos=2),
        ])

    def test_executa_todos_os_passos_na_ordem(self):
        self.falsos.achados = {"passo_01.png": (100, 60), "passo_03.png": (250, 120), "passo_05.png": (250, 120)}
        salva = self.rotina()
        resultado = self.c.testar(salva["id"], {"inicio": "2026-09-01"}, hoje=__import__("datetime").date(2026, 10, 28))
        self.assertTrue(resultado["ok"], resultado)
        acoes = [a for a in self.falsos.acoes if a[0] != "dormir"]
        self.assertEqual(acoes, [("clicar", 100, 60), ("digitar", "01/09/2026"), ("duplo", 250, 120), ("tecla", "enter")])
        self.assertEqual(self.c.obter(salva["id"])["status"], "testada")

    def test_para_no_primeiro_alvo_que_nao_aparece_e_guarda_a_tela(self):
        self.falsos.achados = {"passo_01.png": (100, 60)}   # o passo 3 nunca é achado
        salva = self.rotina()
        resultado = self.c.testar(salva["id"], {"inicio": "2026-09-01"}, hoje=__import__("datetime").date(2026, 10, 28))
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["passo_falho"], 3)
        self.assertEqual([a for a in self.falsos.acoes if a[0] in ("duplo", "tecla")], [])  # nada depois da falha
        self.assertEqual(len(list((self.pasta / "falhas").glob("configurador_*_passo_03.png"))), 1)
        self.assertEqual(self.c.obter(salva["id"])["status"], "rascunho")

    def test_espera_o_alvo_aparecer_e_a_tela_assentar_antes_de_seguir(self):
        achados = [None, None, None, (100, 60)]  # só aparece na 4ª leitura
        self.falsos.achados = {}
        d = self.falsos.dispositivos()
        d.achar_template = lambda img, caminho: achados.pop(0) if achados else (100, 60)
        c = Configurador(self.pasta / "cfg2", d, pasta_falhas=self.pasta / "falhas2")
        captura = c.capturar()
        salva = c.salvar("Espera", [dict(self.passo("clicar"), captura_id=captura, espera=5)])
        self.assertTrue(c.testar(salva["id"])["ok"])
        dormidas = [a for a in self.falsos.acoes if a[0] == "dormir"]
        self.assertGreaterEqual(len([s for s in dormidas if s[1] == 1]), 3)      # esperou o alvo (3 tentativas)
        self.assertIn(("clicar", 100, 60), self.falsos.acoes)

    def test_clica_assim_que_o_alvo_aparece_sem_esperar_o_tempo_todo(self):
        self.falsos.achados = {"passo_01.png": (100, 60)}
        salva = self.c.salvar("Rápido", [dict(self.passo("clicar"), espera=60)])
        self.assertTrue(self.c.testar(salva["id"])["ok"])
        self.assertEqual([a for a in self.falsos.acoes if a == ("dormir", 1)], [])   # nenhuma espera de 1 s: achou na hora
        self.assertIn(("clicar", 100, 60), self.falsos.acoes)

    def test_so_clica_quando_o_alvo_se_repete_no_mesmo_lugar(self):
        # quadro "meio desenhado": aparece uma vez, some, depois fica firme (a leitura seguinte confirma)
        leituras = iter([(100, 60), None, (100, 60), (101, 61)])
        d = self.falsos.dispositivos()
        d.achar_template = lambda img, caminho: next(leituras, (101, 61))
        c = Configurador(self.pasta / "cfg4", d, pasta_falhas=self.pasta / "falhas4")
        captura = c.capturar()
        salva = c.salvar("Firme", [dict(self.passo("clicar"), captura_id=captura, espera=5)])
        self.assertTrue(c.testar(salva["id"])["ok"])
        self.assertEqual([a for a in self.falsos.acoes if a[0] == "clicar"], [("clicar", 101, 61)])

    def test_desiste_do_alvo_so_depois_do_tempo_configurado(self):
        self.falsos.achados = {}
        salva = self.c.salvar("Nunca", [dict(self.passo("clicar"), espera=3)])
        resultado = self.c.testar(salva["id"])
        self.assertFalse(resultado["ok"])
        self.assertIn("em 3 s", resultado["mensagem"])
        self.assertEqual(len([a for a in self.falsos.acoes if a == ("dormir", 1)]), 3)

    def test_espera_invalida_e_recusada(self):
        for ruim in (0, 121, "5"):
            with self.subTest(espera=ruim), self.assertRaises(ConfiguradorErro):
                validar_passos([self.passo("clicar", espera=ruim)], self.c._tamanho_captura)

    def test_foco_perdido_no_meio_nao_envia_nada(self):
        self.falsos.achados = {"passo_01.png": (100, 60)}
        salva = self.c.salvar("Só clique", [self.passo("clicar")])
        self.falsos.foco = False
        resultado = self.c.testar(salva["id"])
        self.assertFalse(resultado["ok"])
        self.assertEqual([a for a in self.falsos.acoes if a[0] == "clicar"], [])

    def test_aprovacao_exige_teste_ok_da_versao_atual(self):
        self.falsos.achados = {"passo_01.png": (100, 60)}
        salva = self.c.salvar("Só clique", [self.passo("clicar")])
        with self.assertRaises(ConfiguradorErro):
            self.c.aprovar(salva["id"])                       # sem teste
        self.assertTrue(self.c.testar(salva["id"])["ok"])
        self.assertEqual(self.c.aprovar(salva["id"])["status"], "aprovada")
        # editar derruba a aprovação: volta a rascunho e exige novo teste
        editada = self.c.salvar("Só clique", [self.passo("clicar"), {"tipo": "tecla", "tecla": "tab"}], salva["id"])
        self.assertEqual(editada["status"], "rascunho")
        with self.assertRaises(ConfiguradorErro):
            self.c.aprovar(salva["id"])


class TestTrocarEmpresaEVoltar(Base):
    """Trocar de empresa e voltar à tela principal: funções dos lotes reais, empresa sempre pelo parâmetro."""

    def montar(self, troca=True, volta=True):
        chamadas = []
        d = self.falsos.dispositivos()
        d.trocar_empresa = lambda codigo: chamadas.append(("trocar", codigo)) or troca
        d.voltar_inicio = lambda: chamadas.append(("voltar",)) or volta
        self.n = getattr(self, "n", 0) + 1
        return Configurador(self.pasta / f"cfg3_{self.n}", d, pasta_falhas=self.pasta / "falhas3"), chamadas

    PASSOS = [{"tipo": "trocar_empresa"}, {"tipo": "tecla", "tecla": "tab"}, {"tipo": "voltar_tela_principal"}]

    def test_parametro_empresa_e_exigido_e_listado(self):
        c, _ = self.montar()
        salva = c.salvar("Trocar e voltar", self.PASSOS)
        self.assertEqual(salva["parametros"], ["empresa_codigo"])
        with self.assertRaises(ConfiguradorErro):
            c.testar(salva["id"], {})                                  # faltou a empresa
        with self.assertRaises(ConfiguradorErro):
            c.testar(salva["id"], {"empresa_codigo": "7a"})

    def test_executa_na_ordem_com_a_empresa_do_parametro(self):
        c, chamadas = self.montar()
        salva = c.salvar("Trocar e voltar", self.PASSOS)
        resultado = c.testar(salva["id"], {"empresa_codigo": "68"})
        self.assertTrue(resultado["ok"], resultado)
        self.assertEqual(chamadas, [("trocar", "68"), ("voltar",)])
        self.assertIn(("tecla", "tab"), self.falsos.acoes)

    def test_pula_a_troca_se_ja_esta_na_empresa_certa(self):
        c, chamadas = self.montar()
        c._dispositivos.empresa_atual = lambda: "68"
        salva = c.salvar("Só trocar", [{"tipo": "trocar_empresa"}])
        resultado = c.testar(salva["id"], {"empresa_codigo": "68"})
        self.assertTrue(resultado["ok"])
        self.assertEqual(chamadas, [])                                   # nenhum F8
        self.assertIn("troca pulada", resultado["passos"][0]["detalhe"])
        # código com zeros à esquerda também conta como a mesma empresa
        resultado = c.testar(salva["id"], {"empresa_codigo": "068"})
        self.assertEqual(chamadas, [])

    def test_troca_quando_a_empresa_atual_e_outra_ou_ilegivel_e_confere_depois(self):
        for lida in ("12", None):
            with self.subTest(lida=lida):
                c, chamadas = self.montar()
                leituras = iter([lida, "68"])                       # antes da troca e depois dela
                c._dispositivos.empresa_atual = lambda: next(leituras)
                salva = c.salvar(f"Só trocar {lida}", [{"tipo": "trocar_empresa"}])
                self.assertTrue(c.testar(salva["id"], {"empresa_codigo": "68"})["ok"])
                self.assertEqual(chamadas, [("trocar", "68")])
        # depois da troca o cabeçalho mostra outra empresa: a rotina para
        c, chamadas = self.montar()
        leituras = iter(["12", "12"])
        c._dispositivos.empresa_atual = lambda: next(leituras)
        salva = c.salvar("Só trocar", [{"tipo": "trocar_empresa"}])
        resultado = c.testar(salva["id"], {"empresa_codigo": "68"})
        self.assertFalse(resultado["ok"])
        self.assertIn("mostra a empresa 12", resultado["mensagem"])

    def test_falha_de_troca_ou_de_volta_para_a_rotina(self):
        c, chamadas = self.montar(troca=False)
        salva = c.salvar("Trocar e voltar", self.PASSOS)
        resultado = c.testar(salva["id"], {"empresa_codigo": "68"})
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["passo_falho"], 1)
        self.assertEqual(chamadas, [("trocar", "68")])                  # nada depois da falha
        c2, _ = self.montar(volta=False)
        salva2 = c2.salvar("Só voltar", [{"tipo": "voltar_tela_principal"}])
        falha = c2.testar(salva2["id"])
        self.assertFalse(falha["ok"])
        self.assertIn("tela principal", falha["mensagem"])

    def test_sem_as_funcoes_reais_falha_com_mensagem(self):
        salva = self.c.salvar("Sem dispositivo", [{"tipo": "voltar_tela_principal"}])   # Falsos não definem voltar_inicio
        resultado = self.c.testar(salva["id"])
        self.assertFalse(resultado["ok"])
        self.assertIn("indisponível", resultado["mensagem"])


class TestSeAparecer(Base):
    """Condicional só para o variável: reconhece a tela pelo recorte e responde com clique ou tecla."""

    def condicional(self, **extra):
        base = {"tipo": "se_aparecer", "rotulo": "Aviso outros dados", "captura_id": self.captura,
                "x": 200, "y": 100, "largura": 100, "altura": 40,          # a tela esperada (o quadrado azul)
                "resposta": {"tipo": "clicar", "x": 50, "y": 40, "largura": 100, "altura": 40, "rotulo": "botão Sim"}}
        base.update(extra)
        return base

    def test_validacao(self):
        ok = validar_passos([self.condicional()], self.c._tamanho_captura)[0]
        self.assertEqual(ok["deslocamento"], [-150, -60])           # centro do botão menos centro da tela
        self.assertFalse(ok["obrigatorio"])
        self.assertEqual(ok["espera"], 10)
        validar_passos([self.condicional(resposta={"tipo": "tecla", "tecla": "enter"})], self.c._tamanho_captura)
        ruins = [
            self.condicional(resposta=None),
            self.condicional(resposta={"tipo": "tecla", "tecla": "delete"}),
            self.condicional(resposta={"tipo": "clicar", "x": 50, "y": 40, "largura": 100, "altura": 40, "rotulo": "Transmitir"}),
            self.condicional(resposta={"tipo": "clicar", "x": 50, "y": 40, "largura": 100, "altura": 40}),  # sem rótulo
            self.condicional(rotulo="Excluir dados"),
            self.condicional(largura=5),
            self.condicional(espera=0),
            self.condicional(obrigatorio="sim"),
        ]
        for ruim in ruins:
            with self.subTest(ruim=ruim), self.assertRaises(ConfiguradorErro):
                validar_passos([ruim], self.c._tamanho_captura)

    def test_salva_o_recorte_da_tela_e_o_do_botao(self):
        salva = self.c.salvar("Com aviso", [self.condicional()])
        self.assertIsNotNone(self.c.modelo(salva["id"], 1))
        self.assertIsNotNone(self.c.modelo(salva["id"], 1, "modelo_alvo"))
        self.assertTrue(salva["passos"][0]["tem_modelo_alvo"])

    def test_se_aparecer_clica_no_botao_relativo_a_tela_onde_ela_surgiu(self):
        # a tela esperada (centro 250,120 na captura) surgiu deslocada: casou em (600, 400)
        self.falsos.achados = {"passo_01.png": (600, 400)}
        salva = self.c.salvar("Com aviso", [self.condicional()])
        self.assertTrue(self.c.testar(salva["id"])["ok"])
        self.assertIn(("clicar", 600 - 150, 400 - 60), self.falsos.acoes)

    def test_opcional_segue_se_nao_aparecer_e_obrigatorio_falha(self):
        self.falsos.achados = {}
        opcional = self.c.salvar("Opcional", [self.condicional(espera=2), {"tipo": "tecla", "tecla": "enter"}])
        resultado = self.c.testar(opcional["id"])
        self.assertTrue(resultado["ok"])
        self.assertIn("não apareceu; seguindo", resultado["passos"][0]["detalhe"])
        self.assertIn(("tecla", "enter"), self.falsos.acoes)          # o fluxo seguiu
        self.assertNotIn("clicar", [a[0] for a in self.falsos.acoes])
        obrigatorio = self.c.salvar("Obrigatório", [self.condicional(espera=2, obrigatorio=True)])
        falha = self.c.testar(obrigatorio["id"])
        self.assertFalse(falha["ok"])
        self.assertIn("não apareceu em 2 s", falha["mensagem"])

    def test_resposta_por_tecla(self):
        self.falsos.achados = {"passo_01.png": (250, 120)}
        salva = self.c.salvar("Tecla", [self.condicional(resposta={"tipo": "tecla", "tecla": "esc"})])
        self.assertTrue(self.c.testar(salva["id"])["ok"])
        self.assertIn(("tecla", "esc"), self.falsos.acoes)


@unittest.skipUnless(WEB_DISPONIVEL, "Componentes opcionais: requirements-dev-servidor.txt")
class TestApi(Base):
    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from app.api_servidor import criar_app
        from app.servidor import RepositorioTarefas, ServicoExecucao
        self.falsos.achados = {"passo_01.png": (100, 60)}
        self.servico = ServicoExecucao(RepositorioTarefas(self.pasta / "banco.sqlite3"), lambda d, r: True,
                                       modo="simulacao", configurador=self.c)
        self.chave = "k" * 48
        self.client = TestClient(criar_app(self.servico, self.chave, self.pasta / "saida", pasta_rotinas=self.pasta / "rot"))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.h = {"Authorization": f"Bearer {self.chave}"}

    def esperar_estado(self, *estados, limite=10):
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            login = self.client.get("/api/estado", headers=self.h).json()["login"]
            if login["estado"] in estados:
                return login
            time.sleep(0.05)
        self.fail(f"estado esperado {estados}; atual {login}")

    def test_exige_autenticacao(self):
        for rota in ("rotinas", "captura"):
            self.assertEqual(self.client.get("/api/configurador/" + rota).status_code, 401)
        for rota in ("captura", "rotinas"):
            self.assertEqual(self.client.post("/api/configurador/" + rota, json={}).status_code, 401)

    def test_fluxo_completo_capturar_salvar_testar_aprovar(self):
        r = self.client.post("/api/configurador/captura", headers=self.h)
        self.assertEqual(r.status_code, 202)
        self.esperar_estado("captura_configurador_pronta")
        imagem = self.client.get("/api/configurador/captura", headers=self.h)
        self.assertEqual(imagem.status_code, 200)
        captura_id = imagem.headers["X-Captura-Id"]
        passos = [{"tipo": "clicar", "rotulo": "Botão vermelho", "captura_id": captura_id,
                   "x": 50, "y": 40, "largura": 100, "altura": 40}]
        # o navegador nunca manda imagem: campo extra de imagem não vira modelo
        criada = self.client.post("/api/configurador/rotinas", headers=self.h, json={"nome": "Minha rotina", "passos": passos})
        self.assertEqual(criada.status_code, 201, criada.text)
        rid = criada.json()["id"]
        self.assertEqual(self.client.get(f"/api/configurador/rotinas/{rid}/modelo/1", headers=self.h).status_code, 200)
        self.assertEqual(self.client.post(f"/api/configurador/rotinas/{rid}/aprovar", headers=self.h).status_code, 422)
        self.assertEqual(self.client.post(f"/api/configurador/rotinas/{rid}/testar", headers=self.h,
                                          json={"parametros": {"inicio": "2026-09-01"}}).status_code, 422)  # não usa
        self.assertEqual(self.client.post(f"/api/configurador/rotinas/{rid}/testar", headers=self.h,
                                          json={"parametros": {}}).status_code, 202)
        self.esperar_estado("teste_configurador_ok")
        detalhe = self.client.get(f"/api/configurador/rotinas/{rid}", headers=self.h).json()
        self.assertEqual(detalhe["status"], "testada")
        self.assertTrue(detalhe["resultado_teste"]["ok"])
        aprovada = self.client.post(f"/api/configurador/rotinas/{rid}/aprovar", headers=self.h)
        self.assertEqual(aprovada.json()["status"], "aprovada")
        self.assertEqual(len(self.client.get("/api/configurador/rotinas", headers=self.h).json()), 1)
        self.assertEqual(self.client.delete(f"/api/configurador/rotinas/{rid}", headers=self.h).status_code, 200)

    def test_regras_de_seguranca_valem_na_api(self):
        captura_id = self.c.capturar()
        ruim = [{"tipo": "clicar", "rotulo": "Transmitir", "captura_id": captura_id, "x": 50, "y": 40, "largura": 100, "altura": 40}]
        r = self.client.post("/api/configurador/rotinas", headers=self.h, json={"nome": "Perigosa", "passos": ruim})
        self.assertEqual(r.status_code, 422)
        self.assertIn("transmitir", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()
