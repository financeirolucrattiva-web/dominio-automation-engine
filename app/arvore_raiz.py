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


def _glifos_baixo(pixels, area_referencia):
    """Triângulo ou V com dois braços; mede pixels, inclusive traço de 1px."""
    import cv2
    import numpy as np
    figuras=[]
    for mascara in ((pixels<100),(pixels>200)):
        achadas,_=cv2.findContours(mascara.astype('uint8')*255,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        figuras.extend(achadas)
    achados=[]
    for figura in figuras:
        casco=cv2.convexHull(figura)
        vertices=cv2.approxPolyDP(casco,.08*cv2.arcLength(casco,True),True)
        if len(vertices)!=3:continue
        a,b,ponta=sorted((tuple(v[0]) for v in vertices),key=lambda p:p[1])
        largura,altura=abs(a[0]-b[0]),ponta[1]-min(a[1],b[1])
        componente=np.zeros(pixels.shape,dtype='uint8')
        cv2.drawContours(componente,[figura],-1,255,cv2.FILLED)
        if not (altura>1 and abs(a[1]-b[1])<=max(1,altura*.25)
                and min(a[0],b[0])<ponta[0]<max(a[0],b[0]) and .8<=largura/altura<=3.5
                and .015*area_referencia<=cv2.countNonZero(componente)<=.45*area_referencia):continue
        raio=max(1,round(min(largura,altura)*.15))
        def braco(origem):
            suporte=[]
            for t in np.linspace(0,1,10):
                px=round(origem[0]+t*(ponta[0]-origem[0]))
                py=round(origem[1]+t*(ponta[1]-origem[1]))
                area=componente[max(0,py-raio):py+raio+1,max(0,px-raio):px+raio+1]
                suporte.append(bool(area.size and area.any()))
            return sum(suporte)/len(suporte)>=.8
        if braco(a) and braco(b):achados.append(cv2.boundingRect(figura))
    return achados


def _seta_no_trilho(roi,minimo,maximo,margem_borda):
    """Botão flat: mede bordas do trilho e clica no glifo, sem supor quadrado."""
    import numpy as np
    h,w=roi.shape
    gradiente=np.abs(np.diff(roi.astype('int16'),axis=1))
    fortes=np.flatnonzero((gradiente[1:h-1]>=8).mean(axis=0)>=.65)
    grupos=[]
    for coluna in fortes:
        if not grupos or coluna>grupos[-1][-1]+1:grupos.append([coluna])
        else:grupos[-1].append(coluna)
    bordas=[max(g,key=lambda c:gradiente[:,c].sum()) for g in grupos]
    encontrados={}
    for esquerda in bordas:
        for direita in bordas:
            largura=int(direita-esquerda)
            if not (minimo<=largura<=maximo and h>=5*largura
                    and 0<=w-1-direita<=max(largura*.25,margem_borda)):continue
            trecho_final=gradiente[max(1,h-math.ceil(maximo)):h-2]
            if not all((trecho_final[:,c]>=8).mean()>=.65 for c in (esquerda,direita)):continue
            inicio=max(1,h-math.ceil(maximo+margem_borda))
            # Exclui as duas linhas físicas; o glifo tem que estar dentro delas.
            faixa=roi[inicio:h-1,int(esquerda)+1:int(direita)]
            if not faixa.size:continue
            for gx,gy,gw,gh in _glifos_baixo(faixa,largura*largura):
                centro=gx+gw/2
                if not (gw<.9*largura and .25*largura<centro<.75*largura):continue
                caixa=(int(esquerda)+1+gx,inicio+gy,gw,gh)
                encontrados[caixa]=int(esquerda)+1
    return encontrados


def medir_seta_baixo(imagem, arvore, altura_texto, *, combo=None, registrar=None):
    """Exige seta para baixo e trilho físico; aceita botão flat sem contorno.

    Não calcula uma seta pela posição presumida da barra. Deslocamento,
    escala, ausência de seta e ambiguidades são resolvidos pelos pixels.
    """
    import cv2
    import numpy as np
    diagnostico={'fase':'medicao_barra','origem_escala':'combo' if combo is not None else 'texto',
                 'retangulos':0,'dimensoes_validas':0,'glifos_validos':0,'trilhos_validos':0}
    def informar(motivo):
        if registrar:registrar({**diagnostico,'motivo':motivo})
    def retangulo_valido(r):
        return (len(r)==4 and all(isinstance(v,(int,float)) and math.isfinite(v) and int(v)==v for v in r)
                and r[0]>=0 and r[1]>=0 and r[2]>0 and r[3]>0
                and r[0]+r[2]<=imagem.width and r[1]+r[3]<=imagem.height)
    try:
        valido=retangulo_valido(arvore) and math.isfinite(altura_texto) and altura_texto>0
        if combo is not None:
            valido=(valido and retangulo_valido(combo)
                    and arvore[0]<=combo[0]<arvore[0]+arvore[2]
                    and combo[1]+combo[3]<arvore[1]
                    and abs(combo[0]+combo[2]-arvore[0]-arvore[2])<=1.5*combo[3]
                    and arvore[2]>6*combo[3] and arvore[3]>3*combo[3])
        if not valido:
            informar('geometria_invalida')
            return None
    except (TypeError,ValueError,OverflowError):
        informar('geometria_invalida')
        return None
    x, y, w, h = (int(v) for v in arvore)
    # O contorno da área de texto pode terminar ANTES da barra. O campo
    # Unidade, medido na mesma captura, delimita a extensão lateral segura.
    if combo is not None:
        w=max(x+w,int(combo[0]+combo[2]))-x
        minimo,maximo=.45*combo[3],1.35*combo[3]
        margem_borda=.4*combo[3]
    else:
        minimo,maximo=.7*altura_texto,2.5*altura_texto
        margem_borda=0
    diagnostico.update(arvore=list(arvore),combo=list(combo) if combo is not None else None,
                       roi=[x,y,w,h],altura_ocr=altura_texto)
    cinza = np.asarray(imagem.convert('L'))
    roi = cinza[y:y+h, x:x+w]
    if not roi.size:
        informar('geometria_invalida')
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
            if (bh >= 5*bw and minimo <= bw <= maximo
                    and 0 <= w-bx-bw <= max(bw*.25,margem_borda)
                    and minimo <= h-by-bh+1 <= maximo):
                caixas.add((bx, by+bh-1, bw, h-by-bh+1))
            # Botão escuro pode se unir ao contorno do trilho. Nesse caso
            # a divisória horizontal real delimita sua borda superior.
            if (bh >= 5*bw and minimo <= bw <= maximo
                    and 0 <= w-bx-bw <= max(bw*.25,margem_borda)
                    and 0 <= h-by-bh <= max(bw*.25,margem_borda)):
                faixa = roi[by:by+bh, bx+1:bx+bw-1].astype('int16')
                for linha in range(max(1, bh-math.ceil(maximo)), bh):
                    if faixa.shape[1] and (np.abs(faixa[linha]-faixa[linha-1]) >= 8).mean() >= .65:
                        caixas.add((bx, by+linha, bw, bh-linha))
    diagnostico['retangulos']=len(caixas)
    for bx, by, bw, bh in caixas:
        if (not .75 <= bw/bh <= 1.3
                or not minimo <= min(bw, bh) <= max(bw, bh) <= maximo
                or not 0 <= w-(bx+bw) <= max(bw*.25,margem_borda)
                or not 0 <= h-(by+bh) <= max(bh*.25,margem_borda) or by < 3*bh):
            continue
        diagnostico['dimensoes_validas']+=1
        margem = max(1, math.ceil(min(bw, bh)*.15))
        interno = roi[by+margem:by+bh-margem, bx+margem:bx+bw-margem]
        if len(_glifos_baixo(interno,bw*bh)) != 1:
            continue
        diagnostico['glifos_validos']+=1
        valores = roi.astype('int16')
        gradiente = np.abs(valores[:, 1:]-valores[:, :-1])
        topo = max(1, bh)
        if by-topo < 3*bh:
            continue
        lados = [gradiente[topo:by, max(0, lado-margem):min(w-1, lado+margem+1)]
                 for lado in (bx, bx+bw-1)]
        if not all(l.size and (l.max(axis=1) >= 8).mean() >= .65 for l in lados):
            continue
        diagnostico['trilhos_validos']+=1
        candidatos.add((x+bx, y+by, bw, bh))
    from app.botoes_formulario import _deduplicar_retangulos
    unicos = _deduplicar_retangulos(candidatos)
    if not unicos and combo is not None:
        planos=_seta_no_trilho(roi,minimo,maximo,margem_borda)
        if len(planos)==1:
            (gx,gy,gw,gh),limite_conteudo=next(iter(planos.items()))
            informar('glifo_no_trilho_confirmado')
            return {'posicao':(x+gx+gw//2,y+gy+gh//2),'botao':(x+gx,y+gy,gw,gh),
                    'conteudo':(x,y,x+limite_conteudo,y+h),'origem':'glifo_no_trilho'}
        if len(planos)>1:
            informar('barra_ambigua')
            return None
    if len(unicos) != 1:
        motivo=('barra_ambigua' if len(unicos)>1 else 'botao_nao_delimitado'
                if not diagnostico['dimensoes_validas'] else 'seta_nao_confirmada'
                if not diagnostico['glifos_validos'] else 'trilho_nao_confirmado')
        informar(motivo)
        return None
    bx, by, bw, bh = unicos[0]
    informar('barra_confirmada')
    return {'posicao': (bx+bw//2, by+bh//2), 'botao': unicos[0],
            'conteudo': (x, y, bx, y+h)}
