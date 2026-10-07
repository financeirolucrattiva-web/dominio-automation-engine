"""PP-OCRv5 mobile CPU opcional, somente para avaliação local de imagens.

Não captura tela, não envia dados e não participa da automação existente.
Os modelos devem ter sido baixados previamente; a criação é preguiçosa.
"""

from collections.abc import Mapping
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
import math
import os
from pathlib import Path


CAMINHO_MODELOS = Path(__file__).resolve().parents[1] / "data" / "modelos_ocr"
NOMES_MODELOS = ("PP-OCRv5_mobile_det", "latin_PP-OCRv5_mobile_rec")
ARQUIVOS_MODELO = ("inference.json", "inference.pdiparams", "inference.yml")


class ErroOCRPaddle(RuntimeError):
    """Diagnóstico fixo, sem texto, caminhos ou representação do modelo."""


@dataclass(frozen=True)
class TextoOCR:
    texto: str
    confianca: float
    caixa: tuple[float, float, float, float]


@contextmanager
def _execucao_local():
    """Inibe consulta ao Hub e mensagens do fornecedor durante a inferência."""
    valores = {"HF_HUB_OFFLINE": "1", "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"}
    anteriores = {nome: os.environ.get(nome) for nome in valores}
    os.environ.update(valores)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            yield
    finally:
        for nome, valor in anteriores.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor


def _numero(valor):
    if isinstance(valor, (bool, str, bytes)):
        raise ValueError
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError
    return numero


def _lista(valor):
    if isinstance(valor, (str, bytes, Mapping)):
        raise ValueError
    return list(valor)


def _caixa(valor, tamanho, poligono):
    pontos = _lista(valor)
    if poligono:
        if len(pontos) != 4:
            raise ValueError
        coordenadas = [_lista(ponto) for ponto in pontos]
        if any(len(ponto) != 2 for ponto in coordenadas):
            raise ValueError
        xs = [_numero(ponto[0]) for ponto in coordenadas]
        ys = [_numero(ponto[1]) for ponto in coordenadas]
        caixa = min(xs), min(ys), max(xs), max(ys)
    else:
        if len(pontos) != 4:
            raise ValueError
        caixa = tuple(_numero(numero) for numero in pontos)
    esquerda, topo, direita, baixo = caixa
    largura, altura = tamanho
    if not (0 <= esquerda < direita <= largura and 0 <= topo < baixo <= altura):
        raise ValueError
    return caixa


def normalizar_resultado(resultado, tamanho):
    """Exige textos, scores e geometria concordantes na imagem original.

    Um resultado malformado nunca é tratado como uma leitura vazia válida.
    Campos auxiliares do Paddle não são usados nem expostos.
    """
    try:
        largura, altura = tamanho
        if (isinstance(largura, bool) or isinstance(altura, bool)
                or not isinstance(largura, int) or not isinstance(altura, int)
                or largura <= 0 or altura <= 0 or not isinstance(resultado, Mapping)):
            raise ValueError
        textos = _lista(resultado["rec_texts"])
        scores = _lista(resultado["rec_scores"])
        geometrias = []
        for chave, poligono in (("rec_polys", True), ("rec_boxes", False)):
            if chave in resultado and resultado[chave] is not None:
                valores = _lista(resultado[chave])
                if len(valores) != len(textos):
                    raise ValueError
                geometrias.append([_caixa(valor, tamanho, poligono) for valor in valores])
        if len(scores) != len(textos) or not geometrias:
            raise ValueError
        if len(geometrias) == 2 and geometrias[0] != geometrias[1]:
            raise ValueError
        normalizado = []
        for indice, texto in enumerate(textos):
            if not isinstance(texto, str):
                raise ValueError
            score = _numero(scores[indice])
            if not 0 <= score <= 1:
                raise ValueError
            if texto.strip():
                normalizado.append(TextoOCR(texto.strip(), score, geometrias[0][indice]))
        return tuple(normalizado)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ErroOCRPaddle("PaddleOCR devolveu texto, confiança ou coordenadas inconsistentes.") from None


def criar_processador(pasta_modelos=CAMINHO_MODELOS):
    """Não solicita autodownload: usa dois diretórios de inferência locais."""
    pasta_modelos = Path(pasta_modelos)
    diretorios = [pasta_modelos / nome for nome in NOMES_MODELOS]
    if any(not (pasta / arquivo).is_file() or (pasta / arquivo).stat().st_size == 0
           for pasta in diretorios for arquivo in ARQUIVOS_MODELO):
        raise ErroOCRPaddle("Modelos locais ausentes ou incompletos. Execute Instalar OCR Paddle.bat.")
    try:
        with _execucao_local():
            from paddleocr import PaddleOCR
            return PaddleOCR(
                device="cpu",
                # Smoke CPU com estes pesos reproduziu uma falha de
                # conversão PIR no executor OneDNN. Mantém inferência
                # padrão até a otimização ser validada separadamente.
                enable_mkldnn=False,
                text_detection_model_name=NOMES_MODELOS[0],
                text_detection_model_dir=str(diretorios[0]),
                text_recognition_model_name=NOMES_MODELOS[1],
                text_recognition_model_dir=str(diretorios[1]),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
    except ImportError:
        raise ErroOCRPaddle("PaddleOCR opcional não está instalado. Execute Instalar OCR Paddle.bat.") from None
    except Exception:
        raise ErroOCRPaddle("Não consegui carregar os modelos locais do PaddleOCR em CPU.") from None


class OCRPaddleCPU:
    """Reutiliza um único processador; não importa Paddle até a primeira leitura."""

    def __init__(self, pasta_modelos=CAMINHO_MODELOS, fabrica=None):
        self.pasta_modelos = pasta_modelos
        self._fabrica = fabrica or criar_processador
        self._processador = None

    def reconhecer(self, imagem):
        from PIL import Image
        if not isinstance(imagem, Image.Image) or min(imagem.size) <= 0:
            raise ErroOCRPaddle("Imagem local inválida para avaliação de OCR.")
        if self._processador is None:
            self._processador = self._fabrica(self.pasta_modelos)
        try:
            import numpy as np
            # Paddle recebe pixels em memória, nunca o caminho privado da imagem.
            pixels = np.asarray(imagem.convert("RGB"))[:, :, ::-1].copy()
            with _execucao_local():
                resultados = list(self._processador.predict(input=pixels))
            if len(resultados) != 1:
                raise ErroOCRPaddle("PaddleOCR devolveu uma quantidade inesperada de imagens.")
            return normalizar_resultado(resultados[0], imagem.size)
        except ErroOCRPaddle:
            raise
        except Exception:
            raise ErroOCRPaddle("PaddleOCR não conseguiu concluir a leitura local em CPU.") from None
