"""Login descrito pelo operador: DOM web, depois OCR no cliente GO-Global.

Credenciais não são gravadas. Só fecha o navegador próprio e janelas
Domínio/Lista de Programas identificadas; nunca mata processos do Windows.
As novas telas ainda precisam de validação na sessão real do operador.
"""

import ctypes
from ctypes import wintypes
from pathlib import Path
import os
import sys
import time
import threading
from urllib.parse import urlparse

from app.autenticacao import LoginRecusado

ROOT = Path(__file__).resolve().parents[1]
DESTINOS = {"onvio.com.br", "auth.thomsonreuters.com", "www.dominioweb.com.br", "dominioweb.com.br"}


def conferir_destino(url):
    destino = urlparse(url)
    if (destino.scheme != "https" or destino.hostname not in DESTINOS or destino.port not in (None, 443)
            or destino.username or destino.password):
        raise LoginRecusado("destino_nao_permitido")


def localizar_campos(imagem, rotulos):
    """Mede retângulos dos campos ao lado dos rótulos OCR; sem offsets.

    Exige três campos alinhados e distintos. Ambiguidade recusa digitação.
    Não lê a senha nem envia imagem a um modelo remoto.
    """
    import cv2
    import numpy as np
    cinza = cv2.cvtColor(np.asarray(imagem.convert("RGB")), cv2.COLOR_RGB2GRAY)
    bordas = cv2.Canny(cinza, 50, 150)
    contornos, _ = cv2.findContours(bordas, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    caixas = []
    for contorno in contornos:
        x, y, largura, altura = cv2.boundingRect(contorno)
        aproximado = cv2.approxPolyDP(contorno, 0.02 * cv2.arcLength(contorno, True), True)
        if (len(aproximado) == 4 and largura >= 3 * altura and altura >= 10
                and largura < imagem.width and altura < imagem.height / 4):
            caixa = (x, y, largura, altura)
            def mesma_borda(anterior):
                ax, ay, aw, ah = anterior
                intersecao = max(0, min(x + largura, ax + aw) - max(x, ax)) * max(0, min(y + altura, ay + ah) - max(y, ay))
                uniao = largura * altura + aw * ah - intersecao
                return intersecao / uniao >= 0.75
            if not any(mesma_borda(anterior) for anterior in caixas):
                caixas.append(caixa)
    escolhidas = []
    for rotulo in rotulos:
        if rotulo is None:
            raise LoginRecusado("campos_login_nao_confirmados")
        rx, ry = rotulo
        candidatas = [c for c in caixas if c[0] > rx and c[1] <= ry <= c[1] + c[3]]
        if len(candidatas) != 1:
            raise LoginRecusado("campos_login_nao_confirmados")
        escolhidas.append(candidatas[0])
    if (len(set(escolhidas)) != 3 or not escolhidas[0][1] < escolhidas[1][1] < escolhidas[2][1]
            or max(c[0] for c in escolhidas) - min(c[0] for c in escolhidas) > 3):
        raise LoginRecusado("campos_login_nao_confirmados")
    return [(x + w // 2, y + h // 2) for x, y, w, h in escolhidas]


def texto_unico(imagem, alvo):
    """Texto exato, na mesma linha e com uma única ocorrência."""
    import unicodedata
    from app import tela
    def normalizar(texto):
        return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold())
                       if not unicodedata.combining(c)).strip(" :.*")
    dados = tela._ler_dados_ocr(imagem, 2)
    alvo = [normalizar(t) for t in alvo.split()]
    indices = [i for i, texto in enumerate(dados["text"]) if normalizar(texto)]
    encontrados = []
    for inicio in range(len(indices) - len(alvo) + 1):
        grupo = indices[inicio:inicio + len(alvo)]
        if [normalizar(dados["text"][i]) for i in grupo] != alvo:
            continue
        if any(len({dados[k][i] for i in grupo}) != 1 for k in ("block_num", "par_num", "line_num")):
            continue
        x = (min(dados["left"][i] for i in grupo) + max(dados["left"][i] + dados["width"][i] for i in grupo)) // 4
        y = (min(dados["top"][i] for i in grupo) + max(dados["top"][i] + dados["height"][i] for i in grupo)) // 4
        encontrados.append((x, y))
    return encontrados[0] if len(encontrados) == 1 else None


class LoginWindows:
    def __init__(self):
        self._playwright = self._contexto = self._pagina = None
        self._janelas = {}
        self._antes = set()
        self._captura_lock = threading.Lock()
        self._captura = None

    def _navegador(self):
        from playwright.sync_api import sync_playwright
        if self._contexto is not None:
            try:
                self._contexto.clear_cookies()
                self._pagina = self._contexto.new_page()
                for pagina in self._contexto.pages:
                    if pagina != self._pagina:
                        pagina.close()
                self._pagina.set_default_timeout(10000)
                return
            except Exception:
                self.encerrar()
        executavel = None
        for base in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            for relativo in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
                candidato = Path(os.environ.get(base, "")) / relativo
                if candidato.is_file():
                    executavel = candidato
                    break
            if executavel:
                break
        if executavel is None:
            raise LoginRecusado("navegador_indisponivel")
        self._playwright = sync_playwright().start()
        self._contexto = self._playwright.chromium.launch_persistent_context(
            ROOT / "data" / "navegador_dominio", executable_path=str(executavel), headless=False,
            no_viewport=True, args=["--start-maximized", "--disable-save-password-bubble"],
            accept_downloads=False)
        self._pagina = self._contexto.new_page()
        self._contexto.clear_cookies()
        self._pagina.set_default_timeout(10000)

    def _janelas_visiveis(self):
        from app import interacao
        api, callback = interacao._api_janelas()
        janelas = []
        def incluir(hwnd, _):
            dados = interacao._dados_janela(api, hwnd)
            if dados and (interacao._titulo_dominio(dados["titulo"])
                          or dados["titulo"].strip().casefold() in ("lista de programas", "conectando ...", "conectando...")
                          or dados["classe"] == "DisplayClientWindowClass"):
                janelas.append(dados)
            return True
        if not api.EnumWindows(callback(incluir), 0):
            raise LoginRecusado("janela_login_nao_confirmada")
        return janelas

    def _atualizar_janelas(self):
        janelas = self._janelas_visiveis()
        for janela in janelas:
            if (janela["hwnd"], janela["pid"]) not in self._antes:
                self._janelas[janela["hwnd"]] = janela
        return janelas

    def _focar(self, janela):
        from app import interacao
        api, _ = interacao._api_janelas()
        atual = interacao._dados_janela(api, janela["hwnd"])
        if atual is None or any(atual[k] != janela[k] for k in ("pid", "classe")):
            raise LoginRecusado("janela_login_nao_confirmada")
        if api.IsIconic(janela["hwnd"]):
            api.ShowWindow(janela["hwnd"], 9)
        api.SetForegroundWindow(janela["hwnd"])
        for _ in range(10):
            if api.GetForegroundWindow() == janela["hwnd"]:
                return
            time.sleep(0.05)
        raise LoginRecusado("janela_login_nao_confirmada")

    def _capturar(self, janela):
        from app import tela, interacao
        api, _ = interacao._api_janelas()
        self._focar(janela)
        rect = wintypes.RECT()
        api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        api.GetWindowRect.restype = wintypes.BOOL
        if not api.GetWindowRect(janela["hwnd"], ctypes.byref(rect)):
            raise LoginRecusado("janela_login_nao_confirmada")
        imagem = tela.capturar_tela()
        esquerda, topo = max(0, rect.left), max(0, rect.top)
        direita, base = min(imagem.width, rect.right), min(imagem.height, rect.bottom)
        if not (esquerda < direita and topo < base) or api.GetForegroundWindow() != janela["hwnd"]:
            raise LoginRecusado("janela_login_nao_confirmada")
        # Bordas de uma janela maximizada podem ficar fora da captura.
        return imagem.crop((esquerda, topo, direita, base)), (esquerda, topo)

    def _esperar(self, sessao, detectar, timeout=60):
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            sessao.verificar()
            resultado = detectar()
            if resultado is not None:
                return resultado
            time.sleep(0.2)
        raise LoginRecusado("tela_login_nao_reconhecida")

    def _visivel(self, seletor):
        elementos = self._pagina.locator(seletor)
        visiveis = [e for e in elementos.all() if e.is_visible()]
        return visiveis[0] if len(visiveis) == 1 else None

    def _botao(self, nome):
        import re
        elementos = self._pagina.get_by_role("button", name=re.compile(r"^" + re.escape(nome) + r"$", re.I)).all()
        elementos += self._pagina.get_by_role("link", name=re.compile(r"^" + re.escape(nome) + r"$", re.I)).all()
        visiveis = [e for e in elementos if e.is_visible()]
        if not visiveis:
            visiveis = [e for e in self._pagina.get_by_text(nome, exact=True).all() if e.is_visible()]
        return visiveis[0] if len(visiveis) == 1 else None

    def _clicar_web(self, sessao, nome):
        elemento = self._esperar(sessao, lambda: self._botao(nome))
        conferir_destino(self._pagina.url)
        elemento.click()

    def executar(self, credenciais, sessao):
        if sys.platform != "win32":
            raise LoginRecusado("janela_login_nao_confirmada")
        sessao.fase("preparando_navegador")
        self._antes = {(j["hwnd"], j["pid"]) for j in self._janelas_visiveis()}
        self._navegador()
        sessao.fase("abrir_onvio")
        self._pagina.goto("https://onvio.com.br/login/#/", wait_until="domcontentloaded")
        conferir_destino(self._pagina.url)
        self._pagina.evaluate("() => {localStorage.clear(); sessionStorage.clear();}")
        self._pagina.reload(wait_until="domcontentloaded")
        self._clicar_web(sessao, "Entrar")
        sessao.fase("credenciais_onvio")
        email = self._esperar(sessao, lambda: self._visivel('input[name="username"]:not([type="hidden"]), input[type="email"]'))
        conferir_destino(self._pagina.url)
        email.fill(credenciais.email)
        self._clicar_web(sessao, "Entrar")
        senha = self._esperar(sessao, lambda: self._visivel('input[type="password"]'))
        conferir_destino(self._pagina.url)
        senha.fill(credenciais.senha_onvio)
        self._clicar_web(sessao, "Entrar")
        sessao.fase("selecionar_email")
        # Método e nome do campo vêm das capturas reais fornecidas.
        self._clicar_web(sessao, "E-mail")
        def campo_codigo():
            encontrado = self._visivel('input[autocomplete="one-time-code"], input[name="code"], input[name="otp"]')
            if encontrado is not None:
                return encontrado
            import re
            rotulados = [e for e in self._pagina.get_by_label(re.compile("Inserir o código", re.I)).all() if e.is_visible()]
            return rotulados[0] if len(rotulados) == 1 else None
        codigo = self._esperar(sessao, campo_codigo)
        valor = sessao.aguardar_codigo()
        sessao.verificar()
        conferir_destino(self._pagina.url)
        codigo.fill(valor)
        valor = None
        self._clicar_web(sessao, "Continuar")
        # Não abre Domínio Web enquanto o formulário MFA continua visível.
        self._esperar(sessao, lambda: True if not codigo.is_visible() and urlparse(self._pagina.url).hostname == "onvio.com.br" else None)
        sessao.fase("abrir_dominioweb")
        self._pagina.goto("https://www.dominioweb.com.br", wait_until="domcontentloaded")
        self._clicar_web(sessao, "Entrar")
        sessao.fase("abrir_escrita_fiscal")
        self._abrir_fiscal(sessao)
        sessao.fase("credenciais_dominio")
        self._login_fiscal(credenciais, sessao)
        sessao.fase("conferir_tela_principal")
        self._confirmar_principal(sessao)
        sessao.fase("tela_principal_confirmada")

    def _abrir_fiscal(self, sessao):
        from app import tela, interacao
        def detectar():
            candidatas = [j for j in self._atualizar_janelas()
                          if j["hwnd"] in self._janelas and j["titulo"].strip().casefold() == "lista de programas"]
            if len(candidatas) != 1:
                return None
            janela = candidatas[0]
            imagem, origem = self._capturar(janela)
            pos = texto_unico(imagem, "Escrita Fiscal")
            return (janela, pos, origem) if pos else None
        janela, pos, origem = self._esperar(sessao, detectar, timeout=120)
        sessao.verificar()
        self._focar(janela)
        interacao.clicar(pos[0] + origem[0], pos[1] + origem[1])

    def _login_fiscal(self, credenciais, sessao):
        from app import tela, interacao
        def detectar():
            for janela in self._atualizar_janelas():
                if janela["hwnd"] not in self._janelas:
                    continue
                imagem, origem = self._capturar(janela)
                with tela.reutilizar_ocr():
                    rotulos = [texto_unico(imagem, alvo) for alvo in ("Nome do Usuário", "Senha", "Conectar em")]
                    ok = texto_unico(imagem, "OK")
                if all(rotulos) and ok:
                    campos = localizar_campos(imagem, rotulos)
                    if ok[1] <= campos[-1][1]:
                        raise LoginRecusado("campos_login_nao_confirmados")
                    return janela, campos, ok, origem
            return None
        janela, campos, ok, origem = self._esperar(sessao, detectar)
        # pyautogui.write não suporta Unicode. Recusa antes de tocar nos campos.
        if not credenciais.usuario_dominio.isascii() or not credenciais.senha_dominio.isascii():
            raise LoginRecusado("campos_login_nao_confirmados")
        for pos, valor in zip(campos[:2], (credenciais.usuario_dominio, credenciais.senha_dominio)):
            sessao.verificar()
            self._focar(janela)
            interacao.clicar(pos[0] + origem[0], pos[1] + origem[1])
            interacao.selecionar_tudo()
            interacao.digitar(valor)
        # Preserva Conectar em observado, conforme a sequência do operador.
        sessao.verificar()
        self._focar(janela)
        interacao.clicar(ok[0] + origem[0], ok[1] + origem[1])

    def _confirmar_principal(self, sessao):
        from app import dominio, interacao, tela_principal
        from types import SimpleNamespace
        if tela_principal.carregar_referencia() is None:
            raise LoginRecusado("calibracao_nao_confirmada")
        def detectar():
            for janela in self._atualizar_janelas():
                if janela["hwnd"] not in self._janelas or not interacao._titulo_dominio(janela["titulo"]):
                    continue
                self._focar(janela)
                if dominio._verificar_retorno_tela_principal(SimpleNamespace(janela_dominio=janela)) == "tela_principal_reconhecida":
                    return True
            return None
        self._esperar(sessao, detectar, timeout=120)

    def calibrar(self, sessao):
        from app import tela, interacao
        from scripts.calibrar_tela_principal import calibrar
        sessao.fase("calibrando_tela")
        candidatas = [j for j in self._janelas_visiveis() if interacao._titulo_dominio(j["titulo"])]
        if len(candidatas) != 1:
            raise LoginRecusado("calibracao_nao_confirmada")
        self._focar(candidatas[0])
        api, _ = interacao._api_janelas()
        api.ShowWindow(candidatas[0]["hwnd"], 3)  # maximiza somente Domínio identificado
        def cabecalho(imagem):
            with tela.reutilizar_ocr():
                topo = tela.recortar_topo(imagem)
                return all(tela.achar_texto(topo, alvo, escala=2) for alvo in ("Domínio", "Escrita Fiscal", "Relatórios", "Movimentos"))
        try:
            calibrar(tela.capturar_tela, interacao.identificar_janela_dominio_atual,
                     interacao.janela_dominio_em_foco, cabecalho)
        except ValueError:
            raise LoginRecusado("calibracao_nao_confirmada") from None
        sessao.fase("calibracao_confirmada")

    def capturar(self, sessao):
        from app import interacao
        import io
        sessao.fase("capturando_tela")
        janelas = self._atualizar_janelas()
        candidatas = [j for j in janelas if interacao._titulo_dominio(j["titulo"])]
        if len(candidatas) != 1:
            candidatas = [j for j in janelas if j["titulo"].strip().casefold() in ("lista de programas", "conectando ...", "conectando...")]
        if len(candidatas) != 1:
            raise LoginRecusado("janela_login_nao_confirmada")
        sessao.verificar()
        imagem, _ = self._capturar(candidatas[0])
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")
        with self._captura_lock:
            self._captura = (buffer.getvalue(), time.monotonic() + 30)
        sessao.fase("captura_pronta")

    def obter_captura(self):
        with self._captura_lock:
            if self._captura is None:
                return None
            imagem, validade = self._captura
            if time.monotonic() >= validade:
                self._captura = None
                return None
            return imagem

    def reiniciar(self, sessao):
        from app import interacao
        sessao.fase("fechando_ciclo")
        # Pedido explícito de reinício: também inclui Domínio já aberto antes do RPA.
        for janela in self._janelas_visiveis():
            if interacao._titulo_dominio(janela["titulo"]) or janela["titulo"].strip().casefold() in ("lista de programas", "conectando ...", "conectando..."):
                self._janelas[janela["hwnd"]] = janela
        api, _ = interacao._api_janelas()
        api.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        api.PostMessageW.restype = wintypes.BOOL
        for janela in list(self._janelas.values()):
            atual = interacao._dados_janela(api, janela["hwnd"])
            if atual is None:
                continue
            if any(atual[k] != janela[k] for k in ("pid", "classe")):
                raise LoginRecusado("fechamento_nao_confirmado")
            sessao.verificar()
            if not api.PostMessageW(janela["hwnd"], 0x0010, 0, 0):  # WM_CLOSE, sem taskkill
                raise LoginRecusado("fechamento_nao_confirmado")
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            sessao.verificar()
            if not any(interacao._dados_janela(api, j["hwnd"]) for j in self._janelas.values()):
                break
            time.sleep(0.2)
        else:
            raise LoginRecusado("fechamento_nao_confirmado")
        self._janelas.clear()
        self.encerrar()

    def encerrar(self):
        with self._captura_lock:
            self._captura = None
        if self._contexto is not None:
            try:
                self._contexto.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._playwright = self._contexto = self._pagina = None
