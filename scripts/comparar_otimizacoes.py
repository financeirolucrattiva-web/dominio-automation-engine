"""Compara o caminho classico e o otimizado das leituras OCR sobre capturas reais ja salvas.

Para cada captura e cada leitura, roda a MESMA imagem duas vezes: com todas as otimizacoes
desligadas (`otimizacoes._forcado = False`, o caminho que ja rodou contra o Dominio) e com todas
ligadas (`True`). Mede o tempo e confere se o resultado e identico: o valor devolvido OU, quando a
leitura levanta erro, a classe da excecao. Serve para provar que as otimizacoes mudam so a
velocidade, nunca a decisao.

Nao opera o Dominio, nao captura a tela e nao usa mouse nem teclado (o pyautogui e trocado por um
modulo que recusa qualquer acao). Nao altera nenhum arquivo.

PRIVACIDADE: as capturas sao telas reais de clientes. Este script nunca imprime nem grava texto
lido por OCR, recortes ou imagens. Mostra so nomes de arquivo, nomes de funcao, contagens,
booleanos, duracoes em segundos, nomes de classe de excecao e nomes de CAMPOS definidos no codigo
(como "inicial.posicao"). Tudo o que a aplicacao imprime durante a leitura e descartado.

Codigo de saida: 0 se tudo identico, 1 se houver divergencia (ou se uma otimizacao se desligar
sozinha durante a rodada), 2 se faltar pasta/capturas/otimizacoes, 130 se interrompido.
"""
import argparse
import contextlib
import io
import json
import os
import re
import sys
import threading
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

CAPTURAS_PADRAO = Path(r'C:\Users\darto\dominio-automation-engine\capturas')
OBRIGATORIA = 'depois_abrir_livros_fiscais.png'
LARGURA_MINIMA = 1000
ALTURA_MINIMA = 600
MAXIMO_PADRAO = 12
CLASSICO = 'classico'
OTIMIZADO = 'otimizado'
GRUPOS = ('selecao', 'campos', 'resumo', 'avisos', 'seletor', 'texto')
TEXTOS = ('Livros Fiscais', 'EFD Contribuições', 'Resumo por acumulador')
CHAVES_DO_SELETOR = ('combo', 'arvore', 'ok', 'botoes_ok')
SEPARADOR = '-' * 118


# ---------------------------------------------------------------------------------------------
# Escolha das capturas (funcoes puras)
# ---------------------------------------------------------------------------------------------

def sem_acentos(texto):
    """So para os nomes mostrados na tabela (o console do Windows nem sempre mostra acento)."""
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')


def tamanho_suficiente(largura, altura):
    """So telas inteiras do Dominio interessam; recortes e miniaturas ficam de fora."""
    return largura >= LARGURA_MINIMA and altura >= ALTURA_MINIMA


def _espacados(itens, quantidade):
    """`quantidade` itens espalhados por toda a lista (primeiro e ultimo incluidos)."""
    if quantidade <= 0:
        return []
    if quantidade >= len(itens):
        return list(itens)
    if quantidade == 1:
        return [itens[0]]
    passo = (len(itens) - 1) / (quantidade - 1)
    return [itens[round(i * passo)] for i in range(quantidade)]


def escolher_imagens(nomes, maximo, obrigatoria=OBRIGATORIA):
    """Ate `maximo` nomes, ordenados e espacados; `obrigatoria` entra sempre que existir."""
    nomes = sorted(set(nomes))
    maximo = max(1, int(maximo))
    if len(nomes) <= maximo:
        return nomes
    fixas = [obrigatoria] if obrigatoria in nomes else []
    restantes = [nome for nome in nomes if nome not in fixas]
    escolhidas = _espacados(restantes, maximo - len(fixas))
    return sorted(set(escolhidas) | set(fixas))


def listar_candidatas(pasta, filtros=()):
    """Nomes dos PNG (sem entrar em subpastas) com tamanho de tela inteira. Devolve (nomes, ignorados)."""
    from PIL import Image
    nomes = []
    ignorados = 0
    filtros = [f.casefold() for f in (filtros or ())]
    for caminho in sorted(Path(pasta).glob('*.png'), key=lambda c: c.name):
        if filtros and not any(f in caminho.name.casefold() for f in filtros):
            continue
        try:
            with Image.open(caminho) as arquivo:
                largura, altura = arquivo.size
        except Exception:
            ignorados += 1
            continue
        if tamanho_suficiente(largura, altura):
            nomes.append(caminho.name)
    return nomes, ignorados


# ---------------------------------------------------------------------------------------------
# Normalizacao e comparacao (funcoes puras)
# ---------------------------------------------------------------------------------------------

