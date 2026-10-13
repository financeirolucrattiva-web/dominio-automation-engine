"""Lê caixas/datas por pixels e caixas OCR da captura atual; sem desktop.

Não usa os offsets antigos de 60/57 pixels. Geometria conservadora para
o formulário mostrado pelo operador; ambiguidade impede confirmação.
Ainda precisa do diagnóstico contra a captura real da instalação.
"""
import datetime as dt
import math
import re
import unicodedata

ROTULOS = {"registro_entradas": "Registro de Entradas",
           "registro_saidas": "Registro de Saídas", "registro_icms": "Registro de ICMS"}


def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold())
                   if not unicodedata.combining(c)).strip(' :')


def _palavras(dados, escala):
    return [{"texto": str(texto), "x": dados['left'][i]/escala, "y": dados['top'][i]/escala,
             "w": dados['width'][i]/escala, "h": dados['height'][i]/escala}
            for i, texto in enumerate(dados['text']) if str(texto).strip()]


def _mesma_linha(a, b):
    return max(a['y'], b['y']) < min(a['y']+a['h'], b['y']+b['h'])


def _rotulo(palavras, frase):
    tokens = [_normalizar(t) for t in frase.split()]
    achados = []
    for palavra in palavras:
        if _normalizar(palavra['texto']) != tokens[0]:
            continue
        linha = sorted((p for p in palavras if p['x'] >= palavra['x'] and _mesma_linha(p, palavra)), key=lambda p:p['x'])
        grupo = linha[:len(tokens)]
        if [_normalizar(p['texto']) for p in grupo] != tokens:
            continue
        x, y = min(p['x'] for p in grupo), min(p['y'] for p in grupo)
        achados.append({'x':x, 'y':y, 'w':max(p['x']+p['w'] for p in grupo)-x,
                        'h':max(p['y']+p['h'] for p in grupo)-y})
    if len(achados) != 1:
        raise ValueError(f'Rótulo ausente ou ambíguo: {frase}.')
    return achados[0]


def _iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    inter = max(0, min(ax+aw, bx+bw)-max(ax, bx))*max(0, min(ay+ah, by+bh)-max(ay, by))
    return inter/(aw*ah+bw*bh-inter)


