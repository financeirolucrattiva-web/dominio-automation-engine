"""Captura de tela e leitura de texto (OCR) da janela do Domínio.

Todas as decisões aqui vêm de teste real contra o Domínio de verdade
(ver docs/00-analise-e-plano-fase0.md, seções 0.3, 0.5 e 0.7) — não são
suposição:

- OCR de tela inteira perde texto (a barra de menu some). Sempre
  recortar a região antes de ler.
- Texto dentro de menu suspenso (fundo branco sobre fundo azul) só é
  lido de forma confiável depois de ampliar a imagem e converter pra
  tons de cinza. Texto da barra de menu externa (fundo cinza claro) lê
  direto, sem precisar disso.
- Ícone (sem texto) não é achado por OCR — precisa de casamento de
  imagem (`achar_icone()`, seção 0.57 — implementado, ainda não
  confirmado contra o Domínio real).
"""

import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import re
import shutil
from pathlib import Path

from PIL import Image, ImageGrab, ImageOps
import pytesseract
from pytesseract import Output

from . import arquivos


def ler_empresa_selecionada(imagem):
    """Lê NOME - CÓDIGO no canto superior direito observado (seção 0.64).

    Não envia captura nem texto a serviços externos. Retorna (nome, código)
    ou None quando OCR não encontra uma única linha reconhecível.
    """
    largura, altura = imagem.size
    recorte = imagem.crop((largura // 2, 0, largura, min(altura, max(140, int(altura * 0.20)))))
    cinza = ImageOps.grayscale(recorte)
    cinza = cinza.resize((cinza.width * 3, cinza.height * 3))
    # Texto claro sobre o cabeçalho escuro; compara as duas polaridades.
    resultados = set()
    for tentativa in (cinza, ImageOps.invert(cinza)):
        texto = pytesseract.image_to_string(tentativa, lang="por", config="--psm 6")
        empresa = arquivos.empresa_do_cabecalho(texto)
        if empresa is not None:
            resultados.add(empresa)
    return resultados.pop() if len(resultados) == 1 else None

# Achado real, seção 0.53: o instalador do Tesseract às vezes não
# adiciona ao PATH (ou o Windows só aplica isso numa janela nova, nunca
# na que já estava aberta) — pytesseract quebra com "tesseract is not
# installed or it's not in your PATH", mesmo com o Tesseract instalado
# de verdade. Se não achar no PATH, tenta (nessa ordem): o caminho
# configurado manualmente em `data/tesseract_caminho.txt` (seção 0.54 —
# mesmo padrão de `data/chave_api.txt`, pra quando o Tesseract está
# instalado num lugar fora do padrão, sem precisar editar este
# arquivo), depois os dois caminhos padrão do instalador oficial
# (UB-Mannheim) — só desiste de verdade se nenhum dos três existir.
if shutil.which("tesseract") is None:
    _arquivo_caminho_tesseract = Path(__file__).resolve().parent.parent / "data" / "tesseract_caminho.txt"
    _caminho_configurado = None
    if _arquivo_caminho_tesseract.exists():
        _caminho_configurado = _arquivo_caminho_tesseract.read_text(encoding="utf-8").strip() or None

    _achou_tesseract_fallback = False
    for _caminho_padrao in filter(None, (
        _caminho_configurado,
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    )):
        if Path(_caminho_padrao).exists():
            pytesseract.pytesseract.tesseract_cmd = _caminho_padrao
            _achou_tesseract_fallback = True
            break

    # Achado real, seção 0.56: pedido do usuário — buscar sozinho em
    # vez de só conferir 2 caminhos fixos, pro caso do instalador ter
    # posto numa subpasta um pouco diferente (nome com versão, etc.).
    # Não busca o C:\ inteiro (demoraria minutos toda vez que abrisse)
    # — só dentro de "Program Files"/"Program Files (x86)", onde
    # praticamente todo instalador do Windows põe as coisas; rápido
    # (segundos, não minutos) porque é uma fração pequena do disco.
    # Achando, salva em data/tesseract_caminho.txt pra não precisar
    # buscar de novo nas próximas vezes (essa busca só roda quando os
    # caminhos fixos acima falham).
    if not _achou_tesseract_fallback:
        for _pasta_busca in (r"C:\Program Files", r"C:\Program Files (x86)"):
            if not Path(_pasta_busca).is_dir():
                continue
            _encontrados = list(Path(_pasta_busca).glob("**/tesseract.exe"))
            if not _encontrados:
                continue
            _caminho_achado = str(_encontrados[0])
            pytesseract.pytesseract.tesseract_cmd = _caminho_achado
            _achou_tesseract_fallback = True
            try:
                _arquivo_caminho_tesseract.parent.mkdir(parents=True, exist_ok=True)
                _arquivo_caminho_tesseract.write_text(_caminho_achado, encoding="utf-8")
            except OSError:
                pass
            break

    # Achado real, seção 0.55: sem isso, não achar o Tesseract em lugar
    # nenhum só quebrava depois, num erro cru do pytesseract, na
    # primeira leitura de tela — confuso pra quem não é programador.
    # Avisa direto, assim que o programa abre, com o que fazer.
    if not _achou_tesseract_fallback:
        print(
            "AVISO: Tesseract OCR não encontrado (nem no PATH, nem nos "
            "caminhos padrão, nem buscando em Program Files). A "
            "automação não vai conseguir ler a tela até ele ser "
            "instalado:\n"
            "  https://github.com/UB-Mannheim/tesseract/wiki\n"
            "Se já instalou num lugar bem diferente do padrão (outra "
            "unidade, por exemplo), crie o arquivo "
            "data/tesseract_caminho.txt com o caminho completo do "
            "tesseract.exe."
        )

ctypes.windll.user32.SetProcessDPIAware()


def capturar_tela():
    """Tira um print da tela inteira."""
    return ImageGrab.grab()


def recortar_topo(imagem, altura=120):
    """Recorta só a faixa de cima (menu + barra de ferramentas +
    empresa/período) — região validada na seção 0.3."""
    largura, _ = imagem.size
    return imagem.crop((0, 0, largura, altura))


def recortar_area_menu(imagem, altura=300):
    """Recorta uma faixa maior, o suficiente pra cobrir um menu suspenso
    aberto (ex.: depois de clicar em Relatórios)."""
    largura, _ = imagem.size
    return imagem.crop((0, 0, largura, altura))


def _preparar_para_ocr(imagem, escala):
    maior = imagem.resize(
        (imagem.width * escala, imagem.height * escala), Image.LANCZOS
    )
    return ImageOps.grayscale(maior)


_CACHE_OCR = ContextVar("cache_ocr_da_checagem", default=None)


@contextmanager
def reutilizar_ocr():
    """Reutiliza leituras só nesta checagem; não guarda texto entre estados.

    ContextVar isola execuções/threads. A chave usa pixels exatos, tamanho,
    modo e escala, evitando reaproveitar uma leitura de região diferente.
    """
    cache = {}
    token = _CACHE_OCR.set(cache)
    try:
        yield
    finally:
        cache.clear()
        _CACHE_OCR.reset(token)


def _ler_dados_ocr(imagem, escala):
    cache = _CACHE_OCR.get()
    chave = None
    if cache is not None:
        pixels = imagem.convert("RGBA").tobytes() if imagem.mode == "P" else imagem.tobytes()
        chave = (imagem.mode, imagem.size, escala, hashlib.sha256(pixels).digest())
        if chave in cache:
            return cache[chave]
    imagem_ocr = _preparar_para_ocr(imagem, escala) if escala > 1 else imagem
    dados = pytesseract.image_to_data(imagem_ocr, lang="por", output_type=Output.DICT)
    if cache is not None and len(cache) < 8:
        cache[chave] = dados
    return dados


def achar_texto(imagem, alvo, escala=1, debug=False, max_palavras=4):
    """Procura `alvo` (uma ou mais palavras, sem diferenciar maiúscula de
    minúscula) no texto lido por OCR em `imagem`.

    `escala`: 1 para texto de barra de menu (funciona direto); 2 para
    texto dentro de menu suspenso ou caixa de diálogo (precisa de
    pré-processamento, seção 0.7). A coordenada devolvida já é
    convertida de volta pra escala original da imagem, pronta pra usar
    em clicar()/passar_mouse().

    `max_palavras`: até quantas palavras consecutivas tenta juntar pra
    achar alvo de mais de uma palavra (ex.: "SPED Fiscal"). Sempre testa
    janela de 1 palavra em **todas** as posições antes de tentar 2, 3,
    4 — senão um texto mais comprido que contém o alvo por coincidência
    (ex.: "...Movimentos Relatórios" contendo "relatórios") pode vencer
    o alvo certo de uma palavra só (achado real, ver checkpoint em
    docs/00-analise-e-plano-fase0.md).

    Devolve (x, y) do centro do texto encontrado, ou None.
    """
    dados = _ler_dados_ocr(imagem, escala)

    indices_validos = [i for i in range(len(dados["text"])) if dados["text"][i].strip()]
    alvo_lower = alvo.lower()

    for tam in range(1, max_palavras + 1):
        for ini in range(len(indices_validos) - tam + 1):
            janela = indices_validos[ini:ini + tam]
            texto = " ".join(dados["text"][idx].strip() for idx in janela)
            if alvo_lower in texto.lower():
                esquerdas = [dados["left"][idx] for idx in janela]
                topos = [dados["top"][idx] for idx in janela]
                direitas = [dados["left"][idx] + dados["width"][idx] for idx in janela]
                baixos = [dados["top"][idx] + dados["height"][idx] for idx in janela]
                x_centro = (min(esquerdas) + max(direitas)) // 2
                y_centro = (min(topos) + max(baixos)) // 2
                return x_centro // escala, y_centro // escala

    if debug:
        print("Palavras vistas:", [dados["text"][i].strip() for i in indices_validos])
    return None


def achar_texto_windows(imagem, alvo, escala=1, debug=False, max_palavras=4, lang="pt"):
    """Mesma interface de `achar_texto()` (mesmo recorte/escala, mesma
    busca por substring em janelas de 1..`max_palavras` palavras
    consecutivas, mesmo retorno `(x, y)` já na escala da imagem
    original, ou `None`), mas usa o motor de OCR **nativo do Windows**
    (`Windows.Media.Ocr`, pacote `winocr`) em vez do Tesseract.

    Serve de **segunda opinião**, não de substituto: o Tesseract já tem
    muito ajuste fino acumulado neste projeto (seções 0.3/0.7) e
    continua sendo o motor principal. Esta função existe pra quando
    `achar_texto()` falha num texto que devia estar visível — achado
    real medido nesta mesma investigação (seção 0.57): o Tesseract leu
    "Inicial"/"Final" (rótulos da tela "Livros Fiscais") como
    "Iniciat"/"Finat" (troca de "l" por "t"); o motor do Windows leu os
    dois certos, de primeira, no mesmo recorte — sem precisar do truque
    de buscar só o prefixo comum ("Inicia"/"Fina") que o resto do
    código usa pra contornar esse tipo de erro.

    Precisa do pacote `winocr` instalado (`pip install winocr`) e do
    pacote de idioma Português do Windows (Configurações → Hora e
    Idioma → Idioma → Adicionar um idioma → Português) — se qualquer
    um dos dois faltar, devolve `None` em vez de quebrar (mesmo padrão
    de `ia.disponivel()`: funcionalidade opcional, o motor principal
    continua funcionando sem ela).
    """
    try:
        import winocr
    except ImportError:
        if debug:
            print("winocr não instalado — pulando segunda opinião do OCR do Windows.")
        return None

    imagem_ocr = _preparar_para_ocr(imagem, escala) if escala > 1 else imagem

    try:
        resultado = winocr.recognize_pil_sync(imagem_ocr, lang=lang)
    except Exception as erro:
        if debug:
            print(f"OCR do Windows falhou: {erro!r}")
        return None

    palavras = [
        (palavra["text"], palavra["bounding_rect"])
        for linha in resultado["lines"]
        for palavra in linha["words"]
    ]
    alvo_lower = alvo.lower()

    for tam in range(1, max_palavras + 1):
        for ini in range(len(palavras) - tam + 1):
            janela = palavras[ini : ini + tam]
            texto = " ".join(p[0] for p in janela)
            if alvo_lower in texto.lower():
                esquerdas = [r["x"] for _, r in janela]
                topos = [r["y"] for _, r in janela]
                direitas = [r["x"] + r["width"] for _, r in janela]
                baixos = [r["y"] + r["height"] for _, r in janela]
                x_centro = (min(esquerdas) + max(direitas)) / 2
                y_centro = (min(topos) + max(baixos)) / 2
                return int(x_centro // escala), int(y_centro // escala)

    if debug:
        print("OCR do Windows não achou:", repr(alvo), "— palavras vistas:", [p[0] for p in palavras])
    return None


def ler_dados_ocr_windows(imagem, escala=2):
    """Segunda opinião local com caixas medidas; None se indisponível."""
    try:
        import winocr
        imagem_ocr = _preparar_para_ocr(imagem, escala)
        resultado = winocr.recognize_pil_sync(imagem_ocr, lang="pt")
        dados = {chave: [] for chave in ("text", "left", "top", "width", "height")}
        for linha in resultado["lines"]:
            for palavra in linha["words"]:
                dados["text"].append(palavra["text"])
                rect = palavra["bounding_rect"]
                for chave, origem in (("left", "x"), ("top", "y"), ("width", "width"), ("height", "height")):
                    dados[chave].append(rect[origem])
        return dados
    except Exception:
        return None


def ler_texto(imagem, escala=2):
    """Lê todo o texto de `imagem` (normalmente um recorte pequeno, ex.:
    uma caixa de erro) e devolve como string — usado pra decidir o que
    fazer com uma caixa de erro (`app/erros.py`, seção 0.32). Mesmo
    pré-processamento de `achar_texto()` (ampliar + tons de cinza)."""
    imagem_ocr = _preparar_para_ocr(imagem, escala) if escala > 1 else imagem
    return pytesseract.image_to_string(imagem_ocr, lang="por")


def texto_mais_proximo(imagem, x, y, raio_x=150, raio_y=60, escala=3):
    """Acha a palavra (e o resto da mesma linha dela) mais perto do
    ponto `(x, y)` — usado quando não se sabe de antemão qual texto
    procurar, só onde foi clicado (`scripts/gravar.py`, seção 0.35/0.36:
    a primeira versão usava `ler_texto()`, que lê tudo de uma área e
    devolve só a primeira linha — numa área com várias colunas/rótulos
    (ex.: cabeçalho de grid de empresas), a primeira linha lida quase
    nunca é a coisa clicada de verdade, achado real do primeiro teste).

    Ao contrário de `achar_texto()` (procura um texto já conhecido) e
    `ler_texto()` (lê tudo, sem saber qual parte importa), esta função
    usa a posição de cada palavra (`pytesseract.image_to_data()`) pra
    achar a mais próxima do clique, e devolve ela junto com as palavras
    **vizinhas próximas o bastante** pra ser o mesmo rótulo (ex.: "SPED
    Fiscal") — expande a partir da palavra mais próxima, palavra por
    palavra, só enquanto o espaço até a próxima for pequeno; um espaço
    maior que isso indica item diferente, não continuação do mesmo
    rótulo.

    Achado real (seção 0.36 primeira versão, seção 0.37/0.38 aqui):
    reconstruir a **linha inteira** do Tesseract (`line_num`/
    `block_num`) juntava demais numa barra de menu, onde vários itens
    distintos ("Arquivos", "Movimentos", "Relatórios"...) ficam todos
    na mesma linha visual — o palpite saía com 3-4 itens de menu
    concatenados em vez de só o clicado. Parar de expandir quando o
    espaço entre uma palavra e a próxima passa de 1,5x a altura do
    texto (heurística — espaço entre palavra de um mesmo rótulo
    costuma ser bem menor que o espaço entre item e item de menu)
    resolve isso sem precisar reconhecer menu especificamente.

    **Segundo achado real, mais específico (seção 0.82, 07/10/2026)**:
    o gap de 1,5x altura sozinho não bastava — o Domínio desenha um
    traço "—" ENTRE cada item da barra de menu ("Controle — Arquivos —
    Movimentos..."), e esse traço fica com um espaço pequeno dos dois
    lados (menor que o limiar), então a expansão atravessa o traço e
    concatena itens de menu DIFERENTES (ex.: rotina gravada guardou o
    palpite "Movimentos — Relatórios — Utilitários — Fax" pra um
    clique só, texto que nunca existe contíguo na tela de verdade —
    achado contra log real de execução). Um traço isolado agora é
    tratado como fronteira: a expansão para ali, nunca atravessa, nunca
    inclui o traço no resultado.

    Devolve o texto achado (string, vazia se não achar nada).
    """
    recorte, dx, dy = recortar_ao_redor(imagem, x, y, raio_x=raio_x, raio_y=raio_y)
    imagem_ocr = _preparar_para_ocr(recorte, escala)
    dados = pytesseract.image_to_data(imagem_ocr, lang="por", output_type=Output.DICT)

    x_local, y_local = x - dx, y - dy  # ponto do clique, coordenada do recorte (escala 1)
    indices_validos = [i for i in range(len(dados["text"])) if dados["text"][i].strip()]
    if not indices_validos:
        return ""

    def distancia(i):
        cx = (dados["left"][i] + dados["width"][i] / 2) / escala
        cy = (dados["top"][i] + dados["height"][i] / 2) / escala
        return (cx - x_local) ** 2 + (cy - y_local) ** 2

    mais_perto = min(indices_validos, key=distancia)
    linha_alvo = dados["line_num"][mais_perto]
    bloco_alvo = dados["block_num"][mais_perto]
    mesma_linha = sorted(
        (i for i in indices_validos if dados["line_num"][i] == linha_alvo and dados["block_num"][i] == bloco_alvo),
        key=lambda i: dados["left"][i],
    )
    posicao = mesma_linha.index(mais_perto)
    gap_maximo = dados["height"][mais_perto] * 1.5

    selecionados = [mais_perto]
    i = posicao - 1
    while i >= 0:
        anterior, atual = mesma_linha[i + 1], mesma_linha[i]
        if _eh_separador_de_menu(dados["text"][atual]):
            break
        gap = dados["left"][anterior] - (dados["left"][atual] + dados["width"][atual])
        if gap > gap_maximo:
            break
        selecionados.insert(0, atual)
        i -= 1
    i = posicao + 1
    while i < len(mesma_linha):
        anterior, atual = mesma_linha[i - 1], mesma_linha[i]
        if _eh_separador_de_menu(dados["text"][atual]):
            break
        gap = dados["left"][atual] - (dados["left"][anterior] + dados["width"][anterior])
        if gap > gap_maximo:
            break
        selecionados.append(atual)
        i += 1

    return " ".join(dados["text"][i].strip() for i in selecionados)


def _eh_separador_de_menu(texto):
    """Traço isolado (hífen, en dash, em dash) que o Domínio usa pra
    separar item de menu — ver achado real na docstring de
    `texto_mais_proximo()` (seção 0.82)."""
    return bool(re.fullmatch(r"[-‐-―]+", texto.strip()))


def achar_texto_ou_no_centro(imagem, alvo, escala=1, debug=False, max_palavras=4):
    """Acha `alvo` na imagem inteira; se não achar, tenta de novo só na
    região central (`recortar_centro()`) antes de desistir.

    Reforço genérico pra todo ponto sensível que lê texto na tela
    cheia sem uma âncora conhecida (não dá pra usar
    `recortar_ao_redor`/`recortar_a_partir_de` sem saber onde procurar
    primeiro) — pedido do usuário depois do achado da seção 0.29: uma
    tela densa o bastante (formulário cheio de campo de empresa real)
    pode confundir o OCR de tela inteira mesmo quando o texto está bem
    legível, e isso não se limita à confirmação de sucesso — qualquer
    busca sem recorte prévio corre o mesmo risco (troca de empresa,
    título de diálogo, rótulo de campo, etc.).

    Devolve a posição já convertida pra coordenada da imagem original,
    achada na tela cheia ou no recorte central — ou None se não achar
    em nenhum dos dois.
    """
    pos = achar_texto(imagem, alvo, escala=escala, debug=debug, max_palavras=max_palavras)
    if pos is not None:
        return pos
    centro, dx, dy = recortar_centro(imagem)
    pos_centro = achar_texto(centro, alvo, escala=escala, max_palavras=max_palavras)
    if pos_centro is not None:
        return pos_centro[0] + dx, pos_centro[1] + dy
    return None


def recortar_ao_redor(imagem, x, y, raio_x=120, raio_y=90):
    """Recorta uma janela pequena ao redor de um ponto (x, y) já
    conhecido — usado para focar o OCR numa área de baixo ruído perto de
    um texto que já foi achado antes (ver seção 0.10: tela densa de
    diálogo confunde o OCR de tela inteira, recorte pequeno resolve).

    Devolve (recorte, deslocamento_x, deslocamento_y) — os deslocamentos
    são o canto superior esquerdo do recorte na imagem original,
    necessários pra converter de volta uma coordenada achada dentro do
    recorte para a coordenada da tela cheia.
    """
    esquerda = max(0, x - raio_x)
    direita = min(imagem.width, x + raio_x)
    topo = max(0, y - raio_y)
    baixo = min(imagem.height, y + raio_y)
    return imagem.crop((esquerda, topo, direita, baixo)), esquerda, topo


def recortar_centro(imagem, fracao=0.6):
    """Recorta a região central da tela (`fracao` da largura e da
    altura, centralizada) — usado quando o alvo é uma caixa de diálogo
    pequena flutuando por cima de uma tela cheia de campo, e não se
    conhece a posição exata dela de antemão (então não dá pra usar
    `recortar_ao_redor`/`recortar_a_partir_de`, que precisam de uma
    âncora já achada).

    Achado real (seção 0.29): a confirmação de sucesso do SPED Fiscal
    ("Final da exportação.") ficou visível e legível numa captura de
    tela de uma empresa real com formulário bem mais cheio de campo
    que o de teste, mas o OCR de tela inteira não achou o texto — o
    mesmo problema da seção 0.10 (tela densa confunde a segmentação do
    Tesseract), só que agora na confirmação, não no botão OK. Caixa de
    diálogo do Windows nasce quase sempre centralizada na janela pai —
    reduzir a área pro centro tira ruído da borda sem precisar de uma
    âncora conhecida.

    Devolve (recorte, deslocamento_x, deslocamento_y).
    """
    margem_x = int(imagem.width * (1 - fracao) / 2)
    margem_y = int(imagem.height * (1 - fracao) / 2)
    return (
        imagem.crop((margem_x, margem_y, imagem.width - margem_x, imagem.height - margem_y)),
        margem_x,
        margem_y,
    )


def recortar_a_partir_de(imagem, x, y, largura=650, altura=420, margem_cima=20, margem_esquerda=20):
    """Recorta uma janela grande a partir de um ponto já conhecido
    (ex.: o título de um diálogo), estendendo principalmente pra
    direita e pra baixo — usado pra isolar um diálogo inteiro (com sua
    coluna de botões) da tela cheia, sem carregar o resto da tela como
    ruído. Mesmo princípio da seção 0.3 (tela inteira não confia,
    recorte resolve), aplicado a uma área maior que
    `recortar_ao_redor` (que é simétrica e pequena, boa pra vizinhança
    de um botão já achado, não pro diálogo inteiro).

    Achado real (seção 0.22): "Empresas..."/"OK"/"Fechar" às vezes não
    lêem de jeito nenhum na tela inteira, de forma consistente e
    repetida (não é problema de timing) — recortar só a área do
    diálogo antes de procurar esses textos reduz o ruído concorrendo
    pela segmentação do Tesseract.

    Devolve (recorte, deslocamento_x, deslocamento_y).
    """
    esquerda = max(0, x - margem_esquerda)
    topo = max(0, y - margem_cima)
    direita = min(imagem.width, x + largura)
    baixo = min(imagem.height, y + altura)
    return imagem.crop((esquerda, topo, direita, baixo)), esquerda, topo


def melhor_casamento_pixel(imagem, caminho_template):
    """Núcleo de `achar_icone()` sem aplicar limiar — devolve o MELHOR
    candidato que `cv2.matchTemplate` achou, mesmo que a confiança seja
    baixa, mais `(largura, altura)` do template. Público (sem `_` na
    frente) de propósito: `dominio.py` usa essa posição — mesmo de
    baixa confiança — como dica de ONDE recortar pra tentar a visão por
    IA como último recurso (seção 0.61), sem precisar rodar
    `cv2.matchTemplate` duas vezes nem duplicar a chamada do OpenCV.

    Devolve `(x_centro, y_centro, confianca, largura_template,
    altura_template)`, ou `None` se o template não abriu."""
    import cv2
    import numpy as np

    template = cv2.imread(str(caminho_template))
    if template is None:
        return None

    alvo = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)
    resultado = cv2.matchTemplate(alvo, template, cv2.TM_CCOEFF_NORMED)
    _, confianca, _, local_max = cv2.minMaxLoc(resultado)

    th, tw = template.shape[:2]
    x_centro = local_max[0] + tw // 2
    y_centro = local_max[1] + th // 2
    return x_centro, y_centro, confianca, tw, th


def achar_icone(imagem, caminho_template, limiar=0.75, debug=False):
    """Acha um ícone (sem texto, impossível achar por OCR — ver aviso
    no topo deste arquivo) por casamento de imagem (`cv2.matchTemplate`),
    não por leitura de texto.

    `caminho_template`: caminho de um recorte pequeno e já salvo do
    ícone (ex.: `app/icones/exportar_excel.png`), recortado uma única
    vez a partir de um print real — ver seção 0.57 do documento pra
    como esse recorte foi feito e calibrado.

    `limiar` (0 a 1, padrão 0.75): confiança mínima do casamento pra
    aceitar — `cv2.TM_CCOEFF_NORMED` devolve 1.0 pra um casamento
    perfeito. Calibrado conservador de propósito: melhor devolver
    `None` (e quem chamou decide o que fazer, ex.: cair pra um
    deslocamento calculado como plano B) do que aceitar um casamento
    fraco e clicar no lugar errado.

    Devolve o centro `(x, y)` do melhor casamento, ou `None` se nada
    passou do limiar. **Confirmado contra o Domínio real** (seção
    0.58/0.61): funciona na maioria das vezes (confiança 1.000 visto
    ao vivo), mas já falhou pelo menos uma vez (confiança 0.534, abaixo
    do limiar) — confirma a ressalva original sobre anti-aliasing via
    GO-Global; por isso o plano B (`achar_icone_robusto()`) importa de
    verdade, não é só cautela teórica.
    """
    resultado = melhor_casamento_pixel(imagem, caminho_template)
    if resultado is None:
        if debug:
            print(f"Não consegui abrir o template: {caminho_template}")
        return None

    x_centro, y_centro, confianca, _, _ = resultado
    if debug:
        print(f"achar_icone({Path(caminho_template).name}): confiança={confianca:.3f} (limiar={limiar})")

    if confianca < limiar:
        return None
    return x_centro, y_centro


def achar_icone_orb(imagem, caminho_template, minimo_bons=8, debug=False):
    """Segunda técnica de casamento de ícone, por CARACTERÍSTICAS (ORB —
    Oriented FAST and Rotated BRIEF), não por correlação direta de
    pixel como `achar_icone()`. Complemento pedido pelo usuário
    (05/10/2026, seção 0.58): `achar_icone()` já tinha uma ressalva
    própria ("o ícone pode renderizar com leve diferença de cor/
    anti-aliasing na tela ao vivo via GO-Global") — ORB é tolerante
    exatamente a esse tipo de diferença (pequena variação de cor,
    brilho, rotação leve, pequena escala), porque compara pontos de
    interesse estruturais da imagem, não o valor exato de cada pixel.

    `minimo_bons`: quantidade mínima de pontos correspondentes "bons"
    (distância de Hamming baixa no descritor) pra aceitar o casamento —
    calibrado conservador de propósito, mesma filosofia do `limiar` de
    `achar_icone()`: melhor devolver `None` do que um casamento fraco.

    Devolve o centro `(x, y)` do casamento (calculado pela homografia
    entre os pontos do template e os pontos achados na tela), ou `None`
    se não achou pontos suficientes. **Ainda não testado contra o
    Domínio real** — mesma ressalva de `achar_icone()`, calibrar depois
    do primeiro uso real."""
    import cv2
    import numpy as np

    template = cv2.imread(str(caminho_template), cv2.IMREAD_GRAYSCALE)
    if template is None:
        if debug:
            print(f"Não consegui abrir o template: {caminho_template}")
        return None

    alvo = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2GRAY)

    orb = cv2.ORB_create(nfeatures=500)
    kp_template, desc_template = orb.detectAndCompute(template, None)
    kp_alvo, desc_alvo = orb.detectAndCompute(alvo, None)

    if desc_template is None or desc_alvo is None or len(kp_template) < 4:
        if debug:
            print("achar_icone_orb(): poucos pontos de interesse pra comparar.")
        return None

    casador = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    correspondencias = casador.match(desc_template, desc_alvo)
    correspondencias = sorted(correspondencias, key=lambda m: m.distance)
    bons = [m for m in correspondencias if m.distance < 64]  # limiar de distância Hamming, não de contagem

    if debug:
        print(f"achar_icone_orb({Path(caminho_template).name}): {len(bons)} pontos bons (mínimo={minimo_bons})")

    if len(bons) < minimo_bons:
        return None

    # Centro = média das posições, na tela, dos pontos que bateram —
    # mais simples e robusto que calcular homografia completa pra um
    # ícone pequeno (poucos pixels, não compensa a complexidade extra).
    pontos_alvo = np.float32([kp_alvo[m.trainIdx].pt for m in bons])
    x_centro, y_centro = pontos_alvo.mean(axis=0)
    return int(x_centro), int(y_centro)


def achar_icone_robusto(imagem, caminho_template, limiar=0.75, minimo_bons=8, debug=False):
    """Combina as duas técnicas de casamento de ícone: tenta
    `achar_icone()` (correlação de pixel, mais rápido e mais preciso
    quando a renderização é idêntica ao template) primeiro; só se isso
    falhar, tenta `achar_icone_orb()` (por características, mais
    tolerante a diferença de cor/anti-aliasing/escala — ver seção 0.58).
    Use esta função no lugar de `achar_icone()` sozinha em qualquer
    automação nova; `achar_icone()` continua existindo e sendo chamada
    por dentro, nada que já usa ela direto quebra."""
    pos = achar_icone(imagem, caminho_template, limiar=limiar, debug=debug)
    if pos is not None:
        return pos
    if debug:
        print("achar_icone_robusto(): casamento por pixel falhou, tentando por características (ORB)...")
    return achar_icone_orb(imagem, caminho_template, minimo_bons=minimo_bons, debug=debug)


def assinatura_tela(imagem, tamanho=8):
    """"Impressão digital" barata da tela (average hash) — reduz a
    imagem a uma grade `tamanho`×`tamanho` em tons de cinza e devolve
    uma string de bits (1 = pixel mais claro que a média, 0 = mais
    escuro). Duas telas muito parecidas (mesmo estado, só o cursor do
    mouse ou um relógio mudou) produzem assinaturas iguais ou quase
    iguais; telas diferentes produzem assinaturas bem diferentes.

    Pedida pelo usuário (05/10/2026, seção 0.58) pra deixar o RPA mais
    rápido: `esperar_e_achar()` hoje roda OCR completo (Tesseract) a
    cada tentativa de espera, mesmo quando a tela não mudou nada desde
    a tentativa anterior — rodar OCR de novo sobre uma imagem idêntica
    nunca muda a resposta, só gasta tempo. Comparando a assinatura
    antes de rodar OCR, dá pra pular o OCR nas tentativas em que a tela
    ainda não mudou (`tela_mudou()` abaixo)."""
    cinza = imagem.convert("L").resize((tamanho, tamanho))
    pixels = list(cinza.getdata())
    media = sum(pixels) / len(pixels)
    return "".join("1" if p >= media else "0" for p in pixels)


def tela_mudou(assinatura_anterior, assinatura_atual, limiar=3):
    """Compara duas assinaturas de `assinatura_tela()` pela distância de
    Hamming (quantos bits diferem). `limiar` (padrão 3, de 64 bits numa
    grade 8×8): acima disso, considera que a tela mudou de verdade — um
    pingo de diferença (cursor piscando, relógio) não deve disparar OCR
    de novo à toa, mas uma mudança real de conteúdo (diálogo abriu,
    texto apareceu) sempre passa desse limiar baixo.

    `assinatura_anterior=None` (primeira tentativa, sem histórico)
    sempre devolve True — a primeira checagem sempre roda OCR."""
    if assinatura_anterior is None:
        return True
    diferenca = sum(a != b for a, b in zip(assinatura_anterior, assinatura_atual))
    return diferenca > limiar


def salvar(imagem, caminho):
    """Salva `imagem` (objeto PIL) em `caminho`. Sempre salva a imagem
    recebida, nunca tira um print novo — importante pra diagnosticar de
    verdade o que o OCR analisou (bug já visto e corrigido, seção 0.7)."""
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    imagem.save(str(caminho))