def _chaves_como_texto(valor):
    if isinstance(valor, dict):
        return {str(chave): _chaves_como_texto(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_chaves_como_texto(item) for item in valor]
    return valor


def normalizar_resultado(valor):
    """Texto JSON estavel do resultado: chaves em ordem, tupla igual a lista, resto via str."""
    try:
        return json.dumps(valor, sort_keys=True, default=str)
    except TypeError:  # chaves de tipos misturados nao ordenam: todas viram texto
        return json.dumps(_chaves_como_texto(valor), sort_keys=True, default=str)


def normalizar_excecao(erro):
    """De uma excecao vale so a classe; a mensagem nunca entra na comparacao."""
    return json.dumps({'excecao': type(erro).__name__}, sort_keys=True)


def selecionar_seletor(detalhes):
    """Do Procurar Pasta, compara so combo, arvore, ok e botoes_ok (a lista 'palavras' fica de fora).

    `botoes_ok` vem de um conjunto (ordem sem significado): entra ordenado."""
    resultado = {chave: detalhes.get(chave) for chave in CHAVES_DO_SELETOR}
    if resultado['botoes_ok'] is not None:
        resultado['botoes_ok'] = sorted(resultado['botoes_ok'])
    return resultado


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def delta_numerico_max(a, b):
    """Maior diferenca absoluta entre as folhas numericas de duas estruturas do mesmo formato.

    Devolve None se o formato difere ou se alguma folha NAO numerica e diferente."""
    if _numero(a) and _numero(b):
        return abs(a - b)
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return None
        deltas = [delta_numerico_max(a[chave], b[chave]) for chave in a]
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return None
        deltas = [delta_numerico_max(x, y) for x, y in zip(a, b)]
    else:
        return 0.0 if type(a) is type(b) and a == b else None
    if any(delta is None for delta in deltas):
        return None
    return max(deltas, default=0.0)


_CHAVE_SEGURA = re.compile(r'[a-z_][a-z0-9_]{0,31}')


def caminhos_diferentes(a, b, limite=6):
    """Onde duas estruturas diferem, so como CAMINHO (ex.: 'inicial.posicao[0]'), nunca o valor.

    Nomes de campo que nao parecem identificadores do codigo viram '*'."""
    achados = []

    def andar(x, y, caminho):
        if len(achados) >= limite:
            return
        if isinstance(x, dict) and isinstance(y, dict):
            if x.keys() != y.keys():
                achados.append(caminho + '{chaves}')
                return
            for chave in sorted(x):
                nome = chave if _CHAVE_SEGURA.fullmatch(str(chave)) else '*'
                andar(x[chave], y[chave], (caminho + '.' if caminho else '') + nome)
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                achados.append(caminho + '[tamanho]')
                return
            for i, (u, v) in enumerate(zip(x, y)):
                andar(u, v, f'{caminho}[{i}]')
        elif not (type(x) is type(y) and x == y):
            achados.append(caminho or '<raiz>')

    andar(a, b, '')
    return achados


@dataclass
class Execucao:
    """Uma rodada de uma leitura. `chave` nunca e impressa: so serve para comparar."""
    chave: str
    excecao: str = ''
    duracao: float = 0.0
    positivo: bool = False
    desligadas: tuple = ()
    contadores: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)


@dataclass
class Comparacao:
    identico: bool
    tipo: str  # identico | excecao_diferente | valor_x_excecao | numerico | estrutura_ou_texto
    delta: float = None
    caminhos: tuple = ()


def comparar(a, b):
    if a.chave == b.chave:
        return Comparacao(True, 'identico', 0.0)
    if a.excecao and b.excecao:
        return Comparacao(False, 'excecao_diferente')
    if a.excecao or b.excecao:
        return Comparacao(False, 'valor_x_excecao')
    estrutura_a, estrutura_b = json.loads(a.chave), json.loads(b.chave)
    delta = delta_numerico_max(estrutura_a, estrutura_b)
    return Comparacao(False, 'numerico' if delta is not None else 'estrutura_ou_texto', delta,
                      tuple(caminhos_diferentes(estrutura_a, estrutura_b)))


@dataclass
class Registro:
    """Resultado do A/B de uma leitura numa captura."""
    linha: str
    imagem: str
    classico: Execucao
    otimizado: Execucao
    comparacao: Comparacao
    positivo: bool = False  # o classico reconheceu/achou algo (nao levantou erro nem devolveu vazio)
    repeticao: dict = None  # so nas divergencias: {'ruido_classico': bool, 'ruido_otimizado': bool}
    informativos: list = field(default_factory=list)  # avisos que nao contam como divergencia
    memoria: dict = None  # so no teste da segunda chamada: {'gravou': bool, 'usou': bool}


def codigo_de_saida(registros):
    """0 se tudo identico; 1 se alguma leitura divergiu ou uma otimizacao se desligou sozinha."""
    for r in registros:
        if not r.comparacao.identico or r.classico.desligadas or r.otimizado.desligadas:
            return 1
    return 0


