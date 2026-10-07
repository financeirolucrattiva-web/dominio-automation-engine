"""Interação com a tela: foco, clique e hover.

Ajustes aqui vêm de teste real (ver docs/00-analise-e-plano-fase0.md,
seção 0.6):

- O Domínio precisa estar **em foco** (janela ativa) no momento do
  clique, senão o clique só ativa a janela sem executar a ação nela.
  `focar_dominio()` resolve isso clicando num ponto vazio e seguro do
  meio da tela antes de qualquer ação.
- Clique "devagar" (mover o mouse, esperar, pressionar, esperar, soltar)
  em vez de um clique instantâneo — não isolamos ainda se isso é
  realmente necessário ou se só o foco já bastava, mas o combo funciona.
- Itens de menu com submenu (setinha ▸) abrem com **hover** (passar o
  mouse), não precisam de clique.
"""

import ctypes
import time
import re
import unicodedata
from ctypes import wintypes

import pyautogui

_SW_MINIMIZE = 6


def _minimizar_console_proprio():
    """Minimiza a janela do CMD/console rodando o script, se existir
    (não faz nada se não tiver console — ex.: rodando por `pythonw`) —
    pedido do usuário, seção 0.37: a própria janela do script pode
    acabar tampando o Domínio ou roubando o foco (mesmo risco visto na
    seção 0.28, aqui prevenido antes de precisar do foco, não só
    corrigido depois de perder)."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, _SW_MINIMIZE)
    except Exception:
        pass  # nunca deixa isso quebrar a automação em si


def focar_dominio():
    """Minimiza a janela do próprio script (se tiver console — seção
    0.37) e clica num ponto vazio e seguro do meio da tela, só pra
    garantir que a janela do Domínio fica em foco antes de qualquer
    ação."""
    _minimizar_console_proprio()
    largura, altura = pyautogui.size()
    pyautogui.click(largura // 2, altura // 2)
    time.sleep(1)


def _titulo_dominio(titulo):
    texto = unicodedata.normalize("NFKD", titulo.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return bool(re.match(r"^dominio\s+escrita\s+fiscal(?:\s|[-–]|$)", texto)) and not any(
        trecho in texto for trecho in (".pdf", "adobe", "acrobat")
    )


def _api_janelas():
    """Tipos Win32 explícitos preservam HWND de 64 bits."""
    api = ctypes.windll.user32
    callback = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    assinaturas = {
        "GetForegroundWindow": ([], wintypes.HWND),
        "IsWindow": ([wintypes.HWND], wintypes.BOOL),
        "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
        "IsIconic": ([wintypes.HWND], wintypes.BOOL),
        "GetWindowTextW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        "GetClassNameW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        "GetWindowThreadProcessId": ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
        "SetForegroundWindow": ([wintypes.HWND], wintypes.BOOL),
        "ShowWindow": ([wintypes.HWND, ctypes.c_int], wintypes.BOOL),
        "EnumWindows": ([callback, wintypes.LPARAM], wintypes.BOOL),
    }
    for nome, (argumentos, retorno) in assinaturas.items():
        funcao = getattr(api, nome)
        funcao.argtypes = argumentos
        funcao.restype = retorno
    return api, callback


def _dados_janela(api, hwnd):
    if not hwnd or not api.IsWindow(hwnd) or not api.IsWindowVisible(hwnd):
        return None
    titulo = ctypes.create_unicode_buffer(1024)
    classe = ctypes.create_unicode_buffer(256)
    pid = wintypes.DWORD()
    api.GetWindowTextW(hwnd, titulo, len(titulo))
    api.GetClassNameW(hwnd, classe, len(classe))
    api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    return {"hwnd": hwnd, "pid": pid.value, "classe": classe.value, "titulo": titulo.value}


def identificar_janela_dominio_atual():
    """Vincula HWND ao checkpoint OCR que o chamador acabou de observar.

    Classe GO-Global isolada nunca autoriza procurar outras janelas.
    Esta função só é usada imediatamente após reconhecer a prévia.
    """
    try:
        api, _ = _api_janelas()
        dados = _dados_janela(api, api.GetForegroundWindow())
        if dados and (_titulo_dominio(dados["titulo"]) or (dados["classe"] == "DisplayClientWindowClass" and not dados["titulo"].strip())):
            return dados
    except Exception:
        pass
    return None


def janela_dominio_em_foco(janela):
    """Confere o HWND associado à rotina, sem mudar foco nem enviar ação."""
    if janela is None:
        return False
    try:
        api, _ = _api_janelas()
        if api.GetForegroundWindow() != janela["hwnd"]:
            return False
        atual = _dados_janela(api, janela["hwnd"])
        if atual is None or any(atual[chave] != janela[chave] for chave in ("pid", "classe")):
            return False
        if _titulo_dominio(janela["titulo"]):
            return _titulo_dominio(atual["titulo"])
        return atual["classe"] == "DisplayClientWindowClass" and not atual["titulo"].strip() and atual["titulo"] == janela["titulo"]
    except Exception:
        return False


def pressionar_esc_no_dominio(janela=None, vezes=2, intervalo=0.5, confirmar_conteudo=None):
    """Retoma HWND identificado e confirma foco antes de cada Esc.

    Sem vínculo anterior, aceita apenas título Domínio inequívoco e único.
    Não clica, fecha leitor PDF ou infere janela apenas pela classe.
    Retorna False se não conseguir confirmar foco; nunca garante fechamento.
    """
    try:
        api, callback = _api_janelas()
        candidatas = []

        def enumerar(hwnd, _):
            dados = _dados_janela(api, hwnd)
            if dados and _titulo_dominio(dados["titulo"]):
                candidatas.append(dados)
            return True

        if not api.EnumWindows(callback(enumerar), 0):
            return False
        if janela is not None:
            atual = _dados_janela(api, janela["hwnd"])
            if atual is None or any(atual[chave] != janela[chave] for chave in ("pid", "classe")):
                return False
            if _titulo_dominio(janela["titulo"]):
                if not _titulo_dominio(atual["titulo"]):
                    return False
            elif (
                atual["classe"] != "DisplayClientWindowClass"
                or atual["titulo"].strip()
                or atual["titulo"] != janela["titulo"]
            ):
                return False
            if any(c["hwnd"] != atual["hwnd"] for c in candidatas):
                return False
        else:
            if len(candidatas) != 1:
                return False
            atual = candidatas[0]
        hwnd = atual["hwnd"]
        if api.IsIconic(hwnd):
            api.ShowWindow(hwnd, 9)  # SW_RESTORE, não fechamento.
        if api.GetForegroundWindow() != hwnd:
            api.SetForegroundWindow(hwnd)
        for _ in range(10):
            if api.GetForegroundWindow() == hwnd:
                break
            time.sleep(0.05)
        else:
            return False
        for numero_esc in range(vezes):
            conferida = _dados_janela(api, hwnd)
            if conferida is None or any(conferida[chave] != atual[chave] for chave in ("pid", "classe")):
                return False
            if _titulo_dominio(atual["titulo"]):
                if not _titulo_dominio(conferida["titulo"]):
                    return False
            elif conferida["titulo"] != atual["titulo"]:
                return False
            if api.GetForegroundWindow() != hwnd:
                return False
            if not _titulo_dominio(conferida["titulo"]):
                if confirmar_conteudo is None:
                    return False
                for tentativa_ocr in range(3):
                    if api.GetForegroundWindow() != hwnd:
                        return False
                    if confirmar_conteudo():
                        break
                    if tentativa_ocr < 2:
                        time.sleep(0.2)
                else:
                    return False
                if api.GetForegroundWindow() != hwnd:
                    return False
            if numero_esc == 0:
                print("Foco do Domínio confirmado; enviando Esc.")
            pressionar_tecla("esc")
            time.sleep(intervalo)
        return True
    except Exception:
        return False


def clicar(x, y):
    """Clique 'devagar': move até o ponto, pausa, pressiona, pausa, solta."""
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.3)
    pyautogui.mouseDown()
    time.sleep(0.15)
    pyautogui.mouseUp()


def passar_mouse(x, y):
    """Só move o mouse até o ponto (sem clicar) — usado pra abrir
    submenu em cascata."""
    pyautogui.moveTo(x, y, duration=0.4)


def pressionar_tecla(tecla):
    """Pressiona uma tecla isolada (ex.: "f8", "enter") — atalho de
    teclado em vez de achar-e-clicar. Útil pra ação que o Domínio expõe
    por tecla de função (ex.: F8 pra "Troca de empresas")."""
    pyautogui.press(tecla)


def pressionar_enter():
    """Pressiona Enter — usado pra confirmar caixa de diálogo padrão do
    Windows com um botão só (ex.: mensagem de sucesso "Final da
    exportação."), que aceita Enter no botão padrão sem precisar clicar
    nele — confirmado funcionando pra esse caso (seção 0.13).

    **Não funciona igual pra caixa de diálogo com vários botões** (ex.:
    a tela de SPED Fiscal/EFD Contribuições, com OK/Fechar/Empresas...)
    — testado e não ativou o OK (achado real, seção 0.22). Não usar
    Enter como atalho pra "botão padrão" fora do caso de diálogo de um
    botão só.
    """
    pressionar_tecla("enter")


def pressionar_esc_repetidas(vezes=5, intervalo=0.5):
    """Aperta Esc várias vezes seguidas, com uma pausa entre elas —
    recuperação genérica de último recurso pra quando o motor não
    reconhece mais o que está na tela (seção 0.34, pedido do usuário).

    Esc é o "cancelar"/"fechar" universal de diálogo do Windows — ao
    contrário de Enter (confirma o botão padrão, seção 0.13, arriscado
    num diálogo desconhecido) ou de um clique (precisa saber onde
    clicar), Esc nunca confirma/gera nada, só cancela ou fecha uma
    camada por vez. Repetir várias vezes desempilha diálogo dentro de
    diálogo (ex.: um aviso em cima da tela de geração) até sobrar só a
    tela principal do Domínio — sem precisar saber quantas camadas
    tinha nem o que era cada uma.
    """
    for _ in range(vezes):
        pressionar_tecla("esc")
        time.sleep(intervalo)


def selecionar_tudo():
    """Seleciona todo o texto do campo em foco (Ctrl+A) — usado antes
    de digitar por cima de um valor já existente (ex.: campo de data),
    em vez de digitar no meio ou no fim do que já está lá.

    **Não confiável sozinho em campo mascarado** (ex.: data com máscara
    `99/99/9999`) — achado real, seção 0.23: o valor antigo continuou lá
    depois de `selecionar_tudo()` + digitar, sem mudar nada. Preferir
    `selecionar_tudo_alternativo()` (Home + Shift+End) pra esse caso,
    mais universal entre tipos de campo."""
    pyautogui.hotkey("ctrl", "a")


def selecionar_tudo_alternativo():
    """Seleciona do início ao fim do campo em foco via Home + Shift+End,
    em vez de Ctrl+A — mais universal entre tipos de campo (funciona
    até em campo mascarado que não trata Ctrl+A como "selecionar tudo",
    achado real da seção 0.23)."""
    pyautogui.press("home")
    pyautogui.hotkey("shift", "end")


def clicar_com_desvio(x, y):
    """Clica em (x, y), mas evita ir até lá em linha reta (diagonal) —
    move primeiro na horizontal (mantendo a altura atual do mouse),
    depois na vertical, em L.

    Usado quando o alvo é um item dentro de um submenu que acabou de
    abrir a partir de um item pai (ex.: item do submenu de "Federais",
    depois de passar o mouse em "Federais"). Uma linha reta a partir
    da posição de "Federais" pode atravessar, na diagonal, a linha de
    um item vizinho na mesma coluna (ex.: "Estaduais", logo abaixo) —
    isso troca o submenu aberto pro do vizinho antes mesmo do mouse
    chegar no alvo, e o clique final acerta o item errado. Pedido real
    do usuário, visto por inspeção do menu (seção 0.24).

    Mover primeiro na horizontal, na mesma altura de onde o mouse já
    estava (ainda dentro da linha do item pai, não do vizinho abaixo),
    e só depois descer verticalmente (já dentro da coluna do submenu
    certo, longe da coluna do vizinho) garante que o mouse nunca passa
    por cima do vizinho no meio do caminho.
    """
    _, y_atual = pyautogui.position()
    pyautogui.moveTo(x, y_atual, duration=0.2)
    time.sleep(0.15)
    clicar(x, y)


def digitar(texto):
    """Digita um texto, tecla por tecla (com pequeno intervalo, mesma
    lógica do clique "devagar" — dar tempo da tela remota do GO-Global
    registrar cada uma). Usado pra preencher campo de busca."""
    pyautogui.write(texto, interval=0.06)
