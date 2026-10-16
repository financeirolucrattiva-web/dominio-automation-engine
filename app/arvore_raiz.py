"""Percepção local da raiz do seletor: rótulo completo e barra medida.

Nunca clica ou escolhe caminhos. A navegação chama estas funções apenas
na raiz já comprovada; nenhuma tolerância adicional vale nos descendentes.
"""
import math
from app import tela
from app.controle_execucao import ponto_seguro, ExecucaoInterrompida


def localizar_raiz(imagem, detalhes, nome, coluna, altura):
    from app.seletor_pasta import _linhas, _normalizar, _posicao
    from app.leitura_resumo import normalizar_selecao
    x, y, w, h = detalhes['arvore']
    recorte = normalizar_selecao(imagem.crop((x, y, x+w, y+h)))
    votos = []
    for motor, preparo in (('tesseract', 'cinza'), ('tesseract', 'binaria'), ('windows', 'padrao')):
        ponto_seguro()
        try:
            dados = (tela.ler_dados_ocr_formulario(recorte, escala=4, preparo=preparo, psm=6)
                     if motor == 'tesseract' else tela.ler_dados_ocr_windows(recorte, escala=4))
            if dados is None:
                continue
            ps = [{'texto': str(t), 'x': x+dados['left'][i]/4, 'y': y+dados['top'][i]/4,
                   'w': dados['width'][i]/4, 'h': dados['height'][i]/4}
                  for i, t in enumerate(dados['text']) if str(t).strip()]
            candidatos = []
            for linha in _linhas(ps):
                linha = list(linha)
                while linha and _normalizar(linha[0]['texto']) in ('+', '-'):
                    linha.pop(0)
                if not linha or _normalizar(' '.join(p['texto'] for p in linha)) != _normalizar(nome):
                    continue
                if not all(x < p['x'] < p['x']+p['w'] < x+w
                           and y < p['y'] < p['y']+p['h'] < y+h for p in linha):
                    continue
                tolerancia = max(2, min(altura, max(p['h'] for p in linha))*.4)
                if abs(min(p['x'] for p in linha)-coluna) > tolerancia:
                    continue
                candidatos.append({'posicao': _posicao(linha), 'x': min(p['x'] for p in linha),
                                   'y': min(p['y'] for p in linha), 'linha': linha,
                                   'nome': _normalizar(nome), 'tolerancia': tolerancia})
            if len(candidatos) > 1:
                return None  # Homônimos no nível esperado continuam ambíguos.
            if candidatos:
                votos.append(candidatos[0])
        except ExecucaoInterrompida:
            raise
        except (ValueError, KeyError, TypeError, IndexError, OSError, RuntimeError):
            continue
    if len(votos) < 2:
        return None
    primeiro = votos[0]
    if any(abs(v['posicao'][i]-primeiro['posicao'][i]) > primeiro['tolerancia']
           for v in votos for i in (0, 1)):
        return None
    return primeiro