# ---------------------------------------------------------------------------------------------
# Execucao medida
# ---------------------------------------------------------------------------------------------

class Contadores:
    """Conta chamadas do OCR (Tesseract e Windows) e suas falhas; seguro entre threads."""
    NOMES = ('tesseract', 'tesseract_falhas', 'windows', 'windows_tempo_limite', 'windows_ocupado',
             'windows_falhas')

    def __init__(self):
        self._trava = threading.Lock()
        self._valores = dict.fromkeys(self.NOMES, 0)

    def somar(self, nome):
        with self._trava:
            self._valores[nome] += 1

    def zerar(self):
        with self._trava:
            self._valores = dict.fromkeys(self.NOMES, 0)

    def copiar(self):
        with self._trava:
            return dict(self._valores)


def instalar_contadores(contadores):
    """Embrulha o Tesseract e o leitor do Windows SO para contar chamadas; o resultado nao muda."""
    import pytesseract
    from app import ocr_limites
    original = pytesseract.image_to_data

    def tesseract_contado(*args, **kwargs):
        contadores.somar('tesseract')
        try:
            return original(*args, **kwargs)
        except BaseException:
            contadores.somar('tesseract_falhas')
            raise

    pytesseract.image_to_data = tesseract_contado
    leitor = ocr_limites.LEITOR_WINDOWS
    executar_windows = leitor.executar

    def windows_contado(*args, **kwargs):
        contadores.somar('windows')
        try:
            return executar_windows(*args, **kwargs)
        except ocr_limites.OCRTempoLimite:
            contadores.somar('windows_tempo_limite')
            raise
        except ocr_limites.OCRLeituraOcupada:
            contadores.somar('windows_ocupado')
            raise
        except BaseException:
            contadores.somar('windows_falhas')
            raise

    leitor.executar = windows_contado


def aguardar_leitor_windows_ocioso(limite=30.0):
    """Uma leitura do Windows que estourou o tempo continua viva em segundo plano e faria a rodada
    seguinte receber 'OCR ocupado'. Espera acabar para que uma rodada nao interfira na outra."""
    try:
        from app import ocr_limites
    except ImportError:
        return True
    leitor = ocr_limites.LEITOR_WINDOWS
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        atual = getattr(leitor, '_atual', None)
        if atual is None or atual['fim'].is_set():
            return True
        time.sleep(0.05)
    return False


def _nome_de_classe(texto):
    return texto if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,60}', str(texto)) else '?'


def executar(chamar, modo, *, preparar=None, simplificar=None, positivo=None, extras=None,
             modulo_otimizacoes=None, contadores=None, esperar_leitor=None):
    """Roda `chamar()` no modo pedido e devolve uma `Execucao`.

    Tudo o que a aplicacao imprimir e descartado. Excecoes (menos KeyboardInterrupt) viram so a classe."""
    if modulo_otimizacoes is None:
        from app import otimizacoes as modulo_otimizacoes
    (esperar_leitor or aguardar_leitor_windows_ocioso)()
    modulo_otimizacoes._forcado = modo == OTIMIZADO
    modulo_otimizacoes._desligadas.clear()
    if preparar is not None:
        preparar()
    if contadores is not None:
        contadores.zerar()
    saida = io.StringIO()
    valor, erro = None, None
    inicio = time.perf_counter()
    try:
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            valor = chamar()
    except Exception as excecao:
        erro = excecao
    duracao = time.perf_counter() - inicio
    desligadas = tuple(sorted((nome, _nome_de_classe(motivo))
                              for nome, motivo in modulo_otimizacoes._desligadas.items()))
    modulo_otimizacoes._desligadas.clear()
    contagens = contadores.copiar() if contadores is not None else {}
    if erro is not None:
        return Execucao(normalizar_excecao(erro), type(erro).__name__, duracao, False, desligadas, contagens)
    try:
        comparavel = simplificar(valor) if simplificar else valor
        chave = normalizar_resultado(comparavel)
        achou = bool(positivo(valor)) if positivo else valor is not None
        adicionais = extras(valor) if extras else {}
    except Exception as falha:  # defeito do comparador, nao da aplicacao: fica visivel na tabela
        return Execucao(normalizar_excecao(falha), 'ErroDoComparador:' + type(falha).__name__, duracao,
                        False, desligadas, contagens)
    return Execucao(chave, '', duracao, achou, desligadas, contagens, adicionais)


# ---------------------------------------------------------------------------------------------
# Casos (uma leitura da aplicacao cada)
# ---------------------------------------------------------------------------------------------

@dataclass
class Caso:
    nome: str
    chamar: object  # (imagem, modo) -> valor bruto
    preparar: object = None  # () -> None, antes de CADA rodada
    simplificar: object = None  # valor bruto -> o que sera comparado
    positivo: object = None  # valor bruto -> o classico reconheceu/achou?
    extras: object = None  # (valor bruto, imagem) -> dict em memoria (nunca impresso)
    informativos: object = None  # (classico, otimizado) -> [texto sem conteudo]
    separar_dialogo: bool = False  # linha 'com dialogo' x 'sem dialogo' conforme o classico


