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
    parser.add_argument('--pasta',help='Confere se esse nome está visível no ramo atual, sem clicar.')
    parser.add_argument('--somente-unidade',action='store_true',
                        help='Confere somente campo/lista de unidades, sem OCR da árvore ou do OK.')
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
        unidade=seletor.medir_dialogo(imagem,somente_unidade=True)
        if args.somente_unidade:
            resultado={'dialogo_confirmado':True,'combo':list(unidade['combo']),
                       'lista_unidades_aberta':unidade['lista'] is not None,
                       'client_c_letras_no_campo':[letra for letra in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                           if seletor._drive_selecionado(unidade,letra)]}
            print('PASTA_DIAGNOSTICO '+json.dumps(resultado,ensure_ascii=False))
            print('Somente a unidade foi analisada. Nenhum clique, tecla ou emissão foi executado.')
            return 0
        if unidade['lista'] is not None:
            resultado={'dialogo_confirmado':True,'combo':list(unidade['combo']),
                       'lista_unidades_aberta':True,'lista':list(unidade['lista']),
                       'realce_confirmado':seletor._realce_unidade(imagem,unidade) is not None,
                       'client_c_letras_no_campo':[letra for letra in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                           if seletor._drive_selecionado(unidade,letra)],
                       'arvore_liberada':False}
            print('PASTA_DIAGNOSTICO '+json.dumps(resultado,ensure_ascii=False))
            print('Nenhum clique, tecla ou emissão foi executado. A lista de unidades estava aberta na captura.')
            return 0
        detalhes=seletor._completar_dialogo(unidade)
        no=seletor._no_selecionado(imagem,detalhes)
        resultado={'dialogo_confirmado':True,'combo':list(detalhes['combo']),
                   'lista_unidades_aberta':False,
                   'arvore':list(detalhes['arvore']),'linhas_visiveis':len(seletor._nos(detalhes)),
                   'client_c_letras_confirmadas':[letra for letra in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                       if seletor._drive_selecionado(detalhes,letra)],
                   'selecao_confirmada':no is not None,
                   'ok_confirmado':seletor._ok_final(imagem,detalhes) is not None}
        if args.pasta:
            alvo=(no if no and no['nome']==seletor._normalizar(args.pasta)
                  else seletor._alvo_visivel(detalhes,no,args.pasta) if no else None)
            resultado['pasta_visivel_no_ramo']=alvo is not None
            resultado['posicao_pasta']=list(alvo['posicao']) if alvo else None
            if no and seletor._normalizar(args.pasta)=='users':
                from app.arvore_raiz import localizar_raiz, medir_seta_baixo
                altura=max(p['h'] for p in no['linha'])
                recorte=localizar_raiz(imagem,detalhes,args.pasta,no['x'],altura)
                medicao={}
                barra=medir_seta_baixo(imagem,detalhes['arvore'],altura,
                    combo=detalhes['combo'],registrar=medicao.update)
                resultado['pasta_por_recorte_confirmada']=recorte is not None
                resultado['seta_rolagem_confirmada']=barra is not None
                resultado['medicao_barra']=medicao
        print('PASTA_DIAGNOSTICO '+json.dumps(resultado,ensure_ascii=False))
    except (OSError,ValueError,RuntimeError) as erro:
        print('PASTA_DIAGNOSTICO '+json.dumps({'dialogo_confirmado':False,'tipo':type(erro).__name__}))
        print('Nenhum clique, tecla ou emissão foi executado.')
        return 1
    print('Nenhum clique, tecla ou emissão foi executado. Captura e nomes de pastas permanecem neste PC.')
    return 0


if __name__=='__main__':raise SystemExit(main())
