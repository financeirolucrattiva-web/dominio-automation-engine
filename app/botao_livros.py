"""OK de Livros Fiscais medido na captura atual; nunca clica ou emite.

Datas/seleção são confirmadas pelo chamador na mesma captura. Este leitor
confirma título, geometria dos campos, coluna e texto literal dos botões.
"""
from app import tela
from app.controle_execucao import ExecucaoInterrompida, ponto_seguro
from app.formulario_livros import _palavras, _rotulo
from app.leitura_resumo import medir_campos, rotulos_periodo
from app.botoes_formulario import (_conferir_avisos, _retangulos, _ler_botao,
                                  _dentro, _oks_exatos)


def _registrar(registrar, fase, motivo, **detalhe):
    if registrar:
        registrar({'fase': fase, 'motivo': motivo, **detalhe})


def _contexto(imagem, registrar):
    contextos = []
    for motor, escala in (('tesseract', 2), ('tesseract', 4), ('windows', 2), ('windows', 4)):
        ponto_seguro()
        try:
            dados = (tela._ler_dados_ocr(imagem, escala) if motor == 'tesseract'
                     else tela.ler_dados_ocr_windows(imagem, escala))
            if dados is None:
                continue
            titulo = _rotulo(_palavras(dados, escala), 'Livros Fiscais')
            campos = medir_campos(imagem, rotulos_periodo(dados, escala, livros=True))
            if titulo['y']+titulo['h'] >= campos['inicial']['retangulo'][1]:
                raise ValueError('Ordem do formulário não confirmada.')
            altura = max(c['retangulo'][3] for c in campos.values())
            direita = max(c['retangulo'][0]+c['retangulo'][2] for c in campos.values())
            caixas = tuple(sorted(c for c in _retangulos(imagem, altura)
                if c[0] > direita and c[1] > titulo['y']+titulo['h']
                and c[1]+c[3] >= campos['inicial']['retangulo'][1]-max(altura, c[3])
                and c[1] <= campos['final']['retangulo'][1]+campos['final']['retangulo'][3]))
            contextos.append(caixas)
            _registrar(registrar, 'coluna', 'botoes_medidos', motor=motor, escala=escala,
                       campos={p: list(c['retangulo']) for p, c in campos.items()},
                       caixas=[list(c) for c in caixas])
        except ExecucaoInterrompida:
            raise
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError, OSError) as erro:
            _registrar(registrar, 'coluna', 'formulario_nao_confirmado', motor=motor,
                       escala=escala, tipo_erro=type(erro).__name__)
    if not contextos or len(set(contextos)) != 1 or not contextos[0]:
        _registrar(registrar, 'fim', 'coluna_ausente_ou_conflitante', leituras=len(contextos))
        return None
    return contextos[0]


def achar_ok_livros(imagem, registrar=None):
    """Retorna somente o centro do único OK confirmado; nenhuma ação de GUI."""
    _registrar(registrar, 'busca', 'analise_iniciada')
    ponto_seguro()
    with tela.reutilizar_ocr():
        resultado = _achar_na_captura(imagem, registrar)
    ponto_seguro()
    return resultado


def _achar_na_captura(imagem, registrar):
    try:
        if _conferir_avisos(imagem, registrar) is not False:
            _registrar(registrar, 'fim', 'modal_ou_leitura_indisponivel', confirmado=False)
            return None
        caixas = _contexto(imagem, registrar)
        if caixas is None:
            return None
        leituras = {}
        fechar = [c for c in caixas if _ler_botao(imagem, c, leituras, registrar) == {'fechar'}]
        oks = [c for c in caixas if _ler_botao(imagem, c, leituras, registrar) == {'ok'}]
        if len(fechar) != 1 or len(oks) != 1:
            _registrar(registrar, 'fim', 'texto_botoes_ausente_ou_ambiguo',
                       fechar_confirmados=len(fechar), ok_confirmados=len(oks), confirmado=False)
            return None
        ok, fechar = oks[0], fechar[0]
        tolerancia = min(ok[3], fechar[3])*.2
        if (ok[1]+ok[3] > fechar[1]
                or any(abs(ok[i]-fechar[i]) > tolerancia for i in (0, 2, 3))):
            _registrar(registrar, 'fim', 'coluna_botoes_divergente', confirmado=False)
            return None
        for motor, escala in (('tesseract', 2), ('tesseract', 4), ('windows', 2), ('windows', 4)):
            ponto_seguro()
            try:
                if any(not _dentro(pos, ok) for pos in _oks_exatos(imagem, motor, escala)):
                    _registrar(registrar, 'fim', 'outro_ok_reconhecido', confirmado=False)
                    return None
            except ExecucaoInterrompida:
                raise
            except (ValueError, KeyError, TypeError, IndexError, RuntimeError, OSError):
                continue
        _registrar(registrar, 'fim', 'ok_literal_confirmado', caixa=list(ok), confirmado=True)
        return ok[0]+ok[2]//2, ok[1]+ok[3]//2
    except ExecucaoInterrompida:
        raise
    except Exception as erro:
        _registrar(registrar, 'fim', 'leitura_ok_nao_confirmada',
                   tipo_erro=type(erro).__name__, confirmado=False)
        return None
