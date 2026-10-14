"""Datas em campos medidos por pixels; nenhuma ação sobre o desktop."""
import datetime as dt
import math
import re

from app.formulario_resumo import campos_periodo


def diagnostico_rotulos(dados, escala):
    """Somente rótulos canônicos/caixas; descarta texto livre da captura."""
    permitidos={'data':'data','inicial':'inicial','final':'final',
                'datainicial':'data_inicial','datafinal':'data_final',
                'iniciat':'inicial','finat':'final'}
    resultado=[]
    for i, texto in enumerate(dados.get('text', [])):
        token=re.sub(r'\s+', '', str(texto).rstrip(':').casefold())
        if token not in permitidos:continue
        try:
            caixa=[dados[k][i]/escala for k in ('left','top','width','height')]
            if any(not isinstance(v,(int,float)) or v<0 for v in caixa):continue
        except (KeyError,IndexError,TypeError,ZeroDivisionError):continue
        resultado.append({'rotulo':permitidos[token],'caixa':caixa})
    return resultado


def motivo_geometria(erro):
    """Converte só mensagens conhecidas em códigos; não imprime exceções."""
    return {
        'Rótulos do período ausentes ou ambíguos.':'rotulos_ausentes_ou_ambiguos',
        'Ordem dos campos não confirmada.':'ordem_campos_nao_confirmada',
        'Bordas do campo ausentes ou ambíguas.':'bordas_ausentes_ou_ambiguas',
        'Área textual do campo não confirmada.':'area_textual_nao_confirmada',
        'A dupla de controles não confirmou alinhamento/tamanho.':'alinhamento_campos_nao_confirmado',
    }.get(str(erro),'geometria_nao_confirmada')


def _rotulo_periodo(dados, escala, papel, livros=False):
    palavras=[{'texto':str(t).strip(), 'x':dados['left'][i]/escala, 'y':dados['top'][i]/escala,
               'w':dados['width'][i]/escala, 'h':dados['height'][i]/escala}
              for i,t in enumerate(dados['text']) if str(t).strip()]
    candidatos=[]
    for p in palavras:
        token=p['texto'].rstrip(':').casefold()
        if livros and token in ('iniciat','finat'):
            token = 'inicial' if token == 'iniciat' else 'final'
        if re.fullmatch('data'+r'\s*'+papel,token):
            candidatos.append(p)
        elif token==papel:
            if livros:
                anteriores = [a for a in palavras if a['x']+a['w'] <= p['x']
                    and p['x']-(a['x']+a['w'])<=2*p['h']
                    and max(p['y'],a['y'])<min(p['y']+p['h'],a['y']+a['h'])]
                if not anteriores:candidatos.append(p)
                continue
            anteriores=[a for a in palavras if a['texto'].casefold()=='data' and a['x']+a['w']<=p['x']
                and p['x']-(a['x']+a['w'])<=2*p['h']
                and max(p['y'],a['y'])<min(p['y']+p['h'],a['y']+a['h'])]
            if len(anteriores)==1:
                a=anteriores[0]
                candidatos.append({'x':a['x'],'y':min(a['y'],p['y']),
                    'w':p['x']+p['w']-a['x'],'h':max(a['y']+a['h'],p['y']+p['h'])-min(a['y'],p['y'])})
    if len(candidatos)!=1:raise ValueError('Rótulos do período ausentes ou ambíguos.')
    return candidatos[0]


def rotulos_periodo(dados, escala, livros=False):
    resultado={p:_rotulo_periodo(dados,escala,p,livros) for p in ('inicial','final')}
    if resultado['inicial']['y']>=resultado['final']['y']:raise ValueError('Ordem dos campos não confirmada.')
    return resultado