def _extras_seletor(detalhes, imagem, tela, normalizar):
    """Palavras da arvore (so em memoria) e se arvore/botoes cabem no recorte central 60% x 60%."""
    x, y, w, h = detalhes['arvore']
    palavras = tuple(sorted(normalizar(p['texto']) for p in detalhes['palavras']
                            if x < p['x'] and p['x'] + p['w'] < x + w and y < p['y'] and p['y'] + p['h'] < y + h))
    _, dx, dy = tela.recortar_centro(imagem)
    largura, altura = imagem.width - 2 * dx, imagem.height - 2 * dy

    def dentro(caixa):
        return (caixa[0] >= dx and caixa[1] >= dy and caixa[0] + caixa[2] <= dx + largura
                and caixa[1] + caixa[3] <= dy + altura)

    return {'palavras_arvore': palavras, 'arvore_no_centro': dentro(detalhes['arvore']),
            'botoes_no_centro': all(dentro(b) for b in detalhes.get('botoes_ok') or [])}


def _informativos_seletor(classico, otimizado):
    notas = []
    if not classico.extras or not otimizado.extras:
        return notas
    a, b = Counter(classico.extras['palavras_arvore']), Counter(otimizado.extras['palavras_arvore'])
    diferentes = sum(((a - b) + (b - a)).values())
    if diferentes:
        notas.append(f'palavras_da_arvore_diferentes={diferentes} '
                     f'(classico={sum(a.values())}, centro={sum(b.values())})')
    if not classico.extras['arvore_no_centro']:
        notas.append('arvore_fora_do_recorte_central')
    if not classico.extras['botoes_no_centro']:
        notas.append('botoes_ok_fora_do_recorte_central')
    return notas


def montar_casos(grupos):
    """Os casos dos grupos pedidos. Os imports da aplicacao so acontecem aqui (nada de OCR nos testes)."""
    from app import (botao_livros, botoes_formulario, dominio, formulario_livros, leitura_resumo,
                     seletor_pasta, tela)

    def com_cache(funcao):
        def chamar(imagem, modo):
            with tela.reutilizar_ocr():
                return funcao(imagem)
        return chamar

    achou_dict = lambda valor: isinstance(valor, dict)
    achou = lambda valor: valor is not None
    casos = []
    if 'selecao' in grupos:
        casos.append(Caso('ler_selecao_com_ocr',
                          lambda imagem, modo: formulario_livros.ler_selecao_com_ocr(imagem),
                          positivo=achou_dict))
    if 'campos' in grupos:
        for livros in (True, False):
            casos.append(Caso(f'ler_campos(livros={livros})',
                              lambda imagem, modo, livros=livros: leitura_resumo.ler_campos(imagem, livros=livros),
                              preparar=leitura_resumo.esquecer_geometria, positivo=achou_dict))
    if 'resumo' in grupos:
        casos.append(Caso('formulario_resumo_reconhecido',
                          lambda imagem, modo: leitura_resumo.formulario_resumo_reconhecido(imagem),
                          positivo=achou))
    if 'avisos' in grupos:
        casos.append(Caso('_conferir_avisos', com_cache(botoes_formulario._conferir_avisos),
                          positivo=lambda valor: valor is True))
        casos.append(Caso('achar_ok_livros', lambda imagem, modo: botao_livros.achar_ok_livros(imagem),
                          positivo=achou))
    if 'seletor' in grupos:
        def medir(imagem, modo):
            # Aqui o "otimizado" e o argumento centro=True; o "classico" e a chamada sem ele.
            return (seletor_pasta.medir_dialogo(imagem, centro=True) if modo == OTIMIZADO
                    else seletor_pasta.medir_dialogo(imagem))
        extras = lambda detalhes, imagem: _extras_seletor(detalhes, imagem, tela, seletor_pasta._normalizar)
        casos.append(Caso('medir_dialogo(centro=True)', medir, simplificar=selecionar_seletor,
                          positivo=achou_dict, extras=extras, informativos=_informativos_seletor,
                          separar_dialogo=True))
        casos.append(Caso('_LeitorDialogo.ler',
                          lambda imagem, modo: seletor_pasta._LeitorDialogo().ler(imagem),
                          simplificar=selecionar_seletor, positivo=achou_dict, separar_dialogo=True))
    if 'texto' in grupos:
        for texto in TEXTOS:
            casos.append(Caso(f"_achar_texto_reforcado('{sem_acentos(texto)}')",
                              com_cache(lambda imagem, texto=texto: dominio._achar_texto_reforcado(
                                  imagem, texto, ocr_windows=True, escalas_adicionais=(4,))),
                              positivo=achou))
    return casos


