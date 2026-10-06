"""Diagnóstico local somente de estrutura; não imprime conteúdo fiscal."""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.arquivos import _compactar


def resumo(texto, inicio, fim, tipo):
    compacto = _compactar(texto)
    titulo = {'saidas': 'REGISTRODESAIDAS', 'entradas': 'REGISTRODEENTRADAS'}[tipo]
    indice = compacto.find(titulo)
    cabecalho = compacto[indice:] if indice >= 0 else ''
    limites = [cabecalho.find(m) for m in ('CODIFICACAO', 'VALORESFISCAIS') if m in cabecalho]
    cabecalho = cabecalho[:min(limites)] if limites else cabecalho[:2500]
    padrao = re.escape(_compactar(inicio)) + r'(?:A|ATE|[-–])' + re.escape(_compactar(fim))
    linhas = [f'Tamanho do texto: {len(texto)}; compacto: {len(compacto)}',
              'Posicoes no texto compacto (-1 = ausente):']
    for marcador in (titulo, 'EMPRESA', 'CNPJ', 'CODIFICACAO', 'VALORESFISCAIS'):
        linhas.append(f'  {marcador}: {compacto.find(marcador)}')
    for rotulo, valor in (('Data inicial esperada', inicio), ('Data final esperada', fim)):
        alvo = _compactar(valor)
        linhas.append(f'  {rotulo}: pagina={compacto.find(alvo)}; cabecalho={cabecalho.find(alvo)}')
    inicial = compacto.find(_compactar(inicio))
    final = compacto.find(_compactar(fim))
    distancia = final - inicial - len(_compactar(inicio)) if inicial >= 0 and final >= 0 else None
    linhas.append(f'Distancia entre datas: {distancia}')
    linhas.append(f'Periodo corresponde na pagina: {bool(re.search(padrao, compacto))}')
    linhas.append(f'Periodo corresponde no cabecalho atual: {bool(re.search(padrao, cabecalho))}')
    return '\n'.join(linhas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo', nargs='?', type=Path)
    parser.add_argument('--inicio', default='01/08/2026')
    parser.add_argument('--fim', default='31/08/2026')
    parser.add_argument('--tipo', choices=['saidas', 'entradas'], default='saidas')
    args = parser.parse_args()
    caminho = args.arquivo
    if caminho is None:
        pasta = Path(__file__).resolve().parent.parent / 'saida'
        arquivos = list(pasta.glob('exportacao_*.pdf'))
        if not arquivos:
            print('Nenhum PDF temporario encontrado em saida/.')
            return 1
        caminho = max(arquivos, key=lambda p: p.stat().st_mtime_ns)
    print('Diagnostico local do PDF temporario mais recente (ou arquivo informado).')
    print(f'Periodo esperado: {args.inicio} a {args.fim}; livro: {args.tipo}.')
    print('Saida contem apenas posicoes e resultados; nao imprime nomes, CNPJ ou valores.')
    try:
        from pypdf import PdfReader
        with caminho.open('rb') as arquivo:
            leitor = PdfReader(arquivo, strict=True)
            if not leitor.pages:
                print('PDF sem paginas.')
                return 1
            print(f'Paginas: {len(leitor.pages)}')
            pagina = leitor.pages[0]
            for modo in ('padrao', 'layout'):
                try:
                    texto = pagina.extract_text(**({'extraction_mode': 'layout'} if modo == 'layout' else {})) or ''
                    print(f'\nExtracao: {modo}')
                    print(resumo(texto, args.inicio, args.fim, args.tipo))
                except Exception as erro:
                    print(f'Extracao {modo} falhou: {type(erro).__name__}.')
    except Exception as erro:
        print(f'Nao consegui ler o PDF: {type(erro).__name__}.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
