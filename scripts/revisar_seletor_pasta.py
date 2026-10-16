"""Revisa captura local do Procurar Pasta sem clicar, digitar ou emitir."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    origem=parser.add_mutually_exclusive_group(required=True)
    origem.add_argument('--imagem',type=Path,help='PNG local do seletor.')
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
    from app import seletor_pasta as seletor
    try:
        with Image.open(caminho) as arquivo:imagem=arquivo.convert('RGB')
        detalhes=seletor.medir_dialogo(imagem)
        no=seletor._no_selecionado(imagem,detalhes)
        resultado={'dialogo_confirmado':True,'combo':list(detalhes['combo']),
                   'arvore':list(detalhes['arvore']),'linhas_visiveis':len(seletor._nos(detalhes)),
                   'selecao_confirmada':no is not None,
                   'ok_confirmado':seletor._ok_final(imagem,detalhes) is not None}
        print('PASTA_DIAGNOSTICO '+json.dumps(resultado,ensure_ascii=False))
    except (OSError,ValueError,RuntimeError) as erro:
        print('PASTA_DIAGNOSTICO '+json.dumps({'dialogo_confirmado':False,'tipo':type(erro).__name__}))
        print('Nenhum clique, tecla ou emissão foi executado.')
        return 1
    print('Nenhum clique, tecla ou emissão foi executado. Captura e nomes de pastas permanecem neste PC.')
    return 0


if __name__=='__main__':raise SystemExit(main())