def medir_seta_baixo(imagem, arvore, altura_texto):
    """Exige botão, triângulo/V para baixo e dois lados do trilho na imagem.

    Não calcula uma seta pela posição presumida da barra. Deslocamento,
    escala, ausência de seta e ambiguidades são resolvidos pelos pixels.
    """
    import cv2
    import numpy as np
    x, y, w, h = arvore
    cinza = np.asarray(imagem.convert('L'))
    roi = cinza[y:y+h, x:x+w]
    if not roi.size:
        return None
    candidatos = set()
    caixas = set()
    mascaras = [(roi < limite).astype('uint8')*255 for limite in (160, 200, 230)]
    mascaras.append(cv2.Canny(roi, 8, 30))
    for mascara in mascaras:
        contornos, _ = cv2.findContours(mascara, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            if len(cv2.approxPolyDP(contorno, .02*cv2.arcLength(contorno, True), True)) != 4:
                continue
            bx, by, bw, bh = cv2.boundingRect(contorno)
            caixas.add((bx, by, bw, bh))
            # O contorno do trilho pode terminar na divisória do botão:
            # a borda inferior da árvore fecha o retângulo adjacente.
            if (bh >= 5*bw and .7*altura_texto <= bw <= 2.5*altura_texto
                    and 0 <= w-bx-bw <= bw*.25
                    and .7*altura_texto <= h-by-bh+1 <= 2.5*altura_texto):
                caixas.add((bx, by+bh-1, bw, h-by-bh+1))
            # Botão escuro pode se unir ao contorno do trilho. Nesse caso
            # a divisória horizontal real delimita sua borda superior.
            if (bh >= 5*bw and .7*altura_texto <= bw <= 2.5*altura_texto
                    and 0 <= w-bx-bw <= bw*.25 and 0 <= h-by-bh <= bw*.25):
                faixa = roi[by:by+bh, bx+1:bx+bw-1].astype('int16')
                for linha in range(max(1, bh-math.ceil(2.5*altura_texto)), bh):
                    if faixa.shape[1] and (np.abs(faixa[linha]-faixa[linha-1]) >= 8).mean() >= .65:
                        caixas.add((bx, by+linha, bw, bh-linha))
    for bx, by, bw, bh in caixas:
        if (not .75 <= bw/bh <= 1.3
                or not .7*altura_texto <= min(bw, bh) <= max(bw, bh) <= 2.5*altura_texto
                or not 0 <= w-(bx+bw) <= bw*.25
                or not 0 <= h-(by+bh) <= bh*.25 or by < 3*bh):
            continue
        margem = max(1, math.ceil(min(bw, bh)*.15))
        interno = roi[by+margem:by+bh-margem, bx+margem:bx+bw-margem]
        figuras = []
        for mascara in ((interno < 100), (interno > 200)):
            achadas, _ = cv2.findContours(mascara.astype('uint8')*255,
                                         cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            figuras.extend(achadas)
        triangulos = []
        for figura in figuras:
            casco = cv2.convexHull(figura)
            vertices = cv2.approxPolyDP(casco, .08*cv2.arcLength(casco, True), True)
            if len(vertices) != 3:
                continue
            pontos = sorted((tuple(v[0]) for v in vertices), key=lambda p: p[1])
            a, b, ponta = pontos
            largura, altura = abs(a[0]-b[0]), ponta[1]-min(a[1], b[1])
            if (altura > 1 and abs(a[1]-b[1]) <= max(1, altura*.25)
                    and min(a[0], b[0]) < ponta[0] < max(a[0], b[0])
                    and .8 <= largura/altura <= 3.5
                    and .015*bw*bh <= cv2.contourArea(figura) <= .35*bw*bh):
                componente = np.zeros(interno.shape, dtype='uint8')
                cv2.drawContours(componente, [figura], -1, 255, cv2.FILLED)
                raio = max(1, round(min(largura, altura)*.15))
                def braco(origem):
                    suporte = []
                    for t in np.linspace(0, 1, 10):
                        px = round(origem[0]+t*(ponta[0]-origem[0]))
                        py = round(origem[1]+t*(ponta[1]-origem[1]))
                        area = componente[max(0, py-raio):py+raio+1, max(0, px-raio):px+raio+1]
                        suporte.append(bool(area.size and area.any()))
                    return sum(suporte)/len(suporte) >= .8
                if braco(a) and braco(b):triangulos.append(vertices)
        if len(triangulos) != 1:
            continue
        valores = roi.astype('int16')
        gradiente = np.abs(valores[:, 1:]-valores[:, :-1])
        topo = max(1, bh)
        if by-topo < 3*bh:
            continue
        lados = [gradiente[topo:by, max(0, lado-margem):min(w-1, lado+margem+1)]
                 for lado in (bx, bx+bw-1)]
        if not all(l.size and (l.max(axis=1) >= 8).mean() >= .65 for l in lados):
            continue
        candidatos.add((x+bx, y+by, bw, bh))
    from app.botoes_formulario import _deduplicar_retangulos
    unicos = _deduplicar_retangulos(candidatos)
    if len(unicos) != 1:
        return None
    bx, by, bw, bh = unicos[0]
    return {'posicao': (bx+bw//2, by+bh//2), 'botao': unicos[0],
            'conteudo': (x, y, bx, y+h)}