def resolver_rotulos_resumo(imagem, dados, escala, registrar=None, titulo_confirmado=False):
    """Global primeiro; relê rótulo final numa ROI das caixas atuais.

    Nunca transforma uma segunda linha em Final por sua posição. Somente
    duas leituras literais completas autorizam medir o controle seguinte.
    """
    from app import tela
    try:return rotulos_periodo(dados,escala)
    except ValueError as erro:
        original=erro
    inicial=_rotulo_periodo(dados,escala,'inicial')
    # Não encobrir Final duplicado, deslocado ou sem Data: se ele já foi
    # lido, a ambiguidade global precisa continuar bloqueando a rotina.
    if any(re.fullmatch(r'(data\s*)?final:?',str(t).strip().casefold()) for t in dados['text']):
        raise original
    datas=[{'x':dados['left'][i]/escala,'y':dados['top'][i]/escala,
            'w':dados['width'][i]/escala,'h':dados['height'][i]/escala}
           for i,t in enumerate(dados['text']) if str(t).strip().casefold()=='data']
    candidatas=[r for r in datas if r['y']>inicial['y']+inicial['h']
                and abs(r['x']-inicial['x'])<=inicial['h']]
    if len(candidatas)!=1:raise original
    if not titulo_confirmado:
        for ampliacao in (2,4):
            if (tela.achar_texto_ou_no_centro(imagem,'Resumo por acumulador',escala=ampliacao) is not None
                    or tela.achar_texto_windows(imagem,'Resumo por acumulador',escala=ampliacao) is not None):
                titulo_confirmado=True; break
    if not titulo_confirmado:raise original
    r=candidatas[0]; margem=max(inicial['h'],r['h'])*.4
    area=(max(0,math.floor(min(inicial['x'],r['x'])-margem)),
          max(math.ceil(inicial['y']+inicial['h']),math.floor(r['y']-margem)),
          min(imagem.width,math.ceil(inicial['x']+inicial['w']+margem)),
          min(imagem.height,math.ceil(r['y']+r['h']+margem)))
    if area[2]<=area[0] or area[3]<=area[1]:raise original
    recorte=imagem.crop(area); reconhecidos=[]; contradicao=False
    for preparo,ampliacao in (('cinza',4),('cinza',6),('binaria',4),('binaria',6)):
        try:
            leitura=tela.ler_dados_ocr_linha_rotulo(recorte,ampliacao,preparo)
            indices=[i for i,t in enumerate(leitura['text']) if str(t).strip()]
            texto=' '.join(str(leitura['text'][i]).strip() for i in indices).casefold()
            if re.fullmatch(r'data\s*inicial:?',texto):
                contradicao=True; break
            if not re.fullmatch(r'data\s*final:?',texto):continue
            if any(leitura['left'][i]<0 or leitura['top'][i]<0
                   or leitura['width'][i]<=0 or leitura['height'][i]<=0
                   or leitura['left'][i]+leitura['width'][i]>recorte.width*ampliacao
                   or leitura['top'][i]+leitura['height'][i]>recorte.height*ampliacao
                   for i in indices):continue
            if (max(leitura['top'][i] for i in indices)>=
                    min(leitura['top'][i]+leitura['height'][i] for i in indices)):continue
            x=min(leitura['left'][i] for i in indices)/ampliacao+area[0]
            y=min(leitura['top'][i] for i in indices)/ampliacao+area[1]
            direita=max(leitura['left'][i]+leitura['width'][i] for i in indices)/ampliacao+area[0]
            baixo=max(leitura['top'][i]+leitura['height'][i] for i in indices)/ampliacao+area[1]
            # A palavra Data relida precisa corresponder à mesma âncora,
            # não a outra linha dentro da margem do recorte.
            i=indices[0]
            data_x=leitura['left'][i]/ampliacao+area[0]
            data_y=leitura['top'][i]/ampliacao+area[1]
            if (max(data_x,r['x'])>=min(data_x+leitura['width'][i]/ampliacao,r['x']+r['w'])
                    or max(data_y,r['y'])>=min(data_y+leitura['height'][i]/ampliacao,r['y']+r['h'])):continue
            reconhecidos.append({'x':x,'y':y,'w':direita-x,'h':baixo-y})
        except Exception:continue
    confirmado=(not contradicao and len(reconhecidos)>=2 and all(
        abs(c[k]-reconhecidos[0][k])<=max(inicial['h'],r['h'])*.3
        for c in reconhecidos for k in ('x','y','w','h')))
    if registrar:registrar({'fase':'rotulo_recorte','campo':'final','area':list(area),
                           'leituras_confirmadas':len(reconhecidos),'confirmado':confirmado})
    if not confirmado:raise original
    return {'inicial':inicial,'final':reconhecidos[0]}


