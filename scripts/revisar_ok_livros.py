"""Diagnóstico local do OK dos Livros: nenhuma tecla, clique ou emissão."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    origem=parser.add_mutually_exclusive_group(required=True)
    origem.add_argument('--imagem',type=Path,help='PNG local da aba Geral.')
    origem.add_argument('--ultima-falha',action='store_true',help='Última captura local da falha dos livros.')
    args=parser.parse_args(argv)
    caminho=args.imagem
    if args.ultima_falha:
        arquivos=list((ROOT/'capturas').glob('*erro_livros_conjuntos.png'))
        if not arquivos:
            print('Nenhuma captura local da falha dos livros encontrada.')
            return 1
        caminho=max(arquivos,key=lambda p:p.stat().st_mtime_ns)
    from PIL import Image
    from app.botao_livros import achar_ok_livros
    try:
        with Image.open(caminho) as arquivo:imagem=arquivo.convert('RGB')
        pos=achar_ok_livros(imagem,registrar=lambda d:print('LIVROS_OK '+json.dumps(d,ensure_ascii=False)))
        print('LIVROS_OK_DIAGNOSTICO '+json.dumps({'confirmado':pos is not None,'posicao':pos}))
        print('Nenhum clique, tecla ou emissão foi executado. Captura permanece neste PC.')
        return 0 if pos is not None else 1
    except (OSError,ValueError,RuntimeError) as erro:
        print('LIVROS_OK_DIAGNOSTICO '+json.dumps({'confirmado':False,'tipo':type(erro).__name__}))
        print('Nenhum clique, tecla ou emissão foi executado.')
        return 1


if __name__=='__main__':raise SystemExit(main())