# ---------------------------------------------------------------------------------------------
# A/B de um caso numa imagem
# ---------------------------------------------------------------------------------------------

def _rodar(caso, imagem, modo, contadores):
    return executar(lambda: caso.chamar(imagem, modo), modo, preparar=caso.preparar,
                    simplificar=caso.simplificar, positivo=caso.positivo,
                    extras=(lambda valor: caso.extras(valor, imagem)) if caso.extras else None,
                    contadores=contadores)


def rodar_caso(caso, imagem, nome_imagem, indice, contadores, repetir=True, rodar=_rodar):
    """Classico e otimizado sobre a mesma imagem (a ordem alterna para nao favorecer ninguem).

    Se divergirem, repete cada modo mais uma vez: se um modo nao repete o proprio resultado, a
    divergencia e ruido do OCR e nao do otimizador."""
    ordem = (CLASSICO, OTIMIZADO) if indice % 2 == 0 else (OTIMIZADO, CLASSICO)
    feitas = {modo: rodar(caso, imagem, modo, contadores) for modo in ordem}
    classico, otimizado = feitas[CLASSICO], feitas[OTIMIZADO]
    comparacao = comparar(classico, otimizado)
    repeticao = None
    if not comparacao.identico and repetir:
        classico2, otimizado2 = rodar(caso, imagem, CLASSICO, contadores), rodar(caso, imagem, OTIMIZADO, contadores)
        repeticao = {'ruido_classico': classico2.chave != classico.chave,
                     'ruido_otimizado': otimizado2.chave != otimizado.chave}
    linha = caso.nome
    if caso.separar_dialogo:
        linha += ' [com dialogo]' if classico.positivo else ' [sem dialogo]'
    notas = caso.informativos(classico, otimizado) if caso.informativos else []
    return Registro(linha, nome_imagem, classico, otimizado, comparacao, classico.positivo, repeticao, notas)


def rodar_memoria(imagem, nome_imagem, livros, contadores, funcoes=None):
    """Segunda chamada de `ler_campos` (otimizado) sobre a mesma imagem: usa a geometria lembrada e
    precisa devolver o mesmo da primeira."""
    if funcoes is None:
        from app import leitura_resumo
        funcoes = leitura_resumo
    primeira_eventos, segunda_eventos = [], []
    primeira = executar(lambda: funcoes.ler_campos(imagem, registrar=primeira_eventos.append, livros=livros),
                        OTIMIZADO, preparar=funcoes.esquecer_geometria, contadores=contadores,
                        positivo=lambda valor: isinstance(valor, dict))
    gravou = (bool(livros), imagem.size) in funcoes._GEOMETRIA_LEMBRADA
    segunda = executar(lambda: funcoes.ler_campos(imagem, registrar=segunda_eventos.append, livros=livros),
                       OTIMIZADO, contadores=contadores, positivo=lambda valor: isinstance(valor, dict))
    usou = any(isinstance(e, dict) and e.get('motivo') == 'geometria_lembrada' for e in segunda_eventos)
    return Registro(f'ler_campos(livros={livros}) 2a chamada com memoria', nome_imagem, primeira, segunda,
                    comparar(primeira, segunda), primeira.positivo, memoria={'gravou': gravou, 'usou': usou})


def aquecer_motores():
    """Uma leitura de cada motor (e do paralelo) numa imagem em branco, para a primeira medicao
    nao pagar o arranque do Tesseract, do OCR do Windows e das threads. Devolve (windows_ok, desligadas)."""
    from PIL import Image, ImageDraw
    from app import otimizacoes, tela
    imagem = Image.new('RGB', (320, 120), 'white')
    ImageDraw.Draw(imagem).text((10, 40), 'Aquecimento', fill='black')
    saida = io.StringIO()
    windows_ok = False
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
        try:
            tela._ler_dados_ocr(imagem, 2)
        except Exception:
            pass
        windows_ok = tela.ler_dados_ocr_windows(imagem, 2) is not None
        otimizacoes._forcado = True
        try:
            with tela.reutilizar_ocr():
                tela.pre_aquecer_ocr((imagem, [('tesseract', 2), ('windows', 2)]))
        except Exception:
            pass
    desligadas = dict(otimizacoes._desligadas)
    otimizacoes._desligadas.clear()
    otimizacoes._forcado = None
    return windows_ok, desligadas


def bloquear_pyautogui():
    """Este script so le arquivos PNG: troca o pyautogui por um modulo que recusa qualquer acao."""
    if 'pyautogui' in sys.modules:
        return
    import types
    falso = types.ModuleType('pyautogui')

    def recusar(*args, **kwargs):
        raise RuntimeError('pyautogui bloqueado: o comparador nao opera mouse nem teclado.')

    falso.__getattr__ = lambda nome: recusar
    sys.modules['pyautogui'] = falso


