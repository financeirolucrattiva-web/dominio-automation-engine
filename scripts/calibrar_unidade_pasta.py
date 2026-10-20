"""Guarda somente o campo Client C confirmado pelo operador; não clica/emite."""
import argparse
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    origem=parser.add_mutually_exclusive_group(required=True)
    origem.add_argument('--ao-vivo',action='store_true')
    origem.add_argument('--imagem',type=Path,help='Captura completa do Procurar Pasta que você conferiu.')
    parser.add_argument('--client-c',required=True,help='Letra que você conferiu visualmente em Client C, por exemplo M.')
    args=parser.parse_args(argv)
    letra=args.client_c.upper()
    if not re.fullmatch('[A-Z]',letra):parser.error('Informe uma única letra de A a Z.')
    from PIL import Image
    from app import tela,seletor_pasta as seletor,referencia_unidade
    try:
        if args.ao_vivo:
            print('Confira Client C ('+letra+':) no Procurar Pasta e clique no vazio da árvore.',flush=True)
            print('Volte a essa tela nos próximos 5 segundos. Somente o campo será guardado; não há cliques ou emissão.',flush=True)
            time.sleep(5); imagem=tela.capturar_tela()
        else:
            with Image.open(args.imagem) as f:imagem=f.convert('RGB')
        d=seletor.medir_dialogo(imagem,somente_unidade=True,usar_referencia=False)
        if d['lista'] is not None:raise ValueError('Feche a lista de unidades antes de calibrar.')
        assinatura=seletor._assinatura_unidade(imagem,d)
        if assinatura is not None and re.fullmatch(r'(servidor|client[a-z]):[a-z]',assinatura[1]):
            if assinatura[1]!='clientc:'+letra.lower():
                raise ValueError('O texto reconhecido contradiz a unidade informada; referência não gravada.')
        resultado=referencia_unidade.gravar(imagem,d['combo'],letra)
        print('UNIDADE_REFERENCIA '+json.dumps({'gravada':True,**resultado},ensure_ascii=False))
        print('Referência visual guardada somente neste PC. Nenhuma pasta foi percorrida e nenhum relatório foi emitido.')
        return 0
    except (OSError,ValueError,RuntimeError) as erro:
        print('UNIDADE_REFERENCIA '+json.dumps({'gravada':False,'tipo':type(erro).__name__}))
        print('Confira Procurar Pasta, Client C com a letra informada, lista fechada e campo sem realce azul.')
        return 1


if __name__=='__main__':raise SystemExit(main())
