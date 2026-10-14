"""Seletor nativo Procurar Pasta: somente alvos OCR e bordas da captura.

A árvore observada não tem campo para colar caminho. Navega por nomes
locais conhecidos e exige a folha exclusiva selecionada antes de OK.
"""
from pathlib import PureWindowsPath
import re
import time
import unicodedata
from app.controle_execucao import ponto_seguro


class SeletorPastaNaoConfirmado(ValueError):
    """Mensagens fechadas, sem nomes de empresa, caminhos ou OCR livre."""


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto).casefold())
    return ''.join(c for c in texto if not unicodedata.combining(c)).strip()


def _palavras(imagem):
    from app import tela
    dados = tela._ler_dados_ocr(imagem, 4)
    return [{'texto': str(t), 'x': dados['left'][i]/4, 'y': dados['top'][i]/4,
             'w': dados['width'][i]/4, 'h': dados['height'][i]/4}
            for i,t in enumerate(dados['text']) if str(t).strip()]


def _linhas(palavras):
    linhas = []
    for p in sorted(palavras, key=lambda p:(p['y'],p['x'])):
        candidatas = [l for l in linhas if max(p['y'],l[0]['y']) < min(p['y']+p['h'],l[0]['y']+l[0]['h'])]
        if len(candidatas) == 1:
            candidatas[0].append(p)
        else:
            linhas.append([p])
    return [sorted(l,key=lambda p:p['x']) for l in linhas]


def _posicao(linha):
    return (round((min(p['x'] for p in linha)+max(p['x']+p['w'] for p in linha))/2),
            round((min(p['y'] for p in linha)+max(p['y']+p['h'] for p in linha))/2))