# ---------------------------------------------------------------------------------------------
# Relatorio (funcoes puras: so contagens, booleanos, duracoes e nomes)
# ---------------------------------------------------------------------------------------------

def aceleracao(classico, otimizado):
    return classico / otimizado if otimizado > 0 else None


def _fmt_acel(valor):
    return 'n/d' if valor is None else f'{valor:.2f}x'


def agrupar_por_linha(registros):
    linhas = {}
    for r in registros:
        linhas.setdefault(r.linha, []).append(r)
    return linhas


def _soma(registros, modo, atributo=None, contador=None):
    total = 0
    for r in registros:
        execucao = getattr(r, modo)
        total += execucao.duracao if atributo == 'duracao' else execucao.contadores.get(contador, 0)
    return total


def formatar_relatorio(registros, cabecalho=()):
    """Linhas do relatorio final. Nenhum conteudo de captura: so nomes, contagens e tempos."""
    saida = list(cabecalho)
    normais = [r for r in registros if r.memoria is None]
    com_memoria = [r for r in registros if r.memoria is not None]

    def tabela_ab(titulo, linhas, rotulo_a='classico (s)', rotulo_b='otimizado (s)'):
        saida.extend(['', SEPARADOR, titulo, SEPARADOR,
                      f"{'funcao':<54}{'imagens':>8}{'identicos':>10}{'diferentes':>11}"
                      f"{rotulo_a:>16}{rotulo_b:>16}{'aceleracao':>11}"])
        todos = []
        for nome, rs in linhas.items():
            todos.extend(rs)
            ident = sum(1 for r in rs if r.comparacao.identico)
            tc, to = _soma(rs, 'classico', 'duracao'), _soma(rs, 'otimizado', 'duracao')
            saida.append(f'{nome:<54}{len(rs):>8}{ident:>10}{len(rs) - ident:>11}{tc:>16.1f}{to:>16.1f}'
                         f'{_fmt_acel(aceleracao(tc, to)):>11}')
        if len(linhas) > 1:
            ident = sum(1 for r in todos if r.comparacao.identico)
            tc, to = _soma(todos, 'classico', 'duracao'), _soma(todos, 'otimizado', 'duracao')
            saida.append(f"{'TOTAL':<54}{len(todos):>8}{ident:>10}{len(todos) - ident:>11}{tc:>16.1f}{to:>16.1f}"
                         f'{_fmt_acel(aceleracao(tc, to)):>11}')

    linhas_normais = agrupar_por_linha(normais)
    if linhas_normais:
        tabela_ab('EQUIVALENCIA E TEMPO POR FUNCAO (tempos em segundos, indicativos: o computador estava ocupado)',
                  linhas_normais)
        saida.extend(['', SEPARADOR,
                      'TEMPO POR TIPO DE RESULTADO DO CLASSICO (positivo = reconheceu/achou; negativo = erro, vazio ou False)',
                      SEPARADOR,
                      f"{'funcao':<54}{'tipo':>9}{'imagens':>8}{'classico (s)':>14}{'otimizado (s)':>15}{'aceleracao':>11}"])
        for nome, rs in linhas_normais.items():
            for rotulo, selecionados in (('positivo', [r for r in rs if r.positivo]),
                                         ('negativo', [r for r in rs if not r.positivo])):
                if not selecionados:
                    continue
                tc, to = _soma(selecionados, 'classico', 'duracao'), _soma(selecionados, 'otimizado', 'duracao')
                saida.append(f'{nome:<54}{rotulo:>9}{len(selecionados):>8}{tc:>14.1f}{to:>15.1f}'
                             f'{_fmt_acel(aceleracao(tc, to)):>11}')
        saida.extend(['', SEPARADOR,
                      'CHAMADAS DE OCR (soma das rodadas; c = classico, o = otimizado)',
                      SEPARADOR,
                      f"{'funcao':<54}{'tess c':>8}{'tess o':>8}{'falha c':>9}{'falha o':>9}{'win c':>7}{'win o':>7}"
                      f"{'tmax c':>8}{'tmax o':>8}{'ocup c':>8}{'ocup o':>8}"])
        for nome, rs in linhas_normais.items():
            cel = [_soma(rs, 'classico', contador='tesseract'), _soma(rs, 'otimizado', contador='tesseract'),
                   _soma(rs, 'classico', contador='tesseract_falhas'), _soma(rs, 'otimizado', contador='tesseract_falhas'),
                   _soma(rs, 'classico', contador='windows'), _soma(rs, 'otimizado', contador='windows'),
                   _soma(rs, 'classico', contador='windows_tempo_limite'),
                   _soma(rs, 'otimizado', contador='windows_tempo_limite'),
                   _soma(rs, 'classico', contador='windows_ocupado'), _soma(rs, 'otimizado', contador='windows_ocupado')]
            saida.append(f'{nome:<54}' + ''.join(f'{v:>{w}}' for v, w in zip(cel, (8, 8, 9, 9, 7, 7, 8, 8, 8, 8))))
        saida.append('(tmax = leituras do OCR do Windows que estouraram o limite de tempo; ocup = recusadas por OCR ocupado)')
    if com_memoria:
        tabela_ab('SEGUNDA CHAMADA COM MEMORIA DA GEOMETRIA (otimizado nas duas; a 2a deve repetir a 1a)',
                  agrupar_por_linha(com_memoria), '1a chamada (s)', '2a chamada (s)')
        gravaram = sum(1 for r in com_memoria if r.memoria['gravou'])
        usaram = sum(1 for r in com_memoria if r.memoria['usou'])
        saida.append(f'Memoria gravada pela 1a chamada em {gravaram} de {len(com_memoria)} casos; '
                     f'usada pela 2a em {usaram} (so esses exercitam a geometria lembrada).')
    dialogo = [r for r in normais if r.linha.startswith('medir_dialogo')]
    if dialogo:
        com = [r for r in dialogo if r.positivo]
        saida.extend(['', f'PROCURAR PASTA: dialogo reconhecido pelo classico em {len(com)} de {len(dialogo)} imagens.'])
        if com:
            fora = sum(1 for r in com if 'arvore_fora_do_recorte_central' in r.informativos)
            saida.append(f'  arvore inteira dentro do recorte central em {len(com) - fora} de {len(com)}.')

    divergentes = [r for r in registros if not r.comparacao.identico]
    saida.extend(['', SEPARADOR, 'DIVERGENCIAS (sem conteudo: so funcao, arquivo e tipo)', SEPARADOR])
    if not divergentes:
        saida.append('nenhuma')
    for r in divergentes:
        partes = [f'{r.linha} :: {r.imagem}', f'tipo={r.comparacao.tipo}']
        if r.comparacao.delta is not None:
            partes.append(f'delta_max={r.comparacao.delta:g}')
        if r.comparacao.caminhos:
            partes.append('campos=' + ','.join(r.comparacao.caminhos))
        if r.classico.excecao or r.otimizado.excecao:
            partes.append(f'excecao_classico={r.classico.excecao or "-"} excecao_otimizado={r.otimizado.excecao or "-"}')
        if r.repeticao is not None:
            partes.append(f"repetindo: ruido_classico={r.repeticao['ruido_classico']} "
                          f"ruido_otimizado={r.repeticao['ruido_otimizado']}")
        saida.append('  ' + '; '.join(partes))
    informativos = [r for r in registros if r.informativos]
    if informativos:
        saida.extend(['', 'INFORMATIVOS (nao entram no codigo de saida)'])
        for r in informativos:
            saida.append(f"  {r.linha} :: {r.imagem}: {'; '.join(r.informativos)}")
    desligadas = [(r, modo) for r in registros for modo in (CLASSICO, OTIMIZADO) if getattr(r, modo).desligadas]
    if desligadas:
        saida.extend(['', 'OTIMIZACAO DESLIGADA SOZINHA DURANTE A RODADA (a medicao "otimizada" nao vale para esses casos)'])
        for r, modo in desligadas:
            saida.append(f"  {r.linha} :: {r.imagem} ({modo}): "
                         + ', '.join(f'{nome}({motivo})' for nome, motivo in getattr(r, modo).desligadas))
    ruidosos = [r for r in divergentes if r.repeticao and (r.repeticao['ruido_classico'] or r.repeticao['ruido_otimizado'])]
    saida.extend(['', SEPARADOR])
    if codigo_de_saida(registros) == 0:
        saida.append(f'RESULTADO: TUDO IDENTICO em {len(registros)} comparacoes.')
    else:
        saida.append(f'RESULTADO: {len(divergentes)} DIVERGENCIA(S) em {len(registros)} comparacoes '
                     f'({len(ruidosos)} com ruido do proprio OCR ao repetir; '
                     f'{len(divergentes) - len(ruidosos)} sem ruido ou nao repetida).')
    return saida


