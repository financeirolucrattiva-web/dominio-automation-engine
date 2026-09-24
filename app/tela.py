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
  imagem (ainda não implementado aqui).
"""

import ctypes
from pathlib import Path

from PIL import Image, ImageGrab, ImageOps
import pytesseract
from pytesseract import Output

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
    imagem_ocr = _preparar_para_ocr(imagem, escala) if escala > 1 else imagem
    dados = pytesseract.image_to_data(imagem_ocr, lang="por", output_type=Output.DICT)

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
        gap = dados["left"][anterior] - (dados["left"][atual] + dados["width"][atual])
        if gap > gap_maximo:
            break
        selecionados.insert(0, atual)
        i -= 1
    i = posicao + 1
    while i < len(mesma_linha):
        anterior, atual = mesma_linha[i - 1], mesma_linha[i]
        gap = dados["left"][atual] - (dados["left"][anterior] + dados["width"][anterior])
        if gap > gap_maximo:
            break
        selecionados.append(atual)
        i += 1

    return " ".join(dados["text"][i].strip() for i in selecionados)


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


def salvar(imagem, caminho):
    """Salva `imagem` (objeto PIL) em `caminho`. Sempre salva a imagem
    recebida, nunca tira um print novo — importante pra diagnosticar de
    verdade o que o OCR analisou (bug já visto e corrigido, seção 0.7)."""
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    imagem.save(str(caminho))
