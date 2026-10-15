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
from .controle_execucao import ponto_seguro, ponto_seguro_sem_foco, ExecucaoInterrompida

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
    ponto_seguro()
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
        "BringWindowToTop": ([wintypes.HWND], wintypes.BOOL),
        "AttachThreadInput": ([wintypes.DWORD, wintypes.DWORD, wintypes.BOOL], wintypes.BOOL),
        "ShowWindow": ([wintypes.HWND, ctypes.c_int], wintypes.BOOL),
        "EnumWindows": ([callback, wintypes.LPARAM], wintypes.BOOL),
        "PostMessageW": ([wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
        "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(_Retangulo)], wintypes.BOOL),
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


def _identidade_dominio_confere(api, janela):
    atual = _dados_janela(api, janela["hwnd"])
    if atual is None or any(atual[chave] != janela[chave] for chave in ("pid", "classe")):
        return False
    if _titulo_dominio(janela["titulo"]):
        return _titulo_dominio(atual["titulo"])
    return (atual["classe"] == "DisplayClientWindowClass"
            and not atual["titulo"].strip() and atual["titulo"] == janela["titulo"])


def janela_dominio_em_foco(janela):
    """Confere o HWND associado à rotina, sem mudar foco nem enviar ação."""
    if janela is None:
        return False
    try:
        api, _ = _api_janelas()
        if api.GetForegroundWindow() != janela["hwnd"]:
            return False
        return _identidade_dominio_confere(api, janela)
    except Exception:
        return False


def _janela_remota_do_dominio(api, janela, hwnd_frente):
    """Dados da janela em foco se for outra janela do MESMO cliente GO-Global.

    Diálogos remotos ("Salvar em PDF", "Procurar Pasta") são janelas próprias,
    com outro HWND, mas mesmo processo e mesma classe da janela principal do
    Domínio. O Acrobat remoto TAMBÉM pode ter esse PID/classe: esta relação
    permite acompanhar a exportação, mas não confirma o retorno ao Domínio.
    """
    dados = _dados_janela(api, hwnd_frente)
    if dados is None or dados["hwnd"] == janela["hwnd"]:
        return None
    if dados["pid"] != janela["pid"] or dados["classe"] != janela["classe"]:
        return None
    return dados


def janela_dominio_ou_remota_em_foco(janela):
    """Foco na janela do Domínio OU em um diálogo remoto do mesmo cliente.

    Só confere, sem mudar foco nem enviar ação. A conferência estrita
    (`janela_dominio_em_foco`) continua valendo onde a tela principal é exigida.
    """
    if janela_dominio_em_foco(janela):
        return True
    if janela is None:
        return False
    try:
        api, _ = _api_janelas()
        return _janela_remota_do_dominio(api, janela, api.GetForegroundWindow()) is not None
    except Exception:
        return False


_WM_CLOSE = 0x0010
_MARCAS_LEITOR_PDF = ("adobe acrobat", "acrobat reader", "adobe reader")


class _Retangulo(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _titulo_leitor_pdf(titulo):
    texto = titulo.casefold()
    return ".pdf" in texto and any(marca in texto for marca in _MARCAS_LEITOR_PDF)


def listar_leitores_pdf():
    """{HWND: título} das janelas visíveis de leitor de PDF (Adobe) com um .pdf no título.

    O leitor NÃO é um processo local: o Acrobat roda no servidor remoto e aparece como
    janela do cliente GO-Global (AppController.exe, classe DisplayClientWindowClass,
    título "Empresa 70 - X.pdf - Adobe Acrobat Reader (32-bit)"). Por isso o
    reconhecimento é pelo título, nunca pelo nome do processo.
    """
    api, callback = _api_janelas()
    achados = {}

    def enumerar(hwnd, _):
        dados = _dados_janela(api, hwnd)
        if dados:
            if _titulo_leitor_pdf(dados["titulo"]):
                achados[dados["hwnd"]] = dados["titulo"]
        return True

    if not api.EnumWindows(callback(enumerar), 0):
        raise OSError("Não foi possível enumerar as janelas do leitor de PDF.")
    return achados


def _focar_leitor_pdf(api, hwnd):
    ponto_seguro_sem_foco()
    antes = _dados_janela(api, hwnd)
    if antes is None or not _titulo_leitor_pdf(antes["titulo"]):
        return False
    if not _trazer_para_frente(api, hwnd):
        return False
    ponto_seguro_sem_foco()
    return api.GetForegroundWindow() == hwnd and _dados_janela(api, hwnd) == antes


def _fechar_leitor_pdf_com_atalho(api, hwnd):
    """Alt+F4 somente no leitor reconhecido e confirmado em primeiro plano."""
    if not _focar_leitor_pdf(api, hwnd):
        return False
    leitor = _dados_janela(api, hwnd)
    ponto_seguro_sem_foco()
    if (leitor is None or not _titulo_leitor_pdf(leitor["titulo"])
            or api.GetForegroundWindow() != hwnd or _dados_janela(api, hwnd) != leitor):
        return False
    print("Fechando o leitor de PDF identificado com Alt+F4.", flush=True)
    pyautogui.hotkey("alt", "f4")
    return True


def _clicar_x_da_janela(api, hwnd):
    """Última tentativa no leitor identificado; não desloca X fora da tela."""
    if not _focar_leitor_pdf(api, hwnd):
        return False
    leitor = _dados_janela(api, hwnd)
    retangulo = _Retangulo()
    if not api.GetWindowRect(hwnd, ctypes.byref(retangulo)):
        return False
    largura, altura = pyautogui.size()
    if retangulo.right - retangulo.left < 200 or retangulo.bottom - retangulo.top < 150:
        return False
    if not (0 <= retangulo.left < retangulo.right <= largura
            and 0 <= retangulo.top < retangulo.bottom <= altura):
        return False
    x = retangulo.right - 24
    y = retangulo.top + 16
    ponto_seguro_sem_foco()
    if (leitor is None or not _titulo_leitor_pdf(leitor["titulo"])
            or api.GetForegroundWindow() != hwnd or _dados_janela(api, hwnd) != leitor):
        return False
    print(f"Clicando no X da janela do leitor de PDF: ({x}, {y}).", flush=True)
    # O leitor local pode ser outro processo; a autorização é este HWND de
    # Adobe novo, não a trava de foco usada nas ações fiscais do Domínio.
    pyautogui.moveTo(x, y, duration=0.3)
    ponto_seguro_sem_foco()
    if api.GetForegroundWindow() != hwnd or _dados_janela(api, hwnd) != leitor:
        return False
    atual = _Retangulo()
    if (not api.GetWindowRect(hwnd, ctypes.byref(atual))
            or (atual.left, atual.top, atual.right, atual.bottom)
            != (retangulo.left, retangulo.top, retangulo.right, retangulo.bottom)):
        return False
    pyautogui.click(x, y)
    return True


def fechar_leitores_pdf_uma_vez(linha_base, fechadas):
    """Uma varredura: pede o fechamento (WM_CLOSE, como o X) de leitores de PDF novos.

    `linha_base`: `listar_leitores_pdf()` tirada ANTES da exportação (as que o
    operador já tinha abertas nunca são fechadas). `fechadas`: HWND já pedidos
    (atualizado aqui). Não envia teclas. Devolve os HWND pedidos que ainda
    constavam na listagem desta varredura; a seguinte confirma que sumiram.
    """
    ponto_seguro_sem_foco()
    if linha_base is None:
        return []  # sem inventário anterior, nenhum leitor pode ser fechado
    api, _ = _api_janelas()
    atuais = listar_leitores_pdf()
    for hwnd in atuais:
        if hwnd not in linha_base and hwnd not in fechadas:
            ponto_seguro_sem_foco()
            dados = _dados_janela(api, hwnd)
            if dados is None or dados["titulo"] != atuais[hwnd] or not _titulo_leitor_pdf(dados["titulo"]):
                continue
            print("Fechando o leitor de PDF aberto pela exportação.", flush=True)
            api.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
            fechadas.add(hwnd)
    return [h for h in fechadas if h in atuais]


def fechar_leitores_pdf_novos(linha_base, espera=20, intervalo=0.5, calma=2.5, espera_clique=4):
    """Espera o leitor de PDF aparecer, fecha as janelas novas e confirma que sumiram.

    WM_CLOSE, depois Alt+F4 no leitor confirmado; se persistir, tenta o X.
    Aguarda `calma` s por outras janelas novas. Devolve só as que sumiram.
    """
    ponto_seguro_sem_foco()
    if linha_base is None:
        return 0
    api, _ = _api_janelas()
    fechadas = set()
    pedido_em = {}
    clicadas = set()
    atalhos = set()
    prazo = time.monotonic() + espera
    ultima_acao = None
    quantidade_anterior = 0
    while True:
        ponto_seguro_sem_foco()
        abertas = fechar_leitores_pdf_uma_vez(linha_base, fechadas)
        agora = time.monotonic()
        for hwnd in fechadas:
            pedido_em.setdefault(hwnd, agora)
        for hwnd in abertas:
            if hwnd not in atalhos and agora - pedido_em[hwnd] >= espera_clique:
                atalhos.add(hwnd)
                try:
                    _fechar_leitor_pdf_com_atalho(api, hwnd)
                except ExecucaoInterrompida:
                    raise
                except Exception:
                    print("Não consegui fechar o leitor de PDF pelo teclado.", flush=True)
            elif hwnd not in clicadas and agora - pedido_em[hwnd] >= espera_clique + 2:
                clicadas.add(hwnd)
                try:
                    _clicar_x_da_janela(api, hwnd)
                except ExecucaoInterrompida:
                    raise
                except Exception:
                    print("Não consegui clicar no X do leitor de PDF.", flush=True)
        if len(fechadas) != quantidade_anterior:
            quantidade_anterior = len(fechadas)
            ultima_acao = agora
        if fechadas:
            if not abertas and agora - ultima_acao >= calma:
                return len(fechadas) - len(abertas)
            if agora - ultima_acao >= espera + espera_clique:
                print("O leitor de PDF não fechou no prazo.", flush=True)
                return len(fechadas) - len(abertas)
        elif agora >= prazo:
            return 0
        time.sleep(intervalo)


def voltar_ao_dominio_com_alt_tab(janela, tentativas=3, espera=0.8):
    """Recupera o HWND exato do Domínio; Adobe remoto não comprova retorno.

    Só envia a tecla se o foco NÃO está no Domínio, confere o foco depois de cada
    Alt+Tab e para assim que voltar (repetir sem conferir alternaria de novo).
    Respeita pausa/interrupção, mas não a trava de foco (é o que a recuperação corrige).
    """
    ponto_seguro_sem_foco()
    if janela is None:
        return False
    try:
        api, _ = _api_janelas()
        if not _identidade_dominio_confere(api, janela):
            return False
        if janela_dominio_em_foco(janela):
            return True
        if api.IsIconic(janela["hwnd"]):
            ponto_seguro_sem_foco()
            api.ShowWindow(janela["hwnd"], 9)
        print("Recuperando a janela identificada do Domínio.", flush=True)
        _trazer_para_frente(api, janela["hwnd"])
        for _ in range(tentativas):
            ponto_seguro_sem_foco()
            if janela_dominio_em_foco(janela):
                print("FOCO_DOMINIO confirmado", flush=True)
                return True
            if not _identidade_dominio_confere(api, janela):
                return False
            print("Domínio fora de foco; Alt+Tab para voltar a ele.", flush=True)
            pyautogui.hotkey("alt", "tab")
            time.sleep(espera)
        return janela_dominio_em_foco(janela)
    except ExecucaoInterrompida:
        raise
    except Exception:
        return False


def _trazer_para_frente(api, hwnd):
    """Traz o HWND já identificado para a frente, sem enviar teclas a outro programa.

    O Windows costuma recusar SetForegroundWindow quando o processo chamador
    não está em primeiro plano (por exemplo, com o painel aberto no navegador
    do mesmo PC). Na segunda tentativa a entrada é anexada, só durante a
    chamada, à thread que está na frente.
    """
    def esperar():
        for _ in range(10):
            ponto_seguro_sem_foco()
            if api.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.05)
        return False

    ponto_seguro_sem_foco()
    if api.GetForegroundWindow() == hwnd:
        return True
    api.SetForegroundWindow(hwnd)
    if esperar():
        return True
    try:
        ponto_seguro_sem_foco()
        frente = api.GetForegroundWindow()
        minha_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        thread_frente = api.GetWindowThreadProcessId(frente, None) if frente else 0
        if not thread_frente or thread_frente == minha_thread:
            return False
        api.AttachThreadInput(minha_thread, thread_frente, True)
        try:
            api.BringWindowToTop(hwnd)
            api.SetForegroundWindow(hwnd)
        finally:
            api.AttachThreadInput(minha_thread, thread_frente, False)
    except ExecucaoInterrompida:
        raise
    except Exception:
        return False
    return esperar()


def descrever_primeiro_plano(pid_dominio=None):
    """Texto de diagnóstico sem título nem conteúdo: só a classe da janela em foco."""
    try:
        api, _ = _api_janelas()
        dados = _dados_janela(api, api.GetForegroundWindow())
        if dados is None:
            return "janela em foco: nenhuma visível"
        mesmo = "" if pid_dominio is None else f"; mesmo processo do Domínio: {dados['pid'] == pid_dominio}"
        return f"janela em foco: classe {dados['classe']}{mesmo}"
    except Exception:
        return "janela em foco: não foi possível descrever"


def pressionar_esc_no_dominio(janela=None, vezes=2, intervalo=0.5, confirmar_conteudo=None):
    """Retoma HWND identificado e confirma foco antes de cada Esc.

    Sem vínculo anterior, aceita apenas título Domínio inequívoco e único.
    Não clica, fecha leitor PDF ou infere janela apenas pela classe.
    Retorna False se não conseguir confirmar foco; nunca garante fechamento.
    """
    ponto_seguro_sem_foco()
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
        remota = (_janela_remota_do_dominio(api, janela, api.GetForegroundWindow())
                  if janela is not None else None)
        if remota is not None and not _titulo_leitor_pdf(remota["titulo"]):
            # Um diálogo remoto do mesmo cliente (ex.: "Salvar em PDF") está na
            # frente: o Esc vai para ele, sem trocar o foco para a janela principal.
            if confirmar_conteudo is not None and not confirmar_conteudo():
                return False
            for numero_esc in range(vezes):
                ponto_seguro_sem_foco()
                frente = api.GetForegroundWindow()
                if frente != hwnd and _janela_remota_do_dominio(api, janela, frente) is None:
                    return False  # o foco saiu do cliente do Domínio
                if _titulo_leitor_pdf((_dados_janela(api, frente) or {}).get("titulo", "")):
                    return False  # mesmo PID/classe não autoriza Esc no Acrobat
                if numero_esc == 0:
                    print("Diálogo remoto do Domínio em foco; enviando Esc.")
                pressionar_tecla("esc")
                time.sleep(intervalo)
            return True
        if api.IsIconic(hwnd):
            api.ShowWindow(hwnd, 9)  # SW_RESTORE, não fechamento.
        if not _trazer_para_frente(api, hwnd):
            print("Não consegui trazer o Domínio para a frente; "
                  + descrever_primeiro_plano(atual["pid"]) + ". Nenhuma tecla foi enviada.", flush=True)
            return False
        for numero_esc in range(vezes):
            ponto_seguro_sem_foco()
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
    except ExecucaoInterrompida:
        raise
    except Exception:
        return False


def clicar(x, y):
    """Clique 'devagar': move até o ponto, pausa, pressiona, pausa, solta."""
    ponto_seguro()
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.3)
    pyautogui.mouseDown()
    time.sleep(0.15)
    pyautogui.mouseUp()


def passar_mouse(x, y):
    """Só move o mouse até o ponto (sem clicar) — usado pra abrir
    submenu em cascata."""
    ponto_seguro()
    pyautogui.moveTo(x, y, duration=0.4)


def pressionar_tecla(tecla):
    """Pressiona uma tecla isolada (ex.: "f8", "enter") — atalho de
    teclado em vez de achar-e-clicar. Útil pra ação que o Domínio expõe
    por tecla de função (ex.: F8 pra "Troca de empresas")."""
    ponto_seguro()
    pyautogui.press(tecla)


def pressionar_atalho(*teclas):
    """Atalho sintético, sujeito à conferência de foco da execução."""
    ponto_seguro()
    pyautogui.hotkey(*teclas)


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
    ponto_seguro()
    pyautogui.hotkey("ctrl", "a")


def selecionar_tudo_alternativo():
    """Seleciona do início ao fim do campo em foco via Home + Shift+End,
    em vez de Ctrl+A — mais universal entre tipos de campo (funciona
    até em campo mascarado que não trata Ctrl+A como "selecionar tudo",
    achado real da seção 0.23)."""
    ponto_seguro()
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
    ponto_seguro()
    _, y_atual = pyautogui.position()
    pyautogui.moveTo(x, y_atual, duration=0.2)
    time.sleep(0.15)
    clicar(x, y)


def digitar(texto):
    """Digita um texto, tecla por tecla (com pequeno intervalo, mesma
    lógica do clique "devagar" — dar tempo da tela remota do GO-Global
    registrar cada uma). Usado pra preencher campo de busca."""
    ponto_seguro()
    pyautogui.write(texto, interval=0.06)
