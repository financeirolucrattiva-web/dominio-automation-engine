"""Cadastro/prévia/teste de pasta no Chromium; sem Domínio ou PDF fiscal."""
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from playwright.sync_api import expect, sync_playwright
import uvicorn
from app.api_servidor import criar_app
from app.servidor import RepositorioTarefas, ServicoExecucao


with tempfile.TemporaryDirectory() as temporaria:
    root = Path(temporaria)
    dados = root / "data"
    dados.mkdir()
    raiz = root / "empresas"
    relativa = "1 LUCRO REAL E LUCRO PRESUMIDO/1.6 EMPRESA FICTICIA"
    (raiz / relativa / "2024/FISCAL").mkdir(parents=True)
    (dados / "destino_livros.json").write_text(json.dumps({"raiz": str(raiz)}))
    repo = RepositorioTarefas(dados / "banco.sqlite3")
    regime = repo.configuracao.salvar_regime(None, "Lucro Presumido", ["registro_entradas"])
    servico = ServicoExecucao(repo)
    chave = "d" * 48
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        porta = sock.getsockname()[1]
    url = f"http://127.0.0.1:{porta}"
    server = uvicorn.Server(uvicorn.Config(criar_app(servico, chave, root / "saida"),
        host="127.0.0.1", port=porta, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run)
    thread.start()
    try:
        for _ in range(100):
            try:
                if httpx.get(url).status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(.05)
        else:
            raise AssertionError("API não iniciou")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=shutil.which("chromium"), headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="pt-BR")
            erros = []
            page.on("pageerror", lambda erro: erros.append(str(erro)))
            page.goto(url)
            page.locator("#chave").fill(chave)
            page.locator("#form-login button").click()
            expect(page.locator("#conteudo")).to_be_visible()
            page.locator("#capacidade").select_option("resumo_acumulador")
            expect(page.locator("#descricao")).to_contain_text("teste supervisionado")
            expect(page.locator("#campo-datas")).to_be_visible()
            expect(page.locator("#competencia")).to_be_disabled()
            page.locator("#config-empresas summary").click()
            page.locator("#empresa-codigo").fill("52")
            page.locator("#empresa-nome").fill("Empresa Fictícia")
            page.locator("#empresa-regime").select_option(regime["id"])
            page.locator("#empresa-pasta").fill(relativa.replace("/", "\\"))
            page.locator("#empresa-subpasta").fill("RELATORIOS_APURAÇÃO\\LIVROS_FISCAIS")
            page.locator("#salvar-empresa").click()
            expect(page.locator("#empresa-codigo")).to_have_value("")
            page.locator("#config-lotes summary").click()
            page.locator("#lote-empresas button").filter(has_text="Editar").click()
            expect(page.locator("#empresa-pasta")).to_have_value(relativa)
            page.locator("#empresa-competencia").fill("2024-02")
            page.locator("#empresa-ver-destino").click()
            expect(page.locator("#empresa-destino")).to_contain_text("nenhuma pasta ou arquivo foi criado")
            destino = raiz / relativa / "2024/FISCAL/02/RELATORIOS_APURAÇÃO/LIVROS_FISCAIS"
            expect(page.locator("#empresa-destino")).to_contain_text(str(destino))
            expect(page.locator("#empresa-destino")).to_contain_text("livro_icms_empresa_ficticia_2024-02.pdf")
            assert not destino.exists()
            page.locator("#empresa-testar-pasta").click()
            expect(page.locator("#empresa-destino")).to_contain_text("Gravação confirmada")
            assert destino.is_dir() and list(destino.iterdir()) == []
            assert repo.listar() == []
            for largura in (1440, 768, 390):
                page.set_viewport_size({"width": largura, "height": 1000})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), largura
            page.locator("#empresa-subpasta").fill("OUTRA_PASTA")
            page.locator("#empresa-ver-destino").click()
            expect(page.locator("#empresa-destino")).to_contain_text("Salve as alterações")
            assert not (destino.parent / "OUTRA_PASTA").exists()
            page.locator("#sair").click()
            expect(page.locator("#empresa-destino")).to_have_text("")
            assert not erros, erros
            browser.close()
        print("OK: cadastro, edição, prévia, gravação, alterações não salvas, três larguras e logout; sem emissão fiscal.")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
