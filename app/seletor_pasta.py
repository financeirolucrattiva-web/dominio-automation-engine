"""Seletor nativo Procurar Pasta: somente alvos OCR e bordas da captura.

A árvore observada não tem campo para colar caminho. Navega por nomes
locais conhecidos e exige a folha exclusiva selecionada antes de OK.
"""
from pathlib import PureWindowsPath
import re
import time
import unicodedata
import json
from app.controle_execucao import ExecucaoInterrompida, ponto_seguro


class SeletorPastaNaoConfirmado(ValueError):
    """Mensagens fechadas, sem nomes de empresa, caminhos ou OCR livre."""


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto).casefold())
    return ''.join(c for c in texto if not unicodedata.combining(c)).strip()


def _palavras(imagem):
    from app import tela
    from app.leitura_resumo import normalizar_selecao
    dados = tela._ler_dados_ocr(normalizar_selecao(imagem), 4)
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
    try:cancelar = _rotulo(palavras, 'Cancelar')
    except ValueError:cancelar = None
    try:
        ok = _rotulo(palavras, 'OK')
    except ValueError:
        ok = None  # a confirmação final exige OK, mas a navegação não
    if not (titulo['y'] < unidade['y']):
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
    arvore=unica([c for c in caixas if combo[1]+combo[3]<c[1]<combo[1]+combo[3]+4*altura
                   and c[2]>12*altura and c[3]>5*altura and c[0]<combo[0]
                   and abs(c[0]+c[2]-combo[0]-combo[2])<=2*altura])
    ok_valido = (ok is not None and cancelar is not None and abs(ok['y']-cancelar['y']) < 2*ok['h']
                 and arvore[0]<ok['x']<cancelar['x'] and arvore[1]+arvore[3]<ok['y']<arvore[1]+arvore[3]+6*altura)
    botoes = [c for c in caixas if c[1]>arvore[1]+arvore[3] and c[0]>=arvore[0]
              and c[0]+c[2]<=arvore[0]+arvore[2] and 4*altura<c[2]<14*altura
              and altura<c[3]<4*altura and c[1]<arvore[1]+arvore[3]+6*altura]
    palavras=_refinar_unidade(imagem,palavras,combo)
    return {'combo':combo,'arvore':arvore,'palavras':palavras,
            'botoes_ok':botoes,
            'ok':(round(ok['x']+ok['w']/2),round(ok['y']+ok['h']/2)) if ok_valido else None}


def _drive(palavras, letra):
    achados=[]
    for linha in _linhas(palavras):
        texto=_normalizar(' '.join(p['texto'] for p in linha))
        # "Client C (M:\)": o OCR lê a barra invertida como \, /, | ou a omite; a
        # linha "Client Z \\server\... (Z:\)" e "Servidor (C:\)" não casam.
        if re.search(r'client\s*c\s*\(\s*'+re.escape(letra.casefold())+r'\s*[:;.]\s*[\\/|!]?\s*\)',texto):
            achados.append(_posicao(linha))
    if len(achados)>1:raise SeletorPastaNaoConfirmado('Unidade Client C ambígua.')
    return achados[0] if achados else None


def _refinar_unidade(imagem,palavras,combo):
    """Relê o campo medido quando a tela inteira omite a unidade ou sua letra."""
    x,y,w,h=combo
    dentro=[p for p in palavras if x<p['x']<x+w and y<p['y']<y+h]
    texto=_normalizar(' '.join(p['texto'] for p in dentro))
    if re.search(r'\bservidor\b|\bclient\s+[a-bd-z]\b',texto):return palavras
    letras='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if any(_drive(dentro,l) is not None for l in letras):return palavras
    from app import tela
    from app.leitura_resumo import normalizar_selecao
    area=(x+2,y+2,x+w-h,y+h-2)  # interior, excluindo borda e botão da seta
    leituras=[]
    recorte=normalizar_selecao(imagem.crop(area))
    for escala,preparo in ((4,'cinza'),(4,'binaria'),(6,'cinza'),(6,'binaria')):
        ponto_seguro()
        try:
            dados=tela.ler_dados_ocr_linha_rotulo(recorte,escala=escala,preparo=preparo)
            ps=[{'texto':t,'x':area[0]+dados['left'][i]/escala,'y':area[1]+dados['top'][i]/escala,
                 'w':dados['width'][i]/escala,'h':dados['height'][i]/escala}
                for i,t in enumerate(dados['text']) if str(t).strip()]
            unidades=[l for l in letras if _drive(ps,l) is not None]
        except ExecucaoInterrompida:raise
        except (RuntimeError,OSError,ValueError,KeyError,TypeError,IndexError):continue
        if len(unidades)==1:leituras.append((unidades[0],ps))
    if len(leituras)>=2 and len({letra for letra,_ in leituras})==1:
        return [p for p in palavras if p not in dentro]+leituras[0][1]
    return palavras