# ---------------------------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------------------------

def ler_argumentos(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--capturas', type=Path, default=CAPTURAS_PADRAO,
                        help='Pasta com os PNG das capturas (padrao: %(default)s).')
    parser.add_argument('--max', type=int, default=MAXIMO_PADRAO, dest='maximo',
                        help='Quantas imagens usar, espalhadas pela lista ordenada por nome (padrao: %(default)s). '
                             f'{OBRIGATORIA} entra sempre que existir.')
    parser.add_argument('--funcoes', nargs='+', default=None,
                        help='Grupos a rodar (padrao: todos): ' + ', '.join(GRUPOS)
                             + '. Aceita varios separados por espaco ou virgula.')
    parser.add_argument('--nome', nargs='+', default=None,
                        help='Usa so capturas cujo nome contem um destes trechos (antes de escolher as espacadas).')
    parser.add_argument('--listar', action='store_true', help='So mostra quais imagens seriam usadas.')
    parser.add_argument('--sem-repeticao', action='store_true',
                        help='Nao repete as leituras divergentes para separar ruido do OCR de defeito.')
    args = parser.parse_args(argv)
    if args.maximo < 1:
        parser.error('--max precisa ser pelo menos 1.')
    pedidos = []
    for valor in args.funcoes or ['todas']:
        for parte in valor.replace(',', ' ').split():
            parte = parte.casefold()
            if parte == 'todas':
                pedidos = list(GRUPOS)
                break
            if parte not in GRUPOS:
                parser.error(f"--funcoes: '{parte}' nao existe. Use: todas, " + ', '.join(GRUPOS))
            pedidos.append(parte)
    args.grupos = [g for g in GRUPOS if g in pedidos]
    return args


