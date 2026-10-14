"""Botão OK do Resumo por OCR e bordas atuais, sem ações de desktop.

A geometria vem da própria captura. Não calcula OK pela posição de Fechar
nem reaproveita coordenadas de outra execução. Falha/ambiguidade retorna
None. Fixtures sintéticas não equivalem à validação no Domínio real.
"""
import math

from app import tela
from app.formulario_livros import _palavras, _rotulo
from app.leitura_resumo import (formulario_resumo_reconhecido, medir_campos,
                                resolver_rotulos_resumo)

AVISOS = ('Atenção', 'Aviso Empresa', 'Aviso')


def _dentro(posicao, caixa):
    x,y,w,h = caixa
    return x < posicao[0] < x+w and y < posicao[1] < y+h


def _retangulos(imagem, altura):
    import cv2
    import numpy as np
    cinza = np.asarray(imagem.convert('L'))
    candidatos = set()
    mascaras = [(cinza < limite).astype('uint8')*255 for limite in (160,200,230)]
    mascaras.append(cv2.Canny(cinza,8,30))
    for mascara in mascaras:
        contornos,_ = cv2.findContours(mascara,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            x,y,w,h = cv2.boundingRect(contorno)
            vertices = cv2.approxPolyDP(contorno,.02*cv2.arcLength(contorno,True),True)
            if (len(vertices)==4 and .6*altura <= h <= 1.7*altura
                    and 2 <= w/h <= 8 and cv2.contourArea(contorno)/(w*h) > .7):
                candidatos.add((x,y,w,h))
    unicos = []
    for c in sorted(candidatos,key=lambda c:c[2]*c[3],reverse=True):
        if not any(c[0]>=a[0] and c[1]>=a[1] and c[0]+c[2]<=a[0]+a[2]
                   and c[1]+c[3]<=a[1]+a[3] for a in unicos):
            unicos.append(c)
    return unicos


def _texto_recorte(imagem, caixa):
    """Texto inteiro do botão: não aceita palavra contida em outra."""
    import pytesseract
    x,y,w,h = caixa
    margem = max(1,math.ceil(h*.08))
    recorte = imagem.crop((x+margem,y+margem,x+w-margem,y+h-margem))
    reconhecidos = set()
    for preparo in ('cinza','binaria'):
        for escala in (2,4):
            try:
                preparado = tela.preparar_recorte_ocr(recorte,escala,preparo)
                # Sem whitelist: não apagar outros caracteres para fabricar OK.
                dados = pytesseract.image_to_data(preparado,lang='por',config='--psm 7',
                                                  output_type=pytesseract.Output.DICT)
                palavras = [str(t).strip() for t in dados['text'] if str(t).strip()]
                texto = ' '.join(palavras).casefold()
                if texto:
                    reconhecidos.add(texto)
            except Exception:
                continue
    return reconhecidos


def _contexto_coluna(imagem):
    contextos = []
    for motor,escala in (('tesseract',2),('tesseract',4),('windows',2),('windows',4)):
        try:
            dados = (tela._ler_dados_ocr(imagem,escala) if motor=='tesseract'
                     else tela.ler_dados_ocr_windows(imagem,escala))
            if dados is None:
                continue
            campos = medir_campos(imagem,resolver_rotulos_resumo(imagem,dados,escala,
                                                               titulo_confirmado=True))
            palavras = _palavras(dados,escala)
            fechar = _rotulo(palavras,'Fechar')
            centro = (fechar['x']+fechar['w']/2,fechar['y']+fechar['h']/2)
            altura = max(c['retangulo'][3] for c in campos.values())
            direita = max(c['retangulo'][0]+c['retangulo'][2] for c in campos.values())
            caixas = [c for c in _retangulos(imagem,altura) if c[0] > direita]
            fechar_caixas = [c for c in caixas if _dentro(centro,c)]
            if len(fechar_caixas)!=1:
                continue
            botao_fechar = fechar_caixas[0]
            # Fechar só delimita a coluna observada. Nenhum deslocamento
            # do rótulo/botão é usado para inventar a posição do OK.
            tolerancia = botao_fechar[3]*.2
            candidatos = [c for c in caixas if c[1]+c[3] <= botao_fechar[1]
                and abs(c[0]-botao_fechar[0]) <= tolerancia
                and abs(c[2]-botao_fechar[2]) <= tolerancia
                and abs(c[3]-botao_fechar[3]) <= tolerancia
                and c[1]+c[3] >= campos['inicial']['retangulo'][1]-altura
                and c[1] <= campos['final']['retangulo'][1]]
            if candidatos:
                contextos.append((tuple(sorted(candidatos)),botao_fechar))
        except Exception:
            continue
    if not contextos or len(set(contextos))!=1:
        return None
    return contextos[0]


def achar_ok_resumo(imagem):
    """Devolve centro do botão inequívoco ou None; nunca clica/gera."""
    try:
        for aviso in AVISOS:
            for escala in (2,4):
                if (tela.achar_texto_ou_no_centro(imagem,aviso,escala=escala) is not None
                        or tela.achar_texto_windows(imagem,aviso,escala=escala) is not None):
                    return None
        if formulario_resumo_reconhecido(imagem) is None:
            return None
        contexto = _contexto_coluna(imagem)
        if contexto is None:
            return None
        candidatos,fechar = contexto
        # Procura também pelas leituras comuns; um OK fora da coluna
        # medida indica outro contexto e não autoriza a emissão.
        for motor,escala in (('tesseract',2),('tesseract',4),('windows',2),('windows',4)):
            try:
                pos = (tela.achar_texto_ou_no_centro(imagem,'OK',escala=escala)
                       if motor=='tesseract' else tela.achar_texto_windows(imagem,'OK',escala=escala))
                if pos is not None:
                    if not any(_dentro(pos,c) for c in candidatos):
                        return None
            except Exception:
                continue
        # O fallback lê cada retângulo medido, mesmo quando tela cheia
        # não segmentou OK. Aceita somente o texto inteiro, sem correções.
        if _texto_recorte(imagem,fechar) != {'fechar'}:
            return None
        confirmados = [c for c in candidatos if _texto_recorte(imagem,c) == {'ok'}]
        if len(confirmados)!=1:
            return None
        x,y,w,h = confirmados[0]
        return (x+w//2,y+h//2)
    except Exception:
        return None