def _selecionado(imagem, no):
    import cv2
    import numpy as np
    p=no['linha']; x=int(min(a['x'] for a in p)); y=int(min(a['y'] for a in p))
    direito=int(max(a['x']+a['w'] for a in p)); baixo=int(max(a['y']+a['h'] for a in p))
    recorte=np.array(imagem.crop((x,y,direito,baixo)).convert('RGB'))
    if not recorte.size:return False
    hsv=cv2.cvtColor(recorte,cv2.COLOR_RGB2HSV)
    return float(((hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>100)&(hsv[:,:,2]>70)).mean())>.25


class _LeitorDialogo:
    """Cache só desta espera; pixels iguais dispensam repetir OCR/contornos."""
    def __init__(self):
        self.assinatura=None
        self.detalhes=None

    def ler(self,imagem):
        assinatura=(imagem.mode,imagem.size,imagem.tobytes())
        if assinatura!=self.assinatura:
            self.assinatura=assinatura
            self.detalhes=None
            self.detalhes=medir_dialogo(imagem)
        if self.detalhes is None:
            raise SeletorPastaNaoConfirmado('Diálogo não reconhecido nesta captura.')
        return self.detalhes


def _aguardar_dialogo(capturar, confirmar=None, tentativas=6, fase='medir_dialogo',estavel=False):
    """Relê a captura após cada ação; nunca repete o clique por atraso."""
    assinatura_anterior=None
    leitor=_LeitorDialogo()
    for tentativa in range(tentativas):
        ponto_seguro()
        imagem = capturar()
        try:
            detalhes = leitor.ler(imagem)
            if confirmar is None or confirmar(imagem, detalhes):
                if not estavel:return imagem, detalhes
                x,y,w,h=detalhes['arvore']
                assinatura=(x,y,w,h,imagem.crop((x,y,x+w,y+h)).tobytes())
                if assinatura==assinatura_anterior:return imagem,detalhes
                assinatura_anterior=assinatura
            else:assinatura_anterior=None
        except ValueError:
            assinatura_anterior=None
        if tentativa < tentativas-1:
            time.sleep(.3)
    print('PASTA_NAVEGACAO '+json.dumps({'fase':fase,'confirmado':False}),flush=True)
    raise SeletorPastaNaoConfirmado('Seletor de pasta não confirmou o estado esperado ('+fase+'); não foi enviado OK.')


def _drive_selecionado(detalhes, letra):
    x,y,w,h = detalhes['combo']
    palavras = [p for p in detalhes['palavras'] if x<p['x']<x+w and y<p['y']<y+h]
    return _drive(palavras, letra) is not None


def _assinatura_unidade(imagem, detalhes):
    x,y,w,h=detalhes['combo']
    # OCR pode tokenizar o mesmo rótulo de outra forma sem mudança visual.
    return ((x,y,w,h), imagem.crop((x,y,x+w,y+h)).tobytes())