def normalizar_selecao(imagem):
    """Converte só blocos azuis detectados na cópia; preserva seus glifos."""
    import cv2
    import numpy as np
    from PIL import Image
    rgb=np.array(imagem.convert('RGB'))
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    azul=((hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>100)&(hsv[:,:,2]>70)).astype('uint8')
    contornos,_=cv2.findContours(azul,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    saida=rgb.copy()
    for contorno in contornos:
        x,y,w,h=cv2.boundingRect(contorno)
        if h<3 or w<3 or cv2.contourArea(contorno)/(w*h)<.4:continue
        trecho=hsv[y:y+h,x:x+w]
        tinta=(trecho[:,:,1]<90)&(trecho[:,:,2]>150)
        regiao=saida[y:y+h,x:x+w]
        regiao[:]=255
        regiao[tinta]=0
    return Image.fromarray(saida)


def medir_campos(imagem, rotulos):
    import cv2
    import numpy as np
    cinza=np.array(imagem.convert('L'))
    altura=max(r['h'] for r in rotulos.values())
    caixas=set()
    mascaras=[(cinza<limite).astype('uint8')*255 for limite in (160,200,230)]
    # Borda Windows tem lados claros: máscara escura isolada pode formar L.
    mascaras.append(cv2.Canny(cinza,8,30))
    for mascara in mascaras:
        contornos,_=cv2.findContours(mascara,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            x,y,w,h=cv2.boundingRect(contorno)
            vertices=cv2.approxPolyDP(contorno,.02*cv2.arcLength(contorno,True),True)
            if (len(vertices)==4 and 1.1*altura<=h<=3.5*altura and 2<=w/h<=10
                    and cv2.contourArea(contorno)/(w*h)>.7):caixas.add((x,y,w,h))
    campos={}
    for papel,r in rotulos.items():
        candidatos=[c for c in caixas if r['x']+r['w']-.25*altura<=c[0]<=r['x']+r['w']+3*altura
                    and c[1]<r['y']+r['h']/2<c[1]+c[3]
                    and abs(c[1]+c[3]/2-(r['y']+r['h']/2))<=altura]
        # Bordas internas/externas e fundo da seleção contidos no mesmo campo.
        unicos=[]
        for c in sorted(candidatos,key=lambda c:c[2]*c[3],reverse=True):
            if not any(c[0]>=a[0] and c[1]>=a[1] and c[0]+c[2]<=a[0]+a[2] and c[1]+c[3]<=a[1]+a[3] for a in unicos):unicos.append(c)
        if len(unicos)!=1:raise ValueError('Bordas do campo ausentes ou ambíguas.')
        x,y,w,h=unicos[0]
        margem=max(1,round(h*.06))
        normalizada=normalizar_selecao(imagem.crop((x,y,x+w,y+h)))
        pixels=np.array(normalizada.convert('L'))
        interno=pixels[margem:h-margem,:]
        divisoes=[i for i in range(max(margem,int(w*.55)),w-2*margem)
                  if (interno[:,i]<200).mean()>=.85]
        direita=min(divisoes) if divisoes else w-margem
        area=(x+margem,y+margem,x+direita-margem,y+h-margem)
        if area[2]-area[0]<2*altura:raise ValueError('Área textual do campo não confirmada.')
        campos[papel]={'retangulo':(x,y,w,h),'area_texto':area,
                       'posicao':((area[0]+area[2])//2,(area[1]+area[3])//2)}
    a,b=campos['inicial']['retangulo'],campos['final']['retangulo']
    if (a[1]+a[3]>b[1] or abs(a[0]-b[0])>altura or abs(a[2]-b[2])>altura or abs(a[3]-b[3])>altura):
        raise ValueError('A dupla de controles não confirmou alinhamento/tamanho.')
    return campos


def data_da_linha(dados):
    """Recompõe componentes completos, sem completar ou corrigir dígitos."""
    palavras=[(str(t).strip(),dados['left'][i],dados['top'][i],dados['height'][i])
              for i,t in enumerate(dados['text']) if str(t).strip()]
    if not palavras or any(not re.fullmatch(r'[0-9/\s]+',p[0]) for p in palavras):return None
    if max(p[2] for p in palavras)>=min(p[2]+p[3] for p in palavras):return None
    texto=''.join(re.sub(r'\s','',p[0]) for p in sorted(palavras,key=lambda p:p[1]))
    digitos=texto.replace('/','')
    separadores=[len(texto[:i].replace('/','')) for i,c in enumerate(texto) if c=='/']
    if len(digitos)==8 and all(i in (2,4) for i in separadores) and len(separadores)==len(set(separadores)):
        texto=digitos[:2]+'/'+digitos[2:4]+'/'+digitos[4:]
    if not re.fullmatch(r'[0-9]{2}/[0-9]{2}/[0-9]{4}',texto):return None
    try:dt.datetime.strptime(texto,'%d/%m/%Y')
    except ValueError:return None
    return texto


def formulario_resumo_reconhecido(imagem):
    """Título e dupla de rótulos; não exige datas legíveis para abrir a etapa."""
    from app import tela
    for motor, escala in (('tesseract', 2), ('tesseract', 4), ('windows', 2), ('windows', 4)):
        try:
            titulo = (tela.achar_texto_ou_no_centro(imagem, 'Resumo por acumulador', escala=escala)
                      if motor == 'tesseract' else
                      tela.achar_texto_windows(imagem, 'Resumo por acumulador', escala=escala))
            if titulo is None:
                continue
            dados = (tela._ler_dados_ocr(imagem, escala) if motor == 'tesseract' else
                     tela.ler_dados_ocr_windows(imagem, escala))
            rotulos = resolver_rotulos_resumo(imagem,dados,escala,titulo_confirmado=True)
            medir_campos(imagem, rotulos)
            return titulo
        except (ValueError, TypeError, KeyError, RuntimeError):
            continue
    return None


def ler_campos(imagem, registrar=None, livros=False, salvar_recorte=None):
    """Mede controles e exige duas leituras completas concordantes por data.

    O período solicitado não entra neste leitor. Leituras completas
    conflitantes recusam confirmação; não escolhe pela data esperada.
    """
    from app import tela
    contextos=[]; completos=[]
    for motor,escala in (('tesseract',2),('tesseract',4),('windows',2),('windows',4),
                         ('binaria_bloco',4),('binaria_esparsa',4)):
        try:
            if motor=='tesseract':dados=tela._ler_dados_ocr(imagem,escala)
            elif motor=='windows':dados=tela.ler_dados_ocr_windows(imagem,escala)
            else:dados=tela.ler_dados_ocr_formulario(imagem,escala,'binaria',6 if motor=='binaria_bloco' else 11)
            if dados is None:
                if registrar:registrar({'fase':'ocr','motor':motor,'escala':escala,
                    'confirmado':False,'motivo':'motor_indisponivel'})
                continue
            try:
                if livros:
                    from app.formulario_livros import _periodo, _palavras
                    completos.append(_periodo(_palavras(dados,escala)))
                else:completos.append(campos_periodo(dados,escala))
            except ValueError:pass
            try:
                rotulos=(rotulos_periodo(dados,escala,livros=True) if livros else
                         resolver_rotulos_resumo(imagem,dados,escala,registrar))
                medidas=medir_campos(imagem,rotulos)
                contextos.append(medidas)
                if registrar:registrar({'fase':'geometria','motor':motor,'escala':escala,'confirmado':True,
                    'campos':{p:list(c['retangulo']) for p,c in medidas.items()}})
            except ValueError as erro:
                if registrar:registrar({'fase':'geometria','motor':motor,'escala':escala,
                    'confirmado':False,'motivo':motivo_geometria(erro),
                    'rotulos':diagnostico_rotulos(dados,escala)})
        except Exception:
            if registrar:registrar({'fase':'ocr','motor':motor,'escala':escala,
                'confirmado':False,'motivo':'leitura_motor_nao_confirmada'})
            continue
    if not contextos:
        # Compatibilidade sem nova geometria: duas leituras globais completas.
        if len(completos)>=2 and len({tuple(c[p]['valor'] for p in ('inicial','final')) for c in completos})==1:
            referencia=completos[0]
            distancia=referencia['final']['posicao'][1]-referencia['inicial']['posicao'][1]
            if distancia>0 and all(abs(c[p]['posicao'][i]-referencia[p]['posicao'][i])<=distancia/4
                                  for c in completos for p in ('inicial','final') for i in (0,1)):
                return referencia
        raise ValueError('Dois campos não confirmados por bordas ou leituras completas concordantes.')
    if len({tuple(c[p]['retangulo'] for p in ('inicial','final')) for c in contextos})!=1:
        raise ValueError('Geometria dos campos conflitante entre leituras.')
    campos=contextos[0]; resultado={}
    for papel,campo in campos.items():
        original=imagem.crop(campo['area_texto'])
        normalizada=normalizar_selecao(original)
        leituras=[]; detalhe=[]
        for variante,recorte in (('original',original),('selecao_normalizada',normalizada)):
            for motor,escala in (('tesseract',4),('tesseract',6),('windows',2)):
                try:
                    dados=tela.ler_dados_ocr_linha_data(recorte,escala) if motor=='tesseract' else tela.ler_dados_ocr_windows(recorte,escala)
                    valor=data_da_linha(dados) if dados is not None else None
                except Exception:valor=None
                detalhe.append({'variante':variante,'motor':motor,'escala':escala,'valor':valor})
                if valor is not None:leituras.append(valor)
        # Preto e branco tenta ler dígitos pequenos sem mudar o valor pedido.
        for escala in (4,6):
            try:
                dados=tela.ler_dados_ocr_linha_data(normalizada,escala,preparo='binaria')
                valor=data_da_linha(dados) if dados is not None else None
            except Exception:valor=None
            detalhe.append({'variante':'binaria','motor':'tesseract','escala':escala,'valor':valor})
            if valor is not None:leituras.append(valor)
        valores=set(leituras)
        if registrar:registrar({'campo':papel,'retangulo':list(campo['retangulo']),
            'area_texto':list(campo['area_texto']),'leituras':detalhe,
            'confirmado':len(leituras)>=2 and len(valores)==1})
        if len(leituras)<2 or len(valores)!=1:
            if salvar_recorte:
                try:
                    salvar_recorte(original,papel+'_original')
                    salvar_recorte(tela.preparar_recorte_ocr(normalizada,6,'binaria'),papel+'_binaria_6x')
                except Exception:pass
            raise ValueError('Data do recorte incompleta ou conflitante entre leituras.')
        valor=valores.pop()
        if any(c[papel]['valor']!=valor for c in completos):
            raise ValueError('Leitura global completa divergiu do recorte do campo.')
        resultado[papel]={'valor':valor,'posicao':campo['posicao']}
    return resultado
