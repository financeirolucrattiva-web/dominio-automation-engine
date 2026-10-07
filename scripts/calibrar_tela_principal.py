"""Mede localmente a tela principal humana confirmada; não guarda imagens."""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import tela_principal


def calibrar(capturar, identificar_janela, em_foco, conferir_cabecalho,
             caminho=tela_principal.ARQUIVO_REFERENCIA):
    """Só grava após duas capturas compatíveis, com foco e cabeçalho."""
    janela = identificar_janela()
    if janela is None or not em_foco(janela):
        raise ValueError("Não confirmei a janela do Domínio em primeiro plano.")
    primeira = capturar()
    if not em_foco(janela) or not conferir_cabecalho(primeira):
        raise ValueError("Não confirmei o cabeçalho do Domínio na captura.")
    referencia = tela_principal.construir_referencia(primeira)
    if not em_foco(janela):
        raise ValueError("O foco mudou durante a medição; a referência anterior foi preservada.")
    time.sleep(0.3)
    if not em_foco(janela):
        raise ValueError("O foco mudou antes da segunda captura.")
    segunda = capturar()
    if not em_foco(janela) or not conferir_cabecalho(segunda):
        raise ValueError("Não confirmei o Domínio na segunda captura.")
    if not tela_principal.corresponde(segunda, referencia):
        raise ValueError("A área azul mudou entre capturas; feche as janelas sobrepostas e tente novamente.")
    if not em_foco(janela):
        raise ValueError("O foco mudou antes de salvar a referência.")
    tela_principal.salvar_referencia(referencia, caminho)
    return referencia


def aguardar_dominio(capturar, identificar_janela, em_foco, conferir_cabecalho,
                     tentativas=30, intervalo=0.5):
    """Aguarda o operador selecionar o Domínio, sem clicar ou enviar teclas."""
    for tentativa in range(tentativas):
        janela = identificar_janela()
        if janela is not None and em_foco(janela):
            imagem = capturar()
            if conferir_cabecalho(imagem) and em_foco(janela):
                return True
        if tentativa + 1 < tentativas:
            time.sleep(intervalo)
    return False


def _restaurar_console():
    # Restaura somente o console deste script para mostrar o resultado.
    try:
        import ctypes
        from ctypes import wintypes
        obter_console = ctypes.windll.kernel32.GetConsoleWindow
        obter_console.argtypes = []
        obter_console.restype = wintypes.HWND
        mostrar = ctypes.windll.user32.ShowWindow
        mostrar.argtypes = [wintypes.HWND, ctypes.c_int]
        mostrar.restype = wintypes.BOOL
        hwnd = obter_console()
        if hwnd:
            mostrar(hwnd, 9)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true", help="Confere a referência existente sem recalibrar ou enviar cliques.")
    args = parser.parse_args()
    from app import interacao, tela

    def cabecalho(imagem):
        topo = tela.recortar_topo(imagem)
        return all(tela.achar_texto(topo, alvo, escala=2) is not None
                   for alvo in ("Domínio", "Escrita Fiscal", "Relatórios", "Movimentos"))

    if not args.verificar:
        print("Deixe o Domínio maximizado na tela principal azul, sem relatório, diálogo ou menu aberto.")
        print("A referência guarda somente medidas e cor; a imagem e os dados da empresa não serão salvos.")
        try:
            input("Pressione Enter aqui e volte ao Domínio com Alt+Tab. Depois aguarde sem mexer no mouse ou teclado.")
        except (EOFError, KeyboardInterrupt):
            print("Calibração cancelada; referência anterior preservada.")
            return 1

    status = 1
    try:
        interacao._minimizar_console_proprio()
        if not aguardar_dominio(tela.capturar_tela, interacao.identificar_janela_dominio_atual,
                                interacao.janela_dominio_em_foco, cabecalho):
            raise ValueError("Não reconheci o Domínio em primeiro plano. Selecione sua janela e tente novamente.")
        if args.verificar:
            referencia = tela_principal.carregar_referencia()
            janela = interacao.identificar_janela_dominio_atual()
            if referencia is None or janela is None or not interacao.janela_dominio_em_foco(janela):
                raise ValueError("Referência ou janela em foco indisponível. Calibre a tela principal primeiro.")
            for tentativa in range(2):
                imagem = tela.capturar_tela()
                if (not cabecalho(imagem) or not tela_principal.corresponde(imagem, referencia)
                        or not interacao.janela_dominio_em_foco(janela)):
                    raise ValueError("A tela atual não corresponde à referência da tela principal.")
                if tentativa == 0:
                    time.sleep(0.3)
            print("Tela principal reconhecida em duas capturas, com foco confirmado.")
        else:
            referencia = calibrar(tela.capturar_tela, interacao.identificar_janela_dominio_atual,
                                  interacao.janela_dominio_em_foco, cabecalho)
            print("Referência local salva em data/tela_principal.json.")
            print(f"Tamanho da captura: {referencia['tamanho']}; área azul medida: {referencia['retangulo']}.")
            print("SPED, Contribuições e Livros Fiscais usarão essa referência para verificar o retorno.")
        status = 0
    except ValueError as erro:
        print(f"Verificação não concluída: {erro}")
    except Exception as erro:
        print(f"Não consegui concluir a medição ({type(erro).__name__}); confira o resultado antes de continuar.")
    finally:
        _restaurar_console()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