def _aguardar_unidade(capturar, diferente=None):
    """Espera o combo fechado estabilizar; atraso nunca repete Down."""
    anterior=None
    leitor=_LeitorDialogo()
    for tentativa in range(8):
        ponto_seguro()
        imagem=capturar()
        try:
            detalhes=leitor.ler(imagem)
            assinatura=_assinatura_unidade(imagem,detalhes)
            x,y,w,h=detalhes['arvore']
            estado=(assinatura,imagem.crop((x,y,x+w,y+h)).tobytes())
            if assinatura!=diferente:
                if estado==anterior:return imagem,detalhes
                anterior=estado
            else:anterior=None
        except ValueError:
            anterior=None
        if tentativa<7:time.sleep(.3)
    print('PASTA_NAVEGACAO '+json.dumps({'fase':'unidade_estavel','confirmado':False}),flush=True)
    raise SeletorPastaNaoConfirmado('A seleção da unidade não mudou ou não estabilizou; não foi enviado OK.')


def _selecionar_unidade(capturar,clicar,tecla,letra,imagem,detalhes):
    """Home/Down escolhem a unidade; Tab aplica sem acionar o OK do diálogo.

    Não depende de OCR das opções da lista aberta. A identidade Client C e
    a letra configurada são conferidas no campo atual antes de usar a árvore.
    """
    if _drive_selecionado(detalhes,letra):return imagem,detalhes
    visitadas=set()
    for passo in range(40):
        ponto_seguro()
        assinatura=_assinatura_unidade(imagem,detalhes)
        x,y,w,h=detalhes['combo']
        clicar(x+w-h//2,y+h//2)  # seta dentro da borda medida do combo
        ponto_seguro()
        tecla('home' if passo==0 else 'down')
        ponto_seguro()
        tecla('tab')  # fecha/aplica a lista, sem Enter nem OK implícito
        imagem,detalhes=_aguardar_unidade(capturar,None if passo==0 else assinatura)
        confirmado=_drive_selecionado(detalhes,letra)
        print('PASTA_NAVEGACAO '+json.dumps({'fase':'unidade_client_c',
              'passo':passo,'confirmado':confirmado}),flush=True)
        if confirmado:return imagem,detalhes
        atual=_assinatura_unidade(imagem,detalhes)
        if atual in visitadas:break
        visitadas.add(atual)
    raise SeletorPastaNaoConfirmado('Unidade Client C configurada não confirmada; não foi enviado OK.')


def _nos(detalhes):
    x,y,w,h = detalhes['arvore']
    palavras = [p for p in detalhes['palavras']
                if x<p['x'] and p['x']+p['w']<x+w and y<p['y'] and p['y']+p['h']<y+h]
    return [{'posicao':_posicao(linha), 'x':min(p['x'] for p in linha),
             'y':min(p['y'] for p in linha), 'linha':linha,
             'nome':_normalizar(' '.join(p['texto'] for p in linha))}
            for linha in _linhas(palavras)]


def _no_selecionado(imagem, detalhes):
    selecionados=[]
    for no in _nos(detalhes):
        # Ícone +/- à esquerda não faz parte do nome selecionado na árvore.
        linha=[p for p in no['linha'] if _selecionado(imagem, {'linha':[p]})]
        if not linha:continue
        selecionados.append({'posicao':_posicao(linha), 'x':min(p['x'] for p in linha),
                             'y':min(p['y'] for p in linha), 'linha':linha,
                             'nome':_normalizar(' '.join(p['texto'] for p in linha))})
    if len(selecionados)==1:return selecionados[0]
    if len(selecionados)>1:return None
    if '_selecao_por_recorte' in detalhes:return detalhes['_selecao_por_recorte']
    detalhes['_selecao_por_recorte']=None
    import cv2
    import numpy as np
    from app import tela
    from app.leitura_resumo import normalizar_selecao
    x,y,w,h=detalhes['arvore']
    hsv=cv2.cvtColor(np.array(imagem.crop((x,y,x+w,y+h)).convert('RGB')),cv2.COLOR_RGB2HSV)
    azul=((hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>100)&(hsv[:,:,2]>70)).astype('uint8')*255
    contornos,_=cv2.findContours(azul,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    caixas=[]
    for contorno in contornos:
        bx,by,bw,bh=cv2.boundingRect(contorno)
        if 3<=bh<h/4 and bw>.75*bh and cv2.contourArea(contorno)/(bw*bh)>.4:
            caixas.append((bx,by,bw,bh))
    if len(caixas)!=1:return None
    bx,by,bw,bh=caixas[0]
    area=(x+bx,y+by,x+bx+bw,y+by+bh)
    from PIL import ImageOps
    margem=4
    recorte=ImageOps.expand(normalizar_selecao(imagem.crop(area)),border=margem,fill='white')
    leituras=[]
    for preparo in ('cinza','binaria'):
        ponto_seguro()
        dados=tela.ler_dados_ocr_linha_rotulo(recorte,escala=4,preparo=preparo)
        linha=[{'texto':str(t),'x':area[0]+dados['left'][i]/4-margem,'y':area[1]+dados['top'][i]/4-margem,
                'w':dados['width'][i]/4,'h':dados['height'][i]/4}
               for i,t in enumerate(dados['text']) if str(t).strip()]
        if linha and all(area[0]<=p['x']<p['x']+p['w']<=area[2]
                         and area[1]<=p['y']<p['y']+p['h']<=area[3] for p in linha):
            leituras.append(linha)
    if len(leituras)!=2:return None
    nomes=[_normalizar(' '.join(p['texto'] for p in linha)) for linha in leituras]
    if nomes[0]!=nomes[1]:return None
    linha=leituras[0]
    no={'posicao':_posicao(linha),'x':min(p['x'] for p in linha),'y':min(p['y'] for p in linha),
        'linha':linha,'nome':nomes[0]}
    detalhes['_selecao_por_recorte']=no
    return no


def _mesmo_no(a,b):
    return a is not None and b is not None and a['nome']==b['nome'] and abs(a['x']-b['x'])<=2


def _ler_selecao(capturar, letra, fase, diferente=None,estavel=False):
    ultima={}
    def confirmar(img,d):
        no=_no_selecionado(img,d)
        ultima.update(unidade_confirmada=_drive_selecionado(d,letra),selecao_lida=no is not None,
                      selecao_mudou=no is not None and (diferente is None or not _mesmo_no(no,diferente)))
        return all(ultima.values())
    try:img,d=_aguardar_dialogo(capturar,confirmar,fase=fase,estavel=estavel)
    except SeletorPastaNaoConfirmado:
        print('PASTA_NAVEGACAO '+json.dumps({'fase':'leitura_selecao','origem':fase,**ultima}),flush=True)
        raise
    return img,d,_no_selecionado(img,d)


def _avancar_irmao(capturar, tecla, letra, no):
    """Down atravessa ramo aberto: volta à sua raiz, fecha e só então avança."""
    tecla('down')
    img,d,atual=_ler_selecao(capturar,letra,'proximo_no',diferente=no)
    if atual['x']<=no['x']+2:
        return img,d,atual
    # Down entrou num ramo que estava aberto. Left pode fechar o descendente
    # ou selecionar o pai; cada resultado é relido antes da próxima tecla.
    for _ in range(32):
        tecla('left')
        img,d,atual=_ler_selecao(capturar,letra,'voltar_do_ramo',estavel=True)
        if _mesmo_no(atual,no):break
        if atual['x']<no['x']-2:
            raise SeletorPastaNaoConfirmado('A árvore saiu do ramo esperado; não foi enviado OK.')
    else:
        raise SeletorPastaNaoConfirmado('Limite ao retornar do ramo; não foi enviado OK.')
    tecla('left')  # ramo comprovadamente aberto, agora selecionado: fecha
    img,d,atual=_ler_selecao(capturar,letra,'fechar_ramo',estavel=True)
    if not _mesmo_no(atual,no):
        raise SeletorPastaNaoConfirmado('O ramo não permaneceu selecionado; não foi enviado OK.')
    tecla('down')
    return _ler_selecao(capturar,letra,'proximo_irmao',diferente=no)


def _alvo_visivel(detalhes,no,nome):
    """Nome literal abaixo do atual e antes de sair do ramo comprovado."""
    candidatos=[]
    for linha in _nos(detalhes):
        palavras=list(linha['linha'])
        while palavras and _normalizar(palavras[0]['texto']) in ('+','-'):
            palavras.pop(0)  # glyph isolado não faz parte do nome
        if not palavras:continue
        x=min(p['x'] for p in palavras)
        if linha['y']<no['y']-2:continue
        if x<no['x']-2:break  # voltou a ancestral: o resto pertence a outro ramo
        if (abs(x-no['x'])<=2
                and _normalizar(' '.join(p['texto'] for p in palavras))==_normalizar(nome)):
            candidatos.append({'posicao':_posicao(palavras),'x':x,'y':linha['y'],
                               'linha':palavras,'nome':_normalizar(nome)})
    if len(candidatos)>1:
        raise SeletorPastaNaoConfirmado('Pasta visível ambígua no ramo; não foi enviado OK.')
    return candidatos[0] if candidatos else None


def _selecionar_visivel(capturar,clicar,letra,estado,nome,nivel):
    img,d,no=estado
    if _alvo_visivel(d,no,nome) is None:return None
    # Não reutiliza coordenada de captura anterior após mudanças/atrasos.
    img,d=_aguardar_dialogo(capturar,lambda img,d:
        _drive_selecionado(d,letra) and _mesmo_no(_no_selecionado(img,d),no),
        fase='reler_alvo_visivel')
    alvo=_alvo_visivel(d,no,nome)
    if alvo is None:return None
    ponto_seguro()
    print('PASTA_NAVEGACAO '+json.dumps({'fase':'clicar_pasta_visivel',
          'nivel':nivel,'posicao':list(alvo['posicao'])}),flush=True)
    clicar(*alvo['posicao'])
    img,d,selecionado=_ler_selecao(capturar,letra,'selecionar_pasta_visivel',estavel=True)
    if not _mesmo_no(selecionado,alvo):
        raise SeletorPastaNaoConfirmado('Clique não confirmou a pasta visível esperada; não foi enviado OK.')
    return img,d,selecionado


def _recuperar_raiz_sem_avanco(capturar,clicar,letra,estado,nome,max_rolagens=8):
    """Só a raiz comprovada admite recorte local e seta física de rolagem.

    Não amplia a hierarquia dos descendentes e não segura o mouse às cegas.
    Cada clique exige mudança/estabilidade antes de procurar ou clicar de novo.
    """
    from app.arvore_raiz import localizar_raiz, medir_seta_baixo
    anterior=estado[2]
    altura=max(p['h'] for p in anterior['linha'])
    img,d=_aguardar_dialogo(capturar,lambda img,d:
        _drive_selecionado(d,letra) and _mesmo_no(_no_selecionado(img,d),anterior),
        fase='raiz_sem_avanco',estavel=True)
    coluna=anterior['x']
    for passo in range(max_rolagens+1):
        ponto_seguro()
        if not _drive_selecionado(d,letra):
            raise SeletorPastaNaoConfirmado('Unidade mudou durante a busca da raiz; não foi enviado OK.')
        if any(_normalizar(p['texto']).strip(':') in ('aviso','atencao') for p in d['palavras']):
            raise SeletorPastaNaoConfirmado('Aviso no seletor; não foi enviado OK.')
        alvo=localizar_raiz(img,d,nome,coluna,altura)
        if alvo is not None:
            img,d=_aguardar_dialogo(capturar,lambda img,d:_drive_selecionado(d,letra),
                fase='raiz_atual_antes_clique',estavel=True)
            alvo=localizar_raiz(img,d,nome,coluna,altura)
            if alvo is None:
                raise SeletorPastaNaoConfirmado('A pasta da raiz mudou antes do clique; não foi enviado OK.')
            ponto_seguro()
            print('PASTA_NAVEGACAO '+json.dumps({'fase':'raiz_por_recorte','passo':passo,
                  'posicao':list(alvo['posicao'])}),flush=True)
            clicar(*alvo['posicao'])
            img,d,selecionado=_ler_selecao(capturar,letra,'confirmar_raiz_recorte',estavel=True)
            if (selecionado['nome']!=_normalizar(nome)
                    or abs(selecionado['x']-alvo['x'])>alvo['tolerancia']):
                raise SeletorPastaNaoConfirmado('A pasta da raiz não foi confirmada; não foi enviado OK.')
            print('PASTA_NAVEGACAO '+json.dumps({'fase':'segmento','nivel':0,
                  'passos':passo,'confirmado':True,'origem':'recorte_raiz'}),flush=True)
            return img,d,selecionado
        if passo==max_rolagens:break
        barra=medir_seta_baixo(img,d['arvore'],altura)
        if barra is None:
            print('PASTA_NAVEGACAO {"fase":"rolar_raiz","motivo":"seta_ou_trilho_nao_confirmados","confirmado":false}',flush=True)
            break
        img,d=_aguardar_dialogo(capturar,lambda img,d:_drive_selecionado(d,letra),
            fase='barra_atual_antes_clique',estavel=True)
        barra=medir_seta_baixo(img,d['arvore'],altura)
        if barra is None:
            raise SeletorPastaNaoConfirmado('A barra mudou antes do clique; não foi enviado OK.')
        antes=img.crop(barra['conteudo']).tobytes()
        geometria=d['arvore']
        ponto_seguro()
        print('PASTA_NAVEGACAO '+json.dumps({'fase':'rolar_raiz','passo':passo,
              'botao':list(barra['botao'])}),flush=True)
        clicar(*barra['posicao'])
        def mudou(imagem,detalhes):
            return (_drive_selecionado(detalhes,letra) and detalhes['arvore']==geometria
                    and imagem.crop(barra['conteudo']).tobytes()!=antes)
        img,d=_aguardar_dialogo(capturar,mudou,fase='confirmar_rolagem_raiz',estavel=True)
    raise SeletorPastaNaoConfirmado('Raiz não confirmada por recorte/rolagem medida; não foi enviado OK.')


def _buscar_irmao(capturar, tecla, letra, estado, nome, nivel, clicar=None):
    img,d,no=estado
    coluna=no['x']
    for passo in range(160):
        ponto_seguro()
        if abs(no['x']-coluna)>2:
            raise SeletorPastaNaoConfirmado('O próximo item não pertence ao nível esperado; não foi enviado OK.')
        if no['nome']==_normalizar(nome):
            print('PASTA_NAVEGACAO '+json.dumps({'fase':'segmento','nivel':nivel,
                  'passos':passo,'confirmado':True}),flush=True)
            return img,d,no
        if clicar is not None:
            selecionado=_selecionar_visivel(capturar,clicar,letra,(img,d,no),nome,nivel)
            if selecionado is not None:
                img,d,no=selecionado
                continue
        try:
            img,d,no=_avancar_irmao(capturar,tecla,letra,no)
        except SeletorPastaNaoConfirmado:
            if nivel!=0 or _normalizar(nome)!='users' or clicar is None:raise
            return _recuperar_raiz_sem_avanco(capturar,clicar,letra,(img,d,no),nome)
    raise SeletorPastaNaoConfirmado('Limite de pastas por nível atingido; não foi enviado OK.')


def _entrar_no(capturar, tecla, letra, pai):
    tecla('right')
    def confirmar(img,d):
        no=_no_selecionado(img,d)
        if not _drive_selecionado(d,letra) or no is None:return False
        if no['x']>pai['x']+2:return True  # ramo já aberto: Right foi ao primeiro filho
        # Right em ramo fechado mantém o pai; o filho pode estar abaixo da
        # área visível. Down fará a rolagem e sua indentação será conferida.
        return _mesmo_no(no,pai)
    img,d=_aguardar_dialogo(capturar,confirmar,fase='expandir_ancestral',estavel=True)
    no=_no_selecionado(img,d)
    if _mesmo_no(no,pai):
        tecla('down')
        img,d,no=_ler_selecao(capturar,letra,'primeiro_filho',diferente=pai)
    if no['x']<=pai['x']+2:
        raise SeletorPastaNaoConfirmado('Primeiro filho não confirmado; não foi enviado OK.')
    return img,d,no


def _ok_final(imagem, detalhes):
    if detalhes['ok'] is not None:
        px,py=detalhes['ok']
        for x,y,w,h in detalhes.get('botoes_ok',[]):
            if not (x<px<x+w and y<py<y+h):continue
            dentro=[p for p in detalhes['palavras'] if x<p['x']<x+w and y<p['y']<y+h]
            if [_normalizar(p['texto']) for p in dentro]==['ok']:
                return detalhes['ok']
    from app import tela
    from app.formulario_livros import _rotulo
    confirmados=[]
    for x,y,w,h in detalhes.get('botoes_ok',[]):
        leituras=[]
        margem=max(1,round(h*.15))
        area=(x+margem,y+margem,x+w-margem,y+h-margem)
        for preparo in ('cinza','binaria'):
            ponto_seguro()
            dados=tela.ler_dados_ocr_linha_rotulo(imagem.crop(area),escala=4,preparo=preparo)
            palavras=[{'texto':t,'x':dados['left'][i]/4,'y':dados['top'][i]/4,
                       'w':dados['width'][i]/4,'h':dados['height'][i]/4}
                      for i,t in enumerate(dados['text']) if str(t).strip()]
            if [_normalizar(p['texto']) for p in palavras]!=['ok']:continue
            try:rotulo=_rotulo(palavras,'OK')
            except ValueError:continue
            if not (0<=rotulo['x']<rotulo['x']+rotulo['w']<=area[2]-area[0]
                    and 0<=rotulo['y']<rotulo['y']+rotulo['h']<=area[3]-area[1]):continue
            leituras.append((area[0]+rotulo['x']+rotulo['w']/2,area[1]+rotulo['y']+rotulo['h']/2))
        if len(leituras)==2 and abs(leituras[0][0]-leituras[1][0])<=3 and abs(leituras[0][1]-leituras[1][1])<=3:
            confirmados.append(tuple(round(v) for v in leituras[0]))
    # Bordas duplicadas do mesmo botão não criam alvos distintos.
    if confirmados and all(abs(p[0]-confirmados[0][0])<=3 and abs(p[1]-confirmados[0][1])<=3 for p in confirmados):
        return confirmados[0]
    return None


def selecionar_pasta(caminho_remoto, capturar, clicar, tecla):
    """Setas percorrem a árvore desde a raiz; só a folha comprovada recebe OK."""
    caminho=PureWindowsPath(caminho_remoto)
    if (not caminho.is_absolute() or not re.fullmatch(r'[A-Za-z]:',caminho.drive)
            or '..' in caminho.parts or not re.fullmatch(r'LIVROS[0-9]{12}',caminho.name)):
        raise SeletorPastaNaoConfirmado('Destino precisa ser uma pasta exclusiva de livros.')
    imagem, detalhes = _aguardar_dialogo(capturar,fase='abrir_seletor')
    imagem,detalhes=_selecionar_unidade(capturar,clicar,tecla,caminho.drive[0],imagem,detalhes)
    partes=caminho.parts[1:]
    nos=_nos(detalhes)
    if not nos:raise SeletorPastaNaoConfirmado('Nenhum item da árvore reconhecido; não foi enviado OK.')
    clicar(*nos[0]['posicao'])  # foco em linha medida, antes de Home
    _ler_selecao(capturar,caminho.drive[0],'foco_arvore')
    tecla('home')
    estado=_ler_selecao(capturar,caminho.drive[0],'inicio_arvore')
    for indice,nome in enumerate(partes):
        estado=_buscar_irmao(capturar,tecla,caminho.drive[0],estado,nome,indice,clicar=clicar)
        if indice<len(partes)-1:
            estado=_entrar_no(capturar,tecla,caminho.drive[0],estado[2])
    folha=estado[2]
    def confirmar_final(img,d):
        if not _drive_selecionado(d,caminho.drive[0]) or not _mesmo_no(_no_selecionado(img,d),folha):return False
        d['ok']=_ok_final(img,d)
        return d['ok'] is not None
    imagem,detalhes=_aguardar_dialogo(capturar,confirmar_final,fase='confirmar_destino_e_ok')
    ponto_seguro()
    clicar(*detalhes['ok'])
    return True
