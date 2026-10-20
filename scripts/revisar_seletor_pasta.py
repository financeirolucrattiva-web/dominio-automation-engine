"""Revisa captura local do Procurar Pasta sem clicar, digitar ou emitir."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def salvar_recorte_unidade(imagem,combo):
    """Contato local só do combo; não inclui árvore, relatório ou empresa."""
    import uuid
    from PIL import Image, ImageDraw
    from app.leitura_resumo import normalizar_selecao
    from app import seletor_pasta as seletor
    x,y,w,h=combo
    if min(x,y)<0 or w<=h+4 or h<=4 or x+w>imagem.width or y+h>imagem.height:
        raise ValueError('Campo Unidade fora dos limites da captura.')
    area=seletor._area_unidade(combo)
    campo=imagem.crop((x,y,x+w,y+h)).resize((w*4,h*4),Image.Resampling.NEAREST)
    normal=normalizar_selecao(imagem.crop(area))
    normal=normal.resize((normal.width*4,normal.height*4),Image.Resampling.NEAREST)
    folha=Image.new('RGB',(campo.width+16,campo.height+normal.height+68),'white')
    desenho=ImageDraw.Draw(folha)
    desenho.text((8,6),'Campo completo (4x); vermelho: area enviada ao OCR',fill='black')
    folha.paste(campo,(8,24))
    desenho.rectangle((8+(area[0]-x)*4,24+(area[1]-y)*4,
                       8+(area[2]-x)*4-1,24+(area[3]-y)*4-1),outline='red',width=1)
    desenho.text((8,campo.height+32),'Recorte normalizado (4x)',fill='black')
    folha.paste(normal,(8,campo.height+52))
    pasta=ROOT/'capturas'; pasta.mkdir(exist_ok=True)
    nome='unidade_ocr_'+uuid.uuid4().hex[:8]+'.png'
    folha.save(pasta/nome)
    return 'capturas/'+nome


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    origem=parser.add_mutually_exclusive_group(required=True)
    origem.add_argument('--imagem',type=Path,help='PNG local do seletor.')
    origem.add_argument('--ultima-falha',action='store_true',help='Última captura local da falha dos livros.')
    parser.add_argument('--pasta',help='Confere se esse nome está visível no ramo atual, sem clicar.')
    parser.add_argument('--somente-unidade',action='store_true',
                        help='Confere somente campo/lista de unidades, sem OCR da árvore ou do OK.')
    parser.add_argument('--detalhar-unidade',action='store_true',
                        help='Com --somente-unidade: motivos por leitor e recorte do campo salvo localmente.')
    args=parser.parse_args(argv)
    if args.detalhar_unidade and not args.somente_unidade:
        parser.error('--detalhar-unidade requer --somente-unidade.')
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
        observacoes=[]
        unidade=(seletor.medir_dialogo(imagem,somente_unidade=True,
                    registrar_unidade=observacoes.append) if args.detalhar_unidade
                 else seletor.medir_dialogo(imagem,somente_unidade=True))
        for observacao in observacoes:
            print('PASTA_UNIDADE_OCR '+json.dumps(observacao,ensure_ascii=False))
        if args.somente_unidade:
            resultado={'dialogo_confirmado':True,'combo':list(unidade['combo']),
                       'lista_unidades_aberta':unidade['lista'] is not None,
                       'client_c_letras_no_campo':[letra for letra in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                           if seletor._drive_selecionado(unidade,letra)]}
            if args.detalhar_unidade:
                resultado['recorte_local']=salvar_recorte_unidade(imagem,unidade['combo'])
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
