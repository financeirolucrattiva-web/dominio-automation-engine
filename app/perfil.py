"""Onde o tempo vai: contadores leves de leituras OCR e capturas de tela por etapa.

Só números (quantas chamadas, quantos segundos); nenhum conteúdo de tela ou de OCR. Mede o motor de
verdade (`pytesseract.image_to_data` e `LEITOR_WINDOWS.executar`), então leituras servidas pelo
cache de checagem não contam. Com OCR em paralelo a soma dos segundos passa do tempo real ("cpu").
A saída (`[perfil] ...`) vai para o console e para `data/servidor_detalhes.log`.
"""
import threading
import time

_trava = threading.Lock()
_totais = {}
_instalado = False


def _medir(nome, funcao):
    def medida(*args, **kwargs):
        inicio = time.perf_counter()
        try:
            return funcao(*args, **kwargs)
        finally:
            gasto = time.perf_counter() - inicio
            with _trava:
                total = _totais.setdefault(nome, [0, 0.0])
                total[0] += 1
                total[1] += gasto
    medida.__wrapped__ = funcao
    return medida


def instalar():
    """Envolve as funções que executam OCR/captura de verdade. Idempotente; nunca levanta erro."""
    global _instalado
    if _instalado:
        return
    _instalado = True
    try:
        import pytesseract
        from app import tela
        from app.ocr_limites import LEITOR_WINDOWS
        if not hasattr(pytesseract.image_to_data, '__wrapped__'):
            pytesseract.image_to_data = _medir('tesseract', pytesseract.image_to_data)
        if not hasattr(LEITOR_WINDOWS.executar, '__wrapped__'):
            LEITOR_WINDOWS.executar = _medir('windows', LEITOR_WINDOWS.executar)
        if not hasattr(tela.capturar_tela, '__wrapped__'):
            tela.capturar_tela = _medir('captura', tela.capturar_tela)
    except Exception:
        pass  # medição é só diagnóstico: nunca atrapalha a rotina


def instantaneo():
    with _trava:
        return {nome: tuple(valor) for nome, valor in _totais.items()}


def diferenca(antes, depois):
    resultado = {}
    for nome, (chamadas, segundos) in depois.items():
        c0, s0 = antes.get(nome, (0, 0.0))
        if chamadas - c0:
            resultado[nome] = (chamadas - c0, segundos - s0)
    return resultado


def texto(delta):
    """`ocr 12x 31s-cpu (tesseract 8x/25s, windows 4x/6s) | captura 9x/1s`."""
    ocr = [(n, v) for n, v in sorted(delta.items()) if n in ('tesseract', 'windows')]
    partes = []
    if ocr:
        partes.append(f"ocr {sum(v[0] for _, v in ocr)}x {sum(v[1] for _, v in ocr):.0f}s-cpu ("
                      + ", ".join(f"{n} {v[0]}x/{v[1]:.0f}s" for n, v in ocr) + ")")
    if 'captura' in delta:
        partes.append(f"captura {delta['captura'][0]}x/{delta['captura'][1]:.1f}s")
    return " | ".join(partes) or "sem leituras OCR"