def _carregar(caminho):
    from PIL import Image
    with Image.open(caminho) as arquivo:
        return arquivo.convert('RGB')


def executar_comparacao(args, pasta, total_elegiveis, escolhidas):
    try:
        from app import otimizacoes  # noqa: F401
    except ImportError:
        print('app/otimizacoes.py nao encontrado: rode este script numa copia do projeto que tenha as '
              'otimizacoes (commit bd830a8 ou posterior).')
        return 2
    contadores = Contadores()
    instalar_contadores(contadores)
    windows_ok, desligadas = aquecer_motores()
    casos = montar_casos(args.grupos)
    cabecalho = [SEPARADOR, 'COMPARACAO CLASSICO x OTIMIZADO DAS LEITURAS OCR',
                 f'capturas: {pasta}', f'elegiveis (>= {LARGURA_MINIMA}x{ALTURA_MINIMA}): {total_elegiveis}; '
                 f'usadas: {len(escolhidas)}', f"grupos: {', '.join(args.grupos)}",
                 f'OCR do Windows disponivel: {windows_ok}; CPUs logicas: {os.cpu_count()}; '
                 f'python: {sys.version.split()[0]}']
    if desligadas:
        cabecalho.append('AVISO: o paralelo se desligou sozinho no aquecimento: ' + ', '.join(sorted(desligadas)))
    print('\n'.join(cabecalho), flush=True)
    registros = []
    contador_global = 0
    interrompido = False
    try:
        for posicao, nome in enumerate(escolhidas, 1):
            imagem = _carregar(pasta / nome)
            for caso in casos:
                registro = rodar_caso(caso, imagem, nome, contador_global, contadores, not args.sem_repeticao)
                contador_global += 1
                registros.append(registro)
                _imprimir_progresso(posicao, len(escolhidas), registro)
            if 'campos' in args.grupos:
                for livros in (True, False):
                    registro = rodar_memoria(imagem, nome, livros, contadores)
                    registros.append(registro)
                    _imprimir_progresso(posicao, len(escolhidas), registro)
    except KeyboardInterrupt:
        interrompido = True
        print('\nInterrompido: relatorio parcial abaixo.', flush=True)
    finally:
        from app import otimizacoes
        otimizacoes._forcado = None
        otimizacoes._desligadas.clear()
    print('\n'.join(formatar_relatorio(registros, [''])), flush=True)
    if interrompido:
        return 130
    return codigo_de_saida(registros)


def _imprimir_progresso(posicao, total, registro):
    if registro.comparacao.identico:
        situacao = 'IDENTICO'
    else:
        situacao = f'DIFERENTE ({registro.comparacao.tipo})'
    print(f'[{posicao:>2}/{total}] {registro.imagem} :: {registro.linha}: '
          f'{registro.classico.duracao:.1f}s x {registro.otimizado.duracao:.1f}s {situacao}', flush=True)


def main(argv=None):
    args = ler_argumentos(argv)
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    pasta = args.capturas
    if pasta == CAPTURAS_PADRAO and not pasta.is_dir() and (RAIZ / 'capturas').is_dir():
        pasta = RAIZ / 'capturas'  # outra maquina: usa as capturas do proprio projeto
    if not pasta.is_dir():
        print(f'Pasta de capturas nao encontrada: {pasta}')
        return 2
    nomes, ignorados = listar_candidatas(pasta, args.nome)
    if not nomes:
        print(f'Nenhuma captura PNG com largura >= {LARGURA_MINIMA} e altura >= {ALTURA_MINIMA} em {pasta}.')
        return 2
    escolhidas = escolher_imagens(nomes, args.maximo)
    if args.listar:
        print(f'{len(nomes)} elegiveis ({ignorados} ilegiveis ignoradas); {len(escolhidas)} escolhidas:')
        print('\n'.join(escolhidas))
        return 0
    bloquear_pyautogui()
    return executar_comparacao(args, pasta, len(nomes), escolhidas)


if __name__ == '__main__':
    sys.exit(main())
