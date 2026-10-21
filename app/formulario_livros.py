"""Lê caixas/datas por pixels e caixas OCR da captura atual; sem desktop.

Não usa os offsets antigos de 60/57 pixels. Geometria conservadora para
o formulário mostrado pelo operador; ambiguidade impede confirmação.
Ainda precisa do diagnóstico contra a captura real da instalação.
"""
import datetime as dt
import math
import re
import unicodedata
import time
from app.controle_execucao import ponto_seguro

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
    candidatos = []
    # Um único limiar perde bordas 3D com lados claros. Duas máscaras
    # preservam também esses lados; só reforçam localização, nunca marcação.
    # Não fecha artificialmente traços nem completa uma caixa cortada.
    mascaras = [(cinza < limite).astype('uint8')*255 for limite in (200,230)]
    for mascara in mascaras:
        contornos, _ = cv2.findContours(mascara, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
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
    # Medido na captura real (15/10/2026): o "✓" marcado ocupa ~47% do interior
    # 6x6 e as caixas vazias dão 0%. O limite antigo (45%) recusava a marcada.
    if .08 <= escuros <= .60 and max(pixels) >= 220:
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


def ler_selecao(imagem, dados, escala=2, registrar=None, rotulos_prontos=None):
    """Confere apenas Emitir, sem depender de datas reconhecidas.

    A imagem original fornece bordas e marcas. Dados de OCR podem vir de
    uma cópia preparada, mas suas coordenadas devem conservar a geometria.
    `rotulos_prontos`: rótulos já combinados de várias leituras da mesma
    captura (`combinar_rotulos`); `dados` pode ser None nesse caso.
    O retorno nunca autoriza OK: o período precisa ser conferido à parte.
    """
    palavras = _palavras(dados, escala) if dados is not None else []
    diagnostico = {'fase':'selecao', 'confirmado':False, 'rotulos':{},
                  'caixas_detectadas':None, 'caixas_emitir':None, 'livros':{}}
    try:
        return _ler_selecao(imagem, palavras, diagnostico, rotulos_prontos)
    finally:
        if registrar:
            registrar(diagnostico)


FRASES_SELECAO = {'titulo':'Livros Fiscais', **ROTULOS,
                  'primeira_opcao':'Termos de abertura e encerramento',
                  'ultima_opcao':'Contra capa'}
ORDEM_VERTICAL = ('titulo', 'primeira_opcao', 'registro_entradas', 'registro_saidas',
                  'registro_icms', 'ultima_opcao')


def _rotulos_da_leitura(palavras):
    """Rótulos reconhecidos de UMA leitura de OCR (os não reconhecidos faltam)."""
    rotulos = {}
    for chave, frase in FRASES_SELECAO.items():
        try:
            rotulos[chave] = _rotulo(palavras, frase)
        except ValueError:
            pass
    return rotulos


def combinar_rotulos(leituras, tolerancia=3):
    """Une rótulos de várias leituras de OCR da MESMA captura.

    Cada leitura de OCR perde rótulos diferentes (negrito, grupo Anexar). Um
    rótulo só entra se todas as leituras que o acharam concordam na posição
    (±tolerância px); discordância o descarta. Devolve None se algum rótulo
    faltar, ou se a ordem vertical/alinhamento forem incoerentes.
    """
    combinados = {}
    for chave in FRASES_SELECAO:
        caixas = [leitura[chave] for leitura in leituras if chave in leitura]
        if not caixas:
            return None
        base = caixas[0]
        if any(abs(c['x']-base['x']) > tolerancia or abs(c['y']-base['y']) > tolerancia for c in caixas):
            return None
        combinados[chave] = base
    ys = [combinados[chave]['y'] for chave in ORDEM_VERTICAL]
    xs = [combinados[chave]['x'] for chave in ORDEM_VERTICAL[1:]]
    if any(b <= a for a, b in zip(ys, ys[1:])) or max(xs)-min(xs) > 8:
        return None
    return combinados


def _ler_selecao(imagem, palavras, diagnostico, rotulos_prontos=None):
    frases = FRASES_SELECAO
    rotulos = {}
    lidos = rotulos_prontos if rotulos_prontos is not None else _rotulos_da_leitura(palavras)
    for chave in frases:
        rotulo = lidos.get(chave)
        if rotulo is not None:
            rotulos[chave] = rotulo
            diagnostico['rotulos'][chave] = {'reconhecido':True,
                'caixa':[rotulo[k] for k in ('x','y','w','h')]}
        else:
            diagnostico['rotulos'][chave] = {'reconhecido':False}
    if len(rotulos) != len(frases):
        diagnostico['motivo'] = 'rotulos_selecao_nao_confirmados'
        raise ValueError('Rótulos da seleção ausentes ou ambíguos.')
    rotulos_livros = {tipo:rotulos[tipo] for tipo in ROTULOS}
    # Mediana, não máximo: o rótulo marcado/focado ("Registro de Entradas") vem
    # com ~21 px (retângulo de foco pontilhado) contra ~11 px dos demais, e o
    # máximo descartava os quadradinhos reais (13 px) como "pequenos demais".
    alturas = sorted(rotulos[c]['h'] for c in ('registro_entradas', 'registro_saidas', 'registro_icms',
                                                'primeira_opcao', 'ultima_opcao'))
    altura = alturas[len(alturas)//2]
    caixas = _quadrados(imagem, altura)
    diagnostico['caixas_detectadas'] = len(caixas)
    livros = {}
    for tipo, rotulo in rotulos_livros.items():
        candidatas = [c for c in caixas if c[0]+c[2] <= rotulo['x']
                      and rotulo['x']-(c[0]+c[2]) <= 2*altura
                      and rotulo['y']-altura/3 <= c[1]+c[3]/2 <= rotulo['y']+rotulo['h']+altura/3]
        diagnostico['livros'][tipo] = {'candidatas':len(candidatas), 'marcada':None}
        if len(candidatas) != 1:
            diagnostico['motivo'] = 'caixa_livro_nao_confirmada'
            raise ValueError(f'Não identifiquei uma única caixa de {ROTULOS[tipo]}.')
        x,y,w,h = candidatas[0]
        diagnostico['livros'][tipo]['retangulo'] = list(candidatas[0])
        try:
            estado = _estado(imagem,candidatas[0])
        except ValueError:
            diagnostico['motivo'] = 'estado_livro_nao_confirmado'
            raise
        diagnostico['livros'][tipo]['marcada'] = estado
        livros[tipo] = {'marcada':estado,'retangulo':candidatas[0],
                        'posicao':(x+w//2,y+h//2)}
    referencia = livros['registro_entradas']['retangulo']
    if max(l['posicao'][0] for l in livros.values())-min(l['posicao'][0] for l in livros.values()) > referencia[2]:
        diagnostico['motivo'] = 'alinhamento_livros_nao_confirmado'
        raise ValueError('As caixas dos três livros não estão alinhadas.')
    primeiro, ultimo = rotulos['primeira_opcao'], rotulos['ultima_opcao']
    grupo = [c for c in caixas if referencia[0]-referencia[2]/2 <= c[0] <= referencia[0]+3*referencia[2]
             and primeiro['y']-altura <= c[1]+c[3]/2 <= ultimo['y']+ultimo['h']+altura]
    # As duas capturas do formulário mostram 16 caixas em Emitir (inclui
    # a opção aninhada Relação de Emitentes). Versão diferente recusa leitura.
    diagnostico['caixas_emitir'] = len(grupo)
    if len(grupo) != 16 or any(l['retangulo'] not in grupo for l in livros.values()):
        diagnostico['motivo'] = 'grupo_emitir_incompleto'
        raise ValueError(f'Identifiquei {len(grupo)} de 16 caixas do grupo Emitir; revisão visual necessária.')
    principais = {l['retangulo'] for l in livros.values()}
    try:
        outros = [{'retangulo':c,'marcada':_estado(imagem,c)} for c in grupo if c not in principais]
    except ValueError:
        diagnostico['motivo'] = 'outras_opcoes_nao_confirmadas'
        raise
    diagnostico['outras_opcoes_marcadas'] = sum(c['marcada'] for c in outros)
    diagnostico['confirmado'] = True
    return {'livros':livros, 'outros':outros, 'altura':altura}


def reler_por_pixels(imagem, referencia, tolerancia=1):
    """Relê o estado das 16 caixas JÁ CONHECIDAS (de uma leitura completa), sem OCR.

    Depois de clicar numa caixa o rótulo fica em negrito e com retângulo de foco e
    nenhum motor de OCR o reconhece de forma confiável; as caixas, porém, não saem
    do lugar. Exige encontrar TODAS as 16 caixas nas mesmas posições (±tolerância)
    e estado legível em cada uma; qualquer ausência (janela diferente, diálogo por
    cima) recusa e o chamador volta à leitura completa por OCR.
    """
    caixas = _quadrados(imagem, referencia['altura'])

    def achar(retangulo):
        for c in caixas:
            if all(abs(a-b) <= tolerancia for a, b in zip(c, retangulo)):
                return c
        raise ValueError('Caixa conhecida não encontrada na captura; leitura por pixels recusada.')

    livros = {}
    for tipo, antigo in referencia['livros'].items():
        c = achar(antigo['retangulo'])
        livros[tipo] = {'marcada':_estado(imagem, c), 'retangulo':c, 'posicao':antigo['posicao']}
    outros = []
    for antigo in referencia['outros']:
        c = achar(antigo['retangulo'])
        outros.append({'retangulo':c, 'marcada':_estado(imagem, c)})
    return {'livros':livros, 'outros':outros, 'altura':referencia['altura']}


def ler_formulario(imagem, dados, escala=2, periodo_confirmado=None):
    selecao = ler_selecao(imagem, dados, escala)
    palavras = _palavras(dados, escala)
    periodo = _periodo(palavras) if periodo_confirmado is None else _validar_periodo_confirmado(periodo_confirmado)
    return {**selecao, 'periodo':periodo}


def ler_selecao_com_ocr(imagem, registrar=None):
    """Varia a leitura dos rótulos sem transformar os pixels das caixas."""
    from app import tela
    ultimo = None
    lidos = []
    tentativas = [('tesseract',2,'padrao'), ('tesseract',4,'padrao'),
                  ('tesseract',4,'cinza'), ('tesseract',4,'binaria'),
                  ('tesseract',6,'binaria'), ('windows',2,'padrao'),
                  ('windows',4,'padrao')]
    from app.tela import pre_aquecer_ocr, reutilizar_ocr  # módulo real, não o patch dos testes
    with reutilizar_ocr():
        # Com o formulário ainda não pintado, as 7 leituras rodavam uma atrás da outra (~15 s por
        # tentativa); em paralelo o tempo é o da mais lenta e as decisões continuam as mesmas.
        pre_aquecer_ocr((imagem, [
            ('windows' if m == 'windows' else 'tesseract', e) if p == 'padrao' or m == 'windows'
            else ('formulario', e, p, 6) for m, e, p in tentativas]))
        return _ler_selecao_sequencial(imagem, registrar, tentativas, tela)


def _ler_selecao_sequencial(imagem, registrar, tentativas, tela):
    ultimo = None
    lidos = []
    for motor, escala, preparo in tentativas:
        contexto = {'motor':motor, 'escala':escala, 'preparo':preparo}
        def registrar_tentativa(diagnostico):
            if registrar:
                registrar({**contexto, **diagnostico})
        try:
            if motor == 'windows':
                dados = tela.ler_dados_ocr_windows(imagem, escala)
            elif preparo == 'padrao':
                dados = tela._ler_dados_ocr(imagem, escala)
            else:
                dados = tela.ler_dados_ocr_formulario(imagem, escala=escala,
                                                    preparo=preparo, psm=6)
            if dados is None:
                registrar_tentativa({'fase':'ocr', 'confirmado':False,
                                     'motivo':'motor_selecao_indisponivel'})
                continue
            try:
                return ler_selecao(imagem, dados, escala, registrar_tentativa)
            except ValueError:
                # Esta leitura perdeu rótulos; guarda os que reconheceu e tenta
                # combiná-los com os das outras leituras da MESMA captura.
                lidos.append(_rotulos_da_leitura(_palavras(dados, escala)))
                combinados = combinar_rotulos(lidos)
                if combinados is not None:
                    contexto = {'motor':'combinado', 'escala':escala, 'preparo':'rotulos_unidos'}
                    return ler_selecao(imagem, None, escala, registrar_tentativa, rotulos_prontos=combinados)
                raise
        except ValueError as erro:
            ultimo = erro
        except Exception:
            registrar_tentativa({'fase':'ocr', 'confirmado':False,
                                 'motivo':'motor_selecao_indisponivel'})
    raise ultimo or ValueError('Seleção dos livros não confirmada pelos motores locais.')


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


def marcar_tres_livros(ler, clicar, tentativas=5, intervalo=.3, ler_rapido=None):
    """Só altera caixas conhecidas, com releitura antes e após cada ação.

    O chamador deve impor foco/empresa/trava antes de qualquer ação. Não
    clica OK nem emite. Não aceita outros relatórios selecionados.
    """
    if type(tentativas) is not int or tentativas < 1 or intervalo < 0:
        raise ValueError('Espera de seleção inválida.')
    confirmados = set()
    referencia = None  # primeira leitura completa (com OCR) que confirmou o formulário

    def conferir():
        nonlocal referencia
        atual = None
        if ler_rapido is not None and referencia is not None:
            try:
                atual = ler_rapido(referencia)  # só pixels das caixas conhecidas, sem OCR
            except ValueError:
                atual = None
        if atual is None:
            atual = ler()
        if (set(atual['livros']) != set(ROTULOS)
                or len(atual['outros']) != 13
                or any(type(c['marcada']) is not bool for c in [*atual['livros'].values(),*atual['outros']])):
            raise ValueError('Estado de seleção incompleto ou indeterminado.')
        posicoes = [c['posicao'] for c in atual['livros'].values()]
        if (any(not isinstance(p, (tuple, list)) or len(p) != 2
                or any(type(v) is not int or v < 0 for v in p) for p in posicoes)
                or len({tuple(p) for p in posicoes}) != 3):
            raise ValueError('Posições de seleção incompletas ou indeterminadas.')
        if 'altura' in atual and referencia is None:
            referencia = atual
        return atual

    def aguardar(campo=None):
        ultimo = None
        for tentativa in range(tentativas):
            ponto_seguro()
            try:
                atual = conferir()
            except ValueError as erro:
                ultimo = erro
                atual = None
            if atual is not None:
                if any(c['marcada'] for c in atual['outros']):
                    raise ValueError('Há outros relatórios selecionados no grupo Emitir; não emitir.')
                # Não clicar novamente em um livro que já confirmou: uma
                # pintura/OCR transitórios podem ocultar uma marca já enviada.
                if (all(atual['livros'][tipo]['marcada'] for tipo in confirmados)
                        and (campo is None or atual['livros'][campo]['marcada'])):
                    return atual
                ultimo = ValueError('Marcação do livro não confirmada; não emitir.')
            print(f'LIVROS_MARCACAO campo={campo or "selecao"} tentativa={tentativa+1} confirmado=False',flush=True)
            if tentativa < tentativas-1:
                time.sleep(intervalo)
        raise ultimo or ValueError('Seleção dos livros não confirmada; não emitir.')

    for tipo in ROTULOS:
        atual = aguardar()
        confirmados.update(t for t, c in atual['livros'].items() if c['marcada'])
        campo = atual['livros'][tipo]
        if not campo['marcada']:
            clicar(*campo['posicao'])
            aguardar(tipo)
        confirmados.add(tipo)
    final = aguardar()
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
