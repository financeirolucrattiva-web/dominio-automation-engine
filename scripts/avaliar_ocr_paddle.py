"""Compara PP-OCRv5 CPU e Tesseract em uma imagem local, sem operar o Domínio."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ocr_paddle import ErroOCRPaddle, OCRPaddleCPU, normalizar_resultado


class ErroAvaliacao(RuntimeError):
    """Mensagem segura, sem conteúdo fiscal ou caminhos locais."""


@dataclass(frozen=True)
class ResumoOCR:
    motor: str
    segundos_inicial: float
    segundos_quentes: tuple[float, float]
    quantidades: tuple[int, int, int]
    alvo_encontrado: tuple[bool, bool, bool] | None
    ocorrencias_alvo: tuple[int, int, int] | None = None


def localizar_alvo(textos, alvo):
    """Comparação do alvo com até quatro segmentos adjacentes; não clica."""
    if not isinstance(alvo, str) or not alvo.strip():
        raise ErroAvaliacao("Informe um alvo de texto não vazio.")
    alvo = alvo.strip().casefold()
    encontrados = []
    for quantidade in range(1, 5):
        for inicio in range(len(textos) - quantidade + 1):
            janela = textos[inicio:inicio + quantidade]
            if alvo in " ".join(item.texto for item in janela).casefold():
                caixa = (min(item.caixa[0] for item in janela),
                         min(item.caixa[1] for item in janela),
                         max(item.caixa[2] for item in janela),
                         max(item.caixa[3] for item in janela))
                encontrados.append(caixa)
        if encontrados:
            break
    return tuple(encontrados)


def _configurar_tesseract(pytesseract):
    if shutil.which("tesseract") is not None:
        return
    configurado = Path(__file__).resolve().parents[1] / "data" / "tesseract_caminho.txt"
    candidatos = []
    try:
        if configurado.is_file():
            candidatos.append(configurado.read_text(encoding="utf-8").strip())
    except OSError:
        pass
    candidatos.extend((r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                       r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"))
    for candidato in candidatos:
        if candidato and Path(candidato).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidato
            return
    raise ErroAvaliacao("Tesseract não encontrado. Confira a instalação e data/tesseract_caminho.txt.")


def reconhecer_tesseract(imagem):
    """Mesmo idioma da automação, sem importar app.tela ou APIs Windows."""
    try:
        import pytesseract
        _configurar_tesseract(pytesseract)
        dados = pytesseract.image_to_data(imagem, lang="por", output_type=pytesseract.Output.DICT)
        chaves = ("text", "conf", "left", "top", "width", "height")
        listas = [list(dados[chave]) for chave in chaves]
        if len({len(valores) for valores in listas}) != 1:
            raise ValueError
        resultado = []
        for indice, texto in enumerate(listas[0]):
            if not isinstance(texto, str):
                raise ValueError
            if not texto.strip():
                continue
            score = float(listas[1][indice]) / 100
            esquerda, topo, largura, altura = [float(valores[indice]) for valores in listas[2:]]
            # Reusa a mesma validação finita de confiança/geometria do Paddle.
            resultado.extend(normalizar_resultado({
                "rec_texts": [texto], "rec_scores": [score],
                "rec_boxes": [[esquerda, topo, esquerda + largura, topo + altura]],
            }, imagem.size))
        return tuple(resultado)
    except ErroAvaliacao:
        raise
    except ImportError:
        raise ErroAvaliacao("Dependências básicas do Tesseract ausentes. Execute Atualizar.bat.") from None
    except Exception:
        raise ErroAvaliacao("Tesseract não conseguiu ler a imagem local em português.") from None


def avaliar(imagem, alvo=None, paddle=None, tesseract=None, relogio=time.perf_counter):
    """Uma leitura inicial e duas aquecidas por motor; só retorna agregados."""
    if alvo is not None and not alvo.strip():
        raise ErroAvaliacao("Informe um alvo de texto não vazio.")
    paddle = paddle or OCRPaddleCPU().reconhecer
    tesseract = tesseract or reconhecer_tesseract
    resumos = []
    for nome, reconhecer in (("PP-OCRv5 mobile CPU", paddle), ("Tesseract por", tesseract)):
        tempos, quantidades, encontrados, ocorrencias = [], [], [], []
        for _ in range(3):
            inicio = relogio()
            textos = reconhecer(imagem)
            tempos.append(relogio() - inicio)
            quantidades.append(len(textos))
            if alvo is not None:
                quantidade_alvos = len(localizar_alvo(textos, alvo))
                ocorrencias.append(quantidade_alvos)
                encontrados.append(quantidade_alvos == 1)
        resumos.append(ResumoOCR(nome, tempos[0], tuple(tempos[1:]), tuple(quantidades),
                               tuple(encontrados) if alvo is not None else None,
                               tuple(ocorrencias) if alvo is not None else None))
    return tuple(resumos)


def _escolher_imagem():
    try:
        import tkinter as tk
        from tkinter import filedialog
        janela = tk.Tk()
        janela.withdraw()
        try:
            return filedialog.askopenfilename(title="Escolher captura local para avaliar OCR",
                                              filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
        finally:
            janela.destroy()
    except Exception:
        raise ErroAvaliacao("Não consegui abrir o seletor local de imagens.") from None


def _carregar_imagem(caminho):
    try:
        from PIL import Image
        if Path(caminho).suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError
        with Image.open(caminho) as imagem:
            if imagem.format not in ("PNG", "JPEG"):
                raise ValueError
            imagem.load()
            return imagem.convert("RGB")
    except Exception:
        raise ErroAvaliacao("Não consegui abrir a imagem local. Escolha uma captura PNG ou JPG válida.") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--imagem", help="Arquivo PNG/JPG local; não é enviado nem copiado.")
    origem.add_argument("--escolher", action="store_true", help="Abre o seletor local de arquivos.")
    parser.add_argument("--alvo", help="Rótulo para comparação local; texto lido e alvo não são impressos.")
    args = parser.parse_args(argv)
    try:
        caminho = _escolher_imagem() if args.escolher else args.imagem
        if not caminho:
            print("Avaliação cancelada; nenhuma imagem foi lida.")
            return 1
        imagem = _carregar_imagem(caminho)
        print("Avaliação local em CPU: uma leitura inicial e duas aquecidas por motor.")
        resumos = avaliar(imagem, args.alvo)
        for resumo in resumos:
            print(f"{resumo.motor}: inicial={resumo.segundos_inicial:.3f}s; "
                  f"aquecidas={resumo.segundos_quentes[0]:.3f}s/{resumo.segundos_quentes[1]:.3f}s; "
                  f"segmentos={resumo.quantidades}.")
            if resumo.alvo_encontrado is not None:
                print(f"Alvo único encontrado com coordenadas válidas: {resumo.alvo_encontrado}; "
                      f"ocorrências={resumo.ocorrencias_alvo}.")
        print("RAM não medida; GPU/VRAM não usadas pelo Paddle configurado em CPU.")
        print("Contagens e alvos não medem precisão geral. Nenhum resultado substitui o OCR da automação.")
        return 0
    except (ErroAvaliacao, ErroOCRPaddle) as erro:
        print(f"Avaliação não concluída: {erro}")
        return 1
    except (Exception, KeyboardInterrupt):
        print("Avaliação interrompida ou não concluída; nenhuma imagem ou texto foi exportado.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
