"""Lê datas do Resumo aberto; não troca empresa, digita ou emite."""
import argparse
import json
from pathlib import Path
import re
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def dados_limitados(dados,escala):
    """Rótulos conhecidos e datas alinhadas; descarta todos os demais tokens."""
    palavras=[{'texto':str(t),'x':dados['left'][i]/escala,'y':dados['top'][i]/escala,
               'w':dados['width'][i]/escala,'h':dados['height'][i]/escala}
              for i,t in enumerate(dados['text']) if str(t).strip()]
    rotulos=[p for p in palavras if p['texto'].rstrip(':').casefold() in ('data','inicial','final')]
    resultado={'rotulos':[{'rotulo':p['texto'].rstrip(':').casefold(),
                          'caixa':[p[k] for k in ('x','y','w','h')]} for p in rotulos]}
    datas=[]
    for p in palavras:
        if not re.fullmatch(r'[0-9]{2}/[0-9]{2}/[0-9]{4}',p['texto']):continue
        if not any(r['texto'].rstrip(':').casefold() in ('inicial','final')
                   and p['x']>r['x']+r['w']
                   and max(p['y'],r['y'])<min(p['y']+p['h'],r['y']+r['h']) for r in rotulos):continue
        datas.append({'valor':p['texto'],'caixa':[p[k] for k in ('x','y','w','h')]})
    resultado['datas_na_linha_dos_campos']=datas
    return resultado


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    imagens=parser.add_mutually_exclusive_group()
    imagens.add_argument('--imagem',type=Path,help='PNG local do formulário, sem desktop.')
    imagens.add_argument('--ultima-falha',action='store_true',
        help='Analisa o PNG mais recente de erro_periodo_resumo ou erro_ok_resumo; não opera o desktop.')
    parser.add_argument('--conferir-ok',action='store_true',help='Também lê o botão OK; não clica.')
    args=parser.parse_args(argv)
    if args.ultima_falha:
        candidatos=[p for padrao in ('*erro_periodo_resumo.png','*erro_ok_resumo.png')
                    for p in (ROOT/'capturas').glob(padrao)]
        if not candidatos:
            print('Nenhuma captura de falha do período ou OK do Resumo encontrada em capturas/. Não houve alteração ou emissão.')
            return 1
        args.imagem=max(candidatos,key=lambda p:p.stat().st_mtime_ns)
        print('Analisando a captura local mais recente da falha do período ou OK; nenhuma nova execução será iniciada.')
    if not args.imagem and sys.platform!='win32':parser.error('Captura ao vivo requer Windows; use --imagem para leitura de PNG.')
    try:
        from PIL import Image
        from app import tela
        from app.formulario_resumo import campos_periodo,resumo_leitura
    except Exception:
        print('Componentes locais de imagem/OCR indisponíveis. Não houve alteração ou emissão.')
        return 1
    try:
        if args.imagem:
            with Image.open(args.imagem) as arquivo:imagem=arquivo.convert('RGB')
        else:
            print('Deixe Resumo por acumulador aberto e inteiro visível nos próximos 5 segundos. Este diagnóstico não clica, digita ou emite.',flush=True)
            time.sleep(5)
            imagem=tela.capturar_tela()
            tela.salvar(imagem,ROOT/'capturas'/f'revisao_periodo_resumo_{uuid.uuid4().hex[:10]}.png')
            print('Captura salva somente no PC, em capturas/.')
    except Exception:
        print('Imagem/captura indisponível. Confira o arquivo local, a sessão e as permissões. Não houve alteração ou emissão.')
        return 1
    titulo=None
    for escala in (2,4):
        try:titulo=tela.achar_texto_ou_no_centro(imagem,'Resumo por acumulador',escala=escala)
        except Exception:titulo=None
        if titulo is not None:break
        try:titulo=tela.achar_texto_windows(imagem,'Resumo por acumulador',escala=escala)
        except Exception:titulo=None
        if titulo is not None:break
    if titulo is None:
        print('RESUMO_FORMULARIO '+json.dumps({'titulo_reconhecido':False,'dimensoes':list(imagem.size)}))
        print('Formulário do Resumo não reconhecido. Não houve alteração ou emissão.')
        return 1
    print('RESUMO_FORMULARIO '+json.dumps({'titulo_reconhecido':True,
        'posicao':list(titulo),'dimensoes':list(imagem.size)}))
    for motor,escala in (('tesseract',2),('tesseract',4),('windows',2)):
        try:
            dados=tela._ler_dados_ocr(imagem,escala) if motor=='tesseract' else tela.ler_dados_ocr_windows(imagem,escala)
            if dados is None:
                print(f'{motor} {escala}x: indisponível.')
                continue
            print('RESUMO_OCR '+json.dumps({'motor':motor,'escala':escala,**dados_limitados(dados,escala)},ensure_ascii=False))
            try:
                campos=resumo_leitura(campos_periodo(dados,escala))
            except ValueError:
                print(f'{motor} {escala}x: não confirmou rótulos e duas datas completas.')
                continue
            print('RESUMO_LEITURA '+json.dumps({'motor':motor,'escala':escala,'campos':campos},ensure_ascii=False))
        except Exception:
            print(f'{motor} {escala}x: leitura indisponível. Confira a instalação local do OCR.')
    print('Nenhum campo foi alterado e nenhum relatório foi emitido.')
    try:
        from app.leitura_resumo import ler_campos
        campos=ler_campos(imagem,registrar=lambda detalhe:print('RESUMO_RECORTE '+json.dumps(detalhe,ensure_ascii=False)),
            salvar_recorte=lambda recorte,nome:tela.salvar(recorte,ROOT/'capturas'/('resumo_data_'+nome+'.png')))
        print('RESUMO_LEITURA_CAMPOS '+json.dumps(resumo_leitura(campos),ensure_ascii=False))
        if args.conferir_ok:
            from app.botoes_formulario import achar_ok_resumo
            print('Analisando botão OK na imagem salva; somente leitura, sem clique.',flush=True)
            pos=achar_ok_resumo(imagem,registrar=lambda d:print('RESUMO_BOTAO '+json.dumps(d,ensure_ascii=False),flush=True))
            print('RESUMO_BOTAO_OK '+json.dumps({'confirmado':pos is not None,'posicao':pos}))
            return 0 if pos is not None else 1
        return 0
    except Exception:
        print('Leitura dos campos não confirmada por recortes/concordância. Não houve alteração ou emissão.')
        return 1


if __name__=='__main__':raise SystemExit(main())