def medir_dialogo(imagem):
    """Combo e árvore medidos, restritos pelos rótulos nativos inequívocos."""
    import cv2
    import numpy as np
    palavras = _palavras(imagem)
    from app.formulario_livros import _rotulo
    titulo = _rotulo(palavras, 'Procurar Pasta')
    unidade = _rotulo(palavras, 'Unidade')
    ok = _rotulo(palavras, 'OK')
    cancelar = _rotulo(palavras, 'Cancelar')
    if not (titulo['y'] < unidade['y'] < ok['y'] and abs(ok['y']-cancelar['y']) < 2*ok['h']):
        raise SeletorPastaNaoConfirmado('Seletor nativo não confirmado.')
    cinza = np.array(imagem.convert('L'))
    caixas = set()
    for limite in (160,200,230):
        contornos,_ = cv2.findContours((cinza<limite).astype('uint8')*255,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for c in contornos:
            x,y,w,h = cv2.boundingRect(c)
            if len(cv2.approxPolyDP(c,.02*cv2.arcLength(c,True),True)) == 4:
                caixas.add((x,y,w,h))
    def unica(candidatas):
        unicas=[]
        for c in sorted(candidatas,key=lambda c:c[2]*c[3],reverse=True):
            if not any(c[0]>=a[0] and c[1]>=a[1] and c[0]+c[2]<=a[0]+a[2] and c[1]+c[3]<=a[1]+a[3] for a in unicas):
                unicas.append(c)
        if len(unicas)!=1:raise SeletorPastaNaoConfirmado('Borda do seletor ausente ou ambígua.')
        return unicas[0]
    altura=unidade['h']
    combo=unica([c for c in caixas if unidade['x']+unidade['w']<=c[0]<=unidade['x']+unidade['w']+4*altura
                  and c[1]<unidade['y']+altura/2<c[1]+c[3] and altura<c[3]<4*altura and c[2]>10*altura])
    arvore=unica([c for c in caixas if c[1]>combo[1]+combo[3] and c[1]+c[3]<ok['y']
                   and c[2]>12*altura and c[3]>5*altura and c[0]<combo[0]])
    return {'combo':combo,'arvore':arvore,'palavras':palavras,
            'ok':(round(ok['x']+ok['w']/2),round(ok['y']+ok['h']/2))}


def _drive(palavras, letra):
    achados=[]
    for linha in _linhas(palavras):
        texto=_normalizar(' '.join(p['texto'] for p in linha))
        if re.search(r'client\s*c\s*\(\s*'+re.escape(letra.casefold())+r'\s*:\s*\\?\s*\)',texto):
            achados.append(_posicao(linha))
    if len(achados)>1:raise SeletorPastaNaoConfirmado('Unidade Client C ambígua.')
    return achados[0] if achados else None


def _no(detalhes, nome):
    x,y,w,h=detalhes['arvore']
    palavras=[p for p in detalhes['palavras'] if x<p['x']<x+w and y<p['y']<y+h]
    candidatos=[l for l in _linhas(palavras) if _normalizar(' '.join(p['texto'] for p in l))==_normalizar(nome)]
    if len(candidatos)>1:raise SeletorPastaNaoConfirmado('Pasta repetida na árvore.')
    if not candidatos:return None
    linha=candidatos[0]
    return {'posicao':_posicao(linha),'x':min(p['x'] for p in linha),
            'y':min(p['y'] for p in linha),'linha':linha}


def _selecionado(imagem, no):
    import cv2
    import numpy as np
    p=no['linha']; x=int(min(a['x'] for a in p)); y=int(min(a['y'] for a in p))
    direito=int(max(a['x']+a['w'] for a in p)); baixo=int(max(a['y']+a['h'] for a in p))
    recorte=np.array(imagem.crop((x,y,direito,baixo)).convert('RGB'))
    if not recorte.size:return False
    hsv=cv2.cvtColor(recorte,cv2.COLOR_RGB2HSV)
    return float(((hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>100)&(hsv[:,:,2]>70)).mean())>.25


def _aguardar_dialogo(capturar, confirmar=None, tentativas=6):
    """Relê a captura após cada ação; nunca repete o clique por atraso."""
    for tentativa in range(tentativas):
        ponto_seguro()
        imagem = capturar()
        try:
            detalhes = medir_dialogo(imagem)
            if confirmar is None or confirmar(imagem, detalhes):
                return imagem, detalhes
        except ValueError:
            pass
        if tentativa < tentativas-1:
            time.sleep(.3)
    raise SeletorPastaNaoConfirmado('Seletor de pasta não confirmou o estado esperado; não foi enviado OK.')


def _drive_selecionado(detalhes, letra):
    x,y,w,h = detalhes['combo']
    palavras = [p for p in detalhes['palavras'] if x<p['x']<x+w and y<p['y']<y+h]
    return _drive(palavras, letra) is not None


def _filho(detalhes, pai_nome, filho_nome):
    pai, filho = _no(detalhes, pai_nome), _no(detalhes, filho_nome)
    if not (pai and filho and filho['x']>pai['x'] and filho['y']>pai['y']):
        return None
    x,y,w,h = detalhes['arvore']
    entre = [p for p in detalhes['palavras'] if x<p['x']<=pai['x']+1
             and pai['y']<p['y']<filho['y'] and y<p['y']<y+h]
    return None if entre else filho


def _aguardar_no_selecionado(capturar, nome, letra):
    def confirmar(imagem, detalhes):
        no = _no(detalhes, nome)
        return _drive_selecionado(detalhes, letra) and no is not None and _selecionado(imagem, no)
    return _aguardar_dialogo(capturar, confirmar)


def selecionar_pasta(caminho_remoto, capturar, clicar, tecla):
    """Navega sem colar; só confirma a folha nova e exclusiva informada."""
    caminho=PureWindowsPath(caminho_remoto)
    if not caminho.is_absolute() or not re.fullmatch(r'LIVROS[0-9]{12}',caminho.name):
        raise SeletorPastaNaoConfirmado('Destino precisa ser uma pasta exclusiva de livros.')
    imagem, detalhes = _aguardar_dialogo(capturar)
    x,y,w,h=detalhes['combo']
    combo_palavras=[p for p in detalhes['palavras'] if x<p['x']<x+w and y<p['y']<y+h]
    if _drive(combo_palavras,caminho.drive[0]) is None:
        clicar(x+w//2,y+h//2)
        alvo=None
        for _ in range(5):
            ponto_seguro()
            imagem=capturar()
            try:
                alvo=_drive(_palavras(imagem),caminho.drive[0])
            except ValueError:
                alvo=None
            if alvo is not None:break
            time.sleep(.3)
        if alvo is None:raise SeletorPastaNaoConfirmado('Unidade Client C não encontrada na lista.')
        clicar(*alvo)
        imagem, detalhes = _aguardar_dialogo(capturar,
            lambda img, d:_drive_selecionado(d, caminho.drive[0]))
    partes=caminho.parts[1:]
    # O print mostra perfil já aberto. Não presume Users como raiz visível.
    visiveis=[(i,_no(detalhes,n)) for i,n in enumerate(partes)]
    visiveis=[(i,n) for i,n in visiveis if n is not None]
    if not visiveis:raise SeletorPastaNaoConfirmado('Nenhum ancestral conhecido visível; revisão da árvore necessária.')
    indice,no=visiveis[-1]
    for seguinte in partes[indice+1:]:
        clicar(*no['posicao'])
        _aguardar_no_selecionado(capturar, partes[indice], caminho.drive[0])
        tecla('right')
        imagem, detalhes = _aguardar_dialogo(capturar,
            lambda img, d:_drive_selecionado(d,caminho.drive[0]) and
                _filho(d, partes[indice], seguinte) is not None)
        filho = _filho(detalhes, partes[indice], seguinte)
        if filho is None:raise SeletorPastaNaoConfirmado('Próxima pasta não confirmada como descendente.')
        indice+=1; no=filho
    clicar(*no['posicao'])
    imagem, detalhes = _aguardar_no_selecionado(capturar, caminho.name, caminho.drive[0])
    clicar(*detalhes['ok'])
    return True
