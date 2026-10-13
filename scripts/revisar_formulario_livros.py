"""Diagnóstico local da aba Geral: captura/OCR, sem cliques ou emissão."""
import argparse
from pathlib import Path
import sys
import time
import uuid

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
    from app.formulario_livros import ler_formulario, ROTULOS
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
    erros = []
    for escala in (2,4):
        try:
            resultado = ler_formulario(imagem,tela._ler_dados_ocr(imagem,escala),escala)
            break
        except ValueError as erro:
            erros.append(str(erro))
    else:
        dados = tela.ler_dados_ocr_windows(imagem,2)
        try:
            if dados is None:
                raise ValueError(erros[-1])
            resultado = ler_formulario(imagem,dados,2)
        except ValueError as erro:
            print(f'Leitura não confirmada: {erro}')
            print('Nenhuma caixa foi alterada e nenhum relatório foi emitido.')
            return 1
    for tipo,livro in resultado['livros'].items():
        estado = 'marcada' if livro['marcada'] else 'desmarcada'
        print(f"{ROTULOS[tipo]}: {estado}; caixa medida: {livro['retangulo']}.")
    print('Inicial:',resultado['periodo']['inicial']['valor'],'— campo:',resultado['periodo']['inicial']['posicao'])
    print('Final:',resultado['periodo']['final']['valor'],'— campo:',resultado['periodo']['final']['posicao'])
    print('Outras opções de emissão marcadas:',sum(c['marcada'] for c in resultado['outros']))
    print('Diagnóstico concluído. Nenhuma caixa foi alterada e nenhum relatório foi emitido.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
