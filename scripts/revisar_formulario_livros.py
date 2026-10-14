"""Diagnóstico local da aba Geral: captura/OCR, sem cliques ou emissão."""
import argparse
from pathlib import Path
import sys
import time
import uuid
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--imagem',type=Path,help='PNG local do formulário para leitura sem desktop.')
    args = parser.parse_args(argv)
    if args.imagem is None and sys.platform != 'win32':
        parser.error('Captura ao vivo requer Windows; use --imagem para diagnóstico local de PNG.')
    from PIL import Image
    from app import tela
    from app.formulario_livros import ler_selecao_com_ocr, ROTULOS
    from app.leitura_resumo import ler_campos
    if args.imagem:
        with Image.open(args.imagem) as arquivo:
            imagem = arquivo.convert('RGB')
    else:
        print('Deixe Livros Fiscais, aba Geral, visível nos próximos 5 segundos. Este diagnóstico não clica nem emite.',flush=True)
        time.sleep(5)  # preparação humana, não espera de geração
        imagem = tela.capturar_tela()
        destino = ROOT/'capturas'/f'revisao_livros_{uuid.uuid4().hex[:10]}.png'
        tela.salvar(imagem,destino)
        print(f'Captura guardada somente neste PC: {destino}')
    try:
        resultado = ler_selecao_com_ocr(imagem,registrar=lambda detalhe:
            print('LIVROS_SELECAO '+json.dumps(detalhe,ensure_ascii=False)))
    except ValueError as erro:
        print(f'Leitura não confirmada: {erro}')
        print('Nenhuma caixa foi alterada e nenhum relatório foi emitido.')
        return 1
    for tipo,livro in resultado['livros'].items():
        estado = 'marcada' if livro['marcada'] else 'desmarcada'
        print(f"{ROTULOS[tipo]}: {estado}; caixa medida: {livro['retangulo']}.")
    print('Outras opções de emissão marcadas:',sum(c['marcada'] for c in resultado['outros']))
    try:
        periodo=ler_campos(imagem,livros=True,registrar=lambda detalhe:
            print('LIVROS_PERIODO '+json.dumps(detalhe,ensure_ascii=False)),
            salvar_recorte=lambda recorte,nome:tela.salvar(recorte,ROOT/'capturas'/('livros_data_'+nome+'.png')))
        print('Inicial:',periodo['inicial']['valor'],'— campo:',periodo['inicial']['posicao'])
        print('Final:',periodo['final']['valor'],'— campo:',periodo['final']['posicao'])
    except ValueError:
        print('Caixas conferidas; leitura das datas não confirmada. Nenhum campo foi alterado ou relatório emitido.')
        return 1
    print('Diagnóstico concluído. Nenhuma caixa foi alterada e nenhum relatório foi emitido.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
