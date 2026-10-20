"""Referência local explícita da unidade Client C; comparação RGB exata."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from PIL import Image

ARQUIVO=Path(__file__).resolve().parents[1]/'data'/'referencia_unidade_pasta.json'
LIMITE=256*1024


def gravar(imagem,combo,letra,*,arquivo=None):
    """O operador declara Client C/letra na captura atual, sem inferir OCR."""
    from app.foco_seletor import medir_realce_campo
    from app.seletor_pasta import _area_unidade
    import numpy as np
    letra=str(letra).upper()
    x,y,w,h=combo
    if not re.fullmatch('[A-Z]',letra) or min(x,y)<0 or w<=h+4 or h<=4:
        raise ValueError('Unidade ou geometria inválida.')
    if x+w>imagem.width or y+h>imagem.height or w>2000 or h>200:
        raise ValueError('Campo fora dos limites da captura.')
    if medir_realce_campo(imagem,combo) is not None:
        raise ValueError('Clique no vazio da árvore para tirar o realce azul da unidade antes de calibrar.')
    recorte=imagem.crop(_area_unidade(combo)).convert('RGB')
    tinta=np.asarray(recorte.convert('L'))<128
    ys,xs=np.nonzero(tinta)
    if len(xs)<h or int(xs.max())-int(xs.min())<2*h:
        raise ValueError('Campo da unidade sem texto suficiente; referência não gravada.')
    buffer=io.BytesIO(); recorte.save(buffer,format='PNG'); png=buffer.getvalue()
    dados={'versao':1,'tipo':'client_c','letra':letra,'confirmada_pelo_operador':True,
           'combo_origem':list(combo),'imagem_origem':list(imagem.size),
           'origem_sha256':hashlib.sha256(imagem.convert('RGB').tobytes()).hexdigest(),
           'dimensoes':list(recorte.size),'png_sha256':hashlib.sha256(png).hexdigest(),
           'png':base64.b64encode(png).decode('ascii')}
    caminho=Path(arquivo) if arquivo is not None else ARQUIVO
    caminho.parent.mkdir(parents=True,exist_ok=True)
    temporario=None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent,delete=False) as f:
            temporario=Path(f.name)
            f.write(json.dumps(dados).encode('utf-8')); f.flush(); os.fsync(f.fileno())
        os.replace(temporario,caminho)
    finally:
        if temporario is not None:temporario.unlink(missing_ok=True)
    return {'tipo':'client_c','letra':letra,'dimensoes':list(recorte.size)}


def reconhecer(recorte,*,arquivo=None):
    """Nada é redimensionado, suavizado, mascarado ou aceito por tolerância."""
    caminho=Path(arquivo) if arquivo is not None else ARQUIVO
    try:
        with caminho.open('rb') as f:conteudo=f.read(LIMITE+1)
        if len(conteudo)>LIMITE:return None
        d=json.loads(conteudo)
        if (not isinstance(d,dict) or type(d.get('versao')) is not int or d['versao']!=1
                or d.get('tipo')!='client_c' or d.get('confirmada_pelo_operador') is not True
                or not isinstance(d.get('letra'),str) or not re.fullmatch('[A-Z]',d['letra'])):return None
        dims=d['dimensoes']; combo=d['combo_origem']; origem=d['imagem_origem']
        if (len(dims)!=2 or len(combo)!=4 or len(origem)!=2
                or any(type(v) is not int for v in (*dims,*combo,*origem))):return None
        x,y,w,h=combo
        if (min(x,y)<0 or not 4<h<=200 or not h+4<w<=2000
                or min(origem)<=0 or x+w>origem[0] or y+h>origem[1]
                or dims!=[w-h-2,h-4] or tuple(dims)!=recorte.size):return None
        if not isinstance(d.get('origem_sha256'),str) or not re.fullmatch('[a-f0-9]{64}',d['origem_sha256']):return None
        png=base64.b64decode(d['png'],validate=True)
        if hashlib.sha256(png).hexdigest()!=d.get('png_sha256'):return None
        with Image.open(io.BytesIO(png)) as referencia:
            if referencia.format!='PNG' or referencia.mode!='RGB' or referencia.size!=tuple(dims):return None
            if referencia.tobytes()!=recorte.convert('RGB').tobytes():return None
        return {'tipo':'client_c','letra':d['letra'],'origem':'calibracao_visual_local'}
    except (OSError,ValueError,KeyError,TypeError,OverflowError,Image.DecompressionBombError):
        return None