def _quadrados(imagem, altura_texto):
    import cv2
    import numpy as np
    cinza = cv2.cvtColor(np.asarray(imagem.convert('RGB')), cv2.COLOR_RGB2GRAY)
    mascara = (cinza < 200).astype('uint8')*255
    contornos, _ = cv2.findContours(mascara, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidatos = []
    for c in contornos:
        x,y,w,h = cv2.boundingRect(c)
        vertices = cv2.approxPolyDP(c, .025*cv2.arcLength(c, True), True)
        if (len(vertices)==4 and .75 <= w/h <= 1.3 and cv2.contourArea(c)/(w*h) >= .65
                and .65*altura_texto <= min(w,h) and max(w,h) <= 2.3*altura_texto):
            candidatos.append((x,y,w,h))
    # Borda interna/externa da mesma caixa não são dois controles.
    caixas = []
    for c in sorted(candidatos, key=lambda c:c[2]*c[3], reverse=True):
        if not any(_iou(c, anterior) >= .45 for anterior in caixas):
            caixas.append(c)
    return caixas


def _estado(imagem, caixa):
    x,y,w,h = caixa
    margem = max(2,math.ceil(min(w,h)*.20))
    interno = imagem.crop((x+margem,y+margem,x+w-margem,y+h-margem)).convert('L')
    pixels = list(interno.tobytes())
    if not pixels:
        raise ValueError('Caixa sem área interna legível.')
    escuros = sum(p < 160 for p in pixels)/len(pixels)
    if min(pixels) >= 220:
        return False
    if .08 <= escuros <= .45 and max(pixels) >= 220:
        return True
    raise ValueError('Estado de caixa indeterminado; não considerar marcado/desmarcado.')


def _periodo(palavras):
    resultado = {}
    for papel, aliases in (('inicial', {'inicial','iniciat'}), ('final', {'final','finat'})):
        encontrados = []
        for rotulo in palavras:
            if _normalizar(rotulo['texto']) not in aliases:
                continue
            datas = [p for p in palavras if p['x'] > rotulo['x']+rotulo['w'] and _mesma_linha(p,rotulo)
                     and re.fullmatch(r'\d{2}/\d{2}/\d{4}',p['texto'])]
            if not datas:
                continue  # "Conforme período inicial" no rodapé não é campo de data.
            if len(datas) != 1:
                raise ValueError('Data ambígua ao lado do rótulo do período.')
            data = datas[0]
            dt.datetime.strptime(data['texto'],'%d/%m/%Y')
            encontrados.append({'valor':data['texto'],
                                'posicao':(int(data['x']+data['w']/2),int(data['y']+data['h']/2))})
        if len(encontrados) != 1:
            raise ValueError(f'Campo de data {papel} ausente ou ambíguo.')
        resultado[papel] = encontrados[0]
    if resultado['inicial']['posicao'] == resultado['final']['posicao']:
        raise ValueError('As datas não correspondem a dois campos distintos.')
    if dt.datetime.strptime(resultado['inicial']['valor'],'%d/%m/%Y') > dt.datetime.strptime(resultado['final']['valor'],'%d/%m/%Y'):
        raise ValueError('Período final anterior ao inicial.')
    return resultado


def ler_formulario(imagem, dados, escala=2, periodo_confirmado=None):
    palavras = _palavras(dados, escala)
    _rotulo(palavras, 'Livros Fiscais')
    rotulos = {tipo:_rotulo(palavras, frase) for tipo,frase in ROTULOS.items()}
    altura = max(r['h'] for r in rotulos.values())
    caixas = _quadrados(imagem, altura)
    livros = {}
    for tipo, rotulo in rotulos.items():
        candidatas = [c for c in caixas if c[0]+c[2] <= rotulo['x']
                      and rotulo['x']-(c[0]+c[2]) <= 2*altura
                      and rotulo['y']-altura/3 <= c[1]+c[3]/2 <= rotulo['y']+rotulo['h']+altura/3]
        if len(candidatas) != 1:
            raise ValueError(f'Não identifiquei uma única caixa de {ROTULOS[tipo]}.')
        x,y,w,h = candidatas[0]
        livros[tipo] = {'marcada':_estado(imagem,candidatas[0]),'retangulo':candidatas[0],
                        'posicao':(x+w//2,y+h//2)}
    referencia = livros['registro_entradas']['retangulo']
    if max(l['posicao'][0] for l in livros.values())-min(l['posicao'][0] for l in livros.values()) > referencia[2]:
        raise ValueError('As caixas dos três livros não estão alinhadas.')
    primeiro = _rotulo(palavras,'Termos de abertura e encerramento')
    ultimo = _rotulo(palavras,'Contra capa')
    grupo = [c for c in caixas if referencia[0]-referencia[2]/2 <= c[0] <= referencia[0]+3*referencia[2]
             and primeiro['y']-altura <= c[1]+c[3]/2 <= ultimo['y']+ultimo['h']+altura]
    # As duas capturas do formulário mostram 16 caixas em Emitir (inclui
    # a opção aninhada Relação de Emitentes). Versão diferente recusa leitura.
    if len(grupo) != 16 or any(l['retangulo'] not in grupo for l in livros.values()):
        raise ValueError(f'Identifiquei {len(grupo)} de 16 caixas do grupo Emitir; revisão visual necessária.')
    principais = {l['retangulo'] for l in livros.values()}
    outros = [{'retangulo':c,'marcada':_estado(imagem,c)} for c in grupo if c not in principais]
    periodo = _periodo(palavras) if periodo_confirmado is None else _validar_periodo_confirmado(periodo_confirmado)
    return {'livros':livros, 'periodo':periodo, 'outros':outros}


def _validar_periodo_confirmado(periodo):
    if not isinstance(periodo, dict) or set(periodo) != {'inicial', 'final'}:
        raise ValueError('Leitura do período incompleta.')
    resultado = {}
    for papel in ('inicial', 'final'):
        campo = periodo[papel]
        valor, posicao = campo['valor'], campo['posicao']
        if (not isinstance(valor, str) or not re.fullmatch(r'\d{2}/\d{2}/\d{4}',valor)
                or len(posicao) != 2 or any(type(p) is not int or p < 0 for p in posicao)):
            raise ValueError('Data ou posição não confirmada.')
        dt.datetime.strptime(valor,'%d/%m/%Y')
        resultado[papel] = {'valor':valor,'posicao':tuple(posicao)}
    if resultado['inicial']['posicao'][1] >= resultado['final']['posicao'][1]:
        raise ValueError('Ordem dos campos não confirmada.')
    return resultado


def marcar_tres_livros(ler, clicar):
    """Primitiva para futura integração: só altera caixas conhecidas.

    O chamador deve impor foco/empresa/trava antes de qualquer ação. Não
    clica OK nem emite. Não aceita outros relatórios selecionados.
    """
    def conferir():
        atual = ler()
        if (set(atual['livros']) != set(ROTULOS)
                or any(type(c['marcada']) is not bool for c in [*atual['livros'].values(),*atual['outros']])):
            raise ValueError('Estado de seleção incompleto ou indeterminado.')
        return atual
    for tipo in ROTULOS:
        atual = conferir()
        if any(c['marcada'] for c in atual['outros']):
            raise ValueError('Há outros relatórios selecionados no grupo Emitir.')
        campo = atual['livros'][tipo]
        if not campo['marcada']:
            clicar(*campo['posicao'])
            depois = conferir()
            if not depois['livros'][tipo]['marcada']:
                raise ValueError('Marcação do livro não confirmada; não emitir.')
    final = conferir()
    if not all(l['marcada'] for l in final['livros'].values()) or any(c['marcada'] for c in final['outros']):
        raise ValueError('Seleção final dos três livros não confirmada.')
    return final


def ler_com_ocr(imagem, periodo_confirmado=None):
    """Mesma leitura local usada pelo atalho e pelo diagnóstico no servidor."""
    from app import tela
    ultimo = None
    for escala in (2, 4):
        try:
            return ler_formulario(imagem, tela._ler_dados_ocr(imagem, escala), escala, periodo_confirmado)
        except ValueError as erro:
            ultimo = erro
    dados = tela.ler_dados_ocr_windows(imagem, 2)
    if dados is not None:
        return ler_formulario(imagem, dados, 2, periodo_confirmado)
    raise ultimo


def resumo_diagnostico(resultado):
    """Somente estados, datas e medidas; nunca texto OCR/captura/caminho."""
    if set(resultado['livros']) != set(ROTULOS):
        raise ValueError('Leitura dos três livros incompleta.')
    livros = {}
    for tipo in ROTULOS:
        livro = resultado['livros'][tipo]
        caixa = livro['retangulo']
        if (type(livro['marcada']) is not bool or len(caixa) != 4
                or any(type(c) is not int or c < 0 for c in caixa)
                or caixa[2] == 0 or caixa[3] == 0):
            raise ValueError('Estado ou caixa do livro inválido.')
        livros[tipo] = {'marcada': livro['marcada'], 'retangulo': list(caixa)}
    periodo = {papel: resultado['periodo'][papel]['valor'] for papel in ('inicial', 'final')}
    for valor in periodo.values():
        if not isinstance(valor, str) or not re.fullmatch(r'\d{2}/\d{2}/\d{4}', valor):
            raise ValueError('Data não confirmada.')
        dt.datetime.strptime(valor, '%d/%m/%Y')
    if dt.datetime.strptime(periodo['inicial'], '%d/%m/%Y') > dt.datetime.strptime(periodo['final'], '%d/%m/%Y'):
        raise ValueError('Período invertido.')
    outros = resultado['outros']
    if len(outros) != 13 or any(type(c['marcada']) is not bool for c in outros):
        raise ValueError('Outras opções não confirmadas.')
    return {'livros': livros, 'periodo': periodo,
            'outras_opcoes_marcadas': sum(c['marcada'] for c in outros),
            'emissao_realizada': False}
