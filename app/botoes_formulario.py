"""Botão OK do Resumo por OCR e bordas atuais, sem ações de desktop.

A geometria vem da própria captura. Não calcula OK pela posição de Fechar
nem reaproveita coordenadas de outra execução. Falha/ambiguidade retorna
None. Fixtures sintéticas não equivalem à validação no Domínio real.
"""
import math
import unicodedata

from app import tela
from app.controle_execucao import ExecucaoInterrompida, ponto_seguro
from app.formulario_livros import _palavras, _rotulo
from app.leitura_resumo import (formulario_resumo_reconhecido, medir_campos,
                                resolver_rotulos_resumo)

AVISOS = ('Atenção', 'Aviso Empresa', 'Aviso')
ROTULOS_BOTOES = {'ok', 'fechar', 'solucoes', 'cancelar', 'sim', 'nao'}


def _dentro(posicao, caixa):
    x,y,w,h = caixa
    return x < posicao[0] < x+w and y < posicao[1] < y+h


def _deduplicar_retangulos(candidatos):
    """Mantém uma borda medida por botão, sem unir botões vizinhos.

    Relevo 3D pode deslocar o contorno para fora do outro em um lado.
    Nesse caso exige cobertura do menor e proximidade nos quatro lados;
    compara sempre ao representante, sem encadear aproximações.
    """
    unicos = []
    for c in sorted(set(candidatos),key=lambda c:(-c[2]*c[3],c)):
        def mesma_borda(a):
            contida = c[0]>=a[0] and c[1]>=a[1] and c[0]+c[2]<=a[0]+a[2] and c[1]+c[3]<=a[1]+a[3]
            inter = max(0,min(c[0]+c[2],a[0]+a[2])-max(c[0],a[0]))*max(0,min(c[1]+c[3],a[1]+a[3])-max(c[1],a[1]))
            areas = (c[2]*c[3],a[2]*a[3])
            lados_c = (c[0],c[1],c[0]+c[2],c[1]+c[3])
            lados_a = (a[0],a[1],a[0]+a[2],a[1]+a[3])
            relevo = (inter/min(areas)>=.9 and
                      all(abs(v-u)<=.2*min(c[3],a[3]) for v,u in zip(lados_c,lados_a)))
            return contida or inter/(sum(areas)-inter)>=.8 or relevo
        if not any(mesma_borda(a) for a in unicos):
            unicos.append(c)
    return unicos


