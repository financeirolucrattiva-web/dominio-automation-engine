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
    d=None
    fase='capturar'
    try:
        if args.ao_vivo:
            print('Confira Client C ('+letra+':) no Procurar Pasta e clique no vazio da árvore.',flush=True)
            print('Volte a essa tela nos próximos 5 segundos. Somente o campo será guardado; não há cliques ou emissão.',flush=True)
            time.sleep(5); imagem=tela.capturar_tela()
        else:
            with Image.open(args.imagem) as f:imagem=f.convert('RGB')
        fase='medir_dialogo'
        d=seletor.medir_dialogo(imagem,somente_unidade=True,usar_referencia=False)
        fase='conferir_unidade'
        if d['lista'] is not None:
            raise referencia_unidade.CalibracaoUnidadeRecusada('lista_aberta')
        assinatura=seletor._assinatura_unidade(imagem,d)
        if assinatura is not None and re.fullmatch(r'(servidor|client[a-z]):[a-z]',assinatura[1]):
            if assinatura[1]!='clientc:'+letra.lower():
                raise referencia_unidade.CalibracaoUnidadeRecusada('identidade_contraditoria')
        fase='gravar_referencia'
        resultado=referencia_unidade.gravar(imagem,d['combo'],letra)
        print('UNIDADE_REFERENCIA '+json.dumps({'gravada':True,**resultado},ensure_ascii=False))
        print('Referência visual guardada somente neste PC. Nenhuma pasta foi percorrida e nenhum relatório foi emitido.')
        return 0
    except (OSError,ValueError,RuntimeError) as erro:
        if isinstance(erro,referencia_unidade.CalibracaoUnidadeRecusada):
            motivo=erro.motivo
        else:
            motivo={'capturar':'captura_indisponivel','medir_dialogo':'dialogo_nao_confirmado',
                    'gravar_referencia':'falha_salvar_referencia' if isinstance(erro,OSError)
                    else 'gravacao_nao_concluida'}.get(fase,'gravacao_nao_concluida')
        resultado={'gravada':False,'tipo':type(erro).__name__,'fase':fase,'motivo':motivo}
        if d is not None:
            from app.foco_seletor import medir_realce_campo
            resultado.update(combo=list(d['combo']),lista_aberta=d['lista'] is not None,
                realce_no_campo=medir_realce_campo(imagem,d['combo']) is not None)
            # Usa a MESMA captura recusada e salva só o campo medido.
            # Nunca salva a tela inteira nem executa uma segunda captura.
            try:
                from scripts.revisar_seletor_pasta import salvar_recorte_unidade
                resultado['recorte_local']=salvar_recorte_unidade(imagem,d['combo'])
            except (OSError,ValueError,RuntimeError):
                resultado['recorte_salvo']=False
        print('UNIDADE_REFERENCIA '+json.dumps(resultado,ensure_ascii=False))
        print(referencia_unidade.MOTIVOS_CALIBRACAO[motivo])
        print('Nenhum clique ou relatório foi executado; a referência anterior foi preservada.')
        return 1


if __name__=='__main__':raise SystemExit(main())
