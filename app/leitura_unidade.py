"""Contraste local do campo Unidade, sem reconstruir texto ou pontuação."""


def normalizar_unidade(imagem):
    """Inverte o realce azul preservando a cobertura dos glifos em cinza.

    O recorte já vem da borda medida do combo. A mistura de azul e branco
    é contínua: limiar por saturação apagava traços finos antialiasados.
    Cores que não pertencem a essa mistura permanecem como no original.
    """
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
        regiao=rgb[y:y+h,x:x+w].astype('float32')
        fundo=np.median(regiao[azul[y:y+h,x:x+w].astype(bool)],axis=0)
        vetor=255-fundo
        norma=float(np.dot(vetor,vetor))
        if norma<=0:continue
        cobertura=np.clip(np.sum((regiao-fundo)*vetor,axis=2)/norma,0,1)
        estimada=fundo+cobertura[:,:,None]*vetor
        # Um caret laranja não vira tinta preta nem é apagado. Só altera
        # pixels compatíveis com o fundo azul e a tinta clara observados.
        compativeis=np.max(np.abs(regiao-estimada),axis=2)<=24
        cinza=np.rint(255*(1-cobertura)).astype('uint8')
        destino=saida[y:y+h,x:x+w]
        destino[compativeis]=np.repeat(cinza[:,:,None],3,axis=2)[compativeis]
    return Image.fromarray(saida)
