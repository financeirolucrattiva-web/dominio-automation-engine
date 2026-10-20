"""Área branca medida para um clique de foco no TreeView, sem ativação."""
import math


def medir_realce_campo(imagem,combo):
    """Realce azul dentro do combo; não afirma foco nativo por essa cor."""
    import cv2
    import numpy as np
    x,y,w,h=combo
    if min(x,y)<0 or h<5 or w<=h or x+w>imagem.width or y+h>imagem.height:return None
    rgb=np.asarray(imagem.crop((x+1,y+1,x+w-h,y+h-1)).convert('RGB'))
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    azul=((hsv[:,:,0]>=90)&(hsv[:,:,0]<=135)&(hsv[:,:,1]>100)&(hsv[:,:,2]>70)).astype('uint8')
    contornos,_=cv2.findContours(azul,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    caixas=[cv2.boundingRect(c) for c in contornos if cv2.contourArea(c)>h]
    caixas=[c for c in caixas if c[2]>2*c[3] and .35*h<=c[3]<=h]
    if len(caixas)!=1:return None
    bx,by,bw,bh=caixas[0]
    return (x+1+bx,y+1+by,bw,bh)


def _interior(imagem,detalhes):
    if detalhes.get('lista') is not None:return None
    x,y,w,h=detalhes['arvore']; cx,cy,cw,ch=detalhes['combo']
    if min(x,y,cx,cy)<0 or ch<=0 or x+w>imagem.width or y+h>imagem.height:return None
    # Altura medida do combo reserva bordas e a coluna da barra lateral.
    area=(x+ch,y+max(1,ch//2),x+w-2*ch,y+h-max(1,ch//2))
    return area if area[2]>area[0] and area[3]>area[1] else None


def confirmar_vazio(imagem,detalhes,candidato):
    """Relê a área atual; não reaproveita clique após movimento do diálogo."""
    import numpy as np
    if candidato is None or tuple(detalhes['arvore'])!=tuple(candidato['arvore']):return False
    if tuple(detalhes['combo'])!=tuple(candidato['combo']):return False
    interior=_interior(imagem,detalhes)
    if interior is None:return False
    x,y,d,b=candidato['area']
    if not (interior[0]<=x<d<=interior[2] and interior[1]<=y<b<=interior[3]):return False
    return bool(np.all(np.asarray(imagem.crop((x,y,d,b)).convert('RGB'))>=245))


def localizar_vazio(imagem,detalhes):
    """Um ponto branco atual, afastado de texto, bordas e barra medida.

    O clique pode mudar a seleção da árvore. O chamador precisa reler a
    unidade e reiniciar a raiz antes de navegar, sem usar a seleção antiga.
    """
    import cv2
    import numpy as np
    interior=_interior(imagem,detalhes)
    if interior is None:return None
    x,y,d,b=interior
    pixels=np.asarray(imagem.crop(interior).convert('RGB'))
    branco=np.all(pixels>=245,axis=2).astype('uint8')
    # Borda preta artificial é só para medir distância dentro da ROI.
    branco=np.pad(branco,1,constant_values=0)
    distancia=cv2.distanceTransform(branco,cv2.DIST_L2,5)
    py,px=np.unravel_index(int(np.argmax(distancia)),distancia.shape)
    raio=max(2,detalhes['combo'][3]//4)
    if distancia[py,px]<math.sqrt(2)*raio:return None
    px=x+int(px)-1; py=y+int(py)-1
    candidato={'posicao':(px,py),'area':(px-raio,py-raio,px+raio+1,py+raio+1),
               'arvore':tuple(detalhes['arvore']),'combo':tuple(detalhes['combo'])}
    return candidato if confirmar_vazio(imagem,detalhes,candidato) else None