def _retangulos(imagem, altura):
    import cv2
    import numpy as np
    cinza = np.asarray(imagem.convert('L'))
    valores = cinza.astype('int16')
    horizontal = np.zeros(cinza.shape,dtype='int16')
    vertical = np.zeros(cinza.shape,dtype='int16')
    horizontal[:,1:] = np.abs(valores[:,1:]-valores[:,:-1])
    vertical[1:,:] = np.abs(valores[1:,:]-valores[:-1,:])
    def quatro_lados(x,y,w,h):
        # Uma borda 3D pode ser L em uma máscara. Não completar esse L:
        # os quatro lados precisam existir como contraste na captura.
        margem = max(1,math.ceil(h*.12))
        a,b = x+margem,x+w-margem
        c,d = y+margem,y+h-margem
        if a>=b or c>=d:return False
        limites = (vertical[max(0,y-margem):min(cinza.shape[0],y+margem+1),a:b],
                   vertical[max(0,y+h-margem):min(cinza.shape[0],y+h+margem+1),a:b],
                   horizontal[c:d,max(0,x-margem):min(cinza.shape[1],x+margem+1)],
                   horizontal[c:d,max(0,x+w-margem):min(cinza.shape[1],x+w+margem+1)])
        return all(t.size and (t.max(axis=eixo)>=8).mean()>=.65
                   for t,eixo in zip(limites,(0,0,1,1)))
    candidatos = set()
    mascaras = [(cinza < limite).astype('uint8')*255 for limite in (160,200,230)]
    mascaras.append(cv2.Canny(cinza,8,30))
    for mascara in mascaras:
        contornos,_ = cv2.findContours(mascara,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            x,y,w,h = cv2.boundingRect(contorno)
            vertices = cv2.approxPolyDP(contorno,.02*cv2.arcLength(contorno,True),True)
            fechado = len(vertices)==4 and cv2.contourArea(contorno)/(w*h) > .7
            if (.6*altura <= h <= 1.7*altura and 2 <= w/h <= 8
                    and (fechado or quatro_lados(x,y,w,h))):
                candidatos.add((x,y,w,h))
    return _deduplicar_retangulos(candidatos)


def _texto_recorte(imagem, caixa):
    """Duas opiniões exatas; erro isolado não fabrica nem veta um rótulo.

    Outro rótulo completo e texto que acrescenta palavras a OK/Fechar
    continuam contraditórios. Sem aliases de caracteres nem whitelist.
    """
    x,y,w,h = caixa
    margem = max(1,math.ceil(h*.08))
    recorte = imagem.crop((x+margem,y+margem,x+w-margem,y+h-margem))
    votos = {}
    contradicao = False
    def observar(dados):
        nonlocal contradicao
        indices = [i for i,t in enumerate(dados.get('text',[])) if str(t).strip()]
        if not indices:return
        texto = ' '.join(str(dados['text'][i]).strip() for i in indices).casefold()
        texto = ''.join(c for c in unicodedata.normalize('NFKD',texto) if not unicodedata.combining(c))
        if (max(dados['top'][i] for i in indices)>=
                min(dados['top'][i]+dados['height'][i] for i in indices)):
            if any(t in ROTULOS_BOTOES for t in texto.split()):contradicao=True
            return
        if texto in ROTULOS_BOTOES:
            votos[texto] = votos.get(texto,0)+1
        elif texto.split() and texto.split()[0] in ROTULOS_BOTOES:
            contradicao = True
    for preparo in ('cinza','binaria'):
        for escala in (2,4):
            try:
                # Sem whitelist: não apagar outros caracteres para fabricar OK.
                observar(tela.ler_dados_ocr_linha_rotulo(recorte,escala,preparo))
            except ExecucaoInterrompida:
                raise
            except Exception:
                continue
    if len(votos)>1 or contradicao:return {'contradicao'}
    return {rotulo for rotulo,n in votos.items() if n>=2}


def _registrar(registrar, fase, motivo, **detalhe):
    if registrar:registrar({'fase':fase,'motivo':motivo,**detalhe})


def _conferir_avisos(imagem, registrar=None):
    """Uma falha de OCR não impede as outras opiniões desta captura.

    None significa que nenhuma leitura funcionou, e continua bloqueando
    emissão. Não transforma indisponibilidade dos motores em ausência de aviso.
    """
    centro, _, _ = tela.recortar_centro(imagem)
    validas = 0
    validas_tela = 0
    for regiao, area in (('tela', imagem), ('centro', centro)):
        for motor, escala in (('tesseract',2),('tesseract',4),('windows',2),('windows',4)):
            ponto_seguro()
            try:
                dados = (tela._ler_dados_ocr(area,escala) if motor == 'tesseract'
                         else tela.ler_dados_ocr_windows(area,escala))
                if dados is None:
                    continue
                textos = dados['text']
                if not isinstance(textos,list) or any(not isinstance(t,str) for t in textos):
                    raise ValueError('Leitura OCR inválida.')
                validas += 1
                if regiao == 'tela':validas_tela += 1
                texto = ' '.join(textos).casefold()
                # Mesmos títulos conhecidos; nada depende de posição de clique.
                if any(aviso.casefold() in texto for aviso in AVISOS):
                    _registrar(registrar,'contexto','aviso_reconhecido',
                        motor=motor,escala=escala,regiao=regiao)
                    return True
            except ExecucaoInterrompida:
                raise
            except Exception as erro:
                _registrar(registrar,'guarda_avisos','leitura_indisponivel',
                    motor=motor,escala=escala,regiao=regiao,tipo_erro=type(erro).__name__)
    ponto_seguro()
    _registrar(registrar,'guarda_avisos','leituras_concluidas' if validas_tela else 'sem_leitura_valida',
        leituras_validas=validas,leituras_tela_inteira=validas_tela)
    return False if validas_tela else None


def _oks_exatos(imagem, motor, escala):
    """Token inteiro; substring de BOOK, por exemplo, não é outro OK."""
    dados=(tela._ler_dados_ocr(imagem,escala) if motor=='tesseract' else
           tela.ler_dados_ocr_windows(imagem,escala))
    if dados is None:return []
    return [((dados['left'][i]+dados['width'][i]/2)/escala,
             (dados['top'][i]+dados['height'][i]/2)/escala)
            for i,t in enumerate(dados['text']) if str(t).strip().casefold()=='ok']


def _ler_botao(imagem, caixa, leituras, registrar=None):
    if caixa not in leituras:
        leituras[caixa] = _texto_recorte(imagem,caixa)
        _registrar(registrar,'texto','recorte_botao_lido',caixa=list(caixa),
            rotulos_confirmados=sorted(leituras[caixa] & ROTULOS_BOTOES),
            contradicao='contradicao' in leituras[caixa])
    return leituras[caixa]


def _contexto_coluna(imagem, registrar=None, leituras=None):
    contextos = []
    leituras = leituras if leituras is not None else {}
    for motor,escala in (('tesseract',2),('tesseract',4),('windows',2),('windows',4)):
        motivo_falha='campos_periodo_nao_confirmados'
        try:
            dados = (tela._ler_dados_ocr(imagem,escala) if motor=='tesseract'
                     else tela.ler_dados_ocr_windows(imagem,escala))
            if dados is None:
                continue
            campos = medir_campos(imagem,resolver_rotulos_resumo(imagem,dados,escala,
                                                               titulo_confirmado=True))
            palavras = _palavras(dados,escala)
            altura = max(c['retangulo'][3] for c in campos.values())
            direita = max(c['retangulo'][0]+c['retangulo'][2] for c in campos.values())
            motivo_falha='bordas_botoes_nao_confirmadas'
            caixas = [c for c in _retangulos(imagem,altura) if c[0] > direita
                and c[1]+c[3]>=campos['inicial']['retangulo'][1]-altura
                and c[1]<=campos['final']['retangulo'][1]+campos['final']['retangulo'][3]]
            motivo_falha='rotulo_fechar_nao_confirmado'
            try:
                fechar = _rotulo(palavras,'Fechar')
                centro = (fechar['x']+fechar['w']/2,fechar['y']+fechar['h']/2)
                fechar_caixas = [c for c in caixas if _dentro(centro,c)]
            except ValueError:
                # O rótulo pode sumir na leitura global. Cada retângulo
                # é real e seu texto precisa confirmar Fechar integralmente.
                fechar_caixas = [c for c in caixas if _ler_botao(imagem,c,leituras,registrar)=={'fechar'}]
                centro = None
                _registrar(registrar,'coluna','fechar_por_recorte',motor=motor,escala=escala,
                    quantidade=len(fechar_caixas))
            if len(fechar_caixas)!=1:
                _registrar(registrar,'coluna','borda_fechar_nao_confirmada',motor=motor,escala=escala,
                    caixas=[list(c) for c in caixas],fechar=list(centro) if centro else None,quantidade=len(fechar_caixas))
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
            _registrar(registrar,'coluna','candidatos_medidos' if candidatos else 'sem_candidato_ok',
                motor=motor,escala=escala,fechar=list(botao_fechar),candidatos=[list(c) for c in candidatos])
        except ExecucaoInterrompida:
            raise
        except Exception:
            _registrar(registrar,'coluna',motivo_falha,motor=motor,escala=escala)
            continue
    if not contextos or len(set(contextos))!=1:
        _registrar(registrar,'coluna','coluna_ausente_ou_conflitante',quantidade=len(contextos))
        return None
    return contextos[0]


def achar_ok_resumo(imagem, registrar=None):
    """Uma análise, uma captura: descarta o OCR ao retornar, sem clicar."""
    _registrar(registrar,'inicio','analise_ok_iniciada')
    ponto_seguro()
    with tela.reutilizar_ocr():
        resultado = _achar_ok_resumo_na_captura(imagem,registrar)
    ponto_seguro()
    return resultado


def _achar_ok_resumo_na_captura(imagem, registrar=None):
    """Devolve centro do botão inequívoco ou None; nunca clica/gera."""
    fase = 'guarda_avisos'
    try:
        if _conferir_avisos(imagem,registrar) is not False:
            return None
        fase = 'verificar_formulario'
        _registrar(registrar,'contexto','verificar_formulario')
        if formulario_resumo_reconhecido(imagem) is None:
            _registrar(registrar,'contexto','formulario_nao_reconhecido')
            return None
        leituras = {}
        fase = 'medir_coluna'
        contexto = _contexto_coluna(imagem,registrar,leituras)
        if contexto is None:
            return None
        candidatos,fechar = contexto
        fase = 'conferir_botoes'
        # Procura também pelas leituras comuns; um OK fora da coluna
        # medida indica outro contexto e não autoriza a emissão.
        for motor,escala in (('tesseract',2),('tesseract',4),('windows',2),('windows',4)):
            try:
                for pos in _oks_exatos(imagem,motor,escala):
                    if not any(_dentro(pos,c) for c in candidatos):
                        _registrar(registrar,'contexto','outro_ok_exato',motor=motor,escala=escala)
                        return None
            except ExecucaoInterrompida:
                raise
            except Exception:
                continue
        # O fallback lê cada retângulo medido, mesmo quando tela cheia
        # não segmentou OK. Aceita somente o texto inteiro, sem correções.
        textos_fechar=_ler_botao(imagem,fechar,leituras,registrar)
        if textos_fechar != {'fechar'}:
            _registrar(registrar,'texto','texto_fechar_nao_confirmado',
                texto_esperado_lido='fechar' in textos_fechar,leituras_distintas=len(textos_fechar))
            return None
        confirmados=[]
        for c in candidatos:
            textos=_ler_botao(imagem,c,leituras,registrar)
            if textos=={'ok'}:confirmados.append(c)
            _registrar(registrar,'texto','ok_lido' if textos=={'ok'} else 'texto_ok_nao_confirmado',
                caixa=list(c),texto_esperado_lido='ok' in textos,leituras_distintas=len(textos))
        if len(confirmados)!=1:
            _registrar(registrar,'texto','texto_ok_ausente_ou_ambiguo',quantidade=len(confirmados))
            return None
        x,y,w,h = confirmados[0]
        _registrar(registrar,'fim','ok_confirmado',caixa=[x,y,w,h])
        return (x+w//2,y+h//2)
    except ExecucaoInterrompida:
        raise
    except Exception as erro:
        _registrar(registrar,'fim','leitura_ok_nao_confirmada',
            origem=fase,tipo_erro=type(erro).__name__)
        return None
